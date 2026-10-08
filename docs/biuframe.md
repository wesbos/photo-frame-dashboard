# BIUFRAME 10.1-inch picture frame

Second device, separate from the Skylight 150-CAL. Notes are for this one unit.

**Setting up another unit?** Follow [biuframe-setup-guide.md](biuframe-setup-guide.md) and
`scripts/biuframe-setup.sh`. This file is the research log behind it, including dead ends.

## eMMC offsets (2026-09-30)

Loader (`rkdeveloptool`) sector 0 = Android `/dev/block/mmcblk0` sector 8192. For example `boot`
is loader `0x14000` and `mmcblk0p5` start 90112 (`0x16000`); the two reads have the same SHA-256
(`26917f33…`). The loader backup therefore does not include the first 4 MiB of the eMMC.

- eMMC sectors 0–8191 were read twice over ADB with root (`dd if=/dev/block/mmcblk0 count=8192`),
  SHA-256 `4cfddf8a59b2236077fa2357fbee4296252843372db0f166f1fc1128c501cfa2` both times, and
  saved as `backups/synergy-10x1/emmc-sectors-0-8191.bin`.
- There are 858 non-zero sectors, from `0x40` to `0x1fc0`. Sector `0x40` starts
  `3b8c dcfc be9f 9d51`, the usual RC4-scrambled Rockchip IDBlock header.
- `scripts/biuframe-setup.sh backup` reads sectors 0 to 8192 + `0x3B4000` over ADB, so it
  includes this area.
- Tested 2026-09-30: `backup` produced `backups/<serial>/emmc-0-3891200.img.gz` (1,992,294,400
  bytes raw, SHA-256 `2e803ae14fbd19055abc41b55f9fa102b1343aae4b8961933a7994bf1bb19b34`, 7 min 15 s).
  boot, recovery, and system data at loader `0xC0000` match re-reads.
- `/system` ext4 superblock mount count: 14,947 in the backup, 15,028 about 7 minutes later, and
  15,036 → 15,042 over 30 s. Something remounts `/system` about 12 times a minute; SuperSU's
  `daemonsu:mount:master` is the likely cause (not confirmed). Only the superblock (sector 2) and
  journal sectors 1329–1330 of system differed from the backup.

## Hardware and ports

| Item | Observation |
| --- | --- |
| Product | BIUFRAME 10.1-inch digital picture frame |
| Ports | Reset pinhole, USB-C, microSD, 5 V DC barrel jack (powered from a USB-A plug) |
| Buttons | Power and reset only; no volume keys |
| Normal USB identity | `Synergy 10X1`, VID:PID `2207:0006` (ADB) |
| Loader USB identity | VID:PID `2207:310d`; `rkdeveloptool ld` reports `Loader` |
| Chip query | `41 32 31 33 37 31 30 32 37 31 34 30 30 30 32 56`; RK312x family (RK3126/RK3128) |
| Flash | eMMC (`Flash ID: 45 4D 4D 43 20` = `EMMC `), 61,063,168 sectors of 512 bytes (~31.3 GB) |
| Firmware | `FIRMWARE_VER:6.0.0`, `MACHINE_MODEL:rk312x`, `MANUFACTURER:RK30SDK` |
| Boot arguments | `console=ttyFIQ0`, `androidboot.selinux=permissive`, `androidboot.hardware=rk30board` |
| Partition table | Rockchip `parameter` (`PARK` magic) with `mtdparts`; no GPT |

## Connecting

- The first cable produced nothing on the USB bus. A different USB-C cable connected immediately.
  The frame's USB-C port is device-capable; cable choice matters.
- The frame runs from USB power alone in loader mode (no DC connected).
- ADB was enabled out of the box but reported `unauthorized`. The authorization prompt appears
  on the frame, not the Mac.
- It then appeared in Rockchip loader mode (`2207:310d`). Exactly what triggered loader mode
  is unconfirmed (it happened around the cable swap; the reset-button-at-power-on method had been suggested).

## Stock recovery

Standard Android recovery menu: reboot system, reboot to bootloader, apply update from ADB,
apply update from SD card, wipe data, wipe cache, mount /system, view recovery logs, power off.

It is unusable on this unit: the header says "any button cycles highlight", but a short power
press selects the default item (Reboot system now), and a long press turns the highlight
green, then reboots on release. A wired USB keyboard through several adapters was not recognized.

## Partition layout (active CMDLINE)

