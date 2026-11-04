// Félix's persona view (8yo): shared kid-view chrome (chores/holiday/mot-du-jour/outfit) plus
// a theme-grouped spelling practice panel ("Mots à pratiquer").
(function () {
  'use strict';

  function readingSection() {
    var groups = window.FAMILY.felixSpelling.themes;
    return '<section class="kd-card kd-reading">' +
      '<header class="ch-head"><div><b>Je lis en français</b><span class="ch-sub">Mots à pratiquer</span></div></header>' +
      '<div class="kd-phonics">' + groups.map(function (g) {
        return '<div class="kd-phonics-group kd-phonics-group--stack">' +
          '<span class="kd-theme-label">' + App.esc(g.theme) + '</span>' +
          '<span class="kd-phonics-words">' + g.words.map(function (w) {
            return '<button class="kd-word" data-say="' + App.esc(w) + '">' + App.icon('play', 16) + App.esc(w) + '</button>';
          }).join('') + '</span></div>';
      }).join('') + '</div></section>';
  }

  App.register('felix', window.makeKidView('felix', readingSection));
})();
