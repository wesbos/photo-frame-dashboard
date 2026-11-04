# PF1506 on firmware 20250731: kiosk at boot without replacing Home

One PF1506 15.6" unit, set up from macOS on 2026-10-28. No raw flash writes.

**Configuration record, not a recovery procedure.** A verified full-device backup was not
reported, so this does not meet README rule 2. The kiosk boot route retains AiMOR as Home.
The contributor also tried a temporary Home change for Firefox setup; that experiment is not
a recommended route for another PF1506. Preserve physical Settings and USB ADB access.

| | |
|---|---|
| Firmware | `YHK.F-null-A133-1506-D2048-PF1506-V45-OS-KXW.0.20250731` (AiMOR 6.0.70), older than the `20250813` units in #104 and #118 |
| Build | `ceres_c3`, Android 10, 32-bit userspace, `ro.config.low_ram=true`, 1920×1080 at density 160 |
| WebView | 74, vendor-signed; no compatible replacement demonstrated |
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

Without the `appops` line, Android 10 blocks the start from the background. AiMOR draws first, so the boot animation ends as usual. If the kiosk fails, the frame just shows AiMOR. The contributor reported six reboots with `boot_completed` after 27–33 s and the configured app
on screen shortly afterward. The shared implementation only launches the kiosk; the experimental
Firefox boot path is not included. Its simplified receiver has been compiled offline, not
retested on this frame. Undo: `--ez boot false`, then restore the overlay app-op to `default`.

`services.jar` is AOSP 10 here, with only the boot animation property renamed (`service.bootanim.abc_exit`). The animation ends on the standard checks, including a drawn Home window. That is a hypothesis about this firmware only. It does not establish the cause or recoverability
of the newer `20250813` unit in #118; its lockout remains unresolved.

## Sites that need a newer engine

A site using `?.` and `??` failed on WebView 74 (`SyntaxError: Unexpected token ?`). The
contributor reported Firefox 159 (`armeabi-v7a`) rendering it and a pinned web app opening
without a toolbar. Firefox opened before Wi-Fi was ready showed an offline page without
retrying. These are browser observations; no Firefox boot integration is included in the kiosk.

The separate [Firefox Home helper](../scripts/firefox-home/README.md) serves frames with broken
WebView where replacing Home is safe, but it **is not validated for this PF1506**. Keep AiMOR as
Home on this device. The adapter on the reported unit is 5 V / 3 A USB-A.

## Wi-Fi ADB

`persist.adb.tcp.port=5555` and a reboot (not an `adbd` restart) keep it on, as in #104. No prompt was reported (`ro.adb.secure=0`); rejection of an unknown host key was not tested.
There is no firewall control from `su`. Treat the listener as exposed. So limit it on the router instead: the frame on its own network, with one rule that lets a single computer reach port 5555. Also remove the saved factory networks; this unit came with two factory test networks saved, one of them open.

Undo: `setprop persist.adb.tcp.port ""` and reboot.
