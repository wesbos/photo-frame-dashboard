// Clara's persona view (6yo): shared kid-view chrome (chores/holiday/mot-du-jour/outfit) plus
// a phonics-by-sound reading practice panel ("Sons et mots").
(function () {
  'use strict';

  function readingSection() {
    var groups = window.FAMILY.claraPhonics;
    return '<section class="kd-card kd-reading">' +
      '<header class="ch-head"><div><b>Je lis en français</b><span class="ch-sub">Sons et mots</span></div></header>' +
      '<div class="kd-phonics">' + groups.map(function (g) {
        return '<div class="kd-phonics-group">' +
          '<span class="kd-sound">' + App.esc(g.sound) + '</span>' +
          '<span class="kd-phonics-words">' + g.words.map(function (w) {
            return '<button class="kd-word" data-say="' + App.esc(w) + '">' + App.icon('play', 16) + App.esc(w) + '</button>';
          }).join('') + '</span></div>';
      }).join('') + '</div></section>';
  }

  App.register('clara', window.makeKidView('clara', readingSection));
})();
