# QOCEN J1008 10.1" Frameo frame (Allwinner A33, Android 6.0.1)

Record of one unit, 2026-10-12/13. Observations are kept separate from guesses. Unique
identifiers (serial, MAC, IP, Frameo peer ID) are left out; they live in the ignored
`backups/` folder. Host: macOS 26 on Apple silicon.

**Short version:** ADB is a toggle in Frameo's own settings, and the frame ships a working
root `su`. No boot patch, FEL or SD card needed. Two things on this unit differ from its
A33 siblings and cost most of the session: **the USB-C port will not enumerate against a
USB-C host** (it needs a USB-A to USB-C cable through an adapter), and the firmware runs a
vendor **`BackgroundManagerService` that blocks both background services and the
`BOOT_COMPLETED` broadcast** for packages outside a built-in whitelist, which defeats the
usual approaches to starting anything at boot.

End result: Firefox showing the dashboard fullscreen, served by `busybox httpd` on the frame
itself, starting automatically on every boot. No firmware flash and **no `/system` write at
all**.

## Observations (read-only unless noted)

### Identity

| | |
| --- | --- |
| About screen | `QOCEN J1008`, Frameo `v1.32.12_-_OTA_test` (78071) |
| Model / device | `ro.product.model=JSC`, `ro.product.device=astar-d7`, `ro.product.name=astar_d7` |
| Manufacturer / brand | `Allwinner` / `Allwinner` |
| Firmware | `ro.product.version=A103T-V1.0-frameo26-250723` |
| Fingerprint | `Allwinner/astar_d7/astar-d7:6.0.1/MOB30R/20250723:user/test-keys` |
| SoC | Allwinner A33 (`ro.board.platform=astar`, `ro.hardware=sun8i`), quad Cortex-A7 (`CPU part 0xc07`), 32-bit ARMv7 |
| Kernel | Linux 3.4.39, `#182 SMP PREEMPT`, built 2025-07-23 |
| Android | 6.0.1, API 23, security patch 2016-07-05 |
| Display | 1280x800, 160 dpi |
| RAM / swap | 1,026,888 kB; zram swap 262,140 kB |
| Storage | eMMC `mmcblk0`, 61,071,360 sectors (~29 GB); `/data` 25.7 GB |
| Wi-Fi | `8189fs` module (Realtek RTL8189FS over SDIO). Works |
| WebView | `com.android.webview` **44.0.2403.119** |
| Browser | `com.android.browser` 6.0.1 (stock AOSP) present |
| SELinux | Permissive |
| OTA host | `ro.product.ota.host=www.zhsjtech.com:2300` |

Same SoC and the same boot partition start sector (172032) as the
[PF1007L](allwinner-a33-pf1007l.md) and the [Joyhong](joyhong-jt101f-i02.md), but a different
vendor build. Do not assume their boot image hashes apply.

### USB — the port does not work with a USB-C host

The frame has a DC barrel for power, a microSD slot, a reset button, and one port labelled
`TYPEC`. Because power comes from the barrel, that port is free to be data, and it is.

What was tried, in order, all with the frame powered and booted:

| Host side | Cable | Result |
| --- | --- | --- |
| Mac USB-C port | USB-C to USB-C, verified for data | **Nothing.** No USB device, no attach event |
| Mac USB-C port | Bundled cable | Nothing |
| USB-C to USB-A adapter | USB-A to USB-C, power-only | Nothing |
| USB-C to USB-A adapter | USB-A to USB-C, data | **Enumerates**, `1f3a:1001`, vendor `USB Developer`, product `Android` |

The controlled comparison is the useful part: an iPhone on the *same* C-to-C cable and the
*same* Mac port enumerated immediately, and the frame on that same cable produced nothing at
all — not an `unauthorized` device, not a failed handshake, no kernel USB event. So this is
below the ADB layer.

Guess, not verified: the port's USB-C receptacle does not present the CC pull-down a USB-C
host needs to detect an attachment, because it is wired for a USB-A host that supplies VBUS
with no CC negotiation. This matches the PF1007L note that "USB-C to USB-C gives no power or
data", and it means **a USB-A to USB-C cable through an adapter is mandatory on this unit**.

Diagnosing this on macOS: `system_profiler SPUSBDataType` returns zero lines on this host
regardless of what is attached and is useless here. `ioreg -c IOUSBHostDevice -r -l -w 0` is
reliable. Note that `ioreg -l | grep idVendor` produces a false positive from the
`IOKitDiagnostics` class-count blob, and the `IOUSBHostDevice` count in that blob is a
cumulative allocation counter, not live instances — both cost time in this session.

### ADB and root

