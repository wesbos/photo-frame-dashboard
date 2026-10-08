# Research log

## 2026-09-14 — USB and loader access

### Starting condition

150-CAL powered by its wall adapter, stuck at Wi-Fi onboarding with an empty network list. Information icon only reveals its MAC address. There is no accessible Skylight Settings menu. The three physical buttons are Volume +, Power, Volume −. A previous soldered UART attempt did not produce useful retained logs; the old project log only reports a missing `config.ini`.

### USB connection

Initial connections through a CalDigit dock and splitter did not enumerate the calendar. Changing cables alone did not establish access. A direct Mac connection produced an accessory approval dialog for Rockchip. After allowing it, `ioreg` showed a registered `D156`, VID:PID `2207:0007`, with a single MTP interface.

Useful inspection commands on macOS:

```sh
ioreg -p IOUSB -w 0
ioreg -r -n D156 -l -w 0
adb devices -l
```

ADB remained empty through normal reboot. The USB device disappeared and returned as MTP. This does not prove a very brief interface could never appear; it is what the polling monitor observed.

macOS `ptpcamerad` claimed the MTP interface. libmtp 1.1.23 failed with `libusb_claim_interface() = -3`; stopping the service did not establish MTP access, and the service restarted after forced termination. No MTP files were retrieved. libmtp labels the shared `2207:0007` ID as an Anbernic device; this database label is not evidence that the calendar is Anbernic hardware.

A Homebrew installation attempt failed due to an unrelated untrusted MongoDB tap. No tap trust settings were changed. The official Homebrew libmtp bottle was instead downloaded into the ignored diagnostics directory, SHA-256 checked against the formula metadata, and run with local dynamic-library paths.

### UI attempts that did not work

- Two-finger swipe down from the top of the onboarding screen: no effect.
- Power held about two seconds: opens Power off / Restart.
- Two-finger swipe with that menu open: no effect.
- Cold boot with Volume +: user reported no useful change.
- Ethernet hub through USB-C-to-Micro-USB adapter: user reported no connection; host-mode adapter and Ethernet driver compatibility were not established.

The Calendar Max instructions are a lead for a different model, not a verified 150-CAL procedure. Do not repeat the info-icon or ordinary Settings instructions on this onboarding screen.

### Loader mode — successful

Holding **Volume −** while restoring wall power, with USB attached directly, produced a black screen and a new macOS accessory prompt. After approval:

```text
USB download gadget
VID:PID 2207:350a
```

Rockchip's `rkdeveloptool ld` identified it as `Loader` (not MaskROM).

Tool source: `rockchip-linux/rkdeveloptool`, commit `304f073752fd25c854e1bcf05d8e7f925b1f4e14`. The macOS 27 SDK and selected Xcode linker were incompatible; explicitly using Xcode's macOS 26.5 SDK resolved compilation. No system SDK configuration was changed.

Build from the source directory on this Mac:

```sh
printf '#define PACKAGE_VERSION "1.3-local"\n' > config.h
clang++ -std=c++11 -O2 \
  -isysroot /Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX26.5.sdk \
  -I/opt/homebrew/opt/libusb/include/libusb-1.0 \
  main.cpp crc.cpp RKBoot.cpp RKComm.cpp RKDevice.cpp RKImage.cpp RKLog.cpp RKScan.cpp \
  -L/opt/homebrew/opt/libusb/lib -lusb-1.0 -liconv -o rkdeveloptool
```

Read-only queries performed sequentially:

```sh
./rkdeveloptool ld
./rkdeveloptool rci
./rkdeveloptool rfi
./rkdeveloptool rcb
./rkdeveloptool ppt
```

Chip bytes: `38 36 35 33 00 ...` (RK3568-family identifier). Flash: 30,539,776 sectors, tool-reported manufacturer SAMSUNG with value `00`; this is an unverified tool interpretation of the storage manufacturer. Capability bytes: `15 03 00 00 00 00 00 00`.

### Partition map

Primary GPT header and entry-array CRC32 both validated independently with Python. Sector size: 512 bytes.

| Partition | Start sector | Sector count |
| --- | ---: | ---: |
| security | 8192 | 8192 |
| uboot | 16384 | 8192 |
| trust | 24576 | 8192 |
| misc | 32768 | 8192 |
| dtbo | 40960 | 8192 |
| vbmeta | 49152 | 2048 |
| boot | 51200 | 131072 |
| recovery | 182272 | 262144 |
| backup | 444416 | 786432 |
| cache | 1230848 | 786432 |
| metadata | 2017280 | 32768 |
| baseparameter | 2050048 | 2048 |
| super | 2052096 | 4915200 |
| userdata | 6967296 | 23572416 |

### Critical finding: stock loader read limit

The following commands return success and correctly sized files, but **the latter two are not valid complete images**:

