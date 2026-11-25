# Frame Calendar

A standalone landscape Android Home app: a Google Calendar-style month grid on
the left 75%, and the real Home Assistant frontend on the right 25%. The calendar
and panel share a dark Catppuccin-inspired palette. This is separate from Home HQ;
installing it does not replace the existing kiosk, vendor apps or system WebView.

## Build

Requires JDK 17 or 21 and Android SDK platform 35. The included Gradle 8.13 wrapper
verifies its distribution checksum. Dependencies are
pinned in `build.gradle`. The default APK targets 32-bit ARM photo frames; change
`abiFilters` if building for another architecture.

```sh
export ANDROID_HOME=/path/to/android-sdk
./gradlew --no-daemon testDebugUnitTest assembleDebug lintDebug
node --test src/test/panel.test.cjs
adb -s FRAME_IP:5555 install -r build/outputs/apk/debug/FrameCalendar-debug.apk
adb -s FRAME_IP:5555 shell am start -n com.wesbos.framecalendar/.MainActivity
```

GeckoView 143 is bundled because Firefox 144 and newer require Android 8.
It has its own certificate store and persistent login profile; it does not require
Google Play services or a system WebView update. **GeckoView 143 no longer receives
security updates.** Android 6 is also unsupported. Keep the frame on a trusted,
restricted network, use a limited Home Assistant account, and do not browse
unrelated sites or expose ADB to the internet.

## Connect calendars and the panel

Open the **gear icon > Connections and time zone**:

- For each Google calendar, use Google Calendar on a computer: **Settings >
  Settings for my calendars > [calendar] > Integrate calendar > Secret address in
  iCal format**. Paste that private HTTPS URL into the corresponding field.
  Do not make the calendar public. Google can withhold private feeds for calendars
  you do not own; in that case the calendar owner must provide a feed, or configure
  an authorized integration in Home Assistant.
- Paste a TripIt private iCalendar feed in the TripIt field.
- Use the Martin and Catherine fields for personal calendars, and UK holidays
  for a public UK holiday iCalendar feed.
- Alternatively, enter `ha:calendar.entity_id` for calendars already integrated
  with Home Assistant. These are read using the panel's authenticated session.
- Enter the Home Assistant dashboard URL and sign in in the right-hand panel.
  HTTPS is recommended. Plain HTTP is supported only for trusted LAN deployments.
- Choose an IANA time zone, such as `Europe/London`.

Google calendars are read-only; no Google account password or OAuth client is
needed on the frame. Private feed URLs grant access to calendar contents: treat
them like passwords. Settings and cached feeds live in the app's private data,
Android backups are disabled, and neither belongs in Git. Rooted frames cannot
provide strong isolation between apps.

The panel discovers dashboards/panels titled **Frame**, and views titled or
pathed **frame**, every minute. Until it finds one, it displays the configured
dashboard with an explicit “Frame not found” notice. It does not create or edit
Home Assistant dashboards. The browser subscribes to `lovelace_updated` on the
frontend's authenticated, reconnecting websocket and reloads the current dashboard
when its configuration changes. Live entity updates remain Home Assistant's own
frontend behavior. Browser chrome is hidden without changing server configuration.
The successful panel status is hidden; connection and discovery errors remain visible.
If the panel cannot connect or gets stuck loading, it retries automatically and
also reconnects when network access returns. A sign-in page is left uninterrupted.

Calendar feeds sync every five minutes, when network access returns, and when
pressing the **reload icon**. The app expands events into a rolling cache covering
at least 12 months ahead, plus the three previews, so navigating within that range
does not wait for a download. Previously downloaded iCalendar feeds are loaded
first on startup and can still be displayed offline; Home Assistant calendar
entities require a live connection. Calendar names appear only in settings and
event details; a thin animated line marks synchronization without moving the
calendar. Three compact
previews below the main grid show the following months, shading dates with events
from any configured calendar. Only the outer edges show adjacent-month dates.
The grid supports Sunday-first months, four to six weeks, recurring events,
exclusions and moved/cancelled occurrences, exclusive all-day end dates, and
bars spanning days/weeks. Events are ordered by day and fill the available space.
Tap an event for details, or tap an empty part of a day to see all its events,
including overflow. Unavailable feeds show an explicit notice.
Exact duplicates across calendars are displayed once, preferring Martin's
version. Matching includes title, start/end, all-day status, location and description;
timed events compare instants rather than time-zone labels.
`RECURRENCE-ID;RANGE=THISANDFUTURE` is reported as unsupported rather than silently
displaying an incorrect schedule.

