# Benibela JT101M-B02 / JT101M-A02 (Allwinner A133, Android 10)

One 10.1-inch Benibela sold as `JT101M-B02`; Android reports `JT101M-A02`.
Tested from a Linux host over micro-USB, with separate DC barrel power.
The [C-2](joyhong-c2-a133.md) and [LOOFII C-3](allwinner-a133-loofii-c3.md)
also use the A133; their recovery and flashing procedures have not been verified on this frame.

## Identity and hardware

| Item | Observed |
| --- | --- |
| SoC | Allwinner A133, four Cortex-A53 cores; configured maximum 1.512 GHz |
| OS | Android 10 / API 29, kernel 4.9.170; 64-bit kernel, 32-bit ARM userspace, VNDK 29 |
| Build fingerprint | `Allwinner/ceres_aw/ceres-aw:10/QP1A.191105.004/eng.joy.20220905.163444:eng/test-keys` |
| Security patch | `2020-11-05` |
| RAM | 2,021,884 KiB visible to the kernel (2 GB class); `ro.config.low_ram=true` |
| eMMC | SCA32G, 61,079,552 × 512-byte sectors = 31,272,730,624 bytes |
| Display / touch | 800×1280 panel, logical landscape 1280×800 at 160 dpi; `a00zp101i004_e40` panel driver, `gslX680` touch |
| Wi-Fi | XR829 / `xradio_wlan`, SDIO `0a9e:2282`; association and network time worked |
| USB / power | Micro-USB data (`1f3a:1001`) and DC barrel jack. USB-only power flickered at startup; booted with DC power attached |
| Access | Root ADB shell as shipped; SELinux Enforcing; vbmeta device state reports locked |
| WebView | Stock 74.0.3729.186 → tested system-app update 155.0.8059.39; AOSP test-key signed |
| Stock HOME | `com.waophoto.smartframe/.ui.GuideActivity` |

One apparent shutdown was the stock 120-second screen-sleep timeout; ADB remained available.

## Sensor and interface observations

Android registers no sensors on stock firmware. Driver and device-tree entries do not
establish fitted hardware:

| Interface | Observed | Unverified |
| --- | --- | --- |
| Accelerometer | `mir3da` is declared; stock logs report sensor-not-found and initialization failures. | Fitted part or working acceleration/rotation samples. |
| Light / proximity | `stk3x1x` is declared; I²C initialization fails and no usable sensor interface appears. | Fitted part or working light/proximity readings. |
| Other inputs | `MH248` PageUp/PageDown, `bl_h18l232b` presence and IR inputs are registered. | Physical switches, presence/IR hardware or working events. |
| Camera | HAL metadata advertises a camera; stock logs show sensor-read retries and ID `0x0`. | Fitted camera or working capture. |
| Bluetooth | Controller initialization and Settings discovery worked. | Pairing, HID, audio or GATT connections. |

## Access and stock software

`ro.adb.secure=0`; `/system/xbin/su` is setuid and world-executable (mode `4777`).
The platform certificate matches the public AOSP platform key. One unprivileged test app
in the `untrusted_app` SELinux domain was denied execution of `su`. This does not establish
that every app or privileged process is restricted; USB ADB still provides unauthenticated root.

No standalone `com.waophoto.fota` package was installed, and no TCP 5555 or 14035 listener
was observed. Do not assume the C-2's updater or network-ADB configuration applies.
Allwinner's persistent logcat/kernel logging is running; its init config includes rotation.

