// Alerts (takeovers, banners, notices) + the hidden demo drawer.
(function () {
  'use strict';
  var D = window.DATA, $ = App.$;

  function img(seed, w, h) { return 'https://picsum.photos/seed/' + seed + '/' + w + '/' + h; }
  App.img = img;

  // ------------------------------------------------------------ full-screen takeovers
  function takeover(html, cls) {
    var el = $('#takeover');
    el.className = 'takeover ' + (cls || '');
    el.innerHTML = html;
    el.classList.add('is-open');
    App.closeSheet();
    if (App.mode !== 'day') App.setMode('day');
    return el;
  }
  function closeTakeover() {
    var el = $('#takeover');
    el.classList.remove('is-open');
    el.innerHTML = '';
  }
  App.closeTakeover = closeTakeover;

  var doorbellTimer;
  App.doorbell = function () {
    var now = App.now();
    var el = takeover(
      '<div class="tk-cam"><img src="' + img('visitor-porch', 1280, 800) + '" alt=""><span class="tk-live"><i></i>LIVE · Front Porch</span></div>' +
      '<div class="tk-door">' +
      '  <div class="label label--light">' + App.icon('bell', 20) + ' Doorbell · ' + App.fmt.time(now) + '</div>' +
      '  <h1 class="serif tk-title">Someone\u2019s at<br>the front door</h1>' +
      '  <div class="tk-actions">' +
      '    <button class="tk-btn" data-talk>' + App.icon('mic', 30) + '<span>Talk</span></button>' +
      '    <button class="tk-btn tk-btn--hold" data-unlock>' + App.icon('unlock', 30) + '<span>Hold to unlock</span></button>' +
      '    <button class="tk-btn tk-btn--solid" data-dismiss>' + App.icon('x', 30) + '<span>Dismiss</span></button>' +
      '  </div>' +
      '</div>', 'takeover--door');
    el.querySelector('[data-dismiss]').onclick = function () { clearTimeout(doorbellTimer); closeTakeover(); };
    el.querySelector('[data-talk]').onclick = function () {
      this.classList.toggle('is-on');
      this.querySelector('span').textContent = this.classList.contains('is-on') ? 'Talking…' : 'Talk';
    };
    var u = el.querySelector('[data-unlock]');
    App.hold(u, 1000, {
      done: function () {
        App.setDevice('e-door', { locked: false });
        u.classList.add('is-on');
        u.querySelector('span').textContent = 'Unlocked';
        App.toast('Front door unlocked · relocks in 2 min', { icon: 'unlock' });
      },
      cancel: function () { App.toast('Keep holding to unlock', { ms: 2000, icon: 'lock' }); }
    });
    clearTimeout(doorbellTimer);
    doorbellTimer = setTimeout(closeTakeover, 45000);
  };

  App.leak = function () {
    var now = App.now();
    var el = takeover(
      '<div class="tk-alarm">' +
      '  <div class="tk-alarm-icon">' + App.icon('drop', 88) + '</div>' +
      '  <div class="label label--light">Critical alert · ' + App.fmt.time(now) + '</div>' +
      '  <h1 class="tk-huge">Water leak</h1>' +
      '  <p class="tk-sub">Laundry room sensor detected water on the floor.</p>' +
      '  <div class="tk-actions">' +
      '    <button class="tk-btn tk-btn--hold tk-btn--light" data-valve>' + App.icon('drop', 30) + '<span>Hold to shut off water</span></button>' +
      '    <button class="tk-btn tk-btn--solid tk-btn--light" data-ack>' + App.icon('check', 30) + '<span>Acknowledge</span></button>' +
      '  </div>' +
      '</div>', 'takeover--alarm');
    var v = el.querySelector('[data-valve]');
    App.hold(v, 1200, {
      done: function () { v.classList.add('is-on'); v.querySelector('span').textContent = 'Water main closed'; },
      cancel: function () { App.toast('Keep holding to shut off the water main', { ms: 2000, icon: 'drop' }); }
    });
    el.querySelector('[data-ack]').onclick = function () {
      closeTakeover();
      App.toast('Leak acknowledged by the kitchen display', { icon: 'check' });
    };
  };

  // ------------------------------------------------------------ banners (amber, actionable)
  App.banner = function (opts) {
    var box = $('#banners');
    var b = document.createElement('div');
    b.className = 'banner banner--' + (opts.tone || 'amber');
    b.innerHTML = App.icon(opts.icon || 'bell', 30) + '<div class="banner-text"><b>' + opts.title + '</b><span>' + (opts.sub || '') + '</span></div>' +
      (opts.action ? '<button class="banner-btn banner-btn--solid" data-act>' + opts.action + '</button>' : '') +
      '<button class="banner-btn" data-x>' + (opts.dismiss || 'Dismiss') + '</button>';
    box.appendChild(b);
    b.classList.add('is-in');
    function kill() { b.remove(); }
    b.querySelector('[data-x]').onclick = kill;
    if (opts.action) b.querySelector('[data-act]').onclick = function () { kill(); opts.onAction(); };
    if (opts.ms) setTimeout(kill, opts.ms);
    return kill;
  };

  App.garageOpenAlert = function () {
    App.setDevice('g-door', { state: 'open' });
    App.banner({
      icon: 'garage', title: 'Garage open for 15 min', sub: 'No one is in the garage · Wes is 12 min away',
      action: 'Close garage', dismiss: 'Leave open',
      onAction: function () { App.openGarageSheet(); }
    });
  };

  App.packageNotice = function () {
    App.banner({
      tone: 'ink', icon: 'box', title: 'Package delivered', sub: 'Front porch · ' + App.fmt.time(App.now()),
      action: 'View camera', dismiss: 'OK', ms: 9000,
      onAction: function () { App.cameraSheet(D.cameras[0]); }
    });
  };

  // ------------------------------------------------------------ settings drawer
  var COLORS = ['#2D5BFF', '#E4007C', '#00A36C', '#FFB000', '#9B59B6', '#E74C3C', '#1ABC9C', '#F39C12'];
  var settingsTab = 'family';

  function colorInk(hex) {
    var r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
    return (r * 299 + g * 587 + b * 114) / 1000 > 128 ? '#111111' : '#FFFFFF';
  }
  function hexToRgb(hex) {
    return parseInt(hex.slice(1, 3), 16) + ' ' + parseInt(hex.slice(3, 5), 16) + ' ' + parseInt(hex.slice(5, 7), 16);
  }
  function loadCfg(key, fallback) {
    try { return localStorage.getItem('hq-' + key) || fallback; } catch (e) { return fallback; }
  }
  function saveCfg(key, val) {
    try { localStorage.setItem('hq-' + key, val); } catch (e) {}
  }
  function saveAll() {
    saveCfg('people', JSON.stringify(D.people));
    saveCfg('chores', JSON.stringify(D.chores));
    saveCfg('stars', JSON.stringify(D.stars));
    saveCfg('week', JSON.stringify(D.week));
    App.emit('data');
  }

  // ---- tab renderers
  function tabFamily() {
    var h = '<div class="cfg-list">';
    D.people.forEach(function (p, i) {
      h += '<div class="cfg-row">' +
        '<span class="cfg-avatar" style="background:' + p.color + ';color:' + p.ink + '">' + p.name.charAt(0) + '</span>' +
        '<input class="cfg-input cfg-input--grow" data-pname="' + i + '" value="' + App.esc(p.name) + '" placeholder="Name">' +
        '<input class="cfg-input cfg-input--sm" data-page="' + i + '" type="number" value="' + (p.age || '') + '" placeholder="Age">' +
        '<input class="cfg-input cfg-input--color" data-pcolor="' + i + '" type="color" value="' + p.color + '">' +
        '<button class="cfg-icon-btn" data-remove-person="' + i + '" title="Remove">' + App.icon('x', 18) + '</button>' +
        '</div>';
    });
    h += '</div>' +
      '<button class="cfg-btn cfg-btn--outline" data-add-person>' + App.icon('plus', 18) + ' Add person</button>';
    return h;
  }

  function tabChores() {
    var curRoutine = App.currentRoutine().id;
    var h = '<div class="cfg-seg">' +
      D.routines.map(function (r) {
        return '<button class="cfg-seg-btn' + (curRoutine === r.id ? ' is-on' : '') + '" data-show-routine="' + r.id + '">' + r.name + '</button>';
      }).join('') + '</div>';

    D.routines.forEach(function (r) {
      var list = D.chores.filter(function (c) { return c.r === r.id; });
      h += '<div class="cfg-routine' + (r.id === curRoutine ? ' is-visible' : '') + '" data-routine="' + r.id + '">';
      if (!list.length) {
        h += '<div class="cfg-empty">No chores yet</div>';
      } else {
        h += '<div class="cfg-list">';
        list.forEach(function (c) {
          var who = c.who === 'any' ? 'Anyone' : (D.people.filter(function (p) { return p.id === c.who; })[0] || {}).name || c.who;
          h += '<div class="cfg-row">' +
            '<span class="cfg-emoji">' + c.emoji + '</span>' +
            '<span class="cfg-chore-title">' + App.esc(c.title) + '</span>' +
            '<span class="cfg-chore-who">' + App.esc(who) + '</span>' +
            '<button class="cfg-icon-btn" data-remove-chore="' + c.id + '" title="Remove">' + App.icon('x', 18) + '</button>' +
            '</div>';
        });
        h += '</div>';
      }
      // Add form for this routine
      h += '<div class="cfg-add-row">' +
        '<select class="cfg-select" data-new-who>' +
        D.people.map(function (p) { return '<option value="' + p.id + '">' + App.esc(p.name) + '</option>'; }).join('') +
        '<option value="any">Anyone</option></select>' +
        '<input class="cfg-input cfg-input--grow" data-new-title placeholder="Chore name">' +
        '<input class="cfg-input cfg-input--emoji" data-new-emoji placeholder="&#x2728;" maxlength="4">' +
        '<button class="cfg-btn cfg-btn--add" data-add-chore="' + r.id + '">Add</button>' +
        '</div></div>';
    });
    return h;
  }

  function tabWeather() {
    return '<div class="cfg-list">' +
      '<div class="cfg-field"><label class="cfg-label">City</label>' +
      '<input class="cfg-input" data-cfg="city" value="' + App.esc(loadCfg('city', 'Versailles, KY')) + '"></div>' +
      '<div class="cfg-field"><label class="cfg-label">Latitude</label>' +
      '<input class="cfg-input" data-cfg="lat" type="number" step="any" value="' + loadCfg('lat', '38.0527') + '"></div>' +
      '<div class="cfg-field"><label class="cfg-label">Longitude</label>' +
      '<input class="cfg-input" data-cfg="lon" type="number" step="any" value="' + loadCfg('lon', '-84.73') + '"></div>' +
      '</div>' +
      '<button class="cfg-btn cfg-btn--solid" data-save-location>Update weather location</button>' +
      '<p class="cfg-hint">Weather data from Open-Meteo (free, no API key). Updates every 15 minutes.</p>';
  }

  function tabDisplay() {
    var themePref = loadCfg('theme', 'light');
    return '<div class="cfg-list">' +
      '<div class="cfg-field"><label class="cfg-label">Theme</label>' +
      '<div class="cfg-seg">' +
      '<button class="cfg-seg-btn' + (themePref === 'light' ? ' is-on' : '') + '" data-theme="light">' + App.icon('sun', 18) + ' Light</button>' +
      '<button class="cfg-seg-btn' + (themePref === 'dark' ? ' is-on' : '') + '" data-theme="dark">' + App.icon('moon', 18) + ' Dark</button>' +
      '<button class="cfg-seg-btn' + (themePref === 'auto' ? ' is-on' : '') + '" data-theme="auto">' + App.icon('clock', 18) + ' Auto</button>' +
      '</div></div>' +
      '</div>' +
      '<p class="cfg-hint">Auto switches to dark mode between 8 PM and 6 AM.</p>' +
      '<div class="cfg-grid">' +
      '<button class="cfg-btn cfg-btn--outline" data-mode="ambient">' + App.icon('sun', 20) + ' Ambient photos</button>' +
      '<button class="cfg-btn cfg-btn--outline" data-mode="night">' + App.icon('moon', 20) + ' Night clock</button>' +
      '</div>' +
      '<p class="cfg-hint">The display dims to ambient photos or a night clock after 2 minutes of no interaction. Touch to wake.</p>';
  }

  // ---- Calendar sync (ICS)
  var editingFeed = -1;
  function getIcsFeeds() {
    try { return JSON.parse(localStorage.getItem('hq-ics-feeds') || '[]'); } catch (e) { return []; }
  }
  function saveIcsFeeds(feeds) { saveCfg('ics-feeds', JSON.stringify(feeds)); }

  function tabCalSync() {
    var feeds = getIcsFeeds();
    var lastSync = loadCfg('ics-last-sync', '');
    var h = '<div class="cfg-list">';
    if (!feeds.length) {
      h += '<div class="cfg-empty">No calendars connected</div>';
    } else {
      feeds.forEach(function (f, i) {
        var p = f.person && f.person !== 'all' ? App.person(f.person) : D.family;
        var personLabel = p ? p.name : 'Everyone';
        var editing = editingFeed === i;
        h += '<div class="cfg-row' + (editing ? ' cfg-row--editing' : '') + '">' +
          '<span class="cfg-avatar" style="' + (p ? App.pstyle(p) : 'background:#C22C1C;color:#fff') + '">' + App.icon('calendar', 18) + '</span>' +
          '<button class="cfg-chore-title" data-edit-feed="' + i + '" style="cursor:pointer;background:none;border:none;color:inherit;text-align:left;font:inherit;padding:0;flex:1">' + App.esc(f.name || 'Calendar ' + (i + 1)) + ' <small style="opacity:.6">(' + personLabel + ')</small></button>' +
          '<button class="cfg-icon-btn" data-remove-feed="' + i + '" title="Remove">' + App.icon('x', 18) + '</button>' +
          '</div>';
        if (editing) {
          h += '<div class="cfg-edit-feed" style="padding:12px 0 16px;border-bottom:1px solid var(--ink-05)">' +
            '<div class="cfg-field"><label class="cfg-label">Name</label>' +
            '<input class="cfg-input" data-edit-name value="' + App.esc(f.name || '') + '"></div>' +
            '<div class="cfg-field"><label class="cfg-label">ICS URL</label>' +
            '<input class="cfg-input" data-edit-url value="' + App.esc(f.url || '') + '"></div>' +
            '<div class="cfg-field"><label class="cfg-label">Assign to</label>' +
            '<div class="add-who">' +
            '<button class="who-btn' + ((!f.person || f.person === 'all') ? ' is-on' : '') + '" data-edit-person="all" style="' + App.pstyle(D.family) + '">' + App.avatar(D.family, 40) + '<span>Everyone</span></button>' +
            D.people.map(function (pp) {
              return '<button class="who-btn' + (f.person === pp.id ? ' is-on' : '') + '" data-edit-person="' + pp.id + '" style="' + App.pstyle(pp) + '">' + App.avatar(pp, 40) + '<span>' + pp.name + '</span></button>';
            }).join('') +
            '</div></div>' +
            '<div style="display:flex;gap:10px;margin-top:8px">' +
            '<button class="cfg-btn cfg-btn--solid" data-save-feed="' + i + '">Save</button>' +
            '<button class="cfg-btn cfg-btn--outline" data-cancel-edit>Cancel</button>' +
            '</div></div>';
        }
      });
    }
    h += '</div>' +
      '<div class="cfg-field" style="margin-top:16px"><label class="cfg-label">Add a calendar</label>' +
      '<input class="cfg-input" data-feed-name placeholder="Name (e.g. Family, Work)"></div>' +
      '<div class="cfg-field"><label class="cfg-label">ICS URL</label>' +
      '<input class="cfg-input" data-feed-url placeholder="https://calendar.google.com/...basic.ics"></div>' +
      '<div class="cfg-field"><label class="cfg-label">Assign to</label>' +
      '<div class="add-who">' +
      '<button class="who-btn is-on" data-feed-person="all" style="' + App.pstyle(D.family) + '">' + App.avatar(D.family, 40) + '<span>Everyone</span></button>' +
      D.people.map(function (p) {
        return '<button class="who-btn" data-feed-person="' + p.id + '" style="' + App.pstyle(p) + '">' + App.avatar(p, 40) + '<span>' + p.name + '</span></button>';
      }).join('') +
      '</div></div>' +
      '<button class="cfg-btn cfg-btn--outline" data-add-feed>' + App.icon('plus', 18) + ' Add calendar</button>' +
      '<div style="display:flex;gap:10px;margin-top:16px">' +
      '<button class="cfg-btn cfg-btn--solid" data-sync-now>' + App.icon('calendar', 18) + ' Sync now</button>' +
      '</div>' +
      (lastSync ? '<p class="cfg-hint">Last synced: ' + lastSync + '</p>' : '') +
      '<p class="cfg-hint">To get your ICS URL from a phone or computer:<br>1. Go to <a href="https://calendar.google.com/calendar/r/settings" target="_blank">calendar.google.com/calendar/r/settings</a><br>2. Click your calendar on the left<br>3. Scroll to "Secret address in iCal format"<br>4. Copy the URL and paste it here<br><br>Syncs every 10 minutes.</p>';
    return h;
  }

  // ICS parser: extracts VEVENT blocks into our event format
  function parseICS(text, feedName, person) {
    var events = [];
    var people = person && person !== 'all' ? [person] : D.ALL.slice();
    var blocks = text.split('BEGIN:VEVENT');
    for (var i = 1; i < blocks.length; i++) {
      var block = blocks[i].split('END:VEVENT')[0];
      var get = function (key) {
        var re = new RegExp('^' + key + '[;:]([^\\r\\n]*)', 'm');
        var m = block.match(re);
        return m ? m[1].replace(/\\n/g, '\n').replace(/\\,/g, ',').replace(/\\\\/g, '\\') : '';
      };
      var dtstart = get('DTSTART');
      var dtend = get('DTEND');
      var summary = get('SUMMARY');
      var location = get('LOCATION');
      var uid = get('UID');
      var rrule = get('RRULE');
      if (!dtstart || !summary) continue;
      var start = parseICSDate(dtstart);
      var end = dtend ? parseICSDate(dtend) : new Date(+start + 3600000);
      if (!start) continue;
      var allDay = dtstart.length <= 8 || dtstart.indexOf('T') < 0;
      var ev = {
        id: 'ics_' + uid.replace(/[^a-zA-Z0-9]/g, '_').slice(0, 40),
        title: summary,
        people: people,
        start: start,
        end: end,
        allDay: allDay,
        loc: location || '',
        remind: 15,
        _ics: feedName
      };
      // Handle recurrence
      if (rrule) {
        var freq = (rrule.match(/FREQ=([^;]+)/) || [])[1];
        if (freq === 'DAILY') ev.repeat = 'daily';
        else if (freq === 'WEEKLY') ev.repeat = 'weekly';
        else if (freq === 'MONTHLY') ev.repeat = 'monthly';
      }
      events.push(ev);
    }
    return events;
  }

  function parseICSDate(s) {
    // Handle TZID prefix: TZID=America/New_York:20261123T150000
    var val = s.indexOf(':') > -1 && s.indexOf('=') > -1 ? s.split(':').pop() : s;
    // Remove VALUE=DATE: prefix
    val = val.replace(/^VALUE=DATE:?/, '');
    if (val.length === 8) {
      // All-day: YYYYMMDD
      return new Date(+val.slice(0, 4), +val.slice(4, 6) - 1, +val.slice(6, 8));
    }
    // YYYYMMDDTHHMMSS or YYYYMMDDTHHMMSSZ
    var m = val.match(/(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})/);
    if (!m) return null;
    if (val.endsWith('Z')) {
      return new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]));
    }
    return new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]);
  }

  function syncIcsFeeds() {
    var feeds = getIcsFeeds();
    if (!feeds.length) return;
    // Remove old ICS events
    D.events = D.events.filter(function (e) { return !e._ics; });
    var pending = feeds.length;
    feeds.forEach(function (f) {
      fetch('http://127.0.0.1:8765/__proxy__?url=' + encodeURIComponent(f.url)).then(function (r) { return r.text(); }).then(function (text) {
        var parsed = parseICS(text, f.name, f.person);
        parsed.forEach(function (ev) { D.events.push(ev); });
      }).catch(function () {}).then(function () {
        pending--;
        if (pending <= 0) {
          saveCfg('ics-last-sync', new Date().toLocaleTimeString());
          App.emit('data');
        }
      });
    });
  }

  // Sync on startup and every 10 minutes
  setTimeout(syncIcsFeeds, 3000);
  setInterval(syncIcsFeeds, 10 * 60 * 1000);

  var TABS = [
    { id: 'family', label: 'Family', render: tabFamily },
    { id: 'chores', label: 'Chores', render: tabChores },
    { id: 'calendar', label: 'Calendar', render: tabCalSync },
    { id: 'weather', label: 'Weather', render: tabWeather },
    { id: 'display', label: 'Display', render: tabDisplay }
  ];

  function settingsHTML() {
    return '<div class="demo-panel">' +
      '<div class="cfg-header">' +
      '<h2 class="serif cfg-title">Settings</h2>' +
      '<button class="cfg-close" data-demo-close>' + App.icon('x', 24) + '</button>' +
      '</div>' +
      '<nav class="cfg-tabs">' +
      TABS.map(function (t) {
        return '<button class="cfg-tab' + (settingsTab === t.id ? ' is-on' : '') + '" data-tab="' + t.id + '">' + t.label + '</button>';
      }).join('') +
      '</nav>' +
      '<div class="cfg-body">' + TABS.filter(function (t) { return t.id === settingsTab; })[0].render() + '</div>' +
      '<p class="cfg-footer">Changes save to the frame and persist across reboots.</p>' +
      '</div>';
  }

  App.openDemo = function () {
    var el = $('#demo');
    el.innerHTML = settingsHTML();
    el.classList.add('is-open');
  };
  function closeDemo() { $('#demo').classList.remove('is-open'); }
  function refreshPanel() { App.openDemo(); }

  function settingsClick(e) {
    var b = e.target.closest('button');
    if (!b) { if (e.target === $('#demo')) closeDemo(); return; }
    if (b.hasAttribute('data-demo-close')) return closeDemo();

    // Tab switching
    if (b.dataset.tab) { settingsTab = b.dataset.tab; refreshPanel(); return; }

    // Routine segment switching (chores tab)
    if (b.dataset.showRoutine) {
      App.$$('.cfg-seg-btn', $('#demo')).forEach(function (s) { s.classList.toggle('is-on', s.dataset.showRoutine === b.dataset.showRoutine); });
      App.$$('.cfg-routine', $('#demo')).forEach(function (r) { r.classList.toggle('is-visible', r.dataset.routine === b.dataset.showRoutine); });
      return;
    }

    // ---- Family CRUD
    if (b.hasAttribute('data-add-person')) {
      var color = COLORS[D.people.length % COLORS.length];
      var id = 'person' + Date.now();
      D.people.push({ id: id, name: '', age: 0, color: color, rgb: hexToRgb(color), ink: colorInk(color), home: true, status: 'Home' });
      D.ALL.push(id);
      refreshPanel();
      var inputs = $('#demo').querySelectorAll('[data-pname]');
      inputs[inputs.length - 1].focus();
      return;
    }
    if (b.hasAttribute('data-remove-person')) {
      var idx = parseInt(b.getAttribute('data-remove-person'));
      if (D.people.length <= 1) { App.toast('Need at least one person', { icon: 'x' }); return; }
      var removed = D.people.splice(idx, 1)[0];
      D.ALL = D.people.map(function (p) { return p.id; });
      D.chores = D.chores.filter(function (c) { return c.who !== removed.id; });
      delete D.stars[removed.id]; delete D.week[removed.id];
      saveAll(); refreshPanel();
      App.toast('Removed ' + (removed.name || 'person'), { icon: 'check' });
      return;
    }

    // ---- Chores CRUD
    if (b.dataset.addChore) {
      var routine = b.dataset.addChore;
      var row = b.closest('.cfg-add-row');
      var title = row.querySelector('[data-new-title]').value.trim();
      var emoji = row.querySelector('[data-new-emoji]').value.trim() || '✅';
      var who = row.querySelector('[data-new-who]').value;
      if (!title) { App.toast('Enter a chore name', { icon: 'x' }); return; }
      D.chores.push({ id: 'c' + Date.now(), r: routine, who: who, title: title, emoji: emoji, stars: 1, done: false });
      saveAll(); refreshPanel();
      App.toast(emoji + ' ' + title + ' added', { icon: 'check' });
      return;
    }
    if (b.dataset.removeChore) {
      var cid = b.dataset.removeChore;
      var chore = D.chores.filter(function (c) { return c.id === cid; })[0];
      D.chores = D.chores.filter(function (c) { return c.id !== cid; });
      saveAll(); refreshPanel();
      App.toast('Removed ' + (chore ? chore.title : 'chore'), { icon: 'check' });
      return;
    }

    // ---- Weather
    if (b.hasAttribute('data-save-location')) {
      var panel = $('#demo');
      var lat = panel.querySelector('[data-cfg="lat"]').value;
      var lon = panel.querySelector('[data-cfg="lon"]').value;
      var city = panel.querySelector('[data-cfg="city"]').value;
      saveCfg('lat', lat); saveCfg('lon', lon); saveCfg('city', city);
      WEATHER_LAT = parseFloat(lat) || 38.0527;
      WEATHER_LON = parseFloat(lon) || -84.73;
      fetchWeather();
      App.toast('Weather location updated', { icon: 'check' });
      return;
    }

    // ---- Display
    if (b.dataset.theme) { App.setTheme(b.dataset.theme); refreshPanel(); return; }
    if (b.dataset.mode) { closeDemo(); App.setMode(b.dataset.mode); return; }

    // ---- Calendar sync CRUD
    if (b.dataset.feedPerson != null) {
      App.$$('[data-feed-person]', $('#demo')).forEach(function (btn) {
        btn.classList.toggle('is-on', btn === b);
      });
      return;
    }
    if (b.dataset.editPerson != null) {
      App.$$('[data-edit-person]', $('#demo')).forEach(function (btn) {
        btn.classList.toggle('is-on', btn === b);
      });
      return;
    }
    if (b.dataset.editFeed != null) {
      editingFeed = editingFeed === +b.dataset.editFeed ? -1 : +b.dataset.editFeed;
      refreshPanel();
      return;
    }
    if (b.dataset.saveFeed != null) {
      var panel = $('#demo');
      var idx = +b.dataset.saveFeed;
      var feeds = getIcsFeeds();
      var f = feeds[idx];
      if (!f) return;
      var newName = panel.querySelector('[data-edit-name]').value.trim();
      var newUrl = panel.querySelector('[data-edit-url]').value.trim();
      var personBtn = panel.querySelector('[data-edit-person].is-on');
      var newPerson = personBtn ? personBtn.dataset.editPerson : f.person || 'all';
      if (newName) f.name = newName;
      if (newUrl) f.url = newUrl;
      f.person = newPerson;
      saveIcsFeeds(feeds);
      editingFeed = -1;
      syncIcsFeeds();
      refreshPanel();
      App.toast('Updated ' + f.name, { icon: 'check' });
      return;
    }
    if (b.hasAttribute('data-cancel-edit')) {
      editingFeed = -1;
      refreshPanel();
      return;
    }
    if (b.hasAttribute('data-add-feed')) {
      var panel = $('#demo');
      var name = panel.querySelector('[data-feed-name]').value.trim() || 'Calendar';
      var url = panel.querySelector('[data-feed-url]').value.trim();
      if (!url) { App.toast('Enter an ICS URL', { icon: 'x' }); return; }
      if (url.indexOf('.ics') < 0 && url.indexOf('ical') < 0) { App.toast('URL should end in .ics', { icon: 'x' }); return; }
      var personBtn = panel.querySelector('[data-feed-person].is-on');
      var person = personBtn ? personBtn.dataset.feedPerson : 'all';
      var feeds = getIcsFeeds();
      feeds.push({ name: name, url: url, person: person });
      saveIcsFeeds(feeds);
      syncIcsFeeds();
      refreshPanel();
      App.toast('Added ' + name, { icon: 'check' });
      return;
    }
    if (b.dataset.removeFeed != null) {
      var feeds = getIcsFeeds();
      var removed = feeds.splice(+b.dataset.removeFeed, 1)[0];
      saveIcsFeeds(feeds);
      D.events = D.events.filter(function (e) { return e._ics !== (removed && removed.name); });
      App.emit('data');
      refreshPanel();
      App.toast('Removed ' + (removed ? removed.name : 'calendar'), { icon: 'check' });
      return;
    }
    if (b.hasAttribute('data-sync-now')) {
      syncIcsFeeds();
      App.toast('Syncing calendars...', { icon: 'calendar', ms: 3000 });
      setTimeout(refreshPanel, 3000);
      return;
    }
  }

  // Auto-save family edits on input change
  function onSettingsInput(e) {
    var el = e.target;
    if (el.dataset.pname !== undefined) {
      var i = parseInt(el.dataset.pname);
      D.people[i].name = el.value.trim() || D.people[i].name;
      saveAll();
    }
    if (el.dataset.page !== undefined) {
      var i = parseInt(el.dataset.page);
      D.people[i].age = parseInt(el.value) || undefined;
      saveAll();
    }
    if (el.dataset.pcolor !== undefined) {
      var i = parseInt(el.dataset.pcolor);
      D.people[i].color = el.value;
      D.people[i].rgb = hexToRgb(el.value);
      D.people[i].ink = colorInk(el.value);
      var avatar = el.closest('.cfg-row').querySelector('.cfg-avatar');
      if (avatar) { avatar.style.background = el.value; avatar.style.color = D.people[i].ink; }
      saveAll();
    }
  }

  // Load saved config on startup
  function loadSavedConfig() {
    try {
      var people = localStorage.getItem('hq-people');
      if (people) { var p = JSON.parse(people); if (p && p.length) { D.people = p; D.ALL = p.map(function (x) { return x.id; }); } }
      var chores = localStorage.getItem('hq-chores');
      if (chores) D.chores = JSON.parse(chores);
      var stars = localStorage.getItem('hq-stars');
      if (stars) D.stars = JSON.parse(stars);
      var week = localStorage.getItem('hq-week');
      if (week) D.week = JSON.parse(week);
      var events = localStorage.getItem('hq-events');
      if (events) {
        var parsed = JSON.parse(events);
        D.events = parsed.map(function (e) {
          e.start = new Date(e.start);
          e.end = new Date(e.end);
          return e;
        });
      }
    } catch (e) {}
  }
  loadSavedConfig();

  // Reset all chores to undone at the start of each new day
  function resetChoresIfNewDay() {
    var today = App.now().toDateString();
    var last = loadCfg('chore-reset-date', '');
    if (last === today) return;
    var anyDone = D.chores.some(function (c) { return c.done; });
    if (anyDone) {
      D.chores.forEach(function (c) { c.done = false; delete c.doneBy; });
      saveAll();
    }
    saveCfg('chore-reset-date', today);
  }
  resetChoresIfNewDay();
  App.on('minute', resetChoresIfNewDay);

  App.on('ready', function () {
    var demo = $('#demo');
    demo.addEventListener('click', settingsClick);
    demo.addEventListener('input', onSettingsInput);
    App.hold($('#railClock'), 700, { done: App.openDemo });
    document.addEventListener('keydown', function (e) {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
      var k = e.key.toLowerCase();
      if (k === 'd') { demo.classList.contains('is-open') ? closeDemo() : App.openDemo(); }
      if (k === 'a') App.setMode('ambient');
      if (k === 'n') App.setMode('night');
      if (k === 'escape') { closeDemo(); App.closeSheet(); }
      var views = ['home', 'calendar', 'tasks', 'shopping', 'photos'];
      if (k >= '1' && k <= '7') App.go(views[+k - 1]);
    });
  });

  // ------------------------------------------------------------ live weather
  var WEATHER_LAT = parseFloat(loadCfg('lat', '38.0527'));
  var WEATHER_LON = parseFloat(loadCfg('lon', '-84.73'));
  function fetchWeather() {
    var url = 'https://api.open-meteo.com/v1/forecast?latitude=' + WEATHER_LAT +
      '&longitude=' + WEATHER_LON +
      '&hourly=temperature_2m,weathercode,precipitation_probability&daily=temperature_2m_max,temperature_2m_min,apparent_temperature_max,windspeed_10m_max&current_weather=true&temperature_unit=fahrenheit&windspeed_unit=mph&timezone=America%2FNew_York&forecast_days=2';
    fetch(url).then(function (r) { return r.json(); }).then(function (j) {
      var W = D.weather;
      var h = j.hourly;
      W.hi = Math.round(j.daily.temperature_2m_max[0]);
      W.lo = Math.round(j.daily.temperature_2m_min[0]);
      W.feels = Math.round(j.daily.apparent_temperature_max[0]);
      W.wind = Math.round((j.daily.windspeed_10m_max || [0])[0] || 0);
      W.humidity = 0;
      for (var i = 0; i < 24; i++) {
        W.t[i] = Math.round(h.temperature_2m[i]);
        W.p[i] = h.precipitation_probability[i] || 0;
        var wc = h.weathercode[i];
        if (wc <= 1) W.c[i] = (i >= 6 && i <= 18) ? 'sun' : 'moon';
        else if (wc <= 3) W.c[i] = 'partly';
        else if (wc <= 48) W.c[i] = 'cloud';
        else W.c[i] = 'rain';
      }
      // Tomorrow's forecast
      if (j.daily.temperature_2m_max.length > 1) {
        var tHi = Math.round(j.daily.temperature_2m_max[1]);
        var tLo = Math.round(j.daily.temperature_2m_min[1]);
        // Dominant condition from tomorrow's hourly data (hours 24-47)
        var condCount = { sun: 0, partly: 0, cloud: 0, rain: 0 };
        for (var ti = 24; ti < 48 && ti < h.weathercode.length; ti++) {
          var twc = h.weathercode[ti];
          if (twc <= 1) condCount.sun++;
          else if (twc <= 3) condCount.partly++;
          else if (twc <= 48) condCount.cloud++;
          else condCount.rain++;
        }
        var tCond = 'sun'; var tMax = 0;
        for (var ck in condCount) { if (condCount[ck] > tMax) { tMax = condCount[ck]; tCond = ck; } }
        var tRain = false;
        for (var ri = 24; ri < 48 && ri < (h.precipitation_probability || []).length; ri++) {
          if ((h.precipitation_probability[ri] || 0) >= 50) { tRain = true; break; }
        }
        var condLabels = { sun: 'Sunny', partly: 'Partly cloudy', cloud: 'Cloudy', rain: 'Rain' };
        W.tomorrow = { hi: tHi, lo: tLo, cond: tCond, label: condLabels[tCond], rain: tRain };
      }
      App.emit('data');
    }).catch(function () {});
  }
  fetchWeather();
  setInterval(fetchWeather, 15 * 60 * 1000);

  // ------------------------------------------------------------ event reminders
  var notifiedEvents = {};

  function playChime() {
    try {
      var ctx = new (window.AudioContext || window.webkitAudioContext)();
      function tone(freq, start, dur, vol) {
        var osc = ctx.createOscillator();
        var gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.value = freq;
        gain.gain.setValueAtTime(0, start);
        gain.gain.linearRampToValueAtTime(vol, start + 0.05);
        gain.gain.exponentialRampToValueAtTime(0.001, start + dur);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(start);
        osc.stop(start + dur);
      }
      var t = ctx.currentTime;
      tone(523, t, 0.4, 0.25);
      tone(659, t + 0.15, 0.4, 0.25);
      tone(784, t + 0.3, 0.6, 0.2);
    } catch (e) {}
  }

  App.on('minute', function (now) {
    var events = App.events();
    events.forEach(function (e) {
      if (e.allDay) return;
      var remind = e.remind != null ? e.remind : 15;
      if (!remind) return;
      var mins = Math.round((e.start - now) / 60000);
      var key = (e._parent || e.id) + '_' + +e.start;
      if (mins === remind && !notifiedEvents[key]) {
        notifiedEvents[key] = true;
        var who = e.people.map(function (id) { var p = App.person(id); return p ? p.name : id; });
        var whoText = App.isFamily(e) ? 'Everyone' : who.join(', ');
        var timeLabel = remind >= 60 ? (remind / 60) + ' hour' : remind + ' min';
        if (App.mode !== 'day') App.setMode('day');
        playChime();
        App.banner({
          icon: 'bell',
          title: e.title + ' in ' + timeLabel,
          sub: App.fmt.time(e.start) + (e.loc ? ' · ' + e.loc : '') + ' · ' + whoText,
          action: 'View',
          dismiss: 'OK',
          onAction: function () { App.go('calendar'); App.eventSheet(App.findEvent(e.id)); }
        });
      }
    });
    var cutoff = +now - 86400000;
    Object.keys(notifiedEvents).forEach(function (k) {
      var ts = parseInt(k.split('_').pop());
      if (ts && ts < cutoff) delete notifiedEvents[k];
    });
  });

  // ------------------------------------------------------------ theme (light / dark / auto)
  function applyTheme() {
    var pref = loadCfg('theme', 'light');
    var stage = document.getElementById('stage');
    if (stage.getAttribute('data-mode') === 'ambient' || stage.getAttribute('data-mode') === 'night') return;
    if (pref === 'dark') { stage.setAttribute('data-mode', 'dark'); }
    else if (pref === 'auto') {
      var h = new Date().getHours();
      stage.setAttribute('data-mode', (h >= 20 || h < 6) ? 'dark' : 'day');
    }
    else { stage.setAttribute('data-mode', 'day'); }
  }
  App.setTheme = function (pref) {
    saveCfg('theme', pref);
    applyTheme();
  };
  // Keep the old toggleDark for the Mode nav button
  App.toggleDark = function () {
    var cur = loadCfg('theme', 'light');
    var next = cur === 'dark' ? 'light' : 'dark';
    App.setTheme(next);
  };
  // Apply on startup
  applyTheme();
  // Re-check auto every minute
  App.on('minute', function () {
    if (loadCfg('theme', 'light') === 'auto') applyTheme();
  });
})();
