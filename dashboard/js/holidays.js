// Next-holiday countdown for the kid views. Always computed relative to App.now(), never
// cached across days — the frame's clock can reset on power loss (see CLAUDE.md), so this
// must stay correct the moment the clock is fixed rather than carrying a stale answer.
window.Holidays = (function () {
  'use strict';

  function next() {
    var now = App.now();
    var today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    var best = null, bestDiff = Infinity;

    window.FAMILY.holidays.forEach(function (h) {
      var year = now.getFullYear();
      var d = new Date(year, h.month - 1, h.day);
      if (d < today) d = new Date(year + 1, h.month - 1, h.day);
      var diff = Math.round((d - today) / 864e5);
      if (diff < bestDiff) { bestDiff = diff; best = h; }
    });

    return { name: best.name, emoji: best.emoji, days: bestDiff };
  }

  return { next: next };
})();
