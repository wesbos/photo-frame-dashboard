/*
 * Standalone backend for the kiosk's calendar page: everything a calendar server would
 * do, done on the frame. It reads each calendar's iCal address (fetched by the app, see
 * LocalContent.java), expands repeating events with ical.js, folds duplicates that sit in
 * several calendars, builds the chore lists, and gets the forecast from Open-Meteo.
 * Chore ticks are kept in the page's localStorage.
 *
 * It needs the global ICAL (ical.js) and an env object:
 *   getConfig()      -> Promise<config>  (/config.json, without the iCal addresses)
 *   fetchFeed(key)   -> Promise<{text, stale}>  (key: opaque feedId from the public config)
 *   fetchJson(url)   -> Promise<object>
 *   store            -> { get(key) -> string|null, set(key, string) }
 *   now()            -> Date (optional)
 */
"use strict";
(function (root) {
  const EVERYONE = new Set(["everyone", "all", "kids", "everybody"]);
  const DAY_MS = 86400000;
  const MAX_OCCURRENCES = 20000;  // per repeating event, a guard against endless rules
  const p2 = n => String(n).padStart(2, "0");

  // Local ISO 8601 with offset, like Python's datetime.isoformat().
  function iso(d) {
    const o = -d.getTimezoneOffset(), a = Math.abs(o);
    return `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())}T${p2(d.getHours())}:` +
      `${p2(d.getMinutes())}:${p2(d.getSeconds())}${o >= 0 ? "+" : "-"}${p2(Math.floor(a / 60))}:${p2(a % 60)}`;
  }
  const ymd = d => `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())}`;
  const midnight = d => new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const addDays = (d, n) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);

  // Dates, floating times and unknown time zones are local wall-clock times.
  function toDate(ICAL, t) {
    const z = t.zone;
    if (t.isDate || !z || z === ICAL.Timezone.localTimezone || z.tzid === "floating") {
      return new Date(t.year, t.month - 1, t.day, t.isDate ? 0 : t.hour, t.isDate ? 0 : t.minute, t.isDate ? 0 : t.second);
    }
    return new Date(t.toUnixTime() * 1000);
  }

  function parseFeed(ICAL, text, calName, start, end) {
    const comp = new ICAL.Component(ICAL.parse(text));
    for (const tz of comp.getAllSubcomponents("vtimezone")) {
      const zone = new ICAL.Timezone(tz);
      if (zone.tzid && !ICAL.TimezoneService.has(zone.tzid)) ICAL.TimezoneService.register(zone);
    }
    const masters = new Map(), loose = [];
    const vevents = comp.getAllSubcomponents("vevent");
    for (const v of vevents) {
      if (!v.hasProperty("recurrence-id")) masters.set(v.getFirstPropertyValue("uid") || Symbol(), new ICAL.Event(v));
    }
    for (const v of vevents) {
      if (!v.hasProperty("recurrence-id")) continue;
      const m = masters.get(v.getFirstPropertyValue("uid"));
      if (m) m.relateException(v); else loose.push(new ICAL.Event(v));
    }
    const out = [];
    const add = (master, item, s, e, allDay) => {
      if (String(item.component.getFirstPropertyValue("status") || "").toUpperCase() === "CANCELLED") return;
      if (!(s < end && (e > start || (+e === +s && s >= start)))) return;
      const rule = master.component.getFirstPropertyValue("rrule");
      out.push({
        calendar: calName,
        uid: String(master.uid || ""),
        repeat: rule && rule.freq ? String(rule.freq).toUpperCase() : null,
        title: String(item.summary || "(no title)"),
        start: iso(s),
        end: iso(e),
        allDay,
        location: String(item.location || ""),
        description: String(item.description || "").slice(0, 1500),
      });
    };
    const single = ev => {
      // No DTEND or DURATION: a timed event has no length, an all-day event lasts the day (RFC 5545).
      add(ev, ev, toDate(ICAL, ev.startDate), toDate(ICAL, ev.endDate), ev.startDate.isDate);
    };
    for (const ev of masters.values()) {
      if (!ev.startDate) continue;
      if (!ev.isRecurring()) { single(ev); continue; }
      const it = ev.iterator();
      let t, n = 0;
      while ((t = it.next()) && n++ < MAX_OCCURRENCES) {
        const det = ev.getOccurrenceDetails(t);
        const s = toDate(ICAL, det.startDate);
        if (toDate(ICAL, t) >= end && s >= end) break;
        add(ev, det.item, s, toDate(ICAL, det.endDate), det.startDate.isDate);
      }
    }
    loose.forEach(single);
    return out;
  }

  const normTitle = t => t.toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");

  // Fold copies of one event that sit in several calendars into one entry that lists
  // every calendar. Same event = same UID and start, or same title, start and end.
  function mergeDuplicates(events, calOrder) {
    const order = new Map(calOrder.map((n, i) => [n, i]));
    const sorted = events.slice().sort((a, b) => (order.get(a.calendar) ?? 99) - (order.get(b.calendar) ?? 99));
    const merged = [], byKey = new Map();
    for (const e of sorted) {
      const keys = [`t|${normTitle(e.title)}|${e.start}|${e.end}`];
      if (e.uid) keys.push(`u|${e.uid}|${e.start}`);
      let hit = keys.map(k => byKey.get(k)).find(Boolean);
      if (!hit) {
        hit = Object.assign({}, e, { calendars: [e.calendar] });
        merged.push(hit);
      } else if (!hit.calendars.includes(e.calendar)) {
        hit.calendars.push(e.calendar);
        for (const f of ["location", "description"]) if (e[f].length > hit[f].length) hit[f] = e[f];
      }
      keys.forEach(k => byKey.set(k, hit));
    }
    return merged;
  }

  function sampleEvents(weekStart, names) {
    let seed = Math.floor(weekStart.getTime() / DAY_MS);
    const rnd = () => ((seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648);
    const pick = a => a[Math.floor(rnd() * a.length)];
    const titles = ["Dentist", "Gym", "Book club", "Groceries", "Soccer practice", "Piano lesson", "Dinner out"];
    const out = [];
    for (let d = 0; d < 7; d++) {
      for (const cal of names) {
        if (rnd() >= 0.55) continue;
        const day = addDays(weekStart, d);
        const s = new Date(day.getFullYear(), day.getMonth(), day.getDate(), pick([8, 9, 10, 12, 14, 16, 18, 19]), pick([0, 30]));
        const e = new Date(s.getTime() + pick([30, 60, 90]) * 60000);
        out.push({ calendar: cal, calendars: [cal], uid: "", title: pick(titles), start: iso(s), end: iso(e),
          allDay: false, location: "", description: "Sample event." });
      }
    }
    return out;
  }

  function create(env) {
    const ICAL = env.ICAL || root.ICAL;
    const now = env.now || (() => new Date());
    let cfg = null, cfgAt = 0, cfgSignature = "", cfgGeneration = 0, configPending = null;
    const feeds = { at: 0, raw: {}, stale: {}, errors: [], pending: null };
    const wx = { at: 0, data: null, key: "" };

    function feedKeys(config) {
      const keys = config.calendars.map(c => [c.feedId, c.name]);
      if (config.hasChores) keys.push([config.choresFeedId, "Chores"]);
      if (keys.some(([id]) => typeof id !== "string" || !id)) throw new Error("calendar identity missing; reload");
      return keys;
    }

    async function config() {
      if (cfg && Date.now() - cfgAt <= 60000) return cfg;
      if (!configPending) {
        configPending = env.getConfig().then(next => {
          const active = new Set(feedKeys(next).map(([id]) => id)), signature = JSON.stringify(next);
          if (signature !== cfgSignature) {
            cfgGeneration++;
            cfgSignature = signature;
            feeds.raw = Object.fromEntries(Object.entries(feeds.raw).filter(([id]) => active.has(id)));
            feeds.at = 0; feeds.errors = []; feeds.stale = {}; feeds.pending = null;
          }
          cfg = next; cfgAt = Date.now();
          return cfg;
        }).finally(() => { configPending = null; });
      }
      return configPending;
    }
    const kids = () => cfg.kids || [];
    const refreshMs = () => (cfg.refreshMinutes || 5) * 60000;

    // A saved config may survive a failed HTTP reply without a page reload. Use
    // native URL digests for both requests and memory; discard older config work.
    async function fetchFeeds() {
      if (Date.now() - feeds.at < refreshMs()) return;
      const generation = cfgGeneration;
      if (feeds.pending && feeds.pending.generation === generation) return feeds.pending.promise;
      const keys = feedKeys(cfg), raw = { ...feeds.raw }, errors = [], stale = {};
      const pending = { generation, promise: null };
      pending.promise = (async () => {
        await Promise.all(keys.map(async ([id, name]) => {
          try {
            const r = await env.fetchFeed(id);
            raw[id] = r.text;
            if (r.stale) { stale[id] = true; errors.push(`${name}: offline, showing the last copy`); }
          } catch (e) {
            errors.push(`${name}: ${e.message || e}`);
          }
        }));
        if (generation !== cfgGeneration) throw new Error("calendar settings changed; retry");
        feeds.raw = raw; feeds.at = Date.now(); feeds.errors = errors; feeds.stale = stale;
      })().finally(() => { if (feeds.pending === pending) feeds.pending = null; });
      feeds.pending = pending;
      return pending.promise;
    }

    function getEvents(weekStart) {
      const end = addDays(weekStart, 7);
      if (!cfg.calendars.length) {
        return { events: sampleEvents(weekStart, ["Parent", "Family", "Kids"]), sample: true, errors: [] };
      }
      let events = [];
      const errors = feeds.errors.slice();
      cfg.calendars.forEach(c => {
        const raw = feeds.raw[c.feedId];
        if (raw == null) return;
        try { events = events.concat(parseFeed(ICAL, raw, c.name, weekStart, end)); }
        catch (e) { errors.push(`${c.name}: can't read the calendar (${e.message || e})`); }
      });
      return { events: mergeDuplicates(events, cfg.calendars.map(c => c.name)), sample: false, errors };
    }

    // "Ana, Ben: Feed the dog" -> [["Ana", "Ben"], "Feed the dog"]; no known prefix = everyone.
    function assignees(title) {
      const all = kids().map(k => k.name), lower = new Map();
      for (const k of kids()) {
        lower.set(k.name.toLowerCase(), k.name);
        for (const a of k.aliases || []) lower.set(a.toLowerCase(), k.name);
      }
      const i = title.indexOf(":");
      if (i >= 0) {
        const who = title.slice(0, i), chore = title.slice(i + 1).trim();
        const names = who.replace(/&/g, ",").replace(/ and /g, ",").split(",").map(n => n.trim().toLowerCase()).filter(Boolean);
        if (names.length && names.every(n => lower.has(n) || EVERYONE.has(n))) {
          if (names.some(n => EVERYONE.has(n))) return [all, chore];
          return [names.map(n => lower.get(n)), chore];
        }
      }
      return [all, title.trim()];
    }

    function loadTicks() {
      try { return JSON.parse(env.store.get("chore-ticks") || "{}") || {}; } catch (e) { return {}; }
    }
    function saveTicks(t) {
      const keep = Object.keys(t).sort().slice(-21);  // ~three weeks of start dates
      env.store.set("chore-ticks", JSON.stringify(Object.fromEntries(keep.map(k => [k, t[k]]))));
    }

    // Weekly chores (repeating weekly) stay up for 7 days from each occurrence and keep
    // their tick for that week; a chore spanning several days works the same way for its
    // span. Everything else shows on its own day and resets daily.
    function getChores() {
      const today = midnight(now()), dayEnd = addDays(today, 1);
      const out = { date: ymd(today), kids: [], configured: !!cfg.hasChores };
      if (!kids().length) return out;
      let found = [];
      if (cfg.hasChores && feeds.raw[cfg.choresFeedId] != null) {
        try { found = parseFeed(ICAL, feeds.raw[cfg.choresFeedId], "Chores", addDays(today, -6), dayEnd); } catch (e) { found = []; }
      }
      const span = e => Math.floor((new Date(e.end) - new Date(e.start)) / DAY_MS);
      const weekly = e => e.repeat === "WEEKLY" || (e.allDay && span(e) >= 2);
      const latest = new Map(), items = [];
      for (const e of found) {
        const s = new Date(e.start), en = new Date(e.end);
        if (e.repeat === "WEEKLY") {
          if (s < dayEnd) {
            const prev = latest.get(e.uid);
            if (!prev || new Date(e.start) > new Date(prev.start)) latest.set(e.uid, e);
          }
        } else if (s < dayEnd && en > today) {
          items.push(e);
        }
      }
      items.push(...latest.values());
      const orderOf = e => { const m = /^\s*order\s*:\s*(\d+)/im.exec(e.description); return m ? +m[1] : 1e6; };
      const sortKey = e => [weekly(e) ? 1 : 0, orderOf(e), e.allDay ? 0 : 1, e.start, assignees(e.title)[1].toLowerCase()];
      items.sort((a, b) => {
        const x = sortKey(a), y = sortKey(b);
        for (let i = 0; i < x.length; i++) if (x[i] !== y[i]) return x[i] < y[i] ? -1 : 1;
        return 0;
      });
      const ticks = loadTicks(), lists = new Map(kids().map(k => [k.name, []]));
      for (const ev of items) {
        const [who, chore] = assignees(ev.title);
        const id = `${ev.uid}|${ev.start}`, done = ticks[ev.start.slice(0, 10)] || {};
        for (const k of who) {
          lists.get(k).push({ id, title: chore, done: `${id}|${k}` in done, weekly: weekly(ev), time: ev.allDay ? null : ev.start });
        }
      }
      out.kids = kids().map(k => ({ name: k.name, color: k.color, chores: lists.get(k.name) }));
      return out;
    }

    async function getWeather() {
      const w = cfg.weather;
      if (!w || w.latitude == null) return null;
      const metric = cfg.units === "metric";
      const key = `${w.latitude},${w.longitude},${metric}`;
      if (wx.data && wx.key === key && Date.now() - wx.at < 30 * 60000) return wx.data;
      const url = "https://api.open-meteo.com/v1/forecast?" +
        `latitude=${encodeURIComponent(w.latitude)}&longitude=${encodeURIComponent(w.longitude)}` +
        "&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m,is_day,relative_humidity_2m" +
        "&hourly=temperature_2m,precipitation_probability,weather_code,wind_speed_10m,is_day" +
        "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset," +
        "wind_speed_10m_max,uv_index_max" +
        (metric ? "&wind_speed_unit=kmh" : "&temperature_unit=fahrenheit&wind_speed_unit=mph") +
        "&timezone=auto&forecast_days=7";
      try {
        wx.data = await env.fetchJson(url); wx.at = Date.now(); wx.key = key;
      } catch (e) { /* keep the last forecast */ }
      return wx.data;
    }

    async function data(week) {
      await config();
      const generation = cfgGeneration;
      await fetchFeeds();
      const weather = week === 0 ? await getWeather() : null;
      if (generation !== cfgGeneration) throw new Error("calendar settings changed; retry");
      const today = midnight(now());
      const weekStart = addDays(today, -today.getDay() + 7 * week);  // Sunday
      const ev = getEvents(weekStart);
      const calendars = {};
      (ev.sample ? ["Parent", "Family", "Kids"].map((n, i) => ({ name: n, color: ["#2f7bf5", "#22a861", "#e8577e"][i] }))
        : cfg.calendars).forEach(c => { calendars[c.name] = { color: c.color }; });
      return {
        now: iso(now()),
        weekStart: ymd(weekStart),
        calendars,
        sample: ev.sample,
        errors: ev.errors,
        events: ev.events.sort((a, b) => (a.allDay === b.allDay ? (a.start < b.start ? -1 : a.start > b.start ? 1 : 0) : a.allDay ? -1 : 1)),
        weather,
        chores: week === 0 ? getChores() : null,
        place: (cfg.weather && cfg.weather.place) || "",
        windUnit: cfg.units === "metric" ? "km/h" : "mph",
        hasChores: !!cfg.hasChores && kids().length > 0,
        setup: cfg.setup || null,
      };
    }

    async function tick(id, kid, done) {
      await config();
      if (!kids().some(k => k.name === kid)) throw new Error("unknown kid");
      const start = id.includes("|") ? id.slice(id.lastIndexOf("|") + 1).slice(0, 10) : "";
      const day = start.length === 10 ? start : ymd(now());
      const t = loadTicks(), d = t[day] || (t[day] = {}), key = `${id}|${kid}`;
      if (done) d[key] = Math.floor(Date.now() / 1000); else delete d[key];
      saveTicks(t);
      return getChores();
    }

    return { data, tick, _parseFeed: (text, name, s, e) => parseFeed(ICAL, text, name, s, e) };
  }

  root.FrameBackend = { create, iso };
})(typeof window !== "undefined" ? window : globalThis);
