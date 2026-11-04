# Famille HQ — family dashboard for the KPKUE DP-10B frame

This is a fork of wesbos/photo-frame-dashboard's generic `dashboard/`, customized into a
French-language family dashboard (Papa / Maman / Clara / Félix) running bundled (no server) on a
KPKUE DP-10B Android photo frame.

## ⚠️ Repo location — read this before doing anything else

**Work only inside a durable, permanent checkout of this repo — never inside a Claude Code
session's scratchpad or temp directory.** This exact mistake already destroyed a full round of
work once (see FRAME-TODO.md's "History" section at the top) — an earlier session did all its
work in a path under `/private/tmp/claude-.../scratchpad/...`, never pushed, and the OS garbage
collected that temp directory, permanently losing ~15 JS files, CSS, and 29 generated audio
clips. None of it was recoverable.

The canonical checkout is **`~/Projects/photo-frame-dashboard`** on this Mac. If you find
yourself working anywhere under `/private/tmp`, `/tmp`, or a path containing `scratch-workspaces`
or `scratchpad`, stop and move the work to `~/Projects/photo-frame-dashboard` first. **Commit and
push early and often** — don't wait until a large block of work is "done" to push. A half-working
commit pushed to the branch is infinitely more valuable than a finished one that only exists in a
temp directory.

Remotes: `fork` = `git@github.com:agoole/photo-frame-dashboard.git` (push here — this is the
user's own fork), `upstream` = `git@github.com:wesbos/photo-frame-dashboard.git` (read-only,
never push). Branch: `add-kpkue-dp-10b`.

Package name is still `com.wesbos.homehq` on purpose — renaming it would force an
uninstall/reinstall and lose the frame's saved Home-app setting.

## Architecture

- Vite + vanilla JS (no framework), ES modules, loaded in order by `js/main.js` — **order
  matters**: each module attaches to the shared `window.App` / `window.DATA` / `window.FAMILY`.
  `data.js` and `family-data.js` load first and must not depend on `App` at module-eval time
  (their top-level code runs before `app.js` has executed), only inside function bodies that run
  later at render time. (A previous session hit `ReferenceError: App is not defined` by breaking
  this rule inside a top-level loop — don't repeat it.)
- `js/data.js` (`window.DATA`) — the calendar/chores/shopping/home-control mock data, **but the
  `events` array is real and live**: it's the actual thing the Home/persona views render. Dates
  are relative-day offsets from "today" (`base = new Date()` at load time), not fixed calendar
  dates, via the `ev(dayOffset, 'HH:MM', 'HH:MM', title, people, extra)` / `allDay(dayOffset,
  days, title, people, extra)` helpers. This means the whole file re-derives "today" fresh on
  every page load — there is no persisted event store. Person ids throughout this file are
  `papa` / `maman` / `clara` / `felix` (renamed from upstream's `alex`/`jordan`/`maya`/`otto` —
  if you add a new view or script that references person ids, grep for any leftover old ids
  first, since a hardcoded array like `views/tasks.js`'s old `LANES` constant silently breaks
  with the wrong-but-valid-looking fallback to "Famille" rather than erroring).
- `js/family-data.js` (`window.FAMILY`) — chores/routine config, holidays list, phonics/spelling
  word banks, and the `wordOfDay(personId, count, now)` deterministic daily word picker. Static
  family configuration, not calendar events.
- `js/views/*.js` — one file per screen/persona (`home.js`, `papa.js`, `maman.js`, `clara.js`,
  `felix.js`; `kid-view.js` is the shared Clara/Félix builder, `adult-view.js` the shared
  Papa/Maman builder).
- `js/reading.js` (`window.Reading`) — plays pre-recorded French audio clips for reading
  practice. **Not Web Speech API** — see "No TTS in this WebView" below.
- `js/homework.js` (`window.Homework`) — full-screen "Commencer les devoirs" review, launched
  from a button in `kid-view.js` via `App.sheet` (`.sheet--homework` full-bleed variant). A
  slider scrubber under the current word: for Clara (`mode: 'letters'`) dragging across each
  letter plays that letter's phonetic sound from `public/audio/fr-letters/<letter>.mp3`
  (sounding-out, not the whole word); for Félix (`mode: 'scrub'`) the slider scrubs the
  position of the whole-word clip from `js/reading.js`'s `CLIPS` map, like a real audio
  scrubber. Word lists come from `FAMILY.claraPhonics` / `FAMILY.felixSpelling.themes`
  (flattened), not the daily "mot du jour" picker.
- `js/bus-alarm.js` — `App.soundVolume` (persisted) + a Web Audio beep helper (`App.beep`,
  `BusAlarm.ring`), not an `<audio>` clip.
- `js/outfit.js` (`window.Outfit`) — "what to wear today" widget for the kid views: reads live
  `DATA.weather` and draws a small cartoon Clara/Félix dressed for the weather (5 categories:
  warm/mild/cold/snow/rain). Pinned to the bottom of the left column via `margin-top: auto` in
  `css/views/kid.css`'s `.kd-outfit` rule.
- `js/weather.js` — live weather for Quispamsis, NB via Open-Meteo (no API key), replacing the
  upstream mock `D.weather`, refetched every 30 min.
- `kiosk/` — the Android WebView wrapper app, built without Gradle (`kiosk/build.sh`). See
  `kiosk/README.md` for the generic (upstream) kiosk mechanics: bundled-site mode, boot-into-kiosk,
  navigation gestures, etc. That doc is shared with every other device using this kiosk and isn't
  family-specific — don't duplicate it here, extend it there if the mechanism itself changes.

## Hard-won facts about this specific frame

- **No Web Speech API in the WebView.** This build is Chrome/106.0.5249.126 on Android 8.1.0
  (`DP105F Build/OC`), 32-bit (`armeabi-v7a`). `window.speechSynthesis` and
  `window.SpeechSynthesisUtterance` are both `undefined` — confirmed via live Chrome DevTools
  Protocol introspection (`adb forward tcp:9222 localabstract:webview_devtools_remote_<PID>` +
  `Runtime.evaluate`), not just "no French voice installed." No sideloaded TTS engine fixes this
  because the WebView itself never exposes the JS API to bridge to any engine. **Don't re-attempt
  TTS engine sideloading** — go straight to pre-recorded clips (see `reading.js`).
- **No RTC battery.** The system clock resets to a stale default on every power loss. This
  breaks anything date-relative (holiday countdown, "today" itself, garbage/recycling schedule)
  until fixed. Fix after each reboot:
  ```sh
  adb shell su -c "date @$(date +%s)"
  ```
  This device's toybox `date` has no `-s` flag; `date @<unixtime>` is the correct SET syntax. The
  real fix is Wi-Fi + NTP sync so Android corrects itself automatically — not yet set up on this
  frame (see FRAME-TODO.md).
- **Bundled-APK mode has no server.** `KIOSK_SITE` build serves the dist folder from
  `http://127.0.0.1:8765/` inside the APK itself.
- **`App.isFamily(e)` checks `e.people.length >= D.people.length`** (currently 4) — an event
  tagged with all four people renders in the "whole family" lane/style rather than per-person
  lanes. `ALL` (all 4 ids) triggers family styling, a subset doesn't.

## Pipelines that exist but aren't part of the app's runtime

- **`scripts/gen-reading-audio.sh "<word>" <slug>`** — generates one French audio clip
  (`public/audio/fr/<slug>.mp3`) via macOS `say -v Amélie -r 150` + `ffmpeg`. Then add
  `'<word>': '<slug>'` to the `CLIPS` map in `js/reading.js`. **Watch for accent collisions**: a
  naive slugify of accented words can collide (e.g. "là"/"la", "où"/"ou", "sûr"/"sur" — the accent
  is lost in the slug). Always check for duplicate slug values before generating audio for a new
  word; append `-v2` to disambiguate if a collision is unavoidable. `CLIPS`/the audio folder
  currently cover all 1135 words across `wordBank`/`felixSpelling`/`claraPhonics`. Adding new
  words later (e.g. Félix's real homework list) means regenerating just the delta — don't redo
  the whole set.
- **`scripts/gen-letter-audio.sh`** — generates the 26 French phonetic letter-sound clips
  (`public/audio/fr-letters/<letter>.mp3`) for Clara's letters-mode homework scrubber
  (`homework.js`). Phonetic sounds, not alphabet names: "beu" for B, "keu" for C, not "bé"/"cé".
  Accented letters in a word reuse the base letter's clip (`homework.js` strips the accent
  before looking up the slug).
- **`scripts/ical-import.mjs` + `scripts/ical-emit.mjs`** — parses a Google Calendar `.ics`
  export (via `node-ical`, NOT a `dashboard/package.json` dependency — see the usage comment at
  the top of `ical-import.mjs` for how to install it standalone) into `/tmp/ical-out.json`, then
  emits `ev()`/`allDay()` calls ready to paste into `js/data.js`'s `icalEvents` array. Rules
  baked into the script: only future events (2-year expansion cap); UTC → local time via `Date`
  getters (DST-safe); name-match titles containing Papa/Maman/Félix/Clara (plus "Frank" → Papa,
  this family's own calendar shorthand) to tag that person, whole-family fallback otherwise;
  annual birthdays/anniversaries deduped to their single nearest upcoming occurrence rather than
  repeating every year across the expansion window; long multi-line SUMMARY fields (some Google
  Calendar entries stuff a date/location line into the title itself) trimmed to just the first
  line. **Never commit the raw `.ics` file** — it's personal family data, not app source; only
  the scripts are checked in. Real recurring data from a fresh import should supersede any
  hand-authored synthetic recurring block for the same activity — don't keep both.

## Build / deploy loop

```sh
npm run build                                   # from dashboard/ — emits dist/
# On this Mac the SDK lives at /usr/local/share/android-commandlinetools, NOT the
# /opt/homebrew/... path kiosk/build.sh defaults to — pass ANDROID_HOME explicitly.
# KIOSK_SITE needs an absolute path; a relative one resolves against kiosk/, not dashboard/.
KIOSK_SITE="$(pwd)/dist" ANDROID_HOME=/usr/local/share/android-commandlinetools bash kiosk/build.sh   # from dashboard/
adb install -r kiosk/build/homehq.apk
adb shell am force-stop com.wesbos.homehq && adb shell am start -n com.wesbos.homehq/.MainActivity
```

After every install, re-check the clock (see "No RTC battery" above) before trusting anything
date-relative on screen.

For local iteration without touching the physical frame, `npm run dev` (from `dashboard/`) works
fine — the relative-day `DATA.events` model renders correctly from any machine's local clock. The
repo's `.claude/launch.json`-style dev-server config (if the session you're in uses one) should
point at `~/Projects/photo-frame-dashboard/dashboard`, not a temp path — check this first if
`preview_start` fails with an `ENOENT` on `package.json`.
