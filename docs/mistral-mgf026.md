# Mistral MGF026 15.6-inch Frameo frame

One 32 GB unit sold by [Bunnings Australia](https://www.bunnings.com.au/mistral-15-6-wi-fi-digital-photo-frame-with-frameo_p1109187) (item 1109187). Tested on Windows with Android SDK Platform-Tools 37.0.3. Home HQ opened at boot and rendered the hosted demo after Wi-Fi reconnected. Frameo was removed for Android user 0 after the kiosk boot test.

## Unit tested

| Observation | Value |
| --- | --- |
| Android model | `MGF026` |
| Firmware | `photo_Frameo_3676_V01_26052607` |
| Build fingerprint | `photo/photo/photo:10/QP1A.191105.004/20260526-075328:user/release-keys` |
| Platform and hardware | `ceres`, `sun50iw10p1`. The CPU property reports `QuadCore-A100`. The chip marking was not inspected. |
| Android | 10 (API 29), 32-bit ARM userspace (`armeabi-v7a`, `armeabi`) |
| WebView | `com.android.webview` 113.0.5672.136 |
| Display and memory | 1920×1080 (58 Hz reported), multitouch, about 1 GB RAM |
| Frameo | `net.frameo.frame` v1.32.18 (80340) after an app update. Built-in copy at `/system/priv-app/Manufacturer`. |
| USB | `1f3a:1007`, Windows MTP device `photo`, WinUSB bound to the ADB interface |
| Bootloader | `ro.boot.flash.locked=1`, verified boot `green` |

## USB and Wi-Fi ADB

Enable **Beta Program** and then **ADB Access** under Frameo **Settings → About**. With the frame on its power adapter, connect it using a **USB-A to USB-C data cable**, with USB-A at the PC and USB-C at the frame. This was the working connection on the tested unit. Windows detected both MTP and ADB. The initial 40 Gb/s USB-C cable setup produced no Windows USB device or ADB entry.

Use `adb devices` to check the connection. The default sandboxed Windows shell did not see the ADB transport even after Windows had bound WinUSB. Running ADB directly on the Windows host worked. The USB shell reported `uid=0` without a separate root command.

The frame answered a ping but refused TCP port 5555 before Wi-Fi ADB was enabled. After USB setup, Android's [USB-first Wi-Fi ADB method](https://developer.android.com/tools/adb#connect-to-a-device-over-wi-fi) worked on the same LAN. A shell over Wi-Fi returned `MGF026`. No persistent TCP port was configured, and survival across reboot was not tested. Keep root ADB on a trusted network. `adb -s <frame-ip>:5555 usb` switches the daemon back to USB mode.

## Home HQ as the launcher

1. Build and install the repo's [Home HQ kiosk APK](../dashboard/kiosk/README.md). The Windows build script worked with JDK 17 and Android SDK build tools 34. Open the kiosk with Frameo still installed and check that the demo renders.
2. On the panel, hold two fingers on the dashboard and tap **Android settings**. The owner confirmed Settings opened by touch. This gives you a way back if you change the default launcher.
3. The kiosk's optional boot receiver with Frameo left as Home did not work on the first restart. Frameo came back in the foreground and the kiosk's overlay permission had reset. The default Home method below worked.

   ```sh
   adb -d shell am start -n com.wesbos.homehq/.MainActivity --ez home true --ez boot false
   adb -d shell cmd package set-home-activity com.wesbos.homehq/.Home
   adb -d shell cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME
   ```

4. Check that the last command resolves to `com.wesbos.homehq/.Home`. Wait about 30 seconds for Android to save the change, then restart from the power menu or with `adb -d shell svc power reboot`. USB ADB returned and Home HQ was in the foreground. The kiosk showed a brief connection error during Wi-Fi startup, then loaded the demo automatically.

## Frameo removal and recovery

After confirming the kiosk boots and USB ADB survives a restart, the tested removal was:

```sh
adb -d shell pm uninstall -k --user 0 net.frameo.frame
```

This requests removal for user 0 with the keep-data option. Android still listed the system package among uninstalled packages. After another orderly restart, user 0 still reported `installed=false`, USB ADB was available, and the demo dashboard rendered in Home HQ.

The expected rollback is to register the built-in package for user 0 and select Frameo as Home again. Frameo's original Home activity was recorded before changing it. The rollback commands were not needed or tested on this unit.

```sh
adb -d shell cmd package install-existing --user 0 net.frameo.frame
adb -d shell cmd package set-home-activity net.frameo.frame/.ui.activities.AWaitForDeferredInitCompleted
```

## Hardware notes

Android exposes an accelerometer (`lis7a20`) and an ambient-light sensor (`light_resistance`). Its display configuration lists automatic brightness support. Android reports zero camera devices. Bluetooth, USB host accessories, and the physical microphone input were not tested. No firmware image, partition write, or Android upgrade was attempted.
