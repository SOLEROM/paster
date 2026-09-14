/* ==========================================================================
   vsCodeFront — wb-overlays.js: toasts, modal, dropdown, quick input, keys
   ==========================================================================
   Classic script, `defer`, after wb-shell.js. Drives the overlay hosts at the
   bottom of snippets/shell.html:

     #toast-host                 notifications, bottom-right above the footer
     #modal-backdrop / #modal    the one reusable dialog
     #dropdown                   a floating menu anchored to a button
     #quickinput                 the Ctrl+P palette; #command-center opens it

   COMMANDS are the unit the palette, the menus and the ⋯ overflow share:
     registerCommand({ id, label, icon, desc, run, when })
   The palette lists every registered command plus one entry per view and
   one per theme; apps add providers for their own items (see
   addQuickOpenProvider). `when()` returning false hides a command.

   Keyboard (document-level, installed by setupOverlays):
     Escape        closes the topmost overlay: dropdown → quick input → modal
     Ctrl/Cmd+P    quick open              Ctrl/Cmd+B  toggle sidebar
     Ctrl/Cmd+,    the view with data-view="config|settings", if any
     Ctrl/Cmd+`    the view with data-view="sessions|terminal", if any

   Exposes: toast, toastError, openModal, closeModal, modalError,
   hookModalCloseOnce, showDropdown, hideDropdown, registerCommand,
   addQuickOpenProvider, openQuickOpen, closeQuickOpen, revealRow, flashRow,
   interceptMarkdownLinks, normalizePath, setupOverlays.
   ========================================================================== */
"use strict";

/* ---------- Toasts ----------
   For the outcome of anything the user triggered but is not watching a row
   for. Failures stay until dismissed; the rest fade. */
const TOAST_ICONS = { info: "info", ok: "check", warn: "warning", error: "error" };

function toast(message, kind = "info", timeout = 4500) {
  const host = $("#toast-host");
  if (!host) return null;
  const node = el("div", `toast ${kind}`,
    `<span class="codicon codicon-${TOAST_ICONS[kind] || "info"}"></span>
     <span class="toast-msg">${esc(message)}</span>`);
  node.setAttribute("role", kind === "error" ? "alert" : "status");
  node.addEventListener("click", () => node.remove());
  host.appendChild(node);
  if (kind !== "error") setTimeout(() => node.remove(), timeout);
  return node;
}

function toastError(prefix, err) {
  toast(`${prefix}: ${err && err.message ? err.message : err}`, "error");
}

/* ---------- Modal ----------
   openModal(title, bodyHtml, buttons) — the apps' signature. A button is
   { label, onClick, secondary?, danger?, id? }; onClick returning false keeps
   the dialog open (validation failed). Returns the body element so the
   caller can wire its fields. */
function openModal(title, bodyHtml, buttons = []) {
  const backdrop = $("#modal-backdrop");
  if (!backdrop) return null;
  $("#modal-title").textContent = title;
  $("#modal-body").innerHTML = bodyHtml || "";
  const footer = $("#modal-footer");
  footer.innerHTML = "";
  for (const btn of buttons) {
    const b = el("button", "btn" + (btn.secondary ? " secondary" : "") + (btn.danger ? " danger" : ""));
    b.textContent = btn.label;
    if (btn.id) b.id = btn.id;
    b.addEventListener("click", () => {
      if (btn.onClick && btn.onClick() === false) return;
      if (btn.keepOpen) return;
      if (!btn.onClick) closeModal();
    });
    footer.appendChild(b);
  }
  backdrop.hidden = false;
  const first = $("#modal-body input, #modal-body select, #modal-body textarea, #modal-body button");
  if (first && typeof first.focus === "function") first.focus();
  return $("#modal-body");
}

function closeModal() {
  const backdrop = $("#modal-backdrop");
  if (!backdrop || backdrop.hidden) return;
  backdrop.hidden = true;
  $("#modal-body").innerHTML = "";
  $("#modal-footer").innerHTML = "";
}

function modalOpen() {
  const backdrop = $("#modal-backdrop");
  return !!backdrop && !backdrop.hidden;
}

