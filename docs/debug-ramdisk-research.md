# Normal-boot debug ramdisk assessment

The diagnostic boot image now boots normal Android with `ro.debuggable=1`, and an explicit `adb root` produces UID 0. This was established after an authorized direct Rockusb boot-partition write with a complete byte-for-byte readback. Earlier fastboot writes returned acknowledgments but did not produce this result; their failure remains unexplained. The successful route persistently modifies the boot partition, while preserving the verified stock kernel, resource/DTBs, and original ramdisk files.

The verified factory boot ramdisk's first-stage `init` contains `/force_debuggable`, `/adb_debug.prop`, `/debug_ramdisk/adb_debug.prop`, and the matching debug-policy paths. The verified system partition's normal second-stage `init` contains `INIT_FORCE_DEBUGGABLE`, the debug-property path, and `orange`. The normal APEX `adbd` contains the runtime `ro.secure` and `service.adb.root` properties, the successful root-restart response, and the production-build denial response. These are distinct from the previously inspected recovery binaries.

Extracted normal binary SHA-256 values:

| Binary | SHA-256 |
| --- | --- |
| `/system/bin/init` | `83f2c2f33409fad8ec220f2fffa5d1b385d224001ce21d0afa0f30eb454f12a7` |
| `/system/apex/com.android.adbd/bin/adbd` | `51c14548938e60ba5dc99ad354250d4158e85d406efe7bb60a94d9dcb949ac75` |

