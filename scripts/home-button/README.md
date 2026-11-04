# Frame Home button

A small native Android app for frames with no usable Home button. Originally tested
on a VESWWE DP100 running Android 8.1; startup was also tested on one Benibela
JT101M-A02 running Android 10. Requires Android 8.0/API 26 or later.

It draws a draggable floating house above ordinary apps. A tap launches the
default HOME activity. It does not inject keys, use accessibility services,
invoke root, or request internet permission. A foreground service keeps the
button available; a boot receiver restores it and its saved position after reboot.
Open **Frame Home** from the launcher to show or hide the button.

## Build

Requires JDK 17 and Android SDK build-tools 34.0.0 plus platform android-34.
Set `JAVA_HOME` to the JDK. By default, the SDK is expected in
`diagnostics/android-sdk`; override with `FRAME_HOME_SDK`.

```sh
bash scripts/home-button/build.sh
```

Output defaults to ignored `diagnostics/home-button/frame-home.apk`, with its
signing key beside it. `FRAME_HOME_OUTPUT` overrides this location. Keep that
key private and preserve it for updates. Do not commit the key or built APK.
The build script only builds and verifies the APK; it never touches the frame.

## Install and enable

Identify the device, verify a backup and get the owner's approval before making
device changes, following the repository's rules.

```sh
adb -d install -r diagnostics/home-button/frame-home.apk
adb -d shell appops set com.photoframe.homebutton SYSTEM_ALERT_WINDOW allow
adb -d shell am start -n com.photoframe.homebutton/.HomeSettingsActivity
```

For updates, reuse the existing signing key; `-r` preserves the app's settings.
Tap **Show Home button**. The non-exported service starts through this UI.
Opening the app also clears its newly installed stopped state before the boot
receiver is needed. Check Home from another app and verify startup on the frame;
vendor builds can restrict boot broadcasts or service starts.

### Allwinner per-app Auto run control

On one Benibela JT101M-A02 (sold as JT101M-B02), stock Android 10 / API 29,
fingerprint `Allwinner/ceres_aw/ceres-aw:10/QP1A.191105.004/eng.joy.20220905.163444:eng/test-keys`,
`BOOT_COMPLETED` arrived but Allwinner's background manager refused the service.
The **Auto run** choice was saved, but its runtime list stayed empty after reboot
until the vendor settings app initialized. An Activity workaround was intermittent.

On this firmware:

1. Open **Auto run** (`com.softwinner.awmanager/.AwManager`) and allow only
   **Frame Home**. Leave service limits, other apps and global policy unchanged.
2. In **Frame Home**, opt into **Reload saved Allwinner Auto run settings at boot**,
   then tap **Show Home button**. Keep independent management access while testing.
3. Reboot and verify both the house and the frame's normal foreground app.

The opt-in is available only for the tested firmware and vendor APK SHA-256
`597068b508ff2dcc8f3a3f372354d74ce05b907cdbf6c3c2a786290476538869`.
After a refused service start, it initializes that app through an action its audited
receiver ignores; the app reloads its saved Auto run choices. It supplies no new
whitelist entries or registration data. The vendor initializer also reapplies its
saved service limit and GCM app list; review those choices before opting in. Those
values were unchanged on the tested unit. Startup retries are bounded,
and Hide or missing overlay permission cancels them. Other firmware or APKs keep
the normal service path; this is not a universal Allwinner fix.

Read-only diagnostics:

```sh
adb -d shell dumpsys background
adb -d shell dumpsys activity services com.photoframe.homebutton
adb -d logcat -d -s FrameHomeBoot
```

On the tested frame, `dumpsys background` showed `enableSkipService:true` and
an initially empty user whitelist. After the restore, the user list contained only
`com.photoframe.homebutton`; the original foreground service started without opening
an Activity. Missing opt-in, an unsupported vendor APK or a refused retry emits a warning.

| Check on the Benibela | Result |
| --- | --- |
| Auto run allowed + reload opted in, two normal reboots | Floating Home returned; saved position, Rootless HOME and photo startup persisted. |
| Hide and reboot | Button/service stayed off despite the reload opt-in. |
| Reload opt-in off and reboot | Service stayed off; the saved vendor choice alone did not restore its runtime list. |
| Auto run Disallowed + reload opted in, reboot | Service stayed off; the helper did not enroll itself. |
| Navigation | Screen taps returned from Settings → About, Settings → Apps, Photos and a native dashboard to Rootless. |

Cold power-loss startup and the original Android 8.1 frame were not re-tested.
The [PF1506 boot-animation failure (#118)](https://github.com/wesbos/photo-frame-dashboard/issues/118)
is a different, undiagnosed startup problem and is not covered by these tests.
This receiver cannot help a boot that never reaches `BOOT_COMPLETED`.

The overlay can cover a small portion of the app below it; drag it aside.
Android may hide overlays on sensitive system screens. It is a Home shortcut,
not a replacement for Back or Recents.

## Undo

Uncheck **Reload saved Allwinner Auto run settings at boot** to remove the restore step.
If changed, restore only Frame Home's **Auto run** setting to **Disallowed**.
Tap **Hide Home button** in Frame Home to hide it and disable boot startup, or
remove the app entirely:

```sh
adb -d uninstall com.photoframe.homebutton
```

Uninstalling removes its service, overlay permission and saved position. No
system APK or boot partition is modified.
