# KPKUE DP-10B frame — progress notes and next steps

Working notes for the family dashboard running on our KPKUE DP-10B frame. See
[`dashboard/CLAUDE.md`](dashboard/CLAUDE.md) for architecture/conventions; this file tracks
what's done, what's known-broken, and what's next.

## ⚠️ History: why this was rebuilt from scratch on 2026-11-04

A full round of Famille HQ customization (family-data.js, weather.js, reading.js, all 4 persona
views, kid/adult CSS, garbage/recycling schedule, a real Google Calendar import, ~990 generated
audio clips) was built in an earlier session but **done entirely inside that session's temp
scratchpad directory** (`/private/tmp/claude-.../scratchpad/...`) and **never pushed** to the
fork remote. When that session ended, the OS garbage-collected the temp directory and the work
was permanently and unrecoverably lost — confirmed via `git log` on the fork that the branch tip
was still the pre-existing upstream device-profile commit, nothing from that work.

This file and `dashboard/CLAUDE.md` were rebuilt from the previous session's conversation
history (which still had enough detail to reconstruct most of it faithfully) into a proper
checkout at `~/Projects/photo-frame-dashboard`, committed, and pushed immediately. **The repo now
lives there permanently — never in a scratchpad.** See the warning at the top of
`dashboard/CLAUDE.md`.

## Done (as of 2026-11-04 rebuild)

- **Famille HQ rebrand.** Title, sidebar nav in French, 4 persona tabs (Papa/Maman/Clara/Félix)
  plus the original Calendrier/Tâches/Épicerie/Photos/Maison/Agents tabs (French-labeled).
- **Family data model.** `family-data.js`: people config (Clara 6, Félix 8, with persona
  colours), chores/routine/taskMenu, holiday list, Clara's phonics-by-sound groups, Félix's
  theme-grouped spelling lists, a ~900-word common-word bank for "mot du jour" with a
  deterministic daily picker.
- **Kid views (Clara, Félix).** Shared `kid-view.js` builder: chores with paid task picker,
  holiday countdown, "mot du jour" (5 words/day, different per kid), and the outfit widget.
  Clara's reading panel is phonics-by-sound; Félix's is spelling-by-theme.
- **Adult views (Papa, Maman).** Shared `adult-view.js` builder: that parent's events today
  (including the garbage/recycling reminder when it applies to them).
- **Reading practice — pre-recorded audio, not TTS.** This WebView has no Web Speech API (see
  CLAUDE.md). `reading.js` plays `public/audio/fr/*.mp3` via `<audio>`. Currently only Clara's 29
  phonics words have generated clips — **see "Known issues" below, the full set is pending.**
- **"What to wear today" widget (`outfit.js`).** Reads live weather, draws a small cartoon
  Clara/Félix dressed for today's conditions (warm/mild/cold/snow/rain), pinned bottom-left of
  each kid's view.
- **Live weather (`weather.js`).** Open-Meteo, Quispamsis NB, no API key, replacing the mock
  data, refetched every 30 min.
- **Garbage/recycling schedule.** City alternates garbage/recycling every Thursday. Implemented
  in `data.js` as real recurring events: an all-day event on Thursday (correct garbage-vs-
  recycling, anchored to a known real date — Oct 29 2026 was a garbage Thursday — so it never
  drifts) plus a Wednesday reminder the day before. See `GARBAGE_ANCHOR` / `isGarbageWeek()`.
- **Judo schedule.** Tuesday + Thursday 6–7 PM for Papa/Clara/Félix (not Maman), plus Sunday
  10–11 AM "Kinder Judo" for the same three. Currently synthetic/placeholder — see known issues,
  the real recurring schedule from the family's actual calendar needs re-importing.
- **Person ids renamed** throughout the demo dataset from upstream's `alex`/`jordan`/`maya`/
  `otto` to `papa`/`maman`/`clara`/`felix` for consistency with the French persona views.

## Known issues / next steps

- **Reading-practice audio set is incomplete.** Only Clara's ~29 phonics words have generated
  mp3 clips (`dashboard/public/audio/fr/`) and matching `CLIPS` entries in `js/reading.js`. Words
  tapped without a clip silently do nothing (no error, just no sound) — this is intentional so
  the UI stays usable, but it means most of Félix's spelling words and the whole "mot du jour"
  word bank are currently silent. To finish: run `scripts/gen-reading-audio.sh "<word>" <slug>`
  for every remaining word (Félix's ~48 theme words + however much of the ~900-word common bank
  is worth covering), adding each to `CLIPS`. Budget real time for this — it's roughly 1-2
  seconds per word but there are hundreds of them.
- **Real Google Calendar import needs redoing.** The garbage/judo schedule above is real, but
  the rest of `data.js`'s events are still upstream's generic demo placeholders (renamed to our
  family's ids, but not the family's actual calendar). A previous round of work imported ~267
  real events from 3 of the family's 5 exported `.ics` files (Lessards/Family/Birthdays
  calendars) — that import was lost with everything else. Redoing it needs the user to re-export
  and re-share those `.ics` files; see `dashboard/CLAUDE.md`'s "Pipelines" section for the
  conversion rules (future-only, name-matching, DST-safe time conversion via `Date` getters).
- **No RTC battery — clock resets on every power loss.** Breaks anything date-relative. Manual
  fix after every reboot/power event:
  ```sh
  adb shell su -c "date @$(date +%s)"
  ```
  **Real fix, not yet done:** get the frame onto Wi-Fi so Android syncs time via NTP
  automatically on boot. Frame's Wi-Fi state was last seen as "DISCONNECTED" — needs onboarding.
- **Current build has not been pushed to the physical frame.** This rebuild exists only in the
  dev-server preview and on GitHub (`fork add-kpkue-dp-10b`) — the physical KPKUE frame is still
  running whatever was last installed on it, which predates all of this. Deploy via the
  Build/deploy loop in `dashboard/CLAUDE.md` once ready, then re-apply the clock fix.
- **Adult (Papa/Maman) views are intentionally minimal.** Just today's schedule. No detailed
  spec survived from the lost session beyond "adult-view.js is a shared adult builder" — expand
  if/when there's a concrete idea of what else should be there (chores status for the kids? a
  garbage/recycling callout? weather?).
