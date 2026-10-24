# Sandstrom SDPFHD10W25 10.1" (Frameo, Currys own brand)

One unit, bought new from Currys (UK). Host: Windows 11, USB, platform-tools 37.0.1. The frame had
**not** been on Wi-Fi at any point in this record.

Status: root ADB over USB with no flash writes. Partitions backed up over ADB; updaters and Frameo
disabled. All changes are in `/data` and can be undone. **WebView can't render on this firmware**
(any version; see below), so the Home Assistant app hangs. The working result is **Firefox showing
the Home Assistant dashboard full screen at boot**, started by a small Home app
([`scripts/firefox-home`](../scripts/firefox-home/README.md)).

## Summary

| | |
| --- | --- |
| SoC | Allwinner A133 (`ro.sys.cputype` `QuadCore-A133`, `sun50iw10p1`, platform `ceres`) |
| Android | 12 (SDK 31, `SQ1A.220105.002`), security patch 2022-08-05, 32-bit userspace (`zygote32`, `armeabi-v7a`) |
| Fingerprint | `Frameo1/ceres_aw/ceres-aw:12/SQ1A.220105.002/20250903.194541:user/test-keys` |
| Build | `SDPFHD10W25_V2.00`; description says `ceres_aw-eng`, fingerprint says `user` |
| RAM / storage | ~1 GB (`MemTotal` 978720 kB), `ro.config.low_ram=true`; 32 GB eMMC, `/data` 26 GB |
| Display | `ro.sf.lcd_density` 160; panel mounted rotated (`ro.vendor.sf.rotation` 270, touch rotation 90) |
| Frameo | `net.frameo.frame` v1.27.5 (versionCode 54800), priv-app |
| WebView | `com.android.webview` 91.0.4472.114 stock, AOSP test-key signed. 156 installs as an update, but **no renderer starts on this firmware** ([below](#webview-cant-render-anything-on-this-firmware)) |
| USB | `1f3a:1001`, name `SDPFHD10W25`, ADB interface `FF/42/01`, WinUSB bound automatically on Windows |
| ADB | On out of the box (`persist.sys.usb.config=adb`), key check on (`ro.adb.secure=1`) |
| Root | `adb shell` is `uid=0` (`ro.secure=0`, `ro.debuggable=1`), context `u:r:su:s0`, SELinux permissive |
| Partitions | A/B (`ro.build.ab_update=true`, slot `_a`), dynamic `super`, eMMC `mmcblk0` |

This is the first A133 frame in the repo on Android 12; the other A133 units in
[devices.md](devices.md) run Android 10. Don't reuse their partition offsets or scripts.

## Observations

### Getting ADB (Windows)

1. Out of the box, before Frameo setup: the ADB interface was already present and `adb devices`
   showed `unauthorized`.
2. Frameo first-run setup completed with Wi-Fi skipped. Frameo → ADB access turned on: still
   `unauthorized`, no prompt. Unplug/replug USB and `adb kill-server`: no change.
3. Toggling Frameo's ADB access off and on again with USB plugged in: the device dropped off,
   came back, and turned `device` about 10 s later (whether a prompt appeared: not yet recorded). No
   `adb_keys` edits or flash writes were needed.

SystemUI was present and enabled at this point (`/system/system_ext/priv-app/SystemUI/SystemUI.apk`).
After the next reboot it was disabled (`enabled="2"`) with Frameo still enabled, as on the
[AMABOO](amaboo-gbzk-y1000.md). Re-enabling it and rebooting starts the SystemUI process, but this
build never creates a status bar or navigation bar window. That probably explains why no ADB prompt appeared
earlier.

`/data/misc/adb/adb_keys` holds two keys: this host's, and one with the comment `tobalr@…` that
was there before. It is probably the factory's. Anyone holding it gets root over USB. Check yours:

```sh
adb shell "cut -d' ' -f2 /data/misc/adb/adb_keys"
```

#### Removing the factory key

On Android 12, system_server keeps its own keystore in `/data/misc/adb/adb_temp_keys.xml` (binary
XML) and regenerates `adb_keys` from it. Keys found in `adb_keys` get imported into it, so the
factory key was in both. Editing only `adb_keys` doesn't last, and a clean reboot lets
system_server write its in-memory copy back. What worked (after backing up both files):

1. `settings put global adb_allowed_connection_time 0` (see below).
2. `adb_keys`: `grep -v tobalr@` into a temp file, then `cat` it back over the original. This keeps
   the owner (`system:shell`), mode and SELinux context.
3. `adb_temp_keys.xml`: `abx2xml`, `grep -v tobalr@`, `xml2abx`, then `cat` it back the same way.
4. `kill -9 $(pidof system_server)`. The framework restarts without saving its old keystore.
   ADB survived the framework restart and a full reboot afterwards, with only the host's key.

#### Turn off key expiry before the frame goes online

Android 11+ forgets an ADB key that hasn't connected for 7 days (`adb_allowed_connection_time`).
This frame's clock starts at the build date (2025-09-03) until it gets network time, so on Wi-Fi
the clock jumps forward more than a year and could expire every key at once. With no status bar,
navigation bar or Settings route on screen, that would leave no way in.
`settings put global adb_allowed_connection_time 0` (Developer options → "Disable adb
authorization timeout") keeps keys until they are revoked.

### Root and `su`

- `adb shell id`: `uid=0(root) ... context=u:r:su:s0`. `getenforce`: `Permissive`.
- `/system/xbin/su` is setuid root with mode `-rwsrwsrwx` (owner root, group shell), 5456 bytes,
  MD5 `422f5c45aafc516675a517941a571596`. Any app can run it and get root.

### Network listeners (offline, no Wi-Fi)

- One TCP listener: `0.0.0.0:38211`, owned by `net.frameo.frame` (uid 10025). Purpose not
  checked yet.
- No `adbd` listener on 5555.

### Vendor, updater and OTA components

| Component | Where | What we saw |
| --- | --- | --- |
| `com.softwinner.update` v2.1.0 | `/system/app/Update` | Allwinner OTA updater. `INTERNET`. Exposes a Settings entry (`EXTRA_SETTINGS`) |
| `update_engine` (native service) | init | Running as root (A/B OTA daemon). `ro.product.ab_ota_partitions` covers product, system, vendor, boot, vendor_boot, dtbo, the vbmetas and vendor_dlkm |
| `com.joyhong.test` v2.0.31 | `/system/priv-app/Test` | Joyhong factory test app, **runs as system uid 1000**. Granted `INSTALL_PACKAGES`, `REQUEST_INSTALL_PACKAGES`, `REBOOT`, `INTERNET`, `RECEIVE_BOOT_COMPLETED` |
| `net.frameo.frame` v1.27.5 | `/system/priv-app/Frame` | `INTERNET`, `RECEIVE_BOOT_COMPLETED` (boot receiver), `REQUEST_INSTALL_PACKAGES`. No `INSTALL_PACKAGES` or update-engine permission seen in `dumpsys` |
| `com.softwinner.awmanager` | `/system/priv-app/AwManager` | Allwinner system manager, priv-app |
| `com.allwinnertech.packageoverride` | `/product/app/PackageOverride` | Allwinner package override |
| `com.softwinner.settingssetup`, `.screenshot`, `.awlogsettings` | system | Allwinner setup, screenshot and log tools |

- `ro.fullja.fota.version=SDPFHD10W25_V2.00` (also `ro.fullja.total_memory`,
  `ro.fullja.total_storage`). No package named `fullja` is installed.
- No packages disabled out of the box (`pm list packages -d` is empty).
- Not installed: `com.waophoto.fota` (see the warning on the [C-2 A133](joyhong-c2-a133.md)),
  Google Play. Not checked yet: native vendor daemons such as `/system/bin/iotv` (see the
  [Runxion RK3126](runxion-zn-dp1002-rk3126.md)).

## Guesses (not yet confirmed)

- The `fullja` props suggest that a FOTA service (Fullja is likely the ODM's FOTA vendor) reports this
  model and version, probably through `com.softwinner.update` or `com.joyhong.test`. Not verified.
- Frameo pushes its own OS updates on other frames. On this A/B build that would likely go through
  `update_engine`, but no Frameo permission for it was seen. Not verified.
- `com.joyhong.test` running as system with `INSTALL_PACKAGES` and `INTERNET` could install APKs
  silently. Its code has not been read.
- 38211 is probably Frameo's local transfer or pairing service.

### Home screen

- HOME resolves to `net.frameo.frame/.ui.activities.AWaitForDeferredInitCompleted`. The only other
  HOME candidate is `com.android.settings/.FallbackHome`, so disabling Frameo with no replacement
  would leave a blank screen.
- No lock-task mode and no device owner.

## Backup (read-only)

Every partition except `userdata` (26 GiB, freshly set up), plus the 36 MiB before `mmcblk0p1`,
streamed over `adb exec-out dd ... | gzip`. Each was checked three ways: `sha256sum` on the frame, the
hash of the stream on the host, and a gzip readback, with exact byte counts. `boot_a`,
`bootloader_a`, `vbmeta_a` and `misc` were re-read independently and matched. About 4 minutes
over USB; 600 MB compressed, mostly `super`. `bootloader_b` and `vendor_boot_b` are all zeros (the
unused B slot). No `mmcblk0boot0`/`boot1` hardware partitions are exposed.

| Partition | Bytes | SHA-256 |
| --- | --- | --- |
| `boot_a` | 67108864 | `e50f54d50fc9657a830bbf079a6d4a0140eef69b9126e9633cca3114c760512a` |
| `vbmeta_a` | 131072 | `a8bb4d255be8daf9f9fa13ba6d197d93410c46803eeea4951db101e721b6736d` |
| `dtbo_a` | 2097152 | `f8ddf0f851137019abdc78b9c1216d3be0fd1e3e2146bd420434ccc5f4e98c05` |

## What was done (owner-approved, in order)

All changes are in `/data`; no partition was written.

| # | Change | Command | Undo | Result |
| --- | --- | --- | --- | --- |
| 1 | Allwinner updater and Joyhong test app off | `pm disable com.softwinner.update`, `pm disable com.joyhong.test` | `pm enable <pkg>` | See the note below; survived a reboot on the second try |
| 2 | WebView 91 → 156 | `adb install -r` of the re-signed LineageOS build (below) | `pm uninstall-system-updates com.android.webview` | Installed and selected, but renderers crash (below). **Undone**: back on stock 91 |
| 3 | Home Assistant minimal 2026.8.4 | `adb install` of `app-minimal-release.apk`, SHA-256 `8f58a7df71c61447d3370f5d5956a66e3523625dc4b51c8434bd166d3e731bea` (same as the [Rollei 100](rollei-smartframe-100.md)) | `adb uninstall io.homeassistant.companion.android.minimal` | Installs (32-bit); native screens and server discovery work; the login page (WebView) never loads |
| 4 | Home Assistant as Home | `pm enable io.homeassistant.companion.android.minimal/io.homeassistant.companion.android.launch.LauncherAlias`, then `cmd package set-home-activity` with the same component. The in-app switch needs a server connection first | `pm disable` the component | HOME resolves to `LauncherAlias`; comes up after reboot |
| 5 | SystemUI back on | `pm enable com.android.systemui` | `pm disable com.android.systemui` | Enabled after reboot, but no bars are drawn (see above) |
| 6 | Frameo off | `pm disable net.frameo.frame` | `pm enable net.frameo.frame` | After reboot: no Frameo, updater or test-app process; HA is Home; ADB still root; no TCP listeners at all |

**Wait for `package-restrictions.xml` before rebooting.** The first disables were rebooted within a
second and came back enabled, as on the [AMABOO](amaboo-gbzk-y1000.md#wait-before-rebooting-after-pm-disable-user).
The file was written about 8 s later. On this build the file is binary XML; read it with
`abx2xml /data/system/users/0/package-restrictions.xml -`. A root `pm` change is recorded as
`enabledCaller="shell:1000"`.

**Way back:** the firmware has no on-screen route to Android Settings (no bars). With the Firefox
Home app below, power-cycle the frame and tap **Android settings** during the 10 s countdown.
Otherwise use USB ADB: `adb shell am start -a android.settings.SETTINGS`. ADB does
not depend on Frameo: it was on before Frameo setup (`persist.sys.usb.config=adb`,
`adb_enabled=1`) and stayed on through four reboots, including with Frameo disabled.

### WebView update with the AOSP test key

The stock WebView (`/product/app/webview`) is signed with the AOSP public **test key**, cert SHA-256
`a40da80a59d170caa950cf15c18c454d47a39b26989d8b640ecd745ba71bf5dc`, not with the platform key.
The platform key is a different key; Frameo has its own key. So any `com.android.webview` signed with
that key installs as a normal update, without touching `/system` or `/product`:

1. Take the LineageOS prebuilt from
   [`android_external_chromium-webview_prebuilt_arm`](https://github.com/LineageOS/android_external_chromium-webview_prebuilt_arm)
   (Git LFS). Tested: commit `472d0ac`, 156.0.8078.47, LFS SHA-256
   `0dc261c3f37e9ac16a4f593ef316a097fc59815bb2082a8e38c519647bbcb3cc`. Package `com.android.webview`,
   versionCode 807804700, minSdk 29, `armeabi-v7a` only (this build is 32-bit), native libraries
   stored and page-aligned. LineageOS re-signs it at build time (`DEFAULT_SYSTEM_DEV_CERTIFICATE`),
   which is why AOSP test-keys builds like this one carry the test key.
2. Re-sign it with `build/target/product/security/testkey.pk8` from AOSP (APK Signature Scheme v2;
   `targetSdk` 37 requires it). Check the frame's own cert first: pull
   `/product/app/webview/webview.apk` and compare `META-INF/CERT.RSA` to `testkey.x509.pem`.
3. `adb install -r`. PackageManager accepted it as an update to the system package.

No `apksigner` or Java was on the host, so a short stdlib Python v2 signer (with `openssl dgst
-sha256 -sign`) was used; PackageManager verifying the signature on install is the check. Any
`apksigner sign --key testkey.pk8 --cert testkey.x509.pem` works the same way.

### WebView can't render anything on this firmware

Installing WebView 156 worked, but **no WebView renderer can start on this firmware, with 156 or the
stock 91**. When the Home Assistant app opened its login page, it hung on the logo. Each time, the
renderer forked from `webview_zygote` aborted at once:

```text
F webview_zygote: JNI FatalError called: (zygote) Failed open(/sys/kernel/tracing/trace_marker, 1): Permission denied
```

`webview_zygote` holds `/sys/kernel/tracing/trace_marker` open, and the forked isolated renderer
has to reopen it. On this build `/sys/kernel/tracing` is mode `0700 root`, so it can't. Ten
tombstones, all `webview_zygote` with this abort. The last came after a reboot with only the
stock WebView 91 installed (`pm uninstall-system-updates com.android.webview`). The first ones
appeared only once something used WebView (Frameo never did here). So any WebView-based app
(the Home Assistant app, this repo's kiosk, Fully Kiosk) hangs on this frame.

## Dashboard: Firefox web app, started by a Home app

Firefox brings its own engine (Gecko). Its tab and GPU processes are ordinary app processes, not
forked from `webview_zygote`, so the trace_marker abort doesn't apply. The end result: the Home
Assistant dashboard full screen at boot, with no taps.

| # | Change | How | Undo |
| --- | --- | --- | --- |
| 7 | Firefox 158.0.2 `armeabi-v7a` | `adb install` from `archive.mozilla.org/pub/fenix/releases/158.0.2/`, SHA-256 `939002048eecad439ab1b81aca8644c842f731bf6f9a0feb03cfcf45d1204013`, signer `CN=Release Engineering, O=Mozilla Corporation`, cert SHA-256 `A7:8B:62:A5:…:9B:04` (same as in [biuframe.md](biuframe.md)). The owner did Firefox's first-run screens (terms) on the panel | `adb uninstall org.mozilla.firefox` |
| 8 | Boot Home app | [`scripts/firefox-home`](../scripts/firefox-home/README.md), set with `cmd package set-home-activity` | `adb uninstall com.photoframe.firefoxhome` |
| 9 | Dashboard as a Firefox web app | Firefox **⋮ → More → Add app to Home screen** on the dashboard; the Home app accepts the pinned shortcut and launches it | Uninstall the Home app, or Firefox |

Observations:

- **First Firefox launch:** every Gecko child process failed to bind (`ServiceAllocator$BindException:
  Cannot connect to process`, `Failed to launch tab subprocess`), so the page stayed blank. No
  reason was logged by system_server. Starting the GPU service from a root shell worked. After
  `am force-stop org.mozilla.firefox` and a relaunch, the child processes started and pages
  rendered. It did not happen again, including after reboots. Guess: the vendor
  `BackgroundManagerService` (a thread of that name is in system_server) during first launch.
- **The web app needs `https`.** In Firefox 158 the `VIEW_PWA` intent filter only accepts
  `https`, and a plain `http://<ip>:8123` dashboard opens in a normal tab with the toolbar. Here
  the dashboard is served through the owner's HTTPS reverse proxy.
- **"Add app to Home screen" only appears when the default Home app can pin shortcuts.** With
  a Home app that has no `CONFIRM_PIN_SHORTCUT` activity, the menu shows only "Add to
  shortcuts" (Firefox's own top sites). `scripts/firefox-home` accepts the pin and stores
  Firefox's shortcut ID (`https://<site>/?homescreen=1`).
- The first web-app launch after the pin hung on Home Assistant's splash (connections to the
  proxy were open). After `am force-stop` of Firefox and a relaunch through the Home app, it
  loaded. Not seen again.
- **Boot timing**, one run: web app in front 55 s after `adb reboot`, dashboard fully drawn by
  95 s. Firefox about 143 MB PSS; about 270 MB of RAM available afterwards.
- Home Assistant's frontend (2026.10) renders and stays logged in ("Keep me logged in").

## Before Wi-Fi

- Use an isolated or IoT network and a dedicated, limited Home Assistant user. Root ADB stays on
  over USB, `su` is world-runnable, a factory ADB key was authorized (removed on this unit), and the
  security patch is from 2022. This unit gets a UniFi IoT VLAN that can reach only Home Assistant's
  port 8123 on the home LAN.
- Turn off ADB key expiry first (above).
- `update_engine` is a native service and keeps running. With the updater app and Frameo off,
  nothing obvious is left to feed it a payload. Check `logcat -s update_engine` after first going
  online.
- Frameo's ADB toggle no longer exists in practice (Frameo is disabled); ADB stays on regardless.
