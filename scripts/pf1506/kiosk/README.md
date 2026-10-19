# PF1506 calendar kiosk app

A full-screen wall calendar for the PF1506 on the LineageOS 20 GSI. It has no Gradle build and no Google account
or server. It's the home app, so the frame powers on straight into it.

## What it shows

- **Week view and a detailed Today panel.** Tap an event or a day for details.
- **Each calendar in its own colour.** An event that's in several calendars shows once, with a dot per calendar.
- **Weather** from Open-Meteo, which needs no key: now, the next 24 hours and 7 days. Tap a day for its hour-by-hour
  forecast.
- **Chores (optional):** a separate calendar with events titled `Ana: Make bed`, `Ana, Ben: Feed the dog`, or no
  name for everyone. Each person ticks off their own on the frame.
  - Daily chores reset every day.
  - A chore that repeats weekly stays on the list for the 7 days from each occurrence, and so does its tick.
  - An `Order: N` line in the event description sets the order on the list.
  - Ticks are saved on the frame.

## Two modes

- **Standalone (default).** The page is built into the app, and the app reads each calendar's **secret iCal
  address** itself, so no server is needed. The frame needs internet: Google Calendar, `api.open-meteo.com`, and
  network time for the clock.
- **URL mode.** Shows a page you host yourself, such as your own calendar server on the LAN:
  `adb shell am broadcast -n com.example.pf1506kiosk/.AdminCommandReceiver --es url http://<server>:<port>/`.
  - The frame can stay off the internet. The app turns automatic time off, and every 5 min sets the clock from the
    HTTP `Date` header of `<page origin>/healthz`, when that returns 200. Android's `setTime` only works with
    automatic time off.
  - The clock trusts that server: anything that can answer for it on your LAN can set the frame's clock. Use a server
    you control, on the LAN.
  - Go back to standalone with `--ez standalone true` (automatic time comes back on).

Why not "Sign in with Google"? The GSI has no Google Play services, and Google blocks sign-in inside embedded
WebViews. Google's TV-style device sign-in doesn't offer calendar access. A secret iCal address is read-only, needs
no Google Cloud project, and works for any calendar service that publishes iCal.

## Setting it up (standalone)

1. On first start, the frame shows an address such as `http://192.168.1.50:8080` and a 6-digit **PIN**.
2. On a phone on the same Wi-Fi, open that address and enter the PIN. Then add:
   - **Calendars:** for each one, a name, a colour and its secret iCal address. In Google Calendar on a computer:
     Settings → the calendar → Integrate calendar → **Secret address in iCal format**.
   - **Weather:** search for your town, and pick °F/mph or °C/km/h.
   - **Chores (optional):** the chores calendar's secret address, and the people with their colours. "Other names"
     lets `Benjamin: ...` count for Ben.
3. Save. The frame reloads with your calendars.

The setup page runs for 15 minutes after each power-on, for as long as no calendar is set, and for 15 minutes after
each save. Five wrong PINs close it until the next start. It's plain HTTP on your LAN, like a router's admin page,
so the addresses you paste cross your Wi-Fi unencrypted. Treat a secret iCal address like a password: anyone who has
it can read that calendar. Google lets you reset it if it leaks.

The frame's time zone (Settings → System → Date & time) is the calendar's time zone. Calendars refresh every 5
minutes. If one can't be reached, its last valid copy stays on screen with a notice. Copies are keyed by a digest
of the secret feed address, so replacing or reordering calendars cannot reuse another feed's disk cache. Removed
feeds and unidentifiable old slot caches are discarded; the active chores feed is retained. Downloads must pass
UTF-8, calendar-envelope and component-balance checks before replacing a good copy. This is structural validation,
not complete RFC 5545 event validation.

## Kiosk behaviour

- **Kiosk:** device owner, pinned in lock-task mode, so there's no status bar, navigation bar or lock screen, and
  Back does nothing.
- **Dim:** after 1 min without a touch, the page is covered with black at minimum backlight. The display stays on,
  so a tap wakes it. On this frame, touch can't wake a screen that's truly off. The waking tap is swallowed, so it
  never opens anything.
- **Quiet hours:** 02:00–07:00 by default (`QUIET_START_HOUR` / `QUIET_END_HOUR` in `ScheduleReceiver.java`). The
  screen goes fully off and an exact alarm turns it back on. During quiet hours only the power button wakes it.
- **Back to the calendar:** after a minute untouched, the page returns to this week, with nothing open.

## Build (Linux or macOS; Android SDK build-tools 35 and platform 33, JDK 17+)

    ANDROID_SDK=~/android-sdk bash build.sh      # -> frame-kiosk.apk

`build.sh` downloads ical.js 2.2.1 (MPL-2.0, the calendar parser) from the npm registry. It checks the download
against the registry's sha512 before using it. The first build also creates `kiosk.keystore`: keep it, because
updates must be signed with the same key.

## Install

    adb install -r frame-kiosk.apk
    adb shell dpm set-device-owner com.example.pf1506kiosk/.AdminReceiver
    adb shell cmd package set-home-activity com.example.pf1506kiosk/.MainActivity
    adb shell am start -n com.example.pf1506kiosk/.MainActivity

`dpm set-device-owner` only works while the device has no accounts, which is true of a fresh GSI install with no
Google apps. As device owner, the app turns automatic time on in standalone mode and off in URL mode.

**Admin commands** (`url`, `standalone`, `release_owner`) go to `AdminCommandReceiver`. It's protected by
`android.permission.DUMP`, which the adb shell holds and ordinary apps can't get. The home screen activity ignores
intent extras, so other apps can't change the page or release device owner.

**This isn't a security boundary.** Lock-task mode keeps a casual user in the calendar. It doesn't stop someone with
the frame in hand, USB access, or root ADB, and this build's ADB has no authentication.

## Undo

    adb shell am broadcast -n com.example.pf1506kiosk/.AdminCommandReceiver --ez release_owner true
    adb shell pm uninstall com.example.pf1506kiosk

After adding a policy to `res/xml/device_admin.xml`, an existing device owner doesn't pick it up on update. Release
the device owner as above, then run `dpm set-device-owner` again.

## Files

| File | What it does |
| --- | --- |
| `assets/web/index.html` | The calendar page (1920×1080) |
| `assets/web/backend.js` | Standalone logic: iCal parsing and repeats (with ical.js), duplicate folding, chores, weather |
| `assets/web/setup.html` | The phone settings page |
| `src/.../MainActivity.java` | WebView, kiosk mode, dimming, quiet hours, URL-mode clock |
| `src/.../LocalContent.java` | Answers the page's requests in standalone mode: assets, settings, calendar downloads with a kept copy |
| `src/.../SetupServer.java` | The PIN-protected settings page on port 8080 |
| `src/.../Config.java` | Saves and checks settings; keeps the iCal addresses away from the page |
| `src/.../ScheduleReceiver.java` | Quiet-hours alarms |
