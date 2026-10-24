# Home HQ kiosk navigation

Hold two fingers still on the dashboard for 1.5 seconds to open the native controls. Keep the
fingers at least an inch (about 2.5 cm) apart: on PF1007L frames the `gslX680` touchscreen reads
closer fingers as one touch.

- **Open launcher** opens another installed Home app, such as Rootless Launcher.
  If none is available, it opens Android Settings.
- **Android settings** opens the device's Settings app.
- **Wi-Fi settings** opens Android's Wi-Fi list directly.
- **Reload dashboard** reloads the current URL.
- **Back to dashboard** dismisses the controls.

## Optional single-tap Menu button

On panels where the two-finger gesture is unreliable, enable a native **Menu** button:

```sh
adb shell am start -n com.wesbos.homehq/.MainActivity --ez menu_button true
```

It opens the same controls with one tap. The preference survives later launches; the button
is hidden by default. Turn it off with the same command and `--ez menu_button false`.
The two-finger gesture remains available in either mode.

The button occupies 72×48 dp, with 12 dp margins at the bottom left, above both the page and
the offline screen. Leave that area clear in your dashboard when enabling it. It needs no
root or additional permissions. The button and physical single-tap interaction were tested
in a local adaptation on the [QCREA YYD-1156](../../docs/qcrea-yyd-1156.md); the saved opt-in is
the shared-kiosk version of that adaptation.

## Dashboard URL

The kiosk opens the hosted demo dashboard by default. To show your own, save its URL once:

```sh
adb shell am start -n com.wesbos.homehq/.MainActivity --es url https://your-dashboard/
```

`scripts/set-kiosk-url.sh <url>` from the repository root does the same, and prints the saved
URL when run without one.

Every later launch, including after a reboot, opens the saved URL. Links that other apps open
in the kiosk, such as a sign-in page, are shown but not saved.

## A page bundled in the APK (no server)

A static page can ship inside the APK instead of being hosted. Build with `KIOSK_SITE` set to a
folder that has an `index.html` (from `dashboard/`):

```sh
KIOSK_SITE=/path/to/site ANDROID_HOME=/path/to/android-sdk bash kiosk/build.sh
adb install -r kiosk/build/homehq.apk
adb shell am start -n com.wesbos.homehq/.MainActivity --es url 'http://127.0.0.1:8765/'
```

On Windows, set `$env:KIOSK_SITE` before `.\build.ps1`.

Home HQ answers `http://127.0.0.1:8765/` from those files itself. Nothing listens on the port, no
other machine is needed, and the page loads without Wi-Fi. Every other URL, including the page's
own API calls, goes to the network as usual. ES modules work, which a `file://` page can't do, and
`localStorage` belongs to the `http://127.0.0.1:8765` origin. A query string
(`http://127.0.0.1:8765/?room=kitchen`) reaches the page unchanged; quote the URL in `adb shell`.
Don't put API keys or tokens in the bundled files or the saved URL: anyone with ADB on the frame
can read them, and so can any page shown at that origin. Keep them on a server
([building-for-the-frame.md](../../docs/building-for-the-frame.md)).
To change the page, rebuild and `adb install -r`. Without `KIOSK_SITE` the APK bundles nothing
and the address answers 404.

## Start at boot

To have the frame boot into the dashboard, make the kiosk its Home app. Installing the kiosk
does not offer it as a Home app, so nothing changes until you run:

```sh
adb shell am start -n com.wesbos.homehq/.MainActivity --ez home true
adb shell cmd package set-home-activity com.wesbos.homehq/.Home
```

If `set-home-activity` answers "Failed to set default home", wait a few seconds for the Home alias
to register and run it again (seen on a Skylight 150-CAL).

