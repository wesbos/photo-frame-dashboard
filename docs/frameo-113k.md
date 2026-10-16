# Frameo 10.1" `113K` frame (`RK3126`, Android 6.0.1, firmware `113K_user_frameo_202607201039`)

Record of one unit, set up on Linux (Omarchy, x86_64, Android platform-tools 37.0.0) on 2026-10-16.
Observations are kept separate from guesses. Unique identifiers (serial, MAC, IP) are left out.

**Short version:** same `incar` RK3126 platform build and eMMC partition layout as the
[Tibuta `TID10`](tibuta-tid10.md), [YIAISIGN `10X1`](yiaisign-10x1.md) and
[Uhale `102KZ`](uhale-102kz.md). Stock WebView is already 107.0.5304.36 and both Let's Encrypt root
certificates (`ISRG Root X1` and `X2`) are already in `/system/etc/security/cacerts/`, so no
`/system` or partition writes are needed to run the [Home HQ kiosk](../dashboard/kiosk/README.md),
Rootless Pixel Launcher and Firefox.

## How it relates to the known RK3126 frames

| | This frame (`113K`) | Tibuta `TID10` | Uhale `102KZ` | YIAISIGN `10X1` |
| --- | --- | --- | --- | --- |
| Model / manufacturer | `113K` / `incar` | `TID10` / `incar` | `102KZ` / `incar` | `10X1` / `incar` |
| Build fingerprint | `…/user.fyl.20170927.202757:userdebug/test-keys` | same | same | same |
| Partition layout | `userdata` at sector 2,846,720 | same | same | same |
| Home app | Frameo (`net.frameo.frame` v1.31.18) | Frameo | Uhale (`com.zeasn.frame`) | Biu Frame (`com.shenju.biuframe`) |
| How ADB is enabled | Frameo Settings → About → Beta Program → ADB access (toggle off/on with USB connected) | Frameo Settings → ADB access | On, stays `unauthorized` | On out of the box |
| Stock WebView | 107.0.5304.36 (`com.google.android.webview`) | 107.0.5304.36 | 44 | 44 |
| Let's Encrypt roots | Pre-installed (`6187b673.0`, `8794b4e3.0`) | Added during setup | Added during setup | Added during setup |
| Wi-Fi chip | AICSemi AIC8800 (`aic8800_fdrv`, `aic8800_bsp`) | AIC8800 (`aic8800_fdrv`) | Not recorded | Realtek SDIO |
| Touch / accelerometer | `gslX680` / `sc7a20` | `gslX680` | `gslX680` | `gslX680` / `0x19` |

## Identity (read-only observations)

| Item | Observed value |
| --- | --- |
| `ro.product.model` / `brand` / `manufacturer` | `113K` / `rockchip` / `incar` |
| `ro.product.device` / `ro.board.platform` / `ro.hardware` | `rk312x` / `rk312x` / `rk30board` |
| Build fingerprint | `rockchip/rk312x/rk312x:6.0.1/MXC89K/user.fyl.20170927.202757:userdebug/test-keys` |
| Display ID | `113K_user_frameo_202607201039` (loader timestamp `2026-07-20_10:34:54`) |
| Android / ABI | 6.0.1, SDK 23 / `armeabi-v7a`, SELinux `Permissive` |
| `ro.secure` / `ro.debuggable` | `1` / `0` (`adb root` unavailable; use `su`) |
| `ro.config.low_ram` | Unset |
| USB, Android running | `2207:0006`, manufacturer string `incar`, product string `113K` |
| eMMC | 61,071,360 sectors of 512 bytes (about 29.8 GiB) |
| RAM / swap | 1 GB (`MemTotal: 1021240 kB`), 128 MB zram (`/dev/block/zram0`) |
| Display | 1280 × 800, 160 dpi |
| Stock WebView | `com.google.android.webview` 107.0.5304.36 (`versionCode=530403610`) in `/system/app/webview` |
| Stock CA certificates | `/system/etc/security/cacerts/6187b673.0` (ISRG Root X1) and `8794b4e3.0` (ISRG Root X2) present out of the box |
| Stock boot image (`mmcblk0p5`) | Partition is 28,672 sectors (14,680,064 bytes), SHA-256 `dc8d2d44a4a1b11c510fde7ab1bb5348868428b20f2f0bfc41556b3c1c28ceba`, SHA-1 `edab6205c599cb4151b9f08b12684afa0a62c5e4`. The 12,664,832-byte image inside it has SHA-1 `b59a6ef9da78f35944a09233a038e70070fb9b04` (SHA-256 `f250f3965fc0efea5095463c58abe56fa64879cbf6faf35275d3d93c054882cb`), matching `MTD:boot:12664832:b59a6ef9…` in `/system/bin/install-recovery.sh` |
| Vendor apps | `net.frameo.frame` v1.31.18 (`/system/priv-app/newFrameo`), `com.adups.fota` v5.28 (`/system/app/FotaUpdate`), `com.DeviceTest` (`/system/app/DeviceTest`). No `/system/bin/iotv` present |

## Cables, ADB and root

1. The frame has a single USB-C port. A **USB-C to USB-C** cable connected to the Linux host did not
   enumerate at all (no kernel USB event). A **USB-A to USB-C** data cable plugged into a USB-A port
   on the host enumerated immediately as `2207:0006`.
2. With **Settings → About → Beta Program → ADB access** already on, `adb devices -l` initially
   listed the device as `unauthorized`, with no prompt on the screen.
3. Toggling **ADB access** off and back on while the USB-A to USB-C cable stayed plugged in caused
   the frame to re-enumerate and transition straight to `device` (`product:113K model:113K
   device:rk312x`) without showing an on-screen authorization dialog (one computer tested).
