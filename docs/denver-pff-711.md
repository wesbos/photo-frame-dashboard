# Denver PFF-711 7" Frameo frame (RK3126, Android 6.0.1, 512 MB RAM)

Record of one unit, 2026-10-17, Linux host (Arch). Observations are kept separate from guesses.
Unique identifiers (serial, MAC, IP) are left out.

**Short version:** Frameo's Beta toggle starts `adbd`, but ADB stays `unauthorized` and no prompt
can appear (SystemUI is disabled). The board has an **Upgrade** button that enters Rockchip Loader
mode. `boot` is a ramdisk-only image in the older Rockchip **`KRNL` wrapper**, not `ANDROID!`;
adding the host's public key as `/adb_keys` to that ramdisk with
[`scripts/krnl-add-adb-key.py`](../scripts/krnl-add-adb-key.py) authorized USB ADB, and the shipped
SuperSU `su` gave root. Same platform family as the [Denver PFF-1015](denver-pff-1015.md) and the
[Uhale 102KZ](uhale-102kz.md), but a 2018 build with its own (`esp8089`) product name.

## Observations

### Identity

| | |
| --- | --- |
| About screen | Denver, Frameo v1.1.1 |
| Brand / model | `ro.product.brand=rockchip`, model `PFF-711`, device `esp8089`, manufacturer `DENVER ELECTRONICS A/S` |
| Fingerprint | `rockchip/esp8089/esp8089:6.0.1/MXC89K/user.bnd_shh.20180321.205816:user/release-keys` |
| Board | Silkscreen `…RK3126-M733 A1.0`; tact switch labelled **Upgrade** next to a screw post |
| SoC | Rockchip RK3126 (`ro.board.platform=rk312x`, `ro.hardware=rk30board`), 32-bit |
| Kernel | Linux 3.10.0 |
| Android | 6.0.1, `user` build, `ro.secure=1`, `ro.debuggable=0`, `ro.config.low_ram=true` |
| SELinux | Permissive (`getenforce`; `androidboot.selinux=permissive` in the parameter block) |
| Display | 1024x600, 160 dpi |
| RAM / storage | 512 MB (`MemTotal: 502700 kB`); 8 GB Hynix NAND (`rkdeveloptool rfi`: 17,301,504 sectors, 16 KB pages), `/data` 5.3 GB |
| WebView | `com.android.webview` 44.0.2403.119 |
| SystemUI | `com.android.systemui` installed but **disabled**: no status bar, navigation bar or ADB prompt |
| Frameo | `net.frameo.frame` v1.1.1, installed in `/data/app` |
| Root | `/system/xbin/su` and `daemonsu` (SuperSU, 2018-03-21) |
| USB IDs | Android/ADB `2207:0006`, product string `PFF-711`; Rockchip Loader `2207:310d` |

### USB and ADB

- **Cable and port:** a USB-A to USB-C data cable. On a front-panel/hub port the frame kept dropping
  off the bus and rebooting; a rear motherboard port was stable. In Loader mode it runs from USB
  power alone.
- **ADB:** Frameo **Settings → About → Beta program** on. There is no separate ADB Access switch on
  this Frameo version; the Beta toggle itself starts `adbd` (`persist.sys.usb.config=adb` afterwards).
- `adb devices` showed **`unauthorized`** and no prompt ever appeared. Toggling Beta off and on with
  USB connected, replugging, rebooting the frame and `adb kill-server` did not change that.
  Guess: the prompt has nowhere to draw because SystemUI is disabled, as on the
  [Pastigio FRAME157](pastigio-frame157.md).
- No network ADB: TCP 5555 was closed, before and after the fix.
- Unlike the [PFF-1015](denver-pff-1015.md) and the Rollei 107, this `adbd` **does** check keys.

### Loader mode

