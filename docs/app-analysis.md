# Skylight factory application analysis

Offline inspection of the factory `system_ext` privileged APK on 2026-09-14. The original extraction was provisional; its source `super` partition has since been byte-compared against the validated full backup and matches exactly. The factory APK analysis therefore uses verified backup contents. Live package-path inspection now resolves `com.skylight` to `/system_ext/priv-app/Skylight/Skylight.apk`, rather than a `/data/app` update.

Factory APK identity:

- Package: `com.skylight`
- Version: `9.29.3`, code `9325`
- Shared UID: `android.uid.system`
- SHA-256: `af529b5fee62e944e571d3556b606ebcc860fa384bee3e0abd190ef342cf854f`

JADX completed with 64 errors elsewhere in the APK. The focused classes below were readable, but decompilation is an interpretation of bytecode rather than the original Kotlin source. Full decompiled code, third-party libraries and embedded constants stay under ignored `diagnostics/app-analysis/`.

## A real onboarding development menu

The activation screen includes an invisible **200 dp square at the upper-left corner**. Ordinary taps increment a counter. At exactly five taps, the manufacturer-code dialog is shown. A long press resets that counter to zero. The touch target exists in the reviewed release build; the debug-build flag only controls whether its bounds are visibly drawn.

The code-entry handler compares against an embedded four-digit value, then emits an event which opens a **Dev Tools** drawer. The entry code is retained in local analysis notes and omitted from this public document. This route has now been exercised successfully: ADB and native settings are accessible. ADB supplies an Android shell with UID 2000, not root access.

The drawer offers:

| Control | Reviewed implementation |
| --- | --- |
| Enable ADB | Writes `Settings.Global.adb_enabled`, reads the result back, and updates the UI state; catches and logs failures. |
| Open native settings | Starts `android.settings.SETTINGS`. |
| Release logging | Changes the application's logging setting and resets its watchdog service. |
| Environment switching | Separate development action with reset implications; unnecessary for diagnostic access. |

The ADB control does not directly flash an image or invoke a bootloader operation. Enabling ADB is a persistent Android setting, not a RAM-only change. USB debugging may still require host authorization after the interface appears.

Local code references, relative to `diagnostics/app-analysis/sources/`:

- `Ub/C4248b.java`: activation layout and native-settings event handler.
- `Xb/C4595j.java`: invisible square, top-left alignment, click/long-click wiring.
- `Q8/a.java`: ordinary tap increments the counter; `Pb/e.java`: long press resets it.
- `Xb/C4586a.java`, `Xb/C4587b.java`: counter, threshold and manufacturer-code check.
- `Ub/C4256j.java`, `Wb/g.java`: successful entry opens Dev Tools.
- `Wb/f.java`: drawer actions.
- `ud/C4268a.java`: `Settings.Global` ADB getter/setter.

JADX preserves Java package names but renames some filenames for the Mac's case-insensitive filesystem; the paths above use the generated local names.

## What the empty Wi-Fi list does and does not establish

`NetworkScanRepo.scanForNetworks()` registers for the scan-results broadcast and calls `WifiManager.startScan()`. It logs the boolean return, but then immediately emits an error response containing the current cached results, regardless of that boolean. When a broadcast arrives, the receiver unregisters itself and emits success containing `getScanResults()`. It does not inspect the broadcast's `EXTRA_RESULTS_UPDATED` flag.

The activation Wi-Fi UI consumes both success and error responses as lists. This can explain why an empty list appears without a useful error message when scan initiation fails or only stale results are available. It does **not** prove that this is the cause of the radio problem: logs and an independent Android scan are still needed. No automatic periodic scan retry was found among the reviewed call sites; entering/showing Wi-Fi and explicit reset/forget actions trigger scans.

`WifiFacade.convertScanResultList()` removes blank SSIDs and permits capability strings containing WPA, WEP, RSN or ESS, or an empty capability string. It sorts by signal strength and removes duplicate SSIDs. No 2.4-GHz-only filter was found in this conversion.

`WifiConnectionStatusRepo` attempts to enable Wi-Fi if disabled. The activation startup invokes a permission-granting helper. Their presence is not proof of successful grants or a healthy driver; actual permission and Wi-Fi service state should be inspected once access is available.

### The information-icon diagnostic is weak

`TerminalUtil.getMacAddressForWlan0()` obtains the address from Java's live network-interface enumeration, falling back to the output of `ip address`. It does not use a saved Wi-Fi address field in the reviewed implementation. The observed address therefore supports that a `wlan0` interface existed at that point, subject to confirmation that this factory APK was running. It does not prove that scans or RF reception work.

`isWifiModuleFunctional()` runs `wpa_cli list_networks` and only declares failure if trimmed stdout or stderr equals `bad mode`, case-insensitively. It otherwise returns true, including when the command helper returns no result. Absence of a bad-module warning is not meaningful hardware validation.

The older `WifiListFragment` contains a three-long-press action on its forget control that clears Wi-Fi files and reboots. The modern activation screen uses a different Compose implementation. Do not recommend that destructive legacy gesture as an onboarding repair merely because its code remains in the APK.

## Next verification

The verified backup also contains a historical recovery kernel log. It identifies the running board as `Rockchip RK3566 g10 Board`, parses `wifi_chip_type = ssv6x5x`, and records an SDR104 SDIO card enumerating on `mmc1`. The device clock was set to 2026-02-27 during that boot. This establishes historical configuration and SDIO enumeration. Subsequent live ADB logs show Broadcom hardware using AP6256 firmware despite the DTB label, with scan-aborted events at Android wificond. The captured failure therefore reaches below application list rendering; the actual abort cause remains unresolved. See [hardware research](hardware-research.md).

The package path and manufacturer-menu access are now verified live. Native Android scan-aborted events reproduce the lower-level failure. Further work should capture the driver's precise abort reason or run a controlled privileged scan before attributing the fault to an antenna, module or firmware bug.


## Signing identity and an app-only replacement

The verified factory APK contains the same Skylight certificate in its v1 PKCS#7 record and v2/v3 signing-block certificate records. Its certificate SHA-256 is `5771f682d75c2d13217dc2d7a8dc3e23b29d94197153542b523676faa8f4d1f4`; its public-key SPKI SHA-256 is `05008eba049af188ecbacd6dc2634c5a7680f715b912c2656c00fd298fadbc66`.

Neither the certificate nor its public key matches the official AOSP [platform certificate](https://android.googlesource.com/platform/build/+/refs/heads/main/target/product/security/platform.x509.pem) or [testkey certificate](https://android.googlesource.com/platform/build/+/refs/heads/main/target/product/security/testkey.x509.pem). Comparing public keys also rules out the simple possibility of a renamed certificate reusing either stock AOSP key.

Consequently, an ordinary modified APK update signed with those AOSP keys would not preserve the installed signing identity. The factory application's `android.uid.system` shared UID also requires signing compatibility; changing the package name alone would not preserve its system privileges. This rules out a straightforward same-package app-only patch using those two test keys. It does not assess every possible manufacturer key, authorized signing lineage, or alternate unprivileged application design. No APK was modified or installed, and only public X.509 certificates were downloaded. Certificate extraction is identity comparison, not a full independent APK signature verification.
