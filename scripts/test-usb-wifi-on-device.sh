#!/system/bin/sh
# Temporary root diagnostic: survives USB ADB disconnect, waits up to 15 minutes.
# Logs can contain nearby network names; keep captures private.
OUT=/data/local/tmp/skylight-usb-wifi-test
mkdir -p "$OUT"
exec >"$OUT/run.log" 2>&1
echo "Waiting for RTL8188EU USB interface"
date
cat /proc/modules
count=0
while [ "$count" -lt 450 ]; do
  for node in /sys/class/net/wlan*; do
    driver=$(readlink -f "$node/device/driver")
    case "$driver" in
      */rtl8188eu)
        iface=${node##*/}
        echo "Found USB interface: $iface ($driver)"
        /data/local/tmp/skylight-iw dev
        ip link set "$iface" up
        sleep 3
        attempt=1
        while [ "$attempt" -le 3 ]; do
          echo "Scan $attempt"
          timeout 25 /data/local/tmp/skylight-iw dev "$iface" scan >"$OUT/scan-$attempt.txt" 2>&1
          echo "Scan exit: $?"
          sleep 3
          attempt=$((attempt + 1))
        done
        dmesg >"$OUT/dmesg.txt"
        ip address >"$OUT/interfaces.txt"
        echo "DONE"
        exit 0
        ;;
    esac
  done
  count=$((count + 1))
  sleep 2
done
echo "Timed out waiting for USB Wi-Fi interface"
dmesg >"$OUT/dmesg.txt"
exit 1