/** Show an error line inside the open modal (created on first use). */
function modalError(message) {
  let box = $("#modal-error");
  if (!box) {
    box = el("p", "form-error");
    box.id = "modal-error";
    $("#modal-body").appendChild(box);
  }
  box.textContent = message;
  if (typeof box.scrollIntoView === "function") box.scrollIntoView({ block: "nearest" });
}

/** Run fn once the modal closes by ANY path (×, backdrop, Escape, a button)
    — lets a modal owner clear its own state without the core knowing. */
function hookModalCloseOnce(fn) {
  const backdrop = $("#modal-backdrop");
  if (!backdrop || typeof MutationObserver !== "function") { fn(); return; }
  const observer = new MutationObserver(() => {
    if (backdrop.hidden) { observer.disconnect(); fn(); }
  });
  observer.observe(backdrop, { attributes: true, attributeFilter: ["hidden"] });
}

/* ---------- Dropdown menu ----------
   showDropdown(anchorEl, items): items are { label, icon?, hint?, action }
   or the string "sep". Positioned below the anchor, flipped to stay inside
   the viewport; any mousedown outside closes it. */
function showDropdown(anchor, items) {
  const dd = $("#dropdown");
  if (!dd) return;
  dd.innerHTML = "";
  for (const it of items) {
    if (it === "sep") { dd.appendChild(el("div", "dropdown-sep")); continue; }
    const b = el("button", "dropdown-item",
      `<span class="codicon codicon-${esc(it.icon || "circle-small")}"></span>` +
      `<span>${esc(it.label)}</span>` +
      (it.hint ? `<span class="dd-hint">${esc(it.hint)}</span>` : ""));
    b.setAttribute("role", "menuitem");
    b.addEventListener("click", () => { hideDropdown(); it.action && it.action(); });
    dd.appendChild(b);
  }
  dd.hidden = false;
  const r = anchor.getBoundingClientRect();
  const w = dd.offsetWidth || 220, h = dd.offsetHeight || 0;
  let x = r.left, y = r.bottom + 4;
  if (x + w > window.innerWidth - 8) x = Math.max(8, r.right - w);
  if (y + h > window.innerHeight - 8) y = Math.max(8, r.top - h - 4);
  dd.style.left = x + "px";
  dd.style.top = y + "px";
}

function hideDropdown() {
  const dd = $("#dropdown");
  if (dd) dd.hidden = true;
}

function dropdownOpen() {
  const dd = $("#dropdown");
  return !!dd && !dd.hidden;
}

/* ---------- Commands + quick input (Ctrl+P) ---------- */
const COMMANDS = new Map();          // id → { id, label, icon, desc, run, when }
const QUICK_PROVIDERS = [];          // () => [{ label, icon, desc, run }]
let qiEntries = [], qiFocus = 0;

function registerCommand(cmd) {
  if (!cmd || !cmd.id || typeof cmd.run !== "function") {
    throw new Error("registerCommand needs { id, label, run }");
  }
  COMMANDS.set(cmd.id, { icon: "circle-small", desc: "command", ...cmd });
  return cmd.id;
}

function unregisterCommand(id) { COMMANDS.delete(id); }

function runCommand(id) {
  const cmd = COMMANDS.get(id);
  if (!cmd) return false;
  cmd.run();
  return true;
}

/** addQuickOpenProvider(() => entries) — app items, docs, sessions… */
function addQuickOpenProvider(fn) { QUICK_PROVIDERS.push(fn); }

function quickOpenEntries() {
  const entries = [];
  for (const [id, v] of Object.entries(VIEWS)) {
    entries.push({ icon: v.icon, label: v.label, desc: "view", run: () => switchView(id) });
  }
  for (const cmd of COMMANDS.values()) {
    if (cmd.when && !cmd.when()) continue;
    entries.push({ icon: cmd.icon, label: cmd.label, desc: cmd.desc, run: cmd.run });
  }
  if (window.Theme4Col) {
    for (const t of window.Theme4Col.list) {
      const meta = window.Theme4Col.meta(t);
      entries.push({ icon: meta.codicon, label: `Theme: ${meta.label}`, desc: "theme",
        run: () => setTheme(t) });
    }
  }
  for (const provider of QUICK_PROVIDERS) {
    try { entries.push(...(provider() || [])); } catch (err) { console.error("quick open provider failed:", err); }
  }
  return entries;
}

