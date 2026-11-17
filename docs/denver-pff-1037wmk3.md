# Denver PFF-1037WMK3 10.1" Frameo frame (RK3126, Android 6.0.1, firmware `F6010T_ZhiHeXing_Frameo_1003`)

Record of one unit, set up from WSL2 (Ubuntu 22.04) with Windows `adb.exe` on 2026-11-17.
Observations are kept separate from guesses. Unique identifiers (serial, MAC, Wi-Fi name) are left
out; they stay in the owner's private backup folder.

**Result:** ADB over USB already on (or enabled earlier in Frameo), a shipped root `su`, a verified
backup of everything before `userdata`, and the [AVYONA AVN-DPF1009](avn-dpf1009.md) /
[PFF-1021BMK3](denver-pff-1021bmk3.md) route applied: the Home HQ [kiosk](../dashboard/kiosk/README.md)
as the Home app (built with `fullSensor` for portrait), Rootless Pixel Launcher, the updaters and
Frameo disabled. Nothing was written to `/system` or a boot partition.

## How it relates to the known RK3126 frames

Android calls itself `PFF_1037` (not `PFF_1024`). Same vendor (Harmony / ZhiHeXing), RK3126, 1 GB
RAM, WebView 107, no low-RAM mode, and the **same `userdata` start sector (2,842,624)** as the
[PFF-1021BMK3](denver-pff-1021bmk3.md) and [AVN-DPF1009](avn-dpf1009.md). Firmware family is
`F6010T_ZhiHeXing_Frameo_1003` (January 2026) vs the PFF-1021BMK3's `…_1001` (December 2025).

| | This frame | [PFF-1021BMK3](denver-pff-1021bmk3.md) |
| --- | --- | --- |
| Model / brand / manufacturer | `Frame` / `denver` / `Harmony` | `Frame` / `denver` / `Harmony` |
| `ro.product.name` / `device` | `PFF_1037` / `PFF_1037` | `PFF_1024` / `PFF_1024` |
| Firmware (display ID) | `F6010T_ZhiHeXing_Frameo_1003-V1.0.1202601290915.release-keys` | `F6010T_ZhiHeXing_Frameo_1001-V1.0.1202512161127.release-keys` |
| RAM | 1 GB | 1 GB |
| `ro.config.low_ram` | not set | not set |
| Stock WebView | 107.0.5304.36 | 107.0.5304.36 |
| SystemUI | present, **disabled** out of the box | disabled |
| `userdata` start | sector 2,842,624 | sector 2,842,624 |

## Identity

| | |
| --- | --- |
| Sold as | Denver PFF-1037WMK3, a Frameo 10.1" frame. Frameo v1.29.14 in `/system` at setup |
| `ro.product.model` / `brand` / `manufacturer` | `Frame` / `denver` / `Harmony` |
| `ro.product.name` / `device` | `PFF_1037` / `PFF_1037` |
| `ro.product.board` / `board.platform` / `hardware` | `rk30sdk` / `rk312x` / `rk30board` |
| `ro.rk.soc` | `rk3126` |
| Build fingerprint | `rockchip/rk312x/rk312x:6.0.1/MXC89K/user.wanghy.20260129.091306:user/release-keys` |
| Display ID | `F6010T_ZhiHeXing_Frameo_1003-V1.0.1202601290915.release-keys`, built 2026-01-29 |
| Android | 6.0.1, API 23, security patch 2017-01-01, kernel 3.10.0 |
| `ro.build.type` / `ro.secure` / `ro.debuggable` | `user` / `1` / `0` |
| SELinux | permissive (`ro.boot.selinux=permissive`) |
| USB (Android running) | `2207:0006`, product string `Frame`; `adb devices -l` shows `product:PFF_1037 model:Frame device:PFF_1037` |
| eMMC | `mmcblk0`, 15,388,672 sectors of 512 bytes |
| RAM / swap | 1,023,552 kB / 128 MB zram |
| Display | 1280x800, 160 dpi, `ro.sf.hwrotation=270` |
| WebView | `com.google.android.webview` 107.0.5304.36 |
| ABI | `armeabi-v7a,armeabi` |
| PCBA / FOTA strings | `ro.pcba.company.name=ChipTrip`, `ro.fota.oem=chiptrip3126_6.0`, `ro.fota.platform=RK3126_6.0` |
| Power | AC powered (battery not checked in detail) |

## Getting ADB and root

1. On the frame: Frameo Settings → About → look for **Beta program → ADB access**, or the
   Model-tap / test-app path used on the [PFF-1040LW](frameo-pff-1040lw.md). This unit already
   enumerated as ADB when first checked.
