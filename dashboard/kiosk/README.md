# Home HQ kiosk navigation

Hold two fingers still on the dashboard for 1.5 seconds to open the native controls:

- **Open launcher** opens another installed Home app, such as Rootless Launcher.
  If none is available, it opens Android Settings.
- **Android settings** opens the device's Settings app.
- **Wi-Fi settings** opens Android's Wi-Fi list directly.
- **Reload dashboard** reloads the current URL.
- **Screen and screensaver** chooses whether Home HQ keeps the screen awake.
- **Back to dashboard** dismisses the controls.

## Screen and screensaver

Home HQ keeps the screen awake by default, preserving the existing wall-dashboard
behavior. To let Android start its native screensaver while the dashboard is open,
hold two fingers for the controls, choose **Screen and screensaver**, then
**Allow Android sleep and screensaver**. The preference is saved across launches
and applies to both the system-WebView and Gecko variants. It changes only Home HQ's
window flag, not Android's global display or screensaver settings.

The same saved setting can be configured remotely. First open the app, then send
the setting to the running activity:

```sh
adb shell am start -n com.wesbos.homehq/.MainActivity
adb shell am start -n com.wesbos.homehq/.MainActivity --ez keep_awake false
```

Use `--ez keep_awake true` or **Keep dashboard screen awake** to undo.
Only a new intent delivered to the running activity updates this preference;
cold launches read the saved policy and ignore launch extras, so Android replaying
an old launch intent after process death cannot overwrite a later choice.
Android must also have a finite display timeout and an enabled/configured screensaver
with appropriate charging or dock conditions. A device configured to never sleep
will not start a screensaver automatically just because this flag is cleared.
Home HQ does not change those global settings or force a screensaver to start.

Host policy regressions: `python3 kiosk/test-screen-awake.py` from `dashboard/`.

## Dashboard URL

The kiosk opens the hosted demo dashboard by default. To show your own, save its URL once:

```sh
adb shell am start -n com.wesbos.homehq/.MainActivity --es url https://your-dashboard/
```

`scripts/set-kiosk-url.sh <url>` from the repository root does the same, and prints the saved
URL when run without one.

Every later launch, including after a reboot, opens the saved URL. Links that other apps open
in the kiosk, such as a sign-in page, are shown but not saved.

## Start at boot

To have the frame boot into the dashboard, make the kiosk its Home app. Installing the kiosk
does not offer it as a Home app, so nothing changes until you run:

```sh
adb shell am start -n com.wesbos.homehq/.MainActivity --ez home true
adb shell cmd package set-home-activity com.wesbos.homehq/.Home
```

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

The dashboard is laid out for 1280×800 at density 160. Most 1280×800 frames ship at 160, but a VESWWE
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

### Photo screensaver integration

The buttons also hide while **iPhoto Frame Saver** is actively dreaming, and return
when its screensaver exits. This does not disable the accessibility service or change
the launcher, and the buttons remain available in the photo app's settings.

Home HQ observes the read-only
`content://io.github.martinwoodward.iphotoframesaver.playback/dream` provider, requesting
only its integer `active` column (`1` while dreaming, otherwise `0`). The provider
must belong to `io.github.martinwoodward.iphotoframesaver`. No album URLs, photos,
settings, or screen contents are read. Provider notifications update visibility;
a five-second recheck recovers from a stopped provider or missed notification.
Queries run off the UI thread. Missing, invalid, denied, or unresponsive state
keeps navigation available, including a two-second query timeout.

The screensaver must reset its process-local flag on stop/detach and notify this
URI on each transition. Process restart defaults to inactive. Home HQ does not
accept exported hide/show broadcasts or write to the provider.

Removing iPhoto Frame Saver restores the original visibility behavior; to undo the
Home HQ code change itself, reinstall your previous Home HQ APK with the same signing key.

Run the host integration regressions from `dashboard/` with
`python3 kiosk/test-dream-navigation.py`.

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

January `20260113` firmware was also observed keeping a navigation service in the selected
list but resetting `accessibility_enabled` to `0` after boot. With the same optional grant,
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

Home HQ keeps retrying every 5 seconds, and the screen disappears once a load
succeeds. Wi-Fi settings open only when tapped, because Wi-Fi is often still
connecting for the first minute after boot.

On frames without a navigation bar (most PF1007L units), set up the navigation service in
[Frames without Home or Back buttons](#frames-without-home-or-back-buttons) first. Otherwise
**Open Wi-Fi settings** leaves no way back to the dashboard.

## Build and install

Host-only navigation regression checks need Python 3 and a JDK on `PATH`:

```sh
python3 kiosk/test-navigation.py
```

Run from `dashboard/`. The test compiles the actual repair method with settings and
permission fakes; it does not prove service binding or reboot behavior on Android.

Use JDK 17, Android build-tools 34.0.0, and platform 34. From `dashboard/`:

```sh
ANDROID_HOME=/path/to/android-sdk bash kiosk/build.sh
adb install -r kiosk/build/homehq.apk
```

The kiosk loads the existing hosted dashboard over the frame's Wi-Fi. A USB
connection is only needed for installation or diagnostics, not normal use.
