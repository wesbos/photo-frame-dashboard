#!/system/bin/sh
# shellcheck shell=ksh
set -u
set -o pipefail
set -f
# MI86: keep public key, logs and rollback snapshots in a dedicated card directory.
card=$(dirname "$0")
d="$card/mi86-adb-v2"
out="$d/result.txt"
keys=/data/misc/adb/adb_keys
expected_fingerprint='rockchip/rk312x/rk312x:6.0.1/MXC89K/user.zcx.20250822.060141:user/release-keys'

# Check before opening result.txt: repeated triggers preserve the first result.
[ -e "$d/done" ] && exit 0
[ -e "$d/started" ] && exit 0
touch "$d/started" || exit 1

main() {
  attempt="$d/attempt.$$"
  stage=
  mutated=0
  committed=0
  baseline_state=
  metadata=
  label=
  date
  id
  [ "$(id -u)" = 0 ] || fail 'root is required'
  fingerprint=$(getprop ro.build.fingerprint) || fail 'cannot read firmware fingerprint'
  printf 'ro.build.fingerprint=%s\n' "$fingerprint"
  [ "$fingerprint" = "$expected_fingerprint" ] \
    || fail 'firmware fingerprint mismatch; no device configuration changes made'
  echo '--- existing ADB security and network properties ---'
  for prop in ro.adb.secure ro.secure ro.debuggable dhcp.wlan0.ipaddress; do
    printf '%s=' "$prop"
    getprop "$prop"
  done
  for required_tool in stat ls cp cmp mktemp chown chmod chcon getprop setprop stop start sync od tr cat; do
    command -v "$required_tool" >/dev/null 2>&1 || fail "required Android tool unavailable: $required_tool"
  done
  mkdir "$attempt" || fail 'cannot create attempt snapshot directory'
  trap 'on_exit' EXIT
  trap 'exit 1' HUP INT TERM

  # This is a card-side trigger, not a device configuration change.
  rm -f "$card/Frameo_utilities/frameo_utilities.config" || fail 'cannot disarm trigger'
  [ ! -e "$card/Frameo_utilities/frameo_utilities.config" ] || fail 'trigger still exists'
  choose_base64_tool || fail 'no working base64 decoder; see base64.stderr'
  validate_keys "$d/adbkey.pub" supplied || fail 'invalid supplied public key'
  [ -L "$keys" ] && fail 'active key path is a symlink'
  if [ ! -e "$keys" ]; then
    # A clean device may have no adb_keys file at all. Do not require prior
    # authorization; create the file with the platform defaults.
    baseline_state=absent
    metadata='1000 2000 640'
    label='u:object_r:adb_keys_file:s0'
    : > "$attempt/adb_keys.raw" || fail 'cannot record absent key baseline'
    : > "$attempt/adb_keys.clean" || fail 'cannot record clean baseline'
  else
    [ -f "$keys" ] || fail 'active key path is not a regular file'
    metadata=$(stat -c '%u %g %a' "$keys") || fail 'cannot read key metadata'
    label=$(get_label "$keys") || fail 'cannot read key SELinux label'
    cp "$keys" "$attempt/adb_keys.raw" || fail 'cannot snapshot active keys'
    cmp -s "$keys" "$attempt/adb_keys.raw" || fail 'active keys changed during snapshot'
    check_metadata "$keys" || fail 'key metadata changed during snapshot'
    # Only the known malformed vendor prefix is removed. Keep all other lines.
    clean_current "$attempt/adb_keys.raw" > "$attempt/adb_keys.clean" || fail 'cannot clean current snapshot'
    if [ -s "$attempt/adb_keys.raw" ]; then
      baseline_state=present
      validate_keys "$attempt/adb_keys.clean" current || fail 'invalid current key snapshot'
    else
      baseline_state=empty
    fi
  fi
  printf '%s\n' "$baseline_state" > "$attempt/baseline.state" || fail 'cannot save baseline state'
  printf '%s\n' "$metadata" > "$attempt/metadata" || fail 'cannot save metadata'
  printf '%s\n' "$label" > "$attempt/selinux" || fail 'cannot save SELinux label'
  service_port=$(getprop service.adb.tcp.port) || fail 'cannot read service port'
  persist_port=$(getprop persist.adb.tcp.port) || fail 'cannot read persistent port'
  adbd_state=$(getprop init.svc.adbd) || fail 'cannot read adbd state'
  adbd_transition_waits=0
  while [ "$adbd_state" != running ] && [ "$adbd_state" != stopped ]; do
    adbd_transition_waits=$((adbd_transition_waits + 1))
    [ "$adbd_transition_waits" -le 10 ] || fail "adbd stayed in transitional state: $adbd_state; reboot before retrying"
    sleep 1
    adbd_state=$(getprop init.svc.adbd) || fail 'cannot refresh adbd state'
  done
  printf '%s\n' "$service_port" > "$attempt/service.adb.tcp.port" || fail 'cannot save service port'
  printf '%s\n' "$persist_port" > "$attempt/persist.adb.tcp.port" || fail 'cannot save persistent port'
  printf '%s\n' "$adbd_state" > "$attempt/init.svc.adbd" || fail 'cannot save adbd state'
  touch "$attempt/snapshot.complete" || fail 'cannot complete snapshot'

  # Preserve the original recovery state. A clean absent/empty baseline has no
  # key backup; a sidecar records that explicitly instead of inventing keys.
  backup_state_file="$d/adb_keys.before.state"
  if [ -e "$backup_state_file" ]; then
    [ -f "$backup_state_file" ] && [ ! -L "$backup_state_file" ] || fail 'invalid recovery state file'
    backup_state=$(cat "$backup_state_file") || fail 'cannot read recovery state'
    case "$backup_state" in absent|empty|present) ;; *) fail 'invalid recovery state';;
    esac
  elif [ -e "$d/adb_keys.before" ]; then
    if [ ! -f "$d/adb_keys.before" ] || [ -L "$d/adb_keys.before" ]; then
      fail 'invalid existing recovery backup'
    fi
    [ -s "$d/adb_keys.before" ] || fail 'invalid existing recovery backup: legacy empty state missing'
    backup_state=present
    printf '%s\n' "$backup_state" > "$backup_state_file" || fail 'cannot save recovery state'
  else
    backup_state=$baseline_state
    case "$backup_state" in
      present)
        cp "$attempt/adb_keys.raw" "$attempt/adb_keys.recovery.pending" || fail 'cannot stage recovery backup'
        cmp -s "$attempt/adb_keys.raw" "$attempt/adb_keys.recovery.pending" || fail 'recovery backup is incomplete'
        mv "$attempt/adb_keys.recovery.pending" "$d/adb_keys.before" || fail 'cannot publish recovery backup'
        ;;
      empty)
        : > "$attempt/adb_keys.recovery.pending" || fail 'cannot stage empty recovery backup'
        mv "$attempt/adb_keys.recovery.pending" "$d/adb_keys.before" || fail 'cannot publish empty recovery backup'
        ;;
      absent) ;;
      *) fail 'invalid clean baseline state';;
    esac
    printf '%s\n' "$backup_state" > "$backup_state_file" || fail 'cannot save recovery state'
  fi
  case "$backup_state" in
    absent)
      [ ! -e "$d/adb_keys.before" ] || fail 'recovery state absent but key backup exists'
      ;;
    empty)
      [ -f "$d/adb_keys.before" ] && [ ! -L "$d/adb_keys.before" ] && [ ! -s "$d/adb_keys.before" ] \
        || fail 'invalid empty recovery backup'
      ;;
    present)
      [ -f "$d/adb_keys.before" ] && [ ! -L "$d/adb_keys.before" ] || fail 'invalid recovery backup'
      clean_current "$d/adb_keys.before" > "$attempt/adb_keys.recovery.clean" || fail 'cannot inspect existing recovery backup'
      validate_keys "$attempt/adb_keys.recovery.clean" recovery || fail 'invalid existing recovery backup' 
      ;;
  esac
  # Cleaning supplies line boundaries; deduplicate only the exact key blob.
  merge_current || fail 'cannot merge keys'
  validate_keys "$attempt/adb_keys.merged" merged || fail 'invalid merged key file'
  stage=$(mktemp "$keys.frameo.XXXXXX") || fail 'cannot create adjacent key staging file'
  prepare_stage "$attempt/adb_keys.merged" || fail 'cannot prepare staged keys'
  sync || fail 'cannot persist recovery snapshots'
  # Detect concurrent edits immediately before replacement.
  case "$baseline_state" in
    absent)
      [ ! -e "$keys" ] || fail 'active key path appeared before replacement'
      ;;
    empty)
      if [ ! -f "$keys" ] || [ -s "$keys" ]; then
        fail 'empty key baseline changed before replacement'
      fi
      check_metadata "$keys" || fail 'empty key baseline changed before replacement'
      ;;
    present)
      cmp -s "$keys" "$attempt/adb_keys.raw" || fail 'active keys changed before replacement'
      check_metadata "$keys" || fail 'key metadata changed before replacement'
      ;;
    *) fail 'invalid key baseline state';;
  esac
  # An ambiguous/interrupted rename also requires rollback.
  mutated=1
  mv -f "$stage" "$keys" || fail 'key replacement failed'
  stage=
  setprop service.adb.tcp.port 5555 || fail 'cannot set service port'
  setprop persist.adb.tcp.port 5555 || fail 'cannot set persistent port'
  stop adbd || fail 'cannot stop adbd'
  wait_state stopped || fail 'adbd did not stop'
  start adbd || fail 'cannot start adbd'
  wait_state running || fail 'adbd did not start'
  cmp -s "$keys" "$attempt/adb_keys.merged" || fail 'installed key bytes differ'
  check_metadata "$keys" || fail 'installed key metadata differs'
  verify_property service.adb.tcp.port 5555 || fail 'service port verification failed'
  verify_property persist.adb.tcp.port 5555 || fail 'persistent port verification failed'
  verify_property init.svc.adbd running || fail 'adbd state verification failed'
  listener_attempts=0
  until verify_listener; do
    listener_attempts=$((listener_attempts + 1))
    [ "$listener_attempts" -lt 5 ] || fail 'TCP 5555 did not enter LISTEN state'
    sleep 1
  done
  sync || fail 'cannot sync changes'
  touch "$d/done" || fail 'cannot mark completion'
  committed=1
  echo 'local keys, persistent TCP port 5555 and listening adbd verified; remote authentication is untested'
  echo 'done'
}

