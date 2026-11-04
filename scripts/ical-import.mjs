// Parses a Google Calendar .ics export into /tmp/ical-out.json, ready for scripts/ical-emit.mjs
// to turn into ev()/allDay() calls for dashboard/js/data.js. See dashboard/CLAUDE.md's
// "Pipelines" section. Needs node-ical, which is NOT a dashboard/package.json dependency (this
// runs standalone, not as part of the app) — install it in a scratch folder first:
//   mkdir -p /tmp/ical-tool && cd /tmp/ical-tool && npm init -y && npm install node-ical
//   node /path/to/scripts/ical-import.mjs /path/to/calendar-export.ics
// Never commit the raw .ics itself — it's personal family data, not app source.
import ical from 'node-ical';
import fs from 'node:fs';

const ICS_PATH = process.argv[2];
if (!ICS_PATH) { console.error('usage: node ical-import.mjs <path-to-ics>'); process.exit(1); }

const data = ical.sync.parseFile(ICS_PATH);

const now = new Date();
const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
const windowEnd = new Date(todayStart);
windowEnd.setFullYear(windowEnd.getFullYear() + 2); // cap expansion — don't need years of recurrence

const NAME_MAP = [
  [/f[ée]lix/i, 'felix'],
  [/clara/i, 'clara'],
  [/papa|fran[cç]ois|frank(?!s bday)/i, 'papa'],
  [/maman/i, 'maman']
];

function cleanTitle(title) {
  // Google Calendar sometimes stuffs a date/location line into SUMMARY itself (with an emoji
  // marker) rather than DESCRIPTION — the app already shows date/time/location separately, so
  // drop everything from the first embedded newline onward.
  return title.split('\n')[0].trim();
}

function peopleFor(title) {
  const matched = new Set();
  for (const [re, id] of NAME_MAP) if (re.test(title)) matched.add(id);
  return matched.size ? [...matched] : ['papa', 'maman', 'clara', 'felix'];
}

function dayOffset(d) {
  const ds = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  return Math.round((ds - todayStart) / 86400000);
}

function hm(d) {
  return String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
}

const out = [];

for (const key in data) {
  const ev = data[key];
  if (ev.type !== 'VEVENT') continue;
  const rawTitle = ev.summary || '(untitled)';
  // Some entries (e.g. birthdays added as a full day in a given timezone) come through as
  // datetype "date-time" rather than the strict iCal all-day "date" form, but still span
  // exactly 24h starting at local midnight — treat those as all-day too.
  const durationMs = ev.end - ev.start;
  const isAllDay = ev.datetype === 'date' || (durationMs === 86400000 && ev.start.getHours() === 0 && ev.start.getMinutes() === 0);

  function pushOccurrence(start, end, isException) {
    if (end < todayStart || start > windowEnd) return;
    const title = cleanTitle(rawTitle);
    const people = peopleFor(title);
    const loc = ev.location || undefined;
    if (isAllDay) {
      const days = Math.max(1, Math.round((end - start) / 86400000));
      out.push({ kind: 'allDay', d: dayOffset(start), days, title, people, loc });
    } else {
      out.push({ kind: 'ev', d: dayOffset(start), s: hm(start), e: hm(end), title, people, loc });
    }
  }

  if (ev.rrule) {
    const dur = ev.end - ev.start;
    const dates = ev.rrule.between(todayStart, windowEnd, true);
    const seen = new Set();
    for (const d of dates) {
      const key2 = d.toISOString().slice(0, 10);
      if (ev.exdate && ev.exdate[d.toISOString().replace(/\.\d+Z$/, '')]) continue;
      seen.add(key2);
      let start = d, end = new Date(+d + dur);
      // per-occurrence override (moved/edited single instance)
      if (ev.recurrences && ev.recurrences[key2]) {
        const r = ev.recurrences[key2];
        start = r.start; end = r.end;
      }
      pushOccurrence(start, end, false);
    }
  } else {
    pushOccurrence(ev.start, ev.end, false);
  }
}

out.sort((a, b) => a.d - b.d || (a.s || '').localeCompare(b.s || ''));

// Annual birthdays/anniversaries (allDay, title matches birthday/bday/anniversary) recur every
// year inside our 2-year expansion window, so the same title shows up twice (a year apart). A
// photo-frame display only needs the nearest upcoming occurrence of each — keep the first
// (soonest) and drop later repeats. Weekly/regular recurring events (Judo, etc.) are untouched
// since they're genuinely distinct occurrences, not duplicates.
const ANNUAL_RE = /birthday|bday|anniversa/i;
const seenTitles = new Set();
const deduped = out.filter((e) => {
  if (e.kind !== 'allDay' || !ANNUAL_RE.test(e.title)) return true;
  if (seenTitles.has(e.title)) return false;
  seenTitles.add(e.title);
  return true;
});

fs.writeFileSync('/tmp/ical-out.json', JSON.stringify(deduped, null, 2));
console.log('parsed', out.length, 'future occurrences,', deduped.length, 'after de-duping repeated annual titles -> /tmp/ical-out.json');
console.log('day offset range:', deduped[0]?.d, 'to', deduped[deduped.length - 1]?.d);
