# ARZOPA P156W (Frameo, RK3326, Android 8.1)

Record of one unit, tested 2026-10-16 from a Linux host (Arch, platform-tools 37.0.0) over USB
ADB. Observations are kept separate from guesses. Unique identifiers (serial, MAC, IP) are left
out.

**Result:** ADB over USB after accepting the frame's own authorization, and a shipped SuperSU
`su` that gives root with no prompt. A verified backup of everything before `userdata` (2.76 GiB)
was taken over ADB; **no flash partition was written**. The stock WebView is
`61.0.3163.98`, which is too old for this repo's dashboard (see
[Dashboard compatibility](#dashboard-compatibility)).

This is a different device from the ARZOPA identified by its app rather than by Frameo
([PR #131](https://github.com/wesbos/photo-frame-dashboard/pull/131), RK3126, `incar` board,
Arzopa home app). Match the About screen, not the brand. **No Arzopa package exists on this
unit**: its vendor app is Frameo, so the Arzopa app's hidden ADB toggle and its fixed code do not
apply here.

## How it relates to the Pastigio FRAME156 and FRAME157

Same BSP and vendor stack as the Pastigio FRAME156/FRAME157 — RK3326, Android 8.1 (API 27), the
same 2020-11-05 security patch, Frameo as the home app, and the same 75,348-byte SuperSU `su` —
but **not the same build**. The partition layouts diverge at `boot`, so offsets from those docs
must not be reused. The one difference that changes a setup plan is the WebView: 106 on the
Pastigio units, 61 here.

| | This unit (P156W) | [FRAME156](pastigio-frame156.md) | [FRAME157](pastigio-frame157.md) |
| --- | --- | --- | --- |
| product / device | `rf001e` / `rk3326_mid` | `FRAME156` / `rk3326_32bit` | `FRAME157` (`DP105F`) |
| Firmware | `rf001e_user_20231007` | `FrameO.DP105F.v2026010414` | `FrameO.DP105F.v2026051219` |
| eMMC, 512-byte sectors | 61,079,552 | 61,063,168 | 61,071,360 |
| `boot` start + sectors | 139264 + 131072 | 139264 + 77824 | not recorded |
| `recovery` start + sectors | 270336 + 262144 | 217088 + 143360 | not recorded |
| `userdata` start | 5784576 | 5612544 | not recorded |
| WebView | **61.0.3163.98** | 106.0.5249.126 | 106.0.5249.126 |
| `ro.boot.flash.locked` | **0** | 1 | not recorded |
| Display density | 160 dpi | 170 dpi | 170 dpi |
| Vendor updaters | `com.adups.fota`, `android.rockchip.update.service` | `com.muxintu.app.mxota` | `com.muxintu.app.mxota` |
| Third-party launcher installed | none | `com.android.launcher3` | not recorded |

The Pastigio methods do transfer: Frameo's ADB toggle, the base64 backup pipeline and its CRLF
trap, `pm disable-user`, the WebView swap. The numbers do not — read the partition table from the
unit in front of you.

## Identity

| | |
| --- | --- |
| Brand / model | `ARZOPA` / `P156W` (`ro.product.brand=ARZOPA`, `ro.product.manufacturer=ZED`) |
| About / `ro.product.device` | `rk3326_mid`; product name `rf001e` |
| Firmware | `rf001e_user_20231007`, build type **`user`**, `ro.build.version.incremental=185820` |
| Fingerprint | `rockchip/rf001e/rk3326_mid:8.1.0/OC/185820:user/release-keys` |
| SoC / userspace | Rockchip RK3326 (`ro.board.platform=rk3326`) / `armv8l`, **32-bit userspace** |
| Android | 8.1.0 (SDK 27), security patch 2020-11-05, kernel 4.4.138 |
| Display | 1920×1080, 160 dpi |
| RAM | `MemTotal` ≈ 977 MB — **`ro.config.low_ram=true`** |
| Storage | eMMC `mmcblk2`, 61,079,552 × 512-byte sectors (31,272,730,624 bytes) |
| `/data` | **f2fs**, `ro.crypto.state=unsupported` (not encrypted) |
| `/system`, `/vendor`, `/oem` | ext4, mounted read-only |
| SELinux | **Permissive** (`ro.boot.selinux=permissive`) |
| Boot | `ro.boot.flash.locked=0`, `ro.boot.verifiedbootstate=orange`, `ro.boot.veritymode=enforcing` |
| USB IDs, Android running | `2207:0012`, manufacturer string `ZED`, product string `P156W`; interface 0 is class 06 (MTP/PTP), interface 1 is class `ff`/`42` (ADB) |
| WebView | `com.android.webview` **61.0.3163.98**; APK in `/system/app/webview` |
| Home app | `net.frameo.frame` (the only launcher installed at the time). System copy in `/system/priv-app/Frameo`; the running copy is **v1.32.16 under `/data/app`**, so the app had already replaced its own version. Later the same day `com.wesbos.homehq` became the HOME app and Frameo was disabled — see [Changes made](#changes-made-to-the-frame) |
| Vendor system apps | `/system/app`: `FotaUpdate` (Adups), `RKUpdateService`, `ZedielPcbTest`, `RkExplorer`, `BookmarkProvider`; `/system/priv-app`: `DeviceTest`, `Frameo`, `Settings`, `SystemUI` |
| Vendor software | `com.adups.fota` (FOTA updater), `android.rockchip.update.service` (Rockchip updater), `com.zediel.pcbtest`, `com.DeviceTest` |
| On-device tools | `dd`, `gzip`, `base64`, `sha256sum`, `md5sum`, `toybox`, `busybox` |

USB enumeration is normal: `adb devices -l` reports
`product:rf001e model:P156W device:rk3326_mid`.

## Orientation

The panel's only mode is **1920×1080p60** (`/sys/class/drm/card0-DSI-1/modes`) and the frame is
physically landscape. The **system default rotation is 90° (portrait)**, which is what `screencap`
and a plain browser get before anything is changed. Apps that lock their own orientation are
unaffected — Frameo runs landscape, and `dashboard/kiosk` declares
`android:screenOrientation="sensorLandscape"` for the same reason. A browser does not, so the
dashboard came up as a letterboxed landscape strip until the frame was put in landscape:

```sh
adb shell settings put system accelerometer_rotation 0
adb shell settings put system user_rotation 0     # 0 = 1920x1080 landscape
# undo: adb shell settings put system accelerometer_rotation 1
```

The setting persists across reboots; it is the same class of change as the density note in the
kiosk README.

## Cable: a USB-A to USB-C cable is required

This unit does **not** enumerate on a USB-C to USB-C cable, even though the same cable works with
a phone. With C-to-C there was no USB event at all on the host — no Android device, no ADB, and
not even Rockchip loader mode while holding power at plug-in. A USB-A to USB-C cable enumerated
immediately. This matches the cable note in the README and the pattern in
[issue #126](https://github.com/wesbos/photo-frame-dashboard/issues/126).

So the port is wired for a reduced USB-C role: do not conclude from a C-to-C failure that the
frame's USB is unusable, and try an A-to-C cable before giving up on USB.

## Getting ADB

ADB access was turned on in Frameo and the frame's own authorization was accepted on screen; no
key was injected and no boot image was touched. `adb devices` then moved from `unauthorized` to
`device`, and the frame wrote the host key to `/data/misc/adb/adb_keys` (715 bytes, `system:shell`,
mode 0640). The exact menu path used on this unit was not recorded; Frameo's ADB toggle is
normally under Settings → About → Beta Program → ADB Access.

`adb shell` runs as uid 2000. `su` works with no prompt and no manager app:

```text
$ adb shell su -c id
uid=0(root) gid=0(root) groups=0(root) context=u:r:toolbox:s0
```

`/system/xbin/su` and `/system/xbin/daemonsu` are 75,348-byte SuperSU binaries. **Any app
installed on this frame can take root**, so install nothing untrusted.

`ro.adb.secure=1`, and SystemUI is present and enabled (only `com.android.nfc` is disabled), so an
authorization dialog does have somewhere to appear.

## Partition table (eMMC `mmcblk2`, 512-byte sectors)

| Partition | Name | Start | Sectors |
| --- | --- | --- | --- |
| p1 | uboot | 16384 | 8192 |
| p2 | trust | 24576 | 8192 |
| p3 | misc | 32768 | 8192 |
| p4 | resource | 40960 | 32768 |
| p5 | kernel | 73728 | 65536 |
| p6 | boot | 139264 | 131072 |
| p7 | recovery | 270336 | 262144 |
| p8 | backup | 532480 | 229376 |
| p9 | security | 761856 | 8192 |
| p10 | cache | 770048 | 786432 |
| p11 | system | 1556480 | 3145728 |
| p12 | metadata | 4702208 | 32768 |
| p13 | vendor | 4734976 | 786432 |
| p14 | oem | 5521408 | 262144 |
| p15 | frp | 5783552 | 1024 |
| p16 | userdata | 5784576 | 55294943 |

Same layout family as the [Pastigio FRAME156](pastigio-frame156.md) (also RK3326), with larger
`boot` and `recovery` partitions.

The stock `boot` partition (139264, 131072 sectors) reads back with SHA-256
`09a7520b2a9674fd2c1cae22b83a709ba890fab34fd57813ebb8c53061aec435`.

## Backup over ADB

Everything before `userdata` was captured read-only over ADB as root: 2,961,702,912 bytes
(sectors 0–5,784,576), gzipped to 624,015,780 bytes. Checks passed: exact byte count, SHA-256 of
the raw stream matching the gzip readback, `gzip -t`, no 1 MiB block consisting of `0xCC` filler
in 2,825 blocks, and independent re-reads of `boot`, `recovery` and 32,768 sectors of `system`
compared against the image.

**Two traps, both avoided:**

- **`adb exec-out` corrupts a raw `dd` stream.** It turns every LF byte into CR LF, so a raw
  stream is longer than the partition and its hash is wrong. Reading 1 MiB directly gave a
  different SHA-256 from the hash computed on the frame for the same 1 MiB, while the same read
  piped through `base64` on the frame and `tr -d '\r\n' | base64 -d` on the host reproduced the
  frame's hash exactly. Compress and base64-encode on the frame; never hash the transport.
- **Read sequentially from sector 0.** `dd` on the whole-disk node cannot seek past 2 GiB from a
  32-bit userspace, so re-reading a partition by sector offset must use the partition node
  (`mmcblk2pN`) instead.

`userdata`, `mmcblk2boot0/1` and `rpmb` were not captured. The restore path was not tested:
it would need Rockchip loader mode and `rkdeveloptool`, neither tried on this unit. This is not a
transactional filesystem snapshot; the system was running during the read.

## System write access (verified)

`/system` can be remounted read-write: `mount -o rw,remount /system` worked on 2026-10-16. dm-verity
is not active here (`ro.boot.veritymode=enforcing` is set, but the filesystem is mounted from
`/dev/block/mmcblk2p11` rather than a `dm-` device, and `verifiedbootstate=orange`). It was needed
for the Adups CA capture and reverted to `ro` afterwards. The remount is racy — an automatic re-`ro`
can land within the same command — so the write and the remount go in one script.

## Dashboard compatibility

The stock WebView, 61.0.3163.98, is the practical ceiling here, and the repo dashboard's built CSS
uses features newer than that. Measured against a local `chrome61`-target build:

| Feature | Occurrences | Needed by |
| --- | --- | --- |
| `gap` in a **flex** container | 81 rules | Chrome 84 |
| `aspect-ratio` | 2 rules | Chrome 88 |
| `:has()` | 1 rule (cosmetic) | Chrome 105 |
| `gap` in a **grid** container | 22 rules | OK from Chrome 57 |
| JS syntax | — | The source is ES5 and `type="module"` works from Chrome 61 |

So the page loads on the stock WebView but loses flex spacing throughout (rail, chips, banners,
toast) and both `aspect-ratio` boxes. The WebView swap that
[biuframe-setup-guide.md](biuframe-setup-guide.md) documents **does not work on this unit** — see the
next subsection — but a **vendor overlay adds a current WebView provider without touching
`/system`**, and that route is verified here.

### The WebView swap does not work on this unit: the signatures differ

The swap in [biuframe-setup-guide.md](biuframe-setup-guide.md) works on the BIUFRAME because that
ROM is signed with the AOSP test keys, so the AOSP-signed LineageOS prebuilt carries the same
signature. This unit is not, and Android refuses the replacement. Installing the pinned APK as a
*system-app update* (a `/data` write, nothing in `/system`) is the harmless way to prove it:

```text
$ adb install -r webview-106.apk
Failure [INSTALL_FAILED_UPDATE_INCOMPATIBLE: Package com.android.webview signatures do not
match the previously installed version; ignoring!]
```

The pinned APK's SHA-256 matched the repo's (`e2edc1f8…90580`), so the refusal is about signing,
not about the download. Measured certificates:

| | serial | SHA-256 fingerprint |
| --- | --- | --- |
| This unit's WebView (`packages.xml`, cert index 3) | `92A528C773D7A141` | `CF:2A:B3:81:85:95:C4:ED:A0:8C:EC:72:BB:E3:9B:C3:77:A3:0B:76:4A:3E:EB:DE:52:53:6E:AE:01:80:85:25` |
| LineageOS 106 prebuilt (`META-INF/CHROMIUM.RSA`) | `504E2C42` (`CN=Unknown`) | `32:A2:FC:74:D7:31:10:58:59:E5:A8:5D:F1:6D:95:F1:02:D8:5B:22:09:9B:80:64:C5:D8:91:5C:61:DA:D1:E0` |
| AOSP `testkey`, present here as cert index 0 | `936EACBE07F201DF` | `A4:0D:A8:0A:59:D1:70:CA:A9:50:CF:15:C1:8C:45:4D:47:A3:9B:26:98:9D:8B:64:0E:CD:74:5B:A7:1B:F5:DC` |

All six certificates in `packages.xml` carry the **AOSP test-key subject**
(`C=US, ST=California, L=Mountain View, O=Android, OU=Android, CN=Android, emailAddress=android@android.com`),
but only index 0 is a real AOSP key: `platform`, `shared`, `media` and `testkey` were all compared,
and indices 1, 2, 3 and 5 are ODM-generated keys that copy the subject. The WebView is signed with
one of those, so an AOSP- or Google-signed prebuilt cannot replace it. Copying the APK straight into
`/system` would produce the same refusal at the next boot scan, with the package then unavailable.

The repo already records this reasoning and, for the pinned prebuilt, the same certificate:
[biuframe.md](biuframe.md) notes its `CN=Unknown` signer with cert SHA-256 `32:A2:FC:74:…:D1:E0`, and
[app-analysis.md](app-analysis.md) compares a vendor app against the AOSP `platform` and `testkey`
certificates to show that an AOSP-signed update cannot preserve the installed signing identity. This
section follows that method; only public X.509 certificates were downloaded, and the comparison is
identity comparison, not an independent verification of the APK signature. The counterpart case is
[allwinner-a133-loofii-c3.md](allwinner-a133-loofii-c3.md), which re-signs a LineageOS prebuilt with
the AOSP `testkey` because that ROM's platform key *is* the public testkey — an option this unit does
not have, since the ODM private key is not available.

So matching signatures is a **precondition** for the WebView step in that guide, not a detail. Note
that `ro.build.tags=release-keys` is not by itself the test — the AOSP key family and the ODM keys
here share the same subject string, so compare the certificate, not the subject.

Without the platform private key, working around this would mean rebuilding
`/data/system/packages.xml`, which is not worth attempting while the restore path is untested. There
is, however, a route that keeps the stock WebView in place entirely — see below.

### A modern WebView without touching `/system` (verified)

The ROM's WebView provider list is **configurable**, so a **vendor resource overlay** can add a
second provider. The stock WebView stays installed and stays the fallback. Verified on this unit on
2026-10-16.

The mechanism, read from AOSP 8.1. The framework loads `res/xml/config_webview_packages.xml` (here
byte-for-byte the AOSP one: a single `com.android.webview` entry with **no `<signature>`**), and
`WebViewUpdater.providerHasValidSignature()` accepts a provider when any of these holds:

- the build is debuggable (`ro.debuggable=1`) — **not** the case here (`0`);
- the entry **declares `<signature>`** — then the provider may be an ordinary user app;
- no signature is declared — then the package must be a system app (`isSystemApp()`).

So the overlay declares the provider's signing certificate and the WebView is installed as a normal
app. On the overlay side, `OverlayManagerServiceImpl` in 8.1 defines `signaturesMatching()` but never
calls it, so a vendor overlay is not required to carry the platform key.

| Item | Value |
| --- | --- |
| Overlay APK | `treble-overlay-mulch-webview.apk` from [A4Alpha/mulch-webview-overlay](https://github.com/A4Alpha/mulch-webview-overlay) release `v0.1` — SHA-256 `372fe0ba0cb7b98e98346978b12d3aeb073ea4cde0fd033c9b1a775187394a5a` |
| Overlay properties | built for `platformBuildVersionCode=27` / `8.1.0`; package `com.alpha.mulch.webview.overlay`, static, `targetPackage=android` |
| Declared signature | base64 X.509 of the Mulch signer, serial `0CD80CB1` — **identical** to the certificate of the APK below |
| WebView | Mulch SystemWebView `us.spotco.mulch_wv` **131.0.6778.200**, from GitLab `divested-mobile/mulch`, `prebuilt/arm64/webview.apk`, SHA-256 `9b6768f3c8c08c2ea5e1a4fa2ed916b0ba6050cb85a5e14954db017e71d88aab` |
| Placement | `/vendor/overlay/`, owner `root:root`, mode 0644 |

```sh
adb install -r mulch-131-arm64-webview.apk                 # ordinary app, reversible
adb shell su -c 'mount -o rw,remount /vendor'
adb push treble-overlay-mulch-webview.apk /data/local/tmp/
adb shell su -c 'cp /data/local/tmp/treble-overlay-mulch-webview.apk /vendor/overlay/ \
                 && chmod 644 /vendor/overlay/treble-overlay-mulch-webview.apk \
                 && chown root:root /vendor/overlay/treble-overlay-mulch-webview.apk && sync'
adb shell su -c 'mount -o ro,remount /vendor'
adb reboot
adb shell cmd overlay list | grep mulch                    # [x] com.alpha.mulch.webview.overlay
adb shell dumpsys webviewupdate | grep 'Valid package'     # now lists us.spotco.mulch_wv
adb shell cmd webviewupdate set-webview-implementation us.spotco.mulch_wv
```

`set-webview-implementation` prints `Success`, `dumpsys webviewupdate` then reports
`Current WebView package: (us.spotco.mulch_wv, 131.0.6778.200)`, and the choice persists in
`settings global webview_provider`. The dashboard rendered correctly on it at 1920×1080, with the
stock WebView still listed as a valid fallback.

**The ABI is the trap.** The WebView native library is loaded **into the app's process**, so the
provider has to supply the ABI that app runs under. Every app on this unit is 64-bit
(`primaryCpuAbi=arm64-v8a`, and the device's default ABI is `arm64-v8a`), which is why the stock
WebView carries both ABIs (`armeabi-v7a` **and** `arm64-v8a`). Installing Mulch's `arm` build first
gave:

```text
UnsatisfiedLinkError: dlopen failed:
"/data/app/us.spotco.mulch_wv-…/base.apk!/lib/armeabi-v7a/libwebviewchromium.so"
is 32-bit instead of 64-bit
```

The `arm64` build fixed it. A unit that runs both 32- and 64-bit apps would need a provider
carrying both ABIs, or the stock WebView.

Note also that **138 is the newest WebView for Android 8.1** (see
[pastigio-frame156.md](pastigio-frame156.md)); LineageOS 139 needs minSdk 29, and a current Cromite
`arm64_SystemWebView` (Chromium 153) was refused here with `Requires newer sdk version #29`. Mulch
131 is not the newest engine in existence, but it is far past the dashboard's needs: flex `gap`
(Chrome 84), `aspect-ratio` (88) and `:has()` (105) all work.

Undo, in this order:

```sh
adb shell cmd webviewupdate set-webview-implementation com.android.webview
adb shell su -c 'mount -o rw,remount /vendor && rm /vendor/overlay/treble-overlay-mulch-webview.apk && sync && mount -o ro,remount /vendor'
adb reboot
adb uninstall us.spotco.mulch_wv
```

To fall back to the alternative, backport the CSS below Chrome 84 and keep the stock WebView, or
install a browser with its own engine (the repo already pins Firefox 143 `armeabi-v7a`, see
`scripts/biuframe-setup.sh`).

## Update checks: the URLs behind each updater

Read 2026-10-16, statically, from the odexed system packages and the installed Frameo APK. The system
APKs carry **no `classes.dex`** — the code lives in the `.odex`/`.vdex` under
`/system/app/<name>/oat/arm64/`, so the constants below were read there. All three updaters are
disabled on this unit (see [Changes made](#changes-made-to-the-frame)), so this is what each package
is *built* to call, not live traffic.

### Rockchip OTA — `android.rockchip.update.service` 1.8.1

This is the "system update" entry in the vendor Settings.

| Item | Value |
| --- | --- |
| Host | `ro.product.ota.host` = **`www.rockchip.com:2300`** |
| Backup host | `ro.product.ota.host2` — unset on this build |
| Fallback in the code | `192.168.1.143:2300` (development default, hard-coded) |
| Query path | **`/OtaUpdater/android?product=…&language=…&sn=…&version=…`** |
| Transport | HTTP on 2300; an `ftp://` download task (ftp4j) is also compiled in |
| User-Agent | `rk29sdk/4.0` |
| Package written to | `/data/media/0/update.img` or `/data/media/0/update.zip` |

`RKUpdateService.vdex` holds the literals `/OtaUpdater/android?product=`, `&language=`, `&sn=`,
`&version=`, and the property keys `ro.product.ota.host`, `ro.product.ota.host2`,
`ro.ota.packagename`, `ro.firmware.version`, `ro.product.version`. On this build the first two
properties are unset and `ro.product.version=1.0.0`. The host property carries no scheme, so the
request is `http://www.rockchip.com:2300/OtaUpdater/android?…`. The `:2300` query pattern is shared
across this vendor family — [qocen-j1008.md](qocen-j1008.md) records `www.zhsjtech.com:2300` on the
same updater, and [veidoo-f10.md](veidoo-f10.md) records the Rockchip default.

### Adups FOTA — `com.adups.fota` 5.28

**Host, verified live: `https://fota5p.adups.com/`.** No OTA host is stored in clear in the APK —
strings over `FotaUpdate.vdex`, `resources.arsc` and the APK contain **no vendor host at all** (no
`adups.com`, no bare IPv4), so Adups assembles the endpoint at runtime; `AduHostnameVerifier` is
present, and the network layer is OkHttp. Sibling units expose the same names as literals —
`fota5p.adups.cn` and `fota5p.adups.com` in [frameo-rk3326-s101.md](frameo-rk3326-s101.md), the same
pair in [veidoo-f10.md](veidoo-f10.md), and `fota5p.adups.com` in [biuframe.md](biuframe.md) — but
this APK has none of them, so the host had to be read from a live check.

The live check (2026-10-16), with the frame's DNS redirected to a logging resolver on the test host,
tapping **Check for updates** in the Adups "Wireless Update" screen produced:

- DNS `A fota5p.adups.com`, repeatedly — falling back to `A fota5p.adups.cn` only when the first name
  fails to connect;
- a TLS connection to **port 443** with ClientHello SNI **`fota5p.adups.com`** and ALPN
  `h2` / `spdy/3.1` / `http/1.1` (OkHttp). So this updater is **HTTPS**, unlike the Rockchip one on
  plain HTTP port 2300.

**Endpoints, verified live.** With the frame temporarily trusting a capture CA (the method is under
[Changes made](#changes-made-to-the-frame)), the check turned out to be two `POST`s, both over
TLS 1.2 with `User-Agent: okhttp/2.7.5`:

| Method | URL | Body |
| --- | --- | --- |
| POST | `https://fota5p.adups.com/otainter-5.0/fota5/detectSchedule.do` | `application/x-www-form-urlencoded`: `shaKey=<sha256 of key>` and `key=<opaque hex>` |
| POST | `https://fota5p.adups.com/otainter-5.0/fota5/submitReport.do` | `multipart/mixed`: `result` (JSON), `mid`, `imei`, `appVersion` (`5.28.0.1.006_2020-03-18 10:48`), `project` (`zediel3326$8.1_P156W_en-US_other`), `version`, `battery`, `time`, `log` |

`detectSchedule.do` is the "is there an update" call and `submitReport.do` uploads the outcome; both
sit under `/otainter-5.0/fota5/`. The `key` field is an opaque hex blob whose SHA-256 travels as
`shaKey`, so only the routing is read here, not the request contents. The obfuscation above is why
the static read missed the host entirely; a *user* CA would also have been ignored, because the app
targets API 28 (`targetSdk=28`), so the capture CA had to go into the **system** store.

Practical note: this LAN's resolver answers **0.0.0.0** for both `fota5p.adups.com` and
`fota5p.adups.cn`, so Adups is already blackholed at DNS on this network; the capture was taken by
overriding those two names **on the test host only**, never on the frame.

What *is* in clear in the APK is the FCM/Firebase control channel, injected into `resources.arsc` by
`google-services`:

| Item | Value |
| --- | --- |
| Firebase project | `fotafcm` |
| Database URL | `https://fotafcm.firebaseio.com` |
| Storage bucket | `fotafcm.appspot.com` |

The client API key, sender ID and app ID that also ship in `resources.arsc` are omitted here, like
the rest of this doc's identifiers (the repo commits no API keys or account IDs).

This build is the push flavour: the check arrives through Firebase Cloud Messaging and the **firmware
URL is server-supplied**. The code carries `download_path_server` and `deltaurl` and logs
`download_path_server : …`; the package lands in `/data/ota_package/update.zip` or
`/data/media/0/adupsfota/update.zip`. Cadence lives in `adupsfota.xml`
(`activate_total_time=900000`, i.e. 15 min, plus `scheduleReportDataCHECKTIME`), and the package reads
`ro.fota.*` (`oem=zediel3326_8.1`, `platform=RK3326_8.1`,
`version=rf001e_user_20231007_20231007-1900`).

### Frameo — `net.frameo.frame` 1.32.16

URLs from the APK currently installed under `/data/app` (`base.apk`, 77 MB):

| URL | Use |
| --- | --- |
| `https://serviceupdates.frameo.net` | update of the Frameo app itself |
| `https://api.frameo.net/` | main API |
| `https://config.frameo.net` | remote configuration |
| `https://manufacturer.frameo.net/` | manufacturer channel |
| `https://test.api.frameo.net/`, `https://test.serviceupdates.frameo.net`, `https://test.manufacturer.frameo.net/` | test variants |
| `https://app.frameo.com/frameaction`, `https://app.frameo.com/pair#code=%1$s&src=qr` | pairing / app |
| `https://frameo.com`, `https://security.frameo.com/`, `https://support.frameo.com` | web and support |
| `https://frameo-27e5f.firebaseio.com`, `frameo-27e5f.appspot.com` | Firebase `frameo-27e5f` |
| `https://s.frameo.sh/calendar-setup` | calendar |
| `https://openweathermap.org` | weather |

The app also bundles Firebase Remote Config, Crashlytics, Installations and Performance.
`net.frameo.frame_preferences.xml` tracks the running build in `KEY_LAST_SEEN_VERSION` (`80320`, i.e.
v1.32.16; the `/system/priv-app/Frameo` copy is v1.18.7 = `35890`). Licensing and push data sit
outside the app, in `/vendor/frameo/`: `licence.key`, `deviceUuid.conf`, and `license_push.info` with
`licensePeerIdPushed` and `frameoVersionWhenPushed=35890`.

### Framework connectivity probe

`captive_portal_server`, `captive_portal_http_url` and `captive_portal_https_url` are all `null`, so
the AOSP 8.1 default applies: `http://connectivitycheck.gstatic.com/generate_204`. With the vendor
updaters disabled this is the only update-adjacent request the unit makes, and it is why the live
`netstat` shows Google addresses (`…1e100.net`).

### No update is offered (checked 2026-10-16)

The frame's own check was relayed to the real Adups host so the answer would be genuine rather than
static. The vendor answered:

```json
{"flag":{"check_freq":2940,"check_url":"no","isFull":0,"sendId":"0",
         "job_schedule_time":"600#1440","job_schedule_downloading_time":"60#1440",
         "isupgrade":1,"isReportApk":0},"status":1010}
```

`check_url` is `"no"`, so no package is offered, and the "Wireless Update" screen showed **"Your
device's software is currently up to date."** for `rf001e_user_20231007_20231007-1900`. The next check
is scheduled `check_freq: 2940` minutes later (~49 h).

The Rockchip endpoint is dead: `www.rockchip.com:2300` does not answer (the name resolves through
Cloudflare, which does not serve port 2300). That is a BSP default that was never wired up for this
build.

So **no Android or firmware update exists for this unit through any of the three channels**: the ODM
updater reports it up to date, the Rockchip updater has no reachable server, and Frameo only updates
its own app (`serviceupdates.frameo.net`). The unit stays on Android 8.1, build
`rf001e_user_20231007` (kernel 4.4.138, security patch 2020-11-05) — there is no newer OS to wait for,
which is why the WebView/modern-engine route above is the way to keep the dashboard usable.

## Status against the README phase map

| Phase | State |
| --- | --- |
| 1 Identify | Done. Not a BIUFRAME, Skylight or PF1007L; neither guide applies as written. |
| 2 ADB | Done, over USB. A USB-A to USB-C cable is required. |
| 3 Loader mode | Not reached, not needed so far. |
| 4 Back up | Done and verified over ADB, before `userdata`. Restore path untested. |
| 5 Root | Shipped `su` works with no prompt. |
| 6 Make it useful | **Partly.** A current WebView is in place through the vendor overlay route, and the dashboard renders on it. The kiosk app itself has not been built or installed on this unit. |
| 7 Networking | Onboard Wi-Fi works. Port 5555 was closed; no network ADB. |
| 8 Vendor updates | Done: `com.adups.fota` and `android.rockchip.update.service` are disabled (see [Changes made](#changes-made-to-the-frame)), and their endpoints are recorded under [Update checks](#update-checks-the-urls-behind-each-updater). Note that Frameo had **already replaced its own version**: the running copy was v1.32.16 in `/data/app`, not the `/system/priv-app/Frameo` copy; Frameo itself is disabled too now — see [the later note](#changes-made-to-the-frame). |
| 9 Security hand-off | Pending. |

## Guesses (unverified)

- Whether Frameo relaunches itself over a third-party HOME app: not observed, because
  `com.wesbos.homehq` took over as HOME and Frameo was then disabled before this could be watched
  (see [Changes made](#changes-made-to-the-frame)).
- Whether loader mode is reachable by holding power at plug-in. It was not reached on C-to-C
  (where nothing enumerated at all); it was not retried on the working A-to-C cable.
- Whether the Rockchip updater ever gets a non-empty `ro.product.ota.host2`; on this build the only
  reachable host is `www.rockchip.com:2300`.

## Changes made to the frame

No flash partition, no `/system` file and no boot image was changed. Everything below reverses
with the frame's own package manager.

| Change | How | Undo |
| --- | --- | --- |
| Adups OTA updater off (`com.adups.fota` v5.28, `INTERNET` granted) | `pm disable-user --user 0 com.adups.fota` | `pm default-state --user 0 com.adups.fota` |
| Rockchip updater off (`android.rockchip.update.service` v1.8.1, `INTERNET` granted, service live against `www.rockchip.com:2300`) | `pm disable-user --user 0 android.rockchip.update.service` | `pm default-state --user 0 android.rockchip.update.service` |
| Firefox 143.0.4 `armeabi-v7a` installed, then removed again, to check what the dashboard looks like on a current engine | `adb install -r fenix-143.0.4.multi.android-armeabi-v7a.apk` (SHA-256 `af560738…3829f8`, the pin in `scripts/biuframe-setup.sh`) | `adb uninstall org.mozilla.firefox` |
| Mulch SystemWebView 131.0.6778.200 added as a **second** WebView provider (`us.spotco.mulch_wv`), selected as the implementation | see [A modern WebView without touching `/system`](#a-modern-webview-without-touching-system-verified) | `cmd webviewupdate set-webview-implementation com.android.webview`, remove the overlay, reboot, `adb uninstall us.spotco.mulch_wv` |

On the stock WebView (61) the same page loads but is visibly wrong; Firefox 143 renders it
correctly and is the reference for what the dashboard should look like at 1920×1080. See
[Dashboard compatibility](#dashboard-compatibility) for what the stock engine cannot do.

`pm default-state` is the undo rather than `pm enable`: both packages reported the default state
(`enabled=0`) before the change, so `pm enable` would leave them explicitly enabled. This mirrors
the [Akimart ZN-DP1002](akimart-zn-dp1002.md) record, which disables the same two packages on a
build from the same vendor stack.

`net.frameo.frame` was deliberately left enabled. It is the only HOME app installed, so disabling
it before another launcher exists would leave the frame with no interface (README rule 9). It is
also still self-updating: the running copy is v1.32.16 under `/data/app`, not the system copy.

**Later the same day** the state moved on, so that reasoning no longer holds: `com.wesbos.homehq`
(v1.1, versionCode 2, installed 2026-10-16 17:28) was added as a HOME app and is now the launcher,
and `net.frameo.frame` was then disabled (`pm disable-user`, `enabled=3`, no Frameo process running).
With Frameo off, none of the three update channels above is active; only the framework connectivity
probe still fires.

**A capture, all reverted (2026-10-16).** Reading the Adups host, then its request path, took two
passes. In the first, `com.adups.fota` was re-enabled, launched and disabled again, and a runtime
`iptables` rule sent its DNS to a logging resolver on the test host. In the second, the frame was
made to trust a temporary capture CA and the app's TLS was tunnelled to a local listener:

| Temporary change | Reverted by |
| --- | --- |
| Runtime `iptables` OUTPUT rules (a DNS redirect, then a TLS redirect for uid 10022) | `iptables -D`; nothing on the frame survives a reboot |
| `adb reverse tcp:4443 tcp:8443` tunnel | `adb reverse --remove-all` |
| CA at `/system/etc/security/cacerts/f4cb1375.0`, written with `/system` remounted read-write | file deleted, `/system` back to `ro`, and the `cacerts` listing hashes identically to before (`md5 ab809786…`, 166 entries) |

The frame's configured DNS was never changed, the app's certificate check passed only against that
temporary CA, and the reply it received carried no update (an empty body), so nothing was downloaded
and nothing was flashed. `com.adups.fota` is back to `enabled=3` with no process running.

The only other write was the frame adding the host ADB key to `/data/misc/adb/adb_keys`, which it
did itself when the authorization was accepted.
