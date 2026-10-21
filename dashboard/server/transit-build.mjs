// Turns the (huge) GO Transit GTFS feed into a small schedule file the dashboard can ship:
//   npm run transit-build -- --list ~/Downloads/GO-GTFS.zip     show station codes and line codes
//   npm run transit-build -- ~/Downloads/GO-GTFS.zip            build public/transit/schedule.json
// A station can set "to": "UN" to keep only trains that go on to that station.
// "lines": ["XX"] on a station limits it to those lines (the top-level "lines" is the default for stations without their own).
// "fallbackFor": "AA" hides a station until the named one has no train within the hour (the page then shows this one instead).
// What to keep comes from dashboard/transit.json: { "stations": [{ "code": "UN", "name": "Union" }], "lines": ["LW", "ST"] } (see transit.example.json; your own transit.json is git-ignored)
// "lines" are GO route codes (rail only, see --list); leave it empty to keep every line that serves a station.
// The feed lists one service day per date (no weekly calendar), so the output is grouped into patterns of
// identical days: { dates: ['20261014', …], deps: [[secondsAfterMidnight, line, headsign, tripNumber], …] }.
// Re-run it when the feed runs out (the page says when) — new feeds are at metrolinx.com/en/about-us/open-data.
import { execFileSync } from 'node:child_process';
import { createReadStream, mkdtempSync, readFileSync, writeFileSync, mkdirSync, rmSync } from 'node:fs';
import { createInterface } from 'node:readline';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
const list = args.includes('--list');
const src = args.filter((a) => !a.startsWith('--'))[0];
if (!src) { console.error('usage: npm run transit-build -- [--list] <GO-GTFS.zip or extracted folder>'); process.exit(1); }

let dir = src;
let tmp = null;
if (/\.zip$/i.test(src)) { tmp = mkdtempSync(join(tmpdir(), 'gtfs-')); execFileSync('unzip', ['-q', '-o', src, '-d', tmp]); dir = tmp; }

// Minimal CSV line parser (quoted fields, doubled quotes). The feed starts with a BOM.
function cells(line) {
  const out = []; let cur = '', q = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (q) { if (c === '"') { if (line[i + 1] === '"') { cur += '"'; i++; } else q = false; } else cur += c; }
    else if (c === '"') q = true;
    else if (c === ',') { out.push(cur); cur = ''; }
    else cur += c;
  }
  out.push(cur);
  return out;
}
async function rows(file, each) {
  const rl = createInterface({ input: createReadStream(join(dir, file), 'utf8'), crlfDelay: Infinity });
  let head = null;
  for await (const raw of rl) {
    if (!raw) continue;
    const c = cells(head ? raw : raw.replace(/^﻿/, ''));
    if (!head) { head = c; continue; }
    const o = {}; head.forEach((h, i) => { o[h] = c[i]; });
    each(o);
  }
}

