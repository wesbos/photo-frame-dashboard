# Frameo 10.1" "102K" (ALONG, Allwinner A33 `astar_xr819`, Android 6.0.1)

Record of one unit, tested on 2026-10-14. Host: macOS 27 on an Apple M2 Pro MacBook Pro.
Observations are kept separate from guesses. The serial, MAC addresses and eMMC CID are left
out; they stay in the owner's ignored `backups/` folder.

**Short version:** USB ADB is on out of the box and connected with no prompt and no key on
file. The shipped `/system/bin/su` gives UID 0 with `su 0 <cmd>`. WebView 106 is preinstalled, so
the [kiosk](../dashboard/kiosk/README.md) runs as is. No boot patch, FEL, SD card or Wi-Fi was
needed, and nothing was written to `/system` or the boot partition.

**Same name, different board.** This frame reports `product:102K model:Digital_Photo_Frame`. The
Rockchip RK3326 [Frameo "Digital Photo Frame 102k" (KJM)](frameo-rk3326-s101.md) has the same
model name and is sold under the same 102k name. Check the fingerprint before you follow either
page.

**Also sold as 112K.** A second unit, sold as a "112K", reports the same `102K` product, firmware
and fingerprint and has a byte-identical boot partition. It differs in eMMC size. See
[Units sold as 112K](#units-sold-as-112k).

**On a Mac, unplug the DC adapter first.** A fourth unit, from the same Amazon.ca listing, only
connected to a Mac with its DC adapter unplugged. See
[Unit 4](#unit-4-amazonca-macos-host).

## Identity

| Item | Observed value |
| --- | --- |
| Listing | [Amazon.ca B088NHSVJN](https://www.amazon.ca/dp/B088NHSVJN), "Frameo 10.1 Inch WiFi Digital Picture Frame, 1280x800 HD IPS Touch Screen Photo Frame Electronic, 32GB Memory, Auto-Rotate, Wall Mountable". Listings may change hardware |
| `adb devices -l` | `product:102K model:Digital_Photo_Frame device:102K` |
| Brand / manufacturer | `ro.product.brand=ALONG`, `ro.product.manufacturer=Allwinner` |
| Firmware | `ro.build.display.id=102K-MS33-HK9365-frameo_V1.29.13_NOPMU_20260113` |
| Fingerprint | `Allwinner/astar_xr819/astar-xr819:6.0.1/MOB30R/20260113:eng/test-keys`. `ro.build.type` is `user` even though the fingerprint says `eng` |
| SoC | Allwinner A33 (`ro.board.platform=astar`, `ro.hardware=sun8i`, `ro.sys.cputype=QuadCore-A33`), Cortex-A7 (`CPU part 0xc07`), 32-bit ARMv7 |
| Board | `ro.product.board=exdroid` |
| Kernel | Linux 3.4.39, `#109 SMP PREEMPT`, built 2026-01-13 |
| Android | 6.0.1, API 23, security patch 2018-08-05 |
| Display / GPU | 1280x800, density 160, `ro.sf.rotation=90`. SurfaceFlinger: `ARM, Mali-400 MP, OpenGL ES 2.0` |
| RAM / swap | 1,027,036 kB; zram swap 327,676 kB |
| Storage | eMMC `mmcblk0`, 61,079,552 sectors (30,539,776 KiB); `/data` 26.7 GB |
| Wi-Fi | `xradio_wlan` / `xradio_core` modules (XR819, as the platform name says). Never used: the frame was never put on a network |
| Power | No `/sys/class/power_supply` entries. `dumpsys battery`: AC powered, no battery present. The build name says `NOPMU` |
| Sensors / input | `mir3da` accelerometer, SoC temperature sensor, `gslX680new` touch. USB Ethernet modules (`asix`, `cdc_ether`, `mcs7830`, `qf9700`) are loaded; not tested |
| Frameo | `net.frameo.frame` v1.29.13 (60080), in `/system/priv-app/Manufacturertest` |
| WebView | `com.android.webview` 106.0.5249.126 in `/system/app/webview` |
| SELinux | Permissive |
| Time zone | `ro.frameo.default.timezone` and `persist.sys.timezone` are `America/New_York` in `/system/build.prop` |

### Closest relatives in this repo

- [Uhale 114KZ](uhale-114kz.md): the same `astar_xr819` fingerprint family and `HK9365` in the
  firmware string. That unit had no usable USB ADB and needed a boot patch.
- [Pastigio / SOMY ZC002](pastigio-zc002.md): the same `astar_xr819` platform, and `MS33` in this
  firmware string (the Pastigio PCB is `MS33-V2.0`). The partition starts below are the same as
  the SOMY ZC002's, through `/data` at sector 4268032. The kernel size (10,165,848 bytes) and the
  stock `sepolicy` SHA-256 (`e538aed0f5a5b93935b897d848ec75477ee5eb8f5bcfd42ff16ce5579ce01e49`)
  match the Pastigio's stock values. `/sbin/adbd` does not (see [Boot image](#boot-image)), and
  ZC002 units stay `unauthorized` over USB while this one doesn't.

Guess, not verified: the ADB difference from the ZC002 is in this build's `adbd`.

## USB

| Host side | Cable | Result |
| --- | --- | --- |
| Mac, first attempt | Not recorded | Nothing enumerated |
| USB-A port on a USB hub on the Mac | USB-A to USB-C | Enumerates as `1f3a:1001`, manufacturer `USB Developer`, product `Android`, 480 Mb/s. `adb devices` showed `device` at once |

The owner replugged between the two attempts. What changed was not recorded, so this unit does
not show whether USB-C to USB-C fails here. The USB-A to USB-C cable through a hub is the one that
worked. Whether the DC adapter was plugged in during the first attempt was not recorded; on
[unit 4](#unit-4-amazonca-macos-host) that alone stopped the Mac from connecting.

## ADB

- `/system/build.prop`: `persist.sys.usb.config=adb`, `ro.adb.secure=1`,
  `persist.service.adb.enable=1`. `/default.prop` in the boot ramdisk: `ro.secure=1`,
  `ro.debuggable=0`, `persist.sys.usb.config=none`. At runtime `sys.usb.config=adb` and
  `sys.usb.state=adb`; `settings get global adb_enabled` is `1`.
- `adbd` runs as `shell`, context `u:r:adbd:s0`. `adb shell id` is UID 2000. `adb root` was not
  tried.
- **No ADB key is on file.** There is no `/adb_keys` in the boot ramdisk, and
  `/data/misc/adb/` exists (`system:shell`, mode `2750`) but is empty: no `adb_keys` file.
- `com.android.systemui` ships disabled (listed by `pm list packages -d`; nothing in this session
  disabled it), so there is no status or navigation bar and nowhere for an "Allow USB debugging"
  prompt to appear.
  `dumpsys usb` prints no "USB Debugging State" section.
- Even so, the Mac got `device` at once, and again after a frame reboot, with no key stored
  anywhere. **ADB on this unit appears to skip the key check.** Not tested with a second computer.
  Assume any computer the frame is plugged into gets a root shell.
- No network ADB listener: `service.adb.tcp.port` is empty, and `netstat -ltn` shows no `5555`
  (only the `adb reverse` port, see below). The frame was never on Wi-Fi, so ADB over the network
  is untested.
- The frame booted to Frameo's first-run language screen. Frameo's own ADB toggle was never
  needed or tried.

## Root

- `/system/bin/su` is setuid root (`-rwsr-sr-x root root`, 17,980 bytes). There is no
  `/system/xbin/su` and no `daemonsu`.
- `adb shell su 0 id` gives `uid=0(root)` with context `u:r:shell:s0`. `su -c id` fails with
  `invalid uid/gid '-c'`, so use `su 0 <cmd>` rather than the `su -c` check in the README's phase
  map.
- `su 0` keeps only `CAP_SETUID` and `CAP_SETGID` (`CapBnd: ffffffe0000000c0`, the same bounding
  set as `adbd`), as on the [second Pastigio unit](pastigio-zc002.md#su-0-from-adb-has-no-capabilities)
  and the [Uhale 114KZ](uhale-114kz.md#uid-0-does-not-provide-all-root-capabilities). Root can't
  open files it doesn't own:
  - `su 0 dd` of `misc` (`system:system`, `brw-rw----`) and `frp` (`system:system`, `brw-------`)
    gives `Permission denied`. SELinux is permissive, so this is file ownership, not SELinux.
    `su 1000 dd` (UID `system`) reads both.
  - `su 0 ls /data/misc/adb` gives `Permission denied`; the plain shell user can list it through
    the `shell` group.
- `su 0 pm disable` works. Remounting `/system` read-write was not tried.

`su` is setuid with no manager app and no prompt, so treat every app on this frame as if it has root.

## Partition table

eMMC `mmcblk0`, 512-byte sectors, from `/sys/block/mmcblk0/mmcblk0p*/start` and
`/dev/block/by-name`. `/data` ends exactly at the end of the eMMC.

| Partition | Name | Start | Size (sectors) |
| --- | --- | --- | --- |
| p2 | bootloader | 73728 | 65536 |
| p5 | env | 139264 | 32768 |
| p6 | boot | 172032 | 32768 |
| p7 | system | 204800 | 2097152 |
| p8 | misc | 2301952 | 32768 |
| p9 | recovery | 2334720 | 65536 |
| p10 | cache | 2400256 | 1572864 |
| p11 | metadata | 3973120 | 32768 |
| p12 | private | 4005888 | 32768 |
| p13 | frp | 4038656 | 1024 |
| p14 | empty | 4039680 | 31744 |
| p15 | alog | 4071424 | 163840 |
| p16 | media_data | 4235264 | 32768 |
| p1 | UDISK (`/data`, ext4) | 4268032 | 56811520 |

## Boot image

Stock, read before any change and never written.

| Item | Value |
| --- | --- |
| Boot partition (16 MiB) SHA-256 | `c7e99c1d2f41c37320c1ab04baf2784ce398ece39e500faa6b48ee7e2826d5bc` |
| Boot partition MD5 | `a87ed8b311a24e5dee5f7894ca954ac0`, the same as `su 0 md5sum /dev/block/by-name/boot` on the frame |
| Header | `ANDROID!`, page 2048, kernel 10,165,848 bytes, ramdisk 4,734,754 bytes, no second stage, cmdline `vmalloc=384M` |
| Android image (first 14,903,296 bytes) SHA-256 | `8af0c638d514d633e00c1bd9c274dd6c9c07690697bd2d574c32a849e3536b84`. The rest of the partition is zeros |
| `/sbin/adbd` SHA-256 | `aad459e841ce03e7eae0add799ac24089c06d786c20fec1fe9148cc2f61b38e3` (the ZC002's is `b5ec816b…`) |
| `sepolicy` SHA-256 | `e538aed0f5a5b93935b897d848ec75477ee5eb8f5bcfd42ff16ce5579ce01e49`, the same as the ZC002 stock |

In `init.rc`, `adbd` is `disabled` and started by the `sys.usb.config` triggers in
`init.sun8i.usb.rc`.

## Backup

Every partition except userdata and cache was read as root over ADB:

```sh
adb exec-out "su 0 dd if=/dev/block/by-name/<name> bs=1048576" > <name>.img
```

MD5 of boot, bootloader and env matched `su 0 md5sum` on the frame. `misc` and `frp` were missed
(see [Root](#root)); `su 1000 dd` reads them. This is MD5 on three partitions, not the
README's full [backup rule](../README.md#rules-we-learned-the-hard-way). Nothing was written that
needs it: all changes below are in `/data`.

## Software of interest

| Package | Location | Notes |
| --- | --- | --- |
| `net.frameo.frame` v1.29.13 | `/system/priv-app/Manufacturertest` | Frameo, and the only **HOME** activity out of the box |
| `com.adups.fota` 5.28 | `/system/app/FotaUpdate` | Adups FOTA. `/system/build.prop` has `ro.fota.oem=alongA33_6.0`, `ro.fota.device=102K`, `ro.fota.version` = the firmware string |
| `com.along.table` V2.2.8 | `/system/app/AlongTestApk` | Vendor test app |
| `com.along.factorytest` | `/system/app/AlongFactoryTest` | Factory test |
| `com.android.agingtest` | `/system/priv-app/AgingTest` | Aging test |
| `com.softwinner.dragonfire`, `dragonaging`, `dragonphone` | `/system/app` | Allwinner factory test apps |
| `com.softwinner.fireplayer` 2.3.10.33 | `/data/app` | Video player. Guess: copied in on first boot from `/system/preinstall/VideoPlayer` |
| `com.android.systemui` | `/system/priv-app/SystemUI` | Present, disabled out of the box |
| `com.android.inputmethod.latin`, `jp.co.omronsoft.openwnn` | `/system/app` | Keyboards |

## What was set up (approved writes, all in `/data`)

1. Built `dashboard/kiosk` with `build.sh` on macOS (Homebrew `openjdk@17`, `android-commandlinetools`
   with build-tools 34.0.0 and platform 34) and installed it with `adb install -r`. It built and
   installed without problems. This owner's copy has a few local changes (default URL, label, and
   the keyboard flags below).
2. Saved the URL with `am start -n com.wesbos.homehq/.MainActivity --es url <url> --ez home true`,
   then `su 0 pm disable net.frameo.frame` and `su 0 pm disable com.adups.fota`, before the
   frame was ever online. With Frameo disabled the kiosk is the only Home app, since Android 6 has
   no `cmd package set-home-activity`. After a reboot the frame starts straight into the kiosk.
3. `settings put global stay_on_while_plugged_in 7`.

The way back on this unit is USB ADB with `su 0`, which is on from `/system/build.prop`. A check
by hand that the kiosk menu reaches Android Settings was not recorded.

### No Wi-Fi: the page comes over the USB cable

The page is served on the Mac's loopback (`127.0.0.1:7681`) and reaches the frame through
`adb reverse tcp:7681 tcp:7681`. This works. A replug, a frame reboot or an `adb kill-server`
drops the mapping, so a loop on the Mac re-applies it.

### Kiosk notes

- The page is a [ttyd](https://github.com/tsl0922/ttyd) / xterm.js terminal. xterm.js's canvas
  renderer drew garbled glyph fragments on this frame; the DOM renderer
  (`-t rendererType=dom`) is fine. Guess, not verified: the Mali-400 GPU.
- xterm.js focuses a hidden textarea, so the LatinIME keyboard popped up over the dashboard.
  Adding `WindowManager.LayoutParams.FLAG_ALT_FOCUSABLE_IM` to the kiosk window plus
  `setSoftInputMode(SOFT_INPUT_STATE_ALWAYS_HIDDEN)` fixed it. The flag alone left a keyboard
  raised by the previous window on screen. This change is in the owner's local kiosk build, not
  in this repo.

## Undo

| Change | Undo |
| --- | --- |
| Frameo and FOTA disabled | `adb shell su 0 pm enable net.frameo.frame`, `adb shell su 0 pm enable com.adups.fota` |
| Kiosk as Home | `adb shell am start -n com.wesbos.homehq/.MainActivity --ez home false`, or `adb uninstall com.wesbos.homehq` |
| Screen always on | `adb shell settings put global stay_on_while_plugged_in 0` (the value before the change was not recorded) |
| Page over USB | `adb reverse --remove tcp:7681`, and stop the loop on the Mac |

Nothing was written to `/system` or the boot partition.

## Not tested

- A second computer with a fresh ADB key, to confirm there is no key check.
- Wi-Fi, network ADB, and what Frameo or Adups do once online.
- A USB-C to USB-C cable, and why the first plug-in enumerated nothing.
- Remounting `/system` with `su 0`, and whether `su` from an app keeps full capabilities.
- How often this listing ships this board. A unit with the same ASIN from Amazon México was the
  [KJM RK3326 board](frameo-rk3326-s101.md#second-unit-amazon-mexico).

## Units sold as 112K

Two more units were sold as a Frameo "112K". Both are the same build as the first unit.

### Unit 2 (Windows host)

A different unit, sold as a Frameo "112K", read on 2026-10-16. Host: Windows 11 with Android
platform-tools. The listing was not recorded. As above, the serial, MAC addresses, eMMC CID and
Wi-Fi details are left out.

**Short version:** it is the same build as the unit above, on a smaller eMMC. USB ADB, `su 0`, the
kiosk build and the kiosk as Home all worked the same way, from a Windows host this time.

#### Same as the first unit

- `adb devices -l`: `product:102K model:Digital_Photo_Frame device:102K`, not 112K. USB
  `1f3a:1001`.
- Firmware `102K-MS33-HK9365-frameo_V1.29.13_NOPMU_20260113` and fingerprint
  `Allwinner/astar_xr819/astar-xr819:6.0.1/MOB30R/20260113:eng/test-keys`, with
  `ro.build.type=user`.
- Boot partition SHA-256 `c7e99c1d2f41c37320c1ab04baf2784ce398ece39e500faa6b48ee7e2826d5bc`
  (MD5 `a87ed8b311a24e5dee5f7894ca954ac0`), the same as in [Boot image](#boot-image). `/sbin/adbd`
  in its ramdisk has MD5 `5b6d9f41e579e0ad068c7a1b21824139` and SHA-256
  `aad459e841ce03e7eae0add799ac24089c06d786c20fec1fe9148cc2f61b38e3`, the same as the first unit's.
- 1280x800, density 160, `ro.sf.rotation=90`, about 1 GB RAM. SELinux permissive. WebView
  106.0.5249.126, Frameo v1.29.13 (60080), Adups FOTA 5.28. SystemUI disabled out of the box. No
  battery (`present: false`, AC powered).
- USB ADB was on out of the box: `device` at once, no prompt, and no `adb_keys` on file. This is a
  second computer and a second unit with no key check, not the same unit with a fresh key.
- `su 0 <cmd>` gives UID 0 with only `CAP_SETUID`/`CAP_SETGID`, as in [Root](#root). `su 1000`
  read the partitions `su 0` could not.
- No TCP 5555 listener.

#### Different from the first unit

- **Smaller eMMC:** 60,620,800 sectors, against 61,079,552. Every partition start and size in the
  [partition table](#partition-table) is the same except UDISK (`/data`), which is
  56,352,768 sectors from 4268032 and still ends at the end of the eMMC.
- `/system/build.prop` has `ro.config.low_ram=true`. There is no
  `/system/etc/lowmem_package_filter.xml`. The first unit's write-up does not mention this
  property; unit 3 has it too. Unlike the
  [Denver PFF-1015](denver-pff-1015.md), the kiosk process survived 15 s in Android Settings and
  Home returned to it.

#### Backup

Every partition except userdata and cache was read with `su 0 dd`, and `su 1000 dd` for the
partitions `su 0` can't open (see [Root](#root)). MD5 matched between the frame and the PC for
every partition, and 1 MiB of `system` at offset 512 MiB was read again and matched.

#### What was set up (approved writes, all in `/data`)

1. Before any change, the owner completed Frameo's first-run setup and joined Wi-Fi with Adups and
   Frameo still enabled, then removed the network about 40 minutes later. No update had been
   downloaded: Adups showed `isupgrade=1` with an empty download path, and Frameo's update folder
   was empty.
2. `su 0 pm disable com.adups.fota`.
3. Built `dashboard/kiosk` with `build.ps1` on Windows 11 (Microsoft OpenJDK 17, build-tools 34,
   platform 34; debug-signed). It built and installed with no changes. The default URL was the
   hosted demo, `https://home-dashboard.wesbos.workers.dev/`.
4. Kiosk set as Home with `--ez home true`, then `su 0 pm disable net.frameo.frame`. After a
   reboot the frame started in the kiosk (`mFocusedActivity=com.wesbos.homehq/.Home`), and
   `package-restrictions.xml` had `enabled=2` for Frameo. Both disables held across the reboot.
5. With no navigation bar (SystemUI disabled), the kiosk's **Home HQ navigation** accessibility
   service was enabled. The setting survived a reboot; the owner had not yet confirmed the floating
   Back/Dashboard buttons appear outside the kiosk.
6. `settings put global stay_on_while_plugged_in 7` (it was `0`).

The frame then went back on Wi-Fi. The owner opened Wi-Fi settings from the kiosk's two-finger
menu by hand. Opening Android Settings from the menu was not separately checked.

Undo is as in [Undo](#undo), plus, for the accessibility service,
`adb shell settings put secure enabled_accessibility_services null` and
`adb shell settings put secure accessibility_enabled 0` (both were unset before).

#### Not tested on this unit

- What Frameo or Adups do online with updates disabled over a longer period.
- Whether the floating navigation buttons show outside the kiosk.
- Network ADB, and which USB cable types enumerate (the cable used was not recorded).

### Unit 3 (Amazon Australia, Windows host)

Record of one more unit, tested on 2026-10-19 from Windows 11 (platform-tools ADB, Git Bash and
PowerShell). It was sold on Amazon Australia as "Frameo WiFi Digital Picture Frame - 10.1 Inch
1280x800 HD IPS Touch Screen". The box says **Model: 112K**, and Frameo's About screen says
"Digital Photo Frame 112K". [#144](https://github.com/wesbos/photo-frame-dashboard/pull/144)
reports another 112K; this section adds what that unit and the first unit did not test. Unlike
the first unit, this one went **online on Wi-Fi**, with internet blocked at the router.

#### Identity

The same build as the first unit:

| Item | Observed value |
| --- | --- |
| Firmware | `102K-MS33-HK9365-frameo_V1.29.13_NOPMU_20260113`, the same |
| Fingerprint | `Allwinner/astar_xr819/astar-xr819:6.0.1/MOB30R/20260113:eng/test-keys`, the same |
| Boot partition SHA-256 | `c7e99c1d2f41c37320c1ab04baf2784ce398ece39e500faa6b48ee7e2826d5bc`, **identical** to the first unit |
| eMMC | `mmcblk0` 30,539,776 KiB (61,079,552 sectors), the same as the first unit (the #144 unit is smaller) |
| `ro.config.low_ram` | `true`, as on the #144 unit |
| Frameo / WebView | `net.frameo.frame` v1.29.13 (60080); `com.android.webview` 106.0.5249.126 |

#### ADB and root

- Frameo Settings → About → **Beta Program** was turned on first. The "ADB access" row never
  appeared, but USB ADB was already `device`, with no prompt, from a Windows host with its own
  key. That makes **two different computers with no key check**, though on two different units.
- Cable: USB-A to USB-C from the PC (exact cable not recorded).
- `su 0 id` gives `uid=0(root)` with `CapBnd: ffffffe0000000c0`. `su 1000` has an empty
  effective set. Effects seen on this unit:
  - `iptables` fails with `can't initialize iptables table 'filter': Permission denied (you must be root)`.
    No `CAP_NET_ADMIN`.
  - `su 0` cannot list `/data/misc/wifi`. `su 1010` (the `wifi` UID) can.
  - `ndc` talks to `netd`, which has full capabilities: `su 0 ndc firewall enable blacklist` and
    `su 0 ndc firewall set_uid_rule none <uid> deny` both answer `200 ... succeeded` (lost at
    reboot). `ndc firewall is_enabled` answered `400` before and after, so it is not a useful check.
  - There is no `wpa_cli`. Wi-Fi was joined on the touchscreen
    (`am start -a android.settings.WIFI_SETTINGS`).
  - **Toybox `sed -i` corrupted the file it edited:** each edited line became `<new text>\0<old text>`.
    Don't edit app files on this frame with `sed -i`.
- With `su 1000` the backup read every partition, `misc` and `frp` included. Each image's SHA-1
  matched `su 1000 sha1sum` on the frame, each size matched `/sys/class/block/<dev>/size`, and no
  image ended in `0xCC` filler. `boot` and `recovery` start with `ANDROID!`.

#### Wi-Fi and the network

- The XR819 radio is 2.4 GHz only. It joined a WPA2 2.4 GHz network and got its DHCP reservation.
- **No TCP listeners at all while on Wi-Fi.** `/proc/net/tcp` and `tcp6` show no `LISTEN` sockets,
  so there is no `5555`. `service.adb.tcp.port` and `persist.adb.tcp.port` are empty.
- IPv6: only unique-local `fd..` addresses and no IPv6 default route.
  `ping6 2001:4860:4860::8888` gives `Network is unreachable`.
- `su 0 pm disable net.frameo.frame` while on Wi-Fi did **not** drop Wi-Fi (unlike the
  [RK3326 102k](frameo-rk3326-s101.md)).
- Frameo was blocked by the router's internet block, plus the `ndc` rule above. Its only socket was
  `SYN_SENT` to a Google address on port 443, which never connected.
- When Wi-Fi went down, `com.softwinner.dragonfire` started a `com.doc.documents` process from
  `DocServiceReceiver`, which died a second later. Not analysed.

#### No internet: Android 6 can hang waiting for NTP

With internet blocked, anything that calls `NetworkStatsManager.querySummaryForDevice` can hang
**forever**. Thread dumps (`kill -3`, after `su 1000 mkdir /data/anr`) of the app and of
`system_server` showed the binder call waiting in `NetworkStatsService.openSessionForUsageStats`
→ `performPoll` → `NtpTrustedTime.forceRefresh` → `SntpClient.requestTime`. That is an NTP
request that never gets an answer. On this unit it made a kiosk app's status endpoint time out on
every call. A reboot was needed to clear the calls that were already stuck.

Fix: point Android at a local NTP server and shorten the timeout. This router answered NTP.

```sh
adb shell settings put global ntp_server <router-ip>
adb shell settings put global ntp_timeout 5000
# undo: adb shell settings delete global ntp_server; adb shell settings delete global ntp_timeout
```

After a reboot the same call returned in 0.1 to 0.3 s. Check first that your router answers
NTP; not every router does.

#### Time zone

`persist.sys.timezone` was `America/New_York`, as on the first unit. `su 1000 setprop
persist.sys.timezone <local zone>` changed it, and it survived reboots
(undo: `su 1000 setprop persist.sys.timezone America/New_York`).

#### Kiosk

- **Building on Windows with JDK 21:** `build.ps1` failed at `d8` (build-tools 34.0.0) with
  `NullPointerException: Cannot invoke "String.length()"` on `MainActivity$1.class`. The only JDK
  on that PC was Android Studio's JBR 21; the README asks for JDK 17. A copy of the script with
  `javac --release 8` and `d8` from build-tools **36.0.0** built a working APK. The #144 unit
  built unchanged with JDK 17.
- Set up as in the first unit:
  `am start -n com.wesbos.homehq/.MainActivity --es url <url> --ez home true`, with
  Frameo, Adups and the vendor test apps (`com.along.table`, `com.along.factorytest`, `com.android.agingtest`) disabled. The kiosk was the only Home app, so there was no chooser.
- Navigation service:
  `pm grant com.wesbos.homehq android.permission.WRITE_SECURE_SETTINGS`, then
  `settings put secure enabled_accessibility_services com.wesbos.homehq/com.wesbos.homehq.NavigationService`
  and `settings put secure accessibility_enabled 1` (both were `null` before). **The floating Back
  and Dashboard buttons appeared** over Android's Wi-Fi settings after a reboot, and Dashboard
  returned to the kiosk.
- Reboot: `sys.boot_completed` after about 20 s, then the dashboard (a Home Assistant page) about
  45 s later.
- Before the kiosk, Fully Kiosk Browser 1.61.4 was tried. It runs on Android 6, but it is the Home
  app only with Kiosk Mode on, and its Remote Admin is a PLUS feature. With Kiosk Mode turned off it
  disabled its own Home components, and with Frameo also disabled the frame booted to a black
  screen. It is disabled on this unit, not uninstalled.

#### Power

USB-C power alone works: the owner ran the frame with no barrel jack (supply not recorded).
Android reports `AC powered: true` either way, which is consistent with `NOPMU`.

#### Undo (this unit)

| Change | Undo |
| --- | --- |
| Frameo, Adups, `com.along.table`, `com.along.factorytest`, `com.android.agingtest` disabled | `adb shell su 0 pm enable <package>` |
| Kiosk as Home, navigation service | `am start -n com.wesbos.homehq/.MainActivity --ez home false`; `pm revoke com.wesbos.homehq android.permission.WRITE_SECURE_SETTINGS`; `settings delete secure enabled_accessibility_services`; `settings put secure accessibility_enabled 0` |
| NTP server and timeout | `settings delete global ntp_server`; `settings delete global ntp_timeout` |
| Time zone | `su 1000 setprop persist.sys.timezone America/New_York` |
| `/data/anr` created | `su 1000 rm -r /data/anr` |
| Screen always on | `settings put global stay_on_while_plugged_in 0` (it was `0` before) |

Nothing was written to `/system` or the boot partition.

## Unit 4 (Amazon.ca, macOS host)

A second unit from the same [Amazon.ca B088NHSVJN](https://www.amazon.ca/dp/B088NHSVJN) listing as
the first, tested on 2026-10-29. Host: macOS 26.5.2 on an Apple M5 Pro MacBook Pro, Homebrew
`adb`. The serial, MAC addresses, eMMC CID and Wi-Fi details are left out.

**Short version:** the same build as the first unit, on a third eMMC size. What is new is the USB
connection: **with the frame's DC adapter plugged in, the Mac never turned its USB port on.** With
DC unplugged, the Mac powered the frame over USB and ADB connected.

### Identity

| Item | Observed value |
| --- | --- |
| `adb devices -l` | `product:102K model:Digital_Photo_Frame device:102K`, USB `1f3a:1001` |
| Firmware | `102K-MS33-HK9365-frameo_V1.29.13_NOPMU_20260113`, the same |
| Fingerprint | `Allwinner/astar_xr819/astar-xr819:6.0.1/MOB30R/20260113:eng/test-keys`, `ro.build.type=user`, the same |
| Boot partition SHA-256 | `c7e99c1d2f41c37320c1ab04baf2784ce398ece39e500faa6b48ee7e2826d5bc`, **identical** to the first unit |
| eMMC | 61,341,696 sectors, larger than both earlier sizes (61,079,552 and 60,620,800). Every partition start and size in the [partition table](#partition-table) is the same except UDISK (`/data`): 57,073,664 sectors from 4268032, ending at the end of the eMMC |
| `ro.config.low_ram` | `true`, as on units 2 and 3 |
| Frameo / WebView | `net.frameo.frame` v1.29.13; `com.android.webview` 106.0.5249.126. SELinux permissive |

### USB and power on a Mac

| Setup | Result |
| --- | --- |
| USB-C to USB-C cable, frame on its DC adapter | Nothing enumerated. The Mac logged a failed connection attempt about every half second for about 20 minutes. Not retried with DC unplugged |
| Mac USB-C port → USB-C-to-USB-A adapter → USB-A-to-USB-C data cable, frame on its DC adapter | Nothing enumerated, in two different ports. The Mac never turned the port on. Instead `AppleHPM` logged `LDCM Interrupt triggered` (its liquid-detection check) about every 31 s. A USB flash drive in the same adapter and port enumerated at once |
| The same adapter and cable, DC unplugged | The Mac powered the frame, which booted. It enumerated as `1f3a:efe8` for about 3 s, then as `1f3a:1001` (`Android`) 6 s later, both at 480 Mb/s |

- macOS blocked both devices at first. The log showed `device functionality blocked by transport
  restrictions` until the owner allowed the accessory on the Mac. Then `adb devices` showed
  `device`, with no prompt on the frame.
- The frame ran on the Mac's USB power alone for the whole session, including the backup and the
  kiosk setup.
- `1f3a:efe8` is Allwinner's FEL ID. It showed up once, during the boot from USB power. Not
  investigated.

Guess, not verified: with DC in, the frame puts 5 V on its own USB VBUS, and the Mac won't turn on
a port that already has voltage on it. Nothing was measured. The same cause may explain the USB-C
to USB-C failure here.

On this unit and this Mac: unplug the DC adapter before you connect USB, and unplug USB before you
plug DC back in. Windows and Linux hosts, and powered hubs, were not tried with DC in.

### Out of the box

- Never on Wi-Fi; Frameo on its first-run language screen.
- `pm list packages -d` listed only `com.android.systemui`. Adups FOTA and the vendor test apps
  were enabled.
- `persist.sys.timezone` was `America/New_York`. The clock read 2024-12-31 before the frame was
  first online, and network time set it correctly once it joined Wi-Fi. Guess: no RTC battery.

### Backup

Every partition except UDISK and cache, read with
`adb exec-out "su <uid> dd if=/dev/block/by-name/<name> bs=1048576"`: `su 0`, and `su 1000` for
`misc` and `frp` (see [Root](#root)). For each image, the size matched
`/sys/class/block/<dev>/size`, the MD5 matched `md5sum` on the frame, and the last 4 KiB was not
`0xCC` filler. Second reads of `bootloader`, `env` and `boot` matched by SHA-256. The images were
kept uncompressed, so there was no gzip readback.

### What was set up (approved writes, all in `/data`)

1. Built `dashboard/kiosk` with `build.sh` on macOS (Homebrew `openjdk@17` and
   `android-commandlinetools`, build-tools 34.0.0, platform 34) at commit `0bff55e`. It built with
   no changes.
2. `adb install -r`, then
   `am start -n com.wesbos.homehq/.MainActivity --es url https://home-dashboard.wesbos.workers.dev/ --ez home true`
   (the hosted demo).
3. `su 0 pm disable` for `net.frameo.frame`, `com.adups.fota`, `com.along.table`,
   `com.along.factorytest` and `com.android.agingtest`, before the frame was ever online.
4. The navigation service, as on [unit 3](#kiosk): `pm grant` of `WRITE_SECURE_SETTINGS`, then
   `enabled_accessibility_services` and `accessibility_enabled` (both were `null`).
5. `stay_on_while_plugged_in` 7 (it was 0). Time zone with `su 1000 setprop persist.sys.timezone <zone>`
   and `su 1000 service call alarm 3 s16 <zone>`, which answered `Parcel(00000000 '....')`.

After a reboot, `sys.boot_completed` came after about 20 s, then the kiosk
(`com.wesbos.homehq/.Home`) on its "Connect to Wi-Fi?" screen. The disables, the navigation
service binding and both settings held. The owner joined Wi-Fi on the panel from that screen.
Online, network time set the clock, the demo loaded, and Frameo, Adups and the test apps were not
running.

Undo is as in [unit 3's table](#undo-this-unit), plus `adb uninstall com.wesbos.homehq`, and
`su 1000 service call alarm 3 s16 America/New_York` for the time zone. Nothing was written to
`/system` or the boot partition.

### The way back, checked by hand

The owner checked on the panel that the floating Back and Dashboard buttons show over Android's
Wi-Fi settings, and that the kiosk's two-finger menu reaches Android Settings → Apps.

### Not tested on this unit

- USB-C to USB-C with DC unplugged, and a measurement of VBUS on the frame's port with DC in.
- What Frameo or Adups do online over a longer period.