Offsets and sizes in 512-byte sectors. The parameter block also contains a commented-out
`#CMDLINE` with a 1 GiB system (`0x200000`); the active line uses 1.5 GiB (`0x300000`).

| Name | Offset | Size | Size (MiB) |
| --- | --- | --- | --- |
| uboot | `0x2000` | `0x2000` | 4 |
| misc | `0x4000` | `0x2000` | 4 |
| resource | `0x6000` | `0x8000` | 16 |
| kernel | `0xE000` | `0x6000` | 12 |
| boot | `0x14000` | `0x6000` | 12 |
| recovery | `0x1A000` | `0x10000` | 32 |
| backup | `0x2A000` | `0x20000` | 64 |
| cache | `0x4A000` | `0x40000` | 128 |
| metadata | `0x8A000` | `0x8000` | 16 |
| kpanic | `0x92000` | `0x2000` | 4 |
| system | `0x94000` | `0x300000` | 1536 |
| radical_update | `0x394000` | `0x20000` | 64 |
| userdata | `0x3B4000` | rest | ~28,000 |

## Loader reads

Unlike the Skylight's stock loader, this one returns real data above 32 MiB:

- `boot` at `0x14000` (40 MiB) starts with `ANDROID!`.
- `system` at `0x94000` and `userdata` at `0x3B4000` both show an ext4 superblock magic (`53ef`).

## Backup

2026-09-30: `scripts/backup-flash.py --sectors 0x3B4000` (sectors 0 to the start of userdata)
into `backups/synergy-10x1/firmware-0-3B4000.img.gz`. Took 2 min 7 s over USB power only.

| Check | Result |
| --- | --- |
| Raw bytes | 1,988,100,096 (3,883,008 sectors) |
| Raw SHA-256 | `8a02a08f959b7337a8feb22f15b04200a815e7ab51c031db3a15862792119b9a` |
| Compressed | 352,791,621 bytes, SHA-256 `45d7b72e2a1c10b7e9ede361c593bf630b0a7a4e2a37ef7eaff2c1790ef6af02` |
| Gzip readback | Verified by the script |
| `0xCC` filler | No 64 KiB runs; no 8-byte `0xCC` runs anywhere |
| Non-zero content | ~495 MB of the 1.99 GB |
| Independent re-reads | uboot, kernel, boot, recovery, radical_update, and three non-empty 16 MiB system slices (`0x94000`, `0xC0000`, `0x120000`) all match the backup |

Partition headers in the backup:

| Partition | First bytes | Meaning |
| --- | --- | --- |
| uboot | `LOADER  ` | Rockchip legacy loader image |
| resource | `RSCE` | Rockchip resource image (DTB, logo) |
| kernel | `KRNL` | Rockchip-wrapped kernel |
| boot | `ANDROID!` | Android boot image (ramdisk) |
| recovery | `ANDROID!` | Android boot image |

userdata (~28 GB) is not backed up yet.

## Root (stock, no flashing)

The stock firmware is already rooted. Verified 2026-09-30:

```
$ adb shell su -c id
uid=0(root) gid=0(root) groups=0(root) context=u:r:toolbox:s0
```

- `system/xbin/su` and `system/xbin/daemonsu` are SuperSU binaries (static ARM, 133,472 bytes).
- `init.rockchip.rc` and `init.rk30board.rc` both define `service daemonsu /system/xbin/daemonsu --auto-daemon`
  in `class main` with no `user` line, so it runs as root at boot. `init.rc` chmods both to `0777`.
- SELinux is permissive (`getenforce` → `Permissive`; `androidboot.selinux=permissive`).
- `adbd` itself runs as `shell` (`ro.secure=1`, `ro.debuggable=0`), so `adb root` is not available; use `su`.
- ADB authorization was already accepted after the loader session; `adb devices` reports
  `product:rk312x model:10X1 device:rk312x`.

Build: `rockchip/rk312x/rk312x:6.0.1/MXC89K/user.thzy.20240919.143320:user/release-keys`,
display ID `V1.0.0`, security patch `2016-07-05`. `build.prop` also sets `ro.adb.secure=1` and
`persist.sys.usb.config=adb`.

### Boot image notes (for any future boot patch)

- `boot` and `recovery` are Android header v0, page size 16,384, with a 1,140,224-byte second
  stage. The header cmdline is empty; the kernel cmdline comes from the `parameter` block.