Android's default HTTPS trust manager and WebView 155 accepted the
[eMudhra AAA-chain test hosts](https://emudhra.we-have-a-problem.com/), including the unlogged
certificate. Android's public-key blocklist then blocked both live hosts in each client and
all 16 offline chains in the trust manager. Ordinary HTTPS still worked; undo/reapply and a
normal reboot were tested. This does not cover apps with independent TLS stacks.

## WebView and video

WebView 155.0.8059.39 installed as an update in `/data` using the
[same pinned LineageOS APK and AOSP test-key route as the C-2](joyhong-c2-a133.md#webview-and-the-kiosk).
The factory APK remained unchanged. `oklch`, `color-mix`, `:has()`, nesting, flex gap and
`aspect-ratio` passed; all six failed on stock WebView 74. A pinned build of the repo's demo
passed visible-content and USB touch-navigation checks on all seven tabs in the existing
WebView test browser. External fonts/images were blocked; the Home HQ APK was not tested.

Local 15-second H.264 Baseline clips at 480p, 720p and 1080p/30 used
`OMX.allwinner.video.decoder.avc`. Each 450-frame clip ended with two browser-reported dropped
frames and no corruption. Streaming and long-term playback were not tested.

Rollback was tested with `adb shell pm uninstall -k com.android.webview` (no `--user`):
the factory provider returned and rendered the test page and 480p video. Avoid
`uninstall-system-updates` on this Android 10 build: it operates on all updated system apps.
After reinstalling 155, a normal reboot preserved it, Photos auto-start and Rootless HOME.

## Launcher and photo viewer on stock Android

Rootless worked as the default HOME. A custom native photo viewer and dashboard ran on stock
Android; dashboard responsiveness and layout were confirmed on the panel. These were separate
from this repo's WebView kiosk.

The photo viewer's existing `BOOT_COMPLETED` receiver ran, but Android blocked its background
Activity start. Allowing the `SYSTEM_ALERT_WINDOW` app-op for that viewer alone let the same
receiver bring it onscreen. Android documents this as a
[background-launch exception](https://developer.android.com/guide/components/activities/secure-bal#when-background-activity-starts-are-allowed-exceptions).
No overlay was drawn. After a normal ADB reboot, the viewer opened automatically in about
35 seconds with Rootless still the default HOME. The cached album appeared and the viewer
later reconnected to its server. Cold power-loss startup was not tested.

No system navigation bar appeared. The repo's [floating Home button](../scripts/home-button/README.md)
worked across apps, but Allwinner's background manager refused its service after reboot.
The vendor **Auto run** app saved Frame Home's Allowed choice without restoring the runtime
list at boot. An Activity workaround was intermittent. [PR #270](https://github.com/wesbos/photo-frame-dashboard/pull/270)
adds an opt-in to reload those saved choices on this exact firmware/vendor APK; two normal
reboots and Hide, opt-out and Disallowed checks passed. No root boot hook was added.

Home and Settings → Apps were confirmed by touch before disabling `com.waophoto.smartframe`.
After disabling it, Home still worked from Settings, Photos and the native dashboard; a normal
reboot preserved the floating button, Rootless HOME and automatic photo startup.

Undo: restore the vendor package's previous enabled state before selecting the stock HOME,
turn off the viewer's boot option and restore its previous overlay app-op (`default` on this
frame). Disable the helper’s saved-settings reload option and restore only its previous
Auto run choice. Hide or uninstall `com.photoframe.homebutton` to remove the floating button.

## Firmware preservation and differences

Preserved 18 regions: firmware partitions, both eMMC hardware boot areas, device configuration
and primary/backup partition tables. Exact byte counts, gzip readback and independent device
hashes were checked. Userdata, cache, writable DSU metadata and RPMB were excluded.
This is a partial firmware backup, not a full-device clone; a full restore has not been tested.

These whole-partition hashes and offsets differ from the C-2 record:

| Partition | Start sector | Sectors | SHA-256 |
| --- | --- | --- | --- |
| `boot` (p3) | 257,568 | 151,072 | `c34b8972af71acbb57fb6807e05af219bf3cc17da267911c00d7b9c4b801d692` |
| `recovery` (p6) | 4,635,712 | 65,536 | `4897ce63357470713a5c2940286433746d29a7d4c6bb5302c8de7b772e6c1ba3` |
| `dtbo` (p15) | 6,470,720 | 4,096 | `cbd231eaf5a513f2a124226feb406e64796680c0c86a9442bbcfb91186111ac2` |

## Android 12 trials and recovery limits

DSU attempts, including phh Android 12.1 v416 and a stock-system control, reached U-Boot
fastboot without guest ADB. A guest-init recorder produced no output. The cause is unknown;
the result does not establish Android 12 incompatibility. Stock Android was recovered, and
ten checked firmware regions matched the preserved copies. No firmware partitions were
flashed and the bootloader was not unlocked.

Software FEL entry and read-only SoC identification worked (`soc=00001855(A133)`). A later
retained-DRAM read stalled FEL and required removal of both DC and USB power. The attempted
reset-pinhole entry booted Android normally, so hardware FEL entry remains unverified.
A software-only FEL return remains unverified. Do not repeat the stalled DRAM probe.
