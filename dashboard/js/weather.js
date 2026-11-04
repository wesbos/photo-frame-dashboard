// Live weather for Quispamsis, NB, replacing the mock D.weather with real Open-Meteo data in
// the same shape the UI already expects: { hi, lo, t: [24], c: [24], p: [24] } indexed by hour
// of the current local day. No API key needed. Refetches every 30 minutes.
(function () {
  'use strict';
  var LAT = 45.43, LON = -65.95, TZ = 'America/Halifax';
  var REFRESH_MS = 30 * 60 * 1000;

  // Open-Meteo WMO weather codes -> this dashboard's 5 condition icons.
  function iconFor(code, isDay) {
    if (code === 0) return isDay ? 'sun' : 'moon';
    if (code === 1 || code === 2) return isDay ? 'partly' : 'moon';
    if (code === 3) return 'cloud';
    if (code >= 45 && code <= 48) return 'cloud';
    if (code >= 51 && code <= 67) return 'rain';
    if (code >= 71 && code <= 77) return 'rain';
    if (code >= 80 && code <= 82) return 'rain';
    if (code >= 85 && code <= 86) return 'rain';
    if (code >= 95) return 'rain';
    return 'cloud';
  }

  function url() {
    return 'https://api.open-meteo.com/v1/forecast'
      + '?latitude=' + LAT + '&longitude=' + LON
      + '&hourly=temperature_2m,precipitation_probability,weather_code,is_day'
      + '&temperature_unit=celsius&timezone=' + encodeURIComponent(TZ)
      + '&forecast_days=2';
  }

  function applyForecast(json) {
    var hrs = json.hourly;
    var now = new Date();
    // Open-Meteo's hourly series starts at local midnight today; find today's 24 entries.
    var startIdx = hrs.time.findIndex(function (iso) {
      var d = new Date(iso);
      return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth() && d.getDate() === now.getDate();
    });
    if (startIdx < 0) startIdx = 0;

    var t = [], c = [], p = [];
    for (var i = 0; i < 24; i++) {
      var idx = startIdx + i;
      t.push(Math.round(hrs.temperature_2m[idx]));
      p.push(Math.round(hrs.precipitation_probability[idx]));
      c.push(iconFor(hrs.weather_code[idx], hrs.is_day[idx]));
    }

    window.DATA.weather = {
      hi: Math.round(Math.max.apply(null, t)),
      lo: Math.round(Math.min.apply(null, t)),
      feels: t[now.getHours()],
      humidity: window.DATA.weather ? window.DATA.weather.humidity : null,
      wind: window.DATA.weather ? window.DATA.weather.wind : null,
      t: t, c: c, p: p
    };

    if (window.App && App.emit) { App.emit('data'); App.rerender && App.rerender(); }
  }

  function fetchWeather() {
    fetch(url())
      .then(function (r) { if (!r.ok) throw new Error('weather fetch failed: ' + r.status); return r.json(); })
      .then(applyForecast)
      .catch(function (err) { console.warn('[weather] keeping previous data:', err); });
  }

  fetchWeather();
  setInterval(fetchWeather, REFRESH_MS);
})();
