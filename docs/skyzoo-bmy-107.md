# SKYZOO BMY-107 (10.1" Frameo, RK3126, Android 6.0.1)

Record of one unit, configured on 2026-11-03 from macOS (Apple silicon). Android's model, product
and device are all `BMY-107`, brand `SKYZOO`, manufacturer `BMY`. It is a sibling of the
[MONOCUS WF105T (`BMY-106`)](monocus-wf105t.md): same vendor build host, same disk size, and the
same ADB, WebView and kiosk route worked. The partition layout is **not** identical (see below).
Match the fingerprint, not the retail name. Unique identifiers and the owner's URLs stay in
private, ignored records.

**Result:** USB ADB through Frameo's Beta program, shipped root with no prompt, persistent Wi-Fi
ADB verified across reboots, WebView 44 replaced with 106, Home HQ as Home with Rootless Launcher
as fallback, Frameo and the vendor updaters disabled. The owner physically confirmed the way back
(controls → Android settings → Apps → floating Dashboard button) before Frameo was disabled.
No boot patch, Loader access or firmware update was needed. **No full eMMC backup was taken**
(the owner declined); only the original WebView files were saved.

## Identity

| | Observed |
| --- | --- |
| Android model / brand / manufacturer | `BMY-107` / `SKYZOO` / `BMY` |
| Product / device | `BMY-107` / `BMY-107` |
| Firmware (`ro.build.display.id`) | `BMY-F606T_SSV6158-SKYZOO_Frameo-V1.0.1202309261720.release-keys` |
| Fingerprint | `rockchip/rk312x/rk312x:6.0.1/MXC89K/user.liubc.20230926.171943:user/release-keys` |
| SoC | `Hardware: Rockchip RK3126` in `/proc/cpuinfo`; `/sys/devices/system/cpu/soc` = `rk3126` |
| Android | 6.0.1, API 23, security patch 2016-07-05, `user` build |
| Security properties | `ro.secure=1`, `ro.debuggable=0`, `ro.adb.secure=1`; SELinux permissive |
| RAM / main eMMC | `MemTotal: 1024048 kB`; 30,777,344 sectors of 512 bytes (same as the BMY-106) |
| Display | 1280x800, density 160, no overrides |
| Touchscreen | `gslX680-d708`, 10 multitouch slots |
| Wi-Fi | `ssv6158` kernel module, driver "SSV WLAN driver", `platform:SSV6020C` |
| Stock WebView | `com.android.webview` 44.0.2403.119, `/system/app/webview/webview.apk` (dated 2023-09-26) |
| Frameo | `net.frameo.frame` v1.32.16 (Beta program) |
| SystemUI | `com.android.systemui` disabled at stock (`enabled=2`); no navigation bar |
| Vendor updaters | `com.adups.fota`, `com.adups.fota.sysoper`, `android.rockchip.update.service`, all enabled at stock |
| USB IDs | Not recorded (USB name shown by macOS: `BMY-107`, vendor `BMY`) |

## USB ADB and root

Frameo **Settings → About → Beta Program**, then **ADB access**. This firmware has no Android
developer options in reach; the Frameo toggle is the only switch.

The first USB-C cable tried was charge-only: the frame powered on but never enumerated, not even
as `unauthorized`. A different data cable through a USB-C dock enumerated at once. No "Allow USB
debugging" prompt appeared and the host was authorized; whether an unfamiliar key is rejected was
not tested.

```sh
adb devices -l                          # BMY-107
adb -s <serial> shell su 0 id           # uid=0(root) context=u:r:init:s0, no prompt
```

`/system/xbin/su` is shipped. Before any change, nothing listened on TCP 5555 and no mDNS ADB
service (`_adb-tls-connect`, `_adb`) was advertised. Turning on Frameo's ADB access only starts
USB ADB on this unit.

## Partition layout

512-byte sectors from `/sys/block/mmcblk0/mmcblk0p*/{start,size}`:

| Partition | Name | Start sector | Size (sectors) |
| --- | --- | --- | --- |
| p1 | uboot | 16,384 | 8,192 |
| p2 | misc | 24,576 | 8,192 |
| p3 | resource | 32,768 | 32,768 |
| p4 | kernel | 65,536 | 24,576 |
| p5 | boot | 90,112 | **32,768** |
| p6 | recovery | 122,880 | 65,536 |
| p7 | backup | 188,416 | 131,072 |
| p8 | cache | 319,488 | 262,144 |
| p9 | metadata | 581,632 | 32,768 |
| p10 | kpanic | 614,400 | 8,192 |
| p11 | system | 622,592 | 2,097,152 |
| p12 | radical_update | 2,719,744 | 131,072 |
| p13 | userdata | 2,850,816 | 27,926,528 |

