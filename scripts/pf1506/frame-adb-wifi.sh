#!/system/bin/sh
# Optional unauthenticated ROOT ADB. An allowed IPv4 host owns the frame.
# Run only through init: setprop ctl.start frame-adb-wifi
# init owns this process so stopping adbd cannot kill reconfiguration halfway through.
# The early-init runtime -1 baseline in frame-adb-wifi.rc is required. Other init
# rules must not enable TCP ADB independently. Boot timing still needs frame testing.
PORT=5555
LOCK=/dev/.frame-adb-wifi.lock
GUARD=frame_adb_guard
HOOK="-A INPUT -p tcp -m tcp --dport $PORT -j"

log_error() { log -t frame-adb "$*"; }
# /dev is root-owned and volatile. Do not reclaim a live or stale lock by guessing.
mkdir "$LOCK" 2>/dev/null || { log_error "reconfiguration already running or lock unavailable; not applied"; exit 1; }
trap 'rmdir "$LOCK"' EXIT
trap 'exit 1' HUP INT TERM

no_listener() {
    sockets=$(cat /proc/net/tcp /proc/net/tcp6) || return 1
    printf '%s\n' "$sockets" | awk -v ports="$ports" '
        BEGIN { n=split(ports,p," ") }
        $4 == "0A" { for(i=1;i<=n;i++) if(toupper($2) ~ ":" p[i] "$") found=1 }
        END { exit found ? 1 : 0 }'
}
wait_daemon() {
    n=0
    while [ "$n" -lt 10 ]; do
        [ "$(getprop init.svc.adbd)" = "$1" ] && no_listener && return 0
        n=$((n + 1)); sleep 1
    done
    return 1
}
fail() {
    # Best effort only: a failed command is never described as verified USB-only.
    ensure_guard iptables
    ensure_guard ip6tables
    setprop service.adb.tcp.port -1
    setprop persist.adb.tcp.port -1
    setprop ctl.stop adbd
    log_error "FAILED: $1; network closure/USB availability not guaranteed; inspect locally"
    exit 1
}
first_rules() {
    rules=$("$1" -S INPUT) || return 1
    printf '%s\n' "$rules" | awk '$1 == "-A" { print; if (++n == 2) exit }'
}
ensure_guard() {
    fw=$1
    if "$fw" -N "$GUARD" 2>/dev/null; then
        "$fw" -A "$GUARD" -j DROP || return 1
    fi
    rules=$("$fw" -S "$GUARD") || return 1
    [ "$rules" = "-N $GUARD
-A $GUARD -j DROP" ] || return 1
    # Always insert at one: membership (-C) cannot establish effective ordering.
    "$fw" -I INPUT 1 -p tcp --dport "$PORT" -j "$GUARD" || return 1
    [ "$(first_rules "$fw" | head -n 1)" = "$HOOK $GUARD" ] || return 1
}
# Remove only our dedicated hooks, from the bottom, keeping the new first hook.
remove_hooks() {
    fw=$1; target=$2; keep=$3
    rules=$("$fw" -S INPUT) || return 1
    positions=$(printf '%s\n' "$rules" | awk -v wanted="$HOOK $target" -v keep="$keep" '
        $1 == "-A" { ++n; if ($0 == wanted && n != keep) a[++k]=n }
        END { for (i=k;i>0;i--) print a[i] }') || return 1
    for pos in $positions; do "$fw" -D INPUT "$pos" || return 1; done
}
old_runtime=$(getprop service.adb.tcp.port) || fail "read runtime TCP property"
old_persist=$(getprop persist.adb.tcp.port) || fail "read persistent TCP property"
ports=15B3
for p in "$old_runtime" "$old_persist"; do
    case "$p" in ''|-1|0) ;; *[!0-9]*) ;; *)
        [ "$p" -le 65535 ] && ports="$ports $(printf '%04X' "$p")" ;;
    esac
done
ensure_guard iptables || fail "could not establish first IPv4 guard"
ensure_guard ip6tables || fail "could not establish first IPv6 guard"
remove_hooks iptables "$GUARD" 1 || fail "IPv4 guard cleanup"
remove_hooks ip6tables "$GUARD" 1 || fail "IPv6 guard cleanup"

