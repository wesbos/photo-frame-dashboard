# TAPINSAW DW10 (S580) frame access notes

One TAPINSAW DW10 frame tested on macOS on 2026-11-08. **Persistent root USB ADB
was achieved** — the host key was written into `/system/etc/security/adb_keys`
and survives cold power cycles. **A verified firmware backup was not completed**:
the frame's USB link and `adbd` dropped every few minutes, and every bulk-read
attempt died mid-transfer. No kiosk was installed. The unit was retired by the
owner during setup. This is a record of one unit, not a setup script.

The board is the same Spreadtrum `si006asb` / `sp7731g_1h10` product family as
the [SI006](si006-uhale.md), [VTimes VT01001](vtimes-vt01001.md),
[Sammix AW105](sammix-aw105-uhale.md) and [HSB / F10](uhale-hsb-f10.md)
reports — same partition layout before userdata — under a new vendor brand and
a newer build (`W26.22.2-16`). The FEL and Rockchip loader routes do not apply.

## Confirmed identity

| Field | Observed value | Source |
| --- | --- | --- |
| Retail product | TAPINSAW DW10 digital picture frame | Retail box / About screen |
| Vendor app | Frameo `v1.30.19 (69880)` | Frameo Settings → About |
| Brand / model | `S580` (`ro.product.model`) | `adb devices -l`, `getprop` |
| Firmware | `SPRD_S580_V01_202605261639` | About screen build string |
| Build fingerprint | `SPRD/si006asb/sp7731g_1h10:6.0/MRA58K/W26.22.2-16:user/release-keys` | `getprop ro.build.fingerprint` |
| Android / ABI | 6.0 / `armeabi-v7a` (same product family; ABI not re-verified) | fingerprint, sibling reports |
| eMMC | 30,535,680 sectors of 512 bytes — same as SI006 | `/sys/block/mmcblk0/size` |
| Userdata | `mmcblk0p23`, starts at sector 3,334,144 — identical layout to SI006/VTimes | sysfs |
| USB | VID `0x1782`, PID `0x4012`, name `Spreadtrum` | macOS IORegistry |
| Cable path | USB-A upstream (monitor hub) to USB-C. **USB-C to USB-C directly into the Mac did not enumerate** | observation |
| Display | 1280 × 800-class panel (not re-measured) | retail listing |
| WebView | `com.android.webview` **106.0.5249.126 already installed** — no swap needed | `dumpsys package` |

## Enabling ADB

