# Uhale 10.1" frame on the RK3326 `RAM_S101` board (Android 8.1, WebView 61)

Record of one unit, set up on 2026-10-24 from a Windows laptop (platform-tools 37.0.1). It records
what was done on this unit; it is not a flashing guide. Observations are kept separate from guesses.
Unique identifiers (serial, MAC, Wi-Fi, IP addresses, account IDs) are left out.

**Short version:** a 10.1" Uhale frame bought from Takealot (South Africa) in October 2026. It runs
the Zeasn/Uhale app instead of Frameo, but the Android build is the same `bnd` / `RAM` RK3326 family
as the [AMABOO GBZK-Y1000](amaboo-gbzk-y1000.md), and its boot partition is **byte-identical to the
[Akimart ZN-DP1002](akimart-zn-dp1002.md)** (SSA) boot. Like the [Runxion RK3326](runxion-zn-dp1002-rk3326.md)
it ships WebView 61 (same `webview.apk`), so it needed the same `/system` WebView swap.

Unlike the [Whale Framely](whale-framely-ram-s915.md), which runs the same Zeasn software and stayed
locked, this unit opened Android Settings from the Uhale About screen, and USB debugging worked.

End result: Uhale, both vendor updaters and a bundled adware app disabled, WebView 106 in `/system`
with the stock tree kept for undo, Rootless Pixel Launcher as a fallback, and the repo's
[Home HQ kiosk](../dashboard/kiosk/README.md) as HOME with its navigation service. Key-checked ADB
over Wi-Fi stays on across reboots. The frame boots straight into the kiosk.

## Identity

