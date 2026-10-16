# PF1006 V43 / ZM789_MB_V4.3: root USB ADB and Home HQ

Tested on one owner-operated frame on 2026-10-16, from an Intel Mac mini running
Linux. The existing Android installation was retained, with the boot and WebView
changes described below. The owner confirmed that the hosted
Home HQ demo opens after a cold boot using only the original power adapter, with
USB disconnected and the microSD removed.

This is a unit report, not a universal PF1006 flashing recipe. Related
[PR #142](https://github.com/wesbos/photo-frame-dashboard/pull/142) describes an
unconfirmed PF1006 with different firmware ending `46-DL-OS-AM.0.20240910`.
Its experimental SD diagnostic was not the route tested here.

## Identity and initial access

| Item | Observed value |
| --- | --- |
| Board silkscreen | `ZM789_MB_V4.3` |
| Firmware | `YHK.F-aizuo-A33-1001-D1024-PF1006-V43-29.0.20240423` |
| Android / vendor app | Android 6.0.1 / AiMOR 3.2.76 |
| Android device | `astar-m86_8723cs` |
| SoC | Allwinner A33, confirmed by FEL version query |
| Display | 1280 × 800, density 160 |
| Exposed eMMC user area | 15,758,000,128 bytes; stock UI capacity differed |
| Stock USB | `1f3a:1000`, mass storage with empty LUNs; no ADB |
| Stock WebView | 44.0.2403.119 |

USB-C-to-C did not produce a working data connection in this setup; USB-A-to-C
did. A USB-C socket was found on the frame. The factory test app was accessible,
but no ADB control was found. Stock TCP port 5555 refused connection.

## Backup and boot change

An 8 KiB FEL stub in a microSD card's boot gap entered `1f3a:efe8` without finding
a reset button. The card boot area was backed up before modification. The general
approach is documented in [the A33 mainline U-Boot notes](allwinner-a33-mainline-uboot.md).
Local loaders and the guarded writer were prepared for this unit; their binaries
and private firmware dumps are not included in this report.

A RAM-loaded U-Boot exposed eMMC through read-only USB mass storage. The successful
backup setup used a 4-bit, 12 MHz eMMC configuration, no PMIC programming and a
408 MHz CPU setting. These settings are observations from this unit, not evidence
of compatibility with other PF1006 boards.

The complete user area was backed up with two matching device reads per segment,
image readback, filler checks, SHA-256 and gzip readback verification. The original
boot image and a restore plan were preserved before the owner-approved write.

The original boot image SHA-256 was
`5941ee9f923c395e9ecd121f09a0761749d371603d15b634e378725d8f67be0f`.
Stock properties already had `ro.secure=0` and `ro.debuggable=1`.
`/system/build.prop` selected `persist.sys.usb.config=mass_storage`, with no saved
userdata override found in this backup.

The only logical ramdisk file change was to the existing
`sys.usb.config=mass_storage` action in `init.sun8i.usb.rc`: expose
`mass_storage,adb`, use USB PID `1002`, and start `adbd`. The kernel was unchanged.
The guarded writer updated the ramdisk slot and boot header, then the entire
user area was read and compared against the original backup plus exactly that
patch, before attempting Android boot. USB subsequently enumerated as
`1f3a:1002`; `adb shell id` reported `uid=0(root)`, and Android completed boot.
Root USB ADB was also confirmed after the later WebView restart.

One loader build pitfall: disabling fastboot removed the implicit Kconfig
selection of `USB_GADGET_DOWNLOAD`, which in turn removed
`CMD_USB_MASS_STORAGE` from the effective configuration. Explicitly selecting
`USB_GADGET_DOWNLOAD` restored the intended UMS build. Check effective `.config`
and executable symbols, not only the requested defconfig.

## Power sequencing

Initial USB-connected startup attempts showed a blank panel. After disconnecting
all power, leaving the microSD out, and starting on the original adapter alone,
the owner saw the boot artwork and AiMOR. Reconnecting USB then exposed root ADB.
No boot restoration was needed. The precise cause of the initial blank screen
was not established; this is not proof of a specific USB-C electrical fault.

## Kiosk result

Installed Rootless Launcher 3.9.1, repository Home HQ 1.1 and the pinned ARM
WebView 106.0.5249.126 from [the existing WebView procedure](allwinner-a33-pf1007l.md#6-upgrade-webview-before-using-the-kiosk).
All three native libraries were extracted from the verified APK and staged with
it. Every new file was read back before and after the swap. The original whole
WebView tree, including its odex, was moved outside the app scan directories to
`/system/homehq-stock-webview` and verified against the backup; `/system` was
remounted read-only. After restart, Package Manager and the runtime both reported
WebView 106, and the dashboard rendered text, layout and remote images.
No CA-store changes were needed for the tested hosted demo.

Following [the kiosk guide](../dashboard/kiosk/README.md), Home HQ saved the hosted
demo URL and was selected as the default Home app. The preferred-activity XML
persisted that selection. The optional `WRITE_SECURE_SETTINGS` permission was
granted for the floating navigation service; the service was observed bound.
The owner physically tested Settings → Apps → Dashboard, then confirmed automatic
dashboard startup after a full power cycle without USB or the microSD.
Rootless and the vendor apps were retained. The demo contains sample data.

## Recovery retained and limits

The owner retains the verified full backup, original boot image, card boot-area
backup, reviewed boot restore plan, and original WebView tree. The prepared WebView
rollback is designed to restore the whole original APK/odex tree, verify readback
and remount read-only before restart; it has not been exercised. It does not require
rewriting the boot partition. Home startup
can be undone by choosing another Home app and disabling Home HQ's Home alias,
as described in the kiosk guide. The original FEL card remains available.

No Linux replacement, Tailscale or SSH service was installed. Android 6 and
WebView 106 remain old software; root USB ADB is privileged access. This report
establishes the observed kiosk and recovery preparation on one unit, not long-term
reliability, current browser security or compatibility across firmware variants.
