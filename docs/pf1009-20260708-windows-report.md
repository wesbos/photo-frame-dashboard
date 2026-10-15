# AEEZO PF1009 July 2026 firmware: root USB ADB out of the box

Tested on Windows / PowerShell on 2026-10-14.

**This unit was straightforward to access: with a working USB-A to USB-C data
cable connected and the frame booted, Windows recognized it and ADB already ran
as root.** No rooting exploit, FEL payload, boot patch, or device-side ADB-enabling
step was needed. No ADB authorization prompt appeared during this test.

Home HQ now starts automatically after a physical power cycle, displays the
hosted demo dashboard, and provides working touch navigation back from Android
Settings. The main extra work after gaining access was backing up the frame,
upgrading its old WebView, and configuring the launcher and navigation.

This is a report of **one unit with the exact firmware below**, not a universal
PF1009 flashing guide. Start with the [A33 guide](pf1007l-start-here.md) and follow
the [backup and write rules](../README.md#rules-we-learned-the-hard-way).

## Identify the matching unit

| Item | Observed value |
| --- | --- |
| Product | AEEZO Digital Picture Frame, [Amazon Canada B0H4T8HX9K](https://www.amazon.ca/dp/B0H4T8HX9K) |
| Model | PF1009 on the back, startup screen, and About screen |
| Firmware | `YHK.F-null-A33-1001-D1024-PF1009-V11-1680.0.20260708` |
| AiMOR | `6.0.78`, code `78`; About showed “Had not updated” |
| Android | 6.0.1 / SDK 23 / ARMv7 (`armeabi-v7a`) |
| Display | 1280 × 800, density 160 |
| USB | USB-C provides power and data; no separate round power jack |
| USB ID | `1f3a:1002` |
| Stock access | `uid=0(root) gid=0(root)` over USB ADB |
| Stock WebView | `44.0.2403.119` |

`adb devices -l` identified product `astar_m86_8723cs`, model `AEEZO`, and device
`astar-m86_8723cs`. The build fingerprint was:

```text
AEEZO/astar_m86_8723cs/astar-m86_8723cs:6.0.1/MOB30R/20260708:eng/test-keys
```

`A33` in the firmware string suggests the Allwinner A33 family; the SoC was not
independently identified through FEL. This firmware differs from the
[April PF1009 units](pf1007l-pf1009-20260417.md), whose string contains
`PF1007L-OS-PF1009.0.20260417`. A shared model name is not evidence that their
boot patches or firmware images are interchangeable.

## USB access: connect a data cable and check root

With the tested cable, Windows detected both interfaces using `usbstor.inf`
(mass storage, `MI_00`) and `winusb.inf` (Android, `MI_01`). With Google's Android
platform tools available, these read-only checks confirmed access:

```sh
adb devices -l
adb -d shell id
adb -d shell getprop ro.build.fingerprint
adb -d shell getprop ro.build.yhk.id
```

The frame appeared as `device` and `id` returned root. Both
`persist.sys.usb.config` and `sys.usb.config` were already `mass_storage,adb`.
Root USB access survived multiple physical power cycles, including after the
vendor apps were disabled. No persistent-ADB modification was required.

There was an earlier unsuccessful enumeration check with an unconfirmed cable
setup. Once a cable tested with a phone was used, the frame was recognized
without a device configuration change. The included cable's data capability was
not established; the earlier failure does not prove it is power-only. If nothing
appears over USB, check the cable and host connection before assuming this
firmware needs an unlocking procedure.

## What was needed to reach a working dashboard

Access was easy; setting up a usable dashboard still involved these stages:

1. **Keep the frame offline and make verified backups.** The full live eMMC user
   area and both hardware boot areas were captured before device changes.
2. **Install Rootless Launcher 3.9.1 as a fallback.** Its app drawer provided
   access to Settings and the stock apps. It remained installed afterward.
3. **Replace WebView 44 with the guide's pinned ARMv7 WebView 106.0.5249.126.**
   The complete stock WebView tree, including its odex, was preserved for rollback.
4. **Install Home HQ and physically test the route to Settings → Apps.** A local
   browser-failure fallback allowed that test while WebView was in an
   intermediate state. After a physical restart, WebView 106 rendered the demo.
5. **Disable the vendor apps only after root USB persistence and physical
   navigation had passed.** Their disabled state persisted after restart.
6. **Connect Wi-Fi, enable Home HQ navigation in Accessibility, and select Home
   HQ as Home with Always.** A subsequent physical power cycle opened Home HQ
   automatically, with working floating navigation buttons.

This order records what was tested; use the linked guides for preparation,
identity checks, exact downloads, and rollback. No firmware image or boot
partition was flashed. The WebView replacement did modify `/system`; this was
more than simply installing a dashboard APK.

### Backup and storage findings

The eMMC user area was **15,634,268,160 bytes** (30,535,680 sectors of 512 bytes),
smaller than the capacity recorded for the April PF1009 units.

| Partition | Block device | Start sector | Sectors |
| --- | --- | --- | --- |
| boot | `mmcblk0p6` | 172032 | 65,536 |
| system | `mmcblk0p7` | 237568 | 2,097,152 |
| recovery | `mmcblk0p9` | 2400256 | 65,536 |

Each hardware boot area (`mmcblk0boot0` and `mmcblk0boot1`) was 4,194,304 bytes.
The capture used shipped `/sbin/busybox dd`, with binary output handled directly
by the host process rather than PowerShell text redirection. The first full USB
read took about **34 minutes at 7.3 MiB/s**. Compression was performed on the host.

Exact byte counts, host SHA-256 readback, a scan for 4 KiB `0xCC` runs,
independent full boot/system/recovery rereads against the image ranges, two reads
of each hardware boot area, and complete gzip decompression readback passed.
This was a verified **live capture**: Android had writable filesystems mounted,
so it does not establish offline filesystem consistency or a tested full restore.

The boot image length calculated from its header was 15,886,336 bytes (31,028
sectors). Its SHA-256, confirmed against an independent boot-partition reread:

```text
c0093e7f70ad1a17a3fe80b5ad378584f9821bd8078777d4d6e06f2ee23a8dbf
```

This differs from the April firmware. Do not reuse another unit's patch payload
based on a matching partition layout.

### WebView upgrade and the first restart

The stock WebView tree included both its APK and `oat/arm/webview.odex`.
The complete original tree was archived and preserved at
`/system/homehq-stock-webview.bak`, outside Android's scanned app directories.
The pinned replacement APK and three ARMv7 libraries were staged and verified
before replacing `/system/app/webview`. File readbacks, ownership and modes
passed; `/system` was remounted read-only afterward.

Before restarting, Package Manager still reported WebView 44 while Chromium
106 code was loading. Home HQ initially crashed with an `AwBrowserProcess`
`NullPointerException` during browser construction. A local Home HQ 1.1.1/code 3
build added native Settings, launcher, and retry controls when browser startup
failed. The owner physically tested its two-finger menu → Settings → Apps route
before the power cycle.

**After the physical restart, WebView reported 106.0.5249.126, loaded its native
library, and rendered the dashboard.** The owner confirmed touch interaction and
the Settings escape route. The restart resolved the observed failure; its
precise cause was not independently isolated.

The tested Home HQ build included that local fallback and was based on kiosk
source at `033b5ac9e1bdec84501e3218873a09fe54555c8a`. The fallback code is
**not included in this documentation contribution**. It did not repair WebView,
and this report does not establish that the fallback is required after a clean
provider restart. Newer upstream navigation changes were not part of the tested
build.

Rollback requires restoring the **whole** original WebView tree, including odex,
verifying it against the backup, returning `/system` to read-only, and arranging
a controlled restart under the repository's write rules.

### Vendor apps and navigation

The frame stayed disconnected from Wi-Fi during preparation because of the
[documented AiMOR remote root-command exposure](aimor-remote-root-shell.md).
After the backup, persistent USB access, and physical escape checks passed,
these packages were disabled individually:

| Package | Purpose |
| --- | --- |
| `com.efercro.os.aimor` | Vendor launcher |
| `com.yhk.qeota` | Vendor updater |
| `com.DeviceTest` | Factory-test app |

After a physical power cycle, all three remained disabled and root USB ADB
still worked. No matching vendor processes or port-7806 connection were observed
in the checks performed. This is not a complete traffic analysis. On this unit,
disabling AiMOR did not remove access; that must not be assumed for frames whose
only ADB access comes through AiMOR. Undo is to re-enable the corresponding
package under the repository's write rules.

There was no usable system navigation bar (`com.android.systemui` was absent
from the package list). The two-finger menu worked within Home HQ, but did not
provide a route back from Android Settings by itself. Physically enabling
**Home HQ navigation** in Accessibility supplied floating **Back** and
**Dashboard** buttons. No `WRITE_SECURE_SETTINGS` grant was applied.

After enabling Home HQ's Home alias as described in the [kiosk guide](../dashboard/kiosk/README.md),
the owner selected **Always** in Android's Home chooser. A physical power cycle
then booted directly into Home HQ. The owner completed **two-finger menu →
Android settings → floating Dashboard** after that automatic startup. Rootless
remained available as a fallback; selecting it as the default Home reverses the
Home choice.

## Remaining quirks and limits

- **Internet clock recovery worked.** The clock lost its manual correction after
  power was removed, but recovered automatically after Wi-Fi connected, including
  on a later boot. Offline timekeeping and synchronization speed were not proven.
- **Timezone data was old (`tzdata2016a`).** A local fixed UTC-5 workaround
  (`Etc/GMT+5`) was applied and native readback verified. Its restart persistence
  and WebView behavior were not tested. It is not a general timezone fix.
- **Some HTTPS requests failed.** The demo rendered over Wi-Fi, but photos were
  blank and logs contained `CertPathValidatorException` / Chromium error `-202`.
  The failed request and certificate chain were not isolated. No certificate
  store changes or TLS bypass were applied.
- **The demo has a simulated clock and sample data.** Its fresh-load time starts
  at 3:18 PM. The demo's Real time control clears that session offset; an apparent
  dashboard clock mismatch does not establish that Android's clock is wrong.
- **The final dashboard did not need the computer's demo server.** USB forwarding
  was used temporarily during setup; later launches loaded the default hosted
  demo over Wi-Fi. Wall-charger-only operation was not separately tested; physical
  power-cycle tests used the known USB connection.

No personal calendar, account credentials, or custom dashboard deployment was
configured. Backups, raw logs, screenshots, vendor APKs, and signing keys remain
private. This report omits serials, MAC addresses, Wi-Fi details, eMMC identifiers,
and whole-device hashes; the firmware identifier and boot-image hash distinguish
the tested variant.
