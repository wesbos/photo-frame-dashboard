# Skylight Calendar 2 (MediaTek MT8786, Android 15)

One unit, tested 2026-11-16 from macOS (Apple silicon). Observations are separate from guesses,
and guesses are marked. This is a different board from the 150-CAL in
[next-session.md](next-session.md) and [skylight-d156.md](skylight-d156.md) (Rockchip RK3566,
Android 12): don't run the Rockchip loader or boot-patch steps on it. No root was needed: USB
ADB came from Android's own Developer options, and the kiosk runs as the Home app.

## Identify it

Over ADB:

| Property | Value |
| --- | --- |
| `ro.build.fingerprint` | `alps/vnd_tb8786p1_64_k66_wifi/tb8786p1_64_k66_wifi:15/AY7222B-mt8786_15_inch-build-20260928193323/skylightOS-cal2_15-mt8786-user-prod-20260928193305:user/test-keys` |
| `ro.product.model` | `tb8786p1_64_k66_wifi` (also the USB product name; USB manufacturer `HUAQIN`) |
| `ro.hardware` | `mt6768` (MediaTek MT8786) |
| Android | 15 (first API level 35), `user` build, `ro.debuggable=0`, security patch 2025-01-05 |
| Boot | A/B slots, `ro.boot.flash.locked=1`, verified boot `green`, `ro.oem_unlock_supported=0` |
| Display | 1920×1080 at 240 dpi (CSS viewport 1280×720) |
| WebView | `com.android.webview` 124.0.6367.219, the only provider. No Play Store, GMS or Chrome |
| Vendor packages | `com.skylight` 26.33.0 (Home), `skylight.watchdog` 3.7.2, `skylight.keyboard` 1.5.0 (default IME) |

## Get ADB

