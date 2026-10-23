# Pastigio ZC002 (MS33-V2.0, Allwinner A33, Android 6.0.1)

Record of one owner-tested unit, rooted on 2026-10-12. USB/FEL, dashboard,
brightness control and network ADB were verified on this unit.

**Result:** authorized root ADB over USB and the LAN, a replacement launcher and
browser, and working Android Back/Home/Recents navigation. Android remains 6.0.1.
This unit was rooted using a custom, FEL-returning SPL storage helper and a
per-unit boot ramdisk patch. A second owner's later report found a smaller
change on the same firmware: authorize the host key in userdata and use the
shipped `su 0`, preserving the stock boot image and SELinux policy. Start with
[that finding](#prefer-stock-su-after-host-key-authorization) before considering
the historical boot patch recorded here. The included boot-candidate helper is
offline; the public SPL and FEL host command provide bounded storage reads only.
They do not provide a complete recovery tool or a boot-write command.

Host scope: Windows was used for the initial USB/FEL/root workflow and offline
Python tests; a Linux container built the pinned SPL and ran offline
filesystem validation; macOS was used for post-root LAN, control and reboot
checks. These are the host contexts tested, not a claim that the workflows are
interchangeable across operating systems.

Related: [ZC002 issue #38](https://github.com/wesbos/photo-frame-dashboard/issues/38).
The SOMY / `DPF ZC002` owner in [PR #73](https://github.com/wesbos/photo-frame-dashboard/pull/73)
reports the same `ZC002_20260313` build and the same 14,911,488-byte stock boot
core hash. Their eMMC capacity and userdata layout differ from this unit;
matching firmware does not establish interchangeable disk images, offsets or
board wiring.
This is different hardware from the Rockchip [Pastigio FRAME156](pastigio-frame156.md).

## Identity

| Item | Observed value |
| --- | --- |
| Brand / model | Pastigio 10.1-inch Frameo frame; `ro.product.model=ZC002` |
| Purchased listing | [Amazon B0D41ZMYB2](https://www.amazon.com/dp/B0D41ZMYB2); listings may change hardware |
| PCB | `MS33-V2.0`, silkscreen date `20240831` |
| SoC | Allwinner A33, package marked `R6383BA`; FEL reports `soc=00001667(A33)` |
| Firmware / build | `ZC002_20260313` |
| Build fingerprint | `Allwinner/astar_xr819/astar-xr819:6.0.1/MOB30R/20260313:eng/test-keys` |
| Android / kernel | Android 6.0.1, API 23; Linux 3.4.39; 32-bit ARM userspace |
| Board / hardware properties | `exdroid` / `sun8i` |
| Frameo | Current beta `v1.32.12_-_OTA_test` (78071); package inspection also reports stock `v1.29.14` |
| Display / memory | 1280x800 touchscreen; approximately 1 GB RAM |
| Storage | eMMC, 60,620,800 addressable 512-byte sectors (31,037,849,600 bytes) |
| Ports used | USB-C device/data port plus a separate power adapter |
| USB modes | FEL `1f3a:efe8`; a modified borrowed U-Boot fastboot gadget enumerated as `1f3a:1010` |
| Vendor home app | `net.frameo.frame` |

Unique identifiers, host addresses, account information, ADB key material and
vendor images are omitted. Stock firmware hashes below identify the tested
public build; the patched candidate hash is retained privately because the
candidate includes this owner's trusted public keys.

## Prefer stock `su` after host-key authorization

[mikestecker's report](https://github.com/wesbos/photo-frame-dashboard/pull/73)
on a SOMY ZC002 independently verified that adding the host's ADB **public** key
to `/data/misc/adb/adb_keys` authorizes the stock ADB daemon. A normal shell then
reports UID 2000, while `adb shell su 0 id` reports UID 0. No `adbd` binary,
boot-image or SELinux-policy change was needed on that unit. Its SystemUI package
was present but disabled; the key method did not require enabling it.

The key file's ownership, mode and SELinux label were matched to that unit's
existing userdata metadata. This finding has not been re-tested against stock
boot on the first Pastigio unit recorded here; a [third Pastigio unit](#third-pastigio-unit)
confirmed it with the guarded writer below. The boot patch below is a historical
tested route, not evidence that those broader changes are required on this build.

PR #73 also verified a full backup through the repository's existing read-only
[Route U](allwinner-a33-mainline-uboot.md). That route remains untested on the first
Pastigio unit; the failed borrowed U-Boot attempts below used different binaries.
A [second Pastigio unit](#second-pastigio-unit) completed Route U, and found that
`su 0` from ADB can't remount `/system`.

The initially submitted key writer exposed the whole eMMC as a writable USB disk.
The maintainer [requested a replacement](https://github.com/wesbos/photo-frame-dashboard/pull/73#issuecomment-6147848346)
that keeps USB mass storage read-only and performs only planned writes through a
generated U-Boot script: check payload CRCs, compare current storage against the
owner's original bytes, write, then read back and compare. The existing read-only
U-Boot build protects its USB disk interface; it still permits controlled internal
`mmc write` commands. The public SPL reader in this report has no such write path.

Re-derive any userdata patch from your own verified backup and exact partition
table. The other unit's nine changed ranges and 7,680-byte total describe that
owner's filesystem edit; they are not reusable offsets or payloads.
[`scripts/a33-uboot/data-patch-prepare.py`](../scripts/a33-uboot/data-patch-prepare.py)
builds the replacement writer the maintainer asked for: see
[Guarded userdata-key writer](#guarded-userdata-key-writer) below.

### SOMY ZC002 unit identity

From the unit reported in PR #73, for comparison against another ZC002:

| Item | Observed value |
| --- | --- |
| About screen | Hardware brand and model number `DPF ZC002`; `ro.product.brand=SOMY` |
| eMMC | 31,268,536,320 bytes total addressable (this unit's `/data` declares a larger size than fits; same "listed past the end of the eMMC" pattern as the PF1007L) |
| Partition starts (sectors) | bootloader 73728, env 139264, **boot 172032**, system 204800 (1 GiB), misc 2301952, recovery 2334720, cache 2400256 (1,572,864 sectors — larger than this Pastigio unit's, so later offsets diverge from here on), `/data` 4268032 |
| Boot image | Legacy `ANDROID!` header, page 2048, kernel 10,165,848 B, ramdisk 4,741,158 B, `vmalloc=384M` |
| `default.prop` | `ro.secure=1`, `ro.debuggable=0`, `persist.sys.usb.config=none` — `adbd` still starts unconditionally from `init.rc`, unrelated to `ro.debuggable` |
| `/misc/adb` | Present, owner `1000:2000` mode `0750`, SELinux context `u:object_r:adb_keys_file:s0`; no `adb_keys` file before the patch |

## What was tried before the successful route

1. Normal USB ADB remained `unauthorized`. Frameo's beta/ADB Access toggles,
   cable reconnects and normal reboots did not produce an authorization dialog.
   Stock network ADB did not provide an accessible shell.
2. The red Frameo Recovery menu appeared with or without a successful UPDATE
   bridge. Its external-storage update option was not used; we did not create
   or test a custom signed OTA package. **That menu is not evidence of FEL.**
3. The rear cover was carefully removed to reach the UPDATE pads, which were
   bridged using a paperclip. Getting contact and repeating power cycles was
   fiddly; the paperclip itself was not evidence that FEL had been entered.
   [DivineHawk's MS33/Pastigio guide](https://divinehawk.github.io/2026/07/08/pastigio-frame-adb-fel-mode.html)
   supplied the UPDATE-pad starting point. Both USB and the separate adapter
   could keep this unit powered. On Windows, Zadig installed WinUSB for the FEL device, not an ADB driver.
   Disconnecting both, placing the UPDATE bridge
   before applying power, then reconnecting USB and the adapter produced FEL.
   Verify `1f3a:efe8` and `sunxi-fel version`; a dark or backlit screen alone
   does not establish the boot mode. No serial adapter was used.
4. [DivineHawk's downloadable U-Boot](https://divinehawk.github.io/2026/07/10/u-boot-adb-setup.html)
   did not expose this unit's eMMC through its default `ums` path. A locally
   modified fastboot loop brought up USB, but storage probes did not open the
   eMMC. Several full U-Boot variants stalled before usable USB access returned.
   The guide's userdata-key insertion method was therefore not completed.

These are observations from the attempted binaries. They do **not** show that
the repository's PF1007L Route U, its later U-Boot fixes, or Route S fail on this
ZC002: those complete routes were not tested here.

## Successful storage access: SPL returning to FEL

Instead of starting full U-Boot and waiting for a new USB gadget, we built a small
SPL helper from mainline U-Boot v2026.07, using the Q8 A33 configuration as a base.
It initializes DRAM and the eMMC, performs one bounded operation, leaves results
in RAM, and returns through U-Boot's existing FEL return path. The host then reads
the result and data with `sunxi-fel`. Successful operations retained FEL, allowing
subsequent reads and the guarded writes without another physical bridge cycle.

The working configuration used no AXP PMIC, DRAM at 456 MHz with ZQ 15291,
CPU at 408 MHz, and the extra MMC slot mapped to controller MMC2. Controller MMC2
was U-Boot MMC device **1** in this build; controller numbers and enumerated device
numbers must not be treated as interchangeable.

The working helper pulsed MMC2's AHB reset bit 10 at `0x01c202c0`, then wrote `1`
to the eMMC hardware-reset control at `0x01c11078` before `mmc_init`. It disabled
high-speed, DDR, 4-bit and 8-bit capability negotiation, initialized at 400 kHz,
and used a 1-bit bus at 12 MHz for transfers. This combination produced repeatable
storage reads. We did not isolate every setting to prove which one was necessary;
it is a record of the tested combination, not a universal MMC2 fix.

The reader reported exact block counts, capacity and errors; the host checked the
returned bytes and confirmed FEL response after each successful transaction.
Read buffers began as `0xCC` filler rather than silently accepting unread memory.
The original private writer required `CONFIG_SPL_MMC_WRITE=y`; without it, a write
attempt returned zero blocks and was rejected. The public reader has had write
and CRC-preflight operations removed and disables that option. It rejects any
nonzero operation before MMC initialization. Its controller reset and pin
configuration do not write storage sectors.

## Backup and boot structure

| Item | Captured / verified value |
| --- | --- |
| Boot partition | Start LBA 172032; 32768 sectors; 16,777,216 bytes |
| Stock boot core SHA-256 (14,911,488 bytes) | `379da4ba0b8c5f0b73401ee526dd8d8184eb18a709222de90a555dbeabe8f0b1` |
| Stock boot partition SHA-256 (16 MiB) | `e54245aa3620d314283c7592a59de6a87268c35ab9ac59dd8ac23ff0b54ab366` |
| Independent original boot read | Same byte count and SHA-256 as the first read |
| Android header | `ANDROID!`, 2048-byte page size |
| Kernel | 10,165,848 bytes; unchanged by the root patch |
| Original compressed ramdisk | 4,741,158 bytes; offset 10,168,320 within boot |
| Ramdisk slot | 4,743,168 bytes, through boot-relative offset 14,911,488 |
| Recovery capture | Start LBA 2334720; pre-root Android core 15,583,232 bytes; independent current 32 MiB partition gzip 10,024,545 bytes; Android core matches the pre-root original |
| Patched boot partition hash | Recorded privately; includes this owner's trusted public keys |

**Backup scope:** before rooting, the complete boot partition was saved twice
independently, and the recovery Android image was saved. After rooting, a raw read
of the 31,037,849,600-byte eMMC user area and separate 4 MiB `boot0` and `boot1`
partitions completed. This does not include RPMB. The compressed user-area stream
passed gzip CRC, EOF and exact decoded-length checks. Its acquisition-stream
SHA-256 matched an independent reread of the saved compressed archive. No `0xCC`
filler remained in the data.
The 16 MiB boot and 32 MiB recovery ranges in the full image matched independent
direct partition rereads. The live boot matches the rooted candidate. The recovery
Android core matches the pre-root original. The stock boot core, measured over the
same 14,911,488-byte length reported in issue #38, also matches that report; this
does not establish that the complete 16 MiB boot partitions match.

This user-area acquisition is byte-verified, but does not by itself establish a
quiescent or transactionally consistent filesystem snapshot. A separate frozen
`/data` capture and offline validation are documented below. No full-device
hardware restore has been performed. The boot-only byte rollback test is
described below; restoring boot alone would not undo later app or
`/system/build.prop` changes.

## Historical boot ramdisk change and verification

This records what was done on this unit before the stock-`su` finding above.
It is not the preferred starting point for another owner with matching firmware.

The patch was prepared offline against the exact original boot bytes:

- `sbin/adbd`: the Thumb bytes `17 20` at file offset `0xf9c` were changed to
  `35 e0`, skipping the privilege-dropping block in **this exact adbd binary**.
  Original adbd SHA-256: `b5ec816bcc70371d1af42bfa51be298fd879755937029c2a232c5c566623a750`.
  These bytes and offsets are compatibility evidence, not a patch recipe for other
  builds; the offline helper checks the expected stock layout and hash.
- `sepolicy`: only the `adbd` and `shell` domains were added to its permissive
  bitmap, allowing the root ADB shell. This weakens enforcement for those domains;
  it is not equivalent to ordinary unprivileged USB debugging. Original sepolicy
  SHA-256: `e538aed0f5a5b93935b897d848ec75477ee5eb8f5bcfd42ff16ce5579ce01e49`.
- `default.prop`: `persist.sys.usb.config=none` became `mtp,adb`.
- `init.sun8i.usb.rc`: the stock MTP and mass-storage actions retained their modes
  but included ADB in the gadget functions and started `adbd`.
- `/adb_keys` in the ramdisk: the owner's two trusted host **public** ADB keys were
  added. ADB authentication code and `ro.adb.secure=1` were retained. Private keys
  stayed on their hosts. This is separate from the userdata method in the blog.

The compressed ramdisk fit its existing slot; its size and legacy Android image
ID were updated. Assertions verified that the kernel and bytes outside the
planned header/ramdisk regions were unchanged.

The per-unit writer checked capacity and the privately retained eMMC identity,
allowed writes only in the two planned regions, and compared each chunk's current
CRC-32 with the original bytes and each RAM payload with its expected CRC-32.
Each write was limited to 128 sectors (64 KiB), read back, compared byte-for-byte
on the host and journaled. The ramdisk was written first and the two header
sectors last: 74 successful transactions, 4,744,192 bytes in total.

An independent read of the entire 16 MiB boot partition then matched the candidate
SHA-256. A normal boot returned `adb shell id` containing `uid=0(root)` and
`context=u:r:shell:s0`. USB ADB and, after configuration, LAN ADB on port 5555
worked with the retained trusted host keys.

**Boot-only undo check:** a guarded byte-level rollback round trip passed on this
unit without rebooting. Before writing, the procedure checked two matching stock
16 MiB boot backups, the known rooted candidate, exact unit identity and capacity,
the boot partition's start/size, and the current complete boot bytes. It wrote only
boot-relative sectors 19860–29123 (ramdisk) followed by sectors 0–1 (header); an
independent whole-partition readback matched the stock backup. It then restored
those same candidate ranges and verified that a second whole 16 MiB readback
matched the rooted candidate. An initial command using an unsupported Android
`dd` conversion option was refused before any write; the corrected block-device
command passed the guards and readbacks.

This verifies byte-level boot undo and reapplication on this unit, not stock boot
runtime: the frame was not rebooted while stock bytes were present. No full-device
restore or general recovery tool for another owner's unit has been tested. Boot
undo does not revert `/system/build.prop`, apps, userdata or other partitions.
No vendor boot binaries are included here.

## Frozen `/data` capture and offline filesystem checks

After the raw user-area image, a separate `/data` snapshot was made with a static
ARMv7 Partclone 0.3.50 binary and static `fsfreeze` 2.40.2. A freeze/thaw probe
passed first. For the capture, clone and gzip were gated on a successful freeze,
with an independent 600-second watchdog. The live capture ran for 6 minutes
10 seconds and thaw completed successfully. The source reported `validfs=1` with
the ext4 `RECOVER` flag clear. Standard CRC-enabled Partclone settings were used;
there was no `-F`, `-I`, no-CRC or rescue option.

The `/data` partition is 28,852,617,216 bytes. Its gzip archive is 293,937,001
bytes (about 280.3 MiB); full gzip CRC validation passed. The decoded Partclone
image is 1,117,266,070 bytes. An offline Partclone restore test passed all
saved-block CRC checks and restored the exact partition size; this was not a
restore to the frame.

Read-only `e2fsck` on the captured image found one open but unlinked inode and
unused inode-bitmap padding. Only a disposable extracted copy was repaired with
`e2fsck -fy`; that removed the recorded orphan and padding finding. A subsequent
read-only `e2fsck -fn` on the repaired copy passed all five passes and exited 0.
The raw source and frozen archives were not changed. This verifies the offline
copy workflow for `/data`; it does not establish a live filesystem repair or
full-device hardware restore. A separate earlier `system` padding-bit observation
was not covered by this `/data` check.

## Post-root setup tested on this unit

- Rootless Launcher 3.9.1 and Fully Kiosk Browser 1.61.4 were installed. Frameo was
  disabled and retained, rather than wiped. A host-served dashboard loads on the
  frame; touch, Wi-Fi and authorized network ADB work.
- WebView 106.0.5249.126 is installed. The Android OS and kernel were not replaced;
  no verified newer Android image was established for this board.
- Root ADB RSA authentication survived repeated ordinary full Android reboots; afterward
  `sys.boot_completed=1` and `adb shell id` again reported UID 0. Fully Kiosk's
  `launchOnBoot` preference remained enabled, but Rootless Launcher stayed foreground
  after the approved overlay and receiver test. Automatic browser launch at boot
  failed this test; manual launch works. A further normal reboot with
  `disableHomeButton=false`, `launchOnBoot=true` and `kioskMode=false` still
  left Rootless foreground. The experimental overlay grant was then returned
  to its default mode. Remote browser opening through the dashboard control
  path succeeded after that reboot. A separate host controller was then tested
  opening Fully once per completed Android boot, without reopening it after
  a manual return to Home. The latest full reboot reached Fully in 55.2 seconds;
  this is one end-to-end startup observation, not a boot-time guarantee.
- `com.android.systemui` was enabled. Appending `qemu.hw.mainkeys=0` to the backed-up
  `/system/build.prop`, preserving root ownership/mode and remounting read-only,
  survived an Android restart and restored functional Back/Home/Recents controls.
  This differs from PF1007L reports where SystemUI is absent and the property
  does nothing. Missing navigation or an authorization popup does not, by itself,
  prove the SystemUI package is absent.
- A clean LAN ADB disconnect/reconnect authenticated as root without an Android
  restart, daemon restart or USB/FEL bridge cycle. Simultaneous additional TCP
  handshake probes stalled while the existing connection remained usable. Use one
  active LAN ADB host as the current workaround; this observation is from one unit
  and is not a universal restriction. The dashboard's HTTP control path changed
  brightness and the requested value was confirmed by exact
  sysfs readback. Home, Settings and Recents were also checked as resumed Android
  activities, not inferred from button appearance alone.
- The thermal zone exposes degrees Celsius on this build, with an active trip
  value of 75. Individual readings of 41 and 51 were observed, not a sustained
  thermal characterization. The native backlight attribute is
  `/sys/class/disp/disp/attr/lcdbl`.

## Browser graphics observations

The installed graphics stack reported `ARM, Mali-400 MP, OpenGL ES 2.0` at
1280x800 and 160 dpi. After 24 scripted taps opening and dismissing a dashboard
controls overlay, `dumpsys gfxinfo de.ozerov.fully framestats` returned 120 recent
ordinary HWUI frames. `FrameCompleted - IntendedVsync` was 63.90 ms at p50,
86.16 ms at p90, 91.10 ms at p95 and 107.24 ms maximum. The interaction harness
ran for 50.94 seconds; that includes starting Android's input command for each
tap and is not an app response-time measurement. No eligible input-event timing
rows were reported. These are recent Android window-rendering diagnostics,
not a whole-page FPS, touch-to-photon or network/page-load result. Temperature
after the interaction was 47 degrees Celsius.

## CPU scaling and workload observations

One short trial was run per core policy with the dashboard/browser active and
brightness set to raw value 79. The same SHA-1 workload used four parallel shell
workers, four iterations each, hashing 8 MiB zero-filled input from `/dev` tmpfs.
Elapsed time came from `/proc/uptime`; temperatures are observed peaks during each
trial. Forced-core phases temporarily disabled `/sys/kernel/autohotplug/enable`,
then re-enabled it as `1` after each phase. Final checks showed autohotplug `1`
and CPU0 online.

| CPU policy | Elapsed | Peak temperature |
| --- | ---: | ---: |
| One core forced online | 13.29 s | 45 °C |
| Two cores forced online | 7.12 s | 48 °C |
| Four cores forced online | 3.25 s | 51 °C |
| Stock automatic hotplug | 3.47 s | 50 °C; all four cores came online |

Temperatures were 41–43 °C before the trials and 43 °C afterward. A larger
640 MiB trial was stopped after about 10 seconds at the chosen 55 °C test cutoff;
the original hotplug policy was restored. That cutoff was a test stop rule, not the
kernel's reported 75 °C trip. These are single short trials, not repeated
benchmarks: the 3.25 s versus 3.47 s difference does not establish a useful
four-core tuning benefit. No sustained thermal, power, UI frame-rate or touch
latency conclusion follows. The cpufreq interface was absent and debug CPU-clock
output was ambiguous, so no frequencies are reported. No lasting CPU policy
change or overclock was applied.

Ten ADB shell true round trips had a 43.0 ms median and 51.8 ms maximum; this is
command round-trip time, not UI input latency. A subsequent Fully Kiosk snapshot
showed 90,218 KiB PSS (about 88.1 MiB), 1,027,036 KiB total RAM and
491,740 KiB MemFree, with additional reclaimable cache. zRAM capacity was
327,676 KiB, with 344 KiB used. This snapshot does not
indicate a need for extra swap. Keep the stock automatic CPU policy pending
repeatable, longer testing.

Root ADB is powerful administration access. Retaining RSA authentication does
not encrypt Android 6 ADB TCP traffic. This owner's LAN setup is not an instruction
to expose port 5555 to the internet or a shared untrusted network.

## Second Pastigio unit

Same listing ([Amazon.ca B0D41ZMYB2](https://www.amazon.ca/dp/B0D41ZMYB2)), firmware
and stock boot hashes as the first Pastigio unit. Host: macOS.

### Route U needed 4-bit 26 MHz eMMC

The `build-uboot.sh` build started, then no USB device appeared. A boot script with
only `ums 0 mmc 0` (the SD card) enumerated, so the eMMC was the problem. With the
eMMC at 4-bit 26 MHz ([patch](patches/pf1007l-v2025.10-emmc-4bit-26mhz.patch)),
Route U and the FEL stub card worked. The SOMY unit in PR #73 didn't need this.

### `su 0` from ADB has no capabilities

The stock `adbd` keeps only `CAP_SETUID` and `CAP_SETGID` (`CapBnd: ffffffe0000000c0`),
and `su 0` inherits that. `pm` works, but `mount -o remount,rw /system` fails with
`Operation not permitted`. Guess, not tested here: `su` from an app may keep full
capabilities, and the first unit's patched `adbd` may not have this limit.

### Video

No HEVC or VP9 decoder. H.264 720p60 plays in hardware.

## Third Pastigio unit

From [#231](https://github.com/wesbos/photo-frame-dashboard/issues/231), macOS, repo at `f1e0820`.
Same fingerprint as above. The partition starts follow the [SOMY ZC002](#somy-zc002-unit-identity)
table, not the first Pastigio unit (`/data` at sector 4268032).

- FEL from the FEL stub card, without opening the case.
- Route U read-only U-Boot (v2025.10) with the base patch, the no-HS patch at 4-bit 26 MHz, START
  STOP and the null console, CPU at 408 MHz, PMIC init kept. **Builds without PMIC init never
  enumerated.** `build-uboot.sh` doesn't take extra patches, so a local copy was used.
- UMS reads dropped within seconds on a port directly on the Mac, and were stable on a dock's USB
  2.0 port. Only a USB-A to USB-C cable worked.
- Full backup with `emmc-macos.py backup-resume`, then the
  [guarded writer](#guarded-userdata-key-writer): 8 ranges, 7,680 bytes, with no Android boot
  between the backup and the write. The ranges were checked over UMS before and after.
- First boot: `device`. `su 0` has the same capability limit as the
  [second unit](#su-0-from-adb-has-no-capabilities).
- Home HQ works as Home with Frameo disabled (`pm disable-user`), and survived a reboot.

Two gaps it found are now in the [guarded writer](#guarded-userdata-key-writer): the generated
`write-data.cmd` and `restore-data.cmd` had no `nulldev` guard (this unit's build needed one; it
was added by hand), now `data-patch-prepare.py --nulldev`; and `emmc-macos.py verify` can't check
a data plan (a one-off read-only check was used), now `emmc-macos.py verify-data`.

The U-Boot patch that needed `git apply --unidiff-zero` was START STOP
(`pf1007l-v2025.10-start-stop.patch`, which has no context lines). The no-HS patch applies with a
plain `git apply` after the base patch.

## What remains untested or unpublished

- On the first Pastigio unit: the repository's complete PF1007L Route U / Route S, and
  the FEL stub SD-card alternative that another ZC002 owner reports in issue #38. (Both
  worked on the [second Pastigio unit](#second-pastigio-unit).)
- The separate `system` inode-bitmap padding-bit observation remains outside the
  completed `/data` validation above.
- Booting the stock image, any full-device restore, serial diagnostics, a newer
  Android ROM, and custom OTA acceptance remain untested.
- The public SPL source has an invalid zeroed request by default. The read-only
  host tool prepares one bounded request after the owner supplies that unit's
  CID and capacity; it checks the result but has not been run on hardware with
  the sanitized image. The previous source compiled from the pinned U-Boot commit in
  an isolated, network-disabled container; the revised reader still needs a full
  SPL rebuild and hardware validation. Native host tests exercise its C request
  handling, reads and rejected write operations using simulated MMC/MMIO, and the
  build refuses an enabled SPL MMC write option or linked storage-write symbols.
  Use on another frame remains unvalidated.
  No per-unit request, eMMC CID, generated SPL, candidate image, or keys are included.

This report contributes the identity, failed-attempt boundary, working storage
initialization, guarded boot changes and observed post-root behavior. It does not
claim that copying another unit's offsets, binary or patched boot hash is safe.

## Guarded userdata-key writer

[`scripts/a33-uboot/data-patch-prepare.py`](../scripts/a33-uboot/data-patch-prepare.py)
builds the host-key authorization from [above](#prefer-stock-su-after-host-key-authorization)
into a guarded U-Boot script, the same way
[`boot-patch.py`](../scripts/a33-uboot/boot-patch.py) builds the PF1007L boot
patch: it checks every payload's CRC-32 and compares the live eMMC against your
recorded original bytes before writing anything, reads each write back and
compares again, and stops at the first check or write that fails — nothing
past that point is written. It uses this repo's existing **read-only**
[Route U U-Boot build](allwinner-a33-mainline-uboot.md) (`build-uboot.sh`);
the eMMC is never exposed as a writable host disk. `mmc write` is a U-Boot
command, internal to the device, unrelated to the USB mass-storage (`ums`)
code path that build patches out.

**Only edit a copy of a backup taken from a frame that has not booted Android since.** Booting
changes `/data`, and the script then refuses (the eMMC no longer holds your recorded bytes). Check
the copy is clean first: `debugfs -R stats` must not list `needs_recovery`; an unreplayed journal
makes a `debugfs -w` edit unsafe.

Prepare it from a pristine and an edited copy of your own verified `/data`
backup (edit the copy with `debugfs -w`, e.g. adding your host's public ADB
key to `/misc/adb/adb_keys` with the ownership/mode/SELinux context already on
your device's own files — never the backup itself):

```sh
python3 -I scripts/a33-uboot/data-patch-prepare.py \
  data-partition-pristine.img data-partition-edited.img <data-partition-start-sector>
```

To skip extracting `/data` (about 29 GB), edit an APFS clone (`cp -c`) of the whole backup with
`debugfs -w 'clone.img?offset=<data start sector × 512>'`, then run `data-patch-prepare.py
backups/a33-emmc-full.img clone.img 0`. Stop if any range it prints starts before the `/data`
start sector ([#231](https://github.com/wesbos/photo-frame-dashboard/issues/231)).

This only reads your two local images. It writes `diagnostics/a33-data-patch/`:
the changed byte ranges (`range-NN.orig`/`.new`), `plan.json`, and
`write-data.scr`/`restore-data.scr`. Re-derive your own plan from your own
backup and partition table — a plan built from one unit's diff describes that
unit's filesystem edit, not reusable offsets or payloads for another one.

To run it: with the frame in FEL and this repo's existing read-only U-Boot
loaded (same as the Route U backup above), load every `range-NN.orig`/`.new`
payload with `sunxi-fel write <addr> <file>` at the addresses `write-data.cmd`
prints for each range, then load and run `write-data.scr` the same way
`write-boot.scr` is run. It checks every range before writing any, so a range that no longer holds
your recorded bytes stops it with nothing written. Undo with `restore-data.scr` the same way, loading the
same payloads. Restore also works after a write that stopped partway: ranges that already hold the
original bytes are left alone, and it writes nothing if any range holds bytes this plan didn't make. Both scripts end in `ums 0 mmc 1`, so the eMMC is available
read-only afterward for a whole-partition reread.

If your U-Boot was built with the null console (`CONFIG_SYS_DEVICE_NULLDEV=y` and an
`ums-readonly.cmd` starting with `setenv stdin nulldev`, as this ZC002 unit needed), prepare with
`data-patch-prepare.py --nulldev ...`. Both scripts then run only inside a successful
`setenv stdin nulldev`, so floating serial input can't look like Ctrl-C and stop a script partway.
If that command fails, they write nothing and wait. Leave the option out for a build without the null console.

Check the ranges over the read-only UMS disk before the write (every range must say `original`)
and after it (every range must say `new`):

```sh
sudo python3 -I scripts/a33-uboot/emmc-macos.py verify-data diskN <exact-bytes>
```

It reads only the planned sectors, checks the payload files against `plan.json`, and stops on a
mix of new and original ranges or on bytes the plan didn't make. After `restore-data.scr`, every
range must say `original` again.

## Offline helper for the historical boot patch

[`scripts/zc002-fel/prepare-root.py`](../scripts/zc002-fel/prepare-root.py) prepares
the historical boot image candidate described above. Check the stock-`su` route
first; this candidate changes `adbd` and SELinux policy. It is an offline builder: it does not
connect to a frame, read storage, or write/flash anything. It accepts only the
verified original 16 MiB boot partition for this ZC002 build, checks the boot,
`adbd` and original `sepolicy` hashes, and refuses unexpected header, ramdisk,
instruction or policy layouts. A mismatch is a stop condition; do not edit the
checks to make another image pass.

Give it a verified original boot-partition backup, one trusted Android
`adbkey.pub` public key, and a new output directory. The tool validates the ADB
RSA key structure, removes its optional comment, and writes a candidate plus a
manifest with the changed paths and allowed boot regions. The candidate contains
that public key and is specific to that owner, so keep the output local and do
not commit it. Different trusted keys produce different candidate hashes.

```sh
python3 scripts/zc002-fel/prepare-root.py \
  --boot /path/to/verified-boot-partition.bin \
  --adb-public-key /path/to/adbkey.pub \
  --output-dir /path/to/new-candidate-folder
```

An existing output directory is refused. This helper does not perform a device
write. The candidate still requires a separately reviewed writer that verifies
the current device bytes, limits writes to the planned regions, and reads every
write back. The [read-only FEL host tool](../scripts/zc002-fel/fel-read.py) can
make one bounded read transaction at a time with a matching compiled SPL,
explicit unit CID/capacity, and the local `sunxi-fel` utility. Its identity-only
probe reports private CID/capacity and stops before any block read; read mode
then requires those explicit values. It verifies the eGON checksum, request
symbols, device result, identity, read length, and CRC; it has no write option
and has only been tested with synthetic host-side fixtures. It does not produce
or verify a full-device backup. Host-only safety checks can be run with:

```sh
python3 -m unittest discover -s scripts/zc002-fel -p 'test_*.py'
```
