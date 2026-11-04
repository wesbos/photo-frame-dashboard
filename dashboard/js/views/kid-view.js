// Shared builder for the Clara and Félix persona views: chores (room + bath routine + paid
// task menu), a holiday countdown, "mot du jour", and a what-to-wear-today widget, plus a
// reading-practice panel supplied by the caller (French copy throughout).
window.makeKidView = function (personId, readingSection) {
  'use strict';
  var F = window.FAMILY;
  var V = { el: null };

  var DOW_FR = ['Dim', 'Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam'];

  function person() { return F.people[personId]; }
  function r() { return F.routine[personId]; }

  function isBathNight(now) { return F.bathNights.indexOf(now.getDay()) !== -1; }

  function choreCard() {
    var p = person(), rt = r(), now = App.now();
    var bathToday = isBathNight(now);
    var items = [
      { key: 'room', label: 'Ranger sa chambre', emoji: '🧸', done: rt.room }
    ];
    if (bathToday) items.push({ key: 'bath', label: 'Bain', emoji: '🛁', done: rt.bath });
    var picked = rt.picked.map(function (tid) {
      var t = F.taskMenu.filter(function (x) { return x.id === tid; })[0];
      return t && { key: 'task:' + t.id, label: t.title, emoji: t.emoji, done: true, price: t.price };
    }).filter(Boolean);

    var earned = rt.earned;
    return '<section class="kd-card" style="' + App.pstyle(p) + '">' +
      '<header class="ch-head"><div><b>Mes tâches</b><span class="ch-sub">' + DOW_FR[now.getDay()] + '</span></div>' +
      '<span class="kd-earned">' + App.icon('star', 18, 'i--fill') + '<span class="num">' + earned + ' $</span></span>' +
      '</header>' +
      '<div class="ch-list">' +
      items.map(function (it) {
        return '<button class="ch' + (it.done ? ' is-done' : '') + '" data-routine="' + it.key + '">' +
          '<span class="ch-emoji">' + it.emoji + '<span class="ch-check"><svg viewBox="0 0 24 24" width="30" height="30"><path d="M5 12.5l4.5 4.5L19 7"/></svg></span></span>' +
          '<span class="ch-text"><b>' + App.esc(it.label) + '</b></span></button>';
      }).join('') +
      picked.map(function (it) {
        return '<div class="ch is-done"><span class="ch-emoji">' + it.emoji + '<span class="ch-check is-done"><svg viewBox="0 0 24 24" width="30" height="30"><path d="M5 12.5l4.5 4.5L19 7"/></svg></span></span>' +
          '<span class="ch-text"><b>' + App.esc(it.label) + '</b><small>+1 $</small></span></div>';
      }).join('') +
      '<button class="kd-add" data-add-task>' + App.icon('plus', 22) + ' Ajouter une tâche (1 $)</button>' +
      '</div></section>';
  }

  function taskPicker() {
    var rt = r();
    var available = F.taskMenu.filter(function (t) { return rt.picked.indexOf(t.id) === -1; });
    App.sheet('<div class="sheet-pad"><h2 class="serif sheet-h">Choisis une tâche</h2>' +
      '<div class="kd-menu">' + available.map(function (t) {
        return '<button class="kd-menu-item" data-pick="' + t.id + '"><span class="kd-menu-emoji">' + t.emoji + '</span><span>' + App.esc(t.title) + '</span><span class="kd-menu-price">+1 $</span></button>';
      }).join('') + '</div></div>', {
      onMount: function (s, close) {
        s.addEventListener('click', function (e) {
          var b = e.target.closest('[data-pick]');
          if (!b) return;
          rt.picked.push(b.dataset.pick);
          rt.earned += 1;
          close();
          render();
        });
      }
    });
  }

  function holidayCard() {
    var h = window.Holidays.next();
    return '<section class="kd-card kd-holiday">' +
      '<div class="kd-holiday-emoji">' + h.emoji + '</div>' +
      '<div><div class="label">Dans ' + h.days + ' jour' + (h.days === 1 ? '' : 's') + '</div>' +
      '<h2 class="serif">' + App.esc(h.name) + '</h2></div>' +
      '</section>';
  }

  // 5 words picked fresh each day from the shared common-word bank, different for Clara vs
  // Félix, same all day.
  function wordOfDayCard() {
    var words = F.wordOfDay(personId, 5);
    return '<section class="kd-card kd-wotd">' +
      '<header class="ch-head"><div><b>Mot du jour</b><span class="ch-sub">5 nouveaux mots</span></div></header>' +
      '<div class="kd-phonics-words kd-wotd-words">' + words.map(function (w) {
        return '<button class="kd-word" data-say="' + App.esc(w) + '">' + App.icon('play', 16) + App.esc(w) + '</button>';
      }).join('') + '</div></section>';
  }

  function render() {
    V.el.innerHTML = '<div class="kd">' +
      '<div class="kd-col">' + choreCard() + holidayCard() + wordOfDayCard() + window.Outfit.card(personId) + '</div>' +
      '<div class="kd-col">' + readingSection() + '</div>' +
      '</div>';
  }

  function onClick(e) {
    var t;
    if ((t = e.target.closest('[data-add-task]'))) return taskPicker();
    if ((t = e.target.closest('[data-routine]'))) {
      var rt = r(), key = t.dataset.routine;
      rt[key] = !rt[key];
      render();
      return;
    }
    if ((t = e.target.closest('[data-say]'))) {
      window.Reading.speak(t.dataset.say);
      return;
    }
  }

  return {
    show: function (el) {
      if (!V.el) { V.el = el; el.addEventListener('click', onClick); }
      render();
    }
  };
};
