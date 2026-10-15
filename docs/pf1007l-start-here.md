# PF1007L (Allwinner A33): start here

Many frames sold as BIUFRAME and similar brands are the **PF1007L**, with an Allwinner A33
board. This is not the Rockchip BIUFRAME in the video. This page collects what owners found on
their units. It has a test sequence. Use the tests to find out,
before you write anything to the frame, whether your unit matches a tested one and
which route to use.

Each step lists a pass condition. **Stop at the first step that fails.** Then report your results
(see [Report your unit](#report-your-unit)). Do not work around a failed check.

Detailed guides behind this page:

| Guide | Covers |
| --- | --- |
| [aimor-remote-root-shell.md](aimor-remote-root-shell.md) | **Read first.** The stock app gives the vendor server a root shell |
| [allwinner-a33-pf1007l.md](allwinner-a33-pf1007l.md) | Identification, FEL with an SD card (Linux), and everything **after** root: backup, launcher, WebView 106, kiosk, memory |
| [pf1007l-20260410-network-adb.md](pf1007l-20260410-network-adb.md) | **T3c:** temporary root ADB over Wi-Fi through the vendor connection, no write. Tested on April firmware |
| [pf1007l-sector-edit-sdcard.md](pf1007l-sector-edit-sdcard.md) | **April `20260410` only:** root ADB over USB with a guarded one-sector `build.prop` edit from the SD card, check-only run first |
| [allwinner-a33-mainline-uboot.md](allwinner-a33-mainline-uboot.md) | **Route U:** root ADB over USB with mainline U-Boot over FEL (macOS and Windows scripts; Linux works too) |
| [allwinner-a33-sdcard-adb-wifi.md](allwinner-a33-sdcard-adb-wifi.md) | **Route S:** root ADB over Wi-Fi from the SD card only, no USB data (Windows + WSL, or macOS) |
| [pf1007l-macos-20260529-recovery-boot-write.md](pf1007l-macos-20260529-recovery-boot-write.md) | **May firmware:** the Route U boot patch written over USB in stock recovery's root-ADB window, no SD card. Erases user data; tight timing |
| [pf1007l-boot-fixes.md](pf1007l-boot-fixes.md) | **After root:** one Wi-Fi MAC, the clock after power cuts, no freeze at Wi-Fi start, fast DHCP |
| [January remote-management report](allwinner-a33-pf1007l.md#9-january-unit-remote-management-and-background-services) | **After root, one unit:** native Tailscale SSH, vendor background exceptions and navigation master-switch reset; custom startup helpers not included |

Unit reports with more detail: [unit A's custom tool](allwinner-a33-boot-access.md),
[January on Windows](pf1007l-windows-20260113-usb-adb-report.md),
[January with ADB already on, full setup over USB](pf1007l-windows-20260113-adb-on-report.md),
[`OS-PF1009` units E and F](pf1007l-pf1009-20260417.md),
[May `20260519` on Windows + WSL](pf1007l-windows-wsl-20260519-report.md),
[May `20260519` on Linux](pf1007l-20260519-linux-report.md),
[May `20260529` on macOS](pf1007l-macos-20260529-report.md),
[May `20260529` on Windows + WSL](pf1007l-windows-20260529-report.md).

Follow the [repository rules](../README.md#rules-we-learned-the-hard-way): the owner approves each
write, a verified backup comes first, and dumps stay private.

## Known firmware and units

More than 30 owners have reported PF1007L units. The firmware string on the About screen is the
best first clue, but it does not settle everything: units with the same firmware and boot image
differ in eMMC size and in whether ADB ships on.

| Firmware string ends with | Reports | eMMC sectors | Boot SHA-256, first 8 (sector 172032, 31,028 sectors) | Stock ADB | What worked |
| --- | --- | --- | --- | --- | --- |
| `321-OS-AIMOR.0.20260113` | units A, B, C; #6, #12, #18, #19, #61, #97, #99, [Windows report](pf1007l-windows-20260113-usb-adb-report.md), [macOS report](pf1007l-macos-20260113-report.md), [ADB-on report](pf1007l-windows-20260113-adb-on-report.md) | 30,535,680 or 30,777,344 | `d71c313d` | Usually no; **on** at first connection in the [ADB-on report](pf1007l-windows-20260113-adb-on-report.md) (`1f3a:1002`, root; origin unknown) | Route U; Route S (at 12 MHz on the larger eMMC, #61; at 1-bit 25 MHz with legacy timing on a smaller Samsung eMMC, #97, local build); a guarded one-sector edit on one unit. #99: the eMMC never initialised in either route's U-Boot (**Unsolved**). On a larger-eMMC unit, Route U needed the warm-up SPL (now in the repository build) and the no-HS patch ([macOS report](pf1007l-macos-20260113-report.md)) |
| `321-OS-AIMOR.0.20260410` | unit D (#13), #17, #20, #27, #69, #8 comment, [unit G](allwinner-a33-sdcard-adb-wifi.md#14-april-20260410-firmware), [Linkdaze PF1007BK](pf1007l-linkdaze-20260410-report.md) (#83) | 30,777,344 | `8ffc2a7d` | Usually no; **on** in one unit | Route U; [T3c](#t3c-temporary-adb-through-the-aimor-connection) with no write, then `persist.sys.usb.config` for persistent USB ADB (#83, one unit); [one-sector edit](pf1007l-sector-edit-sdcard.md); Route S with an April patch builder that is not in this repo (unit G) |
| `321-OS-AIMOR.0.20260416` | #16 comment, #102, #119 | 30,777,344 | `fc4d22d2` over 31,032 sectors (#16 comment, #119); `bef19d67` over 31,028 sectors (#102, #119) | No (#16 comment, #119); **on** in #102 (`1f3a:1002`, root, survives reboot) | Route U with a 12 MHz low-power U-Boot, then a guarded one-sector `build.prop` edit (#119; unlike #16's unit it had no `/data` override, so one sector was enough — the published one-sector guide is `20260410`-only); an unpublished `build.prop` edit; nothing needed (#102) |
| `OS-PF1009.0.20260417` | units E and F ([report](pf1007l-pf1009-20260417.md)) | 30,777,344 | `3f0dc9d5` | No | Route U with [U-Boot fixes](#u-boot-settings-that-fixed-ums-problems) |
| `FL-AIMOR-OS.0.20260519` | #24, #36, #62, #65 comment, #98, [Windows report](pf1007l-windows-wsl-20260519-report.md), [Linux report](pf1007l-20260519-linux-report.md), [macOS Route S](pf1007l-macos-20260519-route-s-report.md) | 30,777,344 | `9a6e2456`, **different ramdisk slot** | No | Route U with U-Boot fixes; Route U patch carried on the SD card with a 12 MHz FEL U-Boot (#62, #68); [recovery-window write](pf1007l-macos-20260529-recovery-boot-write.md) (#65 comment). Route S only by editing its hash guard (do not); one unit: Route S dump at 12 MHz + Route U `boot-patch.py` when `ums` resets. #98: the base build **and** the no-HS patch both showed only the SD card (**Unsolved**) |
| `V10-1680.0.20260529` (also `321-OS-AIMOR.0.20260529`, #81) | #8, #16, [#41](pf1007l-windows-20260529-report.md), [#28](pf1007l-macos-20260529-report.md), [recovery write](pf1007l-macos-20260529-recovery-boot-write.md), [no-HS report](pf1007l-macos-20260529-no-mmc-hs-report.md), #81, [#103](pf1007l-macos-20260529-report.md#second-unit-larger-emmc-2026-10-13-access-only-no-backup), #116, #117 | 30,777,344 or 30,535,680 | `6c118dc1` | **On** in #8; off in #16, #28, #81, #103, #116, #117, the no-HS unit and the recovery-write unit; not established in #41 | Nothing needed (#8); [T3c](#t3c-temporary-adb-through-the-aimor-connection) on Windows, then `persist.sys.usb.config` for persistent USB ADB across a power cut, no boot patch (#117, one unit); Route U; Route U with the [no-HS U-Boot patch](patches/pf1007l-v2025.10-no-mmc-hs.patch) (no-HS report); Route U with a 12 MHz low-power build on Linux, larger eMMC, even on a direct port (#116); Route U with the boot patch aimed at the `ptp` USB action, because that unit's saved USB setting was `ptp` (#81, local edit, not in the repo); recovery-window write, also reachable from AiMOR's on-screen Recovery Mode button (#116); a 1-bit 25 MHz read-only `ums` backup, then a userdata `persist.sys.usb.config` edit (#41, record only, not a published route). The patched boot-image hash depends on the host's zlib, so a different patched hash is expected (#116) |

Numbers are GitHub issues and pull requests. Units A to C are from the first three guides:
[allwinner-a33-pf1007l.md](allwinner-a33-pf1007l.md) (A, DC jack and Linux, rooted with a custom
tool), [allwinner-a33-sdcard-adb-wifi.md](allwinner-a33-sdcard-adb-wifi.md) (B) and
[allwinner-a33-mainline-uboot.md](allwinner-a33-mainline-uboot.md) (C).

What this tells you:

- **Test ADB first** (T3, T3b). Some units ship with root ADB on (#8, #102), even with the same
  firmware and boot image as units that don't.
- **Two eMMC sizes.** The larger 30,777,344-sector eMMC is now the common one. It is behind most
  of the U-Boot `ums` problems, see [U-Boot settings](#u-boot-settings-that-fixed-ums-problems).
- **Route U** checks the boot image's structure, not a fixed hash, so it has worked on every
  firmware it was tried on (all but `20260416`). **Route S** accepts only the January boot image.
- **The one-sector `build.prop` edit** is published for April `20260410` only
  ([guide](pf1007l-sector-edit-sdcard.md)). Its check-only run refuses unless the sector holds
  exactly the expected bytes, because that sector differs on other firmware. The same edit worked on
  one January unit ([report](pf1007l-windows-20260113-usb-adb-report.md)), but it is **not a
  published route** for other firmware. Some units set the same property in
  `/data/property/persist.sys.usb.config`, which overrides `build.prop`; an AiMOR factory reset
  clears it.
- **Stock recovery runs root ADB** (`18d1:d001`, file transfer only, no shell, no prompt) for about
  13 to 20 s during an AiMOR factory reset, on April and May firmware. It erases user data, and it
  is a security issue ([details](pf1007l-sector-edit-sdcard.md#9-stock-recovery-runs-root-adb-during-a-factory-reset)).
  It is enough to copy the boot partition for T6 with no SD card. Writing the boot patch in that
  window worked on two May units, but the margin is a few seconds: an interrupted write leaves a
  frame that only an SD-card route can repair, so have a spare card ready.

Hardware notes from several units (#6, #13): the Wi-Fi chip is an AIC8800 with no stored MAC
address, so the MAC and the DHCP address change at each boot, or even at each Wi-Fi reconnect (#83).
Set a static IP if your Wi-Fi screen has **Modify network** (some don't), pin the MAC with
[pf1007l-boot-fixes.md](pf1007l-boot-fixes.md), or find the frame in the ARP table by the MAC's
first bytes, which stayed the same on one unit. Stock firmware
listens on TCP 8086, AiMOR's paired file service, not ADB. AiMOR's `vuid_cert.txt` is a device
credential: keep it out of anything you publish.

## The USB-A to USB-C rule

On USB-C-only units, **use a USB-A to USB-C data cable**. Plug it into a USB-A port, or into a
USB-A port on a hub or adapter.

Most reports agree. A USB-C to USB-C cable gave unit C **no power and no data**. The frame appears
to lack the USB-C CC
pull-down resistors. Without them, a USB-C host or charger never detects the frame and never turns
on power. The same likely applies to USB-C chargers. For normal use, power the frame from a USB-A
charger with an A-to-C cable.

The [May Mac report](pf1007l-macos-20260529-report.md#cable-power-and-usb-observations)
records intermittent C-to-C enumeration through a hub, with A-to-C as its stable final
path. Treat the cable recommendation as a reliable starting point, rather than proof
that C-to-C can never carry data. CC wiring was not measured in that session.

**Power:** several units dropped off USB through bus-powered hubs and monitor hubs, mostly during
long backups. A direct port on the computer, or a powered hub, fixed it (#16, #18, #24). One
January unit boot-looped with the patched image when powered from an Apple USB-C Digital AV
adapter; direct power fixed it (#110).

Other things that hid USB data:

- **A charge-only cable.** Use a cable that you know carries data, for example one that works
  with a phone.
- **A USB 3 hub without its USB 2.0 half.** The frame is USB 2.0 only. On macOS, check that a
  "USB2.0 Hub" appears in the USB tree. Moving the hub to a different port fixed it. Then
  power-cycle the frame.

## Test sequence

**Try for ADB in this order, and stop at the first that works:**

1. **Stock ADB over USB** ([T3](#t3-usb-data-test)). No changes to the frame.
2. **Stock ADB over the network** ([T3b](#t3b-network-adb-test)). No changes to the frame.
3. **Temporary ADB through the AiMOR connection** ([T3c](#t3c-temporary-adb-through-the-aimor-connection)).
   No write to the frame, but it needs the frame online and gives open root ADB until the next
   reboot. Tested on April `20260410` firmware.
4. **Boot patch written from an SD card** (T4 onward). Use this only if 1 to 3 fail. It
   writes to the frame's boot partition. Both patch routes need an SD card. Route U (USB) is
   preferred over Route S (SD card only), because it takes a full backup and verifies it over USB.

Ideally no one needs a boot patch. Some units do ship with ADB on (#8), so
[report it](#report-your-unit) if yours does.

### T1. Read the About screen (no tools)

Settings → About. Record the model and firmware string.

**Pass:** the model is `PF1007L` and the firmware string ends with one of the versions in
[the firmware table](#known-firmware-and-units).

- `A33` in the firmware string with a version not in the table: the routes may still work, but your
  unit is untested. Continue with the read-only tests only, and report your results.
- Not A33 (for example a Rockchip `rk312x` firmware): this page does not apply. See the
  [BIUFRAME guide](biuframe-setup-guide.md).

Do not connect the frame to Wi-Fi yet. Read [aimor-remote-root-shell.md](aimor-remote-root-shell.md)
first.

### T2. Ports

Look at the frame. Record **DC jack + USB port** (like unit A) or **USB-C only** (like units B and C).

### T3. USB data test

Use a USB-A to USB-C data cable, as described above. Connect the frame to the computer and let it
boot to the AiMOR screen. Then look for vendor ID `1f3a`:

```sh
# macOS
system_profiler SPUSBDataType | grep -i -B4 -A6 '0x1f3a'
# If that profiler type returns nothing on newer macOS:
system_profiler SPUSBHostDataType
ioreg -p IOUSB -w 0
# Linux
lsusb | grep -i 1f3a
# Windows (PowerShell)
Get-PnpDevice -PresentOnly | Where-Object InstanceId -match 'VID_1F3A'
# Any OS, with the Android platform tools
adb devices -l
```

| Result | Meaning | Next |
| --- | --- | --- |
| `adb devices` lists the frame as `device` | You have ADB over USB | Go to [T7](#t7-confirm-root-adb) |
| `adb devices` lists the frame as `unauthorized` | ADB is on, but waits for approval on the screen | Accept the "Allow USB debugging" prompt on the frame. Units B and C have no SystemUI, so the prompt may never appear. Then continue at T3b and report it |
| `1f3a:1000` (product "Android"), no ADB | USB data works, but this unit's current interface does not expose ADB | Go to T3b. If that fails, **Route U** (T4) |
| Nothing, after you try the checklist below | No USB data path | Go to T3b. If that fails, **Route S** (T5) |

Before you decide on "nothing", try each of these:

1. A different A-to-C cable that you know carries data.
2. A USB-A port directly on the computer, and also a USB 2.0 hub.
3. Unplug and replug the frame (on USB-C-only units the cable is the power switch).
4. A different computer.

### T3b. Network ADB test

No PF1007L report so far had network ADB on stock firmware. Other A33 frames did (see the
[device index](devices.md)). Test yours anyway: it is free, and it changes nothing on the frame.

This test needs the frame on Wi-Fi. Then AiMOR connects to the vendor server, which can send it
root commands (see [aimor-remote-root-shell.md](aimor-remote-root-shell.md)). If you can, first
block outbound TCP port 7806 from the frame on your router. Keep the test short.

Find the frame's IP address in your router's client list, or in Settings → About → Status on the
frame. Then, from a computer on the same network:

```sh
nc -vz -w 3 <frame-ip> 5555        # Windows: Test-NetConnection <frame-ip> -Port 5555
adb connect <frame-ip>:5555
adb -s <frame-ip>:5555 shell id
```

| Result | Next |
| --- | --- |
| `uid=0(root)` or another `uid` | You have ADB over the network. Set a static IP for the frame, then go to [T7](#t7-confirm-root-adb) and use `adb -s <frame-ip>:5555` |
| `unauthorized` | Accept the prompt on the frame if one appears, and report it |
| Connection refused or timed out | No stock network ADB. Try T3c, then **Route U** (T4) if T3 found `1f3a:1000`, or **Route S** (T5) |

Take the frame off Wi-Fi again until you finish [T8](#t8-lock-it-down-before-the-frame-stays-online).

### T3c. Temporary ADB through the AiMOR connection

One `PF1007L / AiMOR 6.0.78 / 20260410` unit obtained root ADB through a temporary
DNS redirect of `imsconnect.efercro.com` and one vendor command. See the
[complete procedure and unit report](pf1007l-20260410-network-adb.md), including
the controlled network session, exact command requiring owner approval, identity
checks, and DNS restoration. This is an alternative before a boot patch on that
specific firmware, not stock ADB or a read-only test.

**Pass:** the procedure's ADB identity checks match the April firmware and return
UID 0; restore DNS and stop the helpers. Then back up and follow the existing
post-root setup guides with `adb -s <frame-ip>:5555`. The January-only fingerprint
check in T7 does not apply to this report. A reboot ends this temporary access.
Other firmware variants remain untested for this route. January `20260113` runs the same AiMOR
6.0.78 with the same command path, so it may work there too.

**While this access is active, port 5555 is root ADB with no key check, open to your whole
network.** Run it on a network you control, finish the T8 lock-down in the same session, then
reboot to close it, or move to a key-authenticated setup.

**Making it persistent without flashing (April `20260410` #83; May `20260529` #117):** on these
debuggable builds, `setprop persist.sys.usb.config mass_storage,adb` kept USB ADB after a reboot —
in #117 it survived a 15-second power cut. It writes `/data/property`, so ask the owner first.
Undo: `setprop persist.sys.usb.config mass_storage`. Check USB ADB after a reboot before you count
it as persistent ADB in T8. Don't use the Wi-Fi equivalent (`persist.adb.tcp.port`) except briefly
on a network you control: it opens root ADB with no key check at every boot. See the
[report](pf1007l-linkdaze-20260410-report.md). T3c itself is also confirmed on `20260529` from
Windows (#117), using a local DNS record instead of `dns.py`, which cannot run on Windows.

### T4. Route U: FEL test (non-destructive to the frame)

Do this only if T3 found `1f3a:1000`.

Make the FEL stub SD card. On Linux, use section 2 of the
[PF1007L guide](allwinner-a33-pf1007l.md#2-use-an-sd-card-for-stable-fel-if-adb-is-absent). On
macOS, use `scripts/a33-uboot/fel-card-macos.py`. See
[section 2 of the U-Boot guide](allwinner-a33-mainline-uboot.md#2-fel-from-the-sd-card-macos).
These write 8 KiB to a spare card's unused boot area. They do not write to the frame.

Remove power, insert the card, reconnect the cable. The screen stays dark.

```sh
diagnostics/sunxi-tools/sunxi-fel version
```

**Pass:** the USB ID is `1f3a:efe8` and the output contains `soc=00001667(A33)`.

If the eMMC disk never appears, disappears during the backup, or the frame resets, see
[U-Boot settings that fixed ums problems](#u-boot-settings-that-fixed-ums-problems).
`emmc-macos.py backup-resume` continues a backup after a dropout.

Then continue with the [U-Boot guide](allwinner-a33-mainline-uboot.md) sections 3 and 4. They build
a U-Boot with USB mass-storage writes removed. Its native `mmc write` command still exists
for the separately approved guarded patch. It exposes the eMMC to the host as a **read-only** disk, and you
take a full backup. Go to T6 with that backup.

To use this route on Linux, run the FEL steps from the PF1007L guide. `emmc-macos.py` also
runs on Linux: pass the whole disk name, for example `sudo python3 -I scripts/a33-uboot/emmc-macos.py backup sdb <exact-bytes from lsblk -b>`.

On Windows, use WSL2 with usbipd for the FEL steps and the PowerShell scripts for the card and
the backup. See [section 9 of the U-Boot guide](allwinner-a33-mainline-uboot.md#9-windows-host-wsl2--usbipd).
Never attach U-Boot's disk (`1f3a:1010`) to WSL.

### T5. Route S: SD boot and eMMC dump test (read-only on the frame)

Do this if T3 found no USB device. It also works on units with USB.

The A33 Boot ROM tries the SD card before the eMMC. A card with U-Boot in its boot area therefore
runs before Android, without USB. Follow sections 3 to 6 of the
[SD card guide](allwinner-a33-sdcard-adb-wifi.md). The dump script runs on the frame. It reads the
first 2 GiB of the eMMC twice per chunk and writes the chunks to the card. It does not write to the
eMMC.

**Card choice:** use a **32 GB or smaller (SDHC) card formatted FAT32**. U-Boot cannot read exFAT.
Most cards larger than 32 GB come as exFAT, and Windows formats them as exFAT too. A larger card
works once it has a FAT32 partition (#97 used a 64 GB card). The card needs
2.2 GB free for the dump.

**Pass:** `check-dump.py` prints `stage: finished` and `emmc_dev: ok`, and all 32 chunks (`00`
to `1f`) are `ok`.

If no `a33-status.txt` appears on the card at all, U-Boot did not run. Stop and report it.

Hosts: Windows uses `fel-sdcard.py` and builds U-Boot in WSL; macOS uses `card-macos.py` and
`build-macos.sh` (Docker). See the [SD card guide](allwinner-a33-sdcard-adb-wifi.md). If the dump
stops with `FAIL first read`, see [U-Boot settings](#u-boot-settings-that-fixed-ums-problems).
One macOS unit whose `ums` kept resetting dumped Route S with a 12 MHz build and patched Route U
over FEL: see the [May `20260519` macOS report](pf1007l-macos-20260519-route-s-report.md). Its
manual card write is kept only as a record — use `card-macos.py` above, not `dd`.

### T6. Compatibility gate: is your boot image the tested one?

This is the main test. It shows whether the boot patch was tested on the same bytes that your unit
has. It only reads your backup.

```sh
# Route U, full eMMC image:
dd if=backups/a33-emmc-full.img bs=512 skip=172032 count=31028 2>/dev/null | shasum -a 256
# Route S, 64 MiB chunks (chunk 01 starts at sector 131072):
dd if=backups/pf1007-emmc/emmc-01.bin bs=512 skip=40960 count=31028 2>/dev/null | shasum -a 256
```

On Linux, `sha256sum` replaces `shasum -a 256`. Route S also prints this hash as `original` in
`REPORT.txt` (section 7 of the SD card guide).

| Check | Tested value |
| --- | --- |
| Partition starts (sectors) | env 139264, **boot 172032**, system 237568, recovery 2400256 |
| Boot image | `ANDROID!` header, 2048-byte page, 15,886,336 bytes |
| Boot image SHA-256 | January: `d71c313ddaa4693948acb20af7740ccb56c88bf9376746a47fce2d00c14fc6a4`. Others: the first 8 digits in [the firmware table](#known-firmware-and-units) |
| eMMC size | 30,535,680 sectors (15,634,268,160 bytes) or 30,777,344 sectors (15,758,000,128 bytes) |

`check-dump.py` and `emmc-macos.py` print the partition table. `boot-patch.py` (Route U) refuses a
sector that is not a partition start.

**Pass:** the boot starts at 172032 and the SHA-256 matches a row of the firmware table. Then a
patch has been tested on your exact boot image. The May `20260519` image has a different ramdisk
slot; `boot-patch.py` reads the slot from your image, so its write ranges differ from the ones below.

**On mismatch:**

- **Route S** refuses to continue. `build-write.sh` accepts only the January SHA-256. Do not edit
  it. Report the hash, and use Route U if your frame has USB data.
- **Route U** checks the structure, not a fixed hash. It requires the exact stock USB init action,
  a ramdisk that fits, and only the expected header bytes changed. A different hash is
  **untested**. Report it, and ask in an issue before you write.

## U-Boot settings that fixed ums problems

The repository's Route U build (`scripts/a33-uboot/`) runs the eMMC at full speed on an 8-bit bus.
That worked on units B and C (30,535,680 sectors). On the larger 30,777,344-sector eMMC, many owners
saw the `ums` disk never appear, disappear partway through a backup, or the frame reset. These
changes fixed it for them. **Except for the DRAM fixes, they are not in the repository's build yet**,
so each one is a local change to the U-Boot source, and its reports are the reference.

| Symptom | What fixed it | Reports |
| --- | --- | --- |
| Read errors, `ums` drops, slow or failing backup, or no USB device at all after U-Boot starts while an SD-only `ums 0 mmc 0` script enumerates | eMMC **4-bit at 26 MHz** ([patch](patches/pf1007l-v2025.10-emmc-4bit-26mhz.patch)), or 8-bit at 25 MHz | #16, #18, #24, #27, #29, #6 (8-bit high speed hung), #81 (8-bit dropped 42–172 MB in; 4-bit at 26 MHz with START STOP finished two passes), #96 (Pastigio ZC002, no USB device at 8-bit: [report](pastigio-zc002.md#second-pastigio-unit)) |
| The disk disappears when the computer sends "eject" or "stop" | Ignore START STOP UNIT unless it is a real unload: [patch](patches/pf1007l-v2025.10-start-stop.patch) | #28, #16, #24, #81 |
| Drops through a bus-powered hub | Direct port or powered hub; low-power build (`CONFIG_SUNXI_NO_PMIC=y`, CPU at 408 MHz) | #16, #24, #29 |
| Single read errors | Retry each read up to 8 times | #24 |
| Route S dump fails | eMMC at 12 MHz. On May `20260519` a 12 MHz dump could still reset about a minute in | #24 comment, #61 (January), #62, #68 |
| FEL U-Boot `mmc read` errors on May `20260519` even at 4-bit 26 MHz; guarded write refuses | eMMC at 8-bit **12 MHz** in the FEL U-Boot too | [Windows report](pf1007l-windows-wsl-20260519-report.md) |
| Bulk eMMC reads fail even at 4-bit 26 MHz: the UMS gadget dies on (or seconds before) the first read, or every `mmc read` errors while `mmc info` still identifies the chip | Lower the eMMC cap to **12 MHz** (`pf1007l-v2025.10-linux-12mhz.patch` or `max-frequency = <12000000>`), with the low-power build (`CONFIG_SUNXI_NO_PMIC=y`, CPU 408 MHz) | [Linux report](pf1007l-20260519-linux-report.md); #110 (macOS, January, larger eMMC: `mmc dev 1` took 47 s at 26 MHz and every read failed; all speed modes fine at 12 MHz); #116 (Linux, `20260529`, larger eMMC, direct port); #119 (Windows, `20260416`) |
| `ums` disk (`1f3a:1010`) resets or vanishes after being attached to WSL with usbipd | Never attach `1010` to WSL; read it from Windows with `emmc-windows.ps1` ([Windows section](allwinner-a33-mainline-uboot.md#9-windows-host-wsl2--usbipd)) | #6, #75 |
| DRAM init fails on a cold start | DRAM byte lane 0 retrain and a warm-up SPL, now in the build ([section 4 of the U-Boot guide](allwinner-a33-mainline-uboot.md#4-expose-the-emmc-read-only-and-back-it-up)). Hardware-tested only on #6, with U-Boot v2025.01; #6 also needs the 4-bit eMMC build | #6 |
| `ums` exposes no eMMC (May `20260529`), or Route S writes `emmc_dev=FAIL` (January `20260113`); `unable to select a mode: -1` | Legacy timing. The eMMC stops answering after U-Boot switches it to high-speed timing, at any clock. 4-bit with the HS host capabilities removed: [patch](patches/pf1007l-v2025.10-no-mmc-hs.patch). 1-bit at 25 MHz with HS removed also worked, in Route U (#41) and in Route S's device tree (#97, local change, not in the repo). Three units had the smaller 30,535,680-sector eMMC and the January unit the larger 30,777,344-sector one; #97 reported Samsung `MAG2GC`. Check the disk's capacity: some builds exposed the SD card instead | #41, [no-HS report](pf1007l-macos-20260529-no-mmc-hs-report.md), #97, [macOS report](pf1007l-macos-20260113-report.md) |
| U-Boot never initialises the eMMC: `ums` shows only the SD card, or `mmc dev 1` fails in both Route U and Route S | **Unsolved** on #99 and #98, which have not tried the [no-HS patch](patches/pf1007l-v2025.10-no-mmc-hs.patch) or 1-bit 25 MHz (#97). On another January unit with the larger eMMC, `ums` showed only the SD card until the no-HS patch was added; then the eMMC appeared and a full backup completed ([macOS report](pf1007l-macos-20260113-report.md)) | #99 (January; 8- and 4-bit, 25/26 MHz, low-power build, no `vmmc-supply` and Sinlinx drive strength did not help), #98 (May `20260519`, base build only) |
| `sunxi-fel` stops with `usb_bulk_send ERROR -7` after the SPL; later the read-only disk vanished before a backup started (May `20260529`, larger eMMC, macOS) | **Unsolved** on #103 (START STOP correction already present). On a January unit, the same `ERROR -7` happened on every load, cold starts included, and the warm-up SPL (now in the repository build) fixed it on every later power cycle. That points to the DRAM cold-start problem (#6) on that unit, not necessarily on #103 | [macOS report](pf1007l-macos-20260113-report.md), [#103](pf1007l-macos-20260529-report.md#second-unit-larger-emmc-2026-10-13-access-only-no-backup) |
| Unstable USB reads on April `20260410` | CPU at 480 MHz in the RAM U-Boot | #56 |
| Bulk reads fail on January (Windows) at 4-bit 26 MHz; single sectors are fine | **Unsolved** | #63 |
| U-Boot USB gadgets (`ums`, fastboot) fail with error `-71`, while FEL and Android ADB work | **Unsolved** (one May `20260519` unit) | #62, #36 |
| Large `sunxi-fel write` uploads (about 10 MB) arrive corrupted | **Unsolved.** Route U's CRC and compare guards refused the write, as intended | #62 |
| Frame resets 45 to 50 s after U-Boot starts | The START STOP patch above (full backup at about 2.7 MB/s afterwards) | #19 |
| `ums` never enumerates on May `20260519` | **Unsolved.** Try the 4-bit build and the START STOP patch. One unit: Route S dump, then Route U `boot-patch.py` ([report](pf1007l-macos-20260519-route-s-report.md)) | #36 |
| Frame resets about 16 minutes into a continuous read | **Unsolved.** Resumable backup works around it | #13 |
| SD-booted U-Boot: the eMMC stops answering after 18 MiB to a few hundred MiB of reads, also at 4-bit 26 MHz with retries and `mmc rescan`. U-Boot keeps running | **Unsolved.** Keep U-Boot's eMMC work short ([one-sector edit](pf1007l-sector-edit-sdcard.md)), then back up over root ADB | [sector edit](pf1007l-sector-edit-sdcard.md#8-why-only-one-sector-u-boots-emmc-access-on-this-unit) |

Route S's U-Boot (`scripts/a33-sdboot/a33.config`) has no `CONFIG_CRC32_VERIFY`, so `crc32 -v` does not
work there. Scripts for it must check payloads with `hash sha256`, as `boot-write.cmd.in` does.

Two ways to see what U-Boot is doing on a frame with no serial console: write marker files to the
SD card from the U-Boot script (`fatwrite`, #99), or run a debug U-Boot build in RAM and read its
console over `fastboot oem console` (#110).

`build-uboot.sh` checks where the SPL code ends. Builds with the low-power changes pad the SPL with
`0xFF`, which that check misreads: #16 and #29 bypassed it, while #110 and #119 instead adjusted the
check to treat `0xFF` as padding. Prefer adjusting the check to bypassing it, and do not bypass it
for any other reason.

### Write the patch (owner approval for this specific write)

Pick **one** route. Undo with the same route.

| | Route U ([U-Boot guide](allwinner-a33-mainline-uboot.md) sections 5 to 7) | Route S ([SD card guide](allwinner-a33-sdcard-adb-wifi.md) sections 7 to 10) |
| --- | --- | --- |
| Result | Root ADB over **USB** (`1f3a:1002`), no key needed | Root ADB over **Wi-Fi** on port 5555, only your `adbkey` is accepted |
| Ramdisk change | `init.sun8i.usb.rc`: adds ADB to the USB functions | `default.prop`, `init.rc`, new `/adb_keys` |
| Bytes written | 2 header sectors + the ramdisk slot (5.4 MiB) | Whole boot image (15.9 MB, 31,028 sectors) |
| On-device guard | CRC-32 of each payload, and the eMMC must still hold the original bytes | SHA-256 of the file and of the current partition |
| Host verify | Whole eMMC compared with the backup + plan | Status file on the card (`OK_WRITTEN_AND_VERIFIED`) |
| Undo | `restore-boot.scr` | `sdcard-restore/` script |
| Risk | Interrupted power during a 5 MiB write | **Do not cut power** during the write. An interrupted write cannot be repaired with the published scripts |

Both patches were checked offline on a synthetic boot image of the same size. Both changed only the
documented ramdisk files and kept the kernel identical. Route U's write ranges came out as
`[192004, 203060)` and `[172032, 172034)`, the same ranges that were written on the real units.

### T7. Confirm root ADB

```sh
# Route U / USB:          use  adb -d
# Route S / Wi-Fi:        adb connect <ip>:5555, then use  adb -s <ip>:5555
adb -d shell id                          # uid=0(root)
adb -d shell getprop ro.build.fingerprint
adb -d shell getprop sys.boot_completed  # 1
```

**Pass:** `uid=0(root)`, and a fingerprint like
`AEEZO/astar_m86_8723cs/astar-m86_8723cs:6.0.1/MOB30R/20260113:eng/test-keys` with your firmware's
date in place of `20260113`.

Route S: set a static IP on the frame. The Wi-Fi MAC changes at each boot, so the DHCP address
changes too.

### T8. Lock it down before the frame stays online

> **If your only ADB is temporary (T3c), do not disable AiMOR yet.** AiMOR is then your only way
> back in without an SD card, and some builds hide disabled apps in Settings, so you can't turn it
> back on from the screen (#56, #69). Until you have persistent ADB (Route U, Route S, the
> one-sector edit, or `persist.sys.usb.config` with USB ADB confirmed after a reboot), block TCP 7806 and force-stop AiMOR instead. That is a stopgap: AiMOR still
> turns SELinux off at every start. See
> [the lockout notes](pf1007l-20260410-network-adb.md#6-lockout-after-disabling-aimor-and-offline-recovery).

Do section 8 of [aimor-remote-root-shell.md](aimor-remote-root-shell.md): block TCP 7806, install a
launcher, then disable `com.efercro.os.aimor`, `com.yhk.qeota` and `com.DeviceTest`. Wait until
`package-restrictions.xml` shows `enabled="2"`, then reboot.

After T3b, forget the Wi-Fi network on the frame (or `svc wifi disable` over ADB): one `20260416`
unit had silently rejoined the network it used for T3b, and AiMOR already had an established
connection to `:7806` when T8 started (#119). #113's January unit was caught online the same way,
mid-backup.

```sh
adb shell 'netstat -an | grep :7806'
```

**Pass:** no output after the reboot.

### Then set it up

Continue with sections 4 to 8 of the [PF1007L guide](allwinner-a33-pf1007l.md#4-back-up-before-modifying-android):
launcher, WebView 106, kiosk and memory. Known differences on these units, from
[section 8 of the U-Boot guide](allwinner-a33-mainline-uboot.md#8-notes-from-this-unit-after-root):

- No SystemUI: no status bar or navigation bar. `qemu.hw.mainkeys` does nothing.
- `BOOT_COMPLETED` goes only to a whitelist. For auto-start, make the kiosk a Home app.
- No ISRG Root X1 in the trust store, so Let's Encrypt sites fail in WebView. Add the root
  certificate or use a local proxy.
- One May `20260519` unit also had no GTS Root R1/R4 and no GlobalSign Root CA, so the repo's
  own dashboard on `*.workers.dev` failed with `net_error -202` too. Add the three roots listed
  in the [Uhale guide](si006-uhale.md), checked by SHA-256.
- WebView 106 lacks `oklch()`, `color-mix()`, CSS nesting and `:has()`. Tailwind v4 colours break.
- The time zone ships as `America/New_York`.
- `adb reboot` hangs on many units (one rebooted cleanly). Plan to power-cycle instead.
- After the WebView 106 swap, a hub-powered unit may need one boot with Wi-Fi off (dexopt).
- If the clock shows 1969, run `settings put global auto_time 1`.
- For a frame that must boot unattended (power cuts, a fixed MAC, the clock, a freeze when Wi-Fi
  starts), install [pf1007l-boot-fixes.md](pf1007l-boot-fixes.md).
- `/system/xbin/su` is setuid root with no prompt (#24), so any app on the frame can get root.
  Install nothing untrusted.

## For agents

- First, [check for new issues and pull requests](../README.md#check-for-updates-and-send-back-what-you-find).
  The firmware table was last updated on 2026-10-13. A newer report may cover your unit.
- Run T1 to T6 in order. They are read-only for the frame's eMMC. Do not start T4 or T5 until
  T3 (USB ADB) and T3b (network ADB) have both failed. T4 and T5 write only to a spare
  SD card, and only with the owner's approval.
- T3c is a runtime change. It needs approval for its exact command and the frame online, and it
  does not replace T6 for either boot-patch route.
- Stop at the first failed pass condition, and print the [report](#report-your-unit).
- Never edit a hash, size, sector or disk-name guard in a script to make it pass.
- For a May-style Route U experiment, use the [agent handoff checklist](pf1007l-macos-20260529-report.md#handoff-checklist-for-another-agent).
  It distinguishes the pinned host build, per-unit boot-image plan, generated `.cmd` versus
  executable `.scr`, whole-device readback, and package-state checks after reboot.
- Before the write step, show the owner the route, the exact bytes to be written and the undo path.
  Get explicit approval for that write.
- Do not commit anything in `backups/` or `diagnostics/`, and do not publish serials, MAC
  addresses or the full SHA-256 of a whole-eMMC image.

## Report your unit

Open an issue or PR with this, whether your unit passed or failed. Each report makes the tested range
wider. Agents: follow [the README's PR steps](../README.md#check-for-updates-and-send-back-what-you-find).

```text
About model / firmware:
AiMOR version:
Ports (DC jack, or USB-C only):
Cable and port that gave USB data (or none):
T3 USB IDs seen / adb devices output:
T3b network ADB result (port 5555):
T4 sunxi-fel version output (or skipped):
T5 check-dump stage / chunks (or skipped):
eMMC size in sectors:
Boot partition start sector:
Boot image SHA-256 (sector 172032, 31,028 sectors):
Route used and result:
Host OS:
First failed step and its exact output:
```

The boot image SHA-256 is a firmware hash, not a device identifier, so it is safe to publish.
Do not include serials, MAC addresses, Wi-Fi details or hashes of the whole eMMC.
