/* ==========================================================================
   vsCodeFront — wb-shell.js: views, tabs, breadcrumbs, sidebar, status
   ==========================================================================
   Classic script, `defer`, after wb-core.js. Drives the static skeleton in
   snippets/shell.html:

     .activitybar .activity-item[data-view]   one button per view
     .panels      .tab-panel#panel-<view>     one section per view
     .tabstrip    .tabs                       editor-style tabs (rendered)
     .breadcrumbs                             optional row under the tabs
     .sidebar + .sidebar-resizer              the tree and its drag handle
     #conn-pill/#conn-dot/#conn-label         realtime connection state

   VIEWS ARE DECLARED IN MARKUP, NOT HERE. scanViews() reads every
   .activity-item[data-view]: its label is the .activity-label text (or the
   title attribute), its icon the codicon class, and data-sidebar="0" marks
   a view that hides the project tree (Help, Config — utility views whose
   panel carries its own tree). Adding a view = adding a button and a panel.

   TAB MODES — on the .tabstrip element:
     data-tabs="multi"  (default) VS Code: every visited view gets a tab with
                         a close button; the open set persists.
     data-tabs="single" what resman/mentora/solGit/soldo do: one tab showing
                         the active view; clicking it toggles the sidebar.

   STORAGE (prefixed by <html data-app>): view, tabs, sidebar-w,
   sidebar-hidden.

   Exposes: VIEWS, switchView (alias switchTab), closeTab, viewMeta,
   setBreadcrumbs, setBadge, applySidebarWidth, setSidebarHidden,
   toggleSidebar, revealSidebar, setConn, currentTheme, setTheme, cycleTheme,
   setupShell.
   ========================================================================== */
"use strict";

/* ---------- Views ---------- */
const VIEWS = {};               // id → { label, icon, sidebar, panel }
const shellState = {
  activeView: null,
  openTabs: [],
  tabMode: "multi",
  defaultView: null,
};

function viewMeta(name) { return VIEWS[name] || null; }

function scanViews() {
  for (const key of Object.keys(VIEWS)) delete VIEWS[key];
  $$(".activity-item[data-view]").forEach((btn, i) => {
    const id = btn.dataset.view;
    const icon = ($$(".codicon", btn)[0] || { className: "" }).className
      .split(/\s+/).find((c) => c.startsWith("codicon-") && c !== "codicon-")
      || "codicon-circle-outline";
    const labelEl = $(".activity-label", btn);
    VIEWS[id] = {
      label: (labelEl && labelEl.textContent.trim()) || btn.getAttribute("title") || id,
      icon: icon.replace(/^codicon-/, ""),
      sidebar: btn.dataset.sidebar !== "0",
      panel: $(`#panel-${id}`) || $(`#tab-${id}`),
      order: i,
    };
    if (!shellState.defaultView) shellState.defaultView = id;
  });
  const strip = $(".tabstrip");
  shellState.tabMode = strip && strip.dataset.tabs === "single" ? "single" : "multi";
}

/** Switch the active view. Stamps .active on the activity item, the tab and
    the panel, hides the sidebar for data-sidebar="0" views, and persists. */
function switchView(name) {
  const meta = VIEWS[name];
  if (!meta) return false;
  shellState.activeView = name;
  if (!shellState.openTabs.includes(name)) shellState.openTabs.push(name);
  $$(".activity-item[data-view]").forEach((b) =>
    b.classList.toggle("active", b.dataset.view === name));
  $$("#bottom-tabs button[data-view]").forEach((b) =>
    b.classList.toggle("active", b.dataset.view === name));
  $$(".tab-panel").forEach((p) =>
    p.classList.toggle("active", p === meta.panel));
  const workbench = $(".workbench");
  if (workbench) workbench.classList.toggle("no-sidebar", !meta.sidebar);
  renderTabs();
  renderBreadcrumbs();
  store("view", name);
  store("tabs", JSON.stringify(shellState.openTabs));
  if (typeof closeDrawer === "function") closeDrawer();
  document.dispatchEvent(new CustomEvent("viewchange", { detail: { view: name } }));
  return true;
}
const switchTab = switchView;   // the apps' name for it

function activeView() { return shellState.activeView; }

function closeTab(name) {
  const i = shellState.openTabs.indexOf(name);
  if (i === -1) return;
  shellState.openTabs.splice(i, 1);
  if (shellState.openTabs.length === 0) shellState.openTabs.push(shellState.defaultView);
  if (shellState.activeView === name) {
    switchView(shellState.openTabs[Math.max(0, i - 1)]);
  } else {
    renderTabs();
    store("tabs", JSON.stringify(shellState.openTabs));
  }
}