1. Open the back cover.
2. Remove all power, so the frame is off.
3. Hold the **Upgrade** button, plug in USB, keep holding for 6–8 seconds, release.
4. `rkdeveloptool ld` → `Vid=0x2207,Pid=0x310d ... Loader`. The screen stays black.

Worked first time. `rkdeveloptool rci`, `rfi` and `rl` all worked with the stock loader; no
`db` of an external loader was needed. `rkdeveloptool rd` returns to Android.

### Partition table

From `mtdparts=rk29xxnand:` in the parameter block (`rkdeveloptool rl 0 0x2000 param.bin`).
Loader LBAs, 512-byte sectors. `boot` and `recovery` start one block later than on the Uhale 102KZ,
and `system` is 1.5 GiB.

| Partition | Start | Sectors |
| --- | --- | --- |
| uboot | `0x2000` | `0x2000` |
| misc | `0x4000` | `0x2000` |
| resource | `0x6000` | `0x8000` |
| kernel | `0xE000` | `0x6000` |
| boot | `0x14000` | `0x8000` |
| recovery | `0x1C000` | `0x10000` |
| backup | `0x2C000` | `0x20000` |
| cache | `0x4C000` | `0x40000` |
| metadata | `0x8C000` | `0x8000` |
| kpanic | `0x94000` | `0x2000` |
| system | `0x96000` | `0x300000` |
| radical_update | `0x396000` | `0x20000` |
| userdata | `0x3B6000` | rest |

### Backup (verified, partial)

`uboot`, `misc`, `resource`, `kernel`, `boot`, `recovery` and `kpanic` were each read twice with
`rkdeveloptool rl`; both reads had the same SHA-256 and no all-`0xCC` sector. `system` and
`userdata` were **not** backed up (nothing writes to them), so this does not meet the repo's
complete-device backup rule. Restore of anything other than `boot` is untested.

| Image | SHA-256 |
| --- | --- |
| stock `boot` partition (`0x8000` sectors) | `179e4fe85f63d0dd11c2357389347854b40126e44aaabdf41caa5dcc14840c9e` |
| stock `boot` `KRNL` blob (first 1,711,300 bytes) | `ecafbc4f2adb5b62eeee08bbb681b1948c8cc2d6345ad0023cae61c32889eb98` |
| `kernel` partition | `0f432c84b003f7b2303d4d7690b05351ee612b224ad27085525948348831cda4` |
| `recovery` partition | `127d2daae9558ac3ccb4ef35863ec64b74b3a249e931ecc8473403156e7e3e00` |

### The `KRNL` boot image

- Magic `KRNL`, uint32 LE payload length (1,711,288), gzip'd `newc` cpio ramdisk, uint32 LE CRC,
  then padding to the partition size. `kernel` is also `KRNL`; `recovery` is `ANDROID!`.
- The CRC is Rockchip's CRC32: polynomial `0x04C10DB7`, MSB first, initial value 0, no final XOR,
  over the gzip payload only. Recomputing it over the stock payload gave the stored `abb371b6`.
- The ramdisk has no `/adb_keys`. `sbin/adbd` contains the strings `/adb_keys` and
  `/data/misc/adb/adb_keys`, and `file_contexts` labels `/adb_keys` as `adb_keys_file`.
- `default.prop` sets `persist.sys.usb.config=none`; Frameo's toggle overrides it at runtime.

## What worked: `/adb_keys` in the `KRNL` ramdisk

[`scripts/krnl-add-adb-key.py`](../scripts/krnl-add-adb-key.py) only edits a file; it never touches the
device. It checks the `KRNL` magic and CRC, refuses a ramdisk that already has `/adb_keys`, appends one
cpio entry (`root:root`, `0644`) before `TRAILER!!!`, keeps every other entry byte for byte,
recompresses, recomputes the CRC and pads back to the input size. `ro.adb.secure` was left alone, so
other computers still need authorization.

