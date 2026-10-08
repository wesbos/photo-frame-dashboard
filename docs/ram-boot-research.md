# RAM-only boot routes

Research date: 2026-09-14. This is an offline source and binary review, not a record of a successful diagnostic boot. No USB commands were issued for this research.

Subsequent parent-controlled tests established responding fastboot at `18d1:d00d` after macOS accessory approval. The helper variant and host CLI patch described below were applied successfully. The AP6256 Android-format diagnostic recovery transferred and received `Booting OKAY`, but recovery ADB did not appear; a later fastboot query still responded. Normal Android and ADB were restored with a normal reboot. No diagnostic recovery boot has been established. See the chronological research log and the legacy-image alternative below.

## Preferred candidate: ask stock U-Boot to enter fastboot

The smallest identified change is a RAM-only variant of the already identified Rockchip USB helper that maps its reset subcode 6 to the fastboot reboot flag. This preserves the installed bootloader and its normal DRAM, trusted-firmware and board initialization.

The exact original `rk356x_usbplug_v1.14.bin` has SHA-256 `660886820e2a7b43002e6a5ca576b5cc363907b4d1537c3acd8993132ec17751`. Offline AArch64 disassembly shows:

| File offset | Instruction / role |
| --- | --- |
| `0x9894` | `mov w19, #0xc300` |
| `0x9898` | `movk w19, #0x5242, lsl #16` |
| `0x98e4` | `add w19, w19, #1`, making `0x5242c301` |
| `0x99d8` / `0x99dc` | Compare reset subcode with 6 and branch to `0x9a88` |
| `0x9a88` / `0x9a8c` | Move `w19` into `w0`, call routine at file `0x5c08` |
| `0x5c08` through `0x5c20` | Write `w0` to MMIO `0xfdc20200` if changed |
| `0x9a94` | Call hardware-reset routine at file `0x9098` |

Changing file `0x98e4` from bytes `73 06 00 11` to `73 26 00 11` changes only the immediate from 1 to 9. That produces `0x5242c309`, Rockchip's fastboot flag. In the reviewed main loop, `w19` is initialized once and only consumed by this reset-6 path. Subcode 3's separate MaskROM flag path remains unchanged. This change was independently reviewed, created with a hash-checked patch tool, and subsequently uploaded to RAM by the parent-controlled test, which reached responding fastboot. A recovery variant would use immediate 3 instead of 9, but that variant was not used here.

The relocated helper body uses `runtime_address = file_offset + 0x03000800`; the table intentionally uses file offsets. Do not confuse these two address spaces when reviewing branches or constructing a patch.

The tested sequence was: validate the full backup, return to genuine MaskROM, upload the reviewed helper variant using the matching DDR initializer, confirm a responding helper, and issue reset subcode 6. Normal Android ADB now provides a simpler `adb reboot bootloader` route; there is no need to repeat the helper transition for every subsequent test.

The pinned rkdeveloptool host CLI rejects reset subcodes above 5 before sending them. This was observed when the first `rd 6` attempt printed `Subcode is invalid`. A separately built host binary, `rkdeveloptool-rd6`, changes only that CLI limit to 6; the protocol reset routine already transports an arbitrary byte. [The minimal source patch](../scripts/rkdeveloptool-rd6.patch) records the change. This host patch alone does not change the stock reset meaning: it must be paired with the reviewed RAM helper to request fastboot. The original host binary is retained.

## Legacy multi-image diagnostic candidate

The failed Android-format RAM boot has a plausible memory-layout explanation, not yet confirmed by a UART error log. Installed U-Boot disassembly fixes the fastboot download address at `0x00c00800`. Rockchip's Android path reserves the full downloaded image and then allocates the kernel at its normal low-memory address. With this 27,865,104-byte kernel, those ranges overlap. The pinned sysmem implementation rejects overlapping image reservations. Its FIT RAM path also reserves the input image and may encounter the same issue. The direct RAM path does not itself contain an AVB/unlock gate; fastboot's secure/locked status alone does not establish the cause of this failure.

The installed binary includes legacy multi-image kernel, ramdisk, and FDT support. A legacy image bypasses the special Android/FIT board handlers and specifies a separate kernel load address. [build-legacy-recovery.py](../scripts/build-legacy-recovery.py) constructs a guarded candidate from the verified AP6256 recovery and a private capture of the running device tree:

```sh
python3 scripts/build-legacy-recovery.py \
  --candidate backups/diagnostic-recovery-ap6256/recovery.img \
  --live-tree diagnostics/live-adb/running-tree \
  --output-dir backups/diagnostic-recovery-legacy
```

The builder performs no USB operations. It creates an ARM64/Linux legacy multi-image containing four components: exact stock kernel, exact diagnostic gzip ramdisk, the running DTB with stale initrd bounds removed, and a 16 KiB zero workspace. The fourth component is ignored by the Linux component-selection code, supplies space for in-place FDT growth, and makes the DTB naturally eight-byte aligned without changing the ramdisk. Legacy header/data CRC32 checks, component contents, DTB total size, and the complete address layout were verified with a separate parser.

