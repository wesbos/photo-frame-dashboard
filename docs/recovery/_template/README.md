# <Brand and model>: <variant>

Status: metadata incomplete; no project-hosted download; restoration untested.

Replace this heading and every placeholder before submitting. Keep unknown manifest fields as
`null`. Add a model-level README that links to this variant and to the existing device guide.

## Compatibility

Record the exact model, board revision, SoC, firmware, Android version, sector size, total sectors
and partition layout in `manifest.json`. Say how these were observed and which fields remain
unknown. Different boards or storage layouts need distinct variants.

## Evidence

Link to the existing device guide and public issue/PR. Explain how capture byte counts,
checksums, compression readback, filler checks, static partition re-reads and format integrity
were verified. Distinguish capture/integrity checks from a real restore, and say what was tested
on the source unit versus another unit. Do not include unit identifiers or original whole-disk
hashes.

## Privacy and limitations

Describe excluded identity, personal data, keys and app provisioning without revealing their
values. Cover areas outside userdata and explain the scope of any decoded/structural review.
State the consequences, including missing app activation or calibration. If there is no audited
candidate, say so; do not represent an original backup as safe to share.

## Artifacts and availability

List each candidate filename, purpose, byte sizes, SHA-256 values and exact sector range in
`manifest.json`. State whether its source is official or community-derived. Files remain private
unless their distribution is explicitly approved by the project under its current policy.

`download_url: null` means there is no approved download in this record. Only fill it with a real,
verified URL after approval. Do not add binaries to this directory or turn this record into a
generic flash procedure. Link an existing guarded restore/undo procedure if one is actually
verified for this variant; otherwise state that restoration remains untested.
