// "What to wear today" widget for the kid views (Clara, 6, and Félix, 8). Picks an outfit
// category from today's live weather (DATA.weather — see weather.js) and renders a small
// cartoon drawing of that kid dressed for it. Pure render helper, no state of its own.
window.Outfit = (function () {
  'use strict';

  // Decide today's outfit from DATA.weather: lo/hi temp (°C) for the day plus the current
  // hour's condition icon ('sun'|'partly'|'cloud'|'rain'|'moon'). Order matters — rain/snow
  // beats temperature-only categories.
  function category() {
    var w = window.DATA && window.DATA.weather;
    if (!w) return 'mild';
    var hour = App.now().getHours();
    var cond = (w.c && w.c[hour]) || 'cloud';
    var lo = typeof w.lo === 'number' ? w.lo : 10;

    if (cond === 'rain') return lo <= 1 ? 'snow' : 'rain';
    if (lo <= 1) return 'snow';
    if (lo <= 10) return 'cold';
    if (lo <= 17) return 'mild';
    return 'warm';
  }

  var LABELS = {
    rain: 'Pluie — bottes et manteau de pluie',
    snow: 'Neige — habit de neige et mitaines',
    cold: 'Frisquet — tuque et manteau',
    mild: 'Doux — un chandail suffit',
    warm: 'Chaud — t-shirt et shorts'
  };

  // Shared skin/hair tones; outfit colour comes from the kid's own persona colour via --c.
  var SKIN = '#F2C49B', HAIR_BOY = '#5A3A22', HAIR_GIRL = '#7A3B1E';

  function headBoy() {
    return '<circle cx="50" cy="30" r="17" fill="' + SKIN + '"/>' +
      '<path d="M33 26c0-11 8-18 17-18s17 7 17 15c-6-3-10-7-17-7-8 0-13 4-17 10z" fill="' + HAIR_BOY + '"/>' +
      '<circle cx="44" cy="31" r="1.8" fill="#222"/><circle cx="56" cy="31" r="1.8" fill="#222"/>' +
      '<path d="M45 38q5 4 10 0" stroke="#a65" stroke-width="1.6" fill="none" stroke-linecap="round"/>';
  }

  function headGirl() {
    return '<path d="M30 34c-2-16 8-25 20-25s22 9 20 25c-3-3-4-10-6-13-3 5-9 6-14 6s-11-1-14-6c-2 3-3 10-6 13z" fill="' + HAIR_GIRL + '"/>' +
      '<circle cx="50" cy="31" r="16" fill="' + SKIN + '"/>' +
      '<path d="M31 34c6 9 13 2 10-4M69 34c-6 9-13 2-10-4" fill="' + HAIR_GIRL + '"/>' +
      '<circle cx="44" cy="32" r="1.8" fill="#222"/><circle cx="56" cy="32" r="1.8" fill="#222"/>' +
      '<path d="M45 39q5 4 10 0" stroke="#a65" stroke-width="1.6" fill="none" stroke-linecap="round"/>';
  }

  // Body variants, shared between both kids — outfit colour fills with currentColor so the
  // kid's persona colour (set via --c on the card) comes through.
  var BODIES = {
    warm: '<rect x="37" y="46" width="26" height="28" rx="10" fill="currentColor"/>' +
      '<rect x="22" y="50" width="12" height="7" rx="3.5" fill="' + SKIN + '"/>' +
      '<rect x="66" y="50" width="12" height="7" rx="3.5" fill="' + SKIN + '"/>' +
      '<rect x="40" y="72" width="8" height="14" rx="3" fill="' + SKIN + '"/>' +
      '<rect x="52" y="72" width="8" height="14" rx="3" fill="' + SKIN + '"/>' +
      '<rect x="37" y="84" width="10" height="5" rx="2" fill="#333"/><rect x="53" y="84" width="10" height="5" rx="2" fill="#333"/>',

    mild: '<rect x="35" y="46" width="30" height="30" rx="11" fill="currentColor"/>' +
      '<rect x="22" y="50" width="14" height="8" rx="4" fill="currentColor"/>' +
      '<rect x="64" y="50" width="14" height="8" rx="4" fill="currentColor"/>' +
      '<rect x="20" y="56" width="9" height="7" rx="3.5" fill="' + SKIN + '"/>' +
      '<rect x="71" y="56" width="9" height="7" rx="3.5" fill="' + SKIN + '"/>' +
      '<rect x="38" y="74" width="9" height="15" rx="3" fill="#3B4A63"/><rect x="53" y="74" width="9" height="15" rx="3" fill="#3B4A63"/>' +
      '<rect x="36" y="87" width="11" height="5" rx="2" fill="#222"/><rect x="53" y="87" width="11" height="5" rx="2" fill="#222"/>',

    cold: '<path d="M32 50q0-10 18-10t18 10v28q0 6-18 6t-18-6z" fill="currentColor"/>' +
      '<rect x="18" y="52" width="13" height="9" rx="4" fill="currentColor"/>' +
      '<rect x="69" y="52" width="13" height="9" rx="4" fill="currentColor"/>' +
      '<rect x="17" y="58" width="8" height="7" rx="3.5" fill="#444"/><rect x="75" y="58" width="8" height="7" rx="3.5" fill="#444"/>' +
      '<rect x="36" y="78" width="10" height="13" rx="3" fill="#3B4A63"/><rect x="54" y="78" width="10" height="13" rx="3" fill="#3B4A63"/>' +
      '<rect x="34" y="89" width="12" height="5" rx="2" fill="#5A3A22"/><rect x="54" y="89" width="12" height="5" rx="2" fill="#5A3A22"/>' +
      // tuque + pompom
      '<path d="M30 20q20-12 40 0q2 6-2 9-18-9-36 0q-4-3-2-9z" fill="currentColor"/><circle cx="50" cy="16" r="4" fill="#fff"/>' +
      // scarf
      '<path d="M36 46q14 8 28 0v8q-14 7-28 0z" fill="#fff" opacity=".85"/>',

    snow: '<path d="M26 52q0-12 24-12t24 12v30q0 8-24 8t-24-8z" fill="currentColor"/>' +
      '<rect x="14" y="54" width="15" height="12" rx="5" fill="currentColor"/>' +
      '<rect x="71" y="54" width="15" height="12" rx="5" fill="currentColor"/>' +
      '<circle cx="18" cy="63" r="6" fill="#fff"/><circle cx="82" cy="63" r="6" fill="#fff"/>' +
      '<rect x="33" y="82" width="13" height="14" rx="4" fill="currentColor"/><rect x="54" y="82" width="13" height="14" rx="4" fill="currentColor"/>' +
      '<rect x="31" y="92" width="16" height="7" rx="3" fill="#2B6CB0"/><rect x="53" y="92" width="16" height="7" rx="3" fill="#2B6CB0"/>' +
      '<path d="M26 22q22-14 44 0q3 8-3 11-18-10-38 0q-6-3-3-11z" fill="currentColor"/><circle cx="50" cy="17" r="4.5" fill="#fff"/>' +
      '<path d="M32 46q16 8 36 0v10q-18 8-36 0z" fill="#fff" opacity=".9"/>',

    rain: '<path d="M30 48q20-10 40 0v34q-20 8-40 0z" fill="currentColor"/>' +
      '<rect x="18" y="50" width="14" height="9" rx="4" fill="currentColor"/><rect x="68" y="50" width="14" height="9" rx="4" fill="currentColor"/>' +
      '<rect x="17" y="57" width="8" height="7" rx="3.5" fill="' + SKIN + '"/><rect x="75" y="57" width="8" height="7" rx="3.5" fill="' + SKIN + '"/>' +
      '<rect x="36" y="80" width="11" height="14" rx="3" fill="#3B4A63"/><rect x="53" y="80" width="11" height="14" rx="3" fill="#3B4A63"/>' +
      '<path d="M33 92l6 6 6-6M55 92l6 6 6-6" stroke="#2B6CB0" stroke-width="4" fill="none" stroke-linecap="round" stroke-linejoin="round"/>' +
      // rain hat brim
      '<path d="M26 22q24-10 48 0l-4 6q-20-7-40 0z" fill="currentColor"/>'
  };

  function kidSvg(kind, personId) {
    var head = kind === 'girl' ? headGirl() : headBoy();
    var body = BODIES[category()];
    return '<svg viewBox="0 0 100 100" class="outfit-fig">' + body + head + '</svg>';
  }

  function card(personId) {
    var kind = personId === 'clara' ? 'girl' : 'boy';
    var cat = category();
    return '<section class="kd-card kd-outfit" style="' + App.pstyle(personId) + '">' +
      '<div class="outfit-pic">' + kidSvg(kind, personId) + '</div>' +
      '<div class="outfit-label">' + App.esc(LABELS[cat]) + '</div>' +
      '</section>';
  }

  return { card: card, category: category };
})();
