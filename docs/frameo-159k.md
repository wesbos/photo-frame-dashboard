# Frameo 15.6-inch 159K (RK3326, Android 8.1)

Status: **historical success reports from two units.** The original macOS
owner confirmed that a boot-ramdisk TCP ADB patch booted to the Frameo home
screen, with network ADB and root through the shipped `su`. A second owner,
[ozzyonfire, using ArchLinux](https://github.com/wesbos/photo-frame-dashboard/pull/213#issuecomment-6457452772),
reported success after changing `/adb_keys` from root:root 0600 to
root:root 0644 and using separate ramdisk/header writes. The 0600 key
left ADB `unauthorized` on that unit. **The revised builder and guarded
recipe below have not been hardware-tested.** Other firmware variants
remain untested.

**This patch enables TCP ADB on port 5555 on all network interfaces after
every boot, with root available through the shipped `su`. Rejection of unknown host keys
has not been verified; do not treat preserved authentication properties
as proof of enforcement. Keep the frame on an isolated, trusted network.**

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

The [FRAME157 reader notes](pastigio-frame157.md#reader-needed-for-the-full-backup)
explain the same 32 MiB limit and helper patch. That frame used DDR
**v2.06**; the 159K used **v2.07** below. Do not substitute FRAME157's DDR
binary or firmware layout.

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

After the device-identity checks and owner approval described under
**Flash and rollback**, verify all three reader files against the hashes
above. Enter fresh BootROM and upload the tested pairing:

```sh
rkdeveloptool rd 3
xrock maskrom \
  diagnostics/frameo-159k/reader/rk3326_ddr_333MHz_v2.07.bin \
  diagnostics/frameo-159k/reader/rk3326_usbplug_v1.36-read-unlimited.bin
```

Place the matching official DDR and original helper, plus the locally
patched helper, in that reader directory. Keep xrock's default **RC4
enabled** for this upload; do not pass `--rc4-off`. This command uploads
the DDR v2.07/patched usbplug v1.36 pair; it does not use the RK3568 uploader.
The second owner
[reported xrock `50effce`](https://github.com/wesbos/photo-frame-dashboard/pull/213#issuecomment-6457452772);
the locally reviewed source checkout is
[`50effcef229a7e8ff85fde916e635cdd58fe8c09`](https://github.com/xboot/xrock/tree/50effcef229a7e8ff85fde916e635cdd58fe8c09).
This does not independently pin the original macOS execution.

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
   comment removed. The file is uid/gid 0, mode 0644 so the shell-uid
   `adbd` can read it. No private key is included.
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

The ramdisk's `default.prop` is a symlink to `system/etc/prop.default`.
The builder preserves that symlink and checks the matching extracted
system property file before accepting the build; it does not replace the
symlink with a regular file or edit the system partition.

No `su` binary is added. The owner confirmed root through the frame's
shipped `su`. The firmware includes SuperSU `/system/xbin/su` and a
vendor `rootservice`/`daemonsu` boot path; the patch leaves these intact.

## USB limitation

The 159K USB-C Android gadget did not enumerate on the tested unit. A
USB-config variant, DTB/OTG-role changes and several debug-log attempts
were tried; none produced a USB ADB device. The TCP-only patch
therefore leaves USB alone and uses network ADB.

## Build

The builder is offline-only and refuses a source boot image, layout or
system property file that does not match the pinned firmware. Extract
`/etc/prop.default` from the matching, verified **raw ext4 system partition
backup**. This path is inside that partition, which Android mounts at
`/system`; it is not a path inside the boot ramdisk. For example, with
`debugfs` from e2fsprogs (no `-w`, so the backup is opened read-only):

```sh
debugfs -R 'dump /etc/prop.default diagnostics/frameo-159k/system-prop.default' \
  diagnostics/frameo-159k/system.img
```

Use your own verified system partition backup at `system.img`; do not
substitute another frame's properties or fabricate this input from the
values below. The extracted file must be exactly **391 bytes**, SHA-256
`7f7514955dab69a06621b85eec79c39a22af7312b1d87c9e7558dd0a57d13692`.
The builder checks the complete file and requires exactly one
`ro.adb.secure=1` assignment before creating output.

```sh
python3 scripts/build-frameo159k-boot.py \
  --source diagnostics/frameo-159k/boot-stock-read1.img \
  --system-default-prop diagnostics/frameo-159k/system-prop.default \
  --public-key ~/.android/adbkey.pub \
  --output-dir diagnostics/frameo-159k/boot-patched-review
```

Use a new output directory. Format 2 of `manifest.json` records the
source and candidate images, property-file evidence, public-key hash,
preserved components and four sector-aligned payload files:

| Payload | File | Device LBA | Sectors | Bytes |
| --- | --- | --- | --- | --- |
| Original header | `orig-header.bin` | `0x22000` | 1 | 512 |
| Candidate header | `new-header.bin` | `0x22000` | 1 | 512 |
| Original ramdisk slot | `orig-ramdisk.bin` | `0x2B7A8` | 2,884 | 1,476,608 |
| Candidate ramdisk slot | `new-ramdisk.bin` | `0x2B7A8` | 2,884 | 1,476,608 |

`boot.img` remains the complete 64 MiB candidate for offline comparison
and full readback verification. It is not the write payload. Retain the
stock image and this exact output directory for undo. The manifest's
`NOT_FLASHED_NOT_BOOTED` status describes the newly built candidate;
building an image does not establish that it will boot on a device.

## Flash and rollback

The recipe below is specific to this firmware and writes only the two
ranges above. The builder neither accesses a device nor authorizes a
write. Obtain the owner's approval for the selected operation and finish
these checks before running the recipe:

1. Have a verified backup and the pinned 64 MiB stock boot image ready.
2. With only the intended frame connected, run `rkdeveloptool ld`,
   `rkdeveloptool rci`, `rkdeveloptool rfi` and `rkdeveloptool ppt`.
   Confirm exactly one Rockchip device (`2207:330d`), RK3326, SAMSUNG
   flash with 122,142,720 sectors, and a `boot` partition starting at
   `0x22000` with 131,072 sectors. Stop if any identity or layout differs.
3. Load the exact reader setup above and verify unrestricted reads,
   including beyond 32 MiB. After leaving that RAM reader session, it
   must be re-established before relying on full readbacks.
4. Select `install` to go from the pinned stock image to this candidate,
   or `undo` to restore stock from this exact installed candidate. Keep
   the matching manifest; a different candidate or any unknown current
   image is refused. Investigate a failed or partial write with the
   owner before deciding on recovery.

This common recipe validates **all offline artifacts before any device
command**, then reads and checks the current full boot image. It writes
the ramdisk slot first and requires an exact size/hash readback before
writing the header. It verifies the header readback and finally the
entire boot partition. The same sequence applies to undo. Any exception,
command failure or mismatch stops execution. The recipe never resets the
frame; a failure leaves it in the reader session for investigation.

```sh
operation=install  # Change to undo only for this candidate's approved rollback.
python3 - "$operation" <<'PY'
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

output = Path("diagnostics/frameo-159k/boot-patched-review")
stock_path = Path("diagnostics/frameo-159k/boot-stock-read1.img")
STOCK_SHA256 = "8ab5a0be2740c86ee6af013a9675eb6a571e0dff0967574a4657d5415b8b717e"
BOOT_LBA = 0x22000
BOOT_SECTORS = 131072
BOOT_BYTES = 67108864
EXPECTED = {
    "orig_header": ("orig-header.bin", 0x22000, 1, 512),
    "new_header": ("new-header.bin", 0x22000, 1, 512),
    "orig_ramdisk": ("orig-ramdisk.bin", 0x2B7A8, 2884, 1476608),
    "new_ramdisk": ("new-ramdisk.bin", 0x2B7A8, 2884, 1476608),
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def checked(data, size, digest, label):
    require(len(data) == size, f"{label}: wrong byte count")
    require(sha256(data) == digest, f"{label}: SHA-256 mismatch")
    return data


def main():
    require(len(sys.argv) == 2 and sys.argv[1] in ("install", "undo"),
            "operation must be install or undo")
    operation = sys.argv[1]
    manifest = json.loads((output / "manifest.json").read_text())
    require(type(manifest["format"]) is int and manifest["format"] == 2,
            "manifest format must be 2")
    for field in ("source_boot_bytes", "candidate_boot_bytes"):
        require(type(manifest[field]) is int and manifest[field] == BOOT_BYTES,
                f"{field}: wrong size")
    require(manifest["source_boot_sha256"] == STOCK_SHA256,
            "manifest source hash is not pinned stock")
    stock = checked(stock_path.read_bytes(), BOOT_BYTES, STOCK_SHA256, "stock")
    candidate_hash = manifest["candidate_boot_sha256"]
    candidate = checked((output / "boot.img").read_bytes(), BOOT_BYTES,
                        candidate_hash, "candidate")
    require(candidate_hash != STOCK_SHA256, "candidate equals stock")
    payloads = manifest["payloads"]
    require(isinstance(payloads, dict) and set(payloads) == set(EXPECTED),
            "manifest must contain exactly the four expected payloads")
    data = {}
    for name, (filename, lba, sectors, size) in EXPECTED.items():
        item = payloads[name]
        require(item["file"] == filename, f"{name}: wrong filename")
        for field, expected in (("lba", lba), ("sectors", sectors), ("bytes", size)):
            require(type(item[field]) is int and item[field] == expected,
                    f"{name}: wrong {field}")
        data[name] = checked((output / filename).read_bytes(), size,
                             item["sha256"], name)
        offset = (lba - BOOT_LBA) * 512
        image = stock if name.startswith("orig_") else candidate
        require(data[name] == image[offset:offset + size],
                f"{name}: does not match full-image slice")
    for source, target, prefix in ((stock, candidate, "new"),
                                    (candidate, stock, "orig")):
        rebuilt = bytearray(source)
        for part in ("ramdisk", "header"):
            name = f"{prefix}_{part}"
            _, lba, _, size = EXPECTED[name]
            offset = (lba - BOOT_LBA) * 512
            rebuilt[offset:offset + size] = data[name]
        require(rebuilt == target, f"{prefix}: reconstruction differs outside payloads")

    # Stage validated bytes so later changes to the original files cannot change a write.
    with tempfile.TemporaryDirectory(prefix="159k-verified-", dir=output) as directory:
        work = Path(directory)
        for name, payload in data.items():
            staged = work / EXPECTED[name][0]
            staged.write_bytes(payload)
            checked(staged.read_bytes(), len(payload), sha256(payload), name + " staged")

        def read_checked(lba, sectors, filename, digest):
            path = work / filename  # Each read uses a fresh path, never a stale readback.
            require(not path.exists(), f"readback path already exists: {path}")
            subprocess.run(["rkdeveloptool", "rl", hex(lba), str(sectors), str(path)],
                           check=True)
            checked(path.read_bytes(), sectors * 512, digest, filename)

        before_hash = STOCK_SHA256 if operation == "install" else candidate_hash
        after_hash = candidate_hash if operation == "install" else STOCK_SHA256
        prefix = "new" if operation == "install" else "orig"
        read_checked(BOOT_LBA, BOOT_SECTORS, "boot-current.img", before_hash)
        for part in ("ramdisk", "header"):
            name = f"{prefix}_{part}"
            filename, lba, sectors, size = EXPECTED[name]
            staged = work / filename
            checked(staged.read_bytes(), size, sha256(data[name]), name + " before write")
            subprocess.run(["rkdeveloptool", "wl", hex(lba), str(staged)], check=True)
            read_checked(lba, sectors, part + "-readback.bin", sha256(data[name]))
            # The header iteration is unreachable unless ramdisk readback succeeds.
        read_checked(BOOT_LBA, BOOT_SECTORS, "boot-full-readback.img", after_hash)
        print(f"Verified {operation}: full boot SHA-256 {after_hash}; no reset performed")


try:
    main()
except Exception as error:
    raise SystemExit(f"STOP: {error}; do not reset or retry a write without investigation")
PY
```

Only a successful final full-image check establishes that this operation's
bytes reached flash. It does not establish that the revised candidate
boots. Do not reset or attempt another write after any failure.

## Test plan and status

The original macOS report confirmed a written/read-back boot image,
Frameo home-screen boot, network ADB and shipped-`su` root. Those are
historical results for that owner's candidate. The second ArchLinux
[report by ozzyonfire](https://github.com/wesbos/photo-frame-dashboard/pull/213#issuecomment-6457452772)
confirms that root:root 0644 resolved `unauthorized`, with separate
ramdisk/header writes. These owner reports motivate the revised builder;
neither is a hardware test of its current output or this guarded recipe.

For a newly built candidate, these checks are still pending on hardware:

- [ ] Verify both write ranges and the full boot image with the recipe above.
- [ ] Boot to the Frameo home screen and connect over network ADB.
- [ ] Confirm shell uid and root through the shipped `su`.
- [ ] Test that a fresh, unauthorized host key is rejected.

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
access for ADB. Keep the frame on an isolated, trusted network.

## Security

**TCP 5555 listens on all network interfaces after every boot, and an
admitted ADB client can reach the shipped `su`. Unknown-key rejection is untested. Isolate
this frame from untrusted clients even though `ro.secure=1` and
`ro.adb.secure=1` are preserved.**

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