fail() { echo "ERROR: $*"; exit 1; }

# Android toybox stat -c, ls -Zd, base64 -d, od, cmp, mktemp and chcon.
# Fail closed when metadata/context cannot be read or reproduced.
get_label() {
  label_listing=$(ls -Zd "$1") || return 1
  for label_field in $label_listing; do
    case "$label_field" in
      *:*:*:*) printf '%s\n' "$label_field"; return 0 ;;
    esac
  done
  return 1
}

clean_current() {
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in ,QAAAA*) continue ;; esac
    printf '%s\n' "$line" || return 1
  done < "$1"
}

base64_decode() {
  case "$base64_tool" in
    standalone) base64 -d ;;
    toybox) toybox base64 -d ;;
    busybox) busybox base64 -d ;;
    *) return 1 ;;
  esac
}

base64_encode() {
  case "$base64_tool" in
    standalone) base64 "$1" ;;
    toybox) toybox base64 "$1" ;;
    busybox) busybox base64 "$1" ;;
    *) return 1 ;;
  esac
}

choose_base64_tool() {
  for base64_tool in standalone toybox busybox; do
    case "$base64_tool" in
      standalone) command -v base64 >/dev/null 2>&1 || continue ;;
      toybox) command -v toybox >/dev/null 2>&1 || continue ;;
      busybox) command -v busybox >/dev/null 2>&1 || continue ;;
    esac
    if printf '%s\n' 'aGk=' | base64_decode > "$attempt/base64.selftest" 2> "$attempt/base64.stderr"; then
      if [ "$(cat "$attempt/base64.selftest")" = hi ]; then
        echo "Base64 implementation: $base64_tool"
        return 0
      fi
    fi
  done
  [ ! -s "$attempt/base64.stderr" ] || cat "$attempt/base64.stderr"
  return 1
}

