# AVYONA AVN-DPF1009 10.1" Frameo frame (RK3126, Android 6.0.1, firmware `F601_ZhiHeXing_1009`)

Record of one unit, set up on Windows 11 on 2026-10-15. Observations are kept separate from
guesses. Unique identifiers (serial, MAC, Wi-Fi name) are left out; they stay in the owner's
ignored `backups/` folder.

**Result:** ADB over USB from Frameo's own settings, a shipped root `su`, a verified backup of
everything before `userdata`, and the [Denver PFF-1015](denver-pff-1015.md) route applied by hand:
Rootless Pixel Launcher and the Home HQ [kiosk](../dashboard/kiosk/README.md), vendor apps
disabled, and Home HQ as the Home app. The frame boots into the hosted dashboard and keeps its
Wi-Fi lease across reboots. Nothing was written to `/system` or the boot partition.

**Cable:** a **USB-A to USB-C** data cable from the PC worked. USB-C to USB-C was not tried on this
unit; on its relatives it gives no power and no data.

## How it relates to the known RK3126 frames

Same vendor (Harmony / ZhiHeXing), same RK3126, and the **same partition start offsets** as the
[Denver PFF-1015](denver-pff-1015.md) and the [Rollei Smart Frame 107](rollei-smartframe-107.md)
(the Denver doc says its layout matches the Rollei). The differences that matter are in this table.

| | This frame | [Denver PFF-1015](denver-pff-1015.md) |
| --- | --- | --- |
| Model / brand / manufacturer | `Frame` / `AVYONA` / `Harmony` (`AVN-DPF1009`) | `PFF-1015` / `denver` / `Harmony` |
| Firmware (display ID) | `F601_ZhiHeXing_1009-V1.0.1202510091510.release-keys` | `F608D_V10_ZhiHeXing-PFF-1015-V1.0.1202302221059` |
| Build fingerprint | `rockchip/rk312x/rk312x:6.0.1/ZhiHeXing/user.liubc.20251009.150453:user/release-keys` | `…/MXC89K/user.liubc.20230222.105805:user/release-keys` |
| RAM | 1 GB | 512 MB |
| `ro.config.low_ram` | not set (apps are not killed) | `true` (kills every app you leave) |
| Stock WebView | 107.0.5304.36 | 44.0.2403.119 |
| SystemUI | present, **disabled** out of the box | disabled |
| `userdata` start | sector 2,842,624 | sector 2,842,624 |
| Home app | Frameo (`net.frameo.frame`) | Frameo |

Because `ro.config.low_ram` is not set, the low-RAM app-killing problem in the Denver doc **does
not apply here**, and no `/system/etc/lowmem_package_filter.xml` edit is needed.

## Identity

| | |
| --- | --- |
| Sold as | a Frameo 10.1" frame. About screen shows Frameo v1.27.3 |
| `ro.product.model` / `brand` / `manufacturer` | `Frame` / `AVYONA` / `Harmony` |
| `ro.product.name` / `device` | `AVN-DPF1009` / `AVN-DPF1009` |
| `ro.product.board` / `board.platform` / `hardware` | `rk30sdk` / `rk312x` / `rk30board` |
| `ro.rk.soc` | `rk3126` |
| Build fingerprint | `rockchip/rk312x/rk312x:6.0.1/ZhiHeXing/user.liubc.20251009.150453:user/release-keys` |
| Display ID | `F601_ZhiHeXing_1009-V1.0.1202510091510.release-keys`, built 2025-10-09 |
| Android | 6.0.1, API 23, security patch 2016-07-05 |
| `ro.build.type` / `ro.secure` / `ro.debuggable` | `user` / `1` / `0` (`adb root` unavailable; use `su`) |
| SELinux | permissive (`ro.boot.selinux=permissive`) |
| USB (Android running) | `2207:0006`, product string `Frame` |
| eMMC | `mmcblk0`, 60,620,800 sectors of 512 bytes (about 29.5 GiB) |
| RAM / swap | 1,023,552 kB / 128 MB zram |
| Display | 1280x800, 160 dpi, `ro.sf.hwrotation=90` |
| WebView | `com.google.android.webview` 107.0.5304.36 |
| Home app | Frameo `net.frameo.frame` v1.27.3, `/system/priv-app/Frameo.apk` |
| PCBA / FOTA strings | `ro.pcba.company.name=ChipTrip`, `ro.fota.oem=chiptrip3126_6.0`, `ro.fota.platform=RK3126_6.0` |
| Power | no battery (`dumpsys battery: present=false`), AC powered |

## Getting ADB and root

1. On the frame: Frameo **Settings → ADB access**, USB.
2. Connect a **USB-A to USB-C** data cable to the PC and power the frame on.
3. `adb devices -l`: `device product:AVN-DPF1009 model:Frame device:AVN-DPF1009`.

   SystemUI is disabled on this unit, so an "Allow USB debugging" prompt has nowhere to appear.
   The frame connected as `device` anyway on the one computer tested. It has a host-key file, so a
   key check may still apply — **not re-tested with a fresh key**.
4. **Root is shipped.** `/system/xbin/su` is setuid `root:shell` (SuperSU-style; `daemonsu` sits
   next to it), no manager app and no prompt:

   ```sh
   adb shell su 0 id     # uid=0(root) gid=0(root) context=u:r:toolbox:s0
   ```

   Use `su 0 <cmd>`, not `su -c`. The plain shell user (uid 2000) is denied `pm disable-user`; prefix
   package commands with `su 0`. As on the other ZhiHeXing frames, **any app can get root**.

