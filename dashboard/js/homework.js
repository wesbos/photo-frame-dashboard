// Full-screen "homework" reading-practice review for the kid views. One word at a time, with a
// scrubber slider under it: dragging the slider plays sound as you go, "Readino"-style.
//
// Two modes, picked per kid (passed in by clara.js / felix.js):
//   - 'letters' (Clara, 6yo, phonics stage): the slider is divided into one stop per LETTER of
//     the word. Dragging across a letter plays that letter's phonetic sound (not its alphabet
//     name — "beu" for B, not "bé") from public/audio/fr-letters/<letter>.mp3, so dragging
//     slowly across "chat" sounds out c-h-a-t. Needs window.Reading.CLIPS to NOT be involved —
//     this uses a separate small letter-sound set (see scripts/gen-letter-audio.sh).
//   - 'scrub' (Félix, 8yo, spelling stage): the slider scrubs through the single whole-word clip
///    we already generate (window.Reading.CLIPS) by setting the <audio> element's currentTime
//     proportionally to the slider position — a real audio scrubber, not re-triggering playback.
window.Homework = (function () {
  'use strict';

  var LETTERS_BASE = '/audio/fr-letters/';
  var state = null; // { words, mode, idx, personId }

  function wordList(personId) {
    if (personId === 'clara') {
      var out = [];
      window.FAMILY.claraPhonics.forEach(function (g) { out = out.concat(g.words); });
      return out;
    }
    var out2 = [];
    window.FAMILY.felixSpelling.themes.forEach(function (t) { out2 = out2.concat(t.words); });
    return out2;
  }

  function letterSlug(ch) {
    // Strip accents so e.g. "é" in a word still maps to the base letter's sound clip.
    return ch.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  }

  function renderWord(word, mode) {
    var chars = word.split('');
    if (mode === 'letters') {
      return '<div class="hw-word">' + chars.map(function (c, i) {
        return '<span class="hw-letter" data-letter-idx="' + i + '">' + App.esc(c) + '</span>';
      }).join('') + '</div>';
    }
    return '<div class="hw-word hw-word--whole">' + App.esc(word) + '</div>';
  }

  function render() {
    var s = state;
    var word = s.words[s.idx];
    var p = window.FAMILY.people[s.personId];
    var isLast = s.idx === s.words.length - 1;
    var html = '<div class="hw" style="' + App.pstyle(p) + '">' +
      '<div class="hw-progress">' + (s.idx + 1) + ' / ' + s.words.length + '</div>' +
      renderWord(word, s.mode) +
      '<div class="hw-slider-wrap">' +
      '<input type="range" class="hw-slider" min="0" max="1000" value="0" step="1">' +
      '</div>' +
      '<div class="hw-actions">' +
      '<button class="hw-btn hw-btn--ghost" data-hw-replay>' + App.icon('play', 22) + ' Réécouter</button>' +
      '<button class="hw-btn" data-hw-next>' + (isLast ? 'Terminer' : 'Suivant') + '</button>' +
      '</div></div>';
    document.querySelector('#homeworkSheet').innerHTML = html;
    wireSlider();
  }

  function playLetter(word, idx) {
    var ch = word[idx];
    if (!/[a-zA-Zàâäéèêëïîôöùûüÿçœæ]/.test(ch)) return;
    var a = new Audio(LETTERS_BASE + letterSlug(ch) + '.mp3');
    a.volume = (window.App && typeof App.soundVolume === 'number') ? App.soundVolume : 1;
    a.play().catch(function () {});
  }

  function wireSlider() {
    var s = state;
    var word = s.words[s.idx];
    var slider = document.querySelector('.hw-slider');
    var letters = document.querySelectorAll('.hw-letter');
    var wholeAudio = null;
    var lastLetterIdx = -1;

    if (s.mode === 'scrub') {
      var slug = window.Reading.CLIPS[word];
      if (slug) {
        wholeAudio = new Audio('/audio/fr/' + slug + '.mp3');
        wholeAudio.volume = (window.App && typeof App.soundVolume === 'number') ? App.soundVolume : 1;
        wholeAudio.preload = 'auto';
      }
    }

    function onInput() {
      var frac = +slider.value / 1000;
      if (s.mode === 'letters') {
        var idx = Math.min(word.length - 1, Math.floor(frac * word.length));
        if (idx !== lastLetterIdx) {
          lastLetterIdx = idx;
          playLetter(word, idx);
          letters.forEach(function (el, i) { el.classList.toggle('is-active', i === idx); });
        }
      } else if (wholeAudio && wholeAudio.duration) {
        wholeAudio.currentTime = frac * wholeAudio.duration;
        if (wholeAudio.paused) wholeAudio.play().catch(function () {});
      }
    }

    slider.addEventListener('input', onInput);
    if (wholeAudio) {
      wholeAudio.addEventListener('loadedmetadata', function () {});
      // Pause playback once the user stops dragging, so it doesn't run away to the end.
      slider.addEventListener('change', function () { if (wholeAudio) wholeAudio.pause(); });
    }
  }

  function replay() {
    var s = state, word = s.words[s.idx];
    if (s.mode === 'letters') {
      var i = 0;
      (function step() {
        if (i >= word.length) return;
        playLetter(word, i);
        document.querySelectorAll('.hw-letter').forEach(function (el, idx) { el.classList.toggle('is-active', idx === i); });
        i++;
        setTimeout(step, 550);
      })();
    } else {
      window.Reading.speak(word);
    }
  }

  function next() {
    if (state.idx >= state.words.length - 1) { App.closeSheet(); return; }
    state.idx++;
    render();
  }

  function start(personId, mode) {
    var words = wordList(personId);
    if (!words.length) return;
    state = { personId: personId, mode: mode, words: words, idx: 0 };
    App.sheet('<div id="homeworkSheet"></div>', {
      cls: 'sheet--homework',
      onMount: function (sheetEl) {
        render();
        sheetEl.addEventListener('click', function (e) {
          if (e.target.closest('[data-hw-next]')) next();
          if (e.target.closest('[data-hw-replay]')) replay();
        });
      },
      onClose: function () { state = null; }
    });
  }

  return { start: start };
})();