Opening or waking the calendar returns to the current month. Midnight and
network-time changes also update today's date; manual month browsing remains
available. If the device date is earlier than 10 March 2026, the calendar waits
for a corrected clock instead of displaying or downloading the wrong month.

## Default Home and undo

Installing does **not** select a new default launcher. Enable the Home alias and
then choose **Frame Calendar > Always** in Android's Home chooser:

```sh
adb -s FRAME_IP:5555 shell am start -n com.wesbos.framecalendar/.MainActivity --ez home true
adb -s FRAME_IP:5555 shell am start -a android.intent.action.MAIN -c android.intent.category.HOME
```

Some newer Android versions also support:

```sh
adb -s FRAME_IP:5555 shell cmd package set-home-activity com.wesbos.framecalendar/.Home
```

Do not assume that command exists on Android 6. Keep the old launcher and ADB
available. **Settings > Android settings** is always accessible from the app.
**Settings > Use another Home app** disables this app's Home alias and opens the
existing launcher/chooser. The equivalent ADB undo is:

```sh
adb -s FRAME_IP:5555 shell pm disable com.wesbos.framecalendar/.Home
adb -s FRAME_IP:5555 shell am start -a android.intent.action.MAIN -c android.intent.category.HOME
```

Select the previous launcher with **Always**. Uninstalling Frame Calendar removes
its settings and saved logins. No flash, `/system`, vendor app, screensaver setting
or boot partition change is required.

The calendar stays bright for three minutes after interaction, then starts
Android's selected screensaver without a dimming phase. Change the delay under
**Settings > Screensaver delay** (1-60 minutes). This uses SystemUI's native
screensaver launcher, without root; on firmware that omits it or when no
screensaver is enabled, Android's existing screen timeout remains in use.
Screensaver-start failures are reported and also restore the Android timeout.
Dismissal returns to today's calendar with a brief fade. Calendar sync and Home
Assistant updates continue while the screensaver is showing, subject to Android's
background restrictions. Overnight hours belong to the photo screensaver's settings.

## Floating navigation

On frames without a navigation bar, enable **Frame Calendar navigation** in
Android **Settings > Accessibility**. Its draggable **Back** and **Dashboard**
buttons work outside the app; Dashboard returns to Frame Calendar. The service
does not read screen content, and hides the buttons while the calendar or
screensaver is showing. If Home HQ's navigation is already enabled, turn it off
after enabling Frame Calendar navigation to avoid overlapping controls.
Disable the service in Accessibility settings to remove the buttons.

For temporary diagnostics, launch MainActivity with `--ez debug true` to print
browser console messages to local Android logs; `--ez debug false` turns this off.
Console output and remote debugging are off by default. Do not publish logs
without checking them for private dashboard data.

## Private ADB provisioning

For unattended setup, a private JSON object can have the fields `personal`,
`family`, `tripit`, `holidays`, `ha_url`, and `timezone`. Omitted fields retain
their saved values. Optional `ha_auth` is the Home
Assistant frontend's `hassTokens` object; only provision a session authorized by
the owner, and never place it in source control.

Start the app first and wait for `/data/data/com.wesbos.framecalendar/files` to
exist. On a rooted device, copy the JSON to that directory as
`config-import.json`, set its owner/group to the application's UID and mode 0600,
then start MainActivity with `--ez import_config true`. The app validates the
configuration, saves it privately and deletes the import file. ADB must **not**
create the application's `files` directory as root: that prevents both private
configuration and Gecko's profile from working. Non-root devices should use the
on-screen settings.
