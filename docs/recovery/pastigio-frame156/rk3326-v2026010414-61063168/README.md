# FRAME156: RK3326, v2026010414, 61,063,168 sectors

**Candidate metadata only. Restoration to another frame has not been tested, and this project
does not host a download for this record.** Distribution needs a maintainer decision under the
current keep-dumps-private policy; every download URL in [manifest.json](manifest.json) is `null`.

## Compatibility and provenance

The source was the additional macOS unit captured on 2026-10-12 in the
[FRAME156 device guide](../../../pastigio-frame156.md#additional-unit-tested-on-macos-2026-10-12):
Pastigio FRAME156, RK3326, Android 8.1, `FrameO.DP105F.v2026010414`, 512-byte sectors,
61,063,168 sectors total. The exact board revision was not confirmed. Matching a product name
or capacity alone does not establish board compatibility.

The candidate was prepared for [issue #209](https://github.com/wesbos/photo-frame-dashboard/issues/209).
It is community-derived, not an official manufacturer recovery package. Original backups and
their whole-disk hashes are not included.

## Candidate contents

| Artifact | Expanded size | Sector range, inclusive | Scope |
| --- | --- | --- | --- |
| `frame156-pre-userdata-sanitized.img.gz` | 2,873,622,528 bytes | 0 to 5,612,543 | Firmware before userdata, with identity/provisioning exclusions |
| `frame156-boot-chain-sanitized.img.gz` | 37,748,736 bytes | 0 to 73,727 | Primary GPT, sanitized idbloader records, U-Boot, trust, blank misc and resource; insufficient to restore Android alone |
| `gpt-backup.bin` | 16,896 bytes | 61,063,135 to 61,063,167 | Matching regenerated backup GPT; this disk capacity only |

Userdata starts at LBA 5,612,544 and is absent. The manifest records compressed-file hashes and
expanded-image hashes for these candidates, not a hash of the original whole disk.

## Checks and privacy exclusions

The source static partitions were verified by independent reads as documented in the device
guide. The original OEM capture has the documented one-byte journal difference from later reads.
Candidate checks covered gzip readback and exact lengths, both GPT CRCs, unchanged static
firmware ranges, idbloader metadata CRCs and read-only e2fsck of modified/generated filesystems.

Pre-userdata did contain donor identities: encoded idbloader headers, unpartitioned Rockchip
vendor storage and Frameo provisioning in `vendor`. The candidate clears chip/UID records in all
five idbloader copies while preserving DDR/miniloader code, regenerates GPT GUIDs/checksums and
omits vendor storage. Frameo licence/UUID provisioning files and their data blocks were removed;
the old vendor journal was removed, unallocated blocks omitted and a new journal created.

Cache and metadata are fresh empty ext4 filesystems. Misc, backup, security and FRP are blank.
Userdata, personal app archives/media, eMMC boot0/boot1 and RPMB are absent. Review also covered
known donor identity/provisioning values in the exact candidate, decoded idbloader metadata,
allocated firmware files, boot/recovery ramdisks and nested ZIP/APK contents. These checks have
a defined scope, not a general proof about arbitrary encoded binary contents. Maintainer review
is still pending.

## What remains unknown

Android boot, display, Wi-Fi and app activation on another frame are unverified. Removing donor
provisioning can require manufacturer-supported Frameo activation or hardware identity/calibration.
An erased recipient would need its own userdata initialized by the appropriate stock recovery
path, which has not been tested with this candidate. This record is not a flashing procedure.

If maintainers accept distribution, they can publish the reviewed artifacts in a project-owned
release and fill in the manifest's real URLs after verifying hashes and sizes. Merger of this
record alone does not make the images available or approve their distribution.
