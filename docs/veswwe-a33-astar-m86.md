# VESWWE 10.1" Frameo frame with an Allwinner A33 board (`astar_m86_8723cs`, model `story`)

A record of **one unit**, set up on 2026-11-09. It was bought from
[Amazon.de B0H6NQVZGW](https://www.amazon.de/dp/B0H6NQVZGW), the same ASIN as the second
[DP101 unit](veswwe-dp101.md) (bought on Amazon.nl), but it has a different board: Allwinner A33,
Android 6.0.1, not the A133/Android 10 `DP101`. Nothing from [veswwe-dp101.md](veswwe-dp101.md) or
[veswwe-10.1.md](veswwe-10.1.md) applies to it. Check `ro.product.name` before following any page.

End result: Home HQ is the only Home app and boots into the dashboard, WebView 44 was replaced
with WebView 106, Frameo and both vendor `com.yhk.*` apps are off, Wi-Fi and network time work
after a reboot. No boot patch, flash write or `su` was needed: `adb shell` is already root.

**Tested on:** Ubuntu 26.04 (x86_64), Debian `adb` 1.0.41 (34.0.5), over USB. The cable type was
not recorded. The Frameo About screen was not recorded.

## Identity

| Field | Value seen on this unit |
| --- | --- |
| `ro.product.model` | `story` |
| `ro.product.name` / `ro.product.device` | `astar_m86_8723cs` / `astar-m86_8723cs` |
| `ro.product.brand` / manufacturer | `Allwinner` / `softwinner` |
| `ro.board.platform` / `ro.hardware` | `astar` / `sun8i` |
| `ro.build.display.id` | `astar_m86_8723cs-eng 6.0.1 MOB30R 20240906 test-keys` |
| Fingerprint | `Allwinner/astar_m86_8723cs/astar-m86_8723cs:6.0.1/MOB30R/20240906:eng/test-keys` |
| Android | 6.0.1 (SDK 23), `ro.build.type=user` |
| CPU ABI | `armeabi-v7a,armeabi`, 4 cores, kernel 3.4.39 |
| RAM, storage | `MemTotal` 1026948 kB (1 GB); `/data` 12.4 GB; eMMC 15388672 KiB |
| Display | `wm size` 1280x800, density 160 (no change needed) |
| Build flags | `ro.secure=0`, `ro.adb.secure=0`, `ro.debuggable=1`, SELinux disabled |
| USB IDs | `1f3a:1001` (`Allwinner Technology Android`) once booted; `1f3a:efe8` (FEL) was seen once while the frame was powering up, then the device disappeared from USB until Android was up |
| ADB | `persist.sys.usb.config=adb`, listed as `device` with no prompt, `adb shell id` = `uid=0(root)` |
| Network ADB | `service.adb.tcp.port` empty; nothing listening except `127.0.0.1:5037` |
| `su` | `su -c id` printed `su: invalid uid/gid '-c'`; not needed |
| SystemUI | not installed (no navigation bar) |
| WebView | `com.android.webview` 44.0.2403.119 in `/system/app/webview` |
| Vendor packages | `net.frameo.frame` v1.22.5 (`/system/priv-app/frameo.apk`), `com.yhk.qeota` (OTA), `com.yhk.rabbit.yhkages` (`/system/app/AgeVideoPlayerOldSing`, see below), `com.DeviceTest` |
| Boot partition (`by-name/boot`, `mmcblk0p6`, 33554432 bytes) SHA-256 | `cf8da25bd65ccb6a8bb534487a35688e572f350e5f59a95c5c20b272dc5ed17c` |
| Clock at first boot, offline | `Wed Dec 31 16:13 PST 1969`; `ntp_server` unset, time zone `America/Los_Angeles` |

Partitions by name: `UDISK` (p1, userdata), `bootloader` p2, `env` p5, `boot` p6, `system` p7
(1 GiB, ext4), `misc` p8, `recovery` p9, `cache` p10, `metadata` p11, `private` p12, `frp` p13,
`empty` p14, `alog` p15, `media_data` p16.

## Backup

Before any write, every partition except `UDISK` was read over `adb exec-out dd`, plus
`mmcblk0boot0`, `mmcblk0boot1` and the first 64 MiB of `mmcblk0`. For each one: the byte count
matched `/sys/class/block/<p>/size` × 512, the gzip readback matched, a second independent read
had the same SHA-256, and no part was `0xCC` filler. The original WebView directory,
`packages.xml` and the user 0 settings were archived separately. Restore was not tested.

## Setup that worked

1. **WebView 44 → 106**, following the
   [PF1007L WebView step](allwinner-a33-pf1007l.md#6-upgrade-webview-before-using-the-kiosk) with
   the pinned LineageOS `4b0ae494a7dd` APK (SHA-256 `e2edc1f8…980580` matched). The three
   `lib/armeabi-v7a/*.so` files were extracted on the host, staged under `/data/local/tmp`, copied
   to `/system/homehq-new-webview` (root:root, 0755/0644) and read back. Then the whole stock tree
   was moved to `/system/homehq-stock-webview`, the new tree to `/system/app/webview`, every live
   file was read back again and `/system` was remounted read-only. 455 MB were free on `/system`
   beforehand. After a reboot `dumpsys package com.android.webview` showed `106.0.5249.126`,
   logcat had `System package com.android.webview signature changed; retaining data` and
   `RelroFileCreator … /system/app/webview/lib/arm/libwebviewchromium.so`, with no `dlopen failed`.
2. **Home HQ** built with `dashboard/kiosk/build.sh` (Temurin JDK 17.0.21, build-tools 34.0.0,
   platform 34), installed, `WRITE_SECURE_SETTINGS` granted, URL saved, `--ez home true`.
   `cmd` does not exist on this Android 6 build, so `set-home-activity` is not available. The
   navigation service was already in `enabled_accessibility_services` right after the grant.
3. **Network time:** `settings put global ntp_server time.google.com`, `auto_time 1`,
   `setprop persist.sys.timezone Europe/Berlin`. After joining Wi-Fi on the panel (via the kiosk's
   **Open Wi-Fi settings**) the clock was correct.
4. **Way back checked by hand** (README rule 9): two-finger hold → **Android settings** → Apps,
   and the floating **Dashboard** button returned to the kiosk.
5. **Vendor apps:** `pm disable-user --user 0` for `com.yhk.qeota`, `com.yhk.rabbit.yhkages` and
   then `net.frameo.frame`. With Frameo disabled, Home HQ was the only Home app; no chooser
   appeared and the frame booted into it after waiting 30 seconds and rebooting.

### `com.yhk.rabbit.yhkages` keeps running when disabled

`dumpsys package` shows it as `PERSISTENT`, `sharedUser android.uid.system` (uid 1000), with
`INTERNET`, `REBOOT`, `INSTALL_LOCATION_PROVIDER` and fine location. Version name
`yhk_Video_AgesRecord.1013.2.Old.Sign.Nolauncher`. After `disable-user`, `am force-stop` and
`kill`, it restarted at once with a new PID, and it was running again after a reboot. What fixed
it:

```sh
adb shell pm hide com.yhk.rabbit.yhkages      # undo: pm unhide
```

After the next reboot no `yhk` or `frameo` process was running. What the app does was not
investigated; while it was running, no TCP connection owned by uid 1000 was open.

## Undo

```sh
adb shell 'mount -o remount,rw /system && mv /system/app/webview /system/homehq-new-webview && mv /system/homehq-stock-webview /system/app/webview && sync && mount -o remount,ro /system'
adb shell pm unhide com.yhk.rabbit.yhkages
adb shell pm enable com.yhk.rabbit.yhkages; adb shell pm enable com.yhk.qeota; adb shell pm enable net.frameo.frame
adb shell am start -n com.wesbos.homehq/.MainActivity --ez home false
adb shell settings delete global ntp_server
adb reboot
```

## Guesses

- This is probably close to the PF1006 `astar-m86_8723cs` build (model `AEEZO`) in the
  [device index](devices.md) and to PF1007L units, which also report `astar_m86_8723cs`. But this
  build has no AiMOR app, its firmware string has no `PF1007L`, its model is `story`, and no
  partition layout was compared. Don't reuse PF1006 or PF1007L boot patches on it.
- The FEL ID during power-up was probably the normal boot path briefly exposing the Boot ROM, as
  on the [Frameo 102K](frameo-102k-a33.md). Not investigated.
- Anyone with a USB cable gets a root shell (`ro.adb.secure=0`). Over Wi-Fi no ADB port was open on
  this unit.
