# Frameo 15.6-inch 159K (RK3326, Android 8.1)

Status: **draft device report.** The boot-ramdisk TCP ADB patch has been
written, read back and booted to the Frameo home screen on one unit.
Network ADB and root validation are still pending.

## Identity

| Item | Observed value |
| --- | --- |
| Brand / size | Frameo / BIGASUO “Digital Photo Frame 159K”, 15.6-inch |
| SoC | Rockchip RK3326 |
| Android | 8.1 (API 27) |
| Firmware / build | `RK3326_8.1_AY_FRAMEO_202605131837` on the tested unit |
| Boot partition | LBA `0x22000`, 131,072 sectors (64 MiB) |
| Flash | SAMSUNG, 59,640 MB, 122,142,720 sectors |
| Rockchip Loader USB ID | `2207:330d` |
| Unique identifiers | Not recorded here |

## Loader and backup

The tested 159K entered Rockchip Loader by holding the power button while
reconnecting wall power and USB. The display stayed black and the Mac
showed `2207:330d`; `rkdeveloptool ld` reported Loader/Maskrom.

Before any flash write:

1. Take a full pre-userdata backup and verify its raw and compressed
   hashes.
2. Read the 64 MiB `boot` partition more than once and confirm the stock
   SHA-256:
   `8ab5a0be2740c86ee6af013a9675eb6a571e0dff0967574a4657d5415b8b717e`.
3. Keep the verified stock boot image as the rollback source.

The stock loader has a 32 MiB read limit. Reading the boot partition at
`0x22000` and verifying the full image requires the pinned unrestricted
reader used for the backup; do not trust reads that return `0xCC` filler.
This repository does not ship boot images, keys, or dumps.

## Boot image layout

The tested stock boot image is Android header v0 with a 2 KiB page size:

| Component | Bytes | Notes |
| --- | --- | --- |
| Kernel | 19,873,800 | Preserved byte-for-byte |
| Ramdisk slot | 1,476,608 | New gzip must stay in this 2 KiB-aligned slot |
| RSCE second stage | 4,301,312 | Preserved; offset `0x145d800` |
| Page size | 2,048 | Header v0 |
| Cmdline | `buildvariant=user` | Preserved |
| Legacy header ID | `a5b0f89d351ce1d07ab5515e43f2334911643c2f` | Preserved; it is not a signature |
| Tail | 41,451,520 zero bytes | Preserved |

Kernel SHA-256:
`457981b0120bf73be9a8c330ca2311418adfe256c6abd3af4ead680cdb1e2d39`.

RSCE SHA-256:
`f858c17f67a1fee5c4ee973606b901ea2beeea87ff2b8a58f6ab394071362cf1`.

## TCP ADB boot-ramdisk patch

The builder adds only:

1. `/adb_keys` containing the supplied host ADB public key, with its
   comment removed. The file is uid/gid 0, mode 0600. No private key is
   included.
2. Two commands in the existing `on property:sys.boot_completed=1` block
   of `init.root.rc`:

```text
setprop service.adb.tcp.port 5555
restart adbd
```

The patch does **not** change:

- `ro.secure=1` or `ro.adb.secure=1`;
- the USB configuration (`persist.sys.usb.config`/`sys.usb.config` are
  untouched);
- `ro.debuggable`, `adbd`, the kernel, the RSCE second stage, the cmdline,
  the boot header ID, or the partition tail;
- `system`, `vendor`, `uboot`, `trust`, or `resource`.

The `adb_keys` SHA-256 for the tested public key was
`19d6d0fecb5490ecf638d39a896222a57b864de521078ca7a588f018e5c60801`.
That is a public-key hash only; the private key remains in
`~/.android/adbkey`.

The candidate boot image SHA-256 is
`40b5138e29d706d3f64365e09c105f619cef125e3ce1840404d30e24f05f077c`.

No `su` binary is added. Root is expected from the frame’s shipped
SuperSU `/system/xbin/su` and the vendor `rootservice`/`daemonsu` boot
path. That behavior is still pending validation.

## USB limitation

The 159K USB-C Android gadget did not enumerate on the tested unit. A
USB-config variant, DTB/OTG-role changes and several debug-log attempts
were tried; none produced a USB ADB device. Loader mode worked, and the
same cable was proven for loader writes/reads. The TCP-only patch
therefore leaves USB alone and uses network ADB. Do not treat a
successful loader connection as proof that Android USB ADB will enumerate.

## Build

The builder is offline-only and refuses if the source does not match the
verified stock image or layout.

```sh
python3 scripts/build-frameo159k-boot.py \
  --source diagnostics/frameo-159k/boot-stock-read1.img \
  --public-key ~/.android/adbkey.pub \
  --output-dir diagnostics/frameo-159k/boot-patched

shasum -a 256 diagnostics/frameo-159k/boot-patched/boot.img
# require 40b5138e29d706d3f64365e09c105f619cef125e3ce1840404d30e24f05f077c
```

The output directory is ignored by git. The manifest records the source,
candidate, ramdisk slot, key hash and preserved components.

## Flash and rollback

Write only the `boot` partition:

```sh
rkdeveloptool wl 0x22000 diagnostics/frameo-159k/boot-patched/boot.img
rkdeveloptool rl 0x22000 131072 diagnostics/frameo-159k/boot-patched/boot-readback.img
shasum -a 256 \
  diagnostics/frameo-159k/boot-patched/boot.img \
  diagnostics/frameo-159k/boot-patched/boot-readback.img
# both must be 40b5138e29d706d3f64365e09c105f619cef125e3ce1840404d30e24f05f077c
```

Do not reset until the readback matches. Rollback is the verified stock
boot image:

```sh
rkdeveloptool wl 0x22000 diagnostics/frameo-159k/boot-stock-read1.img
rkdeveloptool rl 0x22000 131072 diagnostics/frameo-159k/boot-patched/boot-stock-readback.img
# both must be 8ab5a0be2740c86ee6af013a9675eb6a571e0dff0967574a4657d5415b8b717e
```

## Test plan and status

- [x] Build the candidate and verify the source/candidate hashes.
- [x] Write the boot partition and read back all 131,072 sectors.
- [x] Boot the frame to the Frameo home screen.
- [ ] Connect the frame to a network and run:

```sh
adb connect <frame-ip>:5555
adb devices
adb shell id
adb shell su -c id
adb shell su 0 id
adb shell getprop sys.config.rootservice
adb shell ps | grep daemonsu
adb shell getprop ro.secure
adb shell getprop ro.adb.secure
```

Expected: `adb shell id` is uid 2000 (shell); a working shipped `su`
returns uid 0; `sys.config.rootservice` is `started`; `daemonsu` is
running; `ro.secure` and `ro.adb.secure` are both `1`. Do not claim root
until the `su` checks pass.

A no-internet Wi-Fi AP is sufficient; the frame does not need internet
access for ADB. Keep the frame on a trusted network.

## Security

- ADB authentication remains enabled; only the supplied public key is
  trusted.
- The patch adds no private key, `su` binary, `ro.debuggable` change or
  `adb root` behavior.
- The vendor `rootservice` starts `daemonsu`; installed apps on the frame
  should be treated as untrusted because that pre-existing vendor root
  path may be reachable by them.
- Do not publish backups, boot images, private keys, or device-specific
  identifiers.

## References

- Repo issue #126: the 159K owner report and loader observations.
- `docs/devices.md`: device index.
- `scripts/build-frameo159k-boot.py`: guarded builder.