With ADB off, the frame enumerates as MTP only (`0e8d:2008`, as in
[#88](https://github.com/wesbos/photo-frame-dashboard/issues/88)). The hidden manufacturer-code
menu from [app-analysis.md](app-analysis.md) wasn't needed:

1. Hold Power until the power menu appears. With it on screen, drag two fingers down from the top
   edge: Quick Settings opens. Tap the gear for Android Settings.
2. Settings → About → tap **Build number** 7 times, then turn on **USB debugging** in Developer
   options.

Afterwards USB shows `0e8d:201c` (MTP + ADB) over a USB-C cable to the Mac, and `adb devices`
listed it as `device`. No RSA prompt appeared during this session; it may have been accepted
when USB debugging was first turned on. The shell is `uid=2000(shell)`. There's no `su`.

By 2026-11-16 the two-finger gesture no longer opened Quick Settings. `skylight.watchdog` had updated
`com.skylight` (to 26.33.0) and the keyboard in the days before. Guess: one of those updates blocks
it. With ADB on, open Settings directly with `adb shell am start -a android.settings.SETTINGS`.

## What the vendor left on it

- **`skylight.watchdog`** runs as the `system` user from `/system_ext/priv-app/Skylight_watchdog`
  and holds `INSTALL_PACKAGES`, `REBOOT` and `RECOVERY`. It's the installer of record for
  `com.skylight` and `skylight.keyboard`, and updated both in the week before testing. Decompiled
  (jadx): it posts a status report (serial number, versions, disk, RAM, eMMC wear) to
  `https://app.ourskylight.com/hq/status_reports`. The reply can name an APK of any package name
  to install silently, force a reinstall of the app, or deliver a firmware OTA (applied with A/B
  `UpdateEngine`), followed by a reboot right away or at a scheduled time. It starts at boot and
  restarts itself. No code that changes `adb_enabled` or launches `com.skylight` was found.
  Guess: a firmware OTA is the real risk to a kiosk, since it could turn ADB off.
- **`com.skylight` turns Wi-Fi on at every boot**, even when it isn't Home: logcat showed
  `setWifiEnabled package=com.skylight uid=1000 enable=true` about 3 s after boot. Turning Wi-Fi
  off in Settings doesn't keep the frame offline across a reboot.
- **No navigation bar.** The three-button, gestural and transparent navbar overlays are all
  disabled, so Android Settings has no way back on screen.
- **A very long Power press is factory reset** (`VERY_LONG_PRESS_POWER_FACTORY_RESET` in
  `dumpsys window policy`). A short press sleeps; a long press opens the power menu.

## Back up first

Without root and with the bootloader locked, the flash can't be read or written, and
`ro.oem_unlock_supported=0` rules out unlocking it from Developer options. What was saved instead,
so every change below can be undone: the APKs (`pm path`, plus the factory copies under
`/system_ext/priv-app`), `getprop`, `settings list global|secure|system`, `pm list packages -f -u`
and the Home resolver. Everything below stays in userspace.

## Make it a kiosk

The kiosk from `dashboard/kiosk` (target SDK 28) installed normally, with no "older version of
Android" dialog. In order, with the owner checking each step on the panel:

```sh
adb install homehq.apk
# The panel has no navigation bar: turn on the kiosk's floating Back and Dashboard buttons.
adb shell settings put secure enabled_accessibility_services com.wesbos.homehq/.NavigationService
adb shell settings put secure accessibility_enabled 1
adb shell pm grant com.wesbos.homehq android.permission.WRITE_SECURE_SETTINGS
# undo: pm revoke …, settings delete secure enabled_accessibility_services, accessibility_enabled 0
```

By hand on the panel: the two-finger hold → **Android settings** → **Apps**, then **Dashboard**
back (README rule 9). Then Home, waiting 30 s before rebooting:

```sh
adb shell am start -n com.wesbos.homehq/.MainActivity --ez home true
adb shell cmd package set-home-activity com.wesbos.homehq/.Home
# undo: set-home-activity com.skylight/odesk.johnlife.skylight.activity.MainActivity, then --ez home false
```

`set-home-activity` answered `Success` the first time, and the frame booted into the kiosk. Then the
vendor apps, which the shell is allowed to disable even though they run as `system`:

```sh
adb shell pm disable-user --user 0 skylight.watchdog   # updates, OTA, status reports
adb shell pm disable-user --user 0 com.skylight        # the Skylight app; also stops the Wi-Fi forcing
# undo: adb shell pm enable <package>
```

`skylight.keyboard` stays enabled: it's the only IME. After a reboot both packages stayed
disabled, nothing from Skylight ran, Wi-Fi stayed as set, and the kiosk came up signed in.

## After Skylight is gone

- **Time zone falls back to GMT.** Automatic time zone is on, but this frame has neither telephony
  nor geolocation detection (`cmd time_zone_detector is_geo_detection_supported` → `false`).
  Guess: the Skylight app set the zone from the account. The shell can't set it on Android 15
  (`suggest_manual_time_zone` needs `SUGGEST_MANUAL_TIME_AND_ZONE`). Set it by hand:
  `adb shell am start -a android.settings.DATE_SETTINGS`, turn off automatic time zone, pick the
  zone, then restart the kiosk.
- **The boot animation stays Skylight's.** It's `/system/media/bootanimation.zip`, read-only under
  verified boot.
- **A brief "Webpage not available" at boot.** The kiosk started about 1.6 s before Wi-Fi joined, so
  its first load failed (`ERR_INTERNET_DISCONNECTED`), and the retry ran when Wi-Fi connected. Then
  `onPageFinished` arrived for WebView's error page (`chrome-error://chromewebdata/`) after the
  retry had started. The kiosk took that as a successful load and hid its offline screen until the
  dashboard drew.
- **`innerWidth`/`innerHeight` can exceed the screen.** On this WebView they read 1315×740 while
  `document.documentElement.clientWidth`/`clientHeight` and `visualViewport` read 1280×720. That
  happened when an absolutely positioned element overflowed the viewport before its `transform:
  scale()` applied. Size a scaled layout from `clientWidth`/`clientHeight`.

## Not tested

- Network ADB, factory reset, and whether a Skylight OTA turns ADB off.
- Which app version blocks the power-menu Quick Settings gesture.
- A second unit.
