// Calendar: Today-by-person lanes (default), 3-day, rolling week, month.
(function () {
  'use strict';
  var D = window.DATA;
  var PX = 72, START = 6, END = 23; // 72px per hour, 6 AM → 11 PM
  var V = { mode: 'day', date: null, el: null, scroll: null };
  var MODES = [['day', 'Today'], ['3day', '3 Day'], ['week', 'Week'], ['month', 'Month']];

  function y(d) { return ((d.getHours() + d.getMinutes() / 60) - START) * PX; }
  function clampTop(e, day) {
    var s = App.dayStart(day);
    var a = e.start < s ? new Date(+s + START * 36e5) : e.start;
    var endOfDay = new Date(+s + END * 36e5);
    var b = e.end > endOfDay ? endOfDay : e.end;
    return { top: Math.max(0, y(a)), h: Math.max(24, y(b) - Math.max(0, y(a)) - 3) };
  }

  // Overlap layout → [{e, col, cols}] (cols capped at 2, extra returned as overflow groups)
  function layout(evs) {
    var out = [], clusters = [], cur = null, curEnd = 0;
    evs.forEach(function (e) {
      if (!cur || +e.start >= curEnd) { cur = []; clusters.push(cur); curEnd = 0; }
      cur.push(e); curEnd = Math.max(curEnd, +e.end);
    });
    clusters.forEach(function (c) {
      var cols = [], placed = [];
      c.forEach(function (e) {
        var i = cols.findIndex(function (end) { return end <= +e.start; });
        if (i < 0) { i = cols.length; cols.push(0); }
        cols[i] = +e.end;
        placed.push({ e: e, col: i });
      });
      var n = cols.length;
      if (n <= 2) placed.forEach(function (p) { out.push({ e: p.e, col: p.col, cols: n }); });
      else {
        var extra = placed.filter(function (p) { return p.col > 0; }).map(function (p) { return p.e; });
        placed.filter(function (p) { return p.col === 0; }).forEach(function (p) { out.push({ e: p.e, col: 0, cols: 2 }); });
        out.push({ more: extra, col: 1, cols: 2, start: new Date(Math.min.apply(null, extra.map(function (e) { return +e.start; }))), end: new Date(Math.max.apply(null, extra.map(function (e) { return +e.end; }))) });
      }
    });
    return out;
  }

  function evBlock(e, style, opts) {
    opts = opts || {};
    var now = App.now();
    var p = opts.color || App.evColor(e);
    var mins = (e.end - e.start) / 60000;
    var cls = 'ev' + (e.end <= now ? ' is-past' : '') + (e.start <= now && e.end > now ? ' is-now' : '') + (mins < 45 ? ' is-short' : '') + (App.isFamily(e) ? ' is-family' : '') + (opts.half ? ' is-half' : '');
    var others = opts.lane ? e.people.filter(function (id) { return id !== opts.lane; }) : (e.people.length > 1 && !App.isFamily(e) ? e.people : []);
    var travel = e.travel ? '<span class="ev-travel" style="height:' + (e.travel * PX / 60) + 'px"></span>' : '';
    return '<button class="' + cls + '" data-ev="' + e.id + '" style="' + App.pstyle(p) + ';' + style + '">' + travel +
      '<span class="ev-title">' + App.esc(e.title) + '</span>' +
      '<span class="ev-meta">' + App.fmt.range(e.start, e.end) + (e.travel ? ' · <b>' + App.icon('car', 16) + 'Leave ' + App.fmt.time(App.leaveBy(e), false) + '</b>' : '') + '</span>' +
      (others.length && !App.isFamily(e) ? '<span class="ev-with">' + App.dots(others, 14) + '</span>' : '') +
      (App.isFamily(e) ? '<span class="ev-with">' + App.dots(D.ALL, 14) + '</span>' : '') +
      '</button>';
  }

  function placeBlocks(list, colorFn, laneId) {
    return layout(list).map(function (it) {
      var w = 100 / it.cols, left = it.col * w;
      if (it.more) {
        var t = y(it.start), h = Math.max(30, y(it.end) - t - 3);
        return '<button class="ev ev--more" data-more="' + it.more.map(function (e) { return e.id; }).join(',') + '" style="top:' + t + 'px;height:' + h + 'px;left:calc(' + left + '% + 2px);width:calc(' + w + '% - 4px)">+' + it.more.length + '<small>more</small></button>';
      }
      var b = clampTop(it.e, V.date);
      return evBlock(it.e, 'top:' + b.top + 'px;height:' + b.h + 'px;left:calc(' + left + '% + 2px);width:calc(' + w + '% - 4px)', { lane: laneId, color: colorFn ? colorFn(it.e) : null, half: it.cols > 1 });
    }).join('');
  }

  function hoursCol() {
    var h = '';
    for (var i = START; i <= END; i++) {
      h += '<div class="hr" style="top:' + (i - START) * PX + 'px"><span>' + (i === 12 ? 'Noon' : (i % 12 || 12) + (i < 12 ? ' AM' : ' PM')) + '</span></div>';
    }
    return h;
  }
  function nowLine(days) {
    var now = App.now(), idx = -1;
    days.forEach(function (d, i) { if (App.sameDay(d, now)) idx = i; });
    if (idx < 0 || now.getHours() < START || now.getHours() >= END) return '';
    return '<div class="now-line" style="top:' + y(now) + 'px"><span class="num">' + App.fmt.time(now, false) + '</span></div>';
  }

  // ------------------------------------------------------------ Today (lanes per person)
  function dayView() {
    var day = V.date;
    var fam = App.timedOn(day).filter(App.isFamily);
    var allDay = App.allDayOn(day);
    var ad = allDay.length ? '<div class="allday"><div class="gutter label">All day</div><div class="allday-grid">' + allDay.map(function (e) {
      var fam2 = App.isFamily(e);
      var idx = D.people.map(function (p) { return p.id; }).indexOf(e.people[0]);
      var col = fam2 ? '1 / -1' : (idx + 1) + ' / span 1';
      var s = App.dayStart(day), spanDays = Math.round((e.end - e.start) / 864e5), dayN = Math.round((s - e.start) / 864e5) + 1;
      return '<button class="ad' + (e.start < s ? ' ad--cont' : '') + '" data-ev="' + e.id + '" style="grid-column:' + col + ';' + App.pstyle(App.evColor(e)) + '">' +
        (e.start < s ? App.icon('left', 16) : '') + App.esc(e.title) + (spanDays > 1 ? ' <small>Day ' + dayN + ' of ' + spanDays + '</small>' : '') + '</button>';
    }).join('') + '</div></div>' : '';
    var grid = '<div class="grid-scroll"><div class="grid" style="height:' + (END - START) * PX + 'px">' +
      '<div class="hours">' + hoursCol() + '</div>' +
      '<div class="lanes">' + D.people.map(function (p) {
        var list = App.timedOn(day, p.id).filter(function (e) { return !App.isFamily(e); });
        return '<div class="lane" style="' + App.pstyle(p) + '">' + placeBlocks(list, null, p.id) + '</div>';
      }).join('') +
      '<div class="lane-fam">' + fam.map(function (e) {
        var b = clampTop(e, day);
        return evBlock(e, 'top:' + b.top + 'px;height:' + b.h + 'px;left:2px;right:2px');
      }).join('') + '</div>' +
      nowLine([day]) + '</div>' +
      '</div></div>';
    var empty = !App.timedOn(day).length ? '<div class="cal-empty serif">Nothing on the calendar.<br><i>A rare, quiet day.</i></div>' : '';
    return '<div class="cal-day">' + ad + grid + empty + '</div>';
  }

  // ------------------------------------------------------------ 3 day
  function threeDay() {
    var days = [0, 1, 2].map(function (i) { return App.addDays(V.date, i); });
    var now = App.now();
    var anyAllDay = days.some(function (d) { return App.allDayOn(d).length; });
    var head = '<div class="lanes-head"><div class="gutter"></div>' + days.map(function (d) {
      var today = App.sameDay(d, now);
      return '<div class="day-head' + (today ? ' is-today' : '') + '"><span class="num">' + d.getDate() + '</span><b>' + App.fmt.rel(d) + '</b><small>' + App.fmt.monthShort(d) + '</small></div>';
    }).join('') + '</div>';
    var ad = '';
    if (anyAllDay) {
      var s0 = App.dayStart(days[0]), s3 = App.addDays(s0, 3);
      var list = App.events().filter(function (e) { return e.allDay && e.start < s3 && e.end > s0; });
      ad = '<div class="allday"><div class="gutter label">All day</div><div class="allday-grid allday-grid--3">' + list.map(function (e) {
        var a = Math.max(0, Math.round((e.start - s0) / 864e5)), b = Math.min(3, Math.round((e.end - s0) / 864e5));
        return '<button class="ad' + (e.start < s0 ? ' ad--cont' : '') + '" data-ev="' + e.id + '" style="grid-column:' + (a + 1) + ' / ' + (b + 1) + ';' + App.pstyle(App.evColor(e)) + '">' +
          (e.start < s0 ? App.icon('left', 16) : '') + App.esc(e.title) + (e.end > s3 ? App.icon('right', 16) : '') + '</button>';
      }).join('') + '</div></div>';
    }
    var grid = '<div class="grid-scroll"><div class="grid" style="height:' + (END - START) * PX + 'px">' +
      '<div class="hours">' + hoursCol() + '</div>' +
      '<div class="lanes lanes--3">' + days.map(function (d) {
        var save = V.date; V.date = d;
        var html = '<div class="lane' + (App.sameDay(d, now) ? ' is-today' : '') + '">' + placeBlocks(App.timedOn(d)) + '</div>';
        V.date = save;
        return html;
      }).join('') + '</div>' +
      nowLine(days).replace('now-line', 'now-line now-line--' + days.findIndex(function (d) { return App.sameDay(d, now); })) +
      '</div></div>';
    return '<div class="cal-day cal-3">' + head + ad + grid + '</div>';
  }

  // ------------------------------------------------------------ rolling week
  function weekView() {
    var now = App.now();
    return '<div class="week">' + [0, 1, 2, 3, 4, 5, 6].map(function (i) {
      var d = App.addDays(V.date, i), today = App.sameDay(d, now);
      var ad = App.allDayOn(d), list = App.timedOn(d), max = 7 - ad.length, more = list.length - max;
      return '<div class="wk-col' + (today ? ' is-today' : '') + '" data-day="' + (+d) + '">' +
        '<div class="wk-head"><b>' + App.fmt.dayShort(d) + '</b><span class="num">' + d.getDate() + '</span></div>' +
        ad.map(function (e) { return '<button class="wk-ad" data-ev="' + e.id + '" style="' + App.pstyle(App.evColor(e)) + '">' + App.esc(e.title) + '</button>'; }).join('') +
        list.slice(0, max).map(function (e) {
          return '<button class="wk-ev' + (e.end <= now ? ' is-past' : '') + '" data-ev="' + e.id + '" style="' + App.pstyle(App.evColor(e)) + '">' +
            '<span class="wk-t">' + App.fmt.time(e.start, false) + '</span><span class="wk-n">' + App.esc(e.title) + '</span></button>';
        }).join('') +
        (more > 0 ? '<button class="wk-more" data-day="' + (+d) + '">+' + more + ' more</button>' : '') +
        (!list.length && !ad.length ? '<div class="wk-free serif"><i>Free</i></div>' : '') +
        '</div>';
    }).join('') + '</div>';
  }

  // ------------------------------------------------------------ month (dots only)
  function monthView() {
    var now = App.now();
    var first = new Date(V.date.getFullYear(), V.date.getMonth(), 1);
    var start = App.addDays(first, -((first.getDay() + 6) % 7)); // Monday start
    var cells = '';
    for (var i = 0; i < 42; i++) {
      var d = App.addDays(start, i);
      var evs = App.allDayOn(d).concat(App.timedOn(d));
      var dots = evs.slice(0, 5).map(function (e) { return '<i style="' + App.pstyle(App.evColor(e)) + '"></i>'; }).join('');
      cells += '<button class="mo-cell' + (d.getMonth() !== first.getMonth() ? ' is-out' : '') + (App.sameDay(d, now) ? ' is-today' : '') + '" data-day="' + (+d) + '">' +
        '<span class="num">' + d.getDate() + '</span><span class="mo-dots">' + dots + (evs.length > 5 ? '<em>+' + (evs.length - 5) + '</em>' : '') + '</span></button>';
    }
    return '<div class="month"><div class="mo-dow">' + ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map(function (d) { return '<span class="label">' + d + '</span>'; }).join('') + '</div>' +
      '<div class="mo-grid">' + cells + '</div></div>';
  }

  // ------------------------------------------------------------ header
  function title() {
    var d = V.date, now = App.now();
    if (V.mode === 'day') return { k: App.fmt.month(d) + ' ' + d.getFullYear() + (App.sameDay(d, now) ? ' · Today' : ' · ' + App.fmt.rel(d)), t: App.fmt.day(d) + ' <i>' + d.getDate() + '</i>' };
    if (V.mode === '3day') { var e = App.addDays(d, 2); return { k: App.fmt.month(d) + ' ' + d.getFullYear(), t: App.fmt.dayShort(d) + ' ' + d.getDate() + ' <i>–</i> ' + App.fmt.dayShort(e) + ' ' + e.getDate() }; }
    if (V.mode === 'week') { var w = App.addDays(d, 6); return { k: 'Next 7 days', t: App.fmt.monthShort(d) + ' ' + d.getDate() + ' <i>–</i> ' + App.fmt.monthShort(w) + ' ' + w.getDate() }; }
    return { k: d.getFullYear(), t: App.fmt.month(d) };
  }
  function header() {
    var t = title();
    var isToday = V.mode === 'month' ? (V.date.getMonth() === App.now().getMonth()) : App.sameDay(V.date, App.now());
    return '<header class="cal-head">' +
      '<button class="icon-btn" data-nav="-1" aria-label="Previous">' + App.icon('left', 24) + '</button>' +
      '<div class="cal-title"><div class="serif">' + t.t + '</div><div class="label">' + t.k + '</div></div>' +
      '<button class="icon-btn" data-nav="1" aria-label="Next">' + App.icon('right', 24) + '</button>' +
      '<button class="btn btn--ghost' + (isToday ? ' is-hidden' : '') + '" data-today>Today</button>' +
      '<div class="seg">' + MODES.map(function (m) { return '<button class="' + (V.mode === m[0] ? 'is-on' : '') + '" data-mode="' + m[0] + '">' + m[1] + '</button>'; }).join('') + '</div>' +
      '<button class="fab" data-add aria-label="Add event">' + App.icon('plus', 26) + '</button>' +
      '</header>';
  }

  function render() {
    var body = { day: dayView, '3day': threeDay, week: weekView, month: monthView }[V.mode]();
    V.el.innerHTML = '<div class="cal cal--' + V.mode + '">' + header() + '<div class="cal-body">' + body + '</div></div>';
    var sc = V.el.querySelector('.grid-scroll');
    if (sc) {
      var now = App.now();
      sc.scrollTop = V.scroll != null ? V.scroll : Math.max(0, y(now) - 170);
      sc.addEventListener('scroll', function () { V.scroll = sc.scrollTop; });
    }
  }

  function nav(dir) {
    if (V.mode === 'month') V.date = new Date(V.date.getFullYear(), V.date.getMonth() + dir, 1);
    else V.date = App.addDays(V.date, dir * ({ day: 1, '3day': 3, week: 7 }[V.mode]));
    V.scroll = null;
    render();
    var b = V.el.querySelector('.cal-body');
    b.classList.add(dir > 0 ? 'slide-l' : 'slide-r');
  }

  function onClick(e) {
    var t;
    if ((t = e.target.closest('[data-ev]'))) return App.eventSheet(App.findEvent(t.dataset.ev));
    if ((t = e.target.closest('[data-more]'))) return moreSheet(t.dataset.more.split(','));
    if ((t = e.target.closest('[data-nav]'))) return nav(+t.dataset.nav);
    if ((t = e.target.closest('[data-today]'))) { V.date = App.dayStart(App.now()); if (V.mode === 'month') V.date.setDate(1); V.scroll = null; return render(); }
    if ((t = e.target.closest('[data-mode]'))) {
      V.mode = t.dataset.mode;
      if (V.mode === 'month') V.date = new Date(V.date.getFullYear(), V.date.getMonth(), 1);
      V.scroll = null;
      return render();
    }
    if ((t = e.target.closest('[data-day]'))) { V.mode = 'day'; V.date = new Date(+t.dataset.day); V.scroll = null; return render(); }
    if ((t = e.target.closest('[data-add]'))) return addSheet();
  }

  // Swipe left/right to change day (the only swipe gesture in the app)
  function swipe(el) {
    var sx, sy, st;
    el.addEventListener('pointerdown', function (e) { sx = e.clientX; sy = e.clientY; st = Date.now(); });
    el.addEventListener('pointerup', function (e) {
      if (sx == null) return;
      var dx = e.clientX - sx, dy = e.clientY - sy;
      sx = null;
      if (Math.abs(dx) > 90 && Math.abs(dy) < 60 && Date.now() - st < 700 && !e.target.closest('.cal-head')) nav(dx < 0 ? 1 : -1);
    });
  }

  // ------------------------------------------------------------ sheets
  App.eventSheet = function (e) {
    if (!e) return;
    var p = App.evColor(e), fam = App.isFamily(e);
    App.sheet(
      '<div class="evs" style="' + App.pstyle(p) + '">' +
      '<div class="evs-band"><div class="label label--on">' + App.fmt.rel(e.start) + ' · ' + App.fmt.month(e.start) + ' ' + e.start.getDate() + '</div>' +
      '<h2 class="serif">' + App.esc(e.title) + '</h2>' +
      '<div class="evs-time num">' + (e.allDay ? 'All day' : App.fmt.range(e.start, e.end)) + '</div></div>' +
      '<div class="evs-body">' +
      (e.travel ? '<div class="evs-row evs-leave">' + App.icon('car', 28) + '<div><b>Leave by ' + App.fmt.time(App.leaveBy(e)) + '</b><span>' + e.travel + ' min drive in current traffic</span></div></div>' : '') +
      (e.loc ? '<div class="evs-row">' + App.icon('pin', 28) + '<div><b>' + App.esc(e.loc) + '</b><span>Tap to send directions to phone</span></div></div>' : '') +
      '<div class="evs-row">' + App.icon('person', 28) + '<div class="evs-people">' + (fam ? D.people : e.people.map(App.person)).map(function (x) {
        return '<span class="chip" style="' + App.pstyle(x) + '">' + App.avatar(x, 32) + x.name + '</span>';
      }).join('') + '</div></div>' +
      (e.notes ? '<div class="evs-notes serif">“' + App.esc(e.notes) + '”</div>' : '') +
      '</div></div>', { cls: 'sheet--event' });
  };

  function moreSheet(ids) {
    var list = ids.map(App.findEvent).filter(Boolean);
    App.sheet('<div class="sheet-pad"><div class="label">Overlapping</div><h2 class="serif sheet-h">' + list.length + ' more events</h2>' +
      '<div class="more-list">' + list.map(function (e) {
        return '<button class="more-row" data-ev="' + e.id + '" style="' + App.pstyle(App.evColor(e)) + '"><i></i><b>' + App.esc(e.title) + '</b><span>' + App.fmt.range(e.start, e.end) + '</span></button>';
      }).join('') + '</div></div>', {
      onMount: function (s) { s.addEventListener('click', function (ev) { var t = ev.target.closest('[data-ev]'); if (t) App.eventSheet(App.findEvent(t.dataset.ev)); }); }
    });
  }

  function addSheet() {
    var now = App.now();
    var st = { who: [], day: 0, time: '15:30', dur: 60, title: '' };
    var days = [0, 1, 2, 3, 4];
    var times = [['08:00', '8 AM'], ['12:00', 'Noon'], ['15:30', '3:30 PM'], ['16:30', '4:30 PM'], ['18:00', '6 PM'], ['19:30', '7:30 PM']];
    var ideas = ['Soccer', 'Playdate', 'Dentist', 'Dinner out', 'Swim', 'Birthday party'];
    App.sheet(
      '<div class="sheet-pad add">' +
      '<div class="label">New event</div>' +
      '<input class="big-input serif" placeholder="What’s happening?" data-f="title">' +
      '<div class="chips">' + ideas.map(function (i) { return '<button class="chip chip--ghost" data-idea="' + i + '">' + i + '</button>'; }).join('') + '</div>' +
      '<div class="label">Who</div><div class="add-who">' + D.people.map(function (p) {
        return '<button class="who-btn" data-who="' + p.id + '" style="' + App.pstyle(p) + '">' + App.avatar(p, 56) + '<span>' + p.name + '</span></button>';
      }).join('') + '<button class="who-btn" data-who="all" style="' + App.pstyle(D.family) + '">' + App.avatar(D.family, 56) + '<span>Everyone</span></button></div>' +
      '<div class="add-row"><div><div class="label">When</div><div class="chips">' + days.map(function (i) {
        var d = App.addDays(now, i);
        return '<button class="chip' + (i === 0 ? ' is-on' : '') + '" data-dayi="' + i + '">' + (i < 2 ? App.fmt.rel(d) : App.fmt.dayShort(d) + ' ' + d.getDate()) + '</button>';
      }).join('') + '</div></div></div>' +
      '<div class="add-row"><div><div class="label">Time</div><div class="chips">' + times.map(function (t) {
        return '<button class="chip' + (t[0] === st.time ? ' is-on' : '') + '" data-time="' + t[0] + '">' + t[1] + '</button>';
      }).join('') + '</div></div>' +
      '<div><div class="label">Length</div><div class="chips">' + [[30, '30m'], [60, '1h'], [120, '2h']].map(function (t) {
        return '<button class="chip' + (t[0] === st.dur ? ' is-on' : '') + '" data-dur="' + t[0] + '">' + t[1] + '</button>';
      }).join('') + '</div></div></div>' +
      '<div class="sheet-actions"><button class="btn btn--ghost" data-close>Cancel</button><button class="btn btn--solid" data-save>Add to calendar</button></div>' +
      '</div>', {
      cls: 'sheet--wide',
      onMount: function (s, close) {
        var input = s.querySelector('[data-f=title]');
        s.addEventListener('click', function (ev) {
          var t = ev.target.closest('button');
          if (!t) return;
          if (t.dataset.idea) { input.value = t.dataset.idea; }
          if (t.dataset.who) {
            if (t.dataset.who === 'all') st.who = st.who.length === 4 ? [] : D.ALL.slice();
            else { var i = st.who.indexOf(t.dataset.who); if (i > -1) st.who.splice(i, 1); else st.who.push(t.dataset.who); }
            App.$$('[data-who]', s).forEach(function (b) {
              b.classList.toggle('is-on', b.dataset.who === 'all' ? st.who.length === 4 : st.who.indexOf(b.dataset.who) > -1);
            });
          }
          ['dayi', 'time', 'dur'].forEach(function (k) {
            if (t.dataset[k] != null) {
              App.$$('[data-' + k + ']', s).forEach(function (b) { b.classList.toggle('is-on', b === t); });
              if (k === 'dayi') st.day = +t.dataset.dayi; else if (k === 'dur') st.dur = +t.dataset.dur; else st.time = t.dataset.time;
            }
          });
          if (t.hasAttribute('data-save')) {
            var title = input.value.trim() || 'New event';
            var who = st.who.length ? st.who.slice() : ['jordan'];
            var start = App.addDays(App.dayStart(now), st.day), p = st.time.split(':');
            start.setHours(+p[0], +p[1]);
            var e = { id: D._eid(), title: title, people: who, start: start, end: new Date(+start + st.dur * 60000) };
            D.events.push(e);
            close();
            V.date = App.dayStart(start); V.mode = V.mode === 'month' ? 'day' : V.mode; V.scroll = null;
            render();
            App.emit('data');
            App.toast('Added <b>' + App.esc(title) + '</b> · ' + App.fmt.rel(start) + ' ' + App.fmt.time(start), {
              icon: 'calendar', undo: function () { D.events.splice(D.events.indexOf(e), 1); render(); App.emit('data'); }
            });
          }
        });
      }
    });
  }

  App.register('calendar', {
    show: function (el, opts) {
      if (!V.el) {
        V.el = el;
        el.addEventListener('click', onClick);
        swipe(el);
      }
      if (!V.date) V.date = App.dayStart(App.now());
      if (!opts.rerender) V.scroll = null;
      render();
    }
  });
  App.on('minute', function () {
    if (App.current !== 'calendar') return;
    var line = V.el.querySelector('.now-line');
    var now = App.now();
    if (line) { line.style.top = y(now) + 'px'; line.querySelector('span').textContent = App.fmt.time(now, false); }
  });
  App.on('time', function () { V.date = App.dayStart(App.now()); V.scroll = null; });
})();