| Range | Start | Exclusive end |
| --- | --- | --- |
| Complete download | `0x00c00800` | `0x03a2e8a0` |
| Kernel runtime allocation | `0x06080000` | `0x07bf6000` |
| Ramdisk, in place | `0x02693864` | `0x03a0ad68` |
| DTB including U-Boot growth allowance | `0x03a0ad68` | `0x03a2d89d` |

The kernel range uses its ARM64 header `image_size`, not just its smaller file size. Load and entry are both `0x06080000`, respecting the kernel's `0x80000` text offset and two-MiB base alignment. These ranges fit the captured usable RAM banks and avoid its explicit reserved-memory nodes. The download and kernel destination do not overlap.

The candidate is 48,423,072 bytes, below the measured 64 MiB fastboot limit; SHA-256 is `d6aac2f324840b0ef5ef66bcd110b9dc5e86309d50d0b94890b3d0ad5b8b9f96`. It is **built and checked offline, not yet shown to boot**. Its manifest retains two limitations: the current U-Boot environment is not directly readable through ordinary fastboot, and filesystem-exported OF properties do not expose runtime-added FDT reserve-header entries. Both original stock DTB reserve headers were empty. Source review indicates the board defaults to preserving ramdisk/FDT in place; an unexpected existing relocation environment remains a runtime uncertainty.

The captured tree and resulting image contain private device identifiers and remain ignored. Public notes do not reproduce those properties.

The first host CLI attempt with `fastboot boot recovery.uimg` did **not** send this legacy image directly. The host printed `creating boot image` and wrapped the 48,423,072-byte input into a 48,427,008-byte Android boot image before uploading it. Its `Booting OKAY` therefore does not test the legacy parser or this candidate’s intended memory layout. Normal Android ADB was restored afterward. [raw-fastboot-boot.py](../scripts/raw-fastboot-boot.py) implements a separate hash-guarded raw transfer: exact image bytes, `getvar:max-download-size`, `download`, and `boot`. Its default is a dry run with no USB access. It provides no flash, erase, unlock, or arbitrary-command interface; a boot acknowledgment still requires separate evidence that Linux actually started.

## Reset-number interpretation