function renderTabs() {
  const host = $(".tabstrip .tabs");
  if (!host) return;
  const ids = shellState.tabMode === "single"
    ? [shellState.activeView].filter(Boolean)
    : shellState.openTabs.filter((id) => VIEWS[id]);
  host.innerHTML = "";
  for (const id of ids) {
    const meta = VIEWS[id];
    const active = id === shellState.activeView;
    const close = shellState.tabMode === "multi"
      ? `<button class="tab-close" title="Close" aria-label="Close ${esc(meta.label)}">
           <span class="codicon codicon-close"></span></button>` : "";
    const tab = el("div", "tab" + (active ? " active" : ""),
      `<span class="codicon codicon-${esc(meta.icon)}"></span><span>${esc(meta.label)}</span>${close}`);
    tab.setAttribute("role", "tab");
    tab.setAttribute("aria-selected", active ? "true" : "false");
    tab.dataset.view = id;
    if (shellState.tabMode === "single") {
      tab.title = "Show or hide the sidebar";
      tab.tabIndex = 0;
      wireButton(tab, toggleSidebar);
    } else {
      tab.addEventListener("click", () => switchView(id));
      const x = $(".tab-close", tab);
      if (x) x.addEventListener("click", (e) => { e.stopPropagation(); closeTab(id); });
    }
    host.appendChild(tab);
  }
}

/* ---------- Breadcrumbs ---------- */
const breadcrumbTails = {};   // view → [{icon, label}] — per view, like VS Code's per-editor crumbs

/** setBreadcrumbs([{icon, label}, …], view?) appends app context after the
    view crumb (a selected item, an open document). Call with [] to clear. */
function setBreadcrumbs(parts, view) {
  breadcrumbTails[view || shellState.activeView] = Array.isArray(parts) ? parts : [];
  renderBreadcrumbs();
}

function renderBreadcrumbs() {
  const bc = $(".breadcrumbs");
  const meta = VIEWS[shellState.activeView];
  if (!bc || !meta) return;
  const sep = `<span class="breadcrumb-sep codicon codicon-chevron-right"></span>`;
  const crumb = (c) => `<span class="codicon codicon-${esc(c.icon || "circle-small")}"></span><span>${esc(c.label)}</span>`;
  const parts = [crumb({ icon: bc.dataset.icon || "repo", label: bc.dataset.root || WB_APP }),
    sep, crumb(meta)];
  for (const part of breadcrumbTails[shellState.activeView] || []) parts.push(sep, crumb(part));
  bc.innerHTML = parts.join("");
}

/* ---------- Activity badges ---------- */
/** setBadge("runs", 3) — the counter on an activity item; 0/null hides it. */
function setBadge(view, count) {
  const btn = $(`.activity-item[data-view="${view}"]`);
  if (!btn) return;
  let badge = $(".activity-badge", btn);
  if (!badge) {
    badge = el("span", "activity-badge");
    btn.insertBefore(badge, $(".activity-label", btn));
  }
  const n = Number(count) || 0;
  badge.hidden = n <= 0;
  badge.textContent = n > 99 ? "99+" : String(n);
}

/* ---------- Sidebar: hide toggle + drag resize ---------- */
/* Bounds come from 4ColThems metrics.css (--sidebar-min-w / --sidebar-max-w
   / --sidebar-w); the fallbacks are those same values. */
function sidebarBound(token, fallback) {
  try {
    const v = parseInt(getComputedStyle(document.documentElement).getPropertyValue(token), 10);
    return Number.isFinite(v) ? v : fallback;
  } catch (_) { return fallback; }
}
function sidebarMinW() { return sidebarBound("--sidebar-min-w", 150); }
function sidebarMaxW() { return sidebarBound("--sidebar-max-w", 500); }
function sidebarDefaultW() { return 300; }

function applySidebarWidth(px) {
  const w = Math.min(sidebarMaxW(), Math.max(sidebarMinW(), Math.round(px)));
  document.documentElement.style.setProperty("--sidebar-w", w + "px");
  return w;
}

function loadSidebarWidth() {
  const v = parseInt(restore("sidebar-w"), 10);
  return Number.isFinite(v) ? v : sidebarDefaultW();
}

function setSidebarHidden(hidden) {
  const sidebar = $(".sidebar");
  if (sidebar) sidebar.classList.toggle("collapsed", hidden);
  store("sidebar-hidden", hidden ? "1" : "0");
}

function toggleSidebar() {
  const workbench = $(".workbench");
  if (workbench && workbench.classList.contains("no-sidebar")) return;
  const sidebar = $(".sidebar");
  if (sidebar) setSidebarHidden(!sidebar.classList.contains("collapsed"));
}

