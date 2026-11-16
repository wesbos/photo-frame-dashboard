# Denver PFF-1021BMK3 10.1" Frameo frame (RK3126, Android 6.0.1, firmware `F6010T_ZhiHeXing_Frameo_1001`)

Record of one unit, set up on macOS (Apple silicon) on 2026-11-16. Observations are kept separate
from guesses. Unique identifiers (serial, MAC, Wi-Fi name) are left out; they stay in the owner's
private backup folder.

**Result:** ADB over USB from Frameo's own settings, a shipped root `su`, a verified backup of
everything before `userdata`, and the [AVYONA AVN-DPF1009](avn-dpf1009.md) route applied by hand:
the Home HQ [kiosk](../dashboard/kiosk/README.md) as the Home app, Rootless Pixel Launcher, the
updaters and Frameo disabled. The frame boots into a Home Assistant dashboard and keeps its Wi-Fi
and its Home Assistant login across a reboot. Nothing was written to `/system` or a boot partition.
The frame stands in **portrait**, which needed a one-line change to the kiosk manifest
([below](#portrait)).

**Cable:** only a **USB-A to USB-C** data cable worked, here from the USB-A port of an Apple USB-C
Digital AV Multiport Adapter. A USB-C to USB-C cable straight into the Mac enumerated nothing: no
device on the USB bus at all, so this is not an ADB authorization problem.

## How it relates to the known RK3126 frames

The box and the label say PFF-1021BMK3, but Android calls itself `PFF_1024`. It is closest to the
[AVYONA AVN-DPF1009](avn-dpf1009.md): same vendor (Harmony / ZhiHeXing), RK3126, 1 GB RAM, the same
stock WebView and no low-RAM mode. It is unlike the older Denver frames
([PFF-1015](denver-pff-1015.md), [PFF-1024BMK2](denver-pff-1024bmk2.md)), which have 512 MB and
WebView 44.

| | This frame | [AVN-DPF1009](avn-dpf1009.md) |
| --- | --- | --- |
| Model / brand / manufacturer | `Frame` / `denver` / `Harmony` | `Frame` / `AVYONA` / `Harmony` |
| `ro.product.name` / `device` | `PFF_1024` / `PFF_1024` | `AVN-DPF1009` |
| Firmware (display ID) | `F6010T_ZhiHeXing_Frameo_1001-V1.0.1202512161127.release-keys` | `F601_ZhiHeXing_1009-V1.0.1202510091510.release-keys` |
| RAM | 1 GB | 1 GB |
| `ro.config.low_ram` | not set | not set |
| Stock WebView | 107.0.5304.36 | 107.0.5304.36 |
| SystemUI | present, **disabled** out of the box | disabled |
| `userdata` start | sector 2,842,624 | sector 2,842,624 |
| eMMC | 30,621,696 sectors (about 14.6 GiB) | 60,620,800 sectors |

`/system/etc/lowmem_package_filter.xml` exists, but with `ro.config.low_ram` unset the kiosk stayed
alive behind Android Settings and across app switches. No whitelist edit was made.

## Identity

| | |
| --- | --- |
| Sold as | Denver PFF-1021BMK3, a Frameo 10.1" frame. Frameo v1.32.18 (updated itself; `/system/priv-app/Frameo.apk` is v1.29.10) |
| `ro.product.model` / `brand` / `manufacturer` | `Frame` / `denver` / `Harmony` |
| `ro.product.name` / `device` | `PFF_1024` / `PFF_1024` |
| `ro.product.board` / `board.platform` / `hardware` | `rk30sdk` / `rk312x` / `rk30board` |
| `ro.rk.soc` | `rk3126` |
| Build fingerprint | `rockchip/rk312x/rk312x:6.0.1/MXC89K/user.wanghy.20251216.112612:user/release-keys` |
| Display ID | `F6010T_ZhiHeXing_Frameo_1001-V1.0.1202512161127.release-keys`, built 2025-12-16 |
| Android | 6.0.1, API 23, security patch 2017-01-01, kernel 3.10.0 |
| `ro.build.type` / `ro.secure` / `ro.debuggable` | `user` / `1` / `0` |
| SELinux | permissive (`ro.boot.selinux=permissive`) |
| USB (Android running) | product string `Frame`; `adb devices -l` shows `product:PFF_1024 model:Frame device:PFF_1024` |
| eMMC | `mmcblk0`, 30,621,696 sectors of 512 bytes |
| RAM / swap | 1,023,552 kB / 128 MB zram |
| Display | 1280x800, 160 dpi, `ro.sf.hwrotation=270` |
| WebView | `com.google.android.webview` 107.0.5304.36, `/system/app/webview/webview.apk` |
| ABI | `armeabi-v7a,armeabi` |
| PCBA / FOTA strings | `ro.pcba.company.name=ChipTrip`, `ro.fota.oem=chiptrip3126_6.0`, `ro.fota.platform=RK3126_6.0` |
| Power | no battery (`dumpsys battery: present=false`), AC powered |

## Getting ADB and root

1. On the frame: Frameo **Settings → About → Beta program → ADB access**.
2. Connect a **USB-A to USB-C** data cable and power the frame on.
3. `adb devices -l` listed it as `device` straight away.

   The Mac's `adb` had been installed minutes earlier, so its host key was new to the frame.
   SystemUI is disabled, so an "Allow USB debugging" prompt has nowhere to appear, and the frame
   connected anyway. `ro.adb.secure=1` and `/data/misc/adb/adb_keys` exists (735 bytes, dated
   2021-05-15, so it shipped with the firmware). On this unit the key check appears to be skipped,
   as on the Denver PFF-1015 and PFF-1024BMK2.
4. **Root is shipped.** `/system/xbin/su` with `daemonsu` next to it, no manager app and no prompt.
   Both `su 0 id` and `su -c id` answered `uid=0(root) … context=u:r:toolbox:s0`. As on the other
   ZhiHeXing frames, **any app can get root**.

Network ADB on port 5555 was not tested.

**No `iotv`.** There is no `/system/bin/iotv` and no `iotv` process, unlike the
[Runxion RK3126](runxion-zn-dp1002-rk3126.md#hidden-root-agent-iotv) and the
[MQQC AST01](mqqc-ast01-p200.md#iotv-on-this-unit). Init services were not listed, so a `run_iotv`
service under another name is not ruled out.

## Partition layout

Start offsets are identical to the [AVN-DPF1009](avn-dpf1009.md#partition-layout-emmc-mmcblk0-512-byte-sectors)
for every partition checked (`uboot`, `resource`, `kernel`, `boot`, `recovery`, `system`,
`userdata`); only `userdata` is smaller: start 2,842,624, size 27,779,072 sectors. The by-name
links are under `/dev/block/platform/*/by-name`, with the same thirteen names.

## Backup

Read as root over ADB, everything before `userdata`, with the AVN-DPF1009 commands:

```sh
adb shell su 0 dd if=/dev/block/mmcblk0 of=/data/local/tmp/pre-userdata.img bs=512 count=2842624
adb shell su 0 chmod 644 /data/local/tmp/pre-userdata.img
adb pull /data/local/tmp/pre-userdata.img
adb shell su 0 rm /data/local/tmp/pre-userdata.img
```

The `dd` took 94 s and the pull 225 s (6.2 MB/s). Checks that passed:

- Length exactly **1,455,423,488 bytes** (2,842,624 x 512).
- The frame's `md5sum` of the image equals the host MD5. This is MD5 only, with no gzip readback, so it does not meet README rule 2.
- `uboot`, `resource`, `kernel`, `boot`, `recovery` and all of `system`, re-read from the frame
  partition by partition, match the corresponding slices of the pulled image.
- No 1 MiB block of the image is all `0xCC`. The boot slice starts with `ANDROID!` and the system
  slice has an ext4 superblock.

This is a **partial backup**: it excludes `userdata`, there was no gzip readback, and restore is
untested. It covers more than this record writes to (this record writes only to `/data`).

| Partition | Size (bytes) | MD5 |
| --- | --- | --- |
| `boot` (p5) | 12,582,912 | `0a86a34158343e1fbfdbeb6669a68dab` |
| `recovery` (p6) | 33,554,432 | `68961b624a91139d601e1fee3958cf67` |

## Setup

All changes are in `/data`. Each was made with owner approval, one at a time, with the undo
recorded first.

1. **Home HQ kiosk**, built from [`dashboard/kiosk`](../dashboard/kiosk/README.md) on macOS with
   Homebrew `openjdk@17`, build-tools 34.0.0 and platform 34. Installed with `adb install`, URL
   saved with `--es url`.
2. **`settings put global stay_on_while_plugged_in 7`** (it was `0`).
3. **Rootless Pixel Launcher 3.9.1**, the F-Droid APK with the SHA-256 given in the
   [AVN-DPF1009 record](avn-dpf1009.md#setup).
4. **Navigation buttons:** `pm grant com.wesbos.homehq android.permission.WRITE_SECURE_SETTINGS`,
   `settings put secure enabled_accessibility_services com.wesbos.homehq/com.wesbos.homehq.NavigationService`,
   `settings put secure accessibility_enabled 1`. Both settings were `null` before. The floating
   **Back** and **Dashboard** buttons showed over Android Settings.
5. **The owner checked the way back by hand** on the panel: Dashboard button, two-finger menu,
   Android settings, Apps, Back, Dashboard.
6. **Kiosk as Home app.** `am start -n com.wesbos.homehq/.MainActivity --ez home true`, then the
   Home chooser (`am start -a android.intent.action.MAIN -c android.intent.category.HOME`), where
   the owner tapped **Home HQ** and **Always**. `dumpsys package preferred-xml` then showed
   `com.wesbos.homehq/.Home`.
7. **Updaters and Frameo disabled**, all with `su 0 pm disable-user --user 0`:
   `com.adups.fota`, `com.adups.fota.sysoper`, `android.rockchip.update.service`, and
   `net.frameo.frame` last. The factory test apps (`com.cghs.stresstest`, `com.DeviceTest`,
   `com.android.rk`, `com.android.rk.mediafloat`) were left enabled. Reboot 35 s later.

Before disabling Frameo: `/data/misc/wifi/wpa_supplicant.conf` already held the network, so Wi-Fi
is stored by Android here and not only inside Frameo.

Verified after the reboot: `sys.boot_completed=1`, the focused activity is
`com.wesbos.homehq/.Home`, Wi-Fi has its address, the accessibility service is still enabled, the
clock and time zone are right, no Frameo or Adups process is running, and the dashboard is logged
in. USB ADB keeps working with Frameo disabled (`persist.sys.usb.config=adb`).

The **boot animation still shows the Frameo logo** for the roughly 30 s Android takes to start. It
is `/system/media/bootanimation.zip`; it was left alone to keep `/system` untouched.

## Portrait

The kiosk's activity is declared `android:screenOrientation="sensorLandscape"`, so standing the
frame on its short side does nothing, although Android's own auto-rotate is on
(`accelerometer_rotation=1`) and Frameo itself rotated. Changing that one attribute to
`fullSensor` in `dashboard/kiosk/AndroidManifest.xml`, rebuilding and `adb install -r` made the
kiosk follow the frame: the window is 800x1280 and the right way up
(`mCurrentOrientation=3`, with `ro.sf.hwrotation=270`). Signed with the same debug key, the update
kept the saved URL and the web login.

This is a local change, not part of this pull request. An opt-in like the kiosk's other `--ez`
switches would let portrait frames use the stock build.

## Home Assistant on this frame

The saved URL is a Home Assistant dashboard on the LAN over plain HTTP. Android 6 does not resolve
`.local` names, so the URL uses the server's IP address.

- WebView 107 runs the current Home Assistant frontend (2026-11) with no changes to the frame.
- The dashboard is a sections view with built-in cards only (clock, weather forecast, tiles, one
  button): no custom cards, templates or iframes.
- First load takes 20 to 30 s from a cold kiosk; cards appear first, icons last. Once drawn, the
  kiosk idles at about 2 % CPU and about 115 MB PSS.
- The owner logged in on the panel with "keep me logged in"; the login survived a reboot, a force
  stop and the `adb install -r` above.
- The WebView reports a light colour scheme. Dark mode was set per browser on the Home Assistant
  profile page and survived a kiosk restart.
- Use a dedicated non-admin Home Assistant user: any app on the frame can get root, so the login
  on it is readable.

Touch responsiveness was not measured.

## Sensors

`dumpsys sensorservice` lists accelerometer, compass, gyroscope, proximity, light, pressure and
temperature sensors, but only the **accelerometer** (input device `gs_mir3da`) delivers events. The
rest are the Rockchip HAL's placeholders with no readings. There is no camera, microphone or motion
sensor. Backlight is `/sys/class/backlight/rk28_bl` (0 to 255).

## Undo

| Change | Undo |
| --- | --- |
| Updaters disabled | `su 0 pm enable <package>` |
| Frameo disabled | `su 0 pm enable net.frameo.frame`, then pick it under Settings → Home |
| Kiosk installed | `adb uninstall com.wesbos.homehq` |
| Rootless Pixel Launcher | `adb uninstall amirz.rootless.nexuslauncher` |
| Navigation buttons | Settings → Accessibility → Home HQ navigation off; `pm revoke com.wesbos.homehq android.permission.WRITE_SECURE_SETTINGS` |
| Screen always on | `settings put global stay_on_while_plugged_in 0` |

## Not tested

- Restoring the backup, loader mode, stock recovery and fastboot.
- Network ADB on port 5555.
- Whether a second computer's key is also accepted with no prompt.
- Why USB-C to USB-C enumerates nothing.
- Whether a `run_iotv` init service exists under another name.
- A larger zram, and long-run stability (the frame had been running for under an hour).
