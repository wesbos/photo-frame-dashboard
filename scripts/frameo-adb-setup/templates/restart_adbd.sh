#!/system/bin/sh
# Launch a detached, complete adbd-only stop/start; status stays on the device.
# Usage: sh restart_adbd.sh /owned/directory/restart.status
set -u
if [ "${1:-}" = --worker ]; then
  status=${2:?status path required}
  trap '' HUP
  # Give the launch command time to acknowledge before the transport stops.
  sleep 1
  printf 'stopping\n' > "$status" || exit 1
  if ! stop adbd; then printf 'failed: stop adbd\n' > "$status"; exit 1; fi
  sleep 1
  if ! start adbd; then printf 'failed: start adbd\n' > "$status"; exit 1; fi
  printf 'complete\n' > "$status"
  sync
  exit 0
fi
status=${1:?status path required}
if ! command -v setsid >/dev/null 2>&1; then
  printf 'failed: setsid\n' > "$status" || exit 1
  exit 1
fi
printf 'scheduled\n' > "$status" || exit 1
# Ignore HUP before creating the detached worker; no command after stop relies
# on the host ADB connection. The worker explicitly names adbd on both commands.
trap '' HUP
setsid sh "$0" --worker "$status" </dev/null >/dev/null 2>&1 &