- The header ID does not match the AOSP SHA-1 on either stock image, nor any tried variant
  (SHA-1/SHA-256, padded or not, with or without sizes and header words). The loader contains
  `boot or recovery image sha mismatch!` next to its secure-boot strings; whether it enforces this
  on this unit is unknown. A modified boot image is untested.
- `/system/bin/install-recovery.sh` checks recovery against boot SHA-1
  `c6c084cbd57137c0ca69957b834e2dc4f6b6fbed` (10,256,384 bytes) and rebuilds recovery from boot
  with `recovery-from-boot.p` if recovery does not match.
- `rkdeveloptool rd` from loader mode returns to normal Android with ADB in about 30 s.

## Peripherals (live, 2026-09-30)

| Function | Part | Where | Evidence |
| --- | --- | --- | --- |
| Display | MIPI DSI panel, 800×1280 native (portrait, shown rotated as 1280×800) | VOP → DSI | `mipi_lcd_en` gpio-43, `mipi_lcd_rst` gpio-76; fb0 modes `U:800x1280p-56` |
| Touch | Hynitron `cst2xxse` | i2c-2 `0x5a`, input1/event0 | `CST_INT_PORT` gpio-0, `CST_RST_PORT` gpio-73 |
| Touch (alt, unbound) | `GSL_THZY` (Silead GSL) | i2c-2 `0x40` | No driver bound; likely an alternate panel option in the same firmware |
| Motion (PIR) | Infrared sensor on a GPIO | gpio-107 (`ir_gpio`, GPIO3_B3), input | Not an input device. Biu Frame strings reference `/infrared_enable`, `/sys/class/input/input5`, `/sys/class/input/input7`, none of which exist on this unit |
| Accelerometer | Silan SC7A20 (LIS3DH-compatible) | i2c-2 `0x19`, input4 `gsensor` | Android "Gravity sensor" reads ~(-0.3, 9.2, 3.4) m/s² |
| RTC | HYM8563 | i2c-2 `0x51` | `rtc_hym8563` |
| Wi-Fi | iComm/South Silicon Valley SSV6020C | SDIO `mmc2`, vendor `0x5653` device `0x2060` | Out-of-tree `ssv6x5x` module |
| GPU | Mali-400 (Utgard) | `10091000.gpu` | Vendor `mali400` r5 kernel driver |
| Keys | ADC keypad `rk29-keypad` | input2 | Power/reset |

PIR logging (`gpio-107` polled every 0.2 s from 13:50:58 for 2 min) showed real transitions:
hi → lo 13:52:11 → hi 13:52:24 → lo 13:52:47 → hi 13:52:53. Which level means "motion" is
not yet confirmed against a known wave.

Memory with Firefox open (`dumpsys meminfo`): Firefox ~370 MB PSS across processes; Android
itself ~150–200 MB (system_server 39 MB, SystemUI 20 MB, keyboard 10 MB, plus a long tail).
Background vendor apps include `com.adups.fota` (Adups OTA) and `com.cghs.stresstest`.

## Newer Android / WebView options (researched 2026-09-30)

- A generic Android 13 image won't work: it needs a Treble `vendor` partition (Android 8+), and
  this parameter table has none. Android 13 also needs a 4.14/4.19+ kernel, which means the
  same mainline work as Linux (DSI panel, CST2xx touch, SSV6020C Wi-Fi), with Mali-400 limited
  to `lima` GLES2. The most Rockchip seems to offer for RK312x is Android 8.1 Go on kernel 4.4
  (unverified).
- The r/immich "Frameo running Android 13+" thread is actually Android 6.0.1 with system
  WebView replaced by 106. Method: https://docs.immichkiosk.app/misc/frameo/ (replace
  `/system/app/webview/webview.apk`, delete `/system/app/webview/oat`, reboot).
- WebView 106 is the newest for Android 6 (Chromium M106 was the last to support API 23).
- Official source: LineageOS `android_external_chromium-webview_prebuilt_arm` commit
  `4b0ae494a7dd` ("Update Chromium Webview arm prebuilt to 106.0.5249.126", 2022-10-12),
  a plain blob (not LFS), 55,529,950 bytes, git blob SHA `95d3beade3a446a4bfe2b8086b91f215613e45f5`.
- This frame: `/system/app/webview/webview.apk` is 38,445,700 bytes (WebView 44.0.2403.119);
  `/system` has 983.5 MB free.

