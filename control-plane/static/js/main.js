// paster — boot: wire the kit, wire the views, connect Socket.IO, load.
"use strict";

const activityLog = [];

function onActivityLogged(entry) {
  activityLog.push(entry);
  activityLog.splice(0, Math.max(0, activityLog.length - 2000));
  if (entry.level === "warn" || entry.level === "error") {
    const dot = $("#activity-log-dot");
    dot.hidden = false;
    dot.classList.toggle("error", entry.level === "error");
  }
}

function logRowHtml(e) {
  const t = (e.ts || "").slice(11, 19);
  return `<div class="log-row ${esc(e.level)}"><span class="log-time">${esc(t)}</span>
    <span class="log-level">${esc(e.level)}</span><span class="log-source">${esc(e.source)}</span>
    <span class="log-msg">${esc(e.message)}</span></div>`;
}

async function openActivityLog() {
  try {
    const data = await api("/api/logs?limit=1000");
    activityLog.splice(0, activityLog.length, ...(data.entries || []));
  } catch (_) { /* keep the socket-fed mirror */ }
  openModal("Activity log", `<div class="log-window">
    <div class="log-toolbar"><span class="muted small">${activityLog.length} entries</span><div class="spacer"></div></div>
    <div class="log-view log-list" id="log-list">${activityLog.map(logRowHtml).join("") || `<p class="log-empty muted">Nothing yet.</p>`}</div></div>`,
    [{ label: "Close", secondary: true, onClick: closeModal }]);
  const list = $("#log-list");
  if (list) list.scrollTop = list.scrollHeight;
  $("#activity-log-dot").hidden = true;
}

async function loadHealth() {
  const h = await api("/api/health");
  const item = $("#status-display");
  if (item) {
    item.innerHTML = `<span class="codicon codicon-${h.display ? "device-desktop" : "debug-disconnect"}"></span><span>${h.display ? "desktop" : "no display"}</span>`;
    item.title = h.display ? "Desktop actions (open popup, apply hotkey) are available"
                           : "No DISPLAY in the server's environment — desktop actions are disabled";
  }
  syncPopupLaunch(h.display);
}

function connectSocket() {
  if (typeof io !== "function") { setConn("disconnected"); return; }
  const socket = io();
  socket.on("connect", () => setConn("connected"));
  socket.on("disconnect", () => setConn("disconnected"));
  socket.on("activity_logged", onActivityLogged);
  // Events say "something moved"; the SPA re-fetches.
  socket.on("tabs_changed", () => loadTabs().catch(() => {}));
  socket.on("entries_changed", (p) => onEntriesChanged(p && p.tab));
  socket.on("config_changed", () => onConfigChanged());
  socket.on("doctor_changed", () => { if (activeView() === "doctor") loadDoctor().catch(() => {}); });
}

// Views that fetch on demand — registered before boot, so the view the
// shell restores on load triggers its loader too.
const VIEW_LOADERS = { config: () => loadConfigTab(), doctor: () => loadDoctor() };
document.addEventListener("viewchange", (e) => {
  const load = VIEW_LOADERS[e.detail && e.detail.view];
  if (load) load().catch((err) => toastError("Load failed", err));
});

async function boot() {
  setupShell();
  setupOverlays();
  setupMobile();
  setupCldBar();
  setupTabs();
  setupEntries();
  setupPopupLaunch();
  setupConfig();
  setupDoctor();
  setupHelp();
  $("#btn-activity-log").addEventListener("click", openActivityLog);
  registerCommand({ id: "log.open", label: "Activity log", icon: "output", mobile: true, run: openActivityLog });
  connectSocket();
  for (const load of [loadHealth, loadTabs, loadHelp]) {
    try { await load(); } catch (err) { console.error("boot loader failed:", err); toastError("Load failed", err); }
  }
  const load = VIEW_LOADERS[activeView()];
  if (load) load().catch((err) => toastError("Load failed", err));
}

document.addEventListener("DOMContentLoaded", boot);
