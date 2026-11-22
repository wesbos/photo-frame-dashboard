# Pastigio 15.6" Frameo frame (`FRAME156`, RK3326, Android 8.1)

Original record of one unit, started 2026-10-09, with an [additional macOS unit report](#additional-unit-tested-on-macos-2026-10-12) below. Observations are kept separate from guesses. Unique
identifiers (serial, MAC, IP) are left out; they live in the ignored `backups/` and `diagnostics/` folders.

Units on the older firmware `v2025052119` report Android model `M15R4`; see
[Model M15R4](#model-m15r4-firmware-v2025052119-sixth-to-eighth-units).

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

Sectors 0–5,612,543 (2,873,622,528 bytes) were captured with the base64 method from
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
`/vendor/etc/init/` on this unit. `ro.adb.secure=1` was reported and the authorized host reconnected;
rejection of a fresh key was not tested. USB did not
re-enumerate within the post-reboot wait; Wi-Fi ADB on 5555 did.

### Backup and kiosk setup

Sectors 0–5,612,543 (2,873,622,528 bytes) were captured with the base64 method from
[Backup](#backup-2026-10-09-verified). `boot`, `recovery` and `vendor` hashes matched fresh device
reads; the whole-disk hash and identifiers stayed private. `userdata`, `mmcblk2boot0/1` and `rpmb`
were not captured. This is a partial backup and does not meet the full-device backup rule.

The kiosk (`homehq.apk` 1.2) was installed, its URL saved, `WRITE_SECURE_SETTINGS` granted, the
accessibility navigation service enabled, `stay_on_while_plugged_in=7` set, the timezone set to
the owner's local zone, and the `.Home` alias enabled before `cmd package set-home-activity` (same order as
the [kiosk README](../dashboard/kiosk/README.md#start-at-boot)). `com.muxintu.app.mxota` and
`net.frameo.frame` were disabled with `pm disable-user --user 0`. After a reboot the kiosk was HOME,
both packages stayed disabled and were not running, the navigation service and stay-on setting
survived, and ADB returned over Wi-Fi.

### User CA store for a self-hosted HTTPS dashboard

The current kiosk targets SDK 28 and explicitly trusts user-installed CAs through its
[network security configuration](../dashboard/kiosk/res/xml/network_security_config.xml). The dashboard server's local root CA plus
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

## Model M15R4, firmware v2025052119 (sixth to eighth units)

Three more units bought as FRAME156 run the older firmware `FrameO.DP105F.v2025052119`. Android reports the
model as **`M15R4`**, and the stock WebView is **61**, not 106. The partitions before `userdata` match the
[table above](#partition-table-emmc-mmcblk2-512-byte-sectors). eMMC size and USB product ID vary by unit.

### Sixth unit: macOS, backup, Loader and WebView 138 (2026-11-10)

Investigated 2026-11-10. A record of one owner's unit, not a flashing guide. Host: macOS 26.5.2 on
Apple silicon (M1 Pro), platform-tools 37.0.1 (ADB 1.0.41), USB ADB.

Sold as a Pastigio 15.6" Frameo frame, but the Android model is **`M15R4`**, not `FRAME156`. It runs
the same `FrameO.DP105F` firmware family, partition table and shipped `su` as the
[FRAME156](pastigio-frame156.md) and [FRAME157](pastigio-frame157.md), on **older firmware**
(`v2025052119`) with **stock WebView 61** instead of 106.

End result: a verified backup of every partition except `userdata` and `cache`; Loader mode
reached and left again; the vendor WebView 61 replaced by WebView 138 in `/system`; Fully Kiosk
Browser as HOME, showing a dashboard page from local storage; Frameo and both vendor updaters
disabled. No flash partition was written.

#### Identity from ADB

| Field | Observation |
| --- | --- |
| Model / product / device | `M15R4` / `M15R4` / `M15R4`; brand `Pastigio`, manufacturer `rockchip`. The Frameo About screen was not recorded |
| Platform / board / hardware | `rk3326` / `rk30sdk` / `rk30board` |
| Firmware | `FrameO.DP105F.v2025052119`, built 2025-05-21 |
| Fingerprint | `rockchip/rk3326_32bit/rk3326_32bit:8.1.0/OC/195458:user/release-keys` |
| Android / API / patch | 8.1.0 / 27 / 2020-11-05; `user` build, `ro.debuggable=0`, `ro.adb.secure=1` |
| ABI | `armeabi-v7a,armeabi` only (`zygote32`), `ro.config.low_ram=true` |
| Kernel | 4.4.138, built 2025-05-21 |
| Boot | `ro.boot.veritymode=enforcing` but no `/dev/block/dm-*`; `ro.boot.verifiedbootstate=unsupported`; `ro.boot.flash.locked=1`; SELinux **Permissive** |
| Display / RAM | 1920x1080 at 170 dpi / 974,220 KiB |
| Storage | Samsung eMMC `mmcblk2`, 61,063,168 sectors (GPT). Partition table identical to the [FRAME156 table](#partition-table-emmc-mmcblk2-512-byte-sectors), including `userdata` at 55,450,560 sectors |
| WebView as shipped | `com.android.webview` **61.0.3163.98** in `/system/app/webview` (`webview.apk` plus `oat/arm/webview.{odex,vdex}`, no `lib/`), vendor-signed |
| Frameo | `net.frameo.frame` v1.25.7 |
| Vendor updaters | `com.muxintu.app.mxota`, `android.rockchip.update.service` |
| USB (ADB) | `2211:0006`, vendor string `rockchip`, product `M15R4` |

#### Cables and ADB access

- Frameo **Settings → About → Beta → ADB Access** was on. Nothing enumerated through a monitor's USB
  hub, after a cable swap, or on one port directly on the Mac. It enumerated after a move to another
  port, which on this Mac was through an Apple USB-C Digital AV Multiport Adapter. The cable types
  were not recorded.
- The frame first showed `unauthorized`. **No dialog appeared** on the frame. Turning ADB Access off and
  on again with the cable connected changed the state to `device`. No key injection or Loader was
  needed, and the authorization survived four reboots.
- After the Loader reset and the first two `adb reboot`s, the Mac did not see the frame again until
  the USB cable was replugged at the frame end. After the third `adb reboot`, ADB came back by itself
  in about 48 s. The cause is unknown; replug if the frame doesn't reappear.

#### Root and binary reads

- `/system/xbin/su` (75,348 bytes, `root:shell`) gives `uid=0` with no prompt. `su -c id` and
  `su 0 id` both work. `adb shell` itself is uid 2000. `daemonsu` runs as root.
- **This `su` translates LF to CRLF**, like the [YENOCK's](yenock-zn-dp1501.md#root-and-binary-reads).
  Raw `adb exec-out su -c "dd …"` images were the wrong size and did not match on-device SHA-256.
  Piping through `gzip -c | base64` on the frame, stripping `\r` and decoding on the host gave exact
  bytes.
- The root shell's `PATH` has no standalone `awk` (`busybox awk` exists). Scripts run through `su`
  should not assume it.
- On both boots checked after the changes below, logcat showed `supolicy` crashing with SIGSEGV
  (fault address `0x1c0`) early in boot. `su` still worked afterwards and SELinux is permissive. Logcat
  was not checked before the changes, so it is unknown whether this is stock behavior.

#### Verified backup

Captured through the shipped `su` with the base64 transport above, one image per region:

- every named partition except `userdata` and `cache` (`uboot`, `trust`, `misc`, `resource`, `kernel`,
  `boot`, `recovery`, `backup`, `security`, `system`, `metadata`, `vendor`, `oem`, `frp`);
- the raw area before `uboot` (sectors 0–16383: protective MBR, primary GPT and loader) and the last
  64 sectors (backup GPT);
- `mmcblk2boot0` and `mmcblk2boot1` (4 MiB each, all zeros on this unit).

Each image's host SHA-256 matched an on-device `sha256sum` taken before and after the copy, and
each size equals the partition's sector count × 512. `metadata` was mounted read-write and did not
change during its copy. `rpmb` was not captured. **This is not a full-device backup**: `userdata` and
`cache` were skipped because the frame was new. Restoration was not tested.

| Partition | SHA-256 |
| --- | --- |
| `boot` (39,845,888 bytes) | `2e5f4fb2083c9ae7dcd040b6291849df590b7ce57c3e914d0bacb72685657c7e` |
| `kernel` (33,554,432 bytes) | `ccef9531eb7be50cee0613c2575588ea9c46fccd778169bd4999abaf4d5c6160` |
| `recovery` (73,400,320 bytes) | `33b2beec28502ea1369da42d40b763d0ebcd45c071094b8ba0e7365ba59c1dc7` |

#### Loader mode

`adb reboot loader` brought up `2207:330d` ("USB download gadget") within about 4 s, and
`rkdeveloptool ld` listed it as `Loader`. `rci` returned chip bytes `36 32 33 33` ("3326"
reversed) and `rfi` reported a Samsung flash of 61,063,168 sectors, matching Android. `rd`
(subcode 0) printed `Reset Device OK.` and Android booted; the Mac saw it again only after a USB
replug. No Loader reads or writes were made, so the stock Loader's 32 MiB read limit reported on the
[FRAME157](pastigio-frame157.md#reader-needed-for-the-full-backup) was not tested here.

`rkdeveloptool` was built from commit `304f073752fd25c854e1bcf05d8e7f925b1f4e14` with the
[research-log build line](research-log.md#loader-mode--successful) and Homebrew `libusb` 1.0.30.
Only the Command Line Tools were installed (no Xcode); the default SDK from `xcrun --show-sdk-path`
built it with Apple clang 21.

#### WebView 138 in place of the vendor WebView 61

> **Record, not a procedure.** The swap follows the [FRAME156](#webview-138-in-place-of-the-vendor-webview-106)
> and [YENOCK](yenock-zn-dp1501.md#webview-138-in-place-of-the-vendor-webview-61) records. The
> scripts are not in this repo.

| File | SHA-256 |
| --- | --- |
| Stock `webview.apk` 61.0.3163.98 | `db1f9a147730a4893670ea98fc72ee8060fdc0b0861485bec8ba63405affbc3b` (same as the YENOCK's) |
| Stock `oat/arm/webview.odex` | `200b513ba6ca18d1bfca6977ab75a6c371456355a3a4f32fd3a4fa3cdd7998f3` (differs from the YENOCK's) |
| Stock `oat/arm/webview.vdex` | `e54a6e515fbedc181644f7eed03809a04a670b14d85f9b39a62b3ffdde1c11c2` (differs from the YENOCK's) |
| New `webview.apk` 138.0.7204.63 ARM (LineageOS LFS object, source as in the FRAME156 record) | `b7268786318f404bdad53eaaec889619ff30100b935541a9e393e32efed3cf11` |
| New `lib/arm/libwebviewchromium.so` | `d217fc3847fad5cecc1f37ffa8461b95fc2bb32586f63f01285381239c11b03d` |
| New `lib/arm/libcrashpad_handler_trampoline.so` | `e16d7cd6d1669d6da68997099425501f8bb6d6f0ae3bb6c8dbbb0bc8e0f4441d` |

The 138 APK declares `com.android.webview`, minSdk 26, target 35, and carries only `armeabi-v7a`
libraries, which suits this 32-bit-only userspace. `/system` (`mmcblk2p11`, ext4 `ro`) had 833 MB free.

A root script staged in `/data/local/tmp` checked the staged files and the live stock tree against
the hashes above, refused existing staging or rollback paths and checked free space, all before
remounting. It then remounted `/system` read-write, built `/system/webview-new-138` (root:root,
0755/0644, `u:object_r:system_file:s0`), read it back, moved the stock tree to
`/system/webview-stock-61` and the new tree to `/system/app/webview`, read both back and remounted
read-only. The first run stopped at the free-space check because `awk` was missing (see above),
before the remount.

After `adb reboot`:

- `dumpsys webviewupdate` reported `com.android.webview, 138.0.7204.63` as current and the only valid
  provider, `codePath=/system/app/webview`, `primaryCpuAbi=armeabi-v7a`, RELRO 1 of 1.
- PackageManager logged `System package com.android.webview signature changed; retaining data.`
  On this firmware, a vendor-signed system WebView was replaced in `/system` by a differently signed
  one and accepted at the boot scan. The [ARZOPA P156W record](arzopa-p156w.md#the-webview-swap-does-not-work-on-this-unit-the-signatures-differ)
  expected a refusal in this case on its unit; it was not tried there.
- `cr_LibraryLoader: Successfully loaded native library`; Settings' licence page rendered in the new
  WebView. Repeated Info-level `Rejecting re-init on previously-failed class … androidx/window/extensions`
  traces come from an optional library (`required=false`) that Android 8.1 lacks.

Undo (not run): `/system/webview-stock-61` is kept on the frame. Remount read-write, move
`/system/app/webview` aside, move the stock tree back, check it against the hashes above, remount
read-only, reboot.

#### Kiosk, HOME and disabled apps

The owner used [Fully Kiosk Browser](https://www.fully-kiosk.com/) instead of this repo's
[kiosk app](../dashboard/kiosk/README.md), which was not tested on this unit.

| Item | Observation |
| --- | --- |
| APK | `Fully-Kiosk-Browser-v1.61.4.apk` from fully-kiosk.com, SHA-256 `42df2da1ef35074611159e1b07c7d16a442ba72079b652d1dd7d5168aa43dec7`; package `de.ozerov.fully`, minSdk 23; installed with `adb install` and ran as `armeabi-v7a` |
| Settings used | Start URL `file:///sdcard/dashboard/<page>.html`, Launch on Boot on, Keep Screen On on (default). Storage permission was already granted |
| HOME | Fully's HOME activity-alias `.LauncherReplacement` ships disabled, so `cmd package set-home-activity` failed with `cannot be home on user 0`. `pm enable` from the shell failed with `Shell cannot change component state`. The free version's menus had no option to enable it. `su -c 'pm enable de.ozerov.fully/.LauncherReplacement'`, then `cmd package set-home-activity de.ozerov.fully/.LauncherReplacement` worked |
| First boot as HOME | Fully showed **"Switch Kiosk Mode off?"** ("Fully will close now and restore the default home app"). **NO** kept Fully as HOME and changed its `kioskMode` setting from `false` to `true`; YES would have handed HOME back. Kiosk Mode is a Fully PLUS feature; no watermark was seen. The dialog did not return on the next boot |
| Escape to Settings | Fully's menus had no route to Android Settings. The owner accepted ADB plus `am start -a android.settings.SETTINGS` as the way back. README rule 9 is not met: there is no on-panel route to Settings, and the only way back is authorized USB ADB |

`pm disable-user --user 0` was used for `com.muxintu.app.mxota`, `android.rockchip.update.service`
and `net.frameo.frame`. Each printed `new state: disabled-user`, and each showed `enabled="3"` in
`/data/system/users/0/package-restrictions.xml` after 30 s, before any reboot. USB ADB stayed on
without Frameo (`adb_enabled=1`, `persist.sys.usb.config=adb`). After two `adb reboot`s, Fully was
HOME on the page, the screen stayed on (`fully:FullWakeLock`), and none of the three disabled
packages were running. Undo: `pm enable` each package, then set Frameo's
`net.frameo.frame/.ui.activities.AWaitForDeferredInitCompleted` as HOME again before turning off
Fully's Kiosk Mode or disabling `.LauncherReplacement`.

#### Rendering and performance

A standalone 1920x1080 dashboard page (no build step, Google Fonts, and later a direct
[Open-Meteo](https://open-meteo.com/) `fetch()`) rendered correctly in Fully on WebView 138, from
both a LAN HTTP server and `file:///sdcard/…`. Open-Meteo answers with
`Access-Control-Allow-Origin: *`, so the `null` origin of a `file://` page is accepted.

Measured with Fully in the foreground on the idle page (20 s): 26 frames drawn at 23–24 ms each
(95th percentile 85 ms; the page only redraws when its clock changes), Fully at about 9% CPU of four
cores, about 123 MB PSS, about 467 MB `MemAvailable`, SoC thermal zone 58.5 °C.

Two page bugs found during the test were in the page, not the WebView: author `display: flex`
rules overrode the `hidden` attribute (fixed with `[hidden] { display: none !important; }` on the
views), and without `<meta charset="utf-8">` WebView 138 guessed the encoding differently on two loads
of the same page served as `text/html` without a charset.

#### Security notes

See [frame security](security.md). On this unit:

- The shipped `su` gives root to any app without a prompt, and SELinux is permissive.
- The Android security patch level is 2020-11-05. WebView 138 is the newest for Android 8.1, but
  not current, and the kernel and vendor services are unchanged.
- USB ADB is on. Network ADB (port 5555) was not checked.
- The frame joined the owner's Wi-Fi after both vendor updaters were disabled. Network isolation,
  outbound connections and certificate-distrust behavior were not assessed.

#### Not tested

Cold power-on (only `adb reboot` was used), sleep and wake with USB disconnected, Wi-Fi reconnect,
network ADB, restoring any backed-up partition, the stock Loader's read limit, this repo's kiosk
app, whether a Frameo or vendor OTA would restore WebView 61, and other units or firmware.

### Seventh unit: Arch Linux, read-only (2026-11-12)

Bought as the Pastigio 15.6" FRAME156 listing. Same `DP105F` firmware family, RK3326 board and
partition map as the units above, but Android reports the model as **`M15R4`**, the firmware is
**older** than every unit above, and the shipped WebView is **61**, not 106. Nothing was written to the
frame in this session: no backup, no kiosk, no package disabled. Read-only observations only.

Host: Arch Linux (kernel 7.2), platform-tools 37.0.1 (ADB 1.0.41). The cable ran from a **USB-A port on
the computer** to the **USB-C port on the back of the frame**, with the frame's **own power supply
connected**; the owner reports the frame does not come up over USB power alone.

| Observation | Value |
| --- | --- |
| `ro.product.model` / `device` / `name` | `M15R4` / `M15R4` / `M15R4`; brand `Pastigio`, manufacturer `rockchip` |
| Firmware | `FrameO.DP105F.v2025052119`, built 2025-05-21 (units above: `v2026010414`, `v2026051219`) |
| Fingerprint | `rockchip/rk3326_32bit/rk3326_32bit:8.1.0/OC/195458:user/release-keys` |
| Android | 8.1.0, API 27, security patch 2020-11-05, kernel 4.4.138, `ro.config.low_ram=true` |
| ABI | `armeabi-v7a,armeabi` |
| Display | 1920x1080, 170 dpi |
| RAM / eMMC | 974,220 kB / 61,472,768 sectors (31,474,057,216 bytes); `boot0`, `boot1` and `rpmb` 4 MiB each |
| Partitions | p1–p15 identical to the [table above](#partition-table-emmc-mmcblk2-512-byte-sectors); `userdata` is 55,860,160 sectors |
| USB (ADB) | `2211:0012`, vendor string `rockchip`, product `M15R4`; one PTP interface plus the ADB interface (class `ff`, interface string `ADB Interface`). Earlier units: product `0006` |
| Frameo | `net.frameo.frame` v1.32.18 in `/data/app` (self-updated; the frame had been online); system copy **v1.25.7** at `/system/priv-app/DP_Frameo`. Still the HOME app |
| OTA / factory test | `com.muxintu.app.mxota` and `com.szclink.app.cldevicetest` present and enabled |
| Launcher3 | `com.android.launcher3` already disabled when received |
| WebView | `com.android.webview` **61.0.3163.98** at `/system/app/webview`, targetSdk 27 |
| Root / SELinux | `su -c id` returns uid 0 with no prompt; `getenforce` reports `Permissive`; `ro.adb.secure=1` |
| Boot / `/system` | `ro.boot.veritymode=enforcing`, `ro.boot.flash.locked=1`, no `/dev/block/dm-*`; `/system` is `mmcblk2p11` ext4 `ro`, `/vendor` is `mmcblk2p13` |
| Network ADB | Port 5555 closed; `service.adb.tcp.port` and `persist.adb.tcp.port` unset |
| Backlight | `/sys/class/backlight/backlight/brightness`, 0–255, `system:system` `0644` (a root write is needed from a non-system app). No `/sys/class/disp` |
| Motion | `pir-s18` node in the device tree, as on the first unit; not tested |

#### ADB authorization

The owner turned on **Settings -> About -> Beta -> ADB Access** and turned computer photo transfer off
before connecting the cable. The kernel log showed the frame enumerate, disconnect and enumerate again
within two seconds of plugging in. The host then showed the frame as **`offline`** (not
`unauthorized`), and still `offline` after `adb kill-server` and `adb start-server`. `adb reconnect
offline` made it leave the device list for a few seconds. On the next server start the handshake
completed: the frame answered the host's `CNXN` with an `AUTH` token, the host signed it, the frame
replied `CNXN`, and `adb devices` reported `device`. About two minutes passed from plugging in to
`device`. No key injection or loader was needed. Whether Frameo showed its ADB warning on the
frame during those two minutes was not recorded.

`/data/misc/adb/adb_keys` (711 bytes, `system:shell`, `0640`, `u:object_r:adb_keys_file:s0`) carried
the timestamp of that handshake, so the host key was stored on the frame at that moment, as on the
[fifth unit](#adb-authorization-and-persistence). Persistence across a reboot was not tested.

#### Guesses (unverified)

- The repeated `offline` may be the server losing a race against the frame's double enumeration at
  plug-in, since the third server start succeeded with nothing else changed. Restarting the host
  server, as the [fourth unit](#adb-authorization) needed, is the thing to try before toggling anything
  on the frame.
- WebView 61 on this older firmware, where the later firmware ships 106, matches the QCREA YYD-1156
  and YENOCK ZN-DP1501 rows on the same BSP. A dashboard built for WebView 106 should be checked on
  61 before relying on it, or the WebView swapped the way the [third unit](#webview-138-in-place-of-the-vendor-webview-106)
  did, after a verified backup.
- Whether the OTA app would move this unit to a 2026 firmware with WebView 106 is unknown; the owner
  intends to disable it rather than find out.

### Eighth unit: Ubuntu, Mulch 131 through `/vendor` (2026-11-15)

An older-firmware unit, sold as "DPF Frame 156" (Frameo About). Host: Ubuntu 24.04, USB-A to USB-C cable. It differs from the
units above in two ways that change the setup plan: a different product name and **WebView 61**. Like every FRAME156 unit, it has a
32-bit userspace (unlike the Arzopa P156W, which runs 64-bit apps).

| Observation | Value |
| --- | --- |
| `ro.product.model` / `ro.product.device` | `M15R4` / `M15R4` (not `FRAME156`) |
| Firmware | `FrameO.DP105F.v2025052119` |
| Fingerprint | `rockchip/rk3326_32bit/rk3326_32bit:8.1.0/OC/195458:user/release-keys`, security patch 2020-11-05 |
| ABI | `armeabi-v7a,armeabi`, `ro.zygote=zygote32`; every app is `primaryCpuAbi=armeabi-v7a` |
| Partition table | Same sizes and order as the table above (p1 `uboot` to p16 `userdata`) |
| Display | 1920x1080, 170 dpi |
| Frameo | `net.frameo.frame` **v1.32.18 (80340)** in `/data/app`, an update over the system copy |
| WebView as shipped | `com.android.webview` **61.0.3163.98**, `/system/app/webview/webview.apk`, signed with certificate `cf2ab381...8525` (index 3 in `packages.xml`, the same ODM key as the [Arzopa P156W](arzopa-p156w.md)) |
| Vendor apps | `com.muxintu.app.mxota`, `android.rockchip.update.service`, `com.szclink.app.cldevicetest`, `com.android.soundrecorder` |
| `/system`, `/vendor` | ext4 `ro`, no `dm-*` devices, although `ro.boot.veritymode=enforcing`; SELinux permissive |
| Root | Shipped `su -c` returned uid 0 without a prompt |

#### USB and ADB

ADB enumerated as `2211:0006`, product name `rockchip M15R4`. `adb devices` printed
`no permissions (missing udev rules?)` until a udev rule for vendor `2211` was added:
`SUBSYSTEM=="usb", ATTR{idVendor}=="2211", MODE="0660", GROUP="plugdev"` in `/etc/udev/rules.d/51-android.rules`, then
`udevadm control --reload-rules && udevadm trigger`. After that the usual Beta Program -> ADB Access toggle
with the cable in gave `device`. **After every `adb reboot` the host stopped seeing the frame until the USB cable was unplugged and
re-plugged at the frame end** (twice, same as the second unit).

#### Backup (verified before any write)

Sectors 0-5,612,544 (everything before `userdata`) through the shipped `su`, compressed on the frame and moved as base64 (the
`exec-out` LF trap above applies; a 1 MiB probe matched the device hash first): 2,873,622,528 bytes raw, 524 MB gzipped, `gzip -t` clean, and the
SHA-256 of the decompressed stream equals a fresh read of the same range on the
frame (the hash itself is kept private with the dump). `userdata`, `cache`, `rpmb` and `mmcblk2boot0/1` were not captured, and restore (Rockchip loader mode) was not tried.
Note for anyone scripting this: a backgrounded `adb exec-out` pipeline keeps running after the shell wrapper reports completion, so wait for the
pipeline itself (a status file written after it) before hashing, or you will compare a partial file.

#### Changes made

| Change | How | Undo |
| --- | --- | --- |
| Vendor updaters off | `pm disable-user --user 0` for `com.muxintu.app.mxota` and `android.rockchip.update.service` | `pm enable <pkg>` |
| Frameo off | `pm disable-user --user 0 net.frameo.frame`, run twice, then waited until `package-restrictions.xml` showed `enabled="3"` before rebooting | `pm enable net.frameo.frame` |
| Sound recorder off | `pm disable-user --user 0 com.android.soundrecorder` (same wait) | `pm enable com.android.soundrecorder` |
| Kiosk | `dashboard/kiosk` built from this repo, `adb install -r`, `WRITE_SECURE_SETTINGS` granted; `am start ... --ez home true`, then `cmd package set-home-activity com.wesbos.homehq/.Home` | Pick another Home app, `--ez home false` |
| WebView 131 | see below | see below |
| Dashboard | Built with `vite build` and bundled with `KIOSK_SITE=dist`; saved URL `http://127.0.0.1:8765/` | `scripts/set-kiosk-url.sh <url>` |

After a reboot: the kiosk is HOME, Frameo, both updaters and the sound recorder stay disabled and not running, the navigation service stays enabled, and Mulch is still the WebView.
`com.android.systemui` showed `enabled="2"` (caller `shell:0`) in `package-restrictions.xml` partway through the session while its process kept running; none of the
commands in this record touched it, and its origin was not established.

#### WebView 61 to Mulch 131 (a 32-bit variant of the Arzopa overlay route)

> **Record, not a procedure.** The `/vendor` write is one owner's result; the doc records an on-frame hash check of the overlay but no readback after the copy.

The `/system` tree swap was not tried on this unit. Its WebView carries the same ODM certificate as the Arzopa P156W's, where installing the prebuilt as an update was refused; on the [sixth unit](#sixth-unit-macos-backup-loader-and-webview-138-2026-11-10) (same firmware) the LineageOS 138 prebuilt copied into `/system` was accepted at the boot scan. The vendor-overlay
route from [arzopa-p156w.md](arzopa-p156w.md#a-modern-webview-without-touching-system-verified) works here, with one change: that unit was 64-bit, this one is **32-bit only**, so the
`arm` build of Mulch is needed, not `arm64`.

| File | Source | SHA-256 |
| --- | --- | --- |
| `treble-overlay-mulch-webview.apk` | [A4Alpha/mulch-webview-overlay](https://github.com/A4Alpha/mulch-webview-overlay) release `v0.1` | `372fe0ba0cb7b98e98346978b12d3aeb073ea4cde0fd033c9b1a775187394a5a` (matches the Arzopa pin) |
| Mulch `webview.apk`, `armeabi-v7a`, `us.spotco.mulch_wv` 131.0.6778.200, minSdk 26 | GitLab `divested-mobile/mulch`, `prebuilt/arm/webview.apk` at commit `c4c5b73fa5a5` (2024-12-18) | `1f5147f86c5733bc98edd42df695294b6940061e61b65a4a71f6628b6aee5750` |

Checked on the host first: the certificate declared in the overlay's `config_webview_packages.xml` (SHA-256 `260e0a49...18d2`) is the same certificate that signs the Mulch APK. Then, with the verified backup in place and the owner's approval:
`adb install -r` the Mulch APK (it installed as `armeabi-v7a`), hash-checked the overlay on the frame, remounted `/vendor` read-write, copied it to `/vendor/overlay/`
(`root:root`, 0644, label `vendor_overlay_file`), `sync`, remounted read-only, rebooted. `cmd overlay list` showed `[x] com.alpha.mulch.webview.overlay`, `dumpsys webviewupdate` listed both providers as valid, and
`cmd webviewupdate set-webview-implementation us.spotco.mulch_wv` printed `Success`. The kiosk process has to be restarted to pick the new provider. The choice survived a reboot.
Undo is the same as the Arzopa record. Mulch is no longer updated, the overlay is a third-party binary, and this is one unit.

#### Black side bars

The first screenshots on the hosted demo showed the fixed 1280-wide stage (96 px side bars, and a shrunken, half-empty page while WebView 61 was active). The hosted demo predates
[#226](https://github.com/wesbos/photo-frame-dashboard/pull/226). Building the dashboard from this checkout and bundling it in the kiosk APK
(`KIOSK_SITE`, see the [kiosk README](../dashboard/kiosk/README.md#a-page-bundled-in-the-apk-no-server)) filled the 1920x1080 panel edge to edge.

Verified on the panel: the two-finger hold opens the kiosk controls and reaches Android Settings.

Not tested on this unit: loader mode, firmware restore, motion/PIR, the vendor boot animation, the factory test app `com.szclink.app.cldevicetest`, whether the system `Frameo` copy returns after a factory reset.

## Ninth unit: firmware v2026051219, Frameo v1.32.18, Windows host (2026-11-22)

A `FRAME156` on firmware `v2026051219`, the first Windows-hosted report for this model. Host:
Windows 11, Git Bash, platform-tools 37.0.3 (ADB 1.0.41). USB-A to USB-C data cable.

| Observation | Value |
| --- | --- |
| `ro.product.model` / `ro.product.device` | `FRAME156` / `FRAME156` |
| Firmware | `FrameO.DP105F.v2026051219` |
| Fingerprint | `rockchip/rk3326_32bit/rk3326_32bit:8.1.0/OC/192521:user/release-keys` |
| Android / API / patch | 8.1.0 / 27 / 2020-11-05 |
| ABI | `armeabi-v7a`, `ro.config.low_ram=true` |
| Display | 1920x1080, 170 dpi |
| eMMC | 61,071,360 sectors (31,268,536,320 bytes) |
| WebView | `com.android.webview` 106.0.5249.126 |
| Frameo | `net.frameo.frame` v1.32.18 |
| Root / SELinux | Shipped `su -c id` returns uid 0 without a prompt; `Permissive` |
| ADB settings | `persist.sys.usb.config=adb`, `adb_enabled=1` |

### ADB authorization on Windows

With Frameo **Settings → About → Beta Program → ADB Access** on and computer photo transfer off,
the host showed `unauthorized`. No dialog appeared on the frame (SystemUI likely disabled).
**Toggling ADB Access off and on with the USB cable connected** changed the state from
`unauthorized` to `device`. No key injection, loader or ADB server restart was needed. The
authorization survived a reboot.

### Backup on Windows (verified)

Each partition was backed up individually through the partition device node (`mmcblk2pN`),
using `dd | base64` on the frame and `tr -d '\r' | base64 -d` on the host.

**The `adb exec-out` CRLF issue is confirmed on Windows:** a raw `dd` stream through
`exec-out su -c` was 98 bytes too long for a 512 KiB partition. The base64 workaround
produced exact bytes.

All 16 regions (pre-partition area through `frp`) passed exact byte count, SHA-256 and no
0xCC filler. Five independent re-reads (`boot`, `recovery`, `uboot`, `kernel`, `vendor`) all
matched. `userdata`, `cache`, `mmcblk2boot0/1` and `rpmb` were not captured.

| Partition | SHA-256 |
| --- | --- |
| `boot` (39,845,888 bytes) | `84524aa9c4c8fd519037062a629f3c3ba286c6929d5afe18c15535f319ca939a` |
| `kernel` (33,554,432 bytes) | `2481302c300c6e871a008f13a7003601ed50cbee2a5be466aef23da0868edbd7` |
| `recovery` (73,400,320 bytes) | `bfaaebf520f085f549c7724e810fcd4dc884b595379731abb8b141a8f3aed565` |

### Kiosk setup

The kiosk (`dashboard/kiosk`, `com.wesbos.homehq` v1.2) was installed and set as HOME using the
`--ez home true` then `cmd package set-home-activity` order. `pm disable-user --user 0` was run for
`com.muxintu.app.mxota`, `net.frameo.frame` and `com.szclink.app.cldevicetest`. After a reboot the
kiosk was HOME (`mResumedActivity: com.wesbos.homehq/.Home`), `sys.boot_completed=1`, and all three
packages stayed disabled. No `/system` or flash partition was written.

### mDNS `.local` does not resolve

Same as the [fourth unit](#fourth-unit-firmware-v2026051219-tested-on-macos-2026-10-18):
`ping homeassistant.local` returns `unknown host`. Use an IP address or a DNS name that the network
resolves. This is an Android 8.1 limitation, not a frame-specific issue.

### Not tested

Loader mode, firmware restore, motion/PIR, WebView upgrade, network ADB persistence, the vendor
boot animation, and whether Frameo returns after a factory reset.