function renderQuickList() {
  const input = $("#quickinput-input");
  const host = $("#quickinput-list");
  if (!input || !host) return;
  const q = input.value.trim().toLowerCase();
  // Only the rendered slice is navigable, so Enter always hits a visible row.
  qiEntries = quickOpenEntries().filter((e) =>
    !q || e.label.toLowerCase().includes(q) || (e.desc || "").toLowerCase().includes(q))
    .slice(0, 40);
  qiFocus = Math.min(qiFocus, Math.max(0, qiEntries.length - 1));
  host.innerHTML = "";
  qiEntries.forEach((e, i) => {
    const b = el("button", "quickinput-item" + (i === qiFocus ? " focused" : ""),
      `<span class="codicon codicon-${esc(e.icon || "circle-small")}"></span><span>${esc(e.label)}</span>` +
      `<span class="qi-desc">${esc(e.desc || "")}</span>`);
    b.setAttribute("role", "option");
    b.addEventListener("click", () => { closeQuickOpen(); e.run(); });
    host.appendChild(b);
    if (i === qiFocus && typeof b.scrollIntoView === "function") b.scrollIntoView({ block: "nearest" });
  });
  if (!qiEntries.length) host.appendChild(el("div", "empty", "No matching commands"));
}

function openQuickOpen() {
  const qi = $("#quickinput");
  const input = $("#quickinput-input");
  if (!qi || !input) return;
  qiFocus = 0;
  qi.hidden = false;
  input.value = "";
  renderQuickList();
  input.focus();
}

function closeQuickOpen() {
  const qi = $("#quickinput");
  if (qi) qi.hidden = true;
}

function quickOpenOpen() {
  const qi = $("#quickinput");
  return !!qi && !qi.hidden;
}

function onQuickInputKey(e) {
  if (e.key === "ArrowDown") { qiFocus++; renderQuickList(); e.preventDefault(); }
  else if (e.key === "ArrowUp") { qiFocus = Math.max(0, qiFocus - 1); renderQuickList(); e.preventDefault(); }
  else if (e.key === "Enter") {
    const entry = qiEntries[qiFocus];
    closeQuickOpen();
    if (entry) entry.run();
  } else if (e.key === "Escape") { closeQuickOpen(); }
}

/* ---------- Reveal a row ----------
   Scroll the row the user just picked into its scrolling box (.dash-body,
   .tree, .docs-tree-body, or [data-scroll]) — nudging if partly visible,
   centring if off-screen — then pulse it once. */
const REVEAL_PAD = 12;

function revealRow(row, { flash = true } = {}) {
  if (!row || typeof row.closest !== "function") return;
  const box = row.closest(".dash-body, .tree, .docs-tree-body, .log-view, [data-scroll]");
  if (!box || !box.clientHeight) return;   // panel hidden — nothing to scroll
  const head = box.querySelector("thead");
  const headH = head ? head.getBoundingClientRect().height : 0;
  const boxRect = box.getBoundingClientRect();
  const rect = row.getBoundingClientRect();
  const viewTop = boxRect.top + headH;
  const bandH = boxRect.bottom - viewTop;
  let delta = 0;
  if (rect.bottom <= viewTop || rect.top >= boxRect.bottom) {
    delta = (rect.top - viewTop) - Math.max(0, (bandH - rect.height) / 2);
  } else {
    const above = rect.top - (viewTop + REVEAL_PAD);
    const below = rect.bottom - (boxRect.bottom - REVEAL_PAD);
    delta = above < 0 ? above : Math.max(0, below);
  }
  if (delta && typeof box.scrollBy === "function") box.scrollBy({ top: delta, behavior: "smooth" });
  if (flash) flashRow(row);
}

