# Frameo 15.6-inch 159K (RK3326, Android 8.1)

Status: **tested on one unit, using macOS.** The boot-ramdisk TCP ADB patch
has been written, read back and booted to the Frameo home screen. The
owner confirmed working network ADB and root through the shipped `su`.
Other firmware variants have not been tested.

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
reconnecting its single USB cable, which carries both power (5 V, 3 A)
and data. The display stayed black and the Mac
showed `2207:330d`; `rkdeveloptool ld` reported Loader/Maskrom.

Before any flash write:

1. Take a full pre-userdata backup and verify its raw and compressed
   hashes.
2. Read the 64 MiB `boot` partition more than once and confirm the stock
   SHA-256:
   `8ab5a0be2740c86ee6af013a9675eb6a571e0dff0967574a4657d5415b8b717e`.
3. Keep the verified stock boot image as the rollback source.

The stock loader has a 32 MiB read limit. Reading the boot partition at
`0x22000` and verifying the full image requires the unrestricted reader
below; do not trust reads that return `0xCC` filler. This repository does
not ship boot images, keys, or dumps.

### Reader used on the tested unit

The original DDR and USB-helper binaries match Rockchip's official rkbin commit
[`3968b8eb04e365e64480a6b24f776273c6708e95`](https://github.com/rockchip-linux/rkbin/tree/3968b8eb04e365e64480a6b24f776273c6708e95),
under `bin/rk33/`. The table also identifies the locally patched helper:

| Binary | SHA-256 |
| --- | --- |
| `rk3326_ddr_333MHz_v2.07.bin` | `55f67007fe8e01efbf7892957b7f0dc7e0703c29273fb9a831835ef9f9d5daf0` |
| `rk3326_usbplug_v1.36.bin` | `886b3ff055df92411ceddb9f851cbee753a93203bab55f5711f7c69fd1874f71` |
| `rk3326_usbplug_v1.36-read-unlimited.bin` (locally patched) | `3f27fc0e248d8f1a96c1b5356449b333feafb16caa2b854e5354083cf8649090` |

The patched helper differs only at file offset `0x908c`: `ee031032`
(`mov w14, #0x10000`) becomes `0e008012` (`mov w14, #-1`), raising the
shared read limit. These bytes apply only to the exact helper above.
`scripts/load-usb-reader.py` targets RK3568 and is not the uploader for
this frame.

The reader was loaded into RAM, not installed to flash. A responding
flash-info query alone does not establish unrestricted reads: verify
repeated reads against the backup, including data beyond 32 MiB. The
reader files identify this unit's tested setup; they do not establish
compatibility with another frame's DDR or firmware.

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

No `su` binary is added. The owner confirmed root through the frame's
shipped `su`. The firmware includes SuperSU `/system/xbin/su` and a
vendor `rootservice`/`daemonsu` boot path; the patch leaves these intact.

## USB limitation

The 159K USB-C Android gadget did not enumerate on the tested unit. A
USB-config variant, DTB/OTG-role changes and several debug-log attempts
were tried; none produced a USB ADB device. The TCP-only patch
therefore leaves USB alone and uses network ADB.

## Build

The builder is offline-only and refuses if the source does not match the
verified stock image or layout.

```sh
python3 scripts/build-frameo159k-boot.py \
  --source diagnostics/frameo-159k/boot-stock-read1.img \
  --public-key ~/.android/adbkey.pub \
  --output-dir diagnostics/frameo-159k/boot-patched

python3 - <<'PY'
import hashlib
import json
from pathlib import Path

output = Path("diagnostics/frameo-159k/boot-patched")
manifest = json.loads((output / "manifest.json").read_text())
candidate = (output / "boot.img").read_bytes()
if (len(candidate) != 64 * 1024 * 1024
        or hashlib.sha256(candidate).hexdigest() != manifest["candidate_boot_sha256"]):
    raise SystemExit("STOP: candidate size or manifest hash mismatch")
print("Candidate matches its manifest:", manifest["candidate_boot_sha256"])
PY
```

The manifest records the source,
candidate, ramdisk slot, key hash and preserved components. Its
`NOT_FLASHED_NOT_BOOTED` status describes the newly built candidate;
building an image does not establish that it will boot on a device.

## Flash and rollback

The boot-only commands below use the tested unit's layout. The builder
itself neither flashes nor checks a connected device. Before **either**
write, obtain the owner's approval for that specific write and complete
these checks:

1. Have a verified backup and the verified 64 MiB stock boot image ready.
2. With only the intended frame connected, run `rkdeveloptool ld`,
   `rkdeveloptool rci`, `rkdeveloptool rfi` and `rkdeveloptool ppt`.
   Confirm exactly one Rockchip device (`2207:330d`), RK3326, SAMSUNG
   flash with 122,142,720 sectors, and a `boot` partition starting at
   `0x22000` with 131,072 sectors. Stop if any identity or layout differs.
3. Confirm the exact reader setup above is loaded and unrestricted reads
   have been verified. Re-entering Loader/MaskROM after a reset requires
   re-establishing that RAM reader before relying on full readbacks.
4. Read the current boot partition before writing:

   ```sh
   rkdeveloptool rl 0x22000 131072 diagnostics/frameo-159k/boot-current.img
   wc -c diagnostics/frameo-159k/boot-current.img
   shasum -a 256 diagnostics/frameo-159k/boot-current.img
   ```

   Require exactly 67,108,864 bytes. Before an initial patch, the hash
   must equal the pinned stock hash above. Before replacing or rolling
   back a known patched image, it must equal that installed image's
   saved manifest hash. Stop on an unknown hash; keep the read for
   investigation rather than overwriting an unknown device state.
5. Verify the image to be written immediately before the write: the
   candidate must pass the manifest check in **Build**, or the stock
   rollback file must be exactly 67,108,864 bytes with the pinned stock
   hash. Keep the saved manifest for the candidate actually installed.

After those checks, the candidate write and full readback are:

```sh
rkdeveloptool wl 0x22000 diagnostics/frameo-159k/boot-patched/boot.img
rkdeveloptool rl 0x22000 131072 diagnostics/frameo-159k/boot-patched/boot-readback.img
python3 - <<'PY'
import hashlib
import json
from pathlib import Path

output = Path("diagnostics/frameo-159k/boot-patched")
manifest = json.loads((output / "manifest.json").read_text())
for name in ("boot.img", "boot-readback.img"):
    data = (output / name).read_bytes()
    if (len(data) != 64 * 1024 * 1024
            or hashlib.sha256(data).hexdigest() != manifest["candidate_boot_sha256"]):
        raise SystemExit(f"STOP: {name} size or manifest hash mismatch; do not reset")
print("Candidate and full readback match the candidate manifest")
PY
```

Do not reset until the readback matches. If verification fails, keep the
device in the reader session and investigate before another write.
Rollback uses the verified stock boot image, after repeating the checks
above. If a failed write left an unknown current hash, stop and review
recovery with the owner before approving a stock restoration.

```sh
rkdeveloptool wl 0x22000 diagnostics/frameo-159k/boot-stock-read1.img
rkdeveloptool rl 0x22000 131072 diagnostics/frameo-159k/boot-patched/boot-stock-readback.img
cmp diagnostics/frameo-159k/boot-stock-read1.img diagnostics/frameo-159k/boot-patched/boot-stock-readback.img
shasum -a 256 \
  diagnostics/frameo-159k/boot-stock-read1.img \
  diagnostics/frameo-159k/boot-patched/boot-stock-readback.img
```

Require `cmp` to succeed and both hashes to match before resetting.

## Test plan and status

- [x] Build the candidate and verify the source/candidate hashes.
- [x] Write the boot partition and read back all 131,072 sectors.
- [x] Boot the frame to the Frameo home screen.
- [x] Connect over network ADB.
- [x] Obtain root through the shipped `su`.

The following are verification examples, not a transcript of the owner's
results. Use the `su` syntax supported by the shipped binary:

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
returns uid 0. The vendor boot path is expected to report
`sys.config.rootservice=started` with `daemonsu` running; `ro.secure` and
`ro.adb.secure` should both remain `1`. The owner confirmed working ADB
and root; exact shell, daemon and property outputs are not recorded here.

A no-internet Wi-Fi AP is sufficient; the frame does not need internet
access for ADB. Keep the frame on a trusted network.

## Security

- The patch adds the supplied public key and preserves the firmware's
  ADB authentication properties. It does not clear authorizations in
  `/data/misc/adb/adb_keys`.
- The patch adds no private key, `su` binary, `ro.debuggable` change or
  `adb root` behavior.
- The vendor `rootservice` starts `daemonsu`; installed apps on the frame
  should be treated as untrusted because that pre-existing vendor root
  path may be reachable by them.

## References

- Repo issue #126: the 159K owner report and loader observations.
- `docs/devices.md`: device index.
- `scripts/build-frameo159k-boot.py`: guarded builder.
