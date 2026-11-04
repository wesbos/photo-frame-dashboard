// Shared builder for the Papa/Maman persona views: that parent's events today, plus today's
// garbage/recycling reminder if one applies to them.
window.makeAdultView = function (personId) {
  'use strict';
  var V = { el: null };

  function eventRow(e) {
    var time = e.allDay ? 'Toute la journée' : App.fmt.hour(e.start) + ' – ' + App.fmt.hour(e.end);
    return '<div class="ad-event" data-ev="' + e.id + '">' +
      '<span class="ad-time">' + time + '</span>' +
      '<span class="ad-title">' + App.esc(e.title) + '</span>' +
      (e.loc ? '<span class="ad-loc">' + App.esc(e.loc) + '</span>' : '') +
      '</div>';
  }

  function scheduleCard() {
    var now = App.now();
    var allDay = App.allDayOn(now, personId);
    var timed = App.timedOn(now, personId);
    var events = allDay.concat(timed);
    return '<section class="kd-card ad-schedule" style="' + App.pstyle(personId) + '">' +
      '<header class="ch-head"><div><b>Aujourd’hui</b></div></header>' +
      (events.length ? '<div class="ad-list">' + events.map(eventRow).join('') + '</div>' :
        '<div class="kd-empty">Rien de prévu aujourd’hui.</div>') +
      '</section>';
  }

  function render() {
    V.el.innerHTML = '<div class="ad">' + scheduleCard() + '</div>';
  }

  function onClick(e) {
    var t = e.target.closest('[data-ev]');
    if (t && App.eventSheet) App.eventSheet(App.findEvent(t.dataset.ev));
  }

  return {
    show: function (el) {
      if (!V.el) { V.el = el; el.addEventListener('click', onClick); }
      render();
    }
  };
};
