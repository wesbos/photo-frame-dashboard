# PF1007L `20260410`: Test App switch (T3d) on macOS, full offline-kiosk setup

One unit, macOS (Apple silicon). This report confirms the stock **Test App switch**
([T3d](pf1007l-start-here.md#t3d-adb-with-no-additional-tools-required), password `YHK88888888`)
on **April `20260410`** firmware — a firmware the T3d section did not previously list as confirmed —
and records a full offline kiosk setup that needed no SD card, no network, and no boot patch.

## Unit

| Item | Value |
| --- | --- |
| About model / firmware | PF1007L / `YHK.F-null-A33-1001-D1024-PF1007L-321-OS-AIMOR.0.20260410` |
| AiMOR version | 6.0.78 |
| Android | 6.0.1 (SDK 23), `armeabi-v7a`, SELinux **Disabled** |
| eMMC | 30,777,344 sectors (15,758,000,128 bytes) |
| Boot image SHA-256 (sector 172032, 31,028 sectors) | `8ffc2a7d95972422b97ecf7e82da7002011bdacedcbfcc74dd52ae871b98a24e` (the tested `20260410` value) |
| Host | macOS (Apple silicon), `adb` 1.0.41 |

## Access: Test App switch (T3d)

Stock USB was `1f3a:1000` ("Android") with an empty `adb devices`. The switch at
About → tap **Model Number** → **Open test app** → password `YHK88888888` → **IS CLOSED** to
**is open**, then replug, moved USB to **`1f3a:1002`** and gave `adb shell id` → `uid=0(root)`.
`persist.sys.usb.config` was `mass_storage,adb` and `adb_enabled` was `1`. Root USB ADB **survived
a power-cycle** with no further action, so the switch is persistent on this firmware too.

This matches the May (`20260519`/`20260529`, [#135](https://github.com/wesbos/photo-frame-dashboard/issues/135))
and January ([test-app password report](pf1007l-20260113-test-app-password-report.md)) results; the
new data point is that it also works on `20260410`.

## Cable note

Two cables powered the frame but carried no USB data (charge-only). A known-good USB-A → USB-C
**data** cable into a Mac USB-A port enumerated `1f3a:1000`. Worth repeating the existing guidance:
test the cable against a phone before concluding "no USB data".

## Full setup after root (all over USB ADB, frame kept offline)

- **Verified eMMC backup** over `busybox dd` in 256-MiB chunks (host md5 == on-device md5 per chunk;
  whole-image size exact; boot/env/misc/recovery re-read device-vs-image matched; boot hash matched
  `8ffc2a7d`). `toybox dd` rejected `bs=1M` ("illegal number"); `/sbin/busybox dd bs=1M` worked.
- **WebView 44 → 106** `/system` swap per
  [the upgrade section](allwinner-a33-pf1007l.md#6-upgrade-webview-before-using-the-kiosk): native
  libs placed under `lib/arm/`, byte-for-byte readback before and after the live move, stock tree
  preserved at `/system/homehq-stock-webview`. Reports `versionName=106.0.5249.126` and renders.
  Note: `adb push` left the staged files world-writable (666/777); an explicit `chmod 644`/`755`
  was needed, as `find … -exec … {} +` did not apply under this toybox.
- **Kiosk** built with `KIOSK_SITE=` so the demo dashboard is **bundled in the APK** and served at
  `http://127.0.0.1:8765/` — the frame shows the dashboard with no network and no Cloudflare, which
  also sidesteps the missing-CA-root HTTPS issue. Built with `aapt2`/`d8` from **build-tools 31** +
  the `android-31` `android.jar` + JDK 11 (34 was not installed); `kiosk/build.sh` only needed its
  hardcoded `android.jar` path made overridable.
- Home HQ set as default Home; **NavigationService** floating Back/Dashboard buttons enabled
  (`WRITE_SECURE_SETTINGS` granted); vendor apps disabled (`com.efercro.os.aimor`, `com.yhk.qeota`,
  `com.DeviceTest`, `com.android.gl2jni`); both saved Wi-Fi networks forgotten.

## Gotchas

- `adb reboot` hung; a power-cycle worked.
- Disabling AiMOR changed the set of Home candidates and re-triggered the Home chooser on the next
  boot; re-selecting **Home HQ → Always** made it stick permanently.
- No RTC battery: after a power-cut the clock starts near 1970, so the offline demo's date is wrong
  (the demo's time is hardcoded anyway). Only matters if the frame goes back online (HTTPS).

## Result

Boots clean into the dashboard; no vendor software runs; nothing phones home. No step failed.