| Field | Value seen on this unit |
| --- | --- |
| Sold as | 10.1" Uhale Wi-Fi touchscreen frame, 1280×800, "16 GB" (Takealot, listing not recorded) |
| Uhale About screen | Build Number `RAM_S101_20251112`, System version `8.1.0`, app `FSCR-5.0.0-500015` |
| Brand / model | `bnd` / `RAM` |
| Platform | Rockchip RK3326, ABI `armeabi-v7a`, kernel 4.4.138 (`zcx@bnd105`, built 2025-11-12) |
| Android / API | 8.1.0 / 27, security patch 2020-06-05 |
| Fingerprint | `rockchip/rk3326_go/rk3326_go:8.1.0/OC/123208:user/release-keys` |
| Build flags | `ro.debuggable=1`, `ro.adb.secure=1`, SELinux permissive, verified boot `orange`, `ro.config.low_ram` not set |
| Display | 1280×800, density 160 |
| Storage | logical NAND `rknand0`, 60,555,264 sectors; p1–p16 match the [Akimart map](akimart-zn-dp1002.md#logical-nand-partition-map) sector for sector (`userdata` at 6,669,312, 53,885,888 sectors) |
| Root | shipped `su`: `su 0 <cmd>` works, `su -c` fails (`invalid uid/gid '-c'`), as on the Akimart. `adb root` works |
| WebView as shipped | `com.android.webview` **61.0.3163.98** in `/system/app/webview`, `webview.apk` SHA-256 `db1f9a147730a4893670ea98fc72ee8060fdc0b0861485bec8ba63405affbc3b` (same file as the Runxion and YENOCK) |
| Vendor app | `com.zeasn.frame` 5.0.0 in `/system/priv-app/Frame_united` (HOME) |
| Vendor updaters | `com.adups.fota`, `android.rockchip.update.service` |
| Other vendor apps | `com.cross.browser.info` "HardInfo" 5.4.0 (adware, see below), RkExplorer, a hardware-info and a stress-test app |
| USB ID | `2207:0006`, product `RAM`; no extra Windows driver needed |
| Boot partition (p6, 32 MiB) SHA-256 | `4ed777af252fcd537195fcda0cb8a4a59ffb3f88d543d210f04163d1045a891b` (identical to the Akimart ZN-DP1002) |

## Getting ADB

1. In the Uhale app, **Settings → About**, tap **System version** about 15 times. Full Android
   Settings opens.
2. **System → About tablet**, tap **Build number** 7 times, then **Developer options → USB
   debugging** on. There is no "Select USB configuration" entry in Developer options.
3. Connect a **USB-A to USB-C data cable** from the computer's USB-A port to the frame's USB-C port.

**The frame did not enumerate at all until it was booted with the cable already attached.** With
the frame running and its power adapter in, three different data cables on several ports (USB-A and
a Thunderbolt USB-C port) produced no USB event on Windows, not even a failed descriptor request.
The same cable and port enumerated a phone. Restarting the frame with only the laptop cable
connected made it appear at once as `2207:0006`, and `adb devices` showed `device` with no new prompt
(the prompt had presumably been accepted when USB debugging was switched on). After the setup below,
a reboot on the frame's own adapter with the cable attached also brought USB ADB back. Whether the
cable must be in at boot, or the adapter must be out, was not separated further.

TCP 5555 was closed out of the box; the only listener was a system service on 17802.

## Backup (before any write)

Same method as the [AMABOO backup](amaboo-gbzk-y1000.md#backup): `adb root`, then plain
`adb exec-out dd`. Regions past 2 GiB were read from their own partition nodes
(`/dev/block/rknand0pN`), as on the AMABOO 15.6". About 8 to 10 MB/s over USB on laptop power, with
no drops.

- Sectors 0 to 6,669,311 (everything before `userdata`): 3,414,687,744 bytes in 16 regions, 844 MB
  gzipped.
- Exact byte counts, every region's SHA-256 matched a fresh on-device `sha256sum`, every gzip read
  back identical, no aligned 4 KiB block was all `0xCC`, and independent re-reads of all of boot,
  all of recovery and a 64 MiB system sample matched.

Wi-Fi was switched off (`svc wifi disable`) before the backup, because both updaters were enabled
and the frame was already online. It was switched back on after the updaters were disabled.

## Setup performed (2026-10-24)

Each change was recorded with its undo before it was made.

| Change | Command | Undo |
| --- | --- | --- |
| Disable Adups FOTA | `pm disable-user --user 0 com.adups.fota` | `pm default-state --user 0 com.adups.fota` |
| Disable Rockchip updater | `pm disable-user --user 0 android.rockchip.update.service` | `pm default-state --user 0 android.rockchip.update.service` |
| Install fallback launcher | `adb install` Rootless Pixel Launcher 3.9.1 (F-Droid, SHA-256 `7fa44d56…404a`, the pin in [biuframe-setup-guide.md](biuframe-setup-guide.md)) | `adb uninstall amirz.rootless.nexuslauncher` (while it is not HOME) |
| Install Home HQ | `adb install` the kiosk built with `dashboard/kiosk/build.ps1` (JDK 17, build-tools 34) | `adb uninstall com.wesbos.homehq` (set another HOME first) |
| Navigation service | `pm grant com.wesbos.homehq android.permission.WRITE_SECURE_SETTINGS`, then enable the service as in the [AMABOO table](amaboo-gbzk-y1000.md#setup-performed) | `pm revoke` the permission, `settings delete secure enabled_accessibility_services`, `settings put secure accessibility_enabled 0` |
| Home HQ as HOME | `am start -n com.wesbos.homehq/.MainActivity --ez home true`<br>`cmd package set-home-activity com.wesbos.homehq/.Home` | `cmd package set-home-activity` back to the Uhale activity, then `--ez home false` |
| Disable Uhale | `pm disable-user --user 0 com.zeasn.frame` | `pm default-state --user 0 com.zeasn.frame` |
| Disable HardInfo | `pm disable-user --user 0 com.cross.browser.info` | `pm default-state --user 0 com.cross.browser.info` |
| Network ADB | `setprop persist.internet.adb.enable 1` (as root) | `setprop persist.internet.adb.enable 0` |
| Time zone | `service call alarm 3 s16 Africa/Johannesburg` (it shipped on `Africa/Windhoek`) | the same with the old zone |
| WebView 61 → 106 | [below](#webview-106-in-place-of-the-stock-webview-61) | below |

Before Uhale was disabled, the owner checked by hand on the panel that the two-finger menu reached
Android Settings → Apps, that **Open launcher** opened another Home app, and that the floating Back
and Dashboard buttons worked. Each `pm disable-user` was confirmed as `enabled="3"` in
`package-restrictions.xml` before any reboot.

After a reboot on the frame's own adapter: it booted into Home HQ, Wi-Fi ADB came back after about
53 s (key check still on), Uhale, the updaters and HardInfo stayed disabled with no processes, and the
navigation service was bound. `adb root` does not survive a reboot; `su 0` still works.

### Network ADB

`/init.rk30board.rc` has the same vendor hook as the AMABOO 15.6": setting
`persist.internet.adb.enable=1` sets `service.adb.tcp.port` to 5555 and restarts `adbd`, and `0`
turns it off. The authorized laptop key connected over Wi-Fi with root. A raw ADB connection that
offered no key got an `AUTH` challenge, and a fake signature was challenged again. Anyone holding an
authorized key gets root over the network, so keep the frame on a trusted network.

Testing a fresh key with `adb` on Windows was not reliable: with `HOME`, `ANDROID_USER_HOME` and
`ADB_VENDOR_KEYS` pointed at a temporary folder, `adb` still used the user's real key and connected.
The raw handshake was used instead.

## WebView 106 in place of the stock WebView 61

The stock tree matched the [Runxion record](runxion-zn-dp1002-rk3326.md#webview-106-in-place-of-the-stock-webview-61)
(same `webview.apk`; the `.vdex` matched; the `.odex` differed from both documented units, which that
page says is expected). The same swap was done with the same pinned files: LineageOS WebView
106.0.5249.126 ARM (`e2edc1f8…0580`) and the three extracted `lib/arm` libraries, all hashes matching.
The stock tree was moved to `/system/webview-stock-61` and pulled to the host first. `/system` is
plain ext4 with 747 MB free.

After a reboot, `dumpsys webviewupdate` showed 106.0.5249.126 as current with RELRO done, there
were no library load errors, the hosted demo dashboard rendered fully (on WebView 61 it showed only
the sidebar, with `Uncaught SyntaxError: Unexpected token =`), and HTTPS loaded with no certificate
errors. One log line repeats: WebView 106 looks for a class that only exists on Android 9.

## HardInfo is adware

`com.cross.browser.info` 5.4.0 ("HardInfo") is a system app that shows device information, with a
launcher icon and a Quick Settings tile. It also contains a hidden "lite browser" ad module
(`com.cross.lite.*`) with its own news start page, and ran a permanent foreground service.

- It starts on boot, screen unlock, network changes, power plug and unplug, and SD card mounts.
- It holds `INTERNET`, `KILL_BACKGROUND_PROCESSES` and `REQUEST_DELETE_PACKAGES`. It requests
  location, storage and the installed-app list; those were not granted.
- It contacts `brs.sendclick.xyz` over plain HTTP (`/browser/cb/blhost.php?m=info`,
  `/homeinfo.php`). Connections to two of that host's addresses on port 80 were seen.

It plays no part in the dashboard. After `pm disable-user` and a reboot it had no process and no
sockets.

## Guesses, not confirmed

- The USB behaviour suggests the USB-C port is only switched to device mode at boot when a host is
  detected. Not checked in the kernel or init scripts.
- Other Uhale frames on `RAM_S101` builds probably share this route, but the Whale Framely
  (`RAM_S915`, same Zeasn app) shows not every Zeasn build exposes the hidden Settings.

## Not yet checked

- Restoring the backup.
- Whether a factory reset brings Uhale or HardInfo back (both are system apps, so it probably would).
- Battery, PIR sensor or microphone.