```sh
./rkdeveloptool rl 0 34 gpt-primary.img
./rkdeveloptool rl 51200 131072 boot.img
./rkdeveloptool rl 182272 262144 recovery.img
```

`boot.img` contains a valid Android header and the first 7 MiB of its partition, then repeated `0xCC`. `recovery.img` is entirely `0xCC`. The boundary is exactly absolute flash offset 32 MiB (LBA `0x10000`). This matches the documented Rockchip U-Boot rockusb read limit, rather than proving the on-device partitions are corrupt.

The boot header declares Android 12.0.0 / 2022-03, a 27,865,104-byte kernel, 1,255,175-byte ramdisk, 8,857,600-byte second stage, and 254,504-byte DTB. The latter components fall outside the readable area and cannot be inspected from this dump.

A separate `rl 0 65536 first-32MiB.img` read preserved the accessible region. This is a partial storage backup, not a full recovery image. Full backup work is pending a way around the read limit.

The first 7 MiB of the boot partition matched the overlapping independently read region in `first-32MiB.img`. The original invalid full-length files were renamed `boot-INCOMPLETE-CC.img` and `recovery-INCOMPLETE-CC.img`. Complete partitions lying below the cutoff were extracted locally. All nine U-Boot FIT component hashes validate, and its two copies match; see [boot-chain analysis](boot-analysis.md).

### Matching a RAM reader and switching toward MaskROM

The complete 59,392-byte `rk3568_ddr_1056MHz_v1.13.bin` from official Rockchip commit `ddf03c1d80b33dac72a33c4f732fc5849b47ff99` matches the flash backup at offsets `0x8800` and `0x88800`. The same historical configuration pairs this DDR generation with `rk356x_usbplug_v1.14.bin`, with RC4 disabled. Full hashes and pinned URLs are in [loader research](loader-research.md).

Built xrock from commit `50effcef229a7e8ff85fde916e635cdd58fe8c09` locally:

```sh
clang -O2 \
  -isysroot /Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX26.5.sdk \
  -I/opt/homebrew/opt/libusb/include/libusb-1.0 -I. \
  *.c -L/opt/homebrew/opt/libusb/lib -lusb-1.0 -o xrock
```

`rkdeveloptool rd 3` returned `Reset Device OK`. It is a volatile BootROM reset, not a flash upgrade. The original named Loader device disappeared. A new unnamed `2207:350a` device appeared with `bcdUSB=0x0200`, no string descriptors, and no selected USB configuration. Rockchip's scanner uses the low bit of `bcdUSB` to distinguish MaskROM (0) from Loader (1), so these descriptors are consistent with a successful MaskROM transition. However, the node is unregistered/unmatched and `rkdeveloptool ld` cannot open/list it. A renewed macOS accessory approval is the outstanding operational blocker.

Computer Use was unavailable because its Accessibility/Screen Recording permissions were pending. No system accessory security setting was changed. A request was left for the owner to approve the new accessory when back at the computer. **No DDR or USB helper upload has been performed yet.**

`scripts/load-usb-reader.py` was prepared and its default local-only check passed: it verifies both official hashes and the saved stock DDR bytes without opening USB. Actual upload requires `--load`, one configured matching MaskROM device, and an independent `rkdeveloptool ld` confirmation. xrock's return code alone cannot prove success: its upload routine does not propagate every transfer error. The next checks must confirm a responding reader and repeat small flash reads beyond 32 MiB before a full backup.

### Owner approved MaskROM; historical USB helper tested

At approximately 17:20 local time the owner approved the accessory. The MaskROM node gained configuration 1 and `rkdeveloptool ld` confirmed it. Ran `python3 scripts/load-usb-reader.py --load`: stock DDR and component hashes passed, then xrock uploaded the matched DDR and v1.14 USB helper into RAM. No flash-write command was sent.

The device re-enumerated as **USB-MSC**, still `2207:350a` with `bcdUSB=0x0200`, configuration 1. The initial wrapper incorrectly required a Loader descriptor and reported the upload unverified. Independent `rfi` subsequently responded with the expected 30,539,776 sectors. Capability bytes changed from stock `15 03` to `27 03`, further evidence that the helper is running. The descriptor's MaskROM classification alone does not mean the device is still bare BootROM.

Read probes with this helper:

- LBA 65,536, count 8: correct 4,096-byte length, entirely `0xCC`.
- Recovery LBA 182,272, count 8: correct length, entirely `0xCC`.
- LBA 0, count 8: exactly matches the preserved first-32-MiB image.

Thus the historical helper **also restricts reads**. No full backup was attempted, and these high-address samples are not real firmware. Further work is investigating the helper's restriction before any additional RAM upload. The device remains powered in the temporary USB helper.

### Patched RAM helper removes the read restriction

