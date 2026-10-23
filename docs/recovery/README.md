# Recovery catalog

An index of model-specific recovery records, so owners can find the right hardware variant,
see what has actually been verified, and contribute information without searching issue threads.
The first record comes from the erased FRAME156 in [issue #209](https://github.com/wesbos/photo-frame-dashboard/issues/209).

This directory contains documentation and artifact metadata. The repository's
[keep-dumps-private rule](../../README.md#rules-we-learned-the-hard-way) still applies:
do not commit or publish dumps, vendor APKs, boot images, personal backups or device credentials.
A record with verified checksums is not approval to distribute its referenced firmware.

## Find your model

| Brand/model | Variants | Current status |
| --- | --- | --- |
| [Pastigio FRAME156](pastigio-frame156/README.md) | RK3326, v2026010414, 61,063,168 sectors | Candidate metadata recorded; restore untested; project distribution undecided |

Start with the [device index](../devices.md) and the model's existing device guide. The same
marketing name or product listing can cover different boards. Never select an image by model
name alone.

## Directory layout

```text
docs/recovery/
  README.md                         catalog, scope and contribution instructions
  PROMPT.md                         copyable prompt for a contribution
  _template/
    README.md                       variant record to copy
    manifest.json                   metadata to fill in
  <brand>-<model>/
    README.md                       model index and link to its device guide
    <soc>-<firmware>-<disk-sectors>/
      README.md                     compatibility, evidence and limitations
      manifest.json                 artifact sizes, hashes, ranges and availability
```

Use lowercase names with hyphens. Keep one directory per brand/model, then one per distinct
board, firmware and storage layout. Include a board slug in the variant name when board
revisions differ. A shared SoC is not enough to combine boards. Record an unknown board revision
as `null`, not as a guess. Use a separate variant for a different eMMC size or partition layout.
Keep device findings in the existing `docs/<device>.md`; link to them rather than copying a
second hardware guide here.

## Contribute a record

1. Check open issues/PRs and this index for an existing model or variant. Update a matching
   record instead of creating a duplicate.
2. Preserve the complete original backup privately. Follow the device guide's read-only capture
   and verification steps. Keep raw diagnostics, whole-disk hashes and per-unit identifiers out
   of the contribution.
3. For a new model, add its model index and a link to its existing device guide. Copy
   [`_template/`](_template/README.md) into the variant directory and fill in both files.
4. State separately what was captured, what passed integrity checks, what privacy review covered,
   and whether restoration was tested on another unit. Use `null` for unknown metadata. Never
   invent a checksum or mark a restore tested because a gzip or GPT check passed.
5. Inspect identity/provisioning outside userdata as well: vendor storage, encoded bootloader
   headers, vendor/OEM files, security/TEE, FRP, cache, metadata, journals and deleted-file remnants.
   The FRAME156 record explains why a pre-userdata cut is not automatically safe. Removing
   provisioned app licences can also prevent the stock app from working after recovery.
6. Submit only the documentation and metadata for review. Leave `download_url` and
   `project_release_url` as `null` unless the project has approved the source and distribution.
   Use the [prompt](PROMPT.md) if you are working with an assistant.
7. Add the model/variant to the indexes. Check local links, JSON syntax, range arithmetic and
   the privacy of the exact diff. Open a PR describing the evidence and the untested parts.

## Where would downloadable files live?

Any distribution of community firmware needs a separate maintainer decision under the current
repository policy. This catalog can also document an official manufacturer's recovery download
when one exists, with its exact checksum and compatibility constraints.

If maintainers choose to distribute an approved artifact themselves, attach it to a release in
**this project**, then set its real URL in the manifest and verify the uploaded hash and size.
Do not commit large binary parts or split images to bypass Git limits. GitHub
[blocks regular Git files over 100 MiB](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github);
[release assets](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)
are separate from Git history. A merged directory does not transfer a contributor's release
assets: a maintainer must publish the approved files in the project first. Until then, a `null`
download URL means no project-hosted download is available. Never use a placeholder URL as a
download command.

The manifests are descriptive records, not instructions for an automated flash writer. A
recipient still needs the exact target checks, approval, restore/undo procedure and readback
verification required by the device guide.
