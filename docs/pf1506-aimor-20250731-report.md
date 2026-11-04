# PF1506 on firmware 20250731: kiosk at boot without replacing Home

One PF1506 15.6" unit, set up from macOS on 2026-10-28. No flash writes, no Home app change.

| | |
|---|---|
| Firmware | `YHK.F-null-A133-1506-D2048-PF1506-V45-OS-KXW.0.20250731` (AiMOR 6.0.70), older than the `20250813` units in #104 and #118 |
| Build | `ceres_c3`, Android 10, 32-bit userspace, `ro.config.low_ram=true`, 1920×1080 at density 160 |
| WebView | 74, vendor-signed, can't be replaced |
| Bootloader | Locked (`ro.boot.flash.locked=1`, verified boot `green`) |

## Unlock

The empty `license.properties` route from #104 worked as written: microSD (FAT32), five taps top-left, "is closed" → "is open". USB ADB (`1f3a:1006`) came back after a reboot with the card removed.

`su 0` gives UID 0 but **no capabilities** (`CapEff` 0). It can't read app data, run `iptables` or `pm enable` a component, and `cmd wifi` has no `forget-network` on this Android 10. `setprop` works.

## Kiosk at boot, AiMOR stays Home

Because of #118, the kiosk is not the Home app here. It opens itself after boot instead ([Without replacing Home](../dashboard/kiosk/README.md#without-replacing-home)):

```sh
adb shell am start -n com.wesbos.homehq/.MainActivity --ez boot true
adb shell appops set com.wesbos.homehq SYSTEM_ALERT_WINDOW allow
```

Without the `appops` line, Android 10 blocks the start from the background. AiMOR draws first, so the boot animation ends as usual. If the kiosk fails, the frame just shows AiMOR. Over six reboots: `boot_completed` after 27–33 s, kiosk or web app on screen a few seconds later.

`services.jar` is AOSP 10 here, with only the boot animation property renamed (`service.bootanim.abc_exit`). The animation ends on the standard checks, including a drawn Home window. So #118 looks like a Home window that never counted as drawn, not an AiMOR lock.

## Sites that need a newer engine

A site using `?.` and `??` fails on WebView 74 (`SyntaxError: Unexpected token ?`). Firefox 159 (armeabi-v7a, from Mozilla) renders it. Installed as a Firefox web app, it runs fullscreen without the address bar, and the kiosk opens it after boot with `--es boot_firefox_app https://…/`.

- Firefox's **Add app to Home screen** needs a launcher that accepts pinned shortcuts. AiMOR doesn't, so set a launcher as Home just for that step (`cmd package set-home-activity`, no reboot), then set AiMOR back.
- Firefox opened before Wi-Fi was up shows its offline page and doesn't retry, so the kiosk waits for a working connection first (up to 45 s).
- The [navigation buttons](../dashboard/kiosk/README.md#frames-without-home-or-back-buttons) give a way back to the kiosk, and **Power off** for a frame run from a power bank. The adapter is 5 V / 3 A USB-A.

## Wi-Fi ADB

`persist.adb.tcp.port=5555` and a reboot (not an `adbd` restart) keep it on, as in #104. There's no key check (`ro.adb.secure=0` is read-only, the bootloader is locked) and no firewall control from `su`. So limit it on the router instead: the frame on its own network, with one rule that lets a single computer reach port 5555. Also remove the saved factory networks; this unit came with two factory test networks saved, one of them open.

Undo: `setprop persist.adb.tcp.port ""` and reboot.
