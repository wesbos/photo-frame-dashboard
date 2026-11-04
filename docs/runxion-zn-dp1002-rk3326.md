# Runxion 10.1" Frameo frame: SSA RK3326 board (`SSA_Frame_20250928`, Android 8.1, WebView 61)

Record of one unit, set up on 2026-10-23 from a Mac over USB. It records what was done on this
unit; it is not a flashing guide. Observations are kept separate from guesses. Unique identifiers
(serial, MAC, Wi-Fi, URLs, account IDs) are left out.

**Short version:** sold as the [Runxion 10.1" Frameo, 32 GB](https://amzn.to/4B38DQ0).
The [RK3126 Runxion](runxion-zn-dp1002-rk3126.md) shows that this listing ships two boards. This
unit is the **RK3326 / Android 8.1** one, and it confirms the guess in the
[Akimart page](akimart-zn-dp1002.md#guesses-not-confirmed): it is the same SSA RK3326 board, with
the same logical NAND partition map. Two things differ from the Akimart units. The firmware is older
(`SSA_Frame_20250928`), and the stock WebView is **61**, not 106. So this unit needed a WebView swap
in `/system`, like the [YENOCK ZN-DP1501](yenock-zn-dp1501.md)
(WebView 61, same stock `webview.apk`) and the
[FRAME156](pastigio-frame156.md#webview-138-in-place-of-the-vendor-webview-106) (#139).

End result: Frameo and both vendor updaters disabled, WebView 106 in `/system` with the stock tree
kept for undo, Rootless Pixel Launcher as a fallback, and the repo's
[Home HQ kiosk](../dashboard/kiosk/README.md) as HOME with its navigation service. The frame boots
straight into the kiosk. Frameo's boot splash still shows, because it is in the firmware.

![The frame on a shelf running a Cotidiano page made with demo content (sunrise and sunset line blurred)](images/runxion-zn-dp1002-rk3326-dashboard.jpg)

## Identity

| Field | Value seen on this unit |
| --- | --- |
| Sold as | Runxion 10.1" Frameo |
| Model / brand | `ro.product.model` `Frame`, brand `SSA` (as on the Akimart unit; not `ZN-DP1002`) |
| Platform | Rockchip RK3326, 4 cores, ABI `armeabi-v7a` |
| Android / API | 8.1.0 / 27, security patch 2020-06-05 |
| Firmware | `SSA_Frame_20250928` |
| Fingerprint | `rockchip/rk3326_go/rk3326_go:8.1.0/OC/101841:user/release-keys` |
| RAM / display | 1 GB / 1280×800 touch, 160 dpi (`devicePixelRatio` 1), panel tracked 4 fingers in testing (WebView reports `maxTouchPoints` 2) |
| Storage | logical NAND `rknand0`, same partitions p1–p15 as the [Akimart map](akimart-zn-dp1002.md#logical-nand-partition-map) |
| Root | shipped `su`, syntax `su 0 <cmd>`. `adb root` works |
| WebView as shipped | `com.android.webview` **61.0.3163.98** in `/system/app/webview` |
| Vendor updaters | `com.adups.fota`, `android.rockchip.update.service` |
| Ports | one USB-C (power and data share it) and a microSD slot |
| Boot partition (p6, 32 MiB) SHA-256 | `f484bce971c58a6f38124b0f991dc7a13e56043858b814712e5b7fef2ddb020a` |

Compared with the closest documented units:

| | This unit | [Akimart ZN-DP1002](akimart-zn-dp1002.md) | [YENOCK ZN-DP1501](yenock-zn-dp1501.md) |
| --- | --- | --- | --- |
| Panel | 10.1", 1280×800 | 10.1", 1280×800 | 15.6", 1920×1080 |
| Firmware | `SSA_Frame_20250928` | `SSA_Frame_20260420` | `SSA_Frame_20250814` |
| Fingerprint build | `OC/101841` | `OC/085013` | `OC/064459` |
| Boot partition SHA-256 | `f484bce9…020a` | `4ed777af…891b` | `8c873066…2e68` |
| Stock WebView | 61.0.3163.98 | 106.0.5249.126 | 61.0.3163.98 |
| Stock `webview.apk` SHA-256 | `db1f9a14…bc3b` | n/a | `db1f9a14…bc3b` (same file) |

## Cables and ADB access

- **USB-C to USB-C from a Mac gave no power and no data.** A USB-A to USB-C data cable (through an
  adapter on the Mac) worked. This matches the Akimart and Dxmart units.
- Frameo Settings → About → Beta Program → **ADB access**. At first `adb devices` showed
  `unauthorized` and no prompt appeared. Toggling ADB access off and on, with the cable plugged in,
  brought up the authorization prompt. This matches the existing Runxion row.
- `adb root` restarts `adbd`, and the frame asked for authorization again. Accept it on the panel.
- Network ADB (`adb tcpip 5555`) needed its own approval on the panel as well.

## Backup (before any write)

A logical firmware backup over ADB, following the
[Akimart method](akimart-zn-dp1002.md#verified-firmware-backup), with the shipped `su` (not
`adb root`): the first 8 MiB of `/dev/block/rknand0`, then each partition node p1–p15 with
`adb exec-out "su 0 dd if=<partition> bs=1M count=N"`, compressed, with a SHA-256 manifest. About
564 MB compressed. It stays private.

Every region passed all the README rule 2 checks:

- exact byte count, compared with the size in sysfs;
- host SHA-256 equal to a fresh on-device re-read (`su 0 dd … | sha256sum`);
- no 4 KiB block that is all `0xCC`;
- `gzip -t` readback.

Because the host and on-device hashes matched, this firmware's `su` does not translate LF to CRLF
in binary output, unlike the [YENOCK](yenock-zn-dp1501.md) and [21" SSA](ssa-frame-21inch-rk3326.md) units.

Pitfall: **`frp` came out as 0 bytes.** It is only 512 KiB (1,024 sectors), so `count=size/1M`
rounded down to `count=0`. The byte-count check flagged it as a mismatch. Redone with `bs=4096
count=128`, it read 524,288 bytes and passed. Check every region's byte count, not only its hash.

Restoration is untested.

## Setup performed (2026-10-23)

One change at a time, each with its undo written down first. The way back to Settings was proved by
hand before Frameo was disabled (README rule 9).

| Change | Command | Undo |
| --- | --- | --- |
| Disable Adups FOTA | `pm disable-user --user 0 com.adups.fota` | `pm default-state --user 0 com.adups.fota` |
| Disable Rockchip updater | `pm disable-user --user 0 android.rockchip.update.service` | `pm default-state --user 0 android.rockchip.update.service` |
| WebView 61 → 106 in `/system` | See [below](#webview-106-in-place-of-the-stock-webview-61) | See below |
| Install fallback launcher | `adb install` Rootless Pixel Launcher 3.9.1 (F-Droid, SHA-256 `7fa44d56…404a`) | `adb uninstall amirz.rootless.nexuslauncher` (while it is not HOME) |
| Install Home HQ | `adb install` the kiosk built from `dashboard/kiosk` | `adb uninstall com.wesbos.homehq` (set another HOME first) |
| Home HQ as HOME | `am start -n com.wesbos.homehq/.MainActivity --ez home true`<br>`cmd package set-home-activity --user 0 com.wesbos.homehq/.Home` | `cmd package set-home-activity --user 0 amirz.rootless.nexuslauncher/com.google.android.apps.nexuslauncher.NexusLauncherActivity` |
| Navigation service | `pm grant com.wesbos.homehq android.permission.WRITE_SECURE_SETTINGS`<br>`settings put secure enabled_accessibility_services com.wesbos.homehq/com.wesbos.homehq.NavigationService`<br>`settings put secure accessibility_enabled 1` | `pm revoke` the same permission first, then `settings delete secure enabled_accessibility_services` and `settings put secure accessibility_enabled 0` |
| Frame Home button | Installed, then **removed again** (below) | `adb uninstall com.photoframe.homebutton` |
| Disable Frameo | `pm disable-user --user 0 net.frameo.frame`, then wait (below) | `pm default-state --user 0 net.frameo.frame` |

Notes:

- **Wait before rebooting after `pm disable-user`.** Same as the
  [Dxmart](akimart-zn-dp1002.md#second-unit-dxmart-zn-dp1002-2026-10-15-macos) and
  [AMABOO](amaboo-gbzk-y1000.md#wait-before-rebooting-after-pm-disable-user) units: wait about 30 s,
  check that `/data/system/users/0/package-restrictions.xml` shows `enabled="3"` for the package,
  run `sync`, then reboot. Done that way, all three disables survived the reboot.
- **Way back:** the kiosk's two-finger hold (1.5 s, both fingers still) opens its menu with Android
  settings, Wi-Fi and reload. Settings → Apps and back to the kiosk was checked by hand on the panel
  before Frameo was disabled.
- **Frame Home button removed:** its overlay sits in the bottom-right corner and swallowed taps meant
  for that corner of the page. The kiosk's own navigation service covers the same need.

## WebView 106 in place of the stock WebView 61

WebView 61 is too old for most modern pages. The repo's dashboard targets 106. The stock tree here
matched the [YENOCK record](yenock-zn-dp1501.md#webview-138-in-place-of-the-vendor-webview-61), so the same `/system` swap applied. It followed the
[FRAME156 record](pastigio-frame156.md#webview-138-in-place-of-the-vendor-webview-106) and the
[PF1007L procedure](allwinner-a33-pf1007l.md#6-upgrade-webview-before-using-the-kiosk), with 106
instead of 138. **Do not use `adb install -r`:** the stock WebView is vendor-signed, so an update
install fails (`INSTALL_FAILED_UPDATE_INCOMPATIBLE` on the FRAME156).

| File | Source | SHA-256 |
| --- | --- | --- |
| Stock `/system/app/webview/webview.apk` (61.0.3163.98) | as shipped | `db1f9a147730a4893670ea98fc72ee8060fdc0b0861485bec8ba63405affbc3b` |
| New `webview.apk` 106.0.5249.126 ARM | [LineageOS at `4b0ae494a7dd`](https://raw.githubusercontent.com/LineageOS/android_external_chromium-webview_prebuilt_arm/4b0ae494a7dd/webview.apk) (same pin as the PF1007L guide) | `e2edc1f89ec1608b169da9e7ffc037190b70c7825f0be29694f4cae719980580` |
| `lib/arm/libwebviewchromium.so` | extracted from that APK (`lib/armeabi-v7a/`) | `251037128d1125b1ad7a9f8286f5258814dc403cfe5106be3ca05e254260d49f` |
| `lib/arm/libchromium_android_linker.so` | 〃 | `94211d3b11689179f57993f9749142c9a0b77bb0677f0115ac0573b23defff82` |
| `lib/arm/libcrashpad_handler_trampoline.so` | 〃 | `39293822e62a7036df00e051084142df992d2e33959d565534eaf8338b576b55` |

The stock tree's other two files, as recorded before the swap:

| Stock file | SHA-256 |
| --- | --- |
| `oat/arm/webview.vdex` | `b124df0a720926e48bbfc116fd96ce62aed9b8ab7ab828ad0c2b784f58643da0` (same as the YENOCK unit) |
| `oat/arm/webview.odex` | `73b1246eb3aa466ab0c58756e274e472fc2a1771e993c732feaf5ed1cc26a1b0` (differs from the YENOCK's `352fb0ef…4a5c`) |

The `.odex` is compiled code, so it can differ between builds even when the APK is the same. Compare
the `webview.apk` hash to tell whether your stock WebView is this build.

Steps, as root on the frame (after the backup, with the updaters already disabled):

1. Recorded the stock tree's hashes and pulled a copy to the Mac. `/system` is plain ext4 on
   `rknand0p11`, not a `dm-*` device, with about 1.1 GB free.
2. Pushed the APK and the three pre-extracted libraries to a staging folder and checked their hashes
   on the frame. 106 stores its libraries compressed, and Android does not extract native libraries
   for a `/system` app, so they go in `lib/arm/` next to the APK.
3. `mount -o remount,rw /system`, built `/system/webview-new-106` (root:root, 0755 directories,
   0644 files, `chcon -R u:object_r:system_file:s0`) and checked the hashes.
4. Moved the whole stock tree (APK plus `oat/arm/webview.{odex,vdex}`) to `/system/webview-stock-61`,
   outside any scanned app directory, so its stale oat files go with it. Moved the new tree to
   `/system/app/webview`, checked the hashes again, `sync`, remounted read-only.
5. Rebooted. `dumpsys webviewupdate` showed `com.android.webview` 106.0.5249.126 as current,
   RELRO preparation finished 1/1, and logcat showed no WebView library load errors.
   Repeated `ffmExtractor … libffmpeg_utils.so` errors are the stock media server and are unrelated
   (also seen on the FRAME156).

Undo (written down, not run): remount `/system` read-write, move `/system/app/webview` aside, move
`/system/webview-stock-61` back to `/system/app/webview`, check its hashes against the recorded
stock hashes, `sync`, remount read-only and reboot.

## Hosting note: githack shows an interstitial to WebView 80+

The first dashboard was a secret GitHub gist served through `gist.githack.com`. On the stock
WebView 61 it loaded directly. After the swap to 106, githack showed its "One more step" page
instead. It shows that page for top-level navigations that send `Sec-Fetch-Dest: document`
(Chrome and WebView 80 and newer). The bypass cookie it sets lasts 24 hours (`Max-Age=86400`), so a
kiosk would hit the page again every day. XHR and iframe loads are not affected. The kiosk only
saves `http`/`https` URLs, so a `data:` or `file:` shell page is not an option either.

Any static host without an interstitial works, for example the repo's Cloudflare Workers setup.

## Measured on this unit (WebView 106)

Measured with a small set of browser test pages loaded in the kiosk:

- **Frame rate:** `requestAnimationFrame` idles at about 43–47 fps, not 60.
- **Animations:** CSS `@keyframes` held about 47 fps up to 20 animated elements (44 at 50).
  Transforms driven from JavaScript slowed down from 5 elements. Animated `box-shadow` and
  `filter: blur()` were very slow.
- **Page transitions:** a 1.2 s iframe crossfade ran at about 46 fps (about 95 ms to render) with a
  light page. A heavy page dropped to 12 fps at worst.
- **Features:** 129 of 136 checks supported. Missing: `dvh` units, `color-mix()`, `oklch()`/`lab()`,
  CSS nesting, `Array.prototype.findLast`/`toSorted`, `Notification`, `speechSynthesis`.
- **Touch:** the panel tracked up to four fingers in a touch test, but the WebView reports `maxTouchPoints` 2. Chromium derives that number from the multitouch level Android declares, not from the panel itself, so don't use it to rule out gestures. 48 px tap targets were unpleasant to hit; about 100 px felt right.
  Pinch and rotate work, but are awkward one-handed on a frame standing on a shelf.
- **Thin rotated lines:** at DPR 1, a thin CSS line that is rotated shows stair steps. Animated
  layers are not edge-antialiased. Draw thin angled lines with SVG instead.

## Other observations

- **Wi-Fi drops while the screen sleeps.** Same as the
  [Dxmart unit](akimart-zn-dp1002.md#second-unit-dxmart-zn-dp1002-2026-10-15-macos): keep the screen
  on at low brightness if the page must stay current.
- The Frameo boot splash still shows on every boot, since it is part of the firmware.

## What it runs

The frame runs Cotidiano; see [Community Builds](community-builds.md).

## Second unit (2026-10-23, macOS)

A second Runxion from the same listing, set up the same day from a Mac over USB. It matched the
first unit exactly: firmware `SSA_Frame_20250928`, the same fingerprint (`OC/101841`), 1280×800 at
160 dpi, the same boot partition SHA-256 (`f484bce9…020a`) and the same stock WebView tree,
including the `webview.odex` hash (`73b1246e…a1b0`). Frameo was `v1.32.12_-_OTA_test`. The setup
above applied unchanged: updaters disabled, the same WebView 106 swap, Rootless Pixel Launcher,
Home HQ as HOME with its navigation service, then Frameo disabled, each disable checked for
`enabled="3"` before the reboot. All of it survived the reboot.

### No `iotv` on this unit

- `/system/bin/iotv` and `/system/bin/run_iotv.sh` do not exist, and no init `.rc` file mentions
  `iotv`.
- `/proc/net/tcp` and `tcp6`, read while Frameo was still running, showed established connections
  only from Frameo and the Gboard keyboard. No connection belonged to uid 0.

One unit, one check. It does not prove that every RK3326 build is free of it.

### Backup: a USB stream that stopped

The backup used the same per-partition method, with the shipped `su` and no base64 (no CR was
added, as on the first unit). The 1.9 GB `system` stream stopped after about 380 MB compressed and
made no progress for 8 minutes, with `dd` on the frame blocked on its pipe. The frame stayed on ADB.
Re-reading `system`, `uboot` and `vendor` in 64 MiB pieces (`dd bs=1M skip=… count=64`), each piece
checked against an on-device SHA-256 and retried on a timeout, worked without a retry. The whole
partition was then checked again against a fresh on-device read. 15 regions, 579 MB compressed,
every one verified. A whole-partition read with no `count` also avoided the `frp` pitfall above.

### Other observations

- **The frame restarted once on its own** within a few minutes of ADB being authorized (uptime
  showed it). The cause was not established.
- **SystemUI was found disabled after the setup**: `package-restrictions.xml` had `enabled="2"`
  with `enabledCaller="shell:0"` for `com.android.systemui`. It was not in `pm list packages -d` at
  the first check, and nothing in this setup disables SystemUI (only `pm disable-user`, which gives
  `enabled="3"`). No file in `/system/bin`, `/system/etc`, `/vendor` or the init `.rc` files mentions
  it. Cause not established. Home HQ works without it; its navigation service covers Back and Home.
- The [bundled page](../dashboard/kiosk/README.md#a-page-bundled-in-the-apk-no-server)
  (`KIOSK_SITE`) worked as the dashboard at `http://127.0.0.1:8765/`.

## Guesses, not confirmed

- The USB-C port probably lacks the CC resistors a USB-C host needs before it supplies power. That
  would explain why a USB-C to USB-C cable does nothing (the same guess as on the Akimart page).
- The 2025 SSA RK3326 builds (`20250814`, `20250928`) probably all ship WebView 61, and the 2026
  build ships 106. Only one unit of each 2025 build has been reported so far.

## Not yet checked

- Whether a vendor OTA would restore WebView 61 (both updaters are disabled).
- Restoring from the backup.
- `/system/bin/iotv` (the hidden root agent on the [RK3126 Runxion](runxion-zn-dp1002-rk3126.md#hidden-root-agent-iotv))
  on the first unit. It was absent on the [second unit](#no-iotv-on-this-unit). Keep the frame on an
  isolated network either way: Android 8.1, a 2020 security patch and shipped root.
