# Prompt for a recovery contribution

Copy this into your assistant and fill in the non-sensitive model information. Keep the complete
original backup and all unit-specific details private. This prompt prepares a catalog PR; it
does not authorize publishing firmware or writing to a device.

```text
Help me preserve a private backup of my photo frame and contribute a recovery record to
https://github.com/wesbos/photo-frame-dashboard.

Brand/model: <exact model>
Board/SoC: <if known>
Firmware: <if known>
Host OS: <OS>
Private backup destination: <local folder or existing private storage>

Read the current repository rules, docs/recovery/README.md, and my model's existing device
guide. Check open issues/PRs for the same model and firmware. Do not assume a matching product
name means matching hardware. Keep observations separate from guesses.

Use read-only operations to identify the board, firmware, storage size, sector size and partition
layout. Preserve the complete original backup privately, including readable boot regions where
relevant. Do not flash, erase, reset, repartition, send a RAM payload or change settings without
my explicit authorization for that action. If hardware is unavailable, say so and do not invent
a capture. Prefer containerized tools over installing host dependencies.

Verify byte-exact transport, expected raw lengths, compression readback, filler detection, GPT
or other relevant format checks, and independent re-reads of static regions when possible. Say
whether the device was running; a live capture is not automatically a transactional snapshot.

Treat all dumps as private, including pre-userdata ranges. Inspect vendor storage, encoded or
encrypted bootloader identity records, vendor/OEM provisioning, security/TEE, FRP, cache,
metadata, filesystem journals and deleted remnants. Never expose photos, serials, MACs, CIDs,
device UUIDs, accounts, app licences, keys, Wi-Fi details, tokens, emails or local personal paths.
Do not print secret values. A strings scan without matches is not a sufficient privacy review.

If a separate sanitized candidate can be prepared safely, work only on copies. Preserve required
code/metadata, update affected checksums and verify the exact final artifacts, including decoded
metadata and nested archives/ramdisks when relevant. Do not blindly patch signed, compressed or
encrypted formats. If a component cannot be audited safely, exclude it and explain the effect
on recovery. Privacy sanitization alone does not authorize distribution under this repo's rules.

Add a model directory under docs/recovery/<brand>-<model>/ and a distinct variant for each
board/firmware/storage layout, using docs/recovery/_template/. Keep hardware findings in the
existing device guide and link to it. Include exact compatibility, provenance, artifact sizes,
SHA-256 sums, sector ranges, privacy exclusions, provisioning limitations and verification scope.
Do not include original whole-disk hashes. Use null for unknown or unapproved fields and download
URLs. Mark capture, integrity checks and restoration on another unit separately; never infer
successful recovery from passing checksums.

Submit documentation and metadata only. No dumps, vendor binaries, APKs or personal logs in the
PR. Do not upload or publish firmware. Ask maintainers about any proposed distribution; only
after they approve it can project-owned release assets replace null download URLs. Do not create
fake upstream download links or require a contributor's fork as permanent hosting.

Deliver the private backup receipt, model/variant READMEs, manifest, a sanitized diff and a PR
description with the exact evidence and remaining unknowns. Device restoration and firmware
distribution require their own separate decisions.
```
