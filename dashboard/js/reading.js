// French reading-practice audio playback for the kid views. NOT Web Speech API — confirmed via
// live Chrome DevTools Protocol on the actual KPKUE DP-10B frame that window.speechSynthesis is
// undefined on this WebView (Chrome 106, Android 8.1, 32-bit armeabi-v7a). No sideloaded TTS
// engine fixes this; the JS API itself is absent. Plays pre-recorded clips instead — see
// scripts/gen-reading-audio.sh for how clips are generated.
//
// CLIPS is deliberately small right now (just enough to exercise the UI). Regenerating the
// full ~987-word set (phonics/spelling coverage + common words) is a separate follow-up — see
// FRAME-TODO.md. Any word not yet in CLIPS silently does nothing when tapped rather than
// erroring, so the UI stays usable while the audio set grows.
window.Reading = (function () {
  'use strict';

  var CLIPS = {
    'papa': 'papa', 'avion': 'avion', 'ami': 'ami',
    'ici': 'ici', 'lit': 'lit', 'tapis': 'tapis',
    'moto': 'moto', 'vélo': 'velo', 'zéro': 'zero',
    'tutu': 'tutu', 'lune': 'lune', 'rue': 'rue',
    'été': 'ete', 'école': 'ecole',
    'mère': 'mere', 'père': 'pere', 'fève': 'feve',
    'loup': 'loup', 'roue': 'roue', 'bijou': 'bijou',
    'roi': 'roi', 'moi': 'moi', 'toit': 'toit',
    'feu': 'feu', 'jeu': 'jeu', 'bleu': 'bleu',
    'maison': 'maison', 'ballon': 'ballon', 'savon': 'savon'
  };

  var current = null;

  function speak(word) {
    var slug = CLIPS[word];
    if (!slug) return;
    if (current) { current.pause(); current = null; }
    var a = new Audio('/audio/fr/' + slug + '.mp3');
    a.volume = (window.App && typeof App.soundVolume === 'number') ? App.soundVolume : 1;
    current = a;
    a.play().catch(function () { /* autoplay/file-missing — ignore, UI stays usable */ });
  }

  return { speak: speak, CLIPS: CLIPS };
})();
