# PF1007L A33: how boot access was obtained

Companion to the [Allwinner setup guide](allwinner-a33-pf1007l.md). These are
engineering notes from **one** PF1007L / EFERCRO `PF1007L_MB_V1.0`, not a universal
flash procedure. The tested firmware is listed in the companion guide.

## What stock firmware exposed

The frame booted AiMOR normally and exposed USB mass storage (`1f3a:1000`), but
not ADB. ADB over Wi-Fi port 5555 was also unavailable. Reset briefly exposed
`1f3a:efe8` without yielding a working version response. The official
`fel-sdboot.sunxi` stub on an SD card gave persistent FEL and a successful A33
version query. No serial adapter was used.

FEL is the [Allwinner Boot ROM USB recovery protocol](https://linux-sunxi.org/FEL),
not the Rockchip loader protocol. It can upload/execute RAM code, but does not
itself give an Android shell, root privileges, or a standard eMMC block-reader.

## Storage access required a custom helper

The successful reader and writer were small **SPL-only** helpers based on
[U-Boot v2025.10](https://github.com/u-boot/u-boot/tree/e50b1e8715011def8aff1588081a2649a2c6cd47).
They initialized A33 DRAM and MMC2, performed a bounded operation, wrote a result
structure in DRAM, then returned to FEL for the host to retrieve it. A normal
board U-Boot image was not a substitute: attempts to expose storage through a
full RAM-booted U-Boot did not enumerate a working USB disk on this unit.

The working helper configuration used A33 DRAM at 456 MHz, ZQ 15291 and MMC2
PC pins with an 8-bit eMMC bus. Initial storage reads were checked at 400 kHz,
then the same first 4 KiB was verified at 12 MHz before the bounded reading
session. These are **observations about this helper on this board**, not settings
to guess for a different PCB or memory population.

The helpers and host journals contained device-specific eMMC CID guards and
private paths. They are **not distributed in this PR**, nor are vendor images
or a ready-to-flash boot image. An owner who only has stock mass-storage access
cannot complete the root stage using this repository as it stands. They need
a reviewed reader/writer for their actual board, or another independently
verified root/ADB route. Do not remove a CID, capacity, or partition guard to
make a mismatching loader run.

If implementing a reader, its job is to capture partition metadata and actual
eMMC bytes, not just SRAM. Reject errors/filler/short reads, record the exact
capacity and hardware identity privately, and independently reread the bytes
before proposing any flash operation. Parse the partition chain; the first
logical partition on this frame was an environment partition, **not** Android
boot. Do not label the first plausible-looking capture a boot backup.

## The boot-ramdisk change

The captured boot image already contained `/sbin/adbd`, `ro.secure=0` and
`ro.debuggable=1`. Root configuration in an offline image is not proof of a
working root shell. The obstacle on this build was its USB init action:
`init.sun8i.usb.rc`'s `sys.usb.config=mass_storage` action enabled only mass storage
and did not start `adbd`.

The tested patch changed that action to the following, leaving other actions
and the rest of the ramdisk intact:

```rc
on property:sys.usb.config=mass_storage
    write /sys/class/android_usb/android0/enable 0
    write /sys/class/android_usb/android0/idVendor 1f3a
    write /sys/class/android_usb/android0/idProduct 1002
    write /sys/class/android_usb/android0/functions mass_storage,adb
    write /sys/class/android_usb/android0/enable 1
    start adbd
    setprop sys.usb.state ${sys.usb.config}
```

The framework state deliberately still reports the requested `mass_storage`;
the USB descriptor exposes both interfaces. Changing only an Android property
was not an available route from the stock UI, and the existing USB action would
have overwritten the functions on boot.

The image was a legacy `ANDROID!` boot image with a 2048-byte page size and a
gzip-compressed newc CPIO ramdisk. The offline rebuild:

1. Validated the original image, ramdisk gzip and legacy SHA-1 image ID.
2. Changed only the identified init action, preserving every other CPIO record.
3. Recompressed the ramdisk to fit the original padded slot; did not move the
   kernel or other image components.
4. Updated the ramdisk size and legacy boot image ID in the header.
5. Compared original/candidate bytes and refused any differences outside the
   backed-up header and original ramdisk slot.

These instructions explain the change; they do not authorize applying it to an
image with different init actions, page sizes, signatures or AVB requirements.
Android 10+ debug-ramdisk recipes and Rockchip partition numbers are unrelated.

## What the guarded write verified

The tested unit's Android boot image was 15,886,336 bytes. Its complete independent
reread matched the first capture. Recovery was captured too, but did not have a
full independent reread. The owner explicitly approved proceeding with limited
backup coverage of every modified sector rather than a complete device backup.

For reference **only**, the identified layout and write bounds were:

| Region on the tested unit | Absolute 512-byte sectors, end exclusive |
| --- | --- |
| Boot image start | 172032 |
| Recovery image start | 2400256 |
| Modified boot header | `[172032, 172034)` |
| Modified padded boot ramdisk | `[192004, 203060)` |

**Do not turn this table into a `dd` command.** The bounds came from this image's
partition metadata and header. A matching model name or Android version does
not prove matching sectors. Total bounded write coverage was 5,661,696 bytes;
this was not a complete boot-partition rewrite.

The writer checked the exact private eMMC identity/capacity and restricted writes
at both request and controller layers. It blocked erase/protection operations and
preserved persistent eMMC boot-partition configuration. The host then:

1. Read the header first and all original bytes in the proposed write ranges.
   Every byte had to match the independently verified stock backup before the
   first flash write.
2. Uploaded each new chunk to DRAM and read it back before issuing a flash request.
3. Required original-flash CRC and new-input CRC matches inside the helper.
4. Wrote ramdisk chunks **first**, header **last**, at most 128 sectors per request.
5. Compared each flash readback byte-for-byte, then performed a separate complete
   reread of all modified ranges. All 88 preflight reads, 88 writes and 88 final
   reads passed on the successful run.

The host stopped at the first failure, retained a journal, and did not retry a
write automatically. Undo was restricted to the same original-byte ranges with
the apply journal and verified original image. An `OKAY` or successful USB
transfer alone was never accepted as a verified flash write.

## The SRAM-layout failure worth checking for

An earlier writer hung during its first **read-only** preflight, before any flash
write request. Offline review found that SPL code/data overlapped the early
global-data/stack reservation. A binary fitting under the advertised SRAM limit
was not enough.

With the initial SPL stack at `0x8000`, early malloc size `0x2000` and 224 bytes
of global data, the global-data area began at `0x5f20` while the linked image ended
at `0x5f84`. Startup zeroing overlapped the image, including the loader table.
The corrected build used early malloc `0x1000`; global data began at `0x6f20`,
leaving 3,996 bytes between the image end and initial stack reservation. The same
storage guards remained in place. This revision completed the successful run.

The overlap was a plausible explanation for the earlier hang; there was no UART
trace proving the precise runtime cause. Validate **code, data, FEL stash, request
tables, stack, global data and allocator reservations together**, and inspect
the linked output, not just binary size. Keep source/build hashes, review bounds
offline, and obtain fresh approval for a revised RAM payload before loading it.

## Successful boot and remaining limits

After the independently verified patch, both power sources were unplugged, the
FEL card removed, and Android cold-booted normally. USB exposed `1f3a:1002` with
mass storage and ADB. `adb shell id` returned `uid=0(root)` without `su` or an
`adb root` restart. Boot completion, firmware identity and eMMC identity were
checked before installing apps.

This worked because of this firmware's existing insecure/debuggable configuration.
It did not unlock a signed bootloader, supply a general Android root exploit,
replace Android, or prove compatibility with other AiMOR frames. Keep the FEL
card and verified original images: a bad boot patch still needs a functioning,
board-specific restore path, not a factory-reset menu.
