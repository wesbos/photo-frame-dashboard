// Shared sound volume (persisted) plus a simple Web Audio beep, used for a "the bus is coming"
// style alert. Not an <audio> clip — generated tone, so it needs no asset file.
(function () {
  'use strict';

  var KEY = 'famillehq.soundVolume';
  var stored = parseFloat(localStorage.getItem(KEY));
  window.App = window.App || {};
  App.soundVolume = isNaN(stored) ? 1 : Math.min(1, Math.max(0, stored));

  App.setSoundVolume = function (v) {
    App.soundVolume = Math.min(1, Math.max(0, v));
    try { localStorage.setItem(KEY, String(App.soundVolume)); } catch (e) {}
  };

  var ctx = null;
  function audioCtx() {
    if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)();
    return ctx;
  }

  App.beep = function (freq, durationMs) {
    if (App.soundVolume <= 0) return;
    var ac = audioCtx();
    var osc = ac.createOscillator(), gain = ac.createGain();
    osc.frequency.value = freq || 880;
    gain.gain.value = 0.2 * App.soundVolume;
    osc.connect(gain).connect(ac.destination);
    osc.start();
    osc.stop(ac.currentTime + (durationMs || 300) / 1000);
  };

  window.BusAlarm = {
    ring: function () { App.beep(880, 250); setTimeout(function () { App.beep(880, 250); }, 350); }
  };
})();