## WebView 106 installed (2026-09-30)

1. Downloaded the LineageOS blob above; git blob SHA matched. Signer is a generic
   `CN=Unknown` key (cert SHA-256 `32:A2:FC:74:…:D1:E0`).
2. Stock APK pulled to `backups/synergy-10x1/webview-44-stock.apk`
   (SHA-256 `ab29516040a831b0a0670177d6fb40662fea5e6486ef0a02f5a89a0c20a43adc`) and kept on the
   device as `/system/app/webview/webview.apk.bak`.
3. Replaced `webview.apk`, deleted `/system/app/webview/oat`, rebooted. `dumpsys package` then
   reported `versionName=106.0.5249.126`, but WebView logged
   `dlopen failed: can't read file "/system/vendor/lib": Is a directory` and
   `failed to create relro file`.
4. Cause: WebView 106 stores its libraries **compressed** (`Defl:N`) in the APK; stock 44 stored
   them uncompressed. Android 6 does not extract native libraries for `/system` apps, and
   `legacyNativeLibraryDir=/system/app/webview/lib` did not exist. The immichkiosk guide does not
   mention this step.
5. Fix: extracted `lib/armeabi-v7a/*.so` to `/system/app/webview/lib/arm/` (dirs 0755, files 0644,
   root). MD5s match the APK contents. After reboot, `RelroFileCreator` loads
   `/system/app/webview/lib/arm/libwebviewchromium.so` with no error.
6. Rendering test: Lightning 5.1.0 (`acr.browser.lightning`, F-Droid, hash verified; uses the
   system WebView) shows whatismybrowser.com as "Android WebView … Android 6 (Marshmallow)" with
   JavaScript enabled.

Undo: copy `webview.apk.bak` back over `webview.apk`, remove `/system/app/webview/lib` and
`/system/app/webview/oat`, reboot.

## Let's Encrypt roots added to the system CA store (2026-09-30)

WebView uses Android's system trust store (158 certs, dated 2024-09-19 in this build), which has
no ISRG roots. `https://valid-isrgrootx1.letsencrypt.org/` failed in WebView with "Certificate
is not trusted". Firefox is unaffected (bundled NSS store).

| File | Root | SHA-256 fingerprint |
| --- | --- | --- |
| `6187b673.0` | ISRG Root X1 | `96:BC:EC:06:26:49:76:F3:74:60:77:9A:CF:28:C5:A7:CF:E8:A3:C0:AA:E1:1A:8F:FC:EE:05:C0:BD:DF:08:C6` |
| `8794b4e3.0` | ISRG Root X2 | `69:72:9B:8E:15:A8:6E:FC:17:7A:57:AF:B7:17:1D:FC:64:AD:D2:8C:2F:CA:8C:F1:50:7E:34:45:3C:CB:14:70` |

- Downloaded from `letsencrypt.org/certs/`; file names are `openssl x509 -subject_hash_old`;
  contents are PEM plus `-text -fingerprint` output; installed in
  `/system/etc/security/cacerts/` as 0644 root.
- Gotcha: `/system` went read-only again between `cp` and `chmod`, leaving the files 0600
  (unreadable by apps). Re-ran `chmod` after a fresh remount.
- After the fix the test site loads with a valid padlock in WebView.
- whatismybrowser.com also warned once, although its root (USERTrust RSA, `35105088.0`) is present;
  the warning may come from a third-party resource on that page. Not investigated.

## Navigation bar (2026-09-30)

- Enabled with `qemu.hw.mainkeys=0` appended to `/system/build.prop` (original kept as
  `build.prop.bak`). After reboot a `NavigationBar` window exists.
- This firmware's SystemUI shows only volume down, Back, and volume up. Decompiled
  `NavigationBarView` (from the dex carved out of `priv-app/SystemUI/oat/arm/SystemUI.odex`)
  calls `getHomeButton().setVisibility(4)` and `getRecentsButton().setVisibility(4)`
  unconditionally; volume buttons are gated by `ro.rk.systembar.voiceicon=true`. No property
  or setting brings Home/Recents back; `setprop ro.target.product tablet` made no difference.
- Firefox requests a transparent navigation bar (`mLastSystemUiFlags=0xa600`), and this SystemUI
  draws white icons, so over light pages the bar looks missing even though `NavigationBarView` is
  `VISIBLE`. Firefox's dark theme (Settings → Customize → Theme → Dark) makes it readable.