`adbd` did not listen on port 5555 over Wi-Fi on this unit; network ADB was not otherwise tried.

## Partition layout (eMMC `mmcblk0`, 512-byte sectors)

The first 16,384 sectors are the loader area and are not covered by a named partition. Start
offsets are identical to the Denver PFF-1015; only `userdata` is larger.

| Partition | Name | Start (sectors) | Size (sectors) |
| --- | --- | --- | --- |
| p1 | uboot | 16384 | 8192 |
| p2 | misc | 24576 | 8192 |
| p3 | resource | 32768 | 32768 |
| p4 | kernel | 65536 | 24576 |
| p5 | boot | 90112 | 24576 |
| p6 | recovery | 114688 | 65536 |
| p7 | backup | 180224 | 131072 |
| p8 | cache | 311296 | 262144 |
| p9 | metadata | 573440 | 32768 |
| p10 | kpanic | 606208 | 8192 |
| p11 | system | 614400 | 2097152 |
| p12 | radical_update | 2711552 | 131072 |
| p13 | userdata | 2842624 | 57778176 |

There is no `/dev/block/by-name`; the links are under
`/dev/block/platform/1021c000.rksdmmc/by-name`.

## Backup

Read as root over ADB, everything before `userdata`:

```sh
adb shell su 0 dd if=/dev/block/mmcblk0 of=/data/local/tmp/pre-userdata.img bs=512 count=2842624
adb shell su 0 chmod 644 /data/local/tmp/pre-userdata.img   # adb pull runs as the shell user
adb pull /data/local/tmp/pre-userdata.img
```

Checks that passed: length exactly **1,455,423,488 bytes** (2,842,624 x 512); the device's `md5sum`
of the image equals the host MD5; and `kernel`, `boot`, `recovery` and all of `system` re-read from
the frame match the corresponding slices of the pulled image.

This is a **partial backup**: it excludes `userdata`, so it does not meet the repo's complete-device
rule, and restore is untested. It covers every partition this record writes to (this record writes
only to `/data`). Partition-level reads for cross-checking another unit:

| Partition | Size (bytes) | MD5 |
| --- | --- | --- |
| `boot` (p5) | 12,582,912 | `f76c285dfbffcd0bc3713b8dbd067697` |
| `recovery` (p6) | 33,554,432 | `dacbe017ef6ad1d310988697070e6ec6` |

## Setup

All changes are in `/data`; none touch `/system` or a boot partition. Each was made with owner
approval, one at a time, with the undo recorded first.

1. **Home HQ kiosk** (`com.wesbos.homehq`), built from [`dashboard/kiosk`](../dashboard/kiosk/README.md)
   on Windows. Build-tools 34 was not installed, so the build used build-tools 36.0.0 and platform
   `android-37.0` (the same idea as the `BUILD_TOOLS` note in `build.sh`). Installed with
   `adb install`.
2. **Kiosk as Home app.** `am start -n com.wesbos.homehq/.MainActivity --ez home true`, then the
   Home chooser was opened and Home HQ picked. Android 6 has no `cmd package set-home-activity`; the
   default can also be seen under Settings → Home.
3. **Navigation buttons.** The kiosk's accessibility service
   (`com.wesbos.homehq/com.wesbos.homehq.NavigationService`) was enabled, and `WRITE_SECURE_SETTINGS`
   granted so the kiosk can repair it. This unit has no Android navigation bar.
4. **`settings put global stay_on_while_plugged_in 7`.**
5. **Rootless Pixel Launcher 3.9.1** (`amirz.rootless.nexuslauncher`), F-Droid APK
   `amirz.rootless.nexuslauncher_30911.apk`, SHA-256
   `7fa44d560dc4577374d45176220de2c0b00a71e09d6d148cdea4e0a52d38404a` — installed so the kiosk's
   **Open launcher** item has somewhere to go. Home HQ stays the default Home.
6. **Vendor packages disabled** (all `su 0 pm disable-user --user 0`):

   ```sh
   com.adups.fota
   com.adups.fota.sysoper
   android.rockchip.update.service
   com.cghs.stresstest
   com.DeviceTest
   com.android.rk
   com.android.rk.mediafloat
   net.frameo.frame        # Frameo, disabled last, after checking the way back on the panel
   ```

   Frameo was disabled only after the kiosk's two-finger menu and floating **Dashboard** button were
   confirmed working over Settings → Apps.

Verified after reboots: `sys.boot_completed=1`, the resumed activity is `com.wesbos.homehq/.Home`,
Wi-Fi keeps its address, and the dashboard renders fully.

## Undo

| Change | Undo |
| --- | --- |
| Vendor packages disabled | `su 0 pm enable-user --user 0 <package>` |
| Frameo disabled | `su 0 pm enable-user --user 0 net.frameo.frame` |
| Kiosk installed | `adb uninstall com.wesbos.homehq` |
| Rootless Pixel Launcher | `adb uninstall amirz.rootless.nexuslauncher` |
| Navigation buttons | Settings → Accessibility → Home HQ navigation off; `settings put secure accessibility_enabled 0` |
| Screen always on | `settings put global stay_on_while_plugged_in 0` |

## Not tested

- Whether a fresh host ADB key gets an authorization prompt.
- USB-C to USB-C cable, and why a first attempt can enumerate nothing.
- Loader mode, stock recovery and fastboot.
- The Wi-Fi driver module name, and the motion sensor if present.
- The kernel version (not recorded).