validate_keys() {
  [ -f "$1" ] || return 1
  key_kind=$2
  case "$key_kind" in supplied|current|recovery|merged) ;; *) return 1 ;; esac
  key_lines=0
  valid_keys=0
  # Canonical base64, RSAPublicKey size, word count and RSA exponent.
  while IFS= read -r line || [ -n "$line" ]; do
    key_lines=$((key_lines + 1))
    # Split whitespace-delimited fields; set -f disables pathname expansion.
    # shellcheck disable=SC2086
    set -- $line
    if [ "$#" = 0 ]; then
      [ "$key_kind" != supplied ] || return 1
      continue
    fi
    key_blob=$1
    [ "${#key_blob}" = 700 ] || return 1
    case "$key_blob" in QAAAA*=) ;; *) return 1 ;; esac
    case "$key_blob" in *[!A-Za-z0-9+/=]*) return 1 ;; esac
    printf '%s\n' "$key_blob" | base64_decode > "$attempt/key.decode" 2> "$attempt/base64.stderr" || return 1
    decoded_bytes=$(od -An -v -tu1 "$attempt/key.decode") || return 1
    # Split whitespace-delimited fields; set -f disables pathname expansion.
    # shellcheck disable=SC2086
    set -- $decoded_bytes
    [ "$#" = 524 ] || return 1
    [ "$1 $2 $3 $4" = '64 0 0 0' ] || return 1
    shift 520
    case "$1 $2 $3 $4" in '1 0 1 0'|'3 0 0 0') ;; *) return 1 ;; esac
    canonical=$(base64_encode "$attempt/key.decode" | tr -d '\n') || return 1
    [ "$canonical" = "$key_blob" ] || return 1
    valid_keys=$((valid_keys + 1))
  done < "$1"
  case "$key_kind" in
    supplied) [ "$valid_keys" = 1 ] && [ "$key_lines" = 1 ] ;;
    # A file containing only the malformed vendor entry has no usable keys.
    # The raw bytes are still retained in both attempt and recovery snapshots.
    current|recovery) return 0 ;;
    merged) [ "$valid_keys" -ge 1 ] ;;
  esac
}