The [Android 12.1 first-stage implementation](https://android.googlesource.com/platform/system/core/+/refs/tags/android-12.1.0_r1/init/first_stage_init.cpp) copies `/adb_debug.prop` into the debug ramdisk and sets `INIT_FORCE_DEBUGGABLE=true` when `/force_debuggable` exists. [Second-stage init](https://android.googlesource.com/platform/system/core/+/refs/tags/android-12.1.0_r1/init/init.cpp) retains that ramdisk only when the environment flag is true and the device-unlocked check passes. The [actual upstream check](https://android.googlesource.com/platform/system/core/+/refs/tags/android-12.1.0_r1/fs_mgr/libfs_avb/util.cpp) compares boot configuration `verifiedbootstate` with `orange`. This is different from assuming fastboot's separate `unlocked` variable must say yes.

[Property initialization](https://android.googlesource.com/platform/system/core/+/refs/tags/android-12.1.0_r1/init/property_service.cpp) reads the debug property file after the ordinary partition property files and before committing the initial property map. Thus this route can override `ro.debuggable` during initialization, unlike trying to change a read-only property after Android is running. The official [debug property file](https://android.googlesource.com/platform/system/core/+/refs/tags/android-12.1.0_r1/rootdir/adb_debug.prop) enables this mechanism for user-build testing.

The tested candidate preserves the verified stock boot kernel, DTBs/resource section, image header fields, and existing ramdisk entries, and adds only:

- An empty root-owned `/force_debuggable` regular file.
- Root-owned `/adb_debug.prop` containing `ro.debuggable=1` and `ro.force.debuggable=1`.

The candidate retains `ro.secure=1` and does not disable ADB authentication; root is requested explicitly with `adb root`. There is no need to copy the official test file's authentication-disabling setting. No substitute init/adbd binary is proposed. Debug-policy substitution would be another change and is not justified without confirming that existing SELinux behavior blocks the intended diagnostics; the observed kernel command line is permissive, but effective runtime enforcement still matters.

The live test now confirms that these facilities work together on this firmware. The production denial message was a runtime debuggability gate, not proof that root support was compiled out. This root access supports further radio diagnosis; it does not by itself establish a Wi-Fi repair.

Rollback means restoring the exact backed-up boot partition. The successful direct route performed a complete stock readback before writing and an exact candidate readback afterward. A previous fastboot stock restoration returned normal Android, but no post-success direct stock restoration is claimed here. No bootloader unlocking or vbmeta change was required for the successful test.


## Concrete offline candidate

[build-debug-boot.py](../scripts/build-debug-boot.py) requires the exact verified stock boot SHA-256 and extraction manifest. It preserves every original CPIO record, including metadata and trailer, and adds only the two files described above. Gzip level 7 keeps the new ramdisk inside the original page-aligned allocation, so no following component moves.

```sh
python3 scripts/build-debug-boot.py \
  --source backups/extracted/boot.img \
  --output-dir diagnostics/debug-boot-candidate
```

The output is a full 67,108,864-byte partition image, SHA-256 `f6e2c27c89a3db7835089fa8037909dc5e7eb62745eb90471fabab58b49821b3`. Compressed ramdisk size changes from 1,255,175 to 1,254,191 bytes within the existing 1,255,424-byte slot. Outside that slot, only the four-byte ramdisk-size field and twenty-byte Android SHA-1 image ID change. A separate parser independently verified both image IDs, all unchanged components, every original CPIO record, exactly two additions, and equality of the entire partition after restoring those allowed byte intervals.

The 28,870,656-byte unreferenced tail includes 136,293 nonzero bytes and is preserved at its original offset. The source has no AVB footer at partition end and no `AVB0` magic. The separately backed-up `vbmeta` has algorithm NONE, zero authentication and auxiliary bytes, zero descriptors, and flag 2 (verification disabled). It therefore contains no boot hash descriptor to invalidate. This does **not** prove that every bootloader validation path accepts a modified image. Preserving the partition tail is not preservation of a cryptographic signature over changed contents. The recomputed Android SHA-1 ID is an integrity field, not an authenticated signature.

The builder itself remains offline and performs no device operations. The candidate changes the boot ramdisk without changing the bootloader or vbmeta. Its exact bytes were subsequently written and verified through the direct route below; this does not validate the earlier fastboot write path.

## Successful direct write with full readback

After the owner authorized continuing, the parent entered Loader using `adb reboot loader`, transitioned through `rkdeveloptool rd 3`, and loaded the reviewed matched DDR/RAM helper variant. Before writing, it read back the entire 64 MiB physical boot partition and matched the verified stock image exactly.

The parent then wrote the unchanged candidate at LBA 51200 and read back 131072 sectors from the same LBA. The full 67,108,864-byte readback matched candidate SHA-256 `f6e2c27c89a3db7835089fa8037909dc5e7eb62745eb90471fabab58b49821b3`. A normal `rd 0` reset booted Android with `ro.debuggable=1`; `adb root` subsequently yielded UID 0. No unlock, erase, or vbmeta operation was required. This is the evidence establishing the direct write and working debug ramdisk.

These sector values are tied to the verified GPT and 512-byte sectors on this device. They are a record of the reviewed test, not generic offsets for another model or firmware. The matched DDR/helper preparation matters; the original limited reader's filler output would not count as readback verification.

## Earlier fastboot attempts

The earlier authorized `fastboot flash boot` attempt reported `Sending boot_a OKAY` and `Writing boot_a OKAY`, but reboot returned to responding fastboot without Android ADB. Restoring the exact stock image through the same host route returned normal Android with `ro.debuggable=0`. A recompression-only control retained the entire original CPIO and independently passed the same header/component checks; it was used to distinguish repacking from the added debug files. Those earlier attempts did not establish root.

Pstore from the first failure contained the prior normal session, not an identifiable candidate kernel boot. The successful direct write of the exact debug candidate now shows that its content can boot on this device; it does not identify why the fastboot path differed. The host's `boot_a` label differs from the GPT's physical `boot` name. Installed U-Boot contains an alias facility, but its specific mapping and the failed fastboot write outcome remain unproven. No alias, signature, gzip, or init failure should be asserted as the cause without further evidence.

### Installed normal-boot hash check

A further bounded disassembly found the actual normal Android image verification path. At link address `0x00a28c70` it selects header offset `0x240`; at `0x00a28c78` it sets a 20-byte comparison length, then compares the computed digest with that header ID at `0x00a28c84`. A mismatch returns `-77`. Its component-loading routine at `0x00a2870c` processes kernel, ramdisk, second/resource, recovery DTBO, and DTB in order. The size accounting adds a four-byte length for each component, matching the standard SHA-1 computation already verified for both source and candidate.

No separate SHA-256 field was identified in this header; its unused space is zero. A direct search of the complete original partition for SHA-1/SHA-256 digests of each whole component, the uncompressed ramdisk, header, and declared image found no extra matching digest records. This bounded search does not rule out an undocumented signature or differently scoped digest, but supplies no evidence for one. The unchanged resource/DTB hashes are separate from the changed Android ramdisk. No replacement candidate was required: the original debug candidate later succeeded through the verified direct write route.
