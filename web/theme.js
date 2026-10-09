/* C1 Interface: theme (T-08). Loaded synchronously in <head> so the saved theme is applied
   before first paint. Choices: light (default), dark, system (follows the OS live). */
(function () {
  'use strict';
  var KEY = 'peekr-theme';
  var mq = window.matchMedia('(prefers-color-scheme: dark)');
  function pref() {
    try {
      var v = localStorage.getItem(KEY);
      return v === 'dark' || v === 'system' ? v : 'light';
    } catch (e) { return 'light'; }
  }
  function apply(p) {
    var dark = p === 'dark' || (p === 'system' && mq.matches);
    var root = document.documentElement;
    root.setAttribute('data-theme', dark ? 'dark' : 'light');
    root.setAttribute('data-theme-pref', p);
  }
  function changed() { document.dispatchEvent(new CustomEvent('peekr:theme')); }
  apply(pref());
  mq.addEventListener('change', function () { if (pref() === 'system') { apply('system'); changed(); } });
  window.addEventListener('storage', function (e) { if (e.key === KEY) { apply(pref()); changed(); } });
  window.PeekrTheme = {
    get: pref,
    systemDark: function () { return mq.matches; },
    set: function (p) {
      try { localStorage.setItem(KEY, p); } catch (e) { /* private mode: apply for this page only */ }
      apply(p);
      changed();
    }
  };
})();