Two independent offline analyses verified that the helper initializer at file offset `0x94b8` sets the shared read limit to sector `0x10000`. Changed only that four-byte instruction from `e9 03 10 32` (`mov w9, #0x10000`) to `09 00 80 12` (`mov w9, #-1`). The original code already uses the latter unlimited value for other storage types. See [loader research](loader-research.md) for relocation and control-flow evidence.

The guarded patch script produced SHA-256 `38f7a4e06c06b75d476b059ea590f07033f3606ff7848189655727f00b6e84c2`. Parent review confirmed equal file lengths and exactly those four changed bytes. Sent another volatile `rd 3`; macOS retained approval this time. Uploaded using `python3 scripts/load-usb-reader.py --patched --load`. Flash-info verification passed.

`python3 scripts/probe-reader.py --prefix patched-reader` passed all checks: two 4-KiB reads at LBA 65,536 were identical non-filler data; two at recovery LBA 182,272 were identical and started `ANDROID!`; LBA 0 matched the preserved first-32-MiB backup. The private probe manifest records sample hashes. This demonstrates removal of the observed limit at the tested addresses, not yet a validated whole-disk backup.

Started the full 30,539,776-sector gzip capture with `scripts/backup-flash.py`, timeout 3,600 seconds. The output remains `.partial` until byte count, reader result, filler screening, and persisted gzip hash verification all pass. No persistent device writes have been sent.

### Complete backup validated

The full capture completed successfully. Raw size is 15,636,365,312 bytes, SHA-256 `040f0a6f2d3a2b8b8da85069bedf1bcb37af26532ed2b7606edc8abb000eda78`. The gzip is 1,283,729,666 bytes, SHA-256 `52345a47a007eee84cfd93b0c27e8b2a276cb9132669e89874a90e1ff5d6bada`. The wrapper verified reader completion, exact byte count, absence of long filler runs, and persisted gzip readback.

Extracted boot, recovery, super, and cache with `scripts/extract-partitions.py`, requiring the full source hash, embedded GPT checks, and exact agreement with the independent probe manifest. All passed. Provisional images analyzed during capture match these validated extractions byte-for-byte. The diagnostic recovery candidate was promoted only after its source recovery hash matched.