```sh
rkdeveloptool rl 0x14000 0x8000 boot.img
sha256sum boot.img                     # stop unless it matches the stock partition hash above
python3 scripts/krnl-add-adb-key.py boot.img ~/.android/adbkey.pub boot-patched.img
rkdeveloptool wl 0x14000 boot-patched.img
rkdeveloptool rl 0x14000 0x8000 readback.img
cmp readback.img boot-patched.img && echo "readback matches"   # stop here if this fails
rkdeveloptool rd
```

Before writing, the patched image was unpacked again and its file tree compared with the stock
ramdisk: the only difference was the new `adb_keys`. The loader does not check signatures.

Result after the reboot:

```text
adb devices        → device (no prompt)
adb shell id       → uid=2000(shell)
adb shell su -c id → uid=0(root)
```

Authorized ADB survived later reboots.

**Undo:** Loader mode, then `rkdeveloptool wl 0x14000 boot.img` with the stock backup.

## Kiosk (owner's own app)

The owner shows a self-hosted dashboard written for Chrome 44 (ES5, flexbox, inline SVG, MJPEG in
`<img>`), so no WebView swap was needed. A small WebView Home app was installed and chosen as
**Home → Always** in the chooser (Android 6 has no `cmd package set-home-activity`).

- **Frameo has to be disabled.** With another app chosen as Home, Frameo still started itself after
  boot and covered it. After `su -c 'pm disable net.frameo.frame'` (waiting until
  `package-restrictions.xml` showed `enabled="2"`) the frame booted straight into the kiosk. Frameo's
  data is kept; `pm enable net.frameo.frame` undoes it.
- **Way back from Settings.** There is no navigation bar, so the kiosk opens Android Settings
  from an on-screen gesture and then shows a floating "back to dashboard" button (a
  `TYPE_PHONE` overlay, allowed with `appops set <pkg> SYSTEM_ALERT_WINDOW allow`). Checked by
  hand on the panel: Settings opened and the button led back.
- **The low-RAM whitelist is required here.** The first hand test failed: opening Settings
  killed the kiosk at once (`am_kill: [0,<pid>,<kiosk pkg>,0,user request after error]` 1 ms
  after `am_on_paused_called`), and its overlay button died with it, leaving no way back
  except ADB. This is the same Rockchip `completePauseLocked` patch as on the
  [PFF-1015](denver-pff-1015.md#low-ram-mode-kills-every-app-you-leave). The file
  `/system/etc/lowmem_package_filter.xml` has the same `<prev>` / `<next>` / `<empty>`
  sections; Frameo is not listed in it. Adding the kiosk package to `<prev>` and `<empty>`
  (original kept as `.bak`) and rebooting fixed it: the kiosk process stayed alive with
  Settings open and the button returned to it.
- **toybox `sed` broke the XML.** A `sed -i 's|…|…\n…|'` on the frame wrote non-text bytes
  instead of newlines, and the file no longer parsed (`file` reported `data`). It was rebuilt
  on the computer from the `.bak`, checked with an XML parser, pushed and compared with
  `cmp` before the reboot. Edit this file on the computer, not with the frame's `sed`.

## Status against the README phase map

| Phase | State |
| --- | --- |
| 1 Identify | Done. RK3126, 2018 `esp8089` build, NAND. |
| 2 ADB | Frameo Beta toggle, USB, but `unauthorized` with no prompt. |
| 3 Loader mode | Done: **Upgrade** button on the board. |
| 4 Back up | Partial: everything before `backup` plus `kpanic`; no `system`/`userdata`. |
| 5 Root | Host key in the `KRNL` boot ramdisk, then shipped `su`. |
| 6 Make it useful | Done: own kiosk app as Home, Frameo disabled, kiosk in the low-RAM whitelist. |
| 7 Networking | Onboard Wi-Fi works. Network ADB not enabled. |
| 8 Vendor updates | Not looked at. |
| 9 Security hand-off | Root `su` for any app; Android 6 from 2018. Keep it on an isolated network if network ADB is ever enabled. |