function flashRow(row) {
  row.classList.remove("row-flash");
  void row.offsetWidth;                    // restart the animation when re-picking
  row.classList.add("row-flash");
  row.addEventListener("animationend", () => row.classList.remove("row-flash"), { once: true });
}

/* ---------- Markdown link routing ----------
   Relative *.md links inside a rendered page resolve against the page's own
   directory and route through the app (onOpen(path)); http(s) links open in
   a new tab; anchors and absolute paths pass through. */
function normalizePath(path) {
  const out = [];
  for (const segment of String(path || "").split("/")) {
    if (!segment || segment === ".") continue;
    if (segment === "..") out.pop();
    else out.push(segment);
  }
  return out.join("/");
}

function interceptMarkdownLinks(container, currentPath, onOpen) {
  const base = currentPath && currentPath.includes("/")
    ? currentPath.slice(0, currentPath.lastIndexOf("/") + 1) : "";
  $$("a[href]", container).forEach((anchor) => {
    const href = anchor.getAttribute("href") || "";
    if (/^[a-z]+:/i.test(href) || href.startsWith("#") || href.startsWith("/")) {
      if (/^https?:/i.test(href)) {
        anchor.target = "_blank";
        anchor.rel = "noopener noreferrer";
      }
      return;
    }
    if (!href.toLowerCase().split("#")[0].endsWith(".md")) return;
    anchor.addEventListener("click", (ev) => {
      ev.preventDefault();
      onOpen(normalizePath(base + href.split("#")[0]));
    });
  });
}

/* ---------- Keyboard + wiring ---------- */
function findViewByRole(...names) {
  return names.find((n) => VIEWS[n]) || null;
}

function onGlobalKey(e) {
  if (e.key === "Escape") {
    if (dropdownOpen()) { hideDropdown(); return; }
    if (quickOpenOpen()) { closeQuickOpen(); return; }
    if (modalOpen()) { closeModal(); }
    return;
  }
  if (!(e.ctrlKey || e.metaKey) || e.altKey) return;
  const key = e.key.toLowerCase();
  if (key === "p") { e.preventDefault(); openQuickOpen(); }
  else if (key === "b") { e.preventDefault(); toggleSidebar(); }
  else if (key === ",") {
    const v = findViewByRole("config", "settings");
    if (v) { e.preventDefault(); switchView(v); }
  } else if (key === "`") {
    const v = findViewByRole("sessions", "terminal");
    if (v) { e.preventDefault(); switchView(v); }
  }
}

function setupOverlays() {
  const close = $("#modal-close");
  if (close) close.addEventListener("click", closeModal);
  const backdrop = $("#modal-backdrop");
  if (backdrop) backdrop.addEventListener("mousedown", (ev) => {
    if (ev.target === backdrop) closeModal();
  });
  const cc = $("#command-center");
  if (cc) cc.addEventListener("click", openQuickOpen);
  const input = $("#quickinput-input");
  if (input) {
    input.addEventListener("input", () => { qiFocus = 0; renderQuickList(); });
    input.addEventListener("keydown", onQuickInputKey);
  }
  document.addEventListener("mousedown", (e) => {
    const dd = $("#dropdown");
    if (dd && !dd.hidden && !dd.contains(e.target)) hideDropdown();
    const qi = $("#quickinput");
    if (qi && !qi.hidden) {
      const box = $(".quickinput-box", qi);
      if (box && !box.contains(e.target)) closeQuickOpen();
    }
  });
  document.addEventListener("keydown", onGlobalKey);
  // Every .menubar-item[data-menu] opens the menu an app registered with
  // registerMenu(name, () => items).
  $$(".menubar-item[data-menu]").forEach((b) =>
    b.addEventListener("click", () => {
      const items = MENUS[b.dataset.menu];
      if (items) showDropdown(b, items());
    }));
}

/* ---------- Menus (title-bar menubar, optional) ---------- */
const MENUS = {};
/** registerMenu("view", () => [{label, icon, action}, "sep", …]) */
function registerMenu(name, itemsFn) { MENUS[name] = itemsFn; }
