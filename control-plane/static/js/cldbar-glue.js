// paster — the Claude window/week status bar in the footer.
//
// The bar itself is remdev's service, embedded through the shared cldBar
// kit (solBench/cldBar). static/js/cldbar.js is a *copy-in* of that kit —
// refreshed by run.sh, never edited here. This file is the app's policy
// layer: where the bar mounts, which remdev origin it uses, and how the
// four 4ColThems themes map onto remdev's theme slugs.
"use strict";

// 4ColThems theme id -> remdev theme slug. Keys mirror themes.json; an
// unmapped theme would fall back to the dark slug, which on Light Modern
// shows up as an opaque dark strip (tests/test_cldbar_embed.py pins it).
const CLDBAR_THEME = {
  dark: "vscode-dark",
  light: "vscode-light",
  hc: "vscode-hc",
  green: "vscode-green",
};

// The kit needs the theme slug and, only when the env pins one, an explicit
// remdev origin. With no pin it derives the origin from the page's own
// address — a server-rendered loopback would point every remote viewer at
// their own machine and blank the bar (cldBar readme, "the loopback pitfall").
function cldbarOptions() {
  const slot = $("#cldbar-slot");
  const pinned = slot && slot.dataset.remdevUrl;
  const theme = typeof currentTheme === "function" ? currentTheme() : "dark";
  return {
    theme: CLDBAR_THEME[theme] || CLDBAR_THEME.dark,
    ...(pinned ? { url: pinned } : {}),
  };
}

function setupCldBar() {
  const slot = $("#cldbar-slot");
  if (!slot || !window.cldBar) return;   // kit not copied in — no footer bar
  try {
    cldBar.mountCldBar(slot, cldbarOptions());
  } catch (err) {
    console.error("cldBar: not mounted —", err.message);
  }
  // 4ColThems announces switches on window; never wrap setTheme.
  window.addEventListener("themechange", syncCldBar);
}

// Re-point the embed when the theme changes. The iframe is remounted rather
// than its src patched: the kit owns the color-scheme derivation, and an
// iframe whose color-scheme disagrees with the embedded page's loses
// transparency and paints an opaque canvas over the footer.
function syncCldBar() {
  const slot = $("#cldbar-slot");
  if (!slot || !window.cldBar) return;
  const frame = slot.querySelector("iframe.cldbar-embed");
  if (frame && typeof cldBar.cldBarUrl === "function" && frame.src === cldBar.cldBarUrl(cldbarOptions())) return;
  if (frame) frame.remove();
  try { cldBar.mountCldBar(slot, cldbarOptions()); } catch (err) { console.error("cldBar:", err.message); }
}
