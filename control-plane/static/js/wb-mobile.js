/* ==========================================================================
   vsCodeFront — wb-mobile.js: the small-screen behaviours
   ==========================================================================
   Classic script, `defer`, after wb-overlays.js. The layout itself is CSS
   (css/mobile.css); this file is only the behaviour the CSS cannot express:
   the drawer, the sheet, the bottom tab bar and its ⋯ overflow. It reuses
   the shell's hidden-state helpers rather than introducing a second
   component. Ported from soldo, the family's one phone layout.

   Markup it expects (snippets/shell.html ships all of it):
     #btn-drawer        ☰ in the title bar (display:none on desktop)
     #bottom-tabs       an EMPTY <nav class="bottom-tabs"> — filled here from
                        the activity items: the first group's views, then ⋯
     #drawer-scrim      the dim layer behind an open drawer
     .sheet             any element that should slide up full-screen on a
                        phone (an inspector, a detail pane); openSheet(el)

   The breakpoint is read from CSS (--wb-mobile-max on :root, default 768px)
   so the media query and the JS cannot disagree.

   Exposes: isMobile, openDrawer, closeDrawer, openSheet, closeSheet,
   setupMobile.
   ========================================================================== */
"use strict";

const MOBILE_BREAKPOINT_DEFAULT = 768;
const MOBILE_MAX_BOTTOM_TABS = 3;

function mobileBreakpoint() {
  try {
    const v = parseInt(getComputedStyle(document.documentElement).getPropertyValue("--wb-mobile-max"), 10);
    return Number.isFinite(v) ? v : MOBILE_BREAKPOINT_DEFAULT;
  } catch (_) { return MOBILE_BREAKPOINT_DEFAULT; }
}

function isMobile() {
  return !!(window.matchMedia && window.matchMedia(`(max-width: ${mobileBreakpoint()}px)`).matches);
}

/* ----- Drawer (the sidebar on a phone) ----- */
function openDrawer() {
  if (!isMobile()) return;
  const sidebar = $(".sidebar");
  const scrim = $("#drawer-scrim");
  if (sidebar) sidebar.classList.add("drawer-open");
  if (scrim) scrim.classList.add("open");
}

function closeDrawer() {
  const sidebar = $(".sidebar");
  const scrim = $("#drawer-scrim");
  if (sidebar) sidebar.classList.remove("drawer-open");
  if (scrim) scrim.classList.remove("open");
}

function drawerOpen() {
  const sidebar = $(".sidebar");
  return !!sidebar && sidebar.classList.contains("drawer-open");
}

/* ----- Sheet (a detail pane on a phone) ----- */
function openSheet(node) {
  if (!isMobile()) return;
  const target = node || $(".sheet");
  if (target) target.classList.add("sheet-open");
}

function closeSheet(node) {
  const targets = node ? [node] : $$(".sheet.sheet-open");
  targets.forEach((t) => t.classList.remove("sheet-open"));
}

function anySheetOpen() { return $$(".sheet.sheet-open").length > 0; }

/* ----- Bottom tab bar ----- */
/** The first activity group's views become bottom tabs (up to three); every
    other view, the theme and the registered "more" commands go behind ⋯. */
function buildBottomTabs() {
  const bar = $("#bottom-tabs");
  if (!bar || bar.children.length) return;
  const primary = $$(".activity-group:not(.activity-bottom) .activity-item[data-view]")
    .slice(0, MOBILE_MAX_BOTTOM_TABS);
  for (const item of primary) {
    const meta = VIEWS[item.dataset.view];
    if (!meta) continue;
    const b = el("button", "", `<span class="codicon codicon-${esc(meta.icon)}"></span><span>${esc(meta.label)}</span>`);
    b.dataset.view = item.dataset.view;
    b.addEventListener("click", () => { closeSheet(); switchView(item.dataset.view); });
    bar.appendChild(b);
  }
  const more = el("button", "", `<span class="codicon codicon-ellipsis"></span><span>More</span>`);
  more.id = "btn-more-tabs";
  more.addEventListener("click", openOverflowTabs);
  bar.appendChild(more);
}

function openOverflowTabs() {
  const shown = new Set($$("#bottom-tabs button[data-view]").map((b) => b.dataset.view));
  const rows = [];
  for (const [id, meta] of Object.entries(VIEWS)) {
    if (shown.has(id)) continue;
    rows.push(`<button class="btn secondary" data-more-view="${esc(id)}">
      <span class="codicon codicon-${esc(meta.icon)}"></span>${esc(meta.label)}</button>`);
  }
  for (const cmd of COMMANDS.values()) {
    if (!cmd.mobile) continue;
    if (cmd.when && !cmd.when()) continue;
    rows.push(`<button class="btn secondary" data-more-cmd="${esc(cmd.id)}">
      <span class="codicon codicon-${esc(cmd.icon)}"></span>${esc(cmd.label)}</button>`);
  }
  rows.push(`<button class="btn secondary" data-more-theme="1">
    <span class="codicon codicon-color-mode"></span>Cycle theme</button>`);
  const body = openModal("More", `<div class="ops-bar">${rows.join("")}</div>`,
    [{ label: "Close", secondary: true, onClick: closeModal }]);
  if (!body) return;
  $$("[data-more-view]", body).forEach((b) => b.addEventListener("click", () => {
    closeModal(); switchView(b.dataset.moreView);
  }));
  $$("[data-more-cmd]", body).forEach((b) => b.addEventListener("click", () => {
    closeModal(); runCommand(b.dataset.moreCmd);
  }));
  $$("[data-more-theme]", body).forEach((b) => b.addEventListener("click", () => {
    closeModal(); cycleTheme();
  }));
}

/* ----- Boot ----- */
function setupMobile() {
  const drawerBtn = $("#btn-drawer");
  if (drawerBtn) drawerBtn.addEventListener("click", () => {
    if (drawerOpen()) closeDrawer(); else openDrawer();
  });
  const scrim = $("#drawer-scrim");
  if (scrim) scrim.addEventListener("click", closeDrawer);
  $$(".sheet-close").forEach((b) => b.addEventListener("click", () => closeSheet()));
  buildBottomTabs();
  // Mirror the active view onto the bar now that it exists.
  $$("#bottom-tabs button[data-view]").forEach((b) =>
    b.classList.toggle("active", b.dataset.view === activeView()));

  // Escape closes the sheet before it closes anything else, matching the
  // back-button expectation on a phone (capture phase wins over the
  // document-level handler in wb-overlays.js).
  document.addEventListener("keydown", (ev) => {
    if (ev.key !== "Escape" || !isMobile()) return;
    if (anySheetOpen()) { ev.stopPropagation(); closeSheet(); }
    else if (drawerOpen()) { ev.stopPropagation(); closeDrawer(); }
  }, true);

  // Leaving the small layout must not strand a drawer or sheet mid-animation.
  window.addEventListener("resize", () => {
    if (!isMobile()) { closeDrawer(); closeSheet(); }
  });
}
