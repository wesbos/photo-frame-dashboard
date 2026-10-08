#!/system/bin/sh
# One-shot host-mode test. Unplug the Mac, attach an unpowered peripheral/hub,
# and wait four minutes before reconnecting the Mac. No persistent changes.
MODE=/sys/devices/platform/fe8a0000.usb2-phy/otg_mode
STATE=/sys/class/extcon/extcon0/state
LOG=/data/local/tmp/skylight-usb-host-test.log
HOLD_SECONDS=${1:-180}
case "$HOLD_SECONDS" in
  180|900) ;;
  *) echo "Expected duration 180 or 900 seconds"; exit 1 ;;
esac
exec >"$LOG" 2>&1
date
echo "Waiting for Mac USB disconnect"
count=0
while [ "$count" -lt 300 ]; do
  if grep -q '^USB=0$' "$STATE"; then
    sleep 15
    if grep -q '^USB=0$' "$STATE"; then
      break
    fi
  fi
  count=$((count + 1))
  sleep 2
done
if [ "$count" -ge 300 ]; then
  echo "No disconnect; no mode change made"
  exit 1
fi
restore() {
  echo otg >"$MODE"
  echo "Restored automatic OTG mode"
  date
}
trap restore EXIT
trap 'exit 1' HUP INT TERM
# Independent fallback in case the main diagnostic stalls.
(sleep "$((HOLD_SECONDS + 30))"; echo otg >"$MODE") </dev/null >/dev/null 2>&1 &
echo "Enabling host mode"
echo host >"$MODE" || exit 1
started=$(date +%s)
sleep 3
cat "$MODE" "$STATE"
timeout 150 sh /data/local/tmp/skylight-test-usb-wifi.sh
echo "Diagnostic exit: $?"
dmesg >/data/local/tmp/skylight-usb-host-dmesg.txt
ls /sys/bus/usb/devices
remaining=$((HOLD_SECONDS - $(date +%s) + started))
if [ "$remaining" -gt 0 ]; then
  echo "Keeping host mode for $remaining more seconds"
  sleep "$remaining"
fi
