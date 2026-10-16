# Joyhong 10.1" Frameo frame (`JT101F-C01`, Allwinner A33, Android 6.0.1)

Record of one unit, started 2026-10-16. Observations are kept separate from guesses. Unique
identifiers (serial, MAC, IP) are left out. Host: Windows 11.

**Short version:** same firmware image as [JT101F-I02](joyhong-jt101f-i02.md) — identical build
fingerprint — just a different model-name badge (`C01` vs `I02`). Root ADB over Wi-Fi on port 5555,
no key check, exactly as documented there. No USB data path found either, on a different host OS
than that report used.

## Identity

| | |
| --- | --- |
| Label / model | `JT101F-C01` (`ro.product.device=JT101F-C01`, `ro.product.model=JT101F-C01`) |
| Fingerprint | `joy/astar_ococci/astar-ococci:6.0.1/MOB30R/20260107:user/test-keys` — identical string to I02's |
| eMMC size | 61,071,360 sectors — identical to I02 |
| Partition table | same names, start sectors and sizes as I02's table (bootloader, env, boot, system, misc, recovery, cache, metadata, private, frp, empty, alog, media_data, then `UDISK` at sector 3,137,536) |
| Installed packages | `net.frameo.frame`, `com.waophoto.fota`, `com.joyhong.test`, `jp.co.omronsoft.openwnn` — same set as I02 |
| SELinux | Permissive |
| `/data` usage at receipt | 336 MB used of 27.2 GB free — looked like a fresh/unused unit |

## USB

Tried a USB-A-to-USB-C cable, frame on the USB-A end, a Windows 11 laptop on the USB-C end.
Windows played its device-connect chime on plug-in, but: `adb devices` showed nothing, no new
entry appeared in `Get-PnpDevice` (checked both before and after an unplug/replug), and
`setupapi.dev.log` recorded no new device section for that time window. Whatever triggers the
connect sound is not a real USB enumeration. This matches the I02 report's conclusion that the
USB-C port on this board only feeds the PMIC and the data lines never reach the SoC's USB
controller — now observed on a second host OS (Windows, vs. the original report's macOS).

## ADB and root

Confirmed exactly as the I02 report describes: `service.adb.tcp.port=5555` is set in
`/system/build.prop`, and `adbd` runs as root with no key check over the network.
`adb connect <ip>:5555` then `adb shell id` returns `uid=0(root)`, immediately, no prompt on
the frame's screen.

## Boot image hash differs from I02, despite the identical fingerprint string

Both units report the same `ro.build.fingerprint`, but the boot partition's actual bytes are
not identical between the two:

| Sectors from 172032 | I02 (reported) | C01 (this unit, measured) |
| --- | --- | --- |
| 29,248 (Android header + kernel + ramdisk) | `f294ef858752f69a3f25d61fd625e5b5970e96852c40f513a943e77005e95c1f` | `69dcbd74d60b3d0a2a6d27c81dbbe2a26a9da1f8c2dcb982e06477162a3ceefd` |
| 31,028 (the length the PF1007L template uses) | `3b77d1227a0e2b7013ad99be7189b9abaccd3c75932ba89dfcf2c9cb5a6cd24d` | `7f619245e7c88aab5399ec673d2a592f89b811cf978615042aec32a71e050ae3` |

Worth knowing if anyone writes a boot-image-hash-based guard for this device family: the build
fingerprint string alone does not guarantee byte-identical boot partitions across model-name
badges, even from the same vendor and the same build date. A likely cause is a model string baked
into the ramdisk's `default.prop` (`ro.product.model` differs: `JT101F-C01` vs `JT101F_I02`), not
a kernel or app difference.

(Only this sub-range's hash is published, per the repository's rule not to publish a whole-eMMC
hash as it would double as a device identifier. A full pre-modification backup was taken and its
SHA-256 verified after transfer, but is not included here.)

## Setup done on this unit (2026-10-16)

All over network ADB, after a verified backup of the pre-`UDISK` eMMC region and both eMMC boot
partitions (`mmcblk0boot0`/`boot1`). Each step has an undo.

| Step | Command | Undo |
| --- | --- | --- |
| Build the kiosk | `build.ps1` from `dashboard/kiosk/`, on Windows, with JDK 17 (Temurin) and Android `build-tools;34.0.0` + `platforms;android-34` (command-line tools only, no Android Studio) | n/a — local build output |
| Install the kiosk | `adb install -r homehq.apk` | `pm uninstall com.wesbos.homehq` |
| Make the kiosk Home, keep Frameo as fallback | `adb shell am start -n com.wesbos.homehq/.MainActivity --ez home true`, then `adb shell am start -a android.intent.action.MAIN -c android.intent.category.HOME` to raise the chooser, then tapped **Home HQ** → **Always** on the frame's screen | pick another Home app in Settings → Apps → Default apps, then the first command again with `--ez home false` |
| Disable the vendor updater | `pm disable com.waophoto.fota` | `pm enable com.waophoto.fota` |

`cmd package set-home-activity` is not available on this Android 6 build (`/system/bin/sh: cmd:
not found`), same as the PF1007L/BIUFRAME units the kiosk README already calls out — the chooser
route was needed here too.

After these steps, `/data/system/users/0/package-restrictions.xml` shows:

```xml
<preferred-activities>
    <item name="com.wesbos.homehq/.Home" match="100000" always="true" set="2">
        <set name="net.frameo.frame/.ui.activities.AWaitForDeferredInitCompleted" />
```

confirming the Home preference stuck and that Frameo is retained in the set as the other option.
Pressing the Home key opens `com.wesbos.homehq/.Home` directly. The kiosk loaded the repository's
hosted demo dashboard (its compiled-in default URL) over the frame's Wi-Fi with no further changes
needed — no certificate-store patch was required for that hosted page.

This is also, as far as this report's author found, the first worked end-to-end report of
`dashboard/kiosk/build.ps1` (the Windows build path) against a real unit; the kiosk README
documents the script but had no linked unit report.

## Report

```text
About model / firmware:   JT101F-C01, joy/astar_ococci/astar-ococci:6.0.1/MOB30R/20260107:user/test-keys
Ports (DC jack, or USB-C only): USB-C (power) and a USB-A host socket, no DC jack
Cable and port that gave USB data (or none): none, USB-A-to-USB-C cable into a USB-A port on Windows 11
T3 USB IDs seen / adb devices output: nothing; Windows played a connect chime but no PnP entry, no setupapi.dev.log entry
T3b network ADB result (port 5555): open, root shell, product astar_ococci, no key check
eMMC size in sectors: 61071360
Boot partition start sector: 172032
Boot image SHA-256 (sector 172032, 31,028 sectors): 7f619245e7c88aab5399ec673d2a592f89b811cf978615042aec32a71e050ae3 (differs from I02's, see above)
Route used and result: stock network ADB, root out of the box, same as JT101F-I02
Host OS: Windows 11
First failed step and its exact output: none
```