try {
  const routes = new Map(); // route_id -> { code, name, color, rail }
  await rows('routes.txt', (r) => routes.set(r.route_id, { code: r.route_short_name, name: r.route_long_name, color: r.route_color, rail: r.route_type === '2' }));
  const stops = new Map(), where = new Map();
  await rows('stops.txt', (s) => { stops.set(s.stop_id, s.stop_name); where.set(s.stop_id, { lat: +s.stop_lat, lon: +s.stop_lon }); });

  if (list) {
    console.log('Rail lines (use the code in "lines"):');
    [...routes.values()].filter((r) => r.rail).forEach((r) => console.log('  ' + r.code.padEnd(4) + r.name));
    console.log('\nStations / stops (use the code in "stations"):');
    [...stops].filter(([id]) => /^[A-Z]/.test(id)).sort((a, b) => a[1].localeCompare(b[1])).forEach(([id, n]) => console.log('  ' + id.padEnd(5) + n));
    if (tmp) rmSync(tmp, { recursive: true, force: true });
    process.exit(0);
  }

  const cfg = JSON.parse(readFileSync(join(root, 'transit.json'), 'utf8'));
  const stations = (cfg.stations || []).map((s) => ({ code: String(s.code).toUpperCase(), to: s.to ? String(s.to).toUpperCase() : '', fallbackFor: s.fallbackFor ? String(s.fallbackFor).toUpperCase() : '', lines: new Set((s.lines || cfg.lines || []).map((l) => String(l).toUpperCase())), name: s.name || stops.get(String(s.code).toUpperCase()) || s.code }));
  const lines = new Set((cfg.lines || []).map((l) => String(l).toUpperCase()));
  const unknown = stations.flatMap((s) => [s.code, s.to]).filter((c) => c && !stops.has(c));
  if (unknown.length) throw new Error('Unknown station code(s): ' + unknown.join(', ') + ' — run with --list');
  const want = new Set(stations.map((s) => s.code)), dest = new Set(stations.map((s) => s.to).filter(Boolean));

  // trips: keep the ones on a wanted line
  const stationTo = Object.fromEntries(stations.map((s) => [s.code, s.to]));
  const trips = new Map(); // trip_id -> { date, line, head, num }
  await rows('trips.txt', (t) => {
    const r = routes.get(t.route_id);
    if (!r || !r.rail || !stations.some((s) => !s.lines.size || s.lines.has(r.code.toUpperCase()))) return;
    // trip_id looks like 20261127-LW-1040: date, line, trip number
    const num = t.trip_id.slice(t.trip_id.lastIndexOf('-') + 1);
    trips.set(t.trip_id, { date: t.service_id, line: r.code, head: t.trip_headsign.replace(/^[A-Z0-9]+ - /, ''), num });
  });

  // stop_times (80 MB): only rows at a wanted station on a wanted trip
  const byStation = {}; // code -> date -> [[sec, line, head, num]]
  const sec = (t) => { const p = t.split(':'); return +p[0] * 3600 + +p[1] * 60 + +p[2]; };
  const last = new Map(), reach = new Map(), found = []; // reach: trip_id|stop -> stop_sequence at a destination
  const _unused = null; // trip_id -> final stop_sequence; candidate rows (a trip's last stop has no boarding)
  if (want.size) await rows('stop_times.txt', (st) => {
    const t = trips.get(st.trip_id);
    if (!t) return;
    const seq = +st.stop_sequence;
    if (!(last.get(st.trip_id) >= seq)) last.set(st.trip_id, seq);
    if (dest.has(st.stop_id)) reach.set(st.trip_id + '|' + st.stop_id, seq);
    if (want.has(st.stop_id) && st.pickup_type !== '1') found.push([st, t, seq]);
  });
  for (const [st, t, seq] of found) {
    if (seq === last.get(st.trip_id)) continue;
    const mine = stations.find((x) => x.code === st.stop_id);
    if (mine.lines.size && !mine.lines.has(t.line.toUpperCase())) continue;
    const to = stationTo[st.stop_id];
    if (to && !(reach.get(st.trip_id + '|' + to) > seq)) continue; // doesn't go on to the chosen destination
    const days = (byStation[st.stop_id] = byStation[st.stop_id] || {});
    (days[t.date] = days[t.date] || []).push([sec(st.departure_time || st.arrival_time), t.line, t.head, t.num]);
  }

  const out = {
    built: new Date().toISOString(), publisher: 'Metrolinx (Open Government Licence – Ontario)',
    lines: [...routes.values()].filter((r) => r.rail && (!lines.size || lines.has(r.code.toUpperCase()))).map((r) => ({ code: r.code, name: r.name, color: '#' + r.color })),
    stations: stations.map((s) => {
      s = { code: s.code, name: s.name, ...where.get(s.code), to: s.to, fallbackFor: s.fallbackFor, lines: [...s.lines], toName: s.to ? stops.get(s.to).replace(/ GO$/, '') : '' };
      const days = byStation[s.code] || {}, pat = new Map();
      Object.keys(days).sort().forEach((d) => {
        const deps = days[d].sort((a, b) => a[0] - b[0]), key = JSON.stringify(deps);
        if (!pat.has(key)) pat.set(key, { dates: [], deps });
        pat.get(key).dates.push(d);
      });
      return { ...s, patterns: [...pat.values()] };
    })
  };
  const feed = readFileSync(join(dir, 'feed_info.txt'), 'utf8').split(/\r?\n/)[1].split(',');
  out.feedEnd = feed[4]; // YYYYMMDD

  mkdirSync(join(root, 'public/transit'), { recursive: true });
  const file = join(root, 'public/transit/schedule.json');
  writeFileSync(file, JSON.stringify(out));
  console.log('Wrote ' + file + ' — ' + out.stations.map((s) => s.code + ': ' + s.patterns.reduce((n, p) => n + p.dates.length * p.deps.length, 0) + ' departures').join(', ') + '; feed ends ' + out.feedEnd);
} finally {
  if (tmp) rmSync(tmp, { recursive: true, force: true });
}
