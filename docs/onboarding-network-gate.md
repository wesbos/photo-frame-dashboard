# Wi-Fi onboarding gate despite working USB internet

The gnirehtet tunnel provides verified external HTTP access. The factory Skylight app nevertheless remains on Wi-Fi onboarding.

The reason is concrete in the reviewed factory APK: WifiConnectionStatusRepo requests a NetworkRequest with INTERNET capability and transport type1 (Wi-Fi). Its initial state also requires a valid WifiManager network ID. The working VPN transport does not satisfy that request. WifiFacade.isConnectedToNetwork reads the app's own Wi-Fi status objects rather than accepting arbitrary working internet access. ActivationViewModel.v2 sends a disconnected result back to the Wi-Fi step.

Once the app considers itself connected, it checks a persisted activation-update flag. If unchecked, it invokes statusReportAndInstallApks before showing activation-code entry. That path fetches backend-selected Skylight/watchdog APK updates; full Android firmware is a separate question. See app-updates.md for the detailed update analysis when available.

No built-in skip-Wi-Fi action or exported activation-step deep link was found in the inspected activation/manufacturer-menu code. This is a scoped finding, not proof that no other route exists.

Changing the network request to accept the USB VPN is technically plausible as an app modification. A normal modified APK update is blocked by signing: the installed app uses a Skylight-specific signer and shared android.uid.system. Its certificate and public key do not match the official AOSP platform/test certificates. Root/system modification or an official signed update would be needed for those approaches; a separate app experiment is described below. No firmware write was performed.

An official newer signed APK installed through ADB is a potential alternative worth assessing. No compatible newer APK has been downloaded or installed yet, and no claim is made that it removes the Wi-Fi requirement. The original factory app remains installed and USB internet sharing remains active.

## Successful separate-app bypass (2026-09-14)

Built and installed **Skylight USB Test**, package `com.skylight.usbtest`, alongside the factory app. With gnirehtet USB internet active, the UI reached **Enter your activation code**. The owner subsequently confirmed successful activation and adding the display in the mobile app. Full calendar operation remains under observation.

The guarded `scripts/prepare-usb-skylight-copy.py` copies an Apktool-decoded factory APK and changes seven reviewed files. It registers a default-network callback instead of requesting Wi-Fi specifically. Real internet checking remains enabled. The copy removes the system shared UID, has separate provider authorities and its own signature permission, and disables activation APK updates, watchdog actions, and root terminal commands. Implementation class names remain unchanged. The original system app remains installed; no firmware was flashed.

The source APK SHA-256 is `af529b5fee62e944e571d3556b606ebcc860fa384bee3e0abd190ef342cf854f`. Tools: official Apktool 3.0.3, Android build-tools 34 zipalign/apksigner. The locally signed APK SHA-256 is `9cac0a74b5974629ea931063eb54a760d89377266430c44438e1024baec17c71`. Signature verification passed v1/v2/v3. The installed copy runs as an ordinary app UID. Signing keys, APKs, decoded vendor assets and raw logs remain in ignored diagnostics, not public source.

Open the experimental app:

```sh
adb shell am start -n com.skylight.usbtest/odesk.johnlife.skylight.activity.MainActivity
```

Return to Lawnchair:

```sh
adb shell input keyevent KEYCODE_HOME
```

Remove only the experimental copy (also removes its own activation/data):

```sh
adb uninstall com.skylight.usbtest
```

Remaining limits: genuine owner activation is still required; the owner confirmed server acceptance and activation of this separately signed copy. Privileged hardware features may fail under an ordinary app UID. Automatic updates were intentionally disabled in this copy. USB internet depends on the Mac relay and Android VPN remaining connected. This does not repair the native Wi-Fi hardware/driver.