2. Use a **data** USB cable. On the host tested here, Windows platform-tools `adb.exe` saw the
   frame; WSL2 needed `usbipd bind` (admin) for native Linux `adb`, so Windows `adb` was used.
3. `adb devices -l` listed it as `device` with no prompt. SystemUI is disabled, so an "Allow USB
   debugging" dialog has nowhere to appear. `ro.adb.secure=1` and a shipped `adb_keys` file exist;
   on this unit the key check appears to be skipped (one computer tested), as on the PFF-1015 /
   PFF-1024BMK2 / PFF-1021BMK3.
4. **Root is shipped.** `/system/xbin/su` with `daemonsu`. Both `su 0 id` and `su -c id` answered
   `uid=0(root) … context=u:r:toolbox:s0`. **Any app can get root.**

Network ADB on port 5555 was not listening when checked (Wi-Fi had no carrier during setup).

**No `iotv`.** There is no `/system/bin/iotv`.

## Partition layout

`userdata` starts at sector **2,842,624**, same as the PFF-1021BMK3 / AVN-DPF1009. Thirteen
by-name partitions under `/dev/block/platform/*/by-name`.

## Backup

Read as root over ADB, everything before `userdata`:

```sh
adb shell su 0 dd if=/dev/block/mmcblk0 of=/data/local/tmp/pre-userdata.img bs=512 count=2842624
adb shell su 0 chmod 644 /data/local/tmp/pre-userdata.img
adb pull /data/local/tmp/pre-userdata.img
adb shell su 0 rm /data/local/tmp/pre-userdata.img
```

Checks that passed on the kept image:

- Length exactly **1,455,423,488** bytes.
- Frame `md5sum` equals host MD5.
- `uboot`, `kernel`, `boot`, `recovery` and `system` re-read from the matching partitions match
  the corresponding slices of the pulled image.
- No 1 MiB block of the image is all `0xCC`. The boot slice starts with `ANDROID!`.

A first pull's `system` slice later disagreed with a live re-read (boot and other partitions still
matched). A second full pre-`userdata` backup was taken and verified immediately; prefer that one.
This is still a **partial** backup (no `userdata`, restore untested).

| Partition | Size (bytes) | MD5 (verified image) |
| --- | --- | --- |
| `boot` (p5) | 12,582,912 | `f4af932339c73542f6ff1942e5980a55` |
| `recovery` (p6) | 33,554,432 | `27a391530d3afc1b52b57c4aadf818a8` |
| `system` (p11) | 1,073,741,824 | `4345ec770b1f959ea2cc12b393bf8e73` |

## Setup

All changes are in `/data`. Each was made with owner approval (via the bring-up plan), with undo
recorded first.

1. **Home HQ kiosk**, built from [`dashboard/kiosk`](../dashboard/kiosk/README.md) with JDK 17 and
   build-tools / platform 34. `AndroidManifest.xml` `screenOrientation` set to `fullSensor` for
   portrait (local change, same idea as the PFF-1021BMK3). Installed with `adb install`.
2. **`settings put global stay_on_while_plugged_in 7`** (was `0`).
3. **Rootless Pixel Launcher 3.9.1**, F-Droid APK with the SHA-256 in the
   [AVN-DPF1009 record](avn-dpf1009.md#setup).
4. **Navigation service** granted `WRITE_SECURE_SETTINGS` and enabled in secure settings.
5. **Kiosk as Home app** via `am start … --ez home true` and the Home chooser (**Home HQ** →
   **Always**). After the first reboot the preferred entry briefly showed `always="false"` while
   the kiosk still came up (Frameo disabled); it was corrected back to `always="true"`.
6. **Updaters and Frameo disabled** with `su 0 pm disable-user --user 0`:
   `com.adups.fota`, `com.adups.fota.sysoper`, `android.rockchip.update.service`, then
   `net.frameo.frame`. Wait ≥30 s, then reboot.

Wi-Fi is stored by Android in `/data/misc/wifi/wpa_supplicant.conf`. On this unit, tapping a
scanned network in Android's Wi-Fi settings crashed Settings ("Unfortunately, Settings has
stopped") — likely tied to SystemUI being disabled, so the password dialog has nowhere safe to
draw. **Workaround:** Wi-Fi → overflow menu → Advanced → **WPS push button**. That joined the
network; DHCP, validated internet and network time all worked afterward, and the credential was
kept across a reboot. Temporarily enabling SystemUI (`su 0 pm enable com.android.systemui`) was
not tried as an alternate fix for the password dialog.

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
- Long-run stability.