Offline system analysis used [lpunpack](https://github.com/unix3dgforce/lpunpack) revision `c59b8f3b069c5a8aa438a049fa4a091177172434`; primary super geometry, metadata header, and table SHA-256 checks were independently verified. Logical partitions are system, system_ext, vendor, vendor_dlkm, odm, odm_dlkm, and product. Homebrew e2fsprogs 1.47.4 `debugfs` read the ext4 images without mounting them or enabling writes. Extracted factory Skylight APK from system_ext for [app analysis](app-analysis.md).

The cache has historical recovery kernel logs and no `/recovery/command` file. The previously saved bootloader-control message is empty. Historical logs identify the RK3566 g10 device-tree configuration, `ssv6x5x` Wi-Fi configuration, and an enumerated SDIO card; these are older boot observations, not a diagnosis of today's scan failure.

### Switched to the bootloader USB identity; renewed macOS approval needed

After backup validation, used `rd 3` to return to MaskROM and uploaded the separately reviewed fastboot-reset helper. It differs from the unrestricted reader only in the reset-6 flag initializer (file `0x98e4`: add 1 becomes add 9). Helper SHA-256 is `f6f1cf8eb5ea6f0af76e41bb15f8d00a72ae416a1cf43d1a9fea2234cb5c1c31`.

The first ordinary `rkdeveloptool rd 6` was rejected by the host CLI before transmission. Built a separate host executable with the single CLI bound change in `scripts/rkdeveloptool-rd6.patch`. `rkdeveloptool-rd6 rd 6` returned `Reset Device OK`. USB changed to **18d1:d00d**, named `USB download gadget`, at about 17:45 local time. macOS reports configuration absent and enumeration state 2; `fastboot devices` returns no accessible device. The new Android-vendor identity requires another accessory approval, which was requested from the owner.

The source-verified diagnostic recovery is ready locally and reproducible with the public builder, but **has not been booted**. No firmware has been flashed. The Wi-Fi root cause and a responding ADB shell remain outstanding. [Next-session instructions](next-session.md) record both the fastboot test and the newly discovered normal-app manufacturer menu.

### Fastboot responded; compact recovery prepared; connection stalled before upload

After the owner approved the new accessory, fastboot responded. `getvar max-download-size` reports `0x04000000` (64 MiB). The original diagnostic recovery is too large, so it was not uploaded. A compact variant removes exactly four unrelated factory-test Wi-Fi modules and 51 Broadcom firmware assets, retaining the SSV module/configuration and all other ramdisk entries except the same three property changes. The guarded public builder produced a 54,349,824-byte image, SHA-256 `117a92184fdf935d68a53d752d596a6e105c033a8ab163258967981710893ff1`. Independent unpacking verified the retained entries and header-declared kernel/resource/DTB components.

A subsequent `fastboot getvar all` reported `secure:yes`, `unlocked:no`, product `evb_rk3568`, and several partition/slot variables, then stopped responding after `snapshot-update-status:get error`. The host query was interrupted after stalling. A new max-download-size query logged USB pipe errors and timed out after 45 seconds. A narrowly targeted libusb USB-connection reset of the sole `18d1:d00d` device also timed out, after which the USB node disappeared. No download or boot command was sent, and the cause of the bootloader stall is not established. Avoid repeating the broad getvar-all query on a future connection.

The owner was asked to restore wall power without holding buttons and try the normal-app manufacturer menu discovered in the validated factory APK. That route can enable ADB and open Android settings without a replacement firmware image. A responding ADB shell and live Wi-Fi diagnosis are still pending.

### References

- [Rockchip rkdeveloptool source](https://github.com/rockchip-linux/rkdeveloptool)
- [Rockchip U-Boot rockusb implementation](https://github.com/rockchip-linux/u-boot/blob/next-dev/drivers/usb/gadget/f_rockusb.c)
- [PINE64's documentation of the same 32 MiB / 0xCC problem](https://pine64.org/documentation/PineNote/_full/)
- [xrock documentation](https://github.com/xboot/xrock)
- [AOSP boot-image unpacker](https://android.googlesource.com/platform/system/tools/mkbootimg/+/refs/heads/main/unpack_bootimg.py)
- [Apple accessory approval](https://support.apple.com/en-us/102282)
- [Firsthand Micro-USB Skylight ADB report, not reproduced on this unit](https://www.reddit.com/r/skylightcalendar/comments/1hya3ha/comment/m6gp4bz/)
- [Calendar Max ADB method, different model](https://github.com/dinewby88/SkylightMaxCalendarADB)

## Live ADB and native scan failure

The owner successfully enabled ADB through the manufacturer menu. Native Android Wi-Fi scans fail outside Skylight; static iw event capture shows scan started followed by scan aborted 1.107 seconds later. Runtime SDIO/module/firmware evidence identifies Broadcom/AP6256, overriding the generic SSV label in device-tree configuration. Wi-Fi disable/enable did not fix it; temporary verbose logging was restored.

A 57,397,248-byte AP6256 diagnostic recovery was uploaded with fastboot boot. Both commands returned OKAY, but recovery did not start and the bootloader continued answering bounded queries. fastboot reboot restored normal Android with ADB enabled. No firmware was flashed. Source and installed-bootloader analysis suggest a download-buffer/kernel-allocation overlap; an alternative RAM image format is being investigated.

## Host fastboot wrapping discovered

A legacy ARM64 multi-image containing the exact factory kernel, exact AP6256 diagnostic ramdisk, and live device tree was built and independently checked. Standard fastboot boot automatically treated it as a raw kernel and wrapped it in an Android boot header (explicit creating boot image output). Consequently that acknowledged transfer did not test the intended legacy image path. The device remained in fastboot and was returned to normal boot. A raw download-and-boot transport is being prepared; this is distinct from flashing a partition.

## Exact raw legacy test and USB hang

The guarded raw fastboot uploader sent the verified 48,423,072-byte legacy image unchanged. The device responded OKAY to the size query, DATA02e2e0a0 to the download request, then OKAY after payload and boot. Recovery ADB did not appear. USB continued listing its previous fastboot identity, but subsequent fastboot max-download-size timed out after20seconds and a raw libusb query timed out on bulkOUT. Descriptor presence alone was insufficient evidence of responsiveness. The exact hang stage remains unknown; normal power-cycle and pstore capture are needed. No flash/erase/unlock operation was sent.

## Normal operation restored after full disconnect

After the owner disconnected both wall power and USB, the device returned as2207:0006 with working ADB and sys.boot_completed=1. The previous power-cycle request is resolved. Post-boot dmesg and identity were saved privately; pstore was empty. No crash trace establishes whether the legacy test stalled in U-Boot or early Linux. Do not repeat speculative RAM images without a serial boot log. Native Wi-Fi scan failure remains unresolved, but normal access and the complete backup are preserved.

## Working USB internet sharing

Installed the official hash-verified gnirehtet Java2.5.1 Android client and started its Mac relay on loopback127.0.0.1:31416. The ADB reverse tunnel connected and the Android VPN became active. A native HTTP probe executed on the calendar received HTTP204 from an external connectivity endpoint, proving actual traffic through the Mac. No root or firmware change was needed. Relay remains running; restart/stop instructions are in usb-internet-sharing.md. Built-inWiFi and onboarding acceptance remain separate unresolved items.