merge_current() {
  IFS= read -r supplied_line < "$d/adbkey.pub" || [ -n "$supplied_line" ] || return 1
  # Split whitespace-delimited fields; set -f disables pathname expansion.
  # shellcheck disable=SC2086
  set -- $supplied_line
  supplied_blob=$1
  cp "$attempt/adb_keys.clean" "$attempt/adb_keys.merged" || return 1
  supplied_present=0
  while IFS= read -r line || [ -n "$line" ]; do
    # Split whitespace-delimited fields; set -f disables pathname expansion.
    # shellcheck disable=SC2086
    set -- $line
    [ "$#" = 0 ] && continue
    [ "$1" != "$supplied_blob" ] || supplied_present=1
  done < "$attempt/adb_keys.clean"
  if [ "$supplied_present" = 0 ]; then
    printf '%s\n' "$supplied_line" >> "$attempt/adb_keys.merged" || return 1
  fi
}

check_metadata() {
  observed_metadata=$(stat -c '%u %g %a' "$1") || return 1
  observed_label=$(get_label "$1") || return 1
  [ "$observed_metadata" = "$metadata" ] && [ "$observed_label" = "$label" ]
}

prepare_stage() {
  cp "$1" "$stage" || return 1
  # Split whitespace-delimited fields; set -f disables pathname expansion.
  # shellcheck disable=SC2086
  set -- $metadata
  chown "$1:$2" "$stage" && chmod "$3" "$stage" && chcon "$label" "$stage" || return 1
  cmp -s "$stage" "$attempt/adb_keys.merged" && check_metadata "$stage"
}

