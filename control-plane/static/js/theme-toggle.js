/* ==========================================================================
   4ColThems — theme toggle (dependency-free, no build step)
   ==========================================================================
   One button in your chrome cycles the four themes:

       dark → light → hc → green → (back to dark)

   Include it deferred, anywhere after the pre-paint guard:

       <script defer src="/static/js/theme-toggle.js"></script>

   On load it wires the button with id="theme-cycle" (markup in
   snippets/toggle-button.html) and, if the pre-paint guard did not run,
   applies the saved theme itself. Each switch:

     - writes <html data-theme="…">           → the whole UI re-skins via CSS
     - persists the choice in localStorage    → survives reloads
     - repaints <meta name="theme-color">     → mobile browser chrome follows
     - dispatches `themechange` on window     → surfaces CSS cannot reach

   THAT EVENT IS THE INTEGRATION POINT. A terminal canvas (xterm.js/ttyd) and
   a cross-origin iframe (cldBar) are invisible to CSS custom properties;
   they re-skin by listening:

       window.addEventListener("themechange", function (e) {
         applyTerminalTheme(e.detail.theme);   // also: e.detail.previous
       });

   It fires on *switches*, not on load — read Theme4Col.current() when your
   consumer initialises.

   PER-APP SETTINGS — attributes, never edits to this file:
     <html data-theme-key="myapp-theme">   storage key (see theme-boot.js)
     <html data-theme-icons="codicon">     use VS Code codicon glyphs instead
                                           of the inline SVG shipped here
   Anything else app-specific belongs in your own JS, reading the API below.
   ========================================================================== */
