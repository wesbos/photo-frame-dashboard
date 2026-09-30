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
    el.offsetWidth;
    el.classList.add('is-open');
    App.closeSheet();
    if (App.mode !== 'day') App.setMode('day');
    return el;
  }
  function closeTakeover() {
    var el = $('#takeover');
    el.classList.remove('is-open');
    setTimeout(function () { if (!el.classList.contains('is-open')) el.innerHTML = ''; }, 350);
  }
  App.closeTakeover = closeTakeover;

  var doorbellTimer;
  App.doorbell = function () {
    var now = App.now();
    var el = takeover(
      '<div class="tk-cam"><img src="' + img('visitor-porch', 1280, 800) + '" alt=""><span class="tk-live"><i></i>LIVE · Front Porch</span></div>' +
      '<div class="tk-door">' +
      '  <div class="label label--light">' + App.icon('bell', 20) + ' Doorbell · ' + App.fmt.time(now) + '</div>' +
      '  <h1 class="serif tk-title">Someone’s at<br>the front door</h1>' +
      '  <div class="tk-actions">' +
      '    <button class="tk-btn" data-talk>' + App.icon('mic', 30) + '<span>Talk</span></button>' +
      '    <button class="tk-btn tk-btn--hold" data-unlock>' + App.icon('unlock', 30) + '<span>Hold to unlock</span><i class="hold-fill"></i></button>' +
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
      '    <button class="tk-btn tk-btn--hold tk-btn--light" data-valve>' + App.icon('drop', 30) + '<span>Hold to shut off water</span><i class="hold-fill"></i></button>' +
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
    requestAnimationFrame(function () { b.classList.add('is-in'); });
    function kill() { b.classList.remove('is-in'); setTimeout(function () { b.remove(); }, 300); }
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

  // ------------------------------------------------------------ demo drawer
  function demoHTML() {
    var t = App.now();
    return '<div class="demo-panel">' +
      '<div class="demo-head"><div><div class="label label--light">Prototype</div><h2 class="serif">Demo controls</h2></div><button class="demo-x" data-demo-close>' + App.icon('x', 28) + '</button></div>' +
      '<div class="demo-sec"><div class="label label--light">Time of day · now ' + App.fmt.time(t) + '</div><div class="demo-grid">' +
      '<button data-time="7:10">7:10 AM</button><button data-time="15:18">3:18 PM</button><button data-time="19:45">7:45 PM</button><button data-time="23:40">11:40 PM</button><button data-time="real">Real time</button></div></div>' +
      '<div class="demo-sec"><div class="label label--light">Modes</div><div class="demo-grid">' +
      '<button data-mode="ambient">Ambient</button><button data-mode="night">Night</button><button data-fastidle>' + (App.idle.home < 60 ? 'Idle: fast ✓' : 'Idle: fast') + '</button></div></div>' +
      '<div class="demo-sec"><div class="label label--light">Alerts</div><div class="demo-grid">' +
      '<button data-alert="doorbell">Doorbell</button><button data-alert="leak">Water leak</button><button data-alert="garage">Garage open</button><button data-alert="package">Package</button></div></div>' +
      '<div class="demo-sec"><div class="label label--light">Calendar data</div><div class="demo-grid">' +
      ['normal', 'empty', 'busy'].map(function (m) {
        return '<button data-cal="' + m + '" class="' + (App.calMode === m ? 'is-on' : '') + '">' + { normal: 'Normal day', empty: 'Empty day', busy: 'Overloaded' }[m] + '</button>';
      }).join('') + '</div></div>' +
      '<p class="demo-note">Keyboard: <b>D</b> demo · <b>A</b> ambient · <b>N</b> night · <b>1–6</b> views</p>' +
      '</div>';
  }
  App.openDemo = function () {
    var el = $('#demo');
    el.innerHTML = demoHTML();
    el.classList.add('is-open');
  };
  function closeDemo() { $('#demo').classList.remove('is-open'); }

  function demoClick(e) {
    var b = e.target.closest('button');
    if (!b) { if (e.target === $('#demo')) closeDemo(); return; }
    if (b.hasAttribute('data-demo-close')) return closeDemo();
    if (b.dataset.time) {
      if (b.dataset.time === 'real') App.setTime(null);
      else { var p = b.dataset.time.split(':'); App.setTime(+p[0], +p[1]); }
      App.openDemo();
      return;
    }
    if (b.dataset.mode) { closeDemo(); App.setMode(b.dataset.mode); return; }
    if (b.hasAttribute('data-fastidle')) {
      var fast = App.idle.home >= 60;
      App.idle.home = fast ? 8 : 60;
      App.idle.ambient = fast ? 15 : 120;
      App.openDemo();
      return;
    }
    if (b.dataset.alert) {
      closeDemo();
      ({ doorbell: App.doorbell, leak: App.leak, garage: App.garageOpenAlert, package: App.packageNotice })[b.dataset.alert]();
      return;
    }
    if (b.dataset.cal) { App.calMode = b.dataset.cal; App.rerender(); App.openDemo(); }
  }

  App.on('ready', function () {
    $('#demo').addEventListener('click', demoClick);
    App.hold($('#railClock'), 700, { done: App.openDemo });
    document.addEventListener('keydown', function (e) {
      if (e.target.tagName === 'INPUT') return;
      var k = e.key.toLowerCase();
      if (k === 'd') { $('#demo').classList.contains('is-open') ? closeDemo() : App.openDemo(); }
      if (k === 'a') App.setMode('ambient');
      if (k === 'n') App.setMode('night');
      if (k === 'escape') { closeDemo(); App.closeSheet(); }
      var views = ['home', 'calendar', 'tasks', 'shopping', 'photos', 'control'];
      if (k >= '1' && k <= '6') App.go(views[+k - 1]);
    });
  });
})();