verify_property() {
  observed_property=$(getprop "$1") || return 1
  [ "$observed_property" = "$2" ]
}

wait_state() {
  count=0
  while [ "$count" -lt 5 ]; do
    verify_property init.svc.adbd "$1" && return 0
    sleep 1
    count=$((count + 1))
  done
  return 1
}

verify_listener() {
  for listener_table in /proc/net/tcp /proc/net/tcp6; do
    [ -r "$listener_table" ] || continue
    while read -r _listener_slot listener_local _listener_remote listener_state _listener_rest; do
      [ "$listener_state" = 0A ] || continue
      case "$listener_local" in *:15B3) return 0 ;; esac
    done < "$listener_table"
  done
  return 1
}

rollback() {
  echo 'ROLLBACK: restoring this attempt snapshot'
  rollback_failed=0
  [ -z "$stage" ] || rm -f "$stage" || rollback_failed=1
  stage=
  case "$baseline_state" in
    absent)
      # The clean baseline had no key file; remove the generated file.
      rm -f "$keys" || rollback_failed=1
      [ ! -e "$keys" ] || rollback_failed=1
      ;;
    empty|present)
      stage=$(mktemp "$keys.frameo.rollback.XXXXXX") || stage=
      if [ -n "$stage" ]; then
        cp "$attempt/adb_keys.raw" "$stage" || rollback_failed=1
        # Split whitespace-delimited fields; set -f disables pathname expansion.
        # shellcheck disable=SC2086
        set -- $metadata
        chown "$1:$2" "$stage" && chmod "$3" "$stage" && chcon "$label" "$stage" || rollback_failed=1
        if cmp -s "$stage" "$attempt/adb_keys.raw" && check_metadata "$stage"; then
          if mv -f "$stage" "$keys"; then
            stage=
          else
            rollback_failed=1
          fi
        else
          rollback_failed=1
        fi
      else
        rollback_failed=1
      fi
      ;;
    *) rollback_failed=1;;
  esac
  setprop service.adb.tcp.port "$service_port" || rollback_failed=1
  setprop persist.adb.tcp.port "$persist_port" || rollback_failed=1
  stop adbd || rollback_failed=1
  wait_state stopped || rollback_failed=1
  if [ "$adbd_state" = running ]; then
    start adbd || rollback_failed=1
    wait_state running || rollback_failed=1
  fi
  case "$baseline_state" in
    absent)
      [ ! -e "$keys" ] || rollback_failed=1
      ;;
    empty|present)
      cmp -s "$keys" "$attempt/adb_keys.raw" && check_metadata "$keys" || rollback_failed=1
      ;;
    *) rollback_failed=1;;
  esac
  verify_property service.adb.tcp.port "$service_port" || rollback_failed=1
  verify_property persist.adb.tcp.port "$persist_port" || rollback_failed=1
  verify_property init.svc.adbd "$adbd_state" || rollback_failed=1
  sync || rollback_failed=1
  if [ "$rollback_failed" = 0 ]; then
    echo 'ROLLBACK: verified'
  else
    echo 'ROLLBACK FAILED: preserve this attempt directory for manual recovery'
  fi
}

on_exit() {
  status=$?
  trap - EXIT HUP INT TERM
  if [ "$committed" = 0 ] && [ "$mutated" = 1 ]; then
    rm -f "$d/done" || echo 'ROLLBACK FAILED: cannot remove completion marker'
    rollback
  fi
  [ -z "$stage" ] || rm -f "$stage" || echo 'WARNING: cannot remove staging file'
  exit "$status"
}

main > "$out" 2>&1