[Rockchip's reset handler](https://github.com/rockchip-linux/u-boot/blob/1c535d65b8509f388d09e49fb6961f49fda35a1d/drivers/usb/gadget/f_rockusb.c) maps protocol subcode 3 to BootROM download, 6 to Loader, and other values to normal. Therefore `rkdeveloptool rd 9` is not equivalent to booting fastboot. The host tool transports the subcode; it does not translate Android reboot-mode names.

[Rockchip's boot-mode header](https://github.com/rockchip-linux/u-boot/blob/1c535d65b8509f388d09e49fb6961f49fda35a1d/arch/arm/include/asm/arch-rockchip/boot_mode.h) defines distinct 32-bit register values:

| Register value | Meaning |
| --- | --- |
| `0x5242c300` | Normal |
| `0x5242c301` | Rockusb Loader |
| `0x5242c303` | Recovery |
| `0x5242c309` | Bootloader fastboot |

[Boot-mode handling](https://github.com/rockchip-linux/u-boot/blob/1c535d65b8509f388d09e49fb6961f49fda35a1d/arch/arm/mach-rockchip/boot_mode.c) recognizes the fastboot flag with higher priority than a recovery message in `misc`, clears the flag, and calls `fastboot usb 0`. It uses the RAM environment rather than saving it. The installed bootloader's relevant code must still match this behavior; its command strings alone are not complete proof.

The calendar's Android overlay calls value `0x5242c303` both `fastboot` and `recovery`, while `bootloader` is `0x5242c309`. Those kernel reboot labels must not be substituted for Rockusb reset subcodes. For a bootloader fastboot route, `0x5242c309` is the specific target supported by the reviewed U-Boot source.

## If fastboot appears: temporary boot support

[Rockchip's fastboot implementation](https://github.com/rockchip-linux/u-boot/blob/1c535d65b8509f388d09e49fb6961f49fda35a1d/drivers/usb/gadget/f_fastboot.c) registers the `boot` command. `cb_boot` replies `OKAY`, then `do_bootm_on_complete` executes `bootm` at `CONFIG_FASTBOOT_BUF_ADDR`; it resets if boot returns. That callback contains no explicit unlock check or flash operation. This establishes an upstream RAM boot path, not certainty that the installed build accepts every image format or bypasses downstream image validation.

The same source accepts image download into a configured RAM buffer. A complete stock boot or recovery image can provide a baseline for a separately constructed diagnostic image. Confirm image header support, total size, and `max-download-size` before attempting `fastboot boot`. An image booted from RAM can itself mount and write storage; inspect its init/recovery behavior before calling the overall operation read-only. In particular, avoid factory-reset commands or recovery update arguments carried in a ramdisk or `misc`.

Both copies of the installed U-Boot contain `Booting kernel..`, `enter fastboot!`, `boot mode: bootloader`, `max-download-size`, and the upstream preboot command template. This strengthens the source-to-binary correspondence, but string matching is not validation of every control-flow or image-validation path.

The upstream USB fixup uses VID:PID `18d1:4d00` for fastboot. Enumeration and `fastboot devices`/read-only `getvar` responses would be the first success criteria. A new macOS accessory approval may be needed. Do not issue `flashing unlock`: it is unnecessary to test whether the existing implementation supports RAM boot and may erase user data.

## Less attractive alternatives

| Route | Assessment |
| --- | --- |
| `xrock exec` after loading code into RAM | Host API exists, but command availability depends on the running helper. Rockchip's reviewed U-Boot Rockusb source explicitly leaves SDRAM write and execute opcodes unsupported. The historical USB helper is separate code and must be assessed independently. |
| Direct jump to the stock U-Boot payload in RAM | Requires preserving its expected execution level, relocation, DRAM state and ATF/OP-TEE handoff. The stock FIT contains multiple stages, so jumping to an extracted U-Boot component is not equivalent to normal boot. No validated procedure identified. |
| Direct Linux entry from MaskROM | Requires correct AArch64 handoff state, DTB, initramfs placement and firmware services. More new assumptions than resetting through the stock chain. |
| Write a bootloader-control message into `misc` | Persistent storage mutation; not needed for the preferred volatile-register route. |
| Flash a modified boot/recovery/U-Boot partition | Persistent firmware mutation; outside the RAM-only options evaluated here. |

The local xrock checkout's `rock_exec` sends opcode `0x19`, subcode `0xaa`, entry address and DTB address. Its maskrom execution helpers are separate control-transfer payloads; a `bcdUSB=0x0200` label on an already running USB-MSC helper does not prove that BootROM control transfers remain available. Sources: [xrock implementation](https://github.com/xboot/xrock/blob/50effcef229a7e8ff85fde916e635cdd58fe8c09/rock.c), [Rockusb opcode dispatch](https://github.com/rockchip-linux/u-boot/blob/1c535d65b8509f388d09e49fb6961f49fda35a1d/drivers/usb/gadget/f_rockusb.c).

Primary-source snapshots are saved under ignored `diagnostics/ram-boot-research/`. Rockchip source revision inspected: `1c535d65b8509f388d09e49fb6961f49fda35a1d`; this is a comparison reference, not a claim that the calendar was built from that exact revision.


## Installed-binary verification after the raw legacy attempt

A subsequent exact raw upload received both download and boot acknowledgments, but recovery ADB did not appear. The USB node remained visible with its fastboot identity; a bounded fastboot query timed out. This differs from the earlier Android-format attempts, whose subsequent fastboot queries responded. The remaining node may be stale, and the raw candidate may have advanced into a bootloader or kernel hang. The execution stage is unknown; neither a responsive fastboot loop nor a successful Linux boot is established. No further image variant was justified by that observation alone.

A bounded disassembly of the backed-up installed U-Boot confirms more than shared diagnostic strings. Addresses below use its `0x00a00000` link base, not its later runtime relocation:

- The boot command handler at `0x00a8dfa4` installs completion callback `0x00a8d454` before transmitting its response. The callback constructs download address `0x00c00800`, calls `do_bootm` at `0x00a8d4ac`, and calls reset at `0x00a8d4c0` if boot returns.
- `do_bootm` at `0x00a080b4` invokes the board dispatcher at `0x00a04344`. That dispatcher handles Android and FIT specially and returns zero for legacy images, allowing the generic boot state machine to continue.
- The format detector at `0x00a27624` recognizes the legacy image magic and returns format 1. The state machine at `0x00a1a5a4` has a reachable legacy parser, performs header/data integrity checks, accepts ARM64 architecture value `0x16` at `0x00a1a740`, and selects multi-image type 4 at `0x00a1a79c`. It extracts the first component through `0x00a270bc`.

Thus disabled legacy/ARM64/multi-image support is not supported as an explanation. This review did not identify the actual runtime rejection or prove that the completion callback executed during the observed test. UART output or equivalent bootloader diagnostics would distinguish an early boot failure from a callback/USB-completion issue. No new candidate was built in response.

### Recovery from the raw test

The raw upload log confirms an exact DATA02e2e0a0 transfer and boot acknowledgement. USB descriptors remained visible, but a subsequent bounded fastboot query and a raw libusb query both timed out. Descriptor presence did not establish a responding bootloader. After a full disconnect of both wall power and USB, normal Android and ADB returned. The pstore directory was empty; no saved crash trace locates the failure. Further image changes need a serial boot log or comparable evidence.
