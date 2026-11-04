# Pastigio 15.6" Frameo frame (`FRAME156`, RK3326, Android 8.1)

Original record of one unit, started 2026-10-09, with an [additional macOS unit report](#additional-unit-tested-on-macos-2026-10-12) below. Observations are kept separate from guesses. Unique
identifiers (serial, MAC, IP) are left out; they live in the ignored `backups/` and `diagnostics/` folders.

## Observations (read-only unless noted)

### Identity

| | |
| --- | --- |
| Brand / model | `Pastigio` / `FRAME156` (`ro.product.device=FRAME156`) |
| Firmware | `FrameO.DP105F.v2026010414`, built 2026-01-04 |
| Fingerprint | `rockchip/rk3326_32bit/rk3326_32bit:8.1.0/OC/145229:user/release-keys` |
| SoC | Rockchip RK3326 (`ro.board.platform=rk3326`), ARMv8 cores with a 32-bit userspace (`armeabi-v7a`) |
| Android | 8.1.0, API 27, security patch 2020-11-05 |
| Display | 1920x1080, 170 dpi |
| RAM / storage | about 1 GB RAM, 29 GB eMMC (`mmcblk2`), userdata 26 GB |
| WebView | `com.android.webview` 106.0.5249.126 (already current for this repo's Vite target) |
| Boot | verified boot `unsupported`, `ro.boot.flash.locked=1`, SELinux **permissive** on the kernel command line, `veritymode=enforcing` |
| Wi-Fi | onboard radio works (`wlan0`) |

USB: the stock "Enable transfer from computer" setting makes the frame enumerate as
`FRAME156` (WinUSB) and then as an Android Open Accessory device (`18D1:2D00`). That is Frameo's
photo-transfer mode, **not ADB**. ADB shows up (`18D1:0006`, product `FRAME156`) only after
Frameo **Settings -> About -> Beta -> ADB Access** is enabled and "transfer from computer" is off.

### Root

`adb shell su -c id` returns `uid=0(root)` immediately, with no prompt and no manager app. `/system/xbin/su` exists
(75 KB, owner root). `adb shell` itself is uid 2000. **Any app on the frame can probably get root without asking.**

### Software of interest

| Package | Location | Notes |
| --- | --- | --- |
| `net.frameo.frame` v1.29.13 | `/system/priv-app/DP_Frameo` | The slideshow app and the **HOME** activity. System app, cloud connected. |
| `com.muxintu.app.mxota` v1.2.5 | `/system/app/MXOTA` | Vendor OTA updater with `INTERNET`. Disable before going online. |
| `com.szclink.app.cldevicetest` | `/system/app/DP105DeviceTestSM` | Factory test app. |
| `com.android.launcher3` | system | Stock launcher, disabled-by-default state not recorded. |

No browser installed.

### Partition table (eMMC `mmcblk2`, 512-byte sectors)

| Partition | Name | Start | Size (sectors) |
| --- | --- | --- | --- |
| p1 | uboot | 16384 | 8192 |
| p2 | trust | 24576 | 8192 |
| p3 | misc | 32768 | 8192 |
| p4 | resource | 40960 | 32768 |
| p5 | kernel | 73728 | 65536 |
| p6 | boot | 139264 | 77824 |
| p7 | recovery | 217088 | 143360 |
| p8 | backup | 360448 | 229376 |
| p9 | security | 589824 | 8192 |
| p10 | cache | 598016 | 786432 |
| p11 | system | 1384448 | 3145728 |
| p12 | metadata | 4530176 | 32768 |
| p13 | vendor | 4562944 | 786432 |
| p14 | oem | 5349376 | 262144 |
| p15 | frp | 5611520 | 1024 |
| p16 | userdata | 5612544 | 55450560 |

## Backup (2026-10-09, verified)

`backups/<serial>/emmc-0-5612544.img.gz` (ignored by git): eMMC sectors 0-5,612,544, everything before `userdata`,
2,873,622,528 bytes raw, 605.7 MB gzipped. The SHA-256 of the raw stream equals the gzip readback hash.
No 1 MiB block is entirely `0xCC`. Independent re-reads match the backup for `uboot`, `trust`, `misc`, `resource`,
`kernel`, `boot`, `recovery`, `security`, `backup`, `system` (all 1.5 GiB), `vendor`, `metadata` and `frp`.
`oem` (mounted read-only at `/oem`) differs in one byte: byte 43 of the ext4 journal header page at
partition offset `0x17000` is `0x02` now and `0x00` in the backup. That fits a journal flag the kernel sets at mount time, but
it is a guess; fresh reads of `oem` are identical to each other. `cache` and `userdata` are not in the backup.
`mmcblk2boot0/1`, `rpmb` and `userdata` were not backed up.

Two traps on this setup, both seen in practice:

- **`adb exec-out "su -c ..."` turns every LF byte into CR LF**, so a raw `dd` stream is longer than the partition and
  its hash is wrong. `stty -onlcr` and `dd of=/proc/self/fd/1` do not fix it. Piping through `base64` on the frame and
  `tr -d '\r' | base64 -d` on the PC gives byte-exact data. This was the first backup attempt's failure
  (2,879,386,296 bytes against 2,873,622,528 expected).
- **`dd` on the whole-disk node `/dev/block/mmcblk2` cannot seek past 2 GiB** (`Invalid argument`, 32-bit userspace),
  so re-reading `vendor` or `oem` by sector offset returns nothing. Read the partition node (`mmcblk2p13`) instead.
  A sequential read from sector 0 (as the backup does) is fine.

Restore would need Rockchip loader mode and `rkdeveloptool`; neither has been tried on this unit.

## Status against the README phase map

| Phase | State |
| --- | --- |
| 1 Identify | Done. Not a BIUFRAME or Skylight, so neither device guide applies as written. |
| 2 ADB | Done, via the Frameo beta menu. |
| 3 Loader mode | Not needed so far. Not tested. |
| 4 Back up | Done and verified (see Backup). Restore path untested. |
| 5 Root | Shipped `su` works. |
| 6 Make it useful | Done: kiosk installed and set as the Home app (see Changes made). The kiosk in this repo has no HOME intent filter; that was a local change, not included. |
| 7 Networking | Onboard Wi-Fi works. |
| 8 Vendor updates | Pending: disable `com.muxintu.app.mxota` before relying on the frame. |
| 9 Security hand-off | Pending. |

## Guesses (unverified)

- Whether `/system` can be remounted read-write the way the BIUFRAME steps assume, given `veritymode=enforcing`. (Answered on a [third unit](#third-unit-dpf-frame-156-firmware-v2026051219-2026-10-15): yes, `/system` is not on a dm-verity device there.)
- Whether Frameo re-launches itself over a third-party HOME or kiosk app.
- Whether Frameo's cloud or the OTA app can replace system files on their own.

## Host note

This host also runs SuperDisplay, whose bundled ADB v40 fights the current platform-tools
server (v41) for the device. Stop its service while working on the frame.

## Changes made to the frame (2026-10-09 to 10-10)

All reversible; nothing under `/system` or any flash partition was written after the verified backup.

| Change | How | Undo |
| --- | --- | --- |
| Vendor OTA app off | `pm disable-user --user 0 com.muxintu.app.mxota` | `pm enable com.muxintu.app.mxota` |
| Frameo off | `pm disable-user --user 0 net.frameo.frame` | `pm enable net.frameo.frame` (its data is untouched) |
| Kiosk installed | `adb install -r dashboard/kiosk/build/homehq.apk` (`com.wesbos.homehq`) | `adb uninstall com.wesbos.homehq` |

Verified after a reboot: boots into the kiosk (set as the home app), `sys.boot_completed=1`, ADB returns, Frameo and the OTA app are not running.

### Motion sensor

A `pir-s18` node exists in the device tree with `status = "disabled"`; no driver is bound. Reading pin 17 of each GPIO
bank (17, 49, 81, 113) for 45 s while someone moved in front of the frame showed no changes, so no working PIR was
found; this does not rule out a fitted but unpowered sensor. Not pursued further for now.

### Security notes for the owner

- `su` gives root with no prompt and no manager app, so any app installed on this frame can take root. Install nothing untrusted.
- Android 8.1 with a 2020-11 security patch; SELinux is permissive. Keep the frame on a guest or IoT network.
- Management was done over USB ADB. Network ADB (5555) was also found open on the Wi-Fi address on 2026-10-10; how it was enabled was not recorded. Until it is closed, anything on the network can reach ADB, so keep the frame on an isolated network.

## Additional unit tested on macOS (2026-10-12)

Another owner's `FRAME156` matched the firmware, RK3326, Android 8.1/API 27, security patch,
1920x1080 display at 170 dpi, WebView 106 and partition table above. The host ran macOS 26.6.2.
These observations apply to this unit; the cause of the host USB behavior remains unproven.

| Additional observation | Value |
| --- | --- |
| ADB USB vendor/product | `2211:0006`, product/model `FRAME156` |
| Frameo updated system app | `v1.32.12_-_OTA_test` under `/data/app`; original system APK `v1.29.13` |
| Stock launcher | `com.android.launcher3` was already disabled before kiosk installation |
| Root and SELinux | Shipped `su` returned uid 0 without a manager prompt; ordinary shell was uid 2000; `getenforce` reported `Permissive` |
| Boot properties | `ro.boot.veritymode=enforcing`, `ro.boot.flash.locked=1` |
| eMMC size | `/dev/block/mmcblk2`, 31,264,342,016 bytes |

### ADB authorization and reconnecting after a reboot

With Frameo **Settings -> About -> Beta Program -> ADB Access** enabled and computer photo
transfer off, the host initially showed `unauthorized`. Accepting Frameo's own warning, which
linked to `frameo.com/adb_faq`, changed the host status to `device`. The authorization succeeded
without injecting an ADB key or using a loader.

Attempts to enter Rockchip loader mode with the power button did not yield a recognized loader
on this unit. A black display also occurred while ordinary Android ADB was enumerating.
This does not establish that loader mode is impossible, and a black display alone is not proof
of loader entry. The successful FRAME157 procedure in #39 concerns a different model/firmware.

During earlier cable testing, moving the USB adapter to another host port exposed the current
connection state after the host appeared to retain an old USB enumeration. That may be host or
adapter dependent.

After `adb reboot`, the host did not re-enumerate the frame within 150 seconds, although the
owner reported that the kiosk had returned. Disconnecting and reconnecting USB on the frame
side restored ADB. A changed kernel boot ID and `sys.boot_completed=1` confirmed a new boot.
The kiosk was still the default HOME and resumed activity; Frameo and the OTA app remained
disabled. The cause of the USB reconnection behavior was not established.

### Full eMMC and boot-region backup

Captured the complete eMMC through the shipped `su`, compressing the stream on the device and
encoding it in base64 before transport. The method above gave a byte-exact 1 MiB probe with
matching device/host SHA-256. Unencoded `su` newline behavior was not separately retested on
this unit.

The full gzip readback produced exactly 31,264,342,016 bytes, including `cache` and `userdata`.
No complete 1 MiB block consisted of `0xCC` filler. Independent device reads matched the saved
ranges for `uboot`, `trust`, `misc`, `resource`, `kernel`, `boot`, `recovery`, `backup`, `security`,
`system`, `metadata`, `vendor` and `frp`.

`oem` reproduced the one-byte difference described above: partition offset `0x1702b` was `0x00`
in the full capture and `0x02` in the later read. The containing page had the JBD journal
superblock magic `0xc03b3998`. A separate current OEM capture matched two further device reads.
The reason for the change was not proven.

Both 4 MiB `mmcblk2boot0` and `mmcblk2boot1` regions were also captured, each with exact gzip
readback size and two matching device hashes. `rpmb` was not captured.

Android stayed running during the full eMMC capture. `cache` and `userdata` were not compared
against later live reads, so this is **not a transactional filesystem snapshot**. After Frameo
was disabled, its private data, local media directory and installed APK were additionally
archived and the tar was read back successfully. Dumps, APKs and whole-disk hashes stayed private.
Firmware restoration and physical loader entry remain unverified.

**Don't share a pre-userdata dump.** Sectors before `userdata` still hold per-unit data: chip and
UID records in all five idbloader copies, Rockchip vendor storage in unpartitioned space, and
Frameo licence and UUID files in `vendor` (also in its ext4 journal). Removing them may stop Frameo
from activating. Restoring one unit's dump to another frame has not been tested (#209, #211).

### Kiosk startup and dashboard aspect ratio

A separately implemented WebView kiosk with a HOME intent filter loaded the published demo
using the existing WebView and CA store. The HOME component was selected with
`cmd package set-home-activity --user 0 <kiosk-package>/<activity>`. Frameo and
`com.muxintu.app.mxota` were disabled using the `pm disable-user` commands above, preserving
their installed packages and data. The existing undo commands still apply. The kiosk opened
automatically after a reboot. No change to `/system`, `/vendor`, `/oem` or firmware partitions
was needed for installation.

The published demo's fixed 1280x800 stage fitted this 1920x1080 display at 1728x1080, leaving
96-pixel black bars on each side. This was the page layout, rather than an Android window-size
limit. A local kiosk adaptation kept the logical width at 1280, adjusted the logical height to
the screen aspect ratio and compacted the home view's vertical rows, filling 1920x1080 with a
uniform scale. Device screenshots confirmed the result; separate browser tests checked stage
bounds, visible home controls, repeat application and navigation through all seven sections at
1920x1080 and 1280x800. The aspect-ratio change was tested after the reboot/startup check and
is only reported here; this contribution does not change the dashboard implementation.

Motion/PIR support, firmware restoration, other units and other firmware versions were not
tested in this report.

## Third unit: "DPF Frame 156", firmware v2026051219 (2026-10-15)

> **Record, not a procedure.** This unit had no full eMMC backup, so the `/system` WebView swap below
> does not meet README rule 2. The root script that did the swap is not in this repo, and the undo
> below was not run. Read it as what one owner did, not as steps to follow.

A third unit, bought on Amazon.ca as the Pastigio 15.6" listing. Frameo **Settings -> About** names it
`DPF Frame 156` rather than `FRAME156`, but the ADB properties match the earlier units' model on newer
firmware. Host: macOS through a USB hub.

| Observation | Value |
| --- | --- |
| `ro.product.model` / `ro.product.device` | `FRAME156` / `FRAME156` |
| Firmware | `FrameO.DP105F.v2026051219` (earlier units: `v2026010414`) |
| Fingerprint | `rockchip/rk3326_32bit/rk3326_32bit:8.1.0/OC/192521:user/release-keys` |
| ABI | `armeabi-v7a,armeabi` |
| Display | 1920x1080, 170 dpi |
| Frameo | `net.frameo.frame` v1.32.16 (updated), system copy v1.30.19 |
| WebView as shipped | `com.android.webview` 106.0.5249.126 at `/system/app/webview/webview.apk`, vendor-signed |
| `/system` mount | `/dev/block/mmcblk2p11` ext4 `ro`, **no `/dev/block/dm-*` devices**, although `ro.boot.veritymode=enforcing` |
| Root | Shipped `su -c` returns root without a prompt |

### ADB

With computer photo transfer off and **Settings -> About -> Beta -> ADB access** on, the host first
showed `unauthorized`. Turning ADB access off and on again with the cable connected, then accepting
Frameo's ADB warning, changed it to `device`. No key injection or loader was needed. `adb tcpip 5555`
drops the USB connection for a few seconds, so ADB commands run straight after it fail with
`no devices/emulators found`.

### Kiosk as Home app

`dashboard/kiosk` (`com.wesbos.homehq`) installed and `pm grant ... WRITE_SECURE_SETTINGS` succeeded.
The owner's local build was also made device owner with `dpm set-device-owner`. The repo's kiosk has
no device admin receiver, so that step doesn't apply to it. Don't make an app device owner: it
can't be removed without the app's help or a factory reset. The `.Home` alias ships disabled, so `cmd package set-home-activity com.wesbos.homehq/.Home`
fails with `cannot be home on user 0` until the app has enabled it. This order works:

```bash
adb shell am start -n com.wesbos.homehq/.MainActivity --ez home true
adb shell cmd package set-home-activity com.wesbos.homehq/.Home
```

The dashboard's fixed 1280x800 stage again showed 96-pixel side bars at 1920x1080, as on the second unit.

### WebView 138 in place of the vendor WebView 106

`adb install -r` of the LineageOS `com.android.webview` 138.0.7204.63 (armeabi-v7a, minSdk 26) failed with
`INSTALL_FAILED_UPDATE_INCOMPATIBLE` (signatures do not match), so the vendor WebView cannot be updated as
an app. 138 is the newest build for Android 8.1: LineageOS 139 requires minSdk 29.

| File | Source | SHA-256 |
| --- | --- | --- |
| `webview.apk` 138.0.7204.63 ARM | LineageOS [`android_external_chromium-webview_prebuilt_arm` at `b2639126d02b`](https://github.com/LineageOS/android_external_chromium-webview_prebuilt_arm/commit/b2639126d02b401ae8a8a7f3ca302633713a12e6), Git LFS object on LineageOS Gerrit | `b7268786318f404bdad53eaaec889619ff30100b935541a9e393e32efed3cf11` |
| `lib/arm/libwebviewchromium.so` | extracted from that APK (`lib/armeabi-v7a/`) | `d217fc3847fad5cecc1f37ffa8461b95fc2bb32586f63f01285381239c11b03d` |
| `lib/arm/libcrashpad_handler_trampoline.so` | extracted from that APK (`lib/armeabi-v7a/`) | `e16d7cd6d1669d6da68997099425501f8bb6d6f0ae3bb6c8dbbb0bc8e0f4441d` |

GitHub serves only the 133-byte LFS pointer for this file (its `oid` is the SHA-256 above). The
object downloads from LineageOS's Gerrit LFS endpoint (tested 2026-10-15):

```bash
href=$(curl -s -X POST -H "Accept: application/vnd.git-lfs+json" -H "Content-Type: application/vnd.git-lfs+json" \
  -d '{"operation":"download","transfers":["basic"],"objects":[{"oid":"b7268786318f404bdad53eaaec889619ff30100b935541a9e393e32efed3cf11","size":90257078}]}' \
  https://review.lineageos.org/LineageOS/android_external_chromium-webview_prebuilt_arm/info/lfs/objects/batch \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["objects"][0]["actions"]["download"]["href"])')
curl -sfL "$href" -o webview-138.0.7204.63-arm.apk   # signed link, valid for 60 seconds
echo "b7268786318f404bdad53eaaec889619ff30100b935541a9e393e32efed3cf11  webview-138.0.7204.63-arm.apk" \
  | shasum -a 256 -c - &&
unzip -j webview-138.0.7204.63-arm.apk 'lib/armeabi-v7a/*' -d lib-arm && shasum -a 256 lib-arm/*.so
```

Because `/system` on this unit is a plain ext4 mount with no dm-verity device, the whole
`/system/app/webview` tree was replaced through root, following the
[PF1007L procedure](allwinner-a33-pf1007l.md#6-upgrade-webview-before-using-the-kiosk):

1. Pulled the stock tree to the host (`adb pull /system/app/webview`, 3 files, about 211 MB). Its
   hashes were not recorded, so there is nothing to compare the stock tree against before a write.
2. Extracted `lib/armeabi-v7a/libwebviewchromium.so` and `libcrashpad_handler_trampoline.so` from the APK
   on the host and pushed `webview.apk`, `lib/arm/*.so` and their MD5 list to `/data/local/tmp`.
3. A root script checked the staged MD5s and refused existing staging or rollback paths. It checked
   free space (about 700 MB free on `/system`), ran `mount -o remount,rw /system`, built
   `/system/homehq-new-webview` (root:root, 0755 directories, 0644 files, `u:object_r:system_file:s0`)
   and re-checked the MD5s. It then moved the stock tree to `/system/homehq-stock-webview`, moved the new
   tree to `/system/app/webview`, checked the MD5s again, ran `sync` and remounted `/system` read-only.
4. After `adb reboot`: `dumpsys webviewupdate` reported `com.android.webview, 138.0.7204.63`,
   `codePath=/system/app/webview`, and logcat had no WebView `dlopen` errors. The device booted normally,
   and the kiosk dashboard rendered on 138 with the frame's CA store.

Undo (described, never run, and not guarded: the stock tree's hashes were not recorded): remount
`/system` read-write, move `/system/app/webview` aside, move `/system/homehq-stock-webview`
back to `/system/app/webview`, remount read-only and reboot. Repeated `ffmExtractor ... libffmpeg_utils.so not found`
lines in logcat come from the media server, not WebView.

### Disabling Frameo and the updater

After checking that the kiosk's two-finger hold -> **Android settings** reaches Settings -> Apps,
`pm disable-user --user 0` for `com.muxintu.app.mxota` and `net.frameo.frame` printed
`new state: disabled-user`. However, an `adb reboot` run straight after it brought both back:
`enabled=0` and both processes running. Nothing in logcat re-enabled them. Running the same two commands again, waiting about 30 seconds and checking
`/data/system/users/0/package-restrictions.xml` (both `enabled="3"`) before rebooting made the
change survive the reboot, with neither app running afterwards. This is probably Android's
delayed write of package restrictions, not anything the vendor does. Wait, or check the file, before
rebooting. The system copy's `User 0` line in `dumpsys package` stays at `enabled=0`. That is normal;
the first `User 0` line is the one that counts.

Not tested on this unit: whether a Frameo or `com.muxintu.app.mxota` OTA (both now disabled) would restore the vendor
WebView, a full eMMC backup, and loader mode.

## Fourth unit: firmware v2026051219, tested on macOS (2026-10-18)

Another `FRAME156` on the same firmware as the unit in
[the third unit](#third-unit-dpf-frame-156-firmware-v2026051219-2026-10-15). Host: Intel Mac, USB through a
Thunderbolt dock. The frame stayed offline until after the backup and the OTA app was disabled.

| Observation | Value |
| --- | --- |
| Model / firmware | `FRAME156`, `FrameO.DP105F.v2026051219` |
| Fingerprint | `rockchip/rk3326_32bit/rk3326_32bit:8.1.0/OC/192521:user/release-keys` |
| USB (ADB) | `2218:0006`, vendor string `rockchip`, product `FRAME156`, interface class `ff/42/01` |
| Frameo | `net.frameo.frame` v1.30.19 at `/system/priv-app/DP_Frameo` (not updated; kept offline) |
| Launcher3 | Already disabled when received |
| WebView | `com.android.webview` 106.0.5249.126 |
| Root / SELinux | Shipped `su -c id` gives uid 0 without a prompt; `Permissive` |
| eMMC | 31,268,536,320 bytes (61,071,360 sectors) |
| Partitions | p1-p15 identical to the [table above](#partition-table-emmc-mmcblk2-512-byte-sectors); `userdata` is 55,458,752 sectors (first unit: 55,450,560) |

The ADB USB vendor ID differs between units: `18D1` (first unit), `2211` (second unit), `2218`
(this one). Match on product `FRAME156` and the ADB interface class, not on the vendor ID.

### ADB authorization

With ADB Access on and computer photo transfer off, the host showed `unauthorized`. **No prompt or
Frameo warning appeared on the screen** at any point. It stayed `unauthorized` through a server
restart and three minutes of polling. After ADB Access was turned off and on again, the state did
not change by itself within a minute, but `adb kill-server` followed by `adb start-server` turned it
into `device` within about 4 seconds. No key injection or loader was needed.

The host's old SDK `adb` 1.0.36 also saw the frame as `unauthorized` but logged
`Unable to create an interface plug-in (e00002be)`. Current platform-tools (37.0.1, ADB 1.0.41)
was used for everything else.

### Backup of everything before userdata (verified)

Sectors 0-5,612,544 (2,873,622,528 bytes) were captured with the base64 method from
[Backup](#backup-2026-10-09-verified):

```sh
adb exec-out "su -c 'dd if=/dev/block/mmcblk2 bs=524288 count=5481 2>/dev/null | gzip -1 | base64'" \
  | tr -d '\r' | base64 -D > emmc-0-5612544.img.gz   # macOS; use base64 -d on Linux
```

A 1 MiB probe of `uboot` first matched its device-side SHA-256. The full capture took about 10
minutes (568 MB gzipped). The gzip readback was exactly 2,873,622,528 bytes, and its SHA-256 matched
a separate device-side read of the same range. No 1 MiB block was entirely `0xCC`. Per-partition
re-reads on the device matched the backup for `uboot` through `frp`, except `oem`, which differed in
exactly one byte at partition offset `0x1702b` (`0x00` in the backup, `0x02` later), inside the JBD
journal superblock (magic `c03b3998`). This is the same byte as on both earlier units. Here it
changed within minutes, between two reads, while `/oem` was mounted read-only. `userdata`,
`mmcblk2boot0/1` and `rpmb` were not captured. Restore was not tested.

### Kiosk, Frameo and reboot

The kiosk was installed and made Home with the `--ez home true` and `set-home-activity` order from
the [kiosk README](../dashboard/kiosk/README.md#start-at-boot). Before Frameo was disabled, ADB was
confirmed to depend on Android settings rather than Frameo (`settings get global adb_enabled` = `1`,
`persist.sys.usb.config` = `adb`), and the kiosk's two-finger hold -> **Android settings** was
checked on the panel.

`pm disable-user --user 0` was run for `com.muxintu.app.mxota` (well before the reboot)
and `net.frameo.frame` (shortly before it; neither delay was measured). After `adb reboot` the frame
booted into the kiosk, both apps stayed disabled and not running, and ADB was back in about 18
seconds **without replugging USB**. The kiosk WebView kept its login across the reboot. Compare
[the third unit](#third-unit-dpf-frame-156-firmware-v2026051219-2026-10-15), where an immediate reboot
undid `disable-user`.

### Networking

Onboard Wi-Fi joined the network and reconnected after the reboot. Network ADB (port 5555) was
not listening. **mDNS `.local` names do not resolve** on this Android 8.1 build
(`ping homeassistant.local` gives `unknown host`), so a kiosk URL like
`http://homeassistant.local:8123/...` fails. Use an IP address or a regular DNS name. A Home
Assistant dashboard over plain `http://` loaded in the kiosk on WebView 106.

Motion/PIR, loader mode, firmware restore and a WebView upgrade were not tested on this unit.

## Fifth unit: "DPF Frame 156", firmware v2026010414, tested on macOS (2026-10-24)

A fifth unit, named `DPF Frame 156` in Frameo **Settings -> About**, on the original firmware.
It was tested from an Apple silicon Mac (macOS 27.0, platform-tools 37.0.1). USB used a
USB-A to USB-C data cable through a USB-C to USB-A adapter. `ro.product.model` and
`ro.product.device` are `FRAME156`. It matched the [identity table](#identity) above
(`FrameO.DP105F.v2026010414`, RK3326, Android 8.1/API 27, 1920x1080 at 170 dpi, WebView 106,
Frameo v1.29.13, `su` root, `com.android.launcher3` already disabled,
`ro.boot.veritymode=enforcing`, `ro.boot.flash.locked=1`). USB ADB appeared as `2211:0006`,
product `FRAME156`.

### ADB authorization and persistence

With Frameo **Settings -> About -> Beta Program -> ADB Access** on and computer photo transfer off,
the host first showed `unauthorized`. No authorization dialog appeared on the frame through
replugging, a reboot, or toggling ADB Access. The Mac showed its own accessory prompt; after that the
transport became `device`. `/data/misc/adb/adb_keys` contained the host's public key (739 bytes,
`system:shell`, `0640`, `u:object_r:adb_keys_file:s0`). After `adb reboot`, a fresh Wi-Fi connection
authorized from that file, so the authorization was persistent rather than in-memory. No loader or
key injection was needed. If the file is missing on another unit, writing `~/.android/adbkey.pub`
there through the shipped root shell is the equivalent; this unit already had it.

### Network ADB across reboots

Port 5555 was closed before `adb tcpip 5555`. After it, `service.adb.tcp.port=5555` and the port was
open. Setting `persist.adb.tcp.port=5555` kept it open after a reboot; `persist.internet_adb_enable=1`
was set too, but the Rockchip init hook described for the RK3326 S101 build was not found under
`/vendor/etc/init/` on this unit. `ro.adb.secure=1`, so the stored key is required. USB did not
re-enumerate within the post-reboot wait; Wi-Fi ADB on 5555 did.

### Backup and kiosk setup

Sectors 0-5,612,544 (2,873,622,528 bytes) were captured with the base64 method from
[Backup](#backup-2026-10-09-verified). `boot`, `recovery` and `vendor` hashes matched fresh device
reads; the whole-disk hash and identifiers stayed private. `userdata`, `mmcblk2boot0/1` and `rpmb`
were not captured.

The kiosk (`homehq.apk` 1.2) was installed, its URL saved, `WRITE_SECURE_SETTINGS` granted, the
accessibility navigation service enabled, `stay_on_while_plugged_in=7` set, the timezone set to
the owner's local zone, and the `.Home` alias enabled before `cmd package set-home-activity` (same order as
the [kiosk README](../dashboard/kiosk/README.md#start-at-boot)). `com.muxintu.app.mxota` and
`net.frameo.frame` were disabled with `pm disable-user --user 0`. After a reboot the kiosk was HOME,
both packages stayed disabled and were not running, the navigation service and stay-on setting
survived, and ADB returned over Wi-Fi.

### User CA store for a self-hosted HTTPS dashboard

The kiosk targets SDK 23, so it trusts user-installed CAs. The dashboard server's local root CA plus
ISRG Root X1 and GTS Root R4 were installed in `/data/misc/user/0/cacerts-added/` as
`<subject_hash_old>.0`, owned `system:everybody`, mode `0644`. Deleting the three files undoes it.
The server certificate's SAN included its LAN IP, so hostname verification passed. This path worked
on Android 8.1; the keychain path did not.

### Aspect ratio and boot logo

The fixed 1280x800 stage again fitted the 1920x1080 panel at 1728x1080, leaving 96-pixel bars.
`wm size 1920x1200` did **not** remove them: Android scaled the logical display preserving aspect, so
the stage stayed 1728x1080; `wm size reset` restored the native size. The merged
[#226](https://github.com/wesbos/photo-frame-dashboard/pull/226) fixes this by keeping the 800 px
design height and widening the stage to the screen's aspect; 16:10 frames are unchanged. This unit's
dashboard build predated that change.

The vendor `bootanimation.zip` still shows Frameo branding at boot. Frameo is disabled and not
running (`ps` shows no Frameo process); the logo is cosmetic. Replacing it needs a `/system` write and
was not attempted.

Motion/PIR, loader mode, firmware restore and a WebView upgrade were not tested on this unit.
