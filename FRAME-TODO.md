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
  theme-grouped spelling lists, a 1135-word common-word bank for "mot du jour" with a
  deterministic daily picker.
- **Kid views (Clara, Félix).** Shared `kid-view.js` builder: chores with paid task picker,
  holiday countdown, "mot du jour" (5 words/day, different per kid), and the outfit widget.
  Clara's reading panel is phonics-by-sound; Félix's is spelling-by-theme.
- **"Commencer les devoirs" homework review (`homework.js`).** A "Readino"-style slider
  scrubber: a full-screen review cycling through one word at a time (Clara's 30 phonics words /
  Félix's 88 spelling words) with a slider under it. Dragging the slider for Clara sounds out
  each letter as it crosses (phonetic sounds, not alphabet names — `scripts/gen-letter-audio.sh`
  generated the 26 letter clips); for Félix it scrubs the position of the whole-word audio clip
  like a real audio scrubber. "Réécouter" replays, "Suivant"/"Terminer" advances or closes.
- **Adult views (Papa, Maman).** Shared `adult-view.js` builder: that parent's events today
  (including the garbage/recycling reminder when it applies to them).
- **Reading practice — pre-recorded audio, not TTS.** This WebView has no Web Speech API (see
  CLAUDE.md). `reading.js` plays `public/audio/fr/*.mp3` via `<audio>`. **Full audio set
  generated**: all 1135 words across `wordBank`/`felixSpelling`/`claraPhonics` have a clip and a
  `CLIPS` entry (expanded `wordBank` from 585 to 1135 unique words first, to match the original
  ~987+ scope, then generated all 1105 missing clips in one batch via macOS `say -v Amélie` +
  `ffmpeg`, zero failures).
- **"What to wear today" widget (`outfit.js`).** Reads live weather, draws a small cartoon
  Clara/Félix dressed for today's conditions (warm/mild/cold/snow/rain), pinned bottom-left of
  each kid's view.
- **Live weather (`weather.js`).** Open-Meteo, Quispamsis NB, no API key, replacing the mock
  data, refetched every 30 min.
- **Garbage/recycling schedule.** City alternates garbage/recycling every Thursday. Implemented
  in `data.js` as real recurring events: an all-day event on Thursday (correct garbage-vs-
  recycling, anchored to a known real date — Oct 29 2026 was a garbage Thursday — so it never
  drifts) plus a Wednesday reminder the day before. See `GARBAGE_ANCHOR` / `isGarbageWeek()`.
- **Person ids renamed** throughout the demo dataset from upstream's `alex`/`jordan`/`maya`/
  `otto` to `papa`/`maman`/`clara`/`felix` for consistency with the French persona views.
- **Real Google Calendar import, redone.** `data.js`'s `icalEvents` block has 234 real events
  imported from the family's "Lessards" Google Calendar export, today through late 2028: the
  real Judo (Tue/Thu 6–7 PM) + Kinder Judo (Sun 10–11 AM) schedule — all 4 family members, not
  just papa/clara/félix as an earlier synthetic placeholder guessed — baton lessons, real
  birthdays/anniversaries (deduped to one upcoming occurrence each, not repeated every year in
  the expansion window), school closures, appointments, trips, etc. Name-matched to
  Papa/Maman/Clara/Félix where the title mentions them (including "Frank" → Papa, his
  calendar's own shorthand), whole-family fallback otherwise. See `scripts/ical-import.mjs` +
  `scripts/ical-emit.mjs` to re-run this if the calendar changes — **the raw `.ics` file itself
  is never committed** (personal data), only the reusable scripts.
  - The 3 remaining exported calendars (Birthdays, Family, and the user's primary personal
    `agoole@gmail.com` calendar) were checked and brought in narrowly, on request: only
    birthdays/holidays/no-school days, not the full event lists. Found just 2 qualifying
    birthdays (Papa's own, and "Christian Lessard birthday") — everything else in those 3
    calendars was either stale/past, off-topic personal or work content (old recurring work
    meetings, fitness, "Save money to buy crypto"), or already covered by the Lessards import
    above (no-school days). The `agoole@gmail.com` calendar in particular is not family-specific
    and shouldn't be imported wholesale if revisited later.

## Known issues / next steps

- **Félix's real homework word list not yet ingested.** The user is preparing it. When it
  arrives: add the words to `felixSpelling.themes` in `family-data.js`, generate audio for any
  new ones with `scripts/gen-reading-audio.sh "<word>" <slug>` (check for accent-slug collisions
  against the existing 1135-entry map first), add each to `CLIPS` in `js/reading.js`.
- **No RTC battery — clock resets on every power loss.** Breaks anything date-relative. Manual
  fix after every reboot/power event:
  ```sh
  adb shell su -c "date @$(date +%s)"
  ```
  **Real fix, not yet done:** get the frame onto Wi-Fi so Android syncs time via NTP
  automatically on boot. Frame's Wi-Fi state was last seen as "DISCONNECTED" — needs onboarding.
- **Deployed to the physical frame (2026-11-04).** Full rebuild through the homework feature is
  installed and running on the connected KPKUE frame (`4NAY7EM2BE`), clock re-synced. Verified
  on-device: home view renders with live weather/events, Clara's and Félix's homework reviews
  both open and respond to real touchscreen drags (letter-sound highlighting and whole-word
  scrubbing both confirmed via `logcat`'s `MediaFocusControl` audio-session entries). The
  Android SDK needed to rebuild (`aapt2`/`d8`/`apksigner`/build-tools 34, platform 34, JDK 17)
  is already set up at `/usr/local/share/android-commandlinetools` — note this is NOT the
  `/opt/homebrew/...` path `kiosk/build.sh`'s default `ANDROID_HOME` assumes; pass
  `ANDROID_HOME=/usr/local/share/android-commandlinetools` explicitly on this Mac. Clock will
  drift back to its stale default on the next power loss — see the fix above.
- **Adult (Papa/Maman) views are intentionally minimal.** Just today's schedule. No detailed
  spec survived from the lost session beyond "adult-view.js is a shared adult builder" — expand
  if/when there's a concrete idea of what else should be there (chores status for the kids? a
  garbage/recycling callout? weather?).