# Close even when the runtime property is empty but the persistent property is set.
setprop service.adb.tcp.port -1 || fail "runtime TCP disable"
setprop persist.adb.tcp.port -1 || fail "persistent TCP disable"
setprop ctl.stop adbd || fail "stop adbd"
wait_daemon stopped || fail "adbd/listener did not stop"
[ "$(getprop service.adb.tcp.port)" = -1 ] && [ "$(getprop persist.adb.tcp.port)" = -1 ] || fail "TCP disable verification"
ALLOW=$(getprop persist.frame.adb_allow) || fail "read allow list"
WIFI=$(getprop persist.frame.adb_wifi) || fail "read Wi-Fi ADB setting"
usb_only() {
    setprop ctl.start adbd || fail "start USB adbd"
    wait_daemon running || fail "USB adbd/listener verification"
    [ "$(getprop service.adb.tcp.port)" = -1 ] && [ "$(getprop persist.adb.tcp.port)" = -1 ] || fail "USB TCP property verification"
    log_error "verified USB-only: $1"
    exit 0
}
[ "$WIFI" = 0 ] && usb_only "turned off"
[ -z "$ALLOW" ] && usb_only "no allow list"
case "$ALLOW" in *[!0-9.,]*|,*|*,|*,,*) fail "malformed IPv4 allow list" ;; esac
for ip in $(printf '%s' "$ALLOW" | tr ',' ' '); do
    printf '%s\n' "$ip" | awk -F. 'NF!=4 {exit 1} {for(i=1;i<=4;i++) if($i=="" || $i>255 || length($i)>3 || (length($i)>1 && substr($i,1,1)=="0")) exit 1}' || fail "malformed IPv4 address"
done

# Only this dedicated chain is rebuilt. Both INPUT guards remain first throughout.
iptables -N frame_adb 2>/dev/null || iptables -S frame_adb >/dev/null || fail "create allow chain"
iptables -F frame_adb || fail "reset allow chain"
expected='-N frame_adb'
for ip in $(printf '%s' "$ALLOW" | tr ',' ' '); do
    iptables -A frame_adb -s "$ip/32" -j RETURN || fail "append allow rule"
    expected="$expected
-A frame_adb -s $ip/32 -j RETURN"
done
iptables -A frame_adb -j DROP || fail "append final DROP"
expected="$expected
-A frame_adb -j DROP"
[ "$(iptables -S frame_adb)" = "$expected" ] || fail "allow chain order verification"
iptables -I INPUT 2 -p tcp --dport "$PORT" -j frame_adb || fail "insert allow hook"
remove_hooks iptables frame_adb 2 || fail "allow hook cleanup"
[ "$(first_rules iptables)" = "$HOOK $GUARD
$HOOK frame_adb" ] || fail "effective IPv4 order verification"
[ "$(first_rules ip6tables | head -n 1)" = "$HOOK $GUARD" ] || fail "effective IPv6 order verification"
[ "$(getprop persist.frame.adb_allow)" = "$ALLOW" ] && [ "$(getprop persist.frame.adb_wifi)" = "$WIFI" ] || fail "configuration changed; request init reapply"
# Revoked hosts hit this chain before any broad ACCEPT or ESTABLISHED rule.
iptables -D INPUT 1 || fail "lift IPv4 guard"
[ "$(first_rules iptables | head -n 1)" = "$HOOK frame_adb" ] || fail "final hook verification"
setprop service.adb.tcp.port "$PORT" || fail "enable TCP"
setprop ctl.start adbd || fail "start TCP adbd"
n=0
while [ "$(getprop init.svc.adbd)" != running ] && [ "$n" -lt 10 ]; do
    n=$((n + 1)); sleep 1
done
[ "$(getprop service.adb.tcp.port)" = "$PORT" ] && [ "$(getprop init.svc.adbd)" = running ] || fail "TCP start verification"
[ "$(getprop persist.frame.adb_allow)" = "$ALLOW" ] && [ "$(getprop persist.frame.adb_wifi)" = "$WIFI" ] || fail "configuration changed during TCP start; request init reapply"
log_error "configured root TCP $PORT for listed IPv4 hosts only; IPv6 blocked"
