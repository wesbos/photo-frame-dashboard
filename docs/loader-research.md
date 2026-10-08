# Rockchip loader research

Research date: 2026-09-14. Device: Skylight 150-CAL, RK3568. These notes distinguish a responding RAM helper from unrestricted flash access. They contain no device serial numbers or private dump content.

## Observed and verified locally

- The device exposes Rockchip Loader mode, USB `2207:350a`.
- Flash reads beyond the first 32 MiB return repeated `0xCC` bytes. Those bytes must not be accepted as a firmware backup.
- A first-32-MiB backup exists locally at `backups/first-32MiB.img`; it is excluded from Git.
- The complete official `rk3568_ddr_1056MHz_v1.13.bin` is byte-for-byte identical to two regions in that backup, starting at byte offsets `0x8800` and `0x88800`. The match covers all 59,392 bytes, not just the version string.
- `rkdeveloptool rd 3` reported `Reset Device OK`. The old Loader disappeared and a new unnamed `2207:350a` device appeared with `bcdUSB=0x0200`. The user subsequently approved its macOS accessory prompt.
- The parent operator uploaded the matched DDR initializer and historical USB helper once. A configured `USB-MSC` device appeared as `2207:350a`, still with `bcdUSB=0x0200`. `rkdeveloptool rfi` responded with the expected `30539776 Sectors`.
- The initial post-upload `rl 65536 8` probe returned 4,096 bytes of `0xCC`. **The historical USB helper did not establish unrestricted reads. No successful full backup is claimed.**

### Descriptor caveat

Rockchip's scanning code uses the low bit of `bcdUSB` to label Loader versus MaskROM. Historical USB helper v1.14 retains `bcdUSB=0x0200`, so it is still labeled Maskrom despite responding to flash queries as `USB-MSC`. Do not repeat a RAM upload merely because that label remains. `scripts/load-usb-reader.py` recognizes an already-present `USB-MSC` helper, performs only a flash-info query, and refuses another upload. Responding to `rfi` proves neither unrestricted reads nor valid backup content.

## Why reads stop at 32 MiB

Rockchip's [U-Boot rockusb command implementation](https://github.com/rockchip-linux/u-boot/blob/next-dev/cmd/rockusb.c) checks whether the requested ending sector exceeds `RKUSB_READ_LIMIT_ADDR`. If it does, the handler fills the entire requested buffer with `0xCC` and reports the requested sector count. The [header](https://github.com/rockchip-linux/u-boot/blob/next-dev/include/rockusb.h) defines the limit as `32 * 2048` sectors, with 512 bytes per sector.

This explains the observed output without implying a defective eMMC. A request crossing the boundary can also return filler for its portion below the boundary; end the initial backup exactly at sector `0x10000`.

## Capability decoding correction

Observed raw capability bytes: `15 03 00 00 00 00 00 00` (hexadecimal).

