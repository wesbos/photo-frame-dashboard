# Dragon Touch Classic10: USB root ADB and a WebView 106 dashboard

Report from **one unit**, inspected on **14–15 October 2026** using an Apple silicon Mac.
The purchase listing was not recorded. These observations describe this unit, not every
frame sold under the Classic10 name.

**Verified result:** USB ADB with a root shell, an upgrade from WebView 44 to 106, and
the Home HQ kiosk displaying a working web dashboard. Android remains at 6.0.1.

## Identify this variant

| Property | Observed value |
| --- | --- |
| Model / product | `Classic10` / `astar_ococci` |
| Firmware / display ID | `Classic10_A33M187_20250910-1617_V09` |
| Hardware | `sun8i` |
| Android / SDK | `6.0.1` / `23` |
| CPU ABI | `armeabi-v7a` |
| Display / density | `1280x800` / `160` |
| Stock photo app package | `com.waophoto.smartframe` |
| Stock WebView | `com.android.webview`, `44.0.2403.119` |
| WebView after upgrade | `com.android.webview`, `106.0.5249.126` |
| ADB access obtained | USB, root shell |

The firmware's `A33` marker and `sun8i` hardware suggest an **Allwinner A33-family**
board. The chip was not physically inspected.

This is distinct from both:

- The [Modern10 Charm](dragontouch-modern10-charm.md), which shares the platform and
  stock photo app package but has a different model and firmware.
- The **Classic10 Charm / Frameo** unit in [PR #165](https://github.com/wesbos/photo-frame-dashboard/pull/165):
  model `Classic10 charm`, firmware `Classic10 charm_A33M_20260323-1608_V01`, stock
  Frameo and WebView 106, with root ADB obtained over Wi-Fi. That report's access method
  and setup steps are not evidence for this unit.

No Rockchip setup script or PF1007L boot patch was applied to this Classic10.

## USB ADB observations

The Mac obtained a working USB ADB connection and a root shell. The initial USB cable
type, authorization prompt behavior and factory-reset state were not recorded, so this
report does **not** establish that USB debugging is enabled on every factory unit or
that authorization is bypassed. Network ADB was not part of the verified access path.

With Android platform-tools installed and the frame connected, these are read-only
identity checks. With multiple devices, use `adb -s` to select the intended frame:

```sh
adb devices -l
adb shell id
adb shell getprop ro.product.model
adb shell getprop ro.product.name
adb shell getprop ro.build.display.id
adb shell getprop ro.hardware
adb shell getprop ro.build.version.release
adb shell getprop ro.build.version.sdk
adb shell getprop ro.product.cpu.abi
adb shell wm size
adb shell wm density
```

Match the firmware and board before considering any system changes. A working root
shell gives broad access; this report does not establish the state of ADB authentication.

## Backup scope and WebView upgrade

Private live backups were captured for eMMC boot0/boot1 and the bootloader, env, boot,
recovery and system partitions. The capture records report exact byte counts, SHA-256
checks against full gzip readback and no detected `0xCC` filler. Independent re-reads
matched boot0/boot1, bootloader, env, boot and recovery; system was checked with
independent samples, not a second complete partition read. A separate live data archive
and the original WebView directory were retained privately.

These are **not** a verified whole-disk image or an atomic offline snapshot.
**Restore has not been tested.** No backup files, hashes, vendor APKs or identifiers
are included here, and this report supplies no partition offsets or flashing commands.

The system WebView was replaced with a LineageOS ARMv7 build of **106.0.5249.126**,
compatible with API 23. The APK signature and checksum were checked, and the APK and
three native libraries were read back after copying. The original WebView directory,
including its compiled artifacts, was saved first; `/system` was returned to read-only.
After reboot, WebViewFactory reported version 106 and Home HQ displayed the dashboard.

This is an observed outcome, **not an installation recipe**: the precise download and
its pinned checksum are not included. Do not replace WebView using an arbitrary APK
or another device's system layout. The prepared WebView rollback was not exercised.

## Kiosk and reboot behavior

Home HQ (`com.wesbos.homehq`) was installed and used with this unit's upgraded WebView.
The dashboard was checked at 1280x800, including weather, calendars and interactive tasks.
The two-finger hold opens the native menu for the launcher, Android settings, Wi-Fi
and dashboard reload. See the [kiosk guide](../dashboard/kiosk/README.md).

The frame initially reset its clock to January 1970 after reboot. The original NTP
server, `2.android.pool.ntp.org`, did not restore the time during the first trial.
With automatic time enabled, `time.google.com` configured as the NTP server and the
`Europe/Paris` timezone selected, a second reboot restored the time in about 38 seconds
and opened Home HQ automatically. HTTPS certificate checks were not bypassed.

Those are results from this unit and network, not a guarantee of boot timing. Incorrect
system time can prevent HTTPS from loading even when Wi-Fi is connected. A factory-reset
setup, prolonged offline boot and full backup restoration remain untested.
