// Shopping: categorized list (left) + quick-add with usuals (right).
(function () {
  'use strict';
  var D = window.DATA;
  var V = { el: null, store: 'all', adder: 'jordan', query: '', drawer: false, pending: {}, flash: null };

  function open() { return D.groceries.filter(function (g) { return !g.done && (V.store === 'all' || g.store === V.store); }); }
  function done() { return D.groceries.filter(function (g) { return g.done && (V.store === 'all' || g.store === V.store); }); }
  function storeName(id) { return D.stores.filter(function (s) { return s.id === id; })[0].name; }

  function categorize(name) {
    var n = name.toLowerCase();
    var hit = D.catalog.filter(function (c) { return c[0].toLowerCase() === n; })[0] ||
      D.catalog.filter(function (c) { var a = c[0].toLowerCase(); return a.indexOf(n) > -1 || n.indexOf(a) > -1; })[0] ||
      D.catalog.filter(function (c) { return n.split(/\s+/).some(function (w) { return w.length > 3 && c[0].toLowerCase().indexOf(w) > -1; }); })[0];
    return hit ? hit[1] : 'Other';
  }
  function find(name, isDone) {
    return D.groceries.filter(function (g) { return !!g.done === isDone && g.name.toLowerCase() === name.toLowerCase(); })[0];
  }

  function row(g) {
    var p = App.person(g.by);
    return '<div class="s-row' + (V.pending[g.id] ? ' is-checking' : '') + (V.flash === g.id ? ' is-flash' : '') + '" data-id="' + g.id + '" style="' + App.pstyle(p) + '">' +
      '<button class="s-hit" data-check="' + g.id + '">' +
      '<span class="s-who" title="Added by ' + p.name + '"></span>' +
      '<span class="s-box">' + App.icon('check', 22) + '</span>' +
      '<span class="s-name"><b>' + App.esc(g.name) + '</b>' + (g.note ? '<small>' + App.esc(g.note) + '</small>' : '') + '</span>' +
      (V.store === 'all' && g.store === 'costco' ? '<span class="s-store">Costco</span>' : '') +
      '<span class="s-by">' + p.name + '</span>' +
      '</button>' +
      '<div class="s-qty"><button data-qty="-1" data-id="' + g.id + '" aria-label="Less">' + App.icon('minus', 22) + '</button><span class="num">' + g.qty + '</span><button data-qty="1" data-id="' + g.id + '" aria-label="More">' + App.icon('plus', 22) + '</button></div>' +
      '</div>';
  }

  function listHTML() {
    var items = open(), order = D.catOrder[V.store].concat(['Other']);
    var groups = order.map(function (cat) { return { cat: cat, items: items.filter(function (g) { return g.cat === cat; }) }; }).filter(function (x) { return x.items.length; });
    var d = done();
    return (items.length ? groups.map(function (gr) {
      return '<div class="s-cat"><div class="s-cat-h"><span class="label">' + gr.cat + '</span><span class="label">' + gr.items.length + '</span></div>' + gr.items.map(row).join('') + '</div>';
    }).join('') : '<div class="s-empty serif">All stocked up.<br><i>Nothing left to buy.</i></div>') +
      (d.length ? '<div class="s-drawer' + (V.drawer ? ' is-open' : '') + '">' +
        '<button class="s-drawer-h" data-drawer><span>' + App.icon('check', 22) + ' Got it <b class="num">(' + d.length + ')</b></span><span class="label">' + (V.drawer ? 'Hide' : 'Show') + '</span></button>' +
        (V.drawer ? '<div class="s-drawer-list">' + d.map(function (g) {
          return '<button class="s-got" data-revive="' + g.id + '">' + App.esc(g.name) + '<span class="label">Add back</span></button>';
        }).join('') + '<button class="btn btn--ghost s-clear" data-clear>Clear ' + d.length + ' checked items</button></div>' : '') +
        '</div>' : '');
  }

  function suggestHTML() {
    var q = V.query.trim().toLowerCase();
    if (q) {
      var matches = D.catalog.filter(function (c) { return c[0].toLowerCase().indexOf(q) === 0; })
        .concat(D.catalog.filter(function (c) { var i = c[0].toLowerCase().indexOf(q); return i > 0; })).slice(0, 5);
      var exact = matches.some(function (m) { return m[0].toLowerCase() === q; });
      return '<div class="label">Suggestions</div><div class="s-ac">' + matches.map(function (m) {
        var on = find(m[0], false);
        return '<button class="s-ac-row" data-add="' + App.esc(m[0]) + '"><b>' + App.esc(m[0]) + '</b><span class="label">' + (on ? 'On list · ×' + on.qty : m[1]) + '</span>' + App.icon('plus', 26) + '</button>';
      }).join('') + (exact ? '' : '<button class="s-ac-row s-ac-row--new" data-add="' + App.esc(V.query.trim()) + '"><b>Add “' + App.esc(V.query.trim()) + '”</b><span class="label">' + categorize(V.query) + '</span>' + App.icon('plus', 26) + '</button>') + '</div>';
    }
    return '<div class="label">Usuals · tap to add</div><div class="s-usuals">' + D.usuals.map(function (name) {
      var on = find(name, false);
      return '<button class="s-tile' + (on ? ' is-on' : '') + '" data-add="' + App.esc(name) + '"' + (on ? ' style="' + App.pstyle(on.by) + '"' : '') + '>' +
        '<b>' + App.esc(name) + '</b><span>' + (on ? App.icon('check', 16) + 'On list' + (on.qty > 1 ? ' ×' + on.qty : '') : categorize(name)) + '</span></button>';
    }).join('') + '</div>';
  }

  function paintList() { var l = V.el.querySelector('.s-list'); var st = l.scrollTop; l.innerHTML = listHTML(); l.scrollTop = st; paintHead(); }
  function paintSuggest() { V.el.querySelector('.s-suggest').innerHTML = suggestHTML(); }
  function paintHead() {
    var all = D.groceries.filter(function (g) { return !g.done; });
    V.el.querySelector('.s-count').innerHTML = '<span class="num">' + open().length + '</span> to get';
    V.el.querySelector('.s-stores').innerHTML = [['all', 'All']].concat(D.stores.map(function (s) { return [s.id, s.name]; })).map(function (s) {
      var n = s[0] === 'all' ? all.length : all.filter(function (g) { return g.store === s[0]; }).length;
      return '<button class="' + (V.store === s[0] ? 'is-on' : '') + '" data-store="' + s[0] + '">' + s[1] + ' <span class="num">' + n + '</span></button>';
    }).join('');
  }
  function paintAdder() {
    V.el.querySelector('.s-adder-row').innerHTML = D.people.map(function (p) {
      return '<button class="s-adder-btn' + (V.adder === p.id ? ' is-on' : '') + '" data-adder="' + p.id + '" style="' + App.pstyle(p) + '">' + App.avatar(p, 44) + '</button>';
    }).join('');
  }

  function render() {
    V.el.innerHTML = '<div class="shop">' +
      '<header class="s-head"><div><div class="label">Shared list</div><h1 class="serif">Groceries</h1></div><div class="s-count"></div><div class="seg s-stores"></div></header>' +
      '<div class="s-list"></div>' +
      '<aside class="s-side">' +
      '  <div class="s-add">' +
      '    <label class="s-input-wrap">' + App.icon('plus', 30) + '<input class="s-input" placeholder="Add an item…" autocomplete="off" enterkeyhint="done"></label>' +
      '    <div class="s-adder"><span class="label label--light">Adding as</span><div class="s-adder-row"></div></div>' +
      '  </div>' +
      '  <div class="s-suggest"></div>' +
      '</aside></div>';
    var input = V.el.querySelector('.s-input');
    input.value = V.query;
    input.addEventListener('input', function () { V.query = input.value; paintSuggest(); });
    input.addEventListener('keydown', function (e) { if (e.key === 'Enter' && input.value.trim()) { add(input.value); } });
    paintList(); paintSuggest(); paintAdder();
  }

  function add(name) {
    name = name.trim();
    var g = find(name, false), msg;
    if (g) { g.qty++; msg = 'Already on the list · now <b>×' + g.qty + '</b> ' + App.esc(g.name); }
    else if ((g = find(name, true))) { g.done = false; g.qty = 1; g.by = V.adder; msg = 'Added back <b>' + App.esc(g.name) + '</b>'; }
    else {
      var cat = D.catalog.filter(function (c) { return c[0].toLowerCase() === name.toLowerCase(); })[0];
      g = { id: D._gid(), name: cat ? cat[0] : name.charAt(0).toUpperCase() + name.slice(1), cat: categorize(name), qty: 1, by: V.adder, store: V.store === 'all' ? 'grocer' : V.store, done: false, note: '' };
      D.groceries.push(g);
      msg = 'Added <b>' + App.esc(g.name) + '</b> to ' + g.cat;
    }
    V.query = '';
    var input = V.el.querySelector('.s-input');
    if (input) input.value = '';
    V.flash = g.id;
    paintList(); paintSuggest();
    var el = V.el.querySelector('[data-id="' + g.id + '"]');
    if (el && el.scrollIntoView) el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    setTimeout(function () { V.flash = null; }, 1200);
    App.emit('data');
    App.toast(msg, { icon: 'cart', ms: 3000 });
  }

  function check(g) {
    V.pending[g.id] = true;
    var rowEl = V.el.querySelector('[data-id="' + g.id + '"]');
    rowEl.classList.add('is-checking');
    setTimeout(function () {
      if (!V.pending[g.id]) return;
      rowEl.classList.add('is-leaving');
      setTimeout(function () {
        delete V.pending[g.id];
        g.done = true;
        paintList(); paintSuggest();
        App.emit('data');
      }, 320);
    }, 1800);
    App.toast('<b>' + App.esc(g.name) + '</b> checked off', {
      icon: 'check',
      undo: function () {
        delete V.pending[g.id];
        g.done = false;
        paintList(); paintSuggest();
        App.emit('data');
      }
    });
  }

  function onClick(e) {
    var t;
    if ((t = e.target.closest('[data-check]'))) {
      var g = D.groceries.filter(function (x) { return x.id === t.dataset.check; })[0];
      if (g && !V.pending[g.id]) check(g);
      else if (g) { delete V.pending[g.id]; t.parentNode.classList.remove('is-checking'); }
      return;
    }
    if ((t = e.target.closest('[data-qty]'))) {
      var q = D.groceries.filter(function (x) { return x.id === t.dataset.id; })[0];
      q.qty = Math.max(1, q.qty + +t.dataset.qty);
      t.parentNode.querySelector('.num').textContent = q.qty;
      paintSuggest();
      return;
    }
    if ((t = e.target.closest('[data-add]'))) return add(t.dataset.add);
    if ((t = e.target.closest('[data-store]'))) { V.store = t.dataset.store; return paintList(); }
    if ((t = e.target.closest('[data-adder]'))) { V.adder = t.dataset.adder; return paintAdder(); }
    if ((t = e.target.closest('[data-drawer]'))) { V.drawer = !V.drawer; return paintList(); }
    if ((t = e.target.closest('[data-revive]'))) {
      var r = D.groceries.filter(function (x) { return x.id === t.dataset.revive; })[0];
      r.done = false; paintList(); paintSuggest(); App.emit('data');
      return App.toast('Added back <b>' + App.esc(r.name) + '</b>', { icon: 'cart', ms: 2500 });
    }
    if ((t = e.target.closest('[data-clear]'))) {
      var gone = done();
      D.groceries = D.groceries.filter(function (x) { return gone.indexOf(x) < 0; });
      V.drawer = false;
      paintList();
      App.toast('Cleared ' + gone.length + ' items', {
        icon: 'check', undo: function () { D.groceries = D.groceries.concat(gone); paintList(); }
      });
    }
  }

  App.register('shopping', {
    show: function (el) {
      if (!V.el) { V.el = el; el.addEventListener('click', onClick); }
      render();
    }
  });
})();