Using [xrock's bit definitions](https://github.com/xboot/xrock/blob/main/rock.c), these advertise Direct LBA, First 4M Access, New Vendor Storage, New IDB, and Switch Storage. The unrestricted Read LBA bit, byte 0 bit 3, is absent. Partial reads can still succeed through U-Boot's limited handler.

The checked-out [rkdeveloptool capability printer](https://github.com/rockchip-linux/rkdeveloptool/blob/master/main.cpp) uses decimal masks `20`, `40`, and `80` for several labels; these are not hexadecimal bit masks. It also omits the New Vendor Storage label and associates later labels with the wrong positions. Trust the raw bytes and explicit bit definitions, not those printed labels. Correct positions in byte 0 are: New Vendor Storage `0x10`, Read Com Log `0x20`, Read IDB Config `0x40`, Read Secure Mode `0x80`.

## Historical binary identification

The stock dump includes the string `DDR Version V1.13 20220218`. The GitHub commits API for the historical path identifies the commit introducing v1.13:

```text
https://api.github.com/repos/rockchip-linux/rkbin/commits?path=bin/rk35/rk3568_ddr_1560MHz_v1.13.bin&per_page=10
```

Commit: `ddf03c1d80b33dac72a33c4f732fc5849b47ff99`. Its recursive tree lists several frequency variants. Downloading each and comparing the **entire** binary against the backup identified 1056 MHz as the exact match. A matching prefix or version string is insufficient: other frequency variants share long prefixes.

| Component | Length | SHA256 |
| --- | ---: | --- |
| `rk3568_ddr_1056MHz_v1.13.bin` | 59,392 | `6f165b37640eb876b5f41297bcce6451eb8a86fa56649633d4aca76047136a36` |
| `rk356x_usbplug_v1.14.bin` | 100,268 | `660886820e2a7b43002e6a5ca576b5cc363907b4d1537c3acd8993132ec17751` |

Pinned official downloads:

- [DDR initializer](https://raw.githubusercontent.com/rockchip-linux/rkbin/ddf03c1d80b33dac72a33c4f732fc5849b47ff99/bin/rk35/rk3568_ddr_1056MHz_v1.13.bin)
- [USB helper](https://raw.githubusercontent.com/rockchip-linux/rkbin/ddf03c1d80b33dac72a33c4f732fc5849b47ff99/bin/rk35/rk356x_usbplug_v1.14.bin)
- [Historical loader configuration](https://raw.githubusercontent.com/rockchip-linux/rkbin/ddf03c1d80b33dac72a33c4f732fc5849b47ff99/RKBOOT/RK3568MINIALL.ini)

The historical configuration pairs DDR v1.13 with USB helper v1.14 and sets `471_RC4_OFF=true` and `RC4_OFF=true`. Its default DDR frequency is 1560 MHz; the device's complete binary match establishes that this board uses the 1056 MHz variant. The USB helper was not found in the flash backup. It subsequently responded on the device, but retained the read restriction described above.

Reproduce the full-file match without sending any USB commands:

```sh
python3 scripts/match-stock-ddr.py backups/first-32MiB.img diagnostics/stock-loader-research/rk3568_ddr_1056MHz_v1.13.bin
```

The script verifies the known official hash and prints all full-file matches. Optional `--extract PATH` copies the first matching region into a new local file; it refuses to overwrite an existing file.

## RAM-only procedure — initialization observed, unrestricted reads unsuccessful

1. Preserve and verify the first-32-MiB backup.
2. Send `rkdeveloptool rd 3` once, then confirm that `rkdeveloptool ld` reports **Maskrom**. Do not infer the mode from a black screen or the reset command's success message.
3. Only after confirmation, use the stock-identical DDR initializer and historical USB helper:

   ```sh
   xrock maskrom diagnostics/stock-loader-research/rk3568_ddr_1056MHz_v1.13.bin diagnostics/stock-loader-research/rk356x_usbplug_v1.14.bin --rc4-off
   ```

4. Confirm enumeration, read a small region above sector `0x10000`, and verify that it contains plausible data rather than filler. Repeat reads and compare hashes before making larger backups.

The [official U-Boot reset implementation](https://github.com/rockchip-linux/u-boot/blob/next-dev/drivers/usb/gadget/f_rockusb.c) maps reset subcode 3 to a BootROM-download flag in a boot-mode register and resets; that path does not write flash. [rkdeveloptool's `DownloadBoot`](https://github.com/rockchip-linux/rkdeveloptool/blob/master/RKDevice.cpp) sends SRAM/DRAM entries with vendor requests `0x471` and `0x472`. [xrock documents](https://github.com/xboot/xrock#rk3568) the separate DDR/USB-helper method for RK3568.

These operations intend to change only the running RAM environment. A helper failure can require a physical power cycle, and macOS may require another accessory approval. Do not substitute `ul`, `upgrade`, `wl`, or an erase command: those have persistent effects and are unnecessary for the proposed backup procedure.

## Offline read-limit patch candidate

Two agents independently disassembled the exact historical USB helper. Its flash-read paths compare the current LBA against a global threshold and substitute `0xCC` when the LBA is greater than or equal to it. Both the normal and pipelined paths use that threshold.

Startup code copies the body from file offset `0x800` to RAM `0x03001000`, so body instruction addresses are `file_offset + 0x03000800`. Applying this relocation is essential when resolving AArch64 `ADRP` instructions. With the correct base, the initializer and both readers reference the same threshold at RAM `0x0334d5c4`.

Relevant file offsets and original instructions:

```text
0x94b0  adrp x8, <threshold page>
0x94b8  e9031032  mov w9, #0x10000
0x94cc  09c505b9  str w9, [x8, #0x5c4]

0x9d24  ldr w9, [x9, #0x5c4]
0x9d28  cmp w8, w9
0x9d2c  b.hs <0xCC-fill path at file 0x9d8c>

0x9e20  ldr w9, [x9, #0x5c4]
0x9e24  cmp w8, w9
0x9e28  b.hs <0xCC-fill path at file 0x9e40>
```

The candidate changes only the initializer at file offset `0x94b8`:

```text
before: e9031032  mov w9, #0x10000
after:  09008012  mov w9, #-1
```

The stored 32-bit threshold becomes `0xffffffff`. This exceeds every sector on this device. The original helper already assigns this value to the same global in another storage-type path at file offsets `0x460c`/`0x4618`. Register `w9` is consumed by the threshold store and overwritten before later use. The two read branches and the actual storage-read code remain intact.

Create the candidate entirely offline:

```sh
python3 scripts/patch-usb-reader.py diagnostics/stock-loader-research/rk356x_usbplug_v1.14.bin diagnostics/stock-loader-research/rk356x_usbplug_v1.14-read-unlimited.bin
python3 scripts/load-usb-reader.py --patched
```

The first script checks the complete original hash and reviewed instructions, refuses existing outputs, and writes a hash manifest. The second command checks files only. Actual uploading still requires a separately chosen `--load` invocation and confirmed MaskROM. The patched binary SHA256 is `38f7a4e06c06b75d476b059ea590f07033f3606ff7848189655727f00b6e84c2` (100,268 bytes).

The patched helper was subsequently uploaded to RAM successfully on this unit. Repeated 4-KiB reads at sectors 65,536 and 182,272 returned identical non-filler data; the recovery sample starts `ANDROID!`, and a low-address sample matches the original backup. Complete flash capture is underway. No secure-boot signature was regenerated. The upload transport CRC16 is generated afresh by xrock's `rock_maskrom_upload_memory`; that CRC is distinct from secure-boot authentication. The patch script makes no speculative changes to the binary's header or trailer. This helper is for RAM use only and must not be flashed as firmware.

## Streaming a backup after unrestricted reads are verified

`scripts/backup-flash.py` invokes only `rkdeveloptool rl`, starting at sector zero, and pipes its output through a temporary POSIX FIFO into gzip. It does not need space for an additional uncompressed image. Supply the actual flash sector count reported by the device; the following is a command template, not a recorded device run:

```sh
python3 scripts/backup-flash.py --tool diagnostics/tools/rkdeveloptool-src/rkdeveloptool --sectors <actual-sector-count> --output backups/full-flash.img.gz --timeout 1800
```

The destination directory must already exist. Existing destinations, partial files, manifests, and logs are refused. Failed attempts retain `.partial` and `.log` files for inspection; use a new destination for a retry. Compression cannot guarantee that the available disk space is sufficient: a full-disk error aborts the reader.

Before publishing the final filename, the wrapper requires the exact byte count, a successful child exit, a `Read LBA to file (100%)` message, no failure message, and a successful gzip readback with a matching raw SHA256. It conservatively rejects any consecutive run of at least 64 KiB of `0xCC`, including runs spanning read chunks. Such a run could theoretically be legitimate data, but silently accepting the known loader filler would be worse. Other forms of incorrect data may pass these checks; compare independent reads where practical.

The `.img.gz.json` manifest contains raw and compressed lengths and SHA256 hashes. The timeout covers streaming and validation. No resetting, RAM loading, flashing, or erasing is done by this wrapper.

Run the USB-free synthetic validation:

```sh
python3 scripts/test-backup-flash.py
```

Validated cases: deterministic successful backup and hashes, unaligned `0xCC` filler, truncation, a reported failure despite process exit zero, timeout, and refusal to overwrite an existing output. This validates the wrapper's mechanics, not live-device compatibility.

## Separate stock-Fastboot reset candidate

The offline candidate `rk356x_usbplug_v1.14-read-unlimited-fastboot.bin` retains the read-limit patch and changes one additional instruction. Its SHA256 is `f6f1cf8eb5ea6f0af76e41bb15f8d00a72ae416a1cf43d1a9fea2234cb5c1c31`.

```text
file 0x98e4 before: 73060011  add w19, w19, #1
file 0x98e4 after:  73260011  add w19, w19, #9
```

Independent review of the entire command-loop function (`0x9868..0x9e54`) found register 19 only saved in the prologue, initialized to `0x5242c300`, incremented by this instruction, and consumed by the reset-subcode-6 path at `0x9a88`. Other read/write command paths do not use it. The reset flag changes from `0x5242c301` to `0x5242c309`, requesting stock Fastboot instead of Loader. The flag writer at `0x5c08` only compares and stores the value at MMIO `0xfdc20200`; the subsequent reset routine is unchanged. The subcode-3 MaskROM path independently writes `0xef08a53c` and remains intact.

Build and verify without USB access:

```sh
python3 scripts/patch-fastboot-reader.py diagnostics/stock-loader-research/rk356x_usbplug_v1.14-read-unlimited.bin diagnostics/stock-loader-research/rk356x_usbplug_v1.14-read-unlimited-fastboot.bin
python3 scripts/load-usb-reader.py --fastboot-reset
```

The creation script validates the input hash and reviewed instructions and refuses existing outputs. The selection flag checks the exact candidate hash. It does not issue a reset, and no upload occurs without `--load`. After a separately authorized RAM upload, a later `rd 6` would request Fastboot. This section records offline analysis, not observed Fastboot entry. No firmware image is changed by the reviewed reset path; normal actions taken by the stock bootloader after reset are outside this patch's control. See [RAM boot research](ram-boot-research.md) for the stock boot-mode evidence.