- Proposed but not built: an app of our own that draws a Home button in the empty nav-bar slot
  (x 320–448, 48 px tall at the bottom in landscape). It would need `SYSTEM_ALERT_WINDOW` and
  `RECEIVE_BOOT_COMPLETED`; building it requires installing the Android SDK command-line tools.
- Lightning was added to the launcher dock by inserting a `favorites` row
  (`container=-101`, `screen=3`, `cellX=3`) into
  `/data/data/amirz.rootless.nexuslauncher/databases/launcher.db` with the launcher stopped;
  the original was kept as `launcher.db.bak`.

## Security review (2026-09-30)

| Finding | Evidence |
| --- | --- |
| Any app gets root silently | As Lightning's uid 10035, `/system/xbin/su -c id` returned `uid=0(root)`. No SuperSU manager app is installed, so nothing prompts. `daemonsu` starts at boot from `init.rockchip.rc`/`init.rk30board.rc` |
| Security patch 2016-07-05 | `ro.build.version.security_patch`; kernel 3.10.0 built 2024-09-19 |
| SELinux permissive | `getenforce`; `androidboot.selinux=permissive` |
| Adups FOTA running | `com.adups.fota` 5.28 in `/system/app/FotaUpdate`, uid 10019; servers `fota5p.adups.cn`, `fota5p.adups.com`; `ro.boot.vendor.overlay.theme=com.adups.fota.overlay` |
| Biu Frame cloud and push channel | `biu.biuframecloud.com`, `demo.biuframecloud.com`, `dev-firmware-update.shenjugroup.com`, hard-coded `http://161.189.79.192`, XMPP (`etherx.jabber.org/streams`, `xmpp.XmppService`). Runs as system uid 1000. Currently disabled |
| Other vendor apps | `android.rockchip.update.service`, `com.cghs.stresstest` (system uid), `com.DeviceTest` (system uid), `com.android.rk` (RkExplorer, system uid), `com.android.rk.mediafloat` (system uid), `com.android.apkinstaller` |
| Unexplained outbound connections | Two `CLOSE_WAIT` sockets to `119.28.184.101:443` (Tencent Cloud range) at 14:1x. A 60 s watch of `/proc/net/tcp{,6}` afterwards saw no external connections, so the owning uid is unknown |
| No Google Play Services | No `com.google.android.gms` or Play Store; the Google Calendar app cannot run |
| Network | Frame on its own Wi-Fi network; no listening TCP ports found; `service.adb.tcp.port` unset |

## Hardening applied (2026-09-30)

Decision: no further apps will be installed; the frame is for signing into websites in
Firefox or WebView. Root, the firewall, and `su` permissions were left as they are.

Disabled with `su -c "pm disable <pkg>"`:

| Package | What it is |
| --- | --- |
| `com.shenju.biuframe` | Biu Frame app, cloud and XMPP push (disabled earlier) |
| `com.adups.fota` | Adups OTA updater |
| `android.rockchip.update.service` | Rockchip update service |
| `com.cghs.stresstest` | Vendor stress test (system uid) |
| `com.DeviceTest` | Vendor hardware test (system uid) |
| `com.android.rk` | RkExplorer file manager (system uid) |
| `com.android.rk.mediafloat` | Floating media player (system uid) |

- `com.adups.fota` and `com.cghs.stresstest` are `PERSISTENT` system apps. After
  `pm disable` and a reboot, `ActivityManager` still logged
  `Start proc … for added application` for both.
- Fix: `su -c "pm hide com.adups.fota; pm hide com.cghs.stresstest"`. After the next reboot
  there were no vendor processes, `dumpsys package` shows `hidden=true enabled=2`, and there
  are no `Start proc` lines for either.
- Memory after hardening, idle on the launcher: Free RAM 688 MB, Used RAM 208 MB
  (`dumpsys meminfo`).
- Undo: `su -c "pm unhide <pkg>"` for the two hidden apps, then `su -c "pm enable <pkg>"` for
  each package above.

Not done (declined): restricting `su` to the shell group, iptables per-app firewall.

Remaining risks: any app can still get root silently; the 2016 security patch level; SELinux
is permissive; WebView 106 (2022) is older than Firefox 143 (2025), so Firefox is the better
choice for logins.

## Chromium 106 and full-screen kiosk (2026-09-30)

