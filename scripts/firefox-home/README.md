# Firefox Home: open a Firefox web app at boot

A small Home app for frames whose firmware blocks the usual ways to start something at boot,
and where WebView can't be used. Tested on one Sandstrom SDPFHD10W25 (Allwinner A133,
Android 12, Firefox 158.0.2). See [sandstrom-sdpfhd10w25.md](../../docs/sandstrom-sdpfhd10w25.md).

Why a Home app: the Allwinner `BackgroundManagerService` on several frames drops
`BOOT_COMPLETED` and background services for packages outside a built-in whitelist
([QOCEN J1008](../../docs/qocen-j1008.md#the-firmware-blocks-every-normal-way-to-start-something-at-boot)).
Android always starts the default Home activity, so that is the one route left. This app starts
no service, has no boot receiver, asks for no root and has no internet permission.

What it does:

- Waits for a network connection (up to 2 minutes), counts down 10 s, then opens the dashboard.
- During the countdown it shows **Open dashboard now**, **Android settings**, **Wi-Fi settings**
  and **Firefox**. Tapping any of them stops the countdown. This is the way back on frames with
  no navigation bar.
- If Firefox closes or crashes, Android returns to Home and the countdown starts again.
- It accepts Firefox pinned shortcuts (`CONFIRM_PIN_SHORTCUT`) after on-screen confirmation. Firefox only offers **Add app to Home
  screen** when the default Home app can pin shortcuts. The pinned web-app shortcut is what the
  app launches, so the site opens with no toolbar (`ExternalAppBrowserActivity`).
- Without a pinned shortcut it falls back to `VIEW_PWA` (https only), then a normal Firefox tab.

## Build

Requires JDK 17 and Android SDK build-tools 34.0.0 plus platform android-34. By default the SDK
is expected in `diagnostics/android-sdk`; override with `FIREFOX_HOME_SDK`. Works in Git Bash on
Windows (no `zip` needed).

```sh
JAVA_HOME=/path/to/jdk-17 bash scripts/firefox-home/build.sh
```

Output goes to the ignored `diagnostics/firefox-home/firefox-home.apk`, with its signing key
beside it. Keep the key to install updates over the top. The script never touches a frame.

## Test URL handling

With Python 3 and JDK 17 (`java` and `javac` on `PATH`), run from the repository root:

```sh
python3 scripts/firefox-home/test-url-policy.py
```

This checks the actual URL policy and saved URL/pin transitions against small host fakes.
It needs no Android SDK, network or frame, and removes its temporary compiled output.
It does not test Firefox launches or the on-screen shortcut confirmation.

## Install and set up

Follow the repository's rules first: identify the device, verify a backup and get the owner's
approval before changing it.

```sh
adb install diagnostics/firefox-home/firefox-home.apk
adb shell cmd package set-home-activity com.photoframe.firefoxhome/.HomeActivity
adb shell am start -n com.photoframe.firefoxhome/.HomeActivity --es url https://dashboard.example/
```

Then open the dashboard in Firefox, log in, and use **⋮ → More → Add app to Home screen**. A
confirmation asks whether to replace the dashboard, then a toast confirms it was saved. A dashboard served over plain `http` can't be a Firefox web
app; it opens in a normal tab with the toolbar.

Only `http` and `https` URLs with a host are accepted. Invalid values leave the saved URL
unchanged. Setting a different URL clears the old pinned shortcut.

## Undo

Before uninstalling, re-enable and select a known working replacement Home app. On the tested
Sandstrom that was Frameo (`net.frameo.frame/.ui.activities.AWaitForDeferredInitCompleted`).
Confirm Home opens it and that you can still reach Android Settings physically; keep USB ADB
connected while checking. Do not rely on `com.android.settings/.FallbackHome`, which is not a
usable launcher. Only then uninstall:

```sh
adb uninstall com.photoframe.firefoxhome
```
