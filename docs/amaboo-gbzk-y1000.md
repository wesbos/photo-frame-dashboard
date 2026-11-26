# AMABOO GBZK-Y1000 10.1" (Frameo, Rockchip RK3326, Android 8.1)

A record of **one unit**, set up on 2026-10-15. The About screen says `AMABOO` / `GBZK-Y1000`.
ADB shows the same RK3326 board layout as the [Akimart ZN-DP1002](akimart-zn-dp1002.md): Android
8.1 Go, logical NAND and the same partition map. The firmware branding and the boot image differ.
Everything from that page applies, but check the build strings below first.

The same About screen also ships on a **15.6-inch** build with different firmware and ports. See
[Second unit](#second-unit-156-inch-build-2026-10-21-macos-and-linux).

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
| Install Home HQ | `adb install dashboard/kiosk/build/homehq.apk` | `adb uninstall com.wesbos.homehq` (restore another Home app first) |
| Home HQ as HOME | `am start -n com.wesbos.homehq/.MainActivity --ez home true`<br>`cmd package set-home-activity com.wesbos.homehq/.Home` | `cmd package set-home-activity net.frameo.frame/.ui.activities.AWaitForDeferredInitCompleted` |
| Floating Back / Dashboard buttons | `pm grant com.wesbos.homehq android.permission.WRITE_SECURE_SETTINGS`<br>`settings put secure enabled_accessibility_services com.wesbos.homehq/.NavigationService`<br>`settings put secure accessibility_enabled 1` | `pm revoke` the same permission, `settings delete secure enabled_accessibility_services`, `settings put secure accessibility_enabled 0` |
| Disable Frameo | `pm disable-user --user 0 net.frameo.frame`, then wait (below) | `pm default-state --user 0 net.frameo.frame` |

After a normal reboot, the frame booted into Home HQ, the navigation service was bound, USB ADB
returned without a prompt, and Frameo and both updaters stayed `enabled="3"` with no process.

### Wait before rebooting after `pm disable-user`

The first Frameo disable did not survive a reboot sent within a second of `pm disable-user`:
Frameo came back enabled and running. PackageManager wrote the change to
`package-restrictions.xml` about 10 s later. After waiting until the file showed `enabled="3"`,
the disable survived a reboot. [The Dxmart unit](akimart-zn-dp1002.md#second-unit-dxmart-zn-dp1002-2026-10-15-macos)
reports the same on another unit of this board. Check before rebooting:

```sh
adb shell "su 0 grep net.frameo.frame /data/system/users/0/package-restrictions.xml"
```

## Second unit: 15.6-inch build (2026-10-21, macOS and Linux)

A second owner's frame shows the same About screen, `AMABOO` / `GBZK-Y1000`, but is a 15.6-inch
build, bought on Amazon (listing not recorded). Hosts: Linux over USB for first access, then
macOS 26 on Apple silicon over Wi-Fi ADB (platform-tools 35.0.2).

| Field | This unit | First unit (above) |
| --- | --- | --- |
| Firmware | `RAM_S101_15.6_20260314` | `RAM_S101_20251229` |
| Fingerprint build | `OC/095436` | `OC/014151` |
| Display | 1920×1080, 213 dpi | 1280×800, 160 dpi |
| Boot partition SHA-256 (32 MiB) | `9628624b04b574b65c10672889b19c17331da6b514dff54f1d0f969a4536020f` | `96828788…01c62813` |
| Ports | USB-C, USB-A (host) and a DC jack | USB-C and a DC jack |
| Frameo out of the box | v1.29.14 | v1.29.13 |

Brand `bnd`, model `RAM`, RK3326, Android 8.1 (security patch 2020-06-05), `ro.debuggable=1`,
SELinux permissive, WebView 106.0.5249.126, the shipped `su` (`su 0` and `su -c`) and `adb root`
all match the first unit. The logical NAND has the same size and the same partition names, starts
and sizes, including `userdata` at 6,669,312 with 53,885,888 sectors.

- **Cables:** USB-C to USB-C from a Mac never enumerated, in normal boot or with power held at
  plug-in. The same cable worked with an iPad. A USB-A to USB-C cable from a Linux PC's USB-A port
  enumerated at once as `2207:0006` (product `RAM`). ADB then needed a udev rule for vendor `2207`
  (`no permissions` before it) and the on-screen authorization prompt.
- **Wi-Fi ADB:** with USB ADB authorized, `adb tcpip 5555` opened network ADB, and the Mac
  connected after accepting its own key on the panel. To keep it across reboots,
  `setprop persist.internet.adb.enable 1` (as root) uses the vendor's hook in `init.rk30board.rc`.
  ADB came back on 5555 about 46 s after each of two reboots. Anyone with an authorized key
  gets root over the network, so keep the frame on a trusted network.
- **Before Wi-Fi:** both updaters were disabled over USB before the frame first joined Wi-Fi.
  Frameo was disabled about an hour later and had not updated itself by then.
- **SystemUI:** `com.android.systemui` was enabled before the first reboot and disabled after it,
  with Frameo still enabled. It stayed disabled after Frameo was disabled.
- **Backup over Wi-Fi:** the same 16 regions as the first unit, verified against on-device
  `sha256sum` and byte counts, with a gzip readback and no `0xCC` blocks. About 2 MB/s, roughly
  35 minutes. Three things broke the first tries:
  - `adb exec-out "su 0 dd …"` corrupts binary output, the same 4,197-byte result for a 4 KiB read
    reported for the [21.5" SSA frame](ssa-frame-21inch-rk3326.md#verified-firmware-backup) and
    the [YENOCK](yenock-zn-dp1501.md#root-and-binary-reads). `adb root`, then plain
    `adb exec-out dd …`, was byte-exact.
  - `dd if=/dev/block/rknand0 skip=…` failed with `Invalid argument` for every offset past 2 GiB.
    Reading each partition from its own node (`/dev/block/rknand0p12` and so on) from offset 0
    worked. The regions before that offset read fine from `rknand0`.
  - Unplugging the USB cable from the Linux PC during the Wi-Fi backup logged `adbd: USB
    disconnect` and dropped the Wi-Fi ADB session too, cutting the stream short. `adb exec-out`
    still exited 0, so check byte counts rather than exit codes.
- **Setup:** the same steps as [Setup performed](#setup-performed): updaters and Frameo disabled,
  Home HQ as HOME through its `.Home` alias, the navigation service with `WRITE_SECURE_SETTINGS`.
  Rootless Pixel Launcher 3.9.1 (the F-Droid APK pinned in
  [biuframe-setup-guide.md](biuframe-setup-guide.md)) was installed behind it. The owner checked
  the two-finger menu, Android Settings → Apps and the floating Dashboard button on the panel
  before Frameo was disabled. While Frameo was still enabled, **Open launcher** opened Frameo,
  because it is the first other Home app; after the disable it opened the Pixel launcher.
  Frameo's `enabled="3"` was on disk before the reboot, and it stayed disabled after.
- **Dashboard:** the 1280×800 dashboard showed with black bars at the sides on the 16:9 panel.
- **Microphone:** none found. The RK817 codec exposes a capture device and the audio policy lists
  a built-in mic, but `android.hardware.microphone` is not declared. With
  `tinymix 'Capture MIC Path' 'Main Mic'`, an 8 s `tinycap` recording during claps and speech stayed
  flat at −67 dBFS (peak −50.6 dBFS). No mic hole was visible.
- **Time zone:** the frame shipped on `America/New_York`. As root,
  `service call alarm 3 s16 <zone>` changed it.

## Third unit: 15.6-inch April build (2026-11-25 to 2026-11-26, macOS)

A separate 15.6-inch AMABOO unit tested from an Apple silicon Mac reported `RAM_S101_15.6_20260411`
and Frameo `v1.30.13 (69600)`. Android reported `rockchip/rk3326_go/rk3326_go:8.1.0/OC/031316:user/release-keys`.
The panel is 1920×1080 at 213 dpi, and the WebView provider was `com.android.webview` 106.0.5249.126.
The 32 MiB boot partition had the same SHA-256 as the March unit above:
`9628624b04b574b65c10672889b19c17331da6b514dff54f1d0f969a4536020f`.

- **USB ADB:** With a working USB-A to USB-C data cable, macOS enumerated the frame as `2207:0012`.
  With photo transfer off, the observed ID was `2207:0006`. After enabling **ADB access** via the
  Frameo beta menu and accepting the on-screen debugging prompt, the same Mac could reconnect
  and use USB ADB after an Android reboot. ADB was tested over USB only.
- **Backup:** With temporary root ADB, the first 8 MiB and the 15 logical NAND partitions before
  `userdata` were read over USB. Each region passed byte-count, gzip readback and on-device
  SHA-256 verification. Afterwards the USB shell returned to UID 2000. Recovery boot and restore
  remain untested.
- **Kiosk:** Home HQ showed a bundled test page after Android reboot and after a cold start with
  USB disconnected. Frameo remained available as a fallback. The Wi-Fi settings screen had no
  system navigation bar. Enabling **Home HQ navigation** through Android Accessibility settings
  provided a working **Dashboard** button before and after reboot, without a
  `WRITE_SECURE_SETTINGS` grant.
