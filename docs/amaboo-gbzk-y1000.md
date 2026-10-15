# AMABOO GBZK-Y1000 10.1" (Frameo, Rockchip RK3326, Android 8.1)

A record of **one unit**, set up on 2026-10-15. The About screen says `AMABOO` / `GBZK-Y1000`.
ADB shows the same RK3326 board layout as the [Akimart ZN-DP1002](akimart-zn-dp1002.md): Android
8.1 Go, logical NAND and the same partition map. The firmware branding and the boot image differ.
Everything from that page applies, but check the build strings below first.

End result: Home HQ is the Home app and boots into the dashboard, its floating Back and Dashboard
buttons work, and Frameo plus both vendor updaters are disabled for user 0. A verified logical NAND
backup was taken first. No flash write, system remount or WebView swap was needed. Everything
below is reversible over ADB.

**Tested on:** one unit, bought from [Amazon.nl B0DYCSKZC3](https://www.amazon.nl/dp/B0DYCSKZC3),
from a Mac (Apple silicon, macOS 26) with
platform-tools 37.0.1 over USB.

## Identity

| Field | Value seen on this unit |
| --- | --- |
| About screen | Hardware `AMABOO` `GBZK-Y1000`; Frameo `v1.29.13 (60080)` out of the box |
| Brand / manufacturer / model | `bnd` / `rockchip` / `RAM` |
| Platform / board | `rk3326` / `rk30sdk`, kernel 4.4.138 |
| Android / API | 8.1.0 / 27, ABI `armeabi-v7a`, security patch 2020-06-05 |
| Firmware | `RAM_S101_20251229` |
| Fingerprint | `rockchip/rk3326_go/rk3326_go:8.1.0/OC/014151:user/release-keys` |
| Build flags | `ro.debuggable=1`, `ro.adb.secure=1`, SELinux permissive, verified boot `orange` |
| RAM / display | 976,900 KiB / 1280×800, 160 dpi |
| Storage | logical NAND `rknand0`, 60,555,264 sectors |
| Root | shipped `/system/xbin/su`; both `su 0 <cmd>` and `su -c <cmd>` give uid 0. `adb root` works |
| WebView | `com.android.webview` 106.0.5249.126 in `/system/app/webview` |
| Vendor packages | `net.frameo.frame` (`/system/priv-app/Frameo`), `com.adups.fota` 5.26, `android.rockchip.update.service` |
| Ports | USB-C (data and power) and a separate 5V DC jack |

Compared with the Akimart unit:

| | This unit | [Akimart ZN-DP1002](akimart-zn-dp1002.md) (SSA) |
| --- | --- | --- |
| Brand / model | `bnd` / `RAM` | `SSA` / `Frame` |
| Firmware | `RAM_S101_20251229` | `SSA_Frame_20260420` |
| Fingerprint build | `OC/014151` | `OC/085013` |
| `su -c` | works | fails (`invalid uid/gid '-c'`) |
| Boot partition SHA-256 (32 MiB) | `96828788c95fe6f0a2a182e46f966cc7db22c5eebd65804f439f3e4501c62813` | `4ed777af252fcd537195fcda0cb8a4a59ffb3f88d543d210f04163d1045a891b` |
| `userdata` size (sectors) | 53,885,888 | 53,885,919 |

Partitions p1 to p15 have the same names, starts and sizes as the
[Akimart map](akimart-zn-dp1002.md#logical-nand-partition-map); `userdata` starts at 6,669,312.
The [VESWWE DP100](veswwe-10.1.md) uses a smaller `recovery`, so its offsets do not apply.

## Getting ADB

1. Frameo Settings → About → **Beta Program**, then **ADB access**.
2. Connect the frame's USB-C port to the computer with a USB-A to USB-C data cable, and accept the
   authorization prompt on the frame. USB configuration is then `mtp,adb`. TCP 5555 stayed closed.

Joining Wi-Fi made Frameo update itself to v1.32.16 (80320), installed into `/data/app`.

## Backup

Same method as the [Akimart backup](akimart-zn-dp1002.md#verified-firmware-backup), run with
`adb root` so `adb exec-out dd` reads raw blocks directly (a 4 KiB boot probe matched the
on-device SHA-256). About 12 to 13 MB/s over USB.

- Sectors 0 to 6,669,311: 3,414,687,744 bytes, 804,262,892 bytes gzipped.
- Stream SHA-256 matched the gzip readback, no aligned 4 KiB block was all `0xCC`, and fresh
  on-device SHA-256 of the first 8 MiB and of every partition p1 to p15 matched, including `oem`.

A logical firmware capture, not a physical NAND/OOB image or a userdata snapshot. Restoration is
untested.

## Setup performed

From the [kiosk README](../dashboard/kiosk/README.md). Home HQ rendered the hosted demo dashboard
on the stock WebView 106 with no changes, and its `.Home` alias works as HOME without a rebuild.

| Change | Command | Undo |
| --- | --- | --- |
| Disable Adups FOTA | `pm disable-user --user 0 com.adups.fota` | `pm default-state --user 0 com.adups.fota` |
| Disable Rockchip updater | `pm disable-user --user 0 android.rockchip.update.service` | `pm default-state --user 0 android.rockchip.update.service` |
| Install Home HQ | `adb install kiosk/build/homehq.apk` | `adb uninstall com.wesbos.homehq` (restore another Home app first) |
| Home HQ as HOME | `am start -n com.wesbos.homehq/.MainActivity --ez home true`<br>`cmd package set-home-activity com.wesbos.homehq/.Home` | `cmd package set-home-activity net.frameo.frame/.ui.activities.AWaitForDeferredInitCompleted` |
| Floating Back / Dashboard buttons | `pm grant com.wesbos.homehq android.permission.WRITE_SECURE_SETTINGS`<br>`settings put secure enabled_accessibility_services com.wesbos.homehq/.NavigationService`<br>`settings put secure accessibility_enabled 1` | `pm revoke` the same permission, `settings delete secure enabled_accessibility_services`, `settings put secure accessibility_enabled 0` |
| Disable Frameo | `pm disable-user --user 0 net.frameo.frame`, then wait (below) | `pm default-state --user 0 net.frameo.frame` |

After a normal reboot, the frame booted into Home HQ, the navigation service was bound, USB ADB
returned without a prompt, and Frameo and both updaters stayed `enabled="3"` with no process.

### Wait before rebooting after `pm disable-user`

The first Frameo disable did not survive a reboot sent within a second of `pm disable-user`:
Frameo came back enabled and running. PackageManager wrote the change to
`package-restrictions.xml` about 10 s later. After waiting until the file showed `enabled="3"`,
the disable survived a reboot. [PR #124](https://github.com/wesbos/photo-frame-dashboard/pull/124)
reports the same on another unit of this board. Check before rebooting:

```sh
adb shell "su 0 grep net.frameo.frame /data/system/users/0/package-restrictions.xml"
```
