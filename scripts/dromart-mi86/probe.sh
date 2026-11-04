#!/system/bin/sh
# Log-only MI86 compatibility probe. Do not change Android configuration.
# This script never invokes su, installs an app, starts ADB, or writes firmware.
d=${0%/*}
case "$d" in /*) ;; *) exit 1 ;; esac
[ -f "$d/mi86-probe.done" ] && exit 0
{
    printf '%s\n' 'MI86 SD utility probe v1' '--- time ---'
    date
    printf '%s\n' '--- execution identity ---'
    id
    printf '%s\n' '--- device properties (no serial or MAC) ---'
    for prop in ro.product.model ro.product.brand ro.board.platform ro.hardware ro.product.cpu.abi ro.build.version.release ro.build.version.sdk ro.build.display.id ro.build.fingerprint init.svc.adbd service.adb.tcp.port persist.adb.tcp.port; do
        printf '%s=' "$prop"
        getprop "$prop"
    done
    printf '%s\n' '--- su location only; su is not executed ---'
    command -v su || :
    for candidate in /system/bin/su /system/xbin/su /sbin/su /su/bin/su; do
        if [ -e "$candidate" ]; then ls -l "$candidate"; fi
    done
    printf '%s\n' '--- SELinux mode ---'
    if command -v getenforce >/dev/null 2>&1; then getenforce; fi
    printf '%s\n' '--- probe complete; no Android settings changed by this script ---'
} > "$d/mi86-probe.txt" 2>&1 || exit 1
printf '%s\n' 'complete' > "$d/mi86-probe.done"