(function () {
  "use strict";

  /* ---- mirrors of themes.json (tests/test_js.py pins every one) -------- */

  var THEMES = ["dark", "light", "hc", "green"];

  var LABELS = {
    dark: "Dark Modern",
    light: "Light Modern",
    hc: "Dark High Contrast",
    green: "Garage Green"
  };

  /* VS Code codicon glyph per theme — used only with data-theme-icons="codicon",
     for apps that already load the codicon font. */
  var CODICONS = {
    dark: "circle-filled",
    light: "circle-outline",
    hc: "color-mode",
    green: "terminal"
  };

  /* Single-character glyph per theme — used with data-theme-icons="glyph",
     for apps that draw their chrome with text glyphs and want no injected
     markup at all (it is written with textContent, not innerHTML). */
  var GLYPHS = {
    dark: "☾",
    light: "☀",
    hc: "◐",
    green: "❯"
  };

  /* remdev theme slug per theme, for the cldBar status-bar embed
     (solBench/cldBar). Every app used to repeat this map in its own glue. */
  var SLUGS = {
    dark: "vscode-dark",
    light: "vscode-light",
    hc: "vscode-hc",
    green: "vscode-green"
  };

  /* <meta name="theme-color"> per theme == that theme's --bg-base. */
  var META_COLORS = {
    dark: "#1f1f1f",
    light: "#ffffff",
    hc: "#000000",
    green: "#0c120e"
  };

  /* Inline SVG icon for the CURRENT theme — no icon font required. They
     stroke and fill with `currentColor`, so they inherit the button's colour
     (and the accent tint when it carries .active). */
  var ICONS = {
    // crescent moon
    dark: '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M13.2 9.6A5.6 5.6 0 0 1 6.4 2.8a5.6 5.6 0 1 0 6.8 6.8z" fill="currentColor"/></svg>',
    // sun with rays
    light: '<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="3.1" fill="currentColor"/><g stroke="currentColor" stroke-width="1.3" stroke-linecap="round"><path d="M8 1.4v1.8M8 12.8v1.8M1.4 8h1.8M12.8 8h1.8M3.3 3.3l1.3 1.3M11.4 11.4l1.3 1.3M12.7 3.3l-1.3 1.3M4.6 11.4l-1.3 1.3"/></g></svg>',
    // split circle = high contrast
    hc: '<svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" stroke-width="1.4"/><path d="M8 2a6 6 0 0 0 0 12z" fill="currentColor"/></svg>',
    // terminal window with prompt
    green: '<svg viewBox="0 0 16 16" aria-hidden="true"><rect x="1.5" y="2.5" width="13" height="11" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M4 6l2.4 2L4 10" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/><path d="M8.6 10.4h3.4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>'
  };

  var BUTTON_ID = "theme-cycle";
  var ICON_ID = "theme-cycle-icon";

  var root = document.documentElement;
  var script = document.currentScript;   // captured now; null once deferred code runs later

  /* ---- per-app configuration, read off the page --------------------- */

  /* Identical resolution order to theme-boot.js — the two must agree or the
     guard restores one theme and the toggle immediately persists another. */
  function storageKey() {
    var fromRoot = root.getAttribute("data-theme-key");
    if (fromRoot) return fromRoot;
    var fromTag = script && script.getAttribute("data-theme-key");
    return fromTag || "app-theme";
  }

  var KEY = storageKey();

  /* "svg" (default) | "codicon" | "glyph" — see render(). */
  function iconMode() {
    var mode = root.getAttribute("data-theme-icons");
    return (mode === "codicon" || mode === "glyph") ? mode : "svg";
  }

  /* ---- state -------------------------------------------------------- */

  function current() {
    var theme = root.getAttribute("data-theme");
    return THEMES.indexOf(theme) !== -1 ? theme : THEMES[0];
  }

  function stored() {
    try {
      return localStorage.getItem(KEY);
    } catch (e) {
      return null;
    }
  }

  function persist(theme) {
    try {
      localStorage.setItem(KEY, theme);
    } catch (e) {
      /* Storage disabled: the switch still applies, it just won't survive
         the next reload. Not worth failing the click over. */
    }
  }

  function set(name) {
    if (THEMES.indexOf(name) === -1) return;   // unknown id: ignore, don't paint
    var previous = current();
    root.setAttribute("data-theme", name);
    persist(name);
    paintChrome(name);
    render();
    announce(name, previous);
  }

  function cycle() {
    set(THEMES[(THEMES.indexOf(current()) + 1) % THEMES.length]);
  }

  /* ---- surfaces outside CSS's reach ---------------------------------- */

  function paintChrome(theme) {
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta && META_COLORS[theme]) {
      meta.setAttribute("content", META_COLORS[theme]);
    }
  }

  function announce(theme, previous) {
    try {
      window.dispatchEvent(new CustomEvent("themechange", {
        detail: { theme: theme, previous: previous }
      }));
    } catch (e) {
      /* No CustomEvent constructor (very old browser): the CSS half of the
         switch has already happened, only the listeners miss out. */
    }
  }

  /* ---- the button ---------------------------------------------------- */

  function render() {
    var button = document.getElementById(BUTTON_ID);
    if (!button) return;                       // app without a switcher: fine
    var theme = current();
    var host = document.getElementById(ICON_ID) || button;
    var mode = iconMode();
    if (mode === "codicon") {
      host.className = "codicon codicon-" + (CODICONS[theme] || CODICONS[THEMES[0]]);
    } else if (mode === "glyph") {
      host.textContent = GLYPHS[theme] || GLYPHS[THEMES[0]];
    } else {
      host.innerHTML = ICONS[theme] || ICONS[THEMES[0]];
    }
    var title = "Theme: " + (LABELS[theme] || theme) + " — click to cycle";
    button.title = title;
    button.setAttribute("aria-label", title);
    button.classList.add("active");
  }

  function init() {
    /* The pre-paint guard normally did this already. Without it (or with a
       hand-edited attribute) restore the saved theme now — a beat later than
       ideal, but correct. */
    if (THEMES.indexOf(root.getAttribute("data-theme")) === -1) {
      var saved = stored();
      root.setAttribute("data-theme",
                        THEMES.indexOf(saved) !== -1 ? saved : THEMES[0]);
    }
    /* Unconditionally, because the guard may have run before the
       <meta name="theme-color"> tag existed — it only finds tags already
       parsed above it in <head>. By now the whole head is there. */
    paintChrome(current());
    var button = document.getElementById(BUTTON_ID);
    if (button) button.addEventListener("click", cycle);
    render();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();                                    // included late / injected
  }

  /* ---- public API ----------------------------------------------------
     Theme4Col.set("green");        apply + persist + announce
     Theme4Col.cycle();             next in order
     Theme4Col.current();           "dark" | "light" | "hc" | "green"
     Theme4Col.list                 a fresh copy of the cycle order
     Theme4Col.labels               a fresh copy of the id → label map
     Theme4Col.meta("hc")           everything the kit knows about one theme
     Theme4Col.remdevSlug("hc")     cldBar/remdev slug ("vscode-hc")
     Theme4Col.key                  the resolved localStorage key

     `list` and `labels` hand out copies: app code that mutates what it gets
     back must not be able to corrupt the cycle. */
  var api = {
    set: set,
    cycle: cycle,
    current: current,
    meta: function (name) {
      var theme = THEMES.indexOf(name) !== -1 ? name : THEMES[0];
      return {
        theme: theme,
        label: LABELS[theme],
        codicon: CODICONS[theme],
        remdevSlug: SLUGS[theme],
        metaColor: META_COLORS[theme]
      };
    },
    remdevSlug: function (name) {
      return SLUGS[name] || SLUGS[THEMES[0]];
    },
    key: KEY
  };

  Object.defineProperty(api, "list", {
    enumerable: true,
    get: function () { return THEMES.slice(); }
  });
  Object.defineProperty(api, "labels", {
    enumerable: true,
    get: function () {
      var copy = {};
      for (var i = 0; i < THEMES.length; i++) copy[THEMES[i]] = LABELS[THEMES[i]];
      return copy;
    }
  });

  window.Theme4Col = api;
})();