- **ADB is enabled from Frameo**: Settings → About → **ADB access** ("ADB allows communicating
  with the Android system on the frame by cabled connection"). No hidden menu or tap sequence.
- `/system/build.prop`: `sys.usb.config=ptp,adb`, `ro.adb.secure=1`, `ro.debuggable=1`,
  `service.adb.tcp.port=5555`, `persist.sys.usb.config=ptp,adb`. `/default.prop` has
  `ro.secure=1`, `ro.debuggable=0`.
- **Network ADB is live on port 5555** once the frame is on Wi-Fi, and was reachable from the
  host. `/data/misc/adb/adb_keys` gained the host key when USB was authorised, so unlike the
  Joyhong this unit does appear to check keys — **not verified** with a fresh untrusted key.
  Treat an open 5555 as a root shell to anything on the network and keep the frame on an
  isolated or guest network.
- `adb shell` is uid 2000. **`su -c id` returns uid 0** from the shipped `/system/xbin/su`.
  There is no SuperSU manager app, so any installed app can take root silently.
- **USB ADB did not survive every reboot.** After one reboot the gadget came back as
  `1f3a:1009` with no ADB interface; after another it returned as normal. Not explained.
  Network ADB on 5555 was the reliable fallback. The frame also took a new DHCP lease on
  every boot.

### Software of interest

| Package | Notes |
| --- | --- |
| `net.frameo.frame` | Slideshow app and a **HOME** activity. Reported by `pm list packages -s` |
| `com.softwinner.dragonfire`, `dragonaging`, `dragonphone` | Allwinner factory test apps |
| `com.DeviceTest` | Factory test |
| `com.android.webview` | **44.0.2403.119**, far older than the 106 the dashboard targets |
| `com.android.browser` | Stock AOSP browser |

`com.android.systemui` is present and enabled here, unlike the Joyhong where it ships
disabled. No separate vendor OTA package was found despite `ro.product.ota.host` being set.

### Partition table (eMMC `mmcblk0`, 512-byte sectors, 61,071,360 total)

From `/sys/block/mmcblk0/*/start` and `/dev/block/by-name`.

| Partition | Name | Start | Size (sectors) |
| --- | --- | --- | --- |
| p2 | bootloader | 73728 | 65536 |
| p5 | env | 139264 | 32768 |
| p6 | boot | 172032 | 32768 |
| p7 | system | 204800 | 4194304 |
| p8 | misc | 4399104 | 32768 |
| p9 | recovery | 4431872 | 65536 |
| p10 | cache | 4497408 | 1572864 |
| p11 | metadata | 6070272 | 32768 |
| p12 | private | 6103040 | 32768 |
| p13 | frp | 6135808 | 1024 |
| p14 | empty | 6136832 | 31744 |
| p15 | alog | 6168576 | 163840 |
| p16 | media_data | 6332416 | 32768 |
| p1 | UDISK (`/data`) | 6365184 | 54706176 |

### Backup, and why the raw `/system` image cannot be hash-matched

Backed up over root ADB with `dd` piped through `adb exec-out` (binary-safe; verified on a
small partition first). Every partition matched its device-side md5 **except `system`**.

Two consecutive device-side md5 reads of `mmcblk0p7` differ from each other, so no
single-pass hash can ever match. `/system` is mounted `ro` but is remounted repeatedly in the
background (the BIUFRAME notes attribute this to `daemonsu`), which rewrites superblock and
journal metadata. Excluding the first 4 KiB does not help, so it is not only the primary
superblock.

What worked instead: a **file-level backup** — `busybox tar` of `/system` plus a device-side
md5 of all 1504 files. All 1504 verified.

One trap when verifying on macOS: `/system/media/audio/ringtones` contains five pairs of
filenames that collide case-insensitively (`Andromeda.ogg`/`ANDROMEDA.ogg`,
`CanisMajor.ogg`/`CANISMAJOR.ogg`, `hydra.ogg`/`Hydra.ogg`, `Perseus.ogg`/`PERSEUS.ogg`,
`UrsaMinor.ogg`/`URSAMINOR.ogg`). Extracting the tar onto case-insensitive APFS collapses each
pair and reports five false mismatches. Verify those members straight from the archive with
`tar -xO` instead.

### What was set up (approved writes, all in `/data`)

The owner chose the browser route and no `/system` writes. Firefox renders the dashboard fine
on the stock WebView because it brings its own engine, so the WebView 44 → 106 swap was not
needed. Firefox sat at ~227 MB PSS of 1 GB with zram swap almost untouched.

1. **Firefox 143.0.4** and **Rootless Pixel Launcher 3.9.1**, installed from the pinned URLs
   and SHA-256s already in [biuframe-setup-guide.md](biuframe-setup-guide.md).
2. **Dashboard served from the frame itself** with `busybox httpd` out of
   `/data/local/tmp/homehq`, so it does not depend on a host being awake.
3. **Launcher set as HOME**, then later replaced by the boot app below.

### `busybox httpd` needs a MIME config or the dashboard renders blank

Out of the box it serves `.js` as `application/octet-stream`, and Firefox refuses to execute
an ES module with a wrong MIME type — the page loads, the sidebar renders, the content area
stays empty. `.webmanifest` has the same problem, so the manifest is never parsed either.

Fix: an `httpd.conf` in the served directory, passed with `-c`:

```
.js:application/javascript
.mjs:application/javascript
.webmanifest:application/manifest+json
.json:application/json
.css:text/css
.html:text/html
.png:image/png
.svg:image/svg+xml
```

### Fullscreen: the manifest's display mode is not honoured

Firefox on this frame will not launch a home-screen shortcut standalone. Tried and failed:
serving over `http://localhost` so the origin is a secure context, fixing the manifest MIME
type, and adding a service worker so the page meets the usual install criteria. The menu
entry stays "Add to Home screen" (never "Install"), and the shortcut opens with full browser
chrome. Firefox for Android does not build WebAPKs, which is the likely reason.

What does work is the **Fullscreen API from a user gesture**. The gesture requirement means
one tap after launch. To make that tap safe to automate, the page shows a full-screen gate
while not in fullscreen whose only job is to call `requestFullscreen()` — without it, a
scripted tap at a fixed coordinate lands on a dashboard card and opens a detail sheet.

This is **not** committed to `dashboard/` here: the gate would also appear for the WebView
kiosk route, which is not in Fullscreen API state, so it would need to be opt-in before it
could ship for everyone. The shape of it:

```js
var gate = document.getElementById('fs-gate');
var el = document.documentElement;
var req = el.requestFullscreen || el.mozRequestFullScreen || el.webkitRequestFullscreen;
function sync() { gate.hidden = !!(document.fullscreenElement || document.mozFullScreenElement); }
gate.addEventListener('touchend', function (e) { e.preventDefault(); req.call(el); setTimeout(sync, 300); });
document.addEventListener('fullscreenchange', sync);
sync();
```

### The firmware blocks every normal way to start something at boot

This is the main finding on this unit. The vendor build runs a `BackgroundManagerService`
that consults a whitelist the package is not on:

```
BackgroundManagerService: package not in whitelist: com.homehq.boot
BackgroundManagerService: not whitelist service Intent { cmp=com.homehq.boot/.StartService }
BackgroundManagerService: prevent from boot complete broadcast: com.homehq.boot
```

Consequences, both confirmed on-device:

- **A background `Service` cannot be started** by a non-whitelisted app, from a receiver or an
  activity. `startService` returns without error and nothing runs.
- **`BOOT_COMPLETED` is never delivered.** `grep -c BOOT_COMPLETED` over a full boot logcat
  returns 0 for a correctly registered, permission-granted, non-stopped receiver.

No whitelist file was found under `/system/etc` or `/data/system`, and nothing there mentions
`backgroundmanager`; it appears compiled into the vendor framework. Also note **neither
`/system/bin/install-recovery.sh` nor `/system/su.d` exists on this firmware**, so the
BIUFRAME boot-hook recipe does not transfer as written.

**What works: register as the HOME activity.** Android *starts* HOME directly at boot rather
than broadcasting to it, and that path is not intercepted. A minimal app with
`category.HOME` in its intent filter, set as the default HOME app, reliably runs at boot.

It must not start an Android service. It hands off to a **detached root shell script**, which
survives as an orphan owned by init and is outside anything the vendor service polices:

```java
Runtime.getRuntime().exec(new String[] {"su", "-c",
    "sh /data/local/tmp/homehq-start.sh >/dev/null 2>&1 &"});
```

Source for the app is in [`scripts/homehq-boot`](../scripts/homehq-boot). Measured on this
unit: **~100 s from `adb reboot` to a fullscreen dashboard**, unattended.

### Two `su` traps worth knowing on this firmware

- **`su`'s PATH starts with `/sbin`**, where SuperSU ships a stripped busybox. `su -c "busybox
  httpd …"` fails with `httpd: applet not found`, while the same command as the shell user
  works, because the shell user gets `/system/bin/busybox`. Use absolute paths in anything
  run through `su`.
- **`/system/bin/busybox` has no `date` applet** on this build. Use `/system/bin/date`.

## Undo

| Change | Undo |
| --- | --- |
| Boot app as HOME | Settings → Apps → Home HQ → Clear defaults, or `adb uninstall com.homehq.boot`. The HOME chooser returns; Frameo and the launcher are still installed |
| Launcher / Firefox | `adb uninstall amirz.rootless.nexuslauncher`, `adb uninstall org.mozilla.firefox` |
| Dashboard + server | `rm -r /data/local/tmp/homehq /data/local/tmp/homehq-start.sh`; the server is not running after a reboot once the HOME app is gone |
| Frameo as HOME | Press Home and pick Frameo, or clear defaults as above |

Nothing was written to `/system`, so there is nothing to restore there.

## Not done

- Real data. The dashboard ran on its demo dataset throughout.
- WebView 44 → 106 and the native kiosk APK. Not needed for the Firefox route.
- Whether network ADB on this unit accepts an unknown key, which is what makes the Joyhong
  dangerous on a shared network. Assume the worst until someone tests it.
- Why USB ADB survives some reboots and not others.
