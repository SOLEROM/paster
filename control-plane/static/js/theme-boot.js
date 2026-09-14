/* ==========================================================================
   4ColThems — PRE-PAINT THEME GUARD
   ==========================================================================
   Load this as the FIRST script in <head>, synchronously (no defer, no
   module), before any stylesheet:

       <script src="/static/js/theme-boot.js"></script>

   It puts the saved theme on <html data-theme> before the browser paints, so
   the page never shows the default theme and then snaps to the saved one.
   Deferring it, or moving it below the stylesheets, brings that flash back.

   It is a FILE rather than an inline <script> on purpose: an app serving a
   strict `script-src 'self'` CSP cannot run inline script without weakening
   the policy. If your app has no such CSP you can paste
   snippets/prepaint-inline.html instead — same logic, one less request.

   WHERE THE STORAGE KEY COMES FROM (identical in theme-toggle.js):
     1. <html data-theme-key="myapp-theme">   ← per-app, set in your template
     2. <script src="…/theme-boot.js" data-theme-key="myapp-theme">
     3. "app-theme"                           ← the neutral default
   Give each app its own key: two apps on one origin (127.0.0.1:6001 and
   :6002 are one origin per port, but a reverse proxy easily makes them one)
   would otherwise overwrite each other's choice.

   Never edit this file in place inside an app — it is a copy-in. Anything
   app-specific belongs on the attributes above.
   ========================================================================== */
(function () {
  "use strict";

  /* Mirrors themes.json — keep in sync (tests/test_js.py pins this). */
  var VALID = {
    dark: 1,
    light: 1,
    hc: 1,
    green: 1
  };

  /* The <meta name="theme-color"> value per theme: the mobile browser's own
     chrome (address bar, task switcher) is painted from it, and it has to be
     right before first paint too, not after the toggle loads. Equals each
     theme's --bg-base in css/themes.css. */
  var META_COLORS = {
    dark: "#1f1f1f",
    light: "#ffffff",
    hc: "#000000",
    green: "#0c120e"
  };

  var DEFAULT_THEME = "dark";
  var LIGHT_THEME = "light";

  var root = document.documentElement;

  function storageKey() {
    var fromRoot = root.getAttribute("data-theme-key");
    if (fromRoot) return fromRoot;
    var tag = document.currentScript;
    var fromTag = tag && tag.getAttribute("data-theme-key");
    return fromTag || "app-theme";
  }

  function saved() {
    try {
      return localStorage.getItem(storageKey());
    } catch (e) {
      return null;   // storage disabled (private mode, blocked cookies)
    }
  }

  function preferred() {
    var value = saved();
    if (value && VALID[value]) return value;
    /* No choice yet: follow the OS. matchMedia is absent on very old
       browsers, hence the guard. */
    if (window.matchMedia &&
        window.matchMedia("(prefers-color-scheme: light)").matches) {
      return LIGHT_THEME;
    }
    return DEFAULT_THEME;
  }

  function apply(theme) {
    root.setAttribute("data-theme", theme);
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta && META_COLORS[theme]) {
      meta.setAttribute("content", META_COLORS[theme]);
    }
  }

  try {
    apply(preferred());
  } catch (e) {
    /* Whatever went wrong, an unthemed page is worse than a dark one. */
    root.setAttribute("data-theme", DEFAULT_THEME);
  }
})();
