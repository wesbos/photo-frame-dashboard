#!/system/bin/sh
# Android 12 D156 only. Original Broadcom driver remains loaded.
BASE=/metadata/skylight-wifi
MODULE=/data/local/skylight-wifi/8188eu.ko
MODE=/sys/devices/platform/fe8a0000.usb2-phy/otg_mode
STATE=/sys/class/extcon/extcon0/state
exec >"$BASE/start.log" 2>&1
date
if [ -e "$BASE/disabled" ]; then
    echo "Disabled by recovery flag"
    exit 0
fi
if [ "$(getprop ro.build.version.release)" != 12 ] || [ "$(uname -r)" != 4.19.232 ]; then
    echo "Unsupported OS/kernel; no changes made"
    exit 1
fi
# A Mac present at boot takes precedence: retain ordinary USB ADB for recovery.
if grep -q '^USB=1$' "$STATE"; then
    echo "USB computer detected; retaining peripheral mode for recovery"
    exit 0
fi
if [ ! -f "$MODULE" ]; then
    echo "Missing module; retaining automatic OTG"
    exit 1
fi
grep -q '^8188eu ' /proc/modules || insmod "$MODULE" || exit 1
echo host >"$MODE" || exit 1
recover_on_error() {
    result=$?
    if [ "$result" -ne 0 ]; then
        echo "Startup failed ($result); restoring automatic OTG for USB recovery"
        start vendor.wifi_hal_legacy
        echo otg >"$MODE"
    fi
}
trap recover_on_error EXIT
find_usb_iface() {
    for net in /sys/class/net/wlan*; do
        case "$(readlink -f "$net/device/driver")" in
            */rtl8188eu) echo "${net##*/}"; return 0 ;;
        esac
    done
    return 1
}
attempt=0
until iface=$(find_usb_iface); do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 30 ]; then
        echo "No dongle after 60 seconds; restoring automatic OTG for USB recovery"
        echo otg >"$MODE"
        exit 1
    fi
    sleep 2
done
echo "Found $iface"
if [ "$iface" != wlan0 ]; then
    cmd wifi set-wifi-enabled disabled
    stop vendor.wifi_hal_legacy
    sleep 2
    for n in 0 1; do
        old=wlan$n
        if [ -e "/sys/class/net/$old" ]; then
            case "$(readlink -f "/sys/class/net/$old/device/driver")" in
                */bcmsdh_sdmmc|*/bcmdhd)
                    ip link set "$old" down || exit 1
                    ip link set "$old" name "onboard$n" || exit 1
                    ;;
                *) echo "Unexpected owner of $old; not renaming"; exit 1 ;;
            esac
        fi
    done
    ip link set "$iface" down || exit 1
    ip link set "$iface" name wlan0 || exit 1
    start vendor.wifi_hal_legacy
fi
cmd wifi set-wifi-enabled enabled
# Retain authenticated network ADB for maintenance, without forcing root adbd.
setprop service.adb.tcp.port 5555
echo "USB Wi-Fi startup configured"
date
setprop ctl.restart adbd
