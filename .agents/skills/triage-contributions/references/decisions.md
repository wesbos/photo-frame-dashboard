# Decisions the owner already made

Follow these without asking again. Add to this file when the owner decides something new, with
the date.

## How the repo is run

- Every comment posted on Wes's behalf must carry the exact bot footer specified in
  [Comment and close](../SKILL.md#6-comment-and-close), including edits to existing bot comments.
  (2026-11-04.)
- The agent may merge, fix, push to `main`, comment, and close PRs and issues on its own, within
  [SKILL.md](../SKILL.md). Escalate the items listed there.
- Merge PRs by merging their commits into `main` (so GitHub marks them merged and keeps authorship),
  then add fix-up commits. Don't squash contributors' work into one of yours.
- Commit messages end with a `Co-Authored-By:` line for the agent, as the repo already does.
- **One guide per device.** Don't merge parallel standalone trees (a second `pf1007l/` folder, a
  second copy of a setup script). Take their findings, close them with thanks, and invite a
  focused PR against the canonical scripts. (2026-10-12: #6, #14 and #42 were handled this way.)

## Safety

- **No writable `ums` builds.** The Route U U-Boot stays read-only in two layers. Writes go through
  guarded on-device U-Boot scripts generated from a verified backup. (2026-10-13: #73.)
- **ADB order:** USB first, then network, then temporary ADB through the vendor connection (T3c),
  and a boot or sector write last. Ideally nobody needs the SD card route.
- **T8 lock-down:** with only temporary ADB, never disable AiMOR; block TCP 7806 and force-stop it
  until there is persistent ADB. Some builds hide disabled apps in Settings. (2026-10-13: #56, #69.)
- One-unit write procedures whose tools aren't in the repo are published as **records, not
  procedures**, with a note saying so.
- A partial backup is allowed in a report, but the report must say it doesn't meet the backup rule.
- Blur location hints and personal details in images rather than rejecting the PR.

## Docs

- `docs/pf1007l-start-here.md` has **one row per firmware** in "Known firmware and units", and one
  "U-Boot settings that fixed ums problems" table. Mark problems **Unsolved** until a report shows a
  fix; then name the fix and the report.
- `docs/devices.md` is **one table**. First column: optional thumbnail `<img … width="120">` in
  the Device cell, then `<br>` and the name. Columns: Device, SoC and Android, ADB out of the box,
  Root, Start with, Where owners bought it.
- Device thumbnails come from the Amazon listing (owner-approved), resized to 240 px, saved as
  `docs/images/devices/<ASIN>.jpg`. Affiliate tag for amazon.com links: `webo080-20`. Amazon links
  the owner gives are confirmed working.
- `docs/community-builds.md` lists **picture frames only** (no e-ink, no Raspberry Pi builds), newest
  first, with neutral descriptions (no assumed pronouns, no curation notes).
- The README stays short: description, TLDR, working frames (thumbnails), community builds teaser,
  which-frame list, dashboard, agent section. Device details go in `docs/devices.md`.
- Write in plain, short sentences. One fact, stated once, in the right place.

## Kiosk app

- Home app is **opt-in** (`--ez home true` enables a disabled activity-alias). Never add
  `CATEGORY_HOME` to the main launcher filter.
- The saved URL comes only from `--es url` and only `http`/`https`. Links opened by other apps
  are shown, not saved.
- Keep the two-finger controls dialog, the navigation service (opt-in via accessibility, re-enabled
  only with an adb-granted `WRITE_SECURE_SETTINGS`), one pending load retry, and the offline screen.

## Scope decisions

- **The dashboard is a demo** for people to build on themselves. Don't add features to it
  (translations, integrations, new screens). Bug fixes and changes that help it run on the frames are
  fine. Docs for features the demo doesn't have are declined too. Suggest a fork plus a Community
  Builds link instead. (2026-10-13: #34, #52, #53.)
- **Private per-frame records:** yes, in the ignored `frames/` folder, as described in
  `docs/frame-records.md`. (2026-10-13: #47.)
- **Self-hosted services** (hubs, admin pages, stored secrets) belong in their contributors' own
  repos. Link them from Community Builds once they exist. Tools that only work with such a
  service go with it. (2026-10-13: #25, #23.)

## Waiting for the owner (as of 2026-10-13)

- Agent skill files from contributors (`skills/…`) were declined (#54, #55): out of scope, and they
  put instructions above the README's safety rules.