4. `adb shell su -c id` returns `uid=0(root) gid=0(root)` immediately with no prompt. SuperSU's
   `su` and `daemonsu` run out of the box without a manager app, so **any installed app can obtain
   root without asking**.

## Partition layout

From `/sys/block/mmcblk0/mmcblk0p*/start` and `size`, in 512-byte sectors (identical to the
[YIAISIGN `10X1`](yiaisign-10x1.md#partition-layout) and [Tibuta `TID10`](tibuta-tid10.md#partition-layout)):

| Node | Name | Start | Sectors |
| --- | --- | --- | --- |
| `mmcblk0p1` | `uboot` | 16,384 | 8,192 |
| `mmcblk0p2` | `misc` | 24,576 | 8,192 |
| `mmcblk0p3` | `resource` | 32,768 | 32,768 |
| `mmcblk0p4` | `kernel` | 65,536 | 24,576 |
| `mmcblk0p5` | `boot` | 90,112 | 28,672 |
| `mmcblk0p6` | `recovery` | 118,784 | 65,536 |
| `mmcblk0p7` | `backup` | 184,320 | 131,072 |
| `mmcblk0p8` | `cache` | 315,392 | 262,144 |
| `mmcblk0p9` | `metadata` | 577,536 | 32,768 |
| `mmcblk0p10` | `kpanic` | 610,304 | 8,192 |
| `mmcblk0p11` | `system` | 618,496 | 2,097,152 |
| `mmcblk0p12` | `radical_update` | 2,715,648 | 131,072 |
| `mmcblk0p13` | `userdata` | 2,846,720 | 58,224,640 |

## What was set up (all in `/data`, `/system` untouched)

The owner chose to skip a full eMMC dump because no `/system` or partition writes were needed on
this firmware. For a full backup before `userdata` on this partition layout, use the
[YIAISIGN backup command](yiaisign-10x1.md#backup) (`N=2846720`).

1. **Disabled vendor updater and test app:**
   ```sh
   adb shell "su -c 'pm disable com.adups.fota; pm hide com.adups.fota; pm disable com.DeviceTest'"
   ```
   Because `com.adups.fota` is marked persistent, its already-running process stayed up until killed
   once (`su -c 'kill -9 <pid>'`); with the package disabled and hidden it did not respawn.
2. **Installed Rootless Pixel Launcher 3.9.1 and Firefox 143.0.4:** downloaded from the pinned
   URLs and verified against the SHA-256 hashes in [`scripts/biuframe-setup.sh`](../scripts/biuframe-setup.sh),
   then installed with `adb install -r`.
3. **Built and installed the Home HQ kiosk (`com.wesbos.homehq`):** built on Linux with Temurin
   JDK 17 (`17.0.20+8`), Android `build-tools;34.0.0` and `platforms;android-34` via
   `dashboard/kiosk/build.sh`, then installed with `adb install -r dashboard/kiosk/build/homehq.apk`.
4. **Enabled floating navigation and launched Home HQ:**
   ```sh
   adb shell pm grant com.wesbos.homehq android.permission.WRITE_SECURE_SETTINGS
   adb shell settings put secure enabled_accessibility_services com.wesbos.homehq/com.wesbos.homehq.NavigationService
   adb shell settings put secure accessibility_enabled 1
   adb shell settings put global stay_on_while_plugged_in 7
   adb shell am start -n com.wesbos.homehq/.MainActivity --ez home true
   ```
5. **Verified the way back on the panel:** held two fingers on the dashboard for 1.5 s, opened
   **Android settings** from the Home HQ dialog, confirmed the floating **Back** and **Dashboard**
   buttons appeared, and returned to the dashboard using the floating **Dashboard** button.
6. **Set Home HQ as the default Home app and disabled Frameo:** opened the Home chooser with
   `adb shell am start -a android.intent.action.MAIN -c android.intent.category.HOME`, selected
   **Home HQ → Always** on the screen, then disabled and hid Frameo:
   ```sh
   adb shell "su -c 'pm disable net.frameo.frame; pm hide net.frameo.frame; sync'"
   ```
   *Gotcha observed:* running `pm disable net.frameo.frame` followed by `adb reboot` 2 seconds later
   lost the disable state because `PackageManagerService` had not yet flushed
   `/data/system/users/0/package-restrictions.xml`. Running `pm hide net.frameo.frame` and checking
   that `grep 'name="net.frameo.frame"' /data/system/users/0/package-restrictions.xml` showed
   `hidden="true" enabled="2"` before rebooting made it stick.

## Undo

```sh
adb shell "su -c 'pm unhide net.frameo.frame; pm enable net.frameo.frame; pm unhide com.adups.fota; pm enable com.adups.fota; pm enable com.DeviceTest'"
adb shell am start -n com.wesbos.homehq/.MainActivity --ez home false
adb shell pm revoke com.wesbos.homehq android.permission.WRITE_SECURE_SETTINGS
adb shell settings put secure enabled_accessibility_services null
adb shell settings put secure accessibility_enabled 0
adb shell settings put global stay_on_while_plugged_in 0
adb uninstall com.wesbos.homehq
adb uninstall amirz.rootless.nexuslauncher
adb uninstall org.mozilla.firefox
```

## Not tested

- Whether `qemu.hw.mainkeys=0` in `/system/build.prop` enables the system navigation bar on this
  firmware (it worked on the Tibuta `TID10` and YIAISIGN `10X1`, but had no effect on the
  Uhale `102KZ`).
- Network ADB (`adb tcpip 5555`).
- Rockchip loader mode and stock recovery.
