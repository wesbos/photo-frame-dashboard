// Transit: next GO trains at the stations chosen in transit.json. Planned times from the shipped timetable,
// with live predictions (delays, platforms) overlaid when the server has a Metrolinx key.
(function () {
  'use strict';
  var T = window.Transit, V = { el: null, altOpen: false };
  var ROWS = 7;
  var BUFFER_HOME = 5, BUFFER_ALT = 7; // be on the platform this many minutes before departure (home station / alternate route)
  function bufferFor(st) { return st.fallbackFor ? BUFFER_ALT : BUFFER_HOME; }

  // Time to a station (home -> park -> walk), Mapbox via /api/station-time. One state per station code.
  // Only fetched when the refresh button is tapped (never on opening the tab), so it doesn't spend Mapbox calls.
  var X = {};
  function xs(code) { return X[code] || (X[code] = { data: null, busy: false, error: '', off: false }); }
  function homeStation() { var s = T.schedule; return s && s.stations.filter(function (x) { return x.lat && !x.fallbackFor; })[0]; }
  function altStation() {
    var home = homeStation();
    return home && T.schedule.stations.filter(function (x) { return x.fallbackFor === home.code && x.lat; })[0];
  }
  // Stations with their own column. A fallback station only shows up as the "alternate route" panel (see alternate()).
  function shown() {
    return T.schedule.stations.filter(function (x) { return !x.fallbackFor; });
  }
  function trafficNote(d) {
    var diff = d.typical ? d.minutes - d.typical : null;
    return diff == null ? '' : diff >= 2 ? ' · +' + diff + ' vs usual' : diff <= -2 ? ' · ' + -diff + ' faster than usual' : ' · normal traffic';
  }
  // minutes from now before we must leave for this station (null until the travel time is known)
  function need(st) { var d = xs(st.code).data; return d ? d.total + bufferFor(st) : null; }
  // The first train we can still catch if we leave now.
  function catchable(st, list) {
    var n = need(st);
    return (list || T.board(st, ROWS + 4)).filter(function (r) { return r.ts >= T.now() + n * 60000; })[0];
  }
  function leaveBy(st, r) { return App.fmt.time(new Date(r.ts - need(st) * 60000)); }

  // The travel card for one station (contents only; the caller wraps it).
  function tts(st, compact) {
    var x = xs(st.code), d = x.data;
    var go = '<span class="tr-go' + (x.busy ? ' is-busy' : '') + '" data-tts="' + st.code + '">' + App.icon('refresh', 26) + '</span>';
    var label = '<div class="label">' + App.icon('car', 18) + 'Time to ' + App.esc(st.name.replace(/ GO$/, '')) + '</div>';
    var head = function (up) { return compact ? '' : '<div class="tr-tts-head">' + label + (up ? '<span class="tr-up">' + up + '</span>' : '') + go + '</div>'; };
    var note = function (t) { return '<p class="tr-tts-msg">' + t + '</p>'; };
    if (x.off) return (compact ? '' : '<div class="tr-tts-head">' + label + '</div>') + note('Not set up yet' + (x.missing ? ' · add ' + App.esc(x.missing.join(', ')) : ''));
    if (!d) return head('') + note(x.busy ? 'Checking traffic…' : x.error ? 'Couldn’t check · ' + App.esc(x.error) : 'Tap to check traffic');
    var up = x.busy ? 'Checking…' : x.error ? 'Couldn’t refresh' : 'Updated ' + App.fmt.time(new Date(d.at + T.skew));
    var next = catchable(st);
    return head(up) + '<div class="tr-tts-row"><div class="tr-time"><b class="serif">' + d.total + '</b> min</div>' +
      '<div class="tr-legs"><span><b>' + d.drive.minutes + ' min</b> drive to ' + (d.park ? App.esc(d.park) : 'the station') + App.esc(trafficNote(d.drive)) + '</span>' +
      (d.walk ? '<span><b>' + d.walk.minutes + ' min</b> walk to the platform</span>' : '') +
      '</div></div>' +
      '<div class="tr-leave">' + (next ? 'Leave by <b>' + leaveBy(st, next) + '</b> for the ' + App.fmt.time(new Date(next.ts)) : 'No more trains to catch') + '</div>';
  }
  function repaintNow() { if (App.current === 'transit' && V.el) render(); }
  function loadTts(st) {
    var x = st && xs(st.code);
    if (!st || x.busy || x.off) return;
    x.busy = true; x.error = ''; repaintNow();
    fetch('/api/station-time?code=' + st.code + (st.fallbackFor ? '' : '&home=1') + '&lat=' + st.lat + '&lon=' + st.lon).then(function (r) { return r.json(); }).then(function (d) {
      if (d.configured === false) { x.off = true; x.missing = d.missing; return; }
      if (d.error) { x.error = d.error; return; }
      x.data = d; x.off = false;
    }).catch(function () { x.error = 'server unreachable'; }).then(function () { x.busy = false; repaintNow(); }); // rows depend on the travel time too
  }

  // Alternate route: while the home station has no train within the hour, the fallback station's trains that
  // leave before the home station's service resumes. Tap the tile to open it up with the travel time.
  function alternate() {
    var home = homeStation(), alt = altStation();
    if (!alt) return '';
    var next = T.board(home, 1)[0];
    if (next && next.ts - T.now() <= 60 * 60000) return '';
    var open = V.altOpen;
    var rows = T.board(alt, 12).filter(function (r) { return !next || r.ts < next.ts; }).slice(0, open ? 8 : 5);
    var n = need(alt);
    var body = rows.length ? rows.map(function (r) {
      return row(r, open && n != null && r.ts < T.now() + n * 60000, open && n != null ? 'leave by ' + leaveBy(alt, r) : '');
    }).join('') : '<p class="tr-tts-msg">No ' + App.esc(alt.name) + ' trains in that gap.</p>';
    var x = xs(alt.code);
    return '<section class="tr-alt card' + (open ? ' is-open' : '') + '" data-alt>' +
      '<header class="tr-alt-h"><div class="tr-alt-t"><div class="label">Alternate · ' + App.esc(alt.name.replace(/ GO$/, '')) + ' GO' + (next ? ' · until ' + App.fmt.time(new Date(next.ts)) : '') + '</div></div>' +
      (open ? '<span class="tr-go' + (x.busy ? ' is-busy' : '') + '" data-tts="' + alt.code + '">' + App.icon('refresh', 22) + '</span>' : '') +
      '<span class="tr-alt-x">' + App.icon(open ? 'x' : 'right', 22) + '</span></header>' +
      (open ? '<div class="tr-tts tr-tts--in" data-box="' + alt.code + '">' + tts(alt, true) + '</div>' : '') +
      '<div class="tr-alt-list">' + body + '</div></section>';
  }

  function when(r) {
    var mins = Math.round((r.ts - T.now()) / 60000);
    return mins <= 0 ? 'Now' : mins < 60 ? mins + ' min' : App.fmt.mins(mins);
  }
  function row(r, missed, note) {
    var pill = r.late >= 2 ? '<span class="tr-pill tr-pill--late">' + r.late + ' min late</span>' :
      r.late <= -2 ? '<span class="tr-pill">' + -r.late + ' min early</span>' :
      r.live ? '<span class="tr-pill tr-pill--ok">On time</span>' : '';
    if (/cancel/i.test(r.status)) pill = '<span class="tr-pill tr-pill--late">Cancelled</span>';
    return '<div class="tr-row' + (missed ? ' is-missed' : '') + '" style="--c:' + T.lineColor(r.line) + '">' +
      '<span class="tr-line">' + App.esc(r.line) + '</span>' +
      '<div class="tr-body"><b>' + App.esc(r.head) + '</b><span>' + App.fmt.time(new Date(r.ts)) + (note ? ' · ' + note : '') + (r.platform ? ' · Platform ' + App.esc(r.platform) : '') + '</span></div>' +
      pill + '<span class="tr-when num">' + when(r) + '</span></div>';
  }
  function station(st) {
    var rows = T.board(st, ROWS), err = T.live.stops[st.code] && T.live.stops[st.code].error;
    return '<section class="tr-col"><header class="tr-col-h"><div class="label">' + 'Departing' + (st.toName ? ' to ' + App.esc(st.toName) : '') + '</div><h2 class="serif">' + App.esc(st.name.replace(/ GO$/, '')) + '</h2></header>' +
      '<div class="tr-list">' + (rows.length ? rows.map(function (r) { var n = need(st); return row(r, !st.fallbackFor && n != null && r.ts < T.now() + n * 60000); }).join('') : '<div class="tr-empty serif">' + (dayEnd() ? 'Timetable has ended.' : 'No more trains.') + '</div>') + '</div>' +
      (err ? '<div class="tr-err">Live times unavailable · ' + App.esc(err) + '</div>' : '') + '</section>';
  }
  function dayEnd() { return T.schedule.feedEnd && T.schedule.feedEnd < ymd(new Date(T.now())); }
  function ymd(d) { return d.getFullYear() + ('0' + (d.getMonth() + 1)).slice(-2) + ('0' + d.getDate()).slice(-2); }

  function footer() {
    var L = T.live, s = T.schedule, bits = [];
    if (L.configured === false) bits.push('Planned times only · add METROLINX_KEY for live delays');
    else if (L.error) bits.push('Live times unavailable · ' + App.esc(L.error));
    else if (L.configured) bits.push('Live times on');
    if (s && s.feedEnd) {
      var left = Math.round((new Date(+s.feedEnd.slice(0, 4), +s.feedEnd.slice(4, 6) - 1, +s.feedEnd.slice(6)) - T.now()) / 864e5);
      if (left < 0) bits.push('Timetable ended ' + s.feedEnd + ' — rebuild it');
      else if (left <= 7) bits.push('Timetable ends in ' + left + (left === 1 ? ' day' : ' days'));
    }
    return bits.length ? '<div class="tr-foot">' + bits.join(' · ') + '</div>' : '';
  }

  function message(title, body) {
    return '<div class="tr-msg"><div class="serif">' + title + '</div><p>' + body + '</p></div>';
  }
  function render() {
    var s = T.schedule, inner, head = '';
    if (!s) inner = message(T.error ? 'Timetable not available' : 'Loading…', T.error ? App.esc(T.error) + '. Run <code>npm run transit-build</code> in dashboard/.' : '');
    else if (!s.stations.length) inner = message('No stations chosen yet', 'Add stations and lines to <code>dashboard/transit.json</code>, then run <code>npm run transit-build</code>.');
    else {
      var list = shown(), home = homeStation(), alt = alternate();
      var card = home ? '<button class="tr-tts card" data-box="' + home.code + '" data-tts="' + home.code + '">' + tts(home) + '</button>' : '';
      var cols = '<div class="tr-cols tr-cols--' + Math.min(list.length, 3) + '">' + list.map(station).join('') + '</div>';
      // one station: the card sits beside its trains; several: it goes in the header
      inner = (list.length === 1 && home ? '<div class="tr-side">' + cols + '<div class="tr-aside">' + card + alt + '</div></div>' : cols) + footer();
      if (!(list.length === 1 && home)) head = card + alt;
    }
    V.el.innerHTML = '<div class="transit"><header class="tr-head"><div><div class="label">GO Transit</div><h1 class="serif">Trains</h1></div>' + head + '</header>' + inner + '</div>';
  }

  function onClick(e) {
    var t = e.target.closest('[data-tts]');
    if (t) { // refresh a travel time (inside the open alternate tile the refresh button must not also close it)
      var st = T.schedule.stations.filter(function (x) { return x.code === t.dataset.tts; })[0];
      loadTts(st); e.stopPropagation(); return;
    }
    // closed: tap anywhere on the tile to open it; open: tap its title bar to close it again
    if (e.target.closest(V.altOpen ? '.tr-alt-h' : '[data-alt]')) {
      V.altOpen = !V.altOpen; render();
    }
  }
  function repaint() { if (App.current === 'transit' && V.el) render(); }
  App.on('data', repaint);
  App.on('minute', repaint);

  App.register('transit', {
    minutely: true, // minutes-away counters
    show: function (el) {
      if (!V.wired) { V.wired = true; el.addEventListener('click', onClick); }
      V.el = el; render(); T.watch(true);
    },
    resume: function () { T.watch(true); },
    hide: function () { T.watch(false); }
  });
})();