Frameo Settings → About → **Beta Program** on → **ADB Access** on, per
[Frameo's own instructions](https://support.frameo.com/hc/en-us/articles/6126183308434).
With the cable connected through a USB-A-upstream hub, `adb devices` showed the
unit as `unauthorized`.

## Authorization without a visible prompt

The notable difference from the sibling reports: **no RSA "Allow USB debugging?"
dialog was ever observed.** The unit stayed `unauthorized` through:

- multiple cold boots,
- ADB Access toggled off/on,
- `adb reconnect` cycles,
- early-boot polling at ~0.3–2 s intervals.

During one boot cycle it spontaneously changed to `device` — the trigger was
not identified (no prompt seen, no host-side action beyond ordinary polling).
Once `device`, `adb shell id` returned `uid=0(root)` directly
(`ro.secure=0`, `ro.debuggable=1`), and `su -c id` / `su 0 id` also returned
root. SELinux state was not recorded.

Treat "no prompt" on this firmware as possibly transient: keep polling across
boots rather than assuming the AOA-keyboard route is required immediately.

## Making authorization survive reboot

Same mechanism as [si006](si006-uhale.md) and [vtimes](vtimes-vt01001.md):
`/init.sc8830.rc` copies `/system/etc/security/adb_keys` over
`/data/misc/adb/adb_keys` at boot. A key added only to the `/data` file is
wiped on reboot — observed directly: after one reboot the unit returned to
`unauthorized`.

Fix, as root (`adb shell` is already uid 0):

1. `adb push ~/.android/adbkey.pub /data/local/tmp/host.pub`
2. `mount -o remount,rw /system`
3. Append a newline plus the public key to `/system/etc/security/adb_keys`
   (the factory file has no trailing newline — append `echo` first or the key
   joins the previous line).
4. `mount -o remount,ro /system`

Verified across a cold power cycle: the unit re-enumerated as `device` with
no prompt and no toggle.

Undo: the appended key is identifiable by its content — remove the matching
line(s) from `/system/etc/security/adb_keys` the same way (remount rw,
edit, remount ro). No factory copy of that file was saved on this unit;
the `/data` copy regenerates from it at boot regardless.

## Wi-Fi and network ADB

- `service.adb.tcp.port=5555` was already set in `/system/build.prop`, but
  `adbd` did not listen until `adb tcpip 5555` was run over USB.
- After `adb tcpip 5555`, `adb connect <ip>:5555` authorized immediately
  (the persisted key works over TCP too) and `adb shell` was root.
- The TCP transport **went `offline` under sustained load** and did not
  recover — consistent with the `adbd` restart behavior in
  [uhale-hsb-f10.md](uhale-hsb-f10.md). USB and TCP both proved unreliable
  for bulk transfer on this unit.
- Wi-Fi join with no saved network: appending a `network={...}` block to
  `/data/misc/wifi/wpa_supplicant.conf` (SSID/PSK, `key_mgmt=WPA-PSK`), then
  `svc wifi disable; svc wifi enable`, associated normally. The framework
  did not overwrite the file during the session. Undo: remove the block or
  factory-reset (`/data` only).

## USB stability

The dominant problem on this unit. `adb devices` dropped to empty every few
minutes on both transports; `ioreg` lost the Spreadtrum device entirely.
`adb reconnect` made it worse (the device vanished from `adb devices` until
physical replug in some cases). A detached `dd` writing a partition dump to
`/data/local/tmp` also stopped mid-write, so session-detached processes are
not guaranteed to survive `adbd` restarts on this firmware.

What this means for backup: **chunked reads are required.** A single
`adb exec-out dd` stream of the ~1.63 GiB pre-userdata region never
completed. A 64 MiB-per-call chunked reader with per-chunk byte-count
verification and retries was built but not finished before the unit was
retired — treat it as an unproven approach, not a recipe.

## Backup status (incomplete)

- Pre-userdata region (sectors 0–3,334,143): **not captured.** Multiple
  stream attempts died with `adbd`; one on-frame `dd` reached ~178 MiB of
  1,707,081,728 before stopping.
- eMMC boot areas (`mmcblk0boot0`, `mmcblk0boot1`) and the secondary GPT:
  small gzip streams were captured over USB but **not verified** (no
  byte-count/hash readback performed).
- Userdata was not attempted.

No offline restore path was established. Because no writes beyond the two
access-related file edits above were made, there was nothing to restore.

## Downloads used

None installed on the frame. Host-side only: the AOA keyboard helper
(Python `ctypes`/`libusb`, per the [HSB / F10 protocol notes](uhale-hsb-f10.md))
was written but never needed — authorization succeeded without it. The
Terminal Emulator APK route was prepared but unused.

## Limits

- One unit, one firmware (`W26.22.2-16`). Other TAPINSAW/S580 units may
  differ; match the About-screen fingerprint before reusing anything here.
- The spontaneous authorization was not reproduced on demand; the trigger
  is unknown. It may have been a transient early-boot window.
- `adb tcpip 5555` exposes **root** ADB to the LAN — the frame's network
  ADB was left configured but the unit was retired before the
  `service.adb.tcp.port=-1` hardening from the sibling reports could be
  applied and verified.
- The SystemUI malware-loader findings in
  [sammix-aw105-uhale.md](sammix-aw105-uhale.md) were **not checked** on
  this unit; the same `si006asb` product family means the check is still
  warranted on any surviving sibling.
