# Regular Android home screen

Installed the official Lawnchair15.0.0 Beta3.0 APK from the [project release](https://github.com/LawnchairLauncher/lawnchair/releases/tag/v15.0.0-beta3.0), after checking its published SHA-256 d4200d0985169fd79ba1bd225d653f2a2fe7b50aa07cb0d05ca64c7623f86059. Android accepted the installation. No ordinary launcher was previously installed: only Skylight and Settings FallbackHome resolved HOME.

Set app.lawnchair/.LawnchairLauncher as the default home activity and launched it. The resumed activity and HOME resolver both confirm Lawnchair. Skylight remains installed; no app data or firmware was removed. USB internet relay remains active.

To restore Skylight as the default home:

```sh
adb shell cmd package set-home-activity com.skylight/odesk.johnlife.skylight.activity.MainActivity
adb shell input keyevent KEYCODE_HOME
```

Lawnchair can subsequently be removed with adb uninstall app.lawnchair if no longer wanted. APK/provenance are kept privately under diagnostics/tools/lawnchair/.
