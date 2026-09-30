// Home control: status summary, scenes, rooms of tiles, climate, cameras, media.
(function () {
  'use strict';
  var D = window.DATA;
  var V = { el: null, pending: {}, scene: null, camTimer: null, camAge: 4 };

  function dev(id) { return D.devices.filter(function (d) { return d.id === id; })[0]; }

  // Optimistic device update: flip immediately, confirm (or revert) shortly after.
  App.setDevice = function (id, patch, opts) {
    var d = dev(id), before = {};
    Object.keys(patch).forEach(function (k) { before[k] = d[k]; d[k] = patch[k]; });
    V.pending[id] = true;
    paint();
    App.emit('data');
    setTimeout(function () {
      delete V.pending[id];
      if (d.flaky && !(opts && opts.silent)) {
        Object.keys(before).forEach(function (k) { d[k] = before[k]; });
        App.toast('Couldn’t reach <b>' + d.name + '</b> · it may be offline', { tone: 'error', icon: 'bolt' });
      }
      paint();
      App.emit('data');
    }, d.flaky ? 2600 : 600);
  };

  // ------------------------------------------------------------ tiles
  function tile(d) {
    var pend = V.pending[d.id] ? '<i class="pend"></i>' : '';
    if (d.type === 'light') {
      return '<div class="tile tile--light' + (d.on ? ' is-on' : '') + '" data-dev="' + d.id + '" style="--lvl:' + (d.on ? d.level : 0) + '%">' +
        '<span class="tile-fill"></span>' + pend +
        '<span class="tile-icon">' + App.icon('bulb', 28) + '</span>' +
        '<span class="tile-name">' + d.name + '</span>' +
        '<span class="tile-state num">' + (d.on ? d.level + '%' : 'Off') + '</span></div>';
    }
    if (d.type === 'blind') {
      return '<div class="tile tile--blind' + (d.pos > 0 ? ' is-on' : '') + '" data-dev="' + d.id + '" style="--lvl:' + d.pos + '%">' +
        '<span class="tile-fill"></span>' + pend +
        '<span class="tile-icon">' + App.icon('blinds', 28) + '</span>' +
        '<span class="tile-name">' + d.name + '</span>' +
        '<span class="tile-state num">' + (d.pos === 0 ? 'Closed' : d.pos === 100 ? 'Open' : d.pos + '% open') + '</span></div>';
    }
    if (d.type === 'lock') {
      return '<div class="tile tile--lock' + (d.locked ? '' : ' is-warn') + '" data-dev="' + d.id + '">' + pend +
        '<span class="tile-icon">' + App.icon(d.locked ? 'lock' : 'unlock', 28) + '</span>' +
        '<span class="tile-name">' + d.name + '</span>' +
        '<span class="tile-state">' + (d.locked ? 'Locked<small>Hold to unlock</small>' : 'Unlocked<small>Tap to lock</small>') + '</span>' +
        '<svg class="hold-ring" viewBox="0 0 40 40"><circle cx="20" cy="20" r="17"/></svg></div>';
    }
    if (d.type === 'garage') {
      var label = { closed: 'Closed', open: 'Open', opening: 'Opening…', closing: 'Closing…' }[d.state];
      return '<div class="tile tile--garage' + (d.state !== 'closed' ? ' is-warn' : '') + (/ing$/.test(d.state) ? ' is-moving' : '') + '" data-dev="' + d.id + '">' + pend +
        '<span class="tile-icon">' + App.icon('garage', 28) + '</span>' +
        '<span class="tile-name">' + d.name + '</span>' +
        '<span class="tile-state">' + label + '</span></div>';
    }
    return '';
  }

  function summary() {
    var lights = D.devices.filter(function (d) { return d.type === 'light' && d.on; });
    var unlocked = D.devices.filter(function (d) { return d.type === 'lock' && !d.locked; });
    var garage = dev('g-door');
    var secure = !unlocked.length && garage.state === 'closed';
    var c = D.climate, m = D.media;
    return '<button class="sum' + (lights.length ? ' sum--warm' : '') + '" data-sum="lights"><span class="label">Lights</span><b class="num">' + lights.length + '</b><small>on in ' + unique(lights.map(function (l) { return l.room; })).length + ' rooms</small></button>' +
      '<button class="sum' + (secure ? '' : ' sum--warn') + '" data-sum="security"><span class="label">Security</span><b class="num">' + (secure ? 'Locked' : unlocked.length + (garage.state !== 'closed' ? 1 : 0)) + '</b><small>' + (secure ? 'All doors + garage' : (garage.state !== 'closed' ? 'Garage ' + garage.state : '') + (unlocked.length ? (garage.state !== 'closed' ? ' · ' : '') + unlocked.map(function (u) { return u.name; }).join(', ') : '') + (secure ? '' : ' open')) + '</small></button>' +
      '<button class="sum" data-sum="climate"><span class="label">Climate</span><b class="num">' + c.current + '°</b><small>' + (c.mode === 'off' ? 'System off' : (c.set > c.current ? 'Heating' : c.set < c.current ? 'Cooling' : 'Holding') + ' to ' + c.set + '°') + '</small></button>' +
      '<button class="sum" data-sum="media"><span class="label">Media</span><b class="num">' + (m.playing ? 'Playing' : 'Paused') + '</b><small>' + m.room + ' speaker</small></button>';
  }
  function unique(a) { return a.filter(function (x, i) { return a.indexOf(x) === i; }); }

  function scenes() {
    return D.scenes.map(function (s) {
      return '<button class="scene' + (V.scene === s.id ? ' is-on' : '') + '" data-scene="' + s.id + '">' + App.icon(s.icon, 26) + '<span>' + s.name + '</span></button>';
    }).join('');
  }

  function rooms() {
    return D.rooms.map(function (r) {
      var list = D.devices.filter(function (d) { return d.room === r.id; });
      var on = list.filter(function (d) { return d.type === 'light' && d.on; }).length;
      return '<section class="room"><div class="room-h"><h3 class="serif">' + r.name + '</h3><span class="label">' + (on ? on + ' on' : 'All off') + '</span></div>' +
        '<div class="tiles">' + list.map(tile).join('') + '</div></section>';
    }).join('');
  }

  function climate() {
    var c = D.climate;
    var verb = c.mode === 'off' ? 'Off' : c.set > c.current ? 'Heating' : c.set < c.current ? 'Cooling' : 'Holding';
    return '<div class="label label--light">Climate · Main floor</div>' +
      '<div class="th-main"><button class="th-btn" data-temp="-0.5" aria-label="Cooler">' + App.icon('minus', 36) + '</button>' +
      '<div class="th-set"><span class="num">' + c.set.toFixed(1).replace('.0', '') + '°</span><small>Set to</small></div>' +
      '<button class="th-btn" data-temp="0.5" aria-label="Warmer">' + App.icon('plus', 36) + '</button></div>' +
      '<div class="th-now"><span><b class="num">' + c.current + '°</b> inside</span><span class="th-verb th-verb--' + verb.toLowerCase() + '">' + verb + '</span><span><b class="num">' + c.humidity + '%</b> humidity</span></div>' +
      '<div class="seg seg--dark">' + [['heat', 'Heat'], ['cool', 'Cool'], ['auto', 'Auto'], ['off', 'Off']].map(function (m) {
        return '<button class="' + (c.mode === m[0] ? 'is-on' : '') + '" data-tmode="' + m[0] + '">' + m[1] + '</button>';
      }).join('') + '</div>';
  }

  function cams() {
    return '<div class="label">Cameras · snapshots every 20s</div><div class="cams">' + D.cameras.slice(0, 2).map(function (c) {
      return '<button class="cam" data-cam="' + c.id + '"><img src="' + App.img(c.seed, 400, 250) + '" alt=""><span class="cam-name">' + c.name + '</span><span class="cam-age">' + V.camAge + 's ago</span></button>';
    }).join('') + '</div>';
  }

  function media() {
    var m = D.media;
    return '<img class="np-art" src="' + App.img(m.seed, 160, 160) + '" alt="">' +
      '<div class="np-text"><span class="label">' + m.room + '</span><b>' + m.title + '</b><span>' + m.artist + '</span></div>' +
      '<button class="np-btn" data-play aria-label="Play/Pause">' + App.icon(m.playing ? 'pause' : 'play', 30) + '</button>';
  }

  function paint() {
    if (!V.el || App.current !== 'control') return;
    var el = V.el;
    el.querySelector('.hc-sum').innerHTML = summary();
    el.querySelector('.hc-scenes').innerHTML = scenes();
    var rs = el.querySelector('.hc-rooms'), st = rs.scrollTop;
    rs.innerHTML = rooms();
    rs.scrollTop = st;
    bindTiles(rs);
    el.querySelector('.hc-climate').innerHTML = climate();
    el.querySelector('.hc-media').innerHTML = media();
    if (V.sheetPaint) V.sheetPaint();
  }

  // ------------------------------------------------------------ tile gestures
  // Lights + blinds: tap toggles, horizontal drag sets level (whole tile is the slider).
  function sliderTile(t, d) {
    var sx, startLvl, dragging = false, w;
    t.addEventListener('pointerdown', function (e) {
      sx = e.clientX; dragging = false; w = t.getBoundingClientRect().width;
      startLvl = d.type === 'light' ? (d.on ? d.level : 0) : d.pos;
      t.setPointerCapture(e.pointerId);
    });
    t.addEventListener('pointermove', function (e) {
      if (sx == null) return;
      var dx = e.clientX - sx;
      if (!dragging && Math.abs(dx) > 10) { dragging = true; t.classList.add('is-drag'); }
      if (!dragging) return;
      var lvl = Math.max(0, Math.min(100, Math.round(startLvl + dx / w * 100)));
      t.style.setProperty('--lvl', lvl + '%');
      t.classList.toggle('is-on', lvl > 0);
      t.querySelector('.tile-state').textContent = d.type === 'light' ? (lvl ? lvl + '%' : 'Off') : (lvl === 0 ? 'Closed' : lvl === 100 ? 'Open' : lvl + '% open');
      t._lvl = lvl;
    });
    t.addEventListener('pointerup', function () {
      if (sx == null) return;
      sx = null;
      t.classList.remove('is-drag');
      V.scene = null;
      if (dragging) {
        var lvl = t._lvl;
        if (d.type === 'light') App.setDevice(d.id, lvl ? { on: true, level: lvl } : { on: false });
        else App.setDevice(d.id, { pos: lvl });
      } else if (d.type === 'light') App.setDevice(d.id, { on: !d.on, level: d.level || 100 });
      else App.setDevice(d.id, { pos: d.pos > 0 ? 0 : 100 });
    });
    t.addEventListener('pointercancel', function () { sx = null; t.classList.remove('is-drag'); paint(); });
  }

  function bindTiles(root) {
    App.$$('[data-dev]', root).forEach(function (t) {
      var d = dev(t.dataset.dev);
      if (d.type === 'light' || d.type === 'blind') sliderTile(t, d);
      if (d.type === 'lock') {
        App.hold(t, 1000, {
          enabled: function () { return d.locked; },
          done: function () { V.lastHold = Date.now(); App.setDevice(d.id, { locked: false }); App.toast('<b>' + d.name + '</b> unlocked', { icon: 'unlock' }); },
          cancel: function () { App.toast('Hold for a second to unlock <b>' + d.name + '</b>', { icon: 'lock', ms: 2200 }); }
        });
        t.addEventListener('click', function () { if (!d.locked && Date.now() - (V.lastHold || 0) > 800) App.setDevice(d.id, { locked: true }); });
      }
      if (d.type === 'garage') t.addEventListener('click', function () { App.openGarageSheet(); });
    });
  }

  // Slide-to-confirm for the garage
  App.openGarageSheet = function () {
    var g = dev('g-door'), opening = g.state === 'closed';
    App.sheet('<div class="sheet-pad"><div class="label">Garage door · currently ' + g.state + '</div><h2 class="serif sheet-h">' + (opening ? 'Open' : 'Close') + ' the garage?</h2>' +
      '<p class="sheet-p">' + (opening ? 'Make sure the driveway is clear.' : 'The door will stop and reverse if anything is in the way.') + '</p>' +
      '<div class="slide-confirm"><span class="sc-label">Slide to ' + (opening ? 'open' : 'close') + ' →</span><span class="sc-fill"></span><span class="sc-knob">' + App.icon('garage', 30) + '</span></div></div>', {
      onMount: function (s, close) {
        var track = s.querySelector('.slide-confirm'), knob = s.querySelector('.sc-knob'), fill = s.querySelector('.sc-fill');
        var sx = null, max;
        knob.addEventListener('pointerdown', function (e) {
          sx = e.clientX; max = track.getBoundingClientRect().width - knob.getBoundingClientRect().width - 8;
          knob.setPointerCapture(e.pointerId);
        });
        knob.addEventListener('pointermove', function (e) {
          if (sx == null) return;
          var k = App.$('#stage').getBoundingClientRect().width / 1280;
          var x = Math.max(0, Math.min(max / k, (e.clientX - sx) / k));
          knob.style.transform = 'translateX(' + x + 'px)';
          fill.style.width = (x + 76) + 'px';
          knob._x = x; knob._max = max / k;
        });
        knob.addEventListener('pointerup', function () {
          if (sx == null) return;
          sx = null;

          if (knob._x >= knob._max - 6) {
            close();
            g.state = opening ? 'opening' : 'closing';
            V.scene = null;
            paint(); App.emit('data');
            setTimeout(function () { g.state = opening ? 'open' : 'closed'; paint(); App.emit('data'); App.toast('Garage ' + g.state, { icon: 'garage', ms: 2500 }); }, 4000);
          } else { knob.style.transform = ''; fill.style.width = ''; }
        });
      }
    });
  };

  App.cameraSheet = function (c) {
    App.sheet('<div class="cam-big"><img src="' + App.img(c.seed, 1200, 750) + '" alt=""><div class="cam-big-bar"><span class="tk-live"><i></i>' + c.name + '</span><span class="label label--light">Snapshot · ' + V.camAge + 's ago</span></div></div>', { cls: 'sheet--cam' });
  };

  function listSheet(kind) {
    var list = D.devices.filter(function (d) { return kind === 'lights' ? d.type === 'light' : (d.type === 'lock' || d.type === 'garage'); });
    if (kind === 'lights') list.sort(function (a, b) { return b.on - a.on; });
    App.sheet('<div class="sheet-pad"><div class="label">' + (kind === 'lights' ? 'Every light in the house' : 'Doors + garage') + '</div>' +
      '<h2 class="serif sheet-h">' + (kind === 'lights' ? 'Lights' : 'Security') + '</h2>' +
      '<div class="tiles tiles--sheet">' + list.map(tile).join('') + '</div>' +
      '<div class="sheet-actions">' + (kind === 'lights' ? '<button class="btn btn--solid" data-alloff>Turn everything off</button>' : '<button class="btn btn--solid" data-lockall>Lock all doors</button>') + '</div></div>', {
      cls: 'sheet--wide',
      onClose: function () { V.sheetPaint = null; },
      onMount: function (s, close) {
        var box = s.querySelector('.tiles--sheet');
        V.sheetPaint = function () { box.innerHTML = list.map(tile).join(''); bindTiles(box); };
        bindTiles(box);
        var off = s.querySelector('[data-alloff]'), lk = s.querySelector('[data-lockall]');
        if (off) off.onclick = function () {
          var prev = D.devices.filter(function (d) { return d.type === 'light' && d.on; });
          prev.forEach(function (d) { d.on = false; });
          close(); paint(); App.emit('data');
          App.toast('Turned off ' + prev.length + ' lights', { icon: 'bulb', undo: function () { prev.forEach(function (d) { d.on = true; }); paint(); App.emit('data'); } });
        };
        if (lk) lk.onclick = function () {
          D.devices.forEach(function (d) { if (d.type === 'lock') d.locked = true; });
          close(); paint(); App.emit('data');
          App.toast('All doors locked', { icon: 'lock' });
        };
      }
    });
  }

  function applyScene(id) {
    var s = D.scenes.filter(function (x) { return x.id === id; })[0];
    var snapshot = D.devices.map(function (d) { return Object.assign({}, d); });
    var prevScene = V.scene;
    Object.keys(s.set).forEach(function (k) {
      var d = dev(k), v = s.set[k];
      if (d.type === 'blind') d.pos = v;
      else if (v === 0) d.on = false;
      else { d.on = true; d.level = v; }
    });
    if (id === 'away' || id === 'night') D.devices.forEach(function (d) { if (d.type === 'lock') d.locked = true; });
    V.scene = id;
    paint(); App.emit('data');
    App.toast('<b>' + s.name + '</b> scene on', {
      icon: s.icon, undo: function () {
        snapshot.forEach(function (o) { Object.assign(dev(o.id), o); });
        V.scene = prevScene; paint(); App.emit('data');
      }
    });
  }

  function onClick(e) {
    var t;
    if ((t = e.target.closest('[data-scene]'))) return applyScene(t.dataset.scene);
    if ((t = e.target.closest('[data-sum]'))) {
      var k = t.dataset.sum;
      if (k === 'lights' || k === 'security') return listSheet(k);
      var target = V.el.querySelector(k === 'climate' ? '.hc-climate' : '.hc-media');
      target.classList.add('is-pulse'); setTimeout(function () { target.classList.remove('is-pulse'); }, 900);
      return;
    }
    if ((t = e.target.closest('[data-temp]'))) {
      D.climate.set = Math.max(15, Math.min(28, D.climate.set + +t.dataset.temp));
      if (D.climate.mode === 'off') D.climate.mode = 'heat';
      return paint();
    }
    if ((t = e.target.closest('[data-tmode]'))) { D.climate.mode = t.dataset.tmode; return paint(); }
    if ((t = e.target.closest('[data-cam]'))) return App.cameraSheet(D.cameras.filter(function (c) { return c.id === t.dataset.cam; })[0]);
    if ((t = e.target.closest('[data-play]'))) { D.media.playing = !D.media.playing; return paint(); }
  }

  App.register('control', {
    show: function (el) {
      if (!V.el) {
        V.el = el;
        el.innerHTML = '<div class="hc">' +
          '<div class="hc-left"><div class="hc-sum"></div><div class="hc-scenes"></div><div class="hc-rooms"></div></div>' +
          '<div class="hc-right"><div class="hc-climate"></div><div class="hc-cams"></div><div class="hc-media card"></div></div>' +
          '</div>';
        el.addEventListener('click', onClick);
      }
      el.querySelector('.hc-cams').innerHTML = cams();
      paint();
      clearInterval(V.camTimer);
      V.camTimer = setInterval(function () {
        V.camAge = V.camAge >= 20 ? 1 : V.camAge + 1;
        App.$$('.cam-age', el).forEach(function (a) { a.textContent = V.camAge + 's ago'; });
      }, 1000);
    },
    hide: function () { clearInterval(V.camTimer); }
  });
})();