Compared with the [BMY-106](monocus-wf105t.md#partition-layout-and-backup), `boot` is 8,192
sectors larger, so every partition after it starts 8,192 sectors later and `userdata` is 8,192
sectors smaller. Do not reuse the BMY-106 offsets or backup length. `biuframe-setup.sh` has no
profile for this fingerprint; its steps were run by hand.

## Persistent Wi-Fi ADB (tested)

```sh
adb -s <serial> tcpip 5555
adb connect <frame-ip>:5555
adb -s <frame-ip>:5555 shell "su 0 setprop persist.adb.tcp.port 5555"
```

The first `adb tcpip 5555` returned `error: no devices/emulators found` while the USB device
re-enumerated; repeating it worked. A reboot came back with TCP ADB listening after about 26 s
and `persist.adb.tcp.port=5555`. After later reboots, with USB unplugged, Wi-Fi ADB kept working.
Right after a reboot, the old TCP transport showed `offline` until `adb disconnect` and a fresh
`adb connect`.

Wi-Fi ADB is slow on this unit: pulling the 41 MB WebView directory ran at about 0.3 MB/s, while
pushes over USB ran at about 7.4 MB/s. Do large transfers over USB.

Undo (not exercised): `su -c 'setprop persist.adb.tcp.port -1; setprop service.adb.tcp.port -1'`,
then `adb usb`.

## WebView 44 to 106

Same method as the [BIUFRAME guide](biuframe-setup-guide.md) step 4, run by hand because no
setup profile matches. The original `/system/app/webview/` (APK and `oat/arm/webview.odex`) was
pulled to the computer first, and kept on the frame as `webview.apk.bak` and `oat.bak/`.
`/system` had 520 MB free.

| Asset | Source | SHA-256 |
| --- | --- | --- |
| WebView 106.0.5249.126, ARMv7 | LineageOS `android_external_chromium-webview_prebuilt_arm` @ `4b0ae494a7dd` | `e2edc1f89ec1608b169da9e7ffc037190b70c7825f0be29694f4cae719980580` |
| Rootless Pixel Launcher 3.9.1 | F-Droid `amirz.rootless.nexuslauncher_30911.apk` | `7fa44d560dc4577374d45176220de2c0b00a71e09d6d148cdea4e0a52d38404a` |

The APK and the three `lib/armeabi-v7a` libraries were copied into `/system/app/webview/` and
`lib/arm/` (root, 0644 files, 0755 directories), `oat/` was removed, and each file's MD5 matched
on the frame. After a reboot `versionName=106.0.5249.126` and logcat had no
`webviewchromiumloader: Failed to load library`.

## Kiosk, Home and vendor packages

Home HQ was built from `dashboard/kiosk/` with build-tools 35.0.0 and platform 34
(`BUILD_TOOLS=$ANDROID_HOME/build-tools/35.0.0`), installed with Rootless Launcher, and granted
`WRITE_SECURE_SETTINGS`. Home HQ then switched the navigation service on by itself
(`accessibility_enabled=1`). A self-hosted MagicMirror² page loaded and rendered on WebView 106;
the kiosk process used about 35% CPU.

- **Home choice.** `--ez home true`, then the Home chooser. Tapping Home HQ without **Always**
  saved `always="false"`. Disabling Frameo brought the chooser back; Home HQ → Always then wrote
  `always="true"` with Home HQ and Rootless as the set. A reboot booted straight into Home HQ.
- **Disabled** (`pm disable-user --user 0`, through root): `net.frameo.frame`,
  `com.adups.fota`, `com.adups.fota.sysoper`, `android.rockchip.update.service`; also
  `pm hide com.adups.fota`. After reboot all were `enabled=3` with no processes. Undo:
  `pm unhide com.adups.fota`, then `pm enable <package>`.
- **Two-finger hold.** It works on the `gslX680`, but only when held. A `getevent` capture showed
  two separate tracking IDs for every attempt; quick presses lifted after about 0.2 s and did not
  open the controls, while holds of 2.1 s and 2.3 s did. The owner first thought the gesture was
  broken.

## Clock

There is no clock battery. After a reboot the frame came up at **2021-05-15 02:00**, and network
time corrected Android's clock within about 1.5 minutes. A MagicMirror² page that had already
loaded kept showing the 2021 date until the kiosk was restarted (`am force-stop` and start).

## Not tested

A full eMMC backup (declined by the owner), Loader mode, rejection of an unknown ADB key,
any of the undo commands, Let's Encrypt roots, swap, or long-term unattended stability. Android 6
with a 2016 security patch and permissive SELinux remains an old platform; replacing WebView does
not update the OS.