function revealSidebar() {
  const sidebar = $(".sidebar");
  if (sidebar && sidebar.classList.contains("collapsed")) setSidebarHidden(false);
}

function setupSidebar() {
  applySidebarWidth(loadSidebarWidth());
  if (restore("sidebar-hidden") === "1") setSidebarHidden(true);

  const resizer = $(".sidebar-resizer");
  const sidebar = $(".sidebar");
  if (!resizer || !sidebar) return;

  let startX = 0, startW = 0, dragging = false, lastW = sidebarDefaultW();
  const onMove = (ev) => {
    if (!dragging) return;
    lastW = applySidebarWidth(startW + (ev.clientX - startX));
  };
  const stop = () => {
    if (!dragging) return;
    dragging = false;
    resizer.classList.remove("dragging");
    document.body.classList.remove("resizing-sidebar");
    document.removeEventListener("mousemove", onMove);
    document.removeEventListener("mouseup", stop);
    store("sidebar-w", String(Math.round(lastW)));
  };
  resizer.addEventListener("mousedown", (ev) => {
    if (sidebar.classList.contains("collapsed")) return;
    dragging = true;
    startX = ev.clientX;
    startW = sidebar.getBoundingClientRect().width;
    resizer.classList.add("dragging");
    // body.resizing-sidebar kills text selection and makes iframes (ttyd,
    // cldBar) ignore the pointer so the drag tracks across the window.
    document.body.classList.add("resizing-sidebar");
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", stop);
    ev.preventDefault();
  });
  resizer.addEventListener("dblclick", () => {
    lastW = applySidebarWidth(sidebarDefaultW());
    store("sidebar-w", String(lastW));
  });
  resizer.addEventListener("keydown", (ev) => {
    if (sidebar.classList.contains("collapsed")) return;
    const current = sidebar.getBoundingClientRect().width;
    const step = ev.shiftKey ? 32 : 8;
    let next = null;
    if (ev.key === "ArrowLeft") next = current - step;
    else if (ev.key === "ArrowRight") next = current + step;
    else if (ev.key === "Home") next = sidebarMinW();
    else if (ev.key === "End") next = sidebarMaxW();
    if (next == null) return;
    ev.preventDefault();
    store("sidebar-w", String(applySidebarWidth(next)));
  });
}

/* ---------- Connection pill ---------- */
function setConn(status) {
  const pill = $("#conn-pill");
  const dot = $("#conn-dot");
  const label = $("#conn-label");
  const known = ["connected", "disconnected", "connecting"];
  const cls = known.includes(status) ? status : "connecting";
  for (const node of [pill, dot]) {
    if (!node) continue;
    known.forEach((k) => node.classList.remove(k));
    node.classList.add(cls);
  }
  if (label) label.textContent = cls === "connecting" ? "connecting..." : cls;
}

/* ---------- Theme bridge ----------
   4ColThems owns the theme (js/theme-toggle.js → window.Theme4Col, and the
   `themechange` event). These three names exist because every app's glue
   (webterm-glue, cldbar-glue) calls them; they defer to the kit when it is
   on the page and fall back to the attribute when it is not. */
function currentTheme() {
  if (window.Theme4Col) return window.Theme4Col.current();
  return document.documentElement.getAttribute("data-theme") || "dark";
}

function setTheme(name) {
  if (window.Theme4Col) { window.Theme4Col.set(name); return; }
  document.documentElement.setAttribute("data-theme", name);
}

function cycleTheme() {
  if (window.Theme4Col) { window.Theme4Col.cycle(); return; }
  const order = ["dark", "light", "hc", "green"];
  setTheme(order[(order.indexOf(currentTheme()) + 1) % order.length]);
}

/* ---------- Boot ---------- */
/** Wire the shell. Call from the app's boot (main.js) before its loaders.
    opts.view overrides the restored/default view. */
function setupShell(opts = {}) {
  scanViews();
  $$(".activity-item[data-view]").forEach((btn) =>
    btn.addEventListener("click", () => {
      if (VIEWS[btn.dataset.view] && VIEWS[btn.dataset.view].sidebar) revealSidebar();
      switchView(btn.dataset.view);
    }));
  setupSidebar();
  // The footer's app item and the brand both toggle the tree.
  wireButton($(".statusbar-item.remote"), toggleSidebar);
  const brand = $(".titlebar .brand");
  if (brand) brand.addEventListener("click", toggleSidebar);

  let tabs = [];
  try { tabs = JSON.parse(restore("tabs") || "[]"); } catch (_) { tabs = []; }
  shellState.openTabs = tabs.filter((id) => VIEWS[id]);
  const wanted = opts.view || restore("view");
  switchView(VIEWS[wanted] ? wanted : shellState.defaultView);
}