Wait about 30 seconds before rebooting. Android saves the Home alias a few seconds later, and on
a PF1508 (Android 15, #167) a reboot 2 seconds after these commands turned the alias back off, so the
frame booted into the previous Home app. The same delayed save lost a `pm disable-user` on a
Pastigio FRAME156 (#139).

Android 6 frames (PF1007L, BIUFRAME) don't have `cmd package set-home-activity`. After the first
command, open the Home chooser instead, then tap **Home HQ** and **Always** on the frame. Keep
another launcher installed so **Open launcher** has somewhere to go.

```sh
adb shell am start -a android.intent.action.MAIN -c android.intent.category.HOME
adb shell 'grep -A2 "<preferred-activities" /data/system/users/0/package-restrictions.xml'   # check it stuck
```

The kiosk then opens the saved URL at boot, and the Home button returns to it. If the page
fails to load at boot because Wi-Fi isn't up yet, the kiosk keeps retrying. In the controls,
**Open launcher** skips the kiosk and opens another Home app. To undo, pick another Home app in
Settings → Apps → Default apps, then run the first command with `--ez home false`.

## Screen density

The dashboard is laid out for 1280×800 at density 160. On wider screens, such as 1920×1080 frames,
it keeps the 800 px height and widens to fill the screen. Most 1280×800 frames ship at 160, but a VESWWE
`DP101` shipped at 190 and the bottom of the dashboard was cut off
([veswwe-dp101.md](../../docs/veswwe-dp101.md)). Check with `adb shell wm density`. If it isn't 160:

```sh
adb shell wm density 160      # undo: adb shell wm density reset
```

Android's own menus get smaller too. The setting survives a reboot.

## Frames without Home or Back buttons

Some frame firmware omits Android's navigation bar. The two-finger gesture only
works inside Home HQ, so it cannot bring you back from another app's settings.

Enable **Home HQ navigation** in Android **Settings → Accessibility**. The
optional service adds floating **Back** and **Dashboard** buttons outside Home HQ:

- **Back** performs Android's normal Back action.
- **Dashboard** returns directly to Home HQ, keeping the current dashboard URL.
- Drag the dots to move the buttons. Their position is saved.

The buttons hide while Home HQ is active and return when you leave it. Android
keeps the service enabled across reboots. It requests no accessibility events or
screen-content access and does not require root. Disable **Home HQ navigation**
in Accessibility settings to remove the buttons.

On a PF1007L (`20260519` firmware), the vendor `BackgroundManagerService` dropped the
service from the enabled list after every `adb install -r` or force stop of Home HQ, so the
buttons silently disappeared. To have Home HQ put the service back each time it starts, grant
it this permission once:

```sh
adb shell pm grant com.wesbos.homehq android.permission.WRITE_SECURE_SETTINGS
```

With the grant, Home HQ also rebinds the service if it is still listed but not running, which is
what Android 6 leaves behind when Home HQ's process is killed. If the buttons keep disappearing
whenever you leave Home HQ, the firmware may be killing every app you switch away from; see
[the Denver PFF-1015 notes](../../docs/denver-pff-1015.md#low-ram-mode-kills-every-app-you-leave).

The grant survives updates. To turn the buttons off for good, revoke it first
(`pm revoke` with the same arguments), then disable the service in Accessibility settings.

January `20260113` and May `20260529` firmware were also observed keeping a navigation service in
the selected list but resetting `accessibility_enabled` to `0` after boot. On `20260529` (#234)
the buttons came back on every boot once Home HQ was the Home app (see [Start at boot](#start-at-boot)). With the same optional grant,
Home HQ repairs either state when it starts, without rewriting an already selected list.
This reset was measured with a separate navigation app; the Home HQ change has host regression
coverage but has not been installed on that unit. See the
[January report](../../docs/allwinner-a33-pf1007l.md#9-january-unit-remote-management-and-background-services).

Keep an ADB connection available while enabling the service on a frame with no
other way back. If needed, return to the kiosk with:

```sh
adb shell am start -n com.wesbos.homehq/.MainActivity
```

This service supplies navigation controls only. To start the dashboard at boot,
make Home HQ the default Home app (see [Start at boot](#start-at-boot)).

To build your own dashboard for a PF1007L frame, see
[building-for-the-frame.md](../../docs/building-for-the-frame.md): what WebView 106 supports,
what to avoid, and how to test on the frame.

## When the dashboard can't load

If the dashboard fails to load, Home HQ covers WebView's error page with its own
screen. The error page would print the full URL, including any token in it.

- **No Wi-Fi:** "Connect to Wi-Fi?" with an **Open Wi-Fi settings** button.
- **Wi-Fi is up but the dashboard is unreachable:** "Can't reach the dashboard".
- **Wi-Fi has a sign-in page** (a captive portal, as on school, hotel and guest networks): the
  kiosk checks `http://connectivitycheck.gstatic.com/generate_204` the way Android does. A redirect
  or a page instead of the empty 204 means a portal, and the kiosk opens its page with a bar above
  it, so the terms can be accepted on the frame. It checks again every 5 seconds and returns to the
  dashboard once the frame is online. After 10 minutes it goes back to retrying the dashboard. **Cancel** closes the page; the offline screen then offers **Sign in to Wi-Fi**
  until the frame joins a network again. Frames with SystemUI disabled never see Android's own
  "Sign in to network" notification, so this is the only way to reach the page.

- **Certificate error:** never bypassed. If the error is about the date, the screen says
  "Setting the clock…". Frames with no clock battery start with an old date after a power cut
  (a Runxion SSA ZN-DP1002 came up on May 14, 2021), so every HTTPS certificate fails until
  network time arrives, about 20 seconds after Wi-Fi joins.

Home HQ keeps retrying every 5 seconds, and retries at once when Wi-Fi connects or the clock
changes. The screen disappears once a load succeeds. Wi-Fi settings open only when tapped,
because Wi-Fi is often still connecting for the first minute after boot.

On frames without a navigation bar (most PF1007L units), set up the navigation service in
[Frames without Home or Back buttons](#frames-without-home-or-back-buttons) first. Otherwise
**Open Wi-Fi settings** leaves no way back to the dashboard.

## Networks without internet access

A frame on a LAN-only network (an isolated VLAN that reaches only the dashboard server) needs two
settings. Without them it can't rejoin the network on its own, and its clock drifts.

- **Stay joined.** Android checks each Wi-Fi network for internet access. On a Skylight 150-CAL
  (Android 12), a network that failed the check was marked `NETWORK_SELECTION_DISABLED_NO_INTERNET_PERMANENT`
  in `adb shell dumpsys wifi`. After Wi-Fi was turned off and on, the frame didn't rejoin it
  (a reboot would leave it in the same state). This command turns the check off:

  ```sh
  adb shell settings put global captive_portal_mode 0
  ```

  Then join the network once by hand on the frame; that clears the flag. To undo:
  `adb shell settings delete global captive_portal_mode`. This turns off Android's sign-in-page
  detection everywhere. The kiosk's own check above still runs when the dashboard can't load.
  Alternatively, `captive_portal_http_url` and `captive_portal_https_url` can point at a LAN server
  that answers HTTP 204; that hasn't been tried on a frame.
- **Network time.** Android gets the time from `time.android.com`. Point it at an NTP server on the
  LAN that the frame's network is allowed to reach (UDP 123), and keep automatic time on:

  ```sh
  adb shell settings put global ntp_server <lan-ntp-server>
  adb shell settings put global auto_time 1
  ```

  Android only asks again when its last result is more than a day old; a reboot asks at once.

## Time zone

After changing the frame's time zone over ADB (`setprop persist.sys.timezone <zone>` and
`service call alarm 3 s16 <zone>` on Android 6; the transaction number differs on other versions), restart the kiosk. Until then the page keeps the old zone,
while `date` on the frame already shows the new one:

```sh
adb shell am force-stop com.wesbos.homehq
adb shell am start -n com.wesbos.homehq/.MainActivity
```

Seen on an Android 6 Runxion (WebView 107). Changing the zone in Android Settings has not been
compared.

## Build and install

Host-only navigation regression checks need Python 3 and a JDK on `PATH`:

```sh
python3 kiosk/test-navigation.py
```

Run from `dashboard/`. The test compiles the actual repair method with settings and
permission fakes; it does not prove service binding or reboot behavior on Android.

Use JDK 17, Android build-tools 34.0.0, and platform 34. On Ubuntu 24.04, the apt packages listed
at the top of `build.sh` install all three, with `ANDROID_HOME=/usr/lib/android-sdk`. From `dashboard/`:

```sh
ANDROID_HOME=/path/to/android-sdk bash kiosk/build.sh
adb install -r kiosk/build/homehq.apk
```

The kiosk loads the existing hosted dashboard over the frame's Wi-Fi. A USB
connection is only needed for installation or diagnostics, not normal use.

The kiosk targets Android 9 (SDK 28); the minimum is still Android 6 (SDK 23). Android 15
refuses to install targets below 24 (`INSTALL_FAILED_DEPRECATED_SDK_VERSION`), and Android 14
and later show a "built for an older version of Android" dialog on the first launch for targets
below 28.