- APKMirror returns HTTP 403 to scripted downloads. Source used instead: Google's
  `chromium-browser-snapshots` bucket, `Android/1036832/chrome-android.zip` (2022-08-19,
  127 MB, MD5 matches the bucket's `++NiZWq6qMgZ5b9775jeQg==`). `REVISIONS` says
  `refs/heads/main@{#1036832}`, V8 10.6 (the version-106 codebase). `Android/` builds are 32-bit ARM.
- Installed `chrome-android/apks/ChromePublic.apk` (SHA-256
  `d0203c44b40cb3130c25cb009beaacf46faf7afc21cc081362db24c3fa6616f6`) as `org.chromium.chrome`,
  `versionName=106.0.5249.0`, `armeabi-v7a`, flagged `DEBUGGABLE`. This is a trunk build at the version-106
  branch point: it lacks the fixes that went into the version-106 stable releases, and has no Google sync or branding.
- First launch stops at "Chromium won't run without Google Play services". Workaround:
  `/data/local/tmp/chrome-command-line` = `_ --disable-fre --no-default-browser-check --no-first-run`
  plus `am set-debug-app --persistent org.chromium.chrome`. Chromium only reads the flags file
  when it is the debug app (or on a debuggable Android build).
- With the dashboard's `manifest.webmanifest` (`"display": "fullscreen"`) deployed, Chromium's
  ⋮ → **Install app** offered "Home HQ" and added a launcher icon through the older shortcut method (no Play
  services). The icon opens `org.chromium.chrome.browser.webapps.WebappActivity` at 1280×800 with
  no browser toolbar, status bar, or navigation bar. Swipe up from the bottom edge to show the navigation bar.
- A second "Home HQ" icon (a dark "H") is a Firefox shortcut created at 15:09 (`mozilla.components.pwa.category.SHORTCUT`);
  it opens in Firefox's `HomeActivity`.
- Engine note: Chromium 106 and system WebView 106 use the same Blink/V8 version.
- Exit problem: in the full-screen web app the navigation bar did not come back when swiped. The immersive flags are
  `0xaf06` (includes `IMMERSIVE`); touch range is 0–1280 × 0–800 at 160 dpi, so a swipe has to start
  within the bottom 24 px. The cause is not confirmed: both touch captures ran before the user saw the request to swipe
  (`getevent` output is buffered when piped; `cat /dev/input/event0` needs a `chmod` before `adb pull`).

## Custom WebView kiosk app (2026-09-30)

A separate dashboard project built its own kiosk app and installed it on the frame:

- `com.wesbos.homehq` ("Home HQ"): a full-screen WebView app that loads one self-hosted dashboard URL.
  It keeps the screen on, hides the status and nav bars, and forces landscape. It is not registered as
  a home app, but it does register for http/https links. Signed with the Mac's `~/.android/debug.keystore`.
- Built with the Android command-line tools from Homebrew (build-tools 34, platform 34). The same
  setup would also build the proposed nav-bar Home button overlay.
- Redrawing only the parts of the dashboard that change cut touch latency roughly in half on this
  hardware (e.g. a toggle went from 366–448 ms to 160–178 ms, measured in the Chromium 106 web app).

Kiosk candidates on the frame: the `com.wesbos.homehq` WebView app and the Chromium "Home HQ" web app. Neither
is the home app; Rootless Pixel Launcher still is.

### Kiosk chosen: `com.wesbos.homehq` (2026-09-30)

- Dashboard commit `dc1cb0b`: holding **two fingers still for 1.5 s** (`EXIT_HOLD_MS = 1500`)
  explicitly opens `amirz.rootless.nexuslauncher/com.google.android.apps.nexuslauncher.NexusLauncherActivity`
  and shows a toast. WebView remote debugging is off unless launched with `--ez debug true`, and
  the next normal launch turns it off. The kiosk is still not a home app.
- Independent check (this session): after a normal launch the only devtools socket in
  `/proc/net/unix` is Chromium's `@chrome_devtools_remote`. A raw two-finger `sendevent` hold of
  2.2 s moved focus from `com.wesbos.homehq/.MainActivity` to `NexusLauncherActivity`.
- Touch mapping (from the dashboard agent): the panel is rotated. Display (x, y) = raw
  ((800 − rawY) × 1.6, rawX × 0.625), so raw X = y ÷ 0.625 and raw Y = 800 − x ÷ 1.6.
- Home screen tidied through `launcher.db` (backup `launcher.db.bak2`): removed the Firefox shortcut
  (`mozilla.components.pwa.category.SHORTCUT`, the dark "H") and the Chromium web app shortcut (house icon), and
  added one "Home HQ" app icon for `com.wesbos.homehq/.MainActivity` on page 1, row 2. Tapping it opens the kiosk.
- Launcher gotcha: `screen` is a `workspaceScreens._id`, not a page number, and row 0 of page 1
  (`screen=0`) belongs to the date widget. An icon placed there is deleted silently when the launcher reloads.
- Chromium (`org.chromium.chrome`) is still installed with its flags file and debug-app setting,
  and it keeps `@chrome_devtools_remote` open.

## Stock apps

- Home app: `com.shenju.biuframe` ("Biu Frame"; clock screen is `ui.TimeCalendarActivity`).
- No browser and no other launcher. System WebView is `44.0.2403.119`.
- Stock Android Settings opens normally with `am start -a android.settings.SETTINGS`.

## Installed apps (2026-09-30, via `adb install`)

| App | Version | Source | Check |
| --- | --- | --- | --- |
| Firefox (`org.mozilla.firefox`) | 143.0.4, armeabi-v7a | `archive.mozilla.org/pub/fenix/releases/143.0.4/` | Signer `CN=Release Engineering, O=Mozilla Corporation`, cert SHA-256 `A7:8B:62:A5:…:9B:04` |
| Rootless Pixel Launcher (`amirz.rootless.nexuslauncher`) | 3.9.1 | F-Droid `amirz.rootless.nexuslauncher_30911.apk` | SHA-256 matches F-Droid index |

- Firefox 143 is the last Firefox for Android 5–7; Firefox 144 raised the minimum to Android 8.
  Chrome's last Android 6 release was M106. Firefox 143 loads pages and identifies as
  "Firefox 143 on Linux".
- Biu Frame is still the default home app. The launcher was opened with "Just once"; pressing
  Home shows a chooser until "Always" is picked.
- The launcher's Google search bar needs the Google app, which is not installed.

## Memory tuning (2026-09-30)

1 GB RAM (`MemTotal: 1022160 kB`) with a stock 128 MB lzo zram swap (`zramsize=134217728` in
`fstab.rk30board`). Opening syntax.fm in Firefox left ~41 MB free and ~37 MB of swap free, logged
`ANR in org.mozilla.firefox`, and the Firefox process was replaced.

- zram is now 512 MB with 4 compression streams (`max_comp_streams`; RK3126 is quad-core).
- Script: `/system/su.d/50zram` (copy in `scripts/biuframe-su.d-50zram`). `/system` has no
  `verify` flag in fstab; it was remounted read-write for each change and back to read-only.
- SuperSU's `su.d` loop did **not** run it at boot (no `su.d Running` log line; swap came back at
  128 MB). The script works when run by hand.
