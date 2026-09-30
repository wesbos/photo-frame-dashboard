// On-device diagnostics overlay. Enable with ?diag in the URL (remembered) or ?diag=0 to turn off.
(function () {
  'use strict';
  var KEY = 'hq-diag';
  var q = location.search.match(/[?&]diag(=([^&]*))?/);
  try {
    if (q) localStorage.setItem(KEY, q[2] === '0' ? '0' : '1');
    if (localStorage.getItem(KEY) !== '1') return;
  } catch (e) { if (!q || q[2] === '0') return; }

  var S = { down: null, switches: [], frames: [], jank: 0, last: performance.now() };

  function ua() {
    var m = navigator.userAgent.match(/(Firefox|Chrome)\/(\d+)/);
    return (m ? m[1] + ' ' + m[2] : navigator.userAgent.slice(0, 30)) + (/Android ([\d.]+)/.test(navigator.userAgent) ? ' · Android ' + RegExp.$1 : '');
  }

  // Frame timing: rolling 3s window of frame deltas
  function frame(t) {
    var d = t - S.last;
    S.last = t;
    S.frames.push(d);
    if (d > 50) S.jank++;
    if (S.frames.length > 180) S.frames.shift();
    requestAnimationFrame(frame);
  }

  App.on('ready', function () {
    var panel = document.createElement('div');
    panel.className = 'diag';
    App.$('#stage').appendChild(panel);

    // Time from finger down to click (catches the 300ms tap delay)
    App.$('#rail').addEventListener('pointerdown', function (e) { S.down = { t: e.timeStamp, now: performance.now() }; }, true);
    App.$('#rail').addEventListener('click', function (e) {
      if (S.down) S.clickDelay = Math.round(e.timeStamp - S.down.t);
    }, true);

    // Wrap the router: JS render time + time until the next painted frame
    var go = App.go;
    App.go = function (name, opts) {
      var t0 = performance.now();
      var fromTap = S.down && t0 - S.down.now < 1000 ? S.down.now : null;
      go(name, opts);
      var t1 = performance.now();
      document.body.offsetHeight; // force style + layout so it is counted
      var t2 = performance.now();
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          var t3 = performance.now();
          S.switches.unshift({
            view: name, js: t1 - t0, layout: t2 - t1, paint: t3 - t2,
            total: t3 - (fromTap || t0), tap: S.clickDelay
          });
          S.switches.length = Math.min(S.switches.length, 6);
          S.down = null; S.clickDelay = null;
        });
      });
    };

    requestAnimationFrame(frame);

    function f(n) { return n == null ? '–' : Math.round(n); }
    setInterval(function () {
      var fr = S.frames.slice(-90), avg = fr.reduce(function (a, b) { return a + b; }, 0) / (fr.length || 1);
      var stage = App.$('#stage');
      var scale = stage.getBoundingClientRect().width / 1280;
      var imgs = Array.prototype.filter.call(document.images, function (i) { return i.naturalWidth; });
      var mpx = imgs.reduce(function (s, i) { return s + i.naturalWidth * i.naturalHeight; }, 0) / 1e6;
      var mem = performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1048576) + ' MB' : 'n/a';
      panel.innerHTML =
        '<b>DIAG</b> ' + ua() + '<br>' +
        'viewport ' + innerWidth + '×' + innerHeight + ' · dpr ' + devicePixelRatio + ' · scale ' + scale.toFixed(3) + '<br>' +
        'fps ' + (1000 / avg).toFixed(0) + ' · frame ' + avg.toFixed(0) + 'ms · jank>50ms ' + S.jank + '<br>' +
        'dom ' + document.getElementsByTagName('*').length + ' · imgs ' + imgs.length + ' (' + mpx.toFixed(1) + ' MP) · heap ' + mem + '<br>' +
        '<u>view · tap→click · js · layout · paint · TOTAL</u><br>' +
        (S.switches.length ? S.switches.map(function (s) {
          return s.view + ' · ' + f(s.tap) + ' · ' + f(s.js) + ' · ' + f(s.layout) + ' · ' + f(s.paint) + ' · <b>' + f(s.total) + 'ms</b>';
        }).join('<br>') : 'tap a tab to measure');
    }, 500);
  });
})();
