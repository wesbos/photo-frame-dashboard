# Recovery and device-tree analysis

Initial analysis used boot/recovery bytes extracted from the completed prefix of an in-progress full-disk gzip capture. The complete backup has since passed gzip readback, raw length/hash checks, and comparison with independent read probes. Boot, recovery, super, and cache extracted from that validated backup match the earlier analysis copies. The recovery candidate's source has therefore been verified. This offline analysis does not establish that the candidate boots successfully.

## Stock recovery behavior

The recovery ramdisk contains `adbd`, `minadbd`, a shell, toybox, recovery, and fastbootd. Its default properties are:

```text
ro.secure=1
ro.adb.secure=1
ro.debuggable=0
persist.sys.usb.config=none
```

The recovery init file defines adbd but marks it disabled. It starts adbd when `sys.usb.config=adb`. The board init file starts a serial console when `ro.debuggable=1`. Configfs USB setup already provides an ADB function and uses VID:PID `18d1:d001`. The init binary contains UDC discovery strings, including `/sys/class/udc` and `sys.usb.controller`.

The corresponding [AOSP Android 12.1 recovery startup code](https://android.googlesource.com/platform/bootable/recovery/+/refs/tags/android-12.1.0_r1/recovery_main.cpp) chooses ADB automatically for a debuggable recovery or unlocked device. [AOSP adbd](https://android.googlesource.com/platform/packages/modules/adb/+/refs/tags/android-12.1.0_r1/daemon/main.cpp) uses `ro.secure` to decide whether to drop privileges, and permits `ro.adb.secure=0` when the build is debuggable or the device is unlocked. These source comparisons support a diagnostic-image hypothesis; they do not prove that the vendor binary behaves identically in every respect.

## Diagnostic candidate

A local, ignored candidate changes exactly three bytes in the uncompressed recovery CPIO:

| Property | Stock | Candidate |
| --- | --- | --- |
| `ro.secure` | `1` | `0` |
| `ro.adb.secure` | `1` | `0` |
| `ro.debuggable` | `0` | `1` |

No init script changes are needed for the source-based hypothesis above. The candidate preserves CPIO entry metadata, all other ramdisk content, and the existing permissive SELinux kernel argument. It recompresses the ramdisk and regenerates the Android boot-image header. The kernel, second-stage resource bundle, concatenated DTBs, and recovery DT overlay were independently unpacked from the candidate and confirmed byte-identical to the source. Header load addresses, board field, OS version, page size, and command line remain unchanged; the ramdisk size, dependent layout offsets, and image ID are recalculated.

The builder is pinned to AOSP `system/tools/mkbootimg` commit `b7c1a63df33e6763d2482bc9d33007f67706d131`, tag `android-12.1.0_r1`. The initial candidate is 111,534,080 bytes. Fastboot subsequently reported a 64 MiB maximum download size, so this full candidate was not uploaded. Building a file does not establish a working boot route.

### Compact candidate for the measured download limit

The first compact profile followed the misleading SSV device-tree label. It removed Broadcom support and is **obsolete for this unit's Wi-Fi diagnosis**; that image was not booted. Fresh ADB evidence identifies the actual SDIO device as `02d0:a9bf`, using bcmdhd, BCM4345 revision 9, and AP6256 firmware.

The corrected `ap6256` profile preserves `bcmdhd.ko`, `fw_bcm43456c5_ag.bin`, `nvram_ap6256.txt`, and `config.txt`. It removes the SSV module, three unused Realtek modules, and 50 other Broadcom firmware files. No external `clm_bcm43456c5_ag.blob` exists in the stock recovery or extracted vendor tree; none was invented or added. The live driver reports ignoring that external file and reports an embedded CLM version.

The corrected candidate is **57,397,248 bytes**, with SHA-256 `e88e7e4a7a37a84cb898ae2b4cb4f4ed9d515ccb4a5a46aad1302347a0db731e`. Its manifest lists all 54 removed paths, lengths, and hashes, along with the retained AP6256 assets. A separate AOSP unpack and CPIO inventory comparison confirmed the exact removals, unchanged retained entry metadata, preserved AP6256 files, and unchanged header-declared non-ramdisk components. Gzip compression is retained; the extracted kernel configuration supports GZIP and LZ4 ramdisks, but not XZ or LZMA. The removals affect only the temporary diagnostic image, not installed firmware or backups.

The source recovery partition also has 22,548,480 bytes beyond the header-declared image components, including 136,652 nonzero bytes and additional device-tree content. This unreferenced partition tail is **omitted** from the candidate; its origin is not established and it may be stale image data. No AVB footer was found. Preservation claims above apply to the declared components, not every non-ramdisk byte in the entire source partition.

Disabling ADB authentication is confined to this diagnostic candidate. It is not a suggested configuration for a normally deployed calendar.

### Reproducing the build

[build-diagnostic-recovery.py](../scripts/build-diagnostic-recovery.py) accepts only the documented source recovery, matching validated extraction manifest, and exact pinned mkbootimg script. It rejects other firmware instead of guessing offsets or applying a generic patch. Download [the pinned AOSP mkbootimg source](https://android.googlesource.com/platform/system/tools/mkbootimg/+/b7c1a63df33e6763d2482bc9d33007f67706d131/mkbootimg.py?format=TEXT), base64-decode the Gitiles response into a local Python file, then run:

```sh
python3 scripts/build-diagnostic-recovery.py \
  --source backups/extracted/recovery.img \
  --mkbootimg diagnostics/tools/aosp-mkbootimg/mkbootimg.py \
  --trim-pcba-modules --trim-broadcom-firmware --wifi-profile ap6256 \
  --output-dir backups/rebuilt-diagnostic-recovery
```

The output directory must be new. The script validates the source, edits the three property bytes, applies the explicitly selected removals, repacks, and independently parses the resulting image to compare components and recompute the Android image ID. Omitting both trimming options reproduces the initial full candidate. Trimming requires the documented exact module/firmware set and rejects an output exceeding the measured 64 MiB limit. The script performs no USB operations. Firmware binaries, intermediate components, and local manifests remain outside Git.

## Device-tree alternatives

The boot header's DTB payload contains two concatenated trees. Both say `Rockchip RK3566 g10 Board`, compatible with `rockchip,g10` and `rockchip,rk3566`, and both specify Wi-Fi chip type `ssv6x5x`. This is more specific than the generic RK3568 U-Boot configuration, but remains software configuration rather than direct silicon or module identification.

The second-stage resource bundle contains `d156-edp.dtb` and `d156-mipi.dtb`. U-Boot strings and ARM64 disassembly show a runtime selection between those display variants:

- `hw_version_select()` combines two ADC-derived values and returns a comparison result.
- The display ID helper references GPIO4_C2 and GPIO4_C3.
- The selector computes `100 × hardware-version-result + display-ID`.
- Values 0, 1, 10, and 11 select `d156-edp.dtb`; other values select `d156-mipi.dtb`.

Saved historical recovery kernel logs in the now-validated cache image report the RK3566 g10 model, DTB index 0, an `ssv6x5x` rfkill configuration, and SDIO enumeration. They also report orange verified-boot state. These labels did not identify the populated Wi-Fi module: fresh ADB inspection subsequently established AP6256/BCM4345 with bcmdhd. This is a concrete example of why device-tree labels and the presence of multiple driver modules must not substitute for actual bus and driver evidence. The current ADC/GPIO selection values have not been read in this offline analysis.