- Working hook: appended `[ -x /system/su.d/50zram ] && /system/su.d/50zram` to
  `/system/bin/install-recovery.sh` (original kept as `install-recovery.sh.bak`). The
  `flash_recovery` service runs it as root after `swapon_all` in `on fs`. Verified after reboot:
  `/proc/swaps` shows 524280 KB.
- `install-recovery.sh` logs `Installing new recovery image: failed` on every boot; recovery is
  left unchanged.
- Undo: restore `install-recovery.sh.bak`, remove `/system/su.d`, reboot.

## Biu Frame disabled (2026-09-30)

`com.shenju.biuframe` 10.1.1 lives in `/system/app/Biuframe` and uses
`sharedUserId android.uid.system` (uid 1000). `am force-stop` does not stick: it restarted within
2 s from its own alarms (`receiver.BootReceiver`) and `receiver.NetworkCallback`. Services include
`xmpp.XmppService`, `service.PushManagerService`, `service.MotionService`, `service.ZeroTimeService`.

- Disabled with `su -c "pm disable com.shenju.biuframe"`; no processes after 20 s.
- Rootless Pixel Launcher is now the only home app.
- Undo: `su -c "pm enable com.shenju.biuframe"`.

Writes so far: app installs to `/data` (Firefox, Rootless Pixel Launcher, Lightning), package
states (seven disabled, two of them also hidden; see Hardening applied), the launcher database, and
file changes in `/system` (`su.d/50zram`, `bin/install-recovery.sh`, `app/webview/`, two CA
certs, `build.prop`). No partitions have been flashed.
