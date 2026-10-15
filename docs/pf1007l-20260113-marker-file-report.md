# PF1007L / January 20260113: microSD marker-file entry and root USB ADB

One owner-described PF1007, inspected from macOS on October 15, 2026. The firmware identifies it as **PF1007L / Allwinner A33 / Android 6.0.1**. This is a different device from the owner's PF1506/A133 reported in [#104](https://github.com/wesbos/photo-frame-dashboard/issues/104).

## Result

The owner confirmed that an **empty `license.properties` file on a FAT-formatted microSD** opened the manufacturer-tools route into the factory test app. A subsequent live USB inspection found working **root ADB**, without a boot patch, FEL payload, firmware flash, or Android upgrade performed in this session.

This is a newly tested entry route on this unit, not evidence that ADB was enabled out of the box. The owner confirmed switching the test-app debugging control from **“is closed” to “is open”** before obtaining access. The owner subsequently confirmed that USB ADB returned after a normal reboot with the microSD removed. This persistence check is owner-reported; the device profile and root identity were independently read over USB before that check.

## Device profile

| Field | Observed result |
| --- | --- |
| Purchase source | Owner purchased through [Amazon USA, ASIN B0GHR65YYX](https://www.amazon.com/dp/B0GHR65YYX); the listing alone does not identify the shipped board/firmware |
| Owner's model description | PF1007; rear label confirmed **PF1007**; retail brand not recorded |
| Firmware | `YHK.F-null-A33-1001-D1024-PF1007L-321-OS-AIMOR.0.20260113` |
| AiMOR | `6.0.78`, version code 78; `com.efercro.os.aimor` |
| Android | `6.0.1`, SDK 23 |
| Android model / brand / manufacturer | `AEEZO` / `AEEZO` / `YHK` |
| Product / device | `astar_m86_8723cs` / `astar-m86_8723cs` |
| Platform / hardware | `astar` / `sun8i`; firmware identifies Allwinner A33 |
| Build fingerprint | `AEEZO/astar_m86_8723cs/astar-m86_8723cs:6.0.1/MOB30R/20260113:eng/test-keys` |
| Build properties | `ro.build.type=user`, `ro.build.tags=test-keys`; recorded separately from the fingerprint's `eng` component |
| Kernel | `3.4.39` |
| ABI | `armeabi-v7a,armeabi` |
| RAM | `MemTotal: 1026980 kB`, approximately 1 GB |
| Display | 1280 x 800, density 160; physical diagonal not measured |
| eMMC | 30,777,344 sectors of 512 bytes = 15,758,000,128 bytes |
| Boot partition | `/dev/block/mmcblk0p6`; start sector 172032; length 65536 sectors / 33,554,432 bytes |
| Boot SHA-256, template range | `d71c313ddaa4693948acb20af7740ccb56c88bf9376746a47fce2d00c14fc6a4`; measured directly on this unit |
| USB VID:PID | **`1f3a:1002`**, read from the Mac USB registry while ADB worked |
| USB functions | `sys.usb.config=mass_storage,adb`; `persist.sys.usb.config=mass_storage,adb` |
| Debugging | `adb_enabled=1`; `ro.adb.secure=0`; `ro.debuggable=1` |
| Normal ADB identity | **`uid=0(root) gid=0(root)`**, without invoking `su` |
| Shipped root helper | `/system/xbin/su` exists; `su 0 id` also returned UID 0 |
| SELinux | `Disabled` |
| Stock WebView package | `com.android.webview`, version **44.0.2403.119**, version code 246011900, target SDK 23; active-provider service output was unavailable |
| Factory test app | `com.DeviceTest`, **YHKSign_20250303**, version code 121 |
| Disabled packages | `pm list packages -d` returned no entries |
| Network ADB | `service.adb.tcp.port` and `persist.adb.tcp.port` empty; listener/reachability not tested |
| Host | Apple-silicon Mac, macOS 26.6.2 |
| Physical ports | Owner confirms no USB-A socket; USB-C data connection confirmed. Remaining port/power inventory not recorded |
| Working cable | Owner confirms the same arrangement as their PF1506: Mac USB-C → USB-C-to-USB-A hub → USB-A-to-USB-C data cable → frame USB-C |

Sanitized ADB listing:

```text
<serial redacted> device usb:<host-path-redacted> product:astar_m86_8723cs model:AEEZO device:astar-m86_8723cs
```

## Confirmed microSD entry procedure

1. Use a normal FAT-formatted microSD card. The tested card was approximately 8 GB (7,989,100,544 bytes), with an `AIMOR` volume. The card was formatted by the owner before this test.
2. Place a **zero-byte file named `license.properties` at the volume root**. The host verified the file was empty and safely ejected the card.
3. Insert it while stock AiMOR is running. The manufacturer authorization/tools screen opens.
4. Tap the **top-left corner five times within 2.5 seconds** to open the factory test app without entering its password.
5. The owner confirmed this entry route worked. Subsequent host inspection independently confirmed root USB ADB.

The owner explicitly confirmed switching the test app's debugging control from **“is closed” to “is open”**. Subsequent host inspection confirmed working root USB ADB. There was no firmware patch in this access sequence.

An authorization-file error is expected from an empty file. Keep the file empty and avoid registration/logout controls. Static analysis of the separate PF1506's AiMOR APK found that the marker opens the manufacturer screen before license parsing and that the hidden tap target starts `com.DeviceTest.FirstRun`. The PF1007 result here is an owner-confirmed physical reproduction; this PF1007's own APK has not been decompiled in this session.

**USB flash-drive status:** the same owner confirmed both SD and USB marker-file entry on the separate PF1506. Only microSD has been confirmed on this PF1007, which the owner confirms has no USB-A socket. No USB flash-drive or OTG-adapter test was performed on this unit. Do not extend the PF1506 USB result to it.

## Reboot check

The owner confirmed the rear-label model is **PF1007** and that USB ADB returned after a normal reboot with the microSD removed. The firmware identifies the software/hardware variant as **PF1007L**; both names are retained to distinguish the label from the firmware identity. No FEL or SD boot payload was needed, and the marker card did not have to remain inserted. Root identity after that reboot was not separately remeasured by the agent.

## Boot hash and backup status

The actual boot partition is 65,536 sectors, while the shared January report template hashes only its first **31,028 sectors / 15,886,336 bytes**. Both lengths must be explicit when comparing hashes.

A read-only attempt to stream the full boot partition through `adb exec-out dd` returned only **93,184 bytes**, instead of 33,554,432. The host rejected that transfer; subsequent `adb devices -l` was empty. The connection returned on retry. Device-side BusyBox SHA-256 then completed successfully for both ranges:

| Measured range | SHA-256 |
| --- | --- |
| Full boot partition, 33,554,432 bytes | `835a62c73d3ad7ebfea12a03208fcd41e738c69c88caae1dd24148e76c9efd04` |
| First 31,028 sectors, 15,886,336 bytes | `d71c313ddaa4693948acb20af7740ccb56c88bf9376746a47fce2d00c14fc6a4` |

The template-range measurement matches the published January stock hash. These are actual checksums computed on this unit, not values copied from another report. However, a separate full-image USB stream returned only **53,248 bytes** and was also rejected. **No complete host-side boot image, independent host hash verification, or verified firmware backup is claimed.** The cause of the raw-transfer truncation/disconnection has not been established.

## Scope and remaining checks

- Rear label **PF1007**, debugging-toggle action, working cable/hub arrangement, and absence of a USB-A socket are owner-confirmed. Retail branding and remaining power/port inventory were not recorded.
- Resolve the incomplete USB binary transfers and obtain a verified firmware backup before considering firmware changes. Device-side boot hashes were captured on retry, as documented above.
- **USB ADB reboot persistence confirmed by the owner, with microSD removed.** The previously observed `persist.sys.usb.config=mass_storage,adb` is consistent with this result; no persistent property was written by the agent during inspection.
- No FEL, SD boot payload, boot patch, flash write, network recovery, network ADB enablement, dashboard install, or vendor-app disabling was performed in this inspection session.
- Root ADB is unauthenticated (`ro.adb.secure=0`). This report does not establish an authenticated remote-management configuration.
- No serial, Frame ID, MAC address, private network address, household credential, firmware dump, or personal screenshot is included.

## Report-your-unit summary

```text
About model / firmware: PF1007 rear label; firmware PF1007L / YHK.F-null-A33-1001-D1024-PF1007L-321-OS-AIMOR.0.20260113
AiMOR version: 6.0.78
Ports (DC jack, or USB-C only): USB-C data; no USB-A socket; remaining power/port inventory not recorded
Cable and port that gave USB data: Mac USB-C -> USB-A hub -> USB-A-to-USB-C data cable -> frame USB-C
T3 USB IDs seen / adb devices output: 1f3a:1002; device, product astar_m86_8723cs, model AEEZO
T3b network ADB result (port 5555): not tested; runtime and persistent TCP properties empty
T4 sunxi-fel version output: skipped; no FEL needed
T5 check-dump stage / chunks: skipped
eMMC size in sectors: 30777344
Boot partition start sector: 172032; actual partition length 65536 sectors
Boot image SHA-256 (sector 172032, 31028 sectors): d71c313ddaa4693948acb20af7740ccb56c88bf9376746a47fce2d00c14fc6a4
Route used and result: empty license.properties microSD -> manufacturer screen -> top-left five taps -> test app -> is closed to is open -> root USB ADB; owner confirmed ADB after reboot with card removed
Host OS: macOS 26.6.2, Apple silicon
First failed step: initial full boot stream returned 93184 of 33554432 bytes; rejected, USB subsequently disconnected. Device-side hashes completed after reconnect; host-side backup remains unverified.
```
