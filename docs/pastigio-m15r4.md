# Pastigio M15R4 15.6-inch Frameo frame (RK3326)

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

## Identity from ADB

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
| Storage | Samsung eMMC `mmcblk2`, 61,063,168 sectors (GPT). Partition table identical to the [FRAME156 table](pastigio-frame156.md#partition-table-emmc-mmcblk2-512-byte-sectors), including `userdata` at 55,450,560 sectors |
| WebView as shipped | `com.android.webview` **61.0.3163.98** in `/system/app/webview` (`webview.apk` plus `oat/arm/webview.{odex,vdex}`, no `lib/`), vendor-signed |
| Frameo | `net.frameo.frame` v1.25.7 |
| Vendor updaters | `com.muxintu.app.mxota`, `android.rockchip.update.service` |
| USB (ADB) | `2211:0006`, vendor string `rockchip`, product `M15R4` |

## Cables and ADB access

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

## Root and binary reads

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

## Verified backup

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

## Loader mode

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

## WebView 138 in place of the vendor WebView 61

> **Record, not a procedure.** The swap follows the [FRAME156](pastigio-frame156.md#webview-138-in-place-of-the-vendor-webview-106)
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

## Kiosk, HOME and disabled apps

The owner used [Fully Kiosk Browser](https://www.fully-kiosk.com/) instead of this repo's
[kiosk app](../dashboard/kiosk/README.md), which was not tested on this unit.

| Item | Observation |
| --- | --- |
| APK | `Fully-Kiosk-Browser-v1.61.4.apk` from fully-kiosk.com, SHA-256 `42df2da1ef35074611159e1b07c7d16a442ba72079b652d1dd7d5168aa43dec7`; package `de.ozerov.fully`, minSdk 23; installed with `adb install` and ran as `armeabi-v7a` |
| Settings used | Start URL `file:///sdcard/dashboard/<page>.html`, Launch on Boot on, Keep Screen On on (default). Storage permission was already granted |
| HOME | Fully's HOME activity-alias `.LauncherReplacement` ships disabled, so `cmd package set-home-activity` failed with `cannot be home on user 0`. `pm enable` from the shell failed with `Shell cannot change component state`. The free version's menus had no option to enable it. `su -c 'pm enable de.ozerov.fully/.LauncherReplacement'`, then `cmd package set-home-activity de.ozerov.fully/.LauncherReplacement` worked |
| First boot as HOME | Fully showed **"Switch Kiosk Mode off?"** ("Fully will close now and restore the default home app"). **NO** kept Fully as HOME and changed its `kioskMode` setting from `false` to `true`; YES would have handed HOME back. Kiosk Mode is a Fully PLUS feature; no watermark was seen. The dialog did not return on the next boot |
| Escape to Settings | Fully's menus had no route to Android Settings. The owner accepted ADB plus `am start -a android.settings.SETTINGS` as the way back |

`pm disable-user --user 0` was used for `com.muxintu.app.mxota`, `android.rockchip.update.service`
and `net.frameo.frame`. Each printed `new state: disabled-user`, and each showed `enabled="3"` in
`/data/system/users/0/package-restrictions.xml` after 30 s, before any reboot. USB ADB stayed on
without Frameo (`adb_enabled=1`, `persist.sys.usb.config=adb`). After two `adb reboot`s, Fully was
HOME on the page, the screen stayed on (`fully:FullWakeLock`), and none of the three disabled
packages were running. Undo: `pm enable` each package, then set Frameo's
`net.frameo.frame/.ui.activities.AWaitForDeferredInitCompleted` as HOME again before turning off
Fully's Kiosk Mode or disabling `.LauncherReplacement`.

## Rendering and performance

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

## Security notes

See [frame security](security.md). On this unit:

- The shipped `su` gives root to any app without a prompt, and SELinux is permissive.
- The Android security patch level is 2020-11-05. WebView 138 is the newest for Android 8.1, but
  not current, and the kernel and vendor services are unchanged.
- USB ADB is on. Network ADB (port 5555) was not checked.
- The frame joined the owner's Wi-Fi after both vendor updaters were disabled. Network isolation,
  outbound connections and certificate-distrust behavior were not assessed.

## Not tested

Cold power-on (only `adb reboot` was used), sleep and wake with USB disconnected, Wi-Fi reconnect,
network ADB, restoring any backed-up partition, the stock Loader's read limit, this repo's kiosk
app, whether a Frameo or vendor OTA would restore WebView 61, and other units or firmware.
