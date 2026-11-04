# Kodak RCF-1018W

Tested on one frame with an Apple-silicon Mac. Result: Home HQ at boot, working Wi-Fi/touch navigation, WebView 106, and persistent authorized USB ADB.

## Tested firmware

| Field | Value |
| --- | --- |
| Rear label / Android model | `RCF-1018W` / `RCF-1018` |
| Software / original Kodak app | `QY10V1.0.1` / `2.3.3` |
| Manufacturer / SoC | `incar` / Rockchip RK3126 |
| Android / ABI / RAM | 6.0.1 / `armeabi-v7a` / 1 GiB |
| Security patch | 2016-11-01 |
| Fingerprint | `rockchip/rk312x/rk312x:6.0.1/MXC89K/user.fyl.20170927.202757:userdebug/test-keys` |
| Display | 1280×800, density 160 |
| Original WebView | `com.android.webview` 44.0.2403.119 |
| Root / SELinux | `/system/xbin/su`, Permissive |

Match model and firmware before applying changes. Partition layout matches the [YIAISIGN 10X1](yiaisign-10x1.md#partition-layout); `biuframe-setup.sh` does not support this Kodak.

## 1. Get ADB

1. Repeatedly tap the **MAC-address row** in Kodak Settings to open the Android launcher.
2. In Android Settings → About tablet, tap **Build number** seven times. Enable USB debugging in Developer options.
3. Use a **USB-A to USB-C data cable**, with the frame's normal power connected. C-to-C did not enumerate on this unit.
4. If ADB reports `unauthorized` without a prompt, install [Kodak Recovery](../scripts/kodak-recovery/README.md) using ApkInstaller and a FAT32 microSD card. Unknown sources was already enabled on this unit.
5. Open Recovery → **Check root → Enable System UI**. System UI was installed but explicitly disabled; enabling it restores the authorization dialog.
6. Enable USB debugging, reconnect USB, and approve the computer. Select Always allow for the trusted Mac.

Verify:

```sh
adb shell getprop ro.product.model
adb shell getprop ro.build.fingerprint
adb shell su -c id
```

Root must report `uid=0`. Keep System UI enabled.

## 2. Back up

Follow the repository's [backup rules](../README.md#rules-we-learned-the-hard-way) before system-file changes. This unit's verified firmware backup ends at userdata: **2,846,720 sectors / 1,457,520,640 bytes**. Derive the boundary from the device, not this number alone.

Checks passed: exact byte count, stream/readback SHA-256, gzip readback, filler scan, and independent matching reads of uboot, boot, recovery, and a 16 MiB system-data sample. Original system files and package state were saved separately.

The backup excludes userdata, including photos and most app data. It is a partial firmware backup
and does not meet the full-device backup rule. Offline restoration remains untested. Keep dumps private.

## 3. WebView replacement record

**Record, not a procedure.** The following system-file changes were performed manually on one
unit. No guarded Kodak WebView or low-memory writer is supplied by this repository.

The owner used ARMv7 standalone **106.0.5249.126**:

- [Pinned LineageOS APK](https://raw.githubusercontent.com/LineageOS/android_external_chromium-webview_prebuilt_arm/4b0ae494a7dd/webview.apk)
- SHA-256: `e2edc1f89ec1608b169da9e7ffc037190b70c7825f0be29694f4cae719980580`

Its signing certificate differs from stock. The original `/system/app/webview/webview.apk` was
kept as `webview.apk.bak`. The replacement APK and its three `lib/armeabi-v7a` libraries were
placed in the WebView tree (`lib/arm/` on the frame), with root ownership, files 0644,
directories 0755 and `system_file` labels. Generated `oat` was removed. File hashes were checked
by independent readback and `/system` returned to read-only before reboot. Logcat then reported
`WebViewFactory: Loading com.android.webview version 106.0.5249.126`.

See the [native-library explanation](biuframe-setup-guide.md#why-the-non-obvious-parts-are-needed).
SuperSU may remount concurrently. ISRG Root X1/X2 were already correct; no certificate changes
were required.

A reusable writer must compare the current files to the verified stock backup, verify each
incoming payload on the frame before writing, read back the result and return `/system` to
read-only on failure. An APK-only `.bak` is not a complete undo: preserve the entire original
WebView tree, including any libraries, `oat`, owners, modes and labels, before replacement.
Complete tree restoration was not tested on this unit.

## 4. Low-memory and navigation findings

With `ro.config.low_ram=true`, this firmware kills non-exempt apps when switching tasks. Logs
showed Home HQ killed immediately after `onPause` with `user request after error`, taking its
navigation service down too.

The owner saved `/system/etc/lowmem_package_filter.xml` as `.bak`, then added Home HQ to the
`prev` and `empty` sections while preserving other entries. The file had root ownership, mode
0644 and its SELinux label restored; XML readback was checked, `/system` returned read-only,
and the frame rebooted. See [Rockchip low-memory behavior](denver-pff-1015.md#low-ram-mode-kills-every-app-you-leave).
This is part of the manual record, not a supported edit/undo script. A guarded implementation
would need the same before/after checks as the WebView replacement.

Enable **Settings → Accessibility → Home HQ navigation**. Check on the panel that Home HQ
reaches **Settings → Apps** and returns using **Dashboard** before disabling Kodak. This unit
did not need `WRITE_SECURE_SETTINGS`.

## 5. Set startup and disable optional apps

Install [Home HQ](../dashboard/kiosk/README.md), then enable its Menu and Home alias:

```sh
adb shell am start -n com.wesbos.homehq/.MainActivity --ez menu_button true --ez home true
```

Disabled packages, with original APKs/data retained:

| Package | Purpose |
| --- | --- |
| `com.cloudhearing.digital.kodakframe.android` | Kodak photo app |
| `com.dtinfo.tools` | Updater |
| `com.DeviceTest` | Factory tests |
| `com.qg.licensecode` | License verification |
| `android.rk.RockVideoPlayer` | Video player |
| `com.android.phasebeam` | Live wallpaper |
| `com.android.noisefield` | Live wallpaper |
| `com.android.wallpaper.livepicker` | Live wallpaper picker |

Disable each approved package using `adb shell "su -c 'pm disable PACKAGE'"`; force-stop it if needed. Verify saved `enabled=2` state. Keep System UI, Settings, Launcher3, the keyboard, and installers available.

Open the Home chooser, then select **Home HQ → Always**:

```sh
adb shell am start -a android.intent.action.MAIN -c android.intent.category.HOME
```

Wait 15–30 seconds and verify the preferred Home, enabled alias, and package states in `/data/system/users/0/package-restrictions.xml` before rebooting.

## Verify and recover

Verified after the final reboot: automatic dashboard startup, Wi-Fi, Settings/navigation, authorized USB ADB, and all eight disabled apps absent from running processes. Allow about one minute for ADB to reconnect.

- Restore an app: root `pm enable PACKAGE`.
- Change Home: select Launcher3 in Settings → Home before disabling Home HQ's Home alias with `--ez home false`.
- System-file undo was not tested. A restoration must first match the current modified files
  to the expected state, then restore the complete original WebView tree or low-memory XML
  from a verified backup, including metadata. Remove only verified replacement-only files.
  Verify payloads before writing and read back afterward, with `/system` returned read-only.
  Do not infer complete WebView recovery from an APK-only `.bak`.

## Change the dashboard or app

For another webpage:

```sh
adb shell am start -n com.wesbos.homehq/.MainActivity --es url https://your-dashboard.example/
```

For another APK: install/test it first, choose it under Settings → Home if it supports Home, and retain the working launcher/ADB until recovery is proven. It must support Android 6/API 23 and ARMv7 if it has native code. Add its package to the low-memory exceptions if task switching kills it.

## Security

This remains vendor Android 6 with an obsolete WebView, Permissive SELinux, and root accessible to ordinary apps. Disabled apps are not a complete firmware audit. Use an isolated network, restrict outbound traffic, and avoid sensitive account logins. USB ADB was retained; no port-5555 listener was observed. The hosted dashboard contains demo data until you deploy/configure your own.
