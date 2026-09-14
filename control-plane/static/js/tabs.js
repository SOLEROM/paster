// paster — the sidebar: the tab list (folders under entries/), ALL search,
// create / rename / reorder / delete. State → render one string → wire.
"use strict";

const tabsState = { tabs: [], ignored: [], unlabeled: [], selected: restore("tab") || null, search: "", hits: [], all: [] };

function tabById(id) { return tabsState.tabs.find((t) => t.id === id) || null; }

async function loadTabs() {
  const data = await api("/api/tabs");
  tabsState.tabs = data.tabs || [];
  tabsState.ignored = data.ignored || [];
  tabsState.unlabeled = data.unlabeled || [];
  if (!tabById(tabsState.selected)) tabsState.selected = tabsState.tabs.length ? tabsState.tabs[0].id : null;
  renderTree();
  updateSummary();
  api("/api/search?q=").then((d) => { tabsState.all = d.hits || []; }).catch(() => {});
  if (tabsState.selected) await loadEntries(tabsState.selected);
  else renderEntriesEmpty("No tabs yet — create one with the folder button above.");
}

function updateSummary() {
  const strip = $("#summary-strip");
  if (!strip) return;
  const tab = tabById(tabsState.selected);
  const total = tabsState.tabs.reduce((n, t) => n + t.count, 0);
  strip.hidden = false;
  strip.textContent = tab ? `${tab.label} · ${tab.count} entries · ${tabsState.tabs.length} tabs, ${total} total`
                          : `${tabsState.tabs.length} tabs · ${total} entries`;
  strip.title = strip.textContent;
}

function tabRowHtml(t) {
  return `<div class="tree-row ${t.id === tabsState.selected ? "selected" : ""}" data-id="${esc(t.id)}" draggable="true"
       role="treeitem" tabindex="0" style="--depth:1" title="${esc(t.id)}">
    <span class="codicon codicon-folder tree-icon"></span>
    <span class="tree-label">${esc(t.label)}</span>
    <span class="tree-tag">${t.count}</span>
    <span class="tree-actions">
      <button class="icon-btn" data-act="menu" title="Tab actions"><span class="codicon codicon-ellipsis"></span></button>
    </span></div>`;
}

function renderTree() {
  const tree = $("#tree");
  if (tabsState.search) {
    tree.classList.add("search-hits");
    tree.innerHTML = tabsState.hits.map((h) => `
      <div class="tree-row" data-tab="${esc(h.tab)}" data-index="${h.index}" role="treeitem" tabindex="0" style="--depth:1">
        <span class="hit-tab">[${esc(h.label)}]</span><span class="hit-line">${esc(h.line)}</span></div>`).join("")
      || `<p class="empty">No entry matches.</p>`;
    $("#tree-count").textContent = `${tabsState.hits.length} hit${tabsState.hits.length === 1 ? "" : "s"}`;
    $$("#tree .tree-row").forEach((r) => r.addEventListener("click", () => {
      selectTab(r.dataset.tab, Number(r.dataset.index));
    }));
  } else {
    tree.classList.remove("search-hits");
    tree.innerHTML = tabsState.tabs.map(tabRowHtml).join("") || `<p class="empty">No tabs — each folder under entries/ with a content.md is one.</p>`;
    $("#tree-count").textContent = tabsState.tabs.length;
    $$("#tree .tree-row").forEach(wireTabRow);
  }
  const ignored = $("#tree-ignored");
  const notes = [];
  if (tabsState.ignored.length) notes.push(`${tabsState.ignored.length} folder(s) ignored (no content.md): ${tabsState.ignored.join(", ")}`);
  if (tabsState.unlabeled.length) notes.push(`skipped by rofi (empty label): ${tabsState.unlabeled.join(", ")}`);
  ignored.hidden = notes.length === 0;
  ignored.textContent = notes.join(" · ");
}

function wireTabRow(row) {
  const id = row.dataset.id;
  row.addEventListener("click", (e) => {
    if (e.target.closest("[data-act]")) return;
    selectTab(id);
  });
  row.addEventListener("keydown", (e) => { if (e.key === "Enter") selectTab(id); });
  const menu = row.querySelector("[data-act=menu]");
  menu.addEventListener("click", (e) => { e.stopPropagation(); openTabMenu(menu, id); });
  row.addEventListener("contextmenu", (e) => { e.preventDefault(); openTabMenu(row, id); });
  // drag to reorder (desktop)
  row.addEventListener("dragstart", (e) => { e.dataTransfer.setData("text/paster-tab", id); e.dataTransfer.effectAllowed = "move"; row.classList.add("dragging"); });
  row.addEventListener("dragend", () => { row.classList.remove("dragging"); $$("#tree .tree-row").forEach((r) => r.classList.remove("drop-before", "drop-after")); });
  row.addEventListener("dragover", (e) => {
    if (!e.dataTransfer.types.includes("text/paster-tab")) return;
    e.preventDefault();
    const before = e.offsetY < row.offsetHeight / 2;
    row.classList.toggle("drop-before", before);
    row.classList.toggle("drop-after", !before);
  });
  row.addEventListener("dragleave", () => row.classList.remove("drop-before", "drop-after"));
  row.addEventListener("drop", (e) => {
    const from = e.dataTransfer.getData("text/paster-tab");
    if (!from || from === id) return;
    e.preventDefault();
    const before = e.offsetY < row.offsetHeight / 2;
    const ids = tabsState.tabs.map((t) => t.id).filter((x) => x !== from);
    const at = ids.indexOf(id) + (before ? 0 : 1);
    ids.splice(at, 0, from);
    reorderTabs(ids);
  });
}

function openTabMenu(anchor, id) {
  const ids = tabsState.tabs.map((t) => t.id);
  const i = ids.indexOf(id);
  showDropdown(anchor, [
    { label: "Rename…", icon: "edit", action: () => openRenameTab(id) },
    { label: "New tab after this…", icon: "new-folder", action: () => openNewTab(id) },
    "sep",
    { label: "Move up", icon: "arrow-up", action: () => moveTab(id, -1) },
    { label: "Move down", icon: "arrow-down", action: () => moveTab(id, 1) },
    "sep",
    { label: "History of this tab…", icon: "history", action: () => { selectTab(id); openEntriesHistory(); } },
    { label: "Delete…", icon: "trash", action: () => confirmDeleteTab(id) },
  ].filter((it) => it === "sep" || !(it.label === "Move up" && i === 0) && !(it.label === "Move down" && i === ids.length - 1)));
}

function selectTab(id, revealIndex) {
  if (!tabById(id)) return;
  if (id !== entriesState.id && !discardEditIfClean()) {
    toast("Finish the edit first — Enter saves, Esc cancels", "warn");
    return;                       // sidebar and summary keep showing the tab being edited
  }
  tabsState.selected = id;
  store("tab", id);
  renderTree();
  updateSummary();
  switchView("entries");
  loadEntries(id).then(() => { if (revealIndex !== undefined) revealEntry(revealIndex); })
    .catch((err) => toastError("Load failed", err));
}

async function moveTab(id, delta) {
  const ids = tabsState.tabs.map((t) => t.id);
  const i = ids.indexOf(id);
  const j = i + delta;
  if (i < 0 || j < 0 || j >= ids.length) return;
  [ids[i], ids[j]] = [ids[j], ids[i]];
  await reorderTabs(ids);
}

async function reorderTabs(ids) {
  try {
    const data = await api("/api/tabs/order", { method: "PUT", body: { ids } });
    const moved = new Map(data.renames || []);
    if (moved.has(tabsState.selected)) { tabsState.selected = moved.get(tabsState.selected); store("tab", tabsState.selected); }
    toast("Tabs reordered", "ok");
    await loadTabs();
  } catch (err) { toastError("Reorder failed", err); }
}

function openNewTab(after) {
  const body = openModal(after ? `New tab after ${esc(tabById(after).label)}` : "New tab", `
    <div class="form-row"><label>Name</label><input type="text" id="new-tab-name" placeholder="Prompts" maxlength="64" /></div>
    <p class="form-help">Becomes a folder <code>NN_Name</code> under entries/. Letters, digits, spaces, _ . - only;
       the characters <code>, : ' "</code> would be dropped by rofi and are refused here.</p>`, [
    { label: "Cancel", secondary: true, onClick: closeModal },
    { label: "Create", onClick: () => {
      const name = $("#new-tab-name").value.trim();
      if (!name) { modalError("A name is required."); return false; }
      api("/api/tabs", { method: "POST", body: after ? { name, after } : { name } })
        .then((d) => { closeModal(); toast(`Created ${d.id}`, "ok"); tabsState.selected = d.id; store("tab", d.id); return loadTabs(); })
        .catch((err) => modalError(err.message));
      return false;
    } }]);
  if (body) $("#new-tab-name", body).focus();
}

function openRenameTab(id) {
  const tab = tabById(id);
  const body = openModal("Rename tab", `
    <div class="form-row"><label>Name</label><input type="text" id="rename-tab-name" value="${esc(tab.label)}" maxlength="64" /></div>
    <p class="form-help">The <code>NN_</code> ordering prefix of <code>${esc(id)}</code> is kept.</p>`, [
    { label: "Cancel", secondary: true, onClick: closeModal },
    { label: "Rename", onClick: () => {
      const name = $("#rename-tab-name").value.trim();
      if (!name) { modalError("A name is required."); return false; }
      api(`/api/tabs/${encodeURIComponent(id)}`, { method: "PATCH", body: { name } })
        .then((d) => { closeModal(); if (tabsState.selected === id) { tabsState.selected = d.id; store("tab", d.id); } toast(`Renamed to ${d.id}`, "ok"); return loadTabs(); })
        .catch((err) => modalError(err.message));
      return false;
    } }]);
  if (body) { const i = $("#rename-tab-name", body); i.focus(); i.select(); }
}

function confirmDeleteTab(id) {
  const tab = tabById(id);
  openModal("Delete tab", `<p>Delete <b>${esc(tab.label)}</b> (${tab.count} entries)?</p>
    <p class="form-help">The folder <code>${esc(id)}</code> moves to the trash under the data dir (~/.paster/trash) — nothing is erased.</p>`, [
    { label: "Cancel", secondary: true, onClick: closeModal },
    { label: "Delete", danger: true, onClick: () => {
      api(`/api/tabs/${encodeURIComponent(id)}`, { method: "DELETE" })
        .then((d) => { closeModal(); toast(`Moved to ${d.trash}`, "ok"); return loadTabs(); })
        .catch((err) => modalError(err.message));
      return false;
    } }]);
}

let searchTimer = null;
function onTreeSearch(value) {
  tabsState.search = value.trim();
  clearTimeout(searchTimer);
  if (!tabsState.search) { tabsState.hits = []; renderTree(); return; }
  searchTimer = setTimeout(async () => {
    try {
      const d = await api(`/api/search?q=${encodeURIComponent(tabsState.search)}`);
      tabsState.hits = d.hits || [];
    } catch (err) { tabsState.hits = []; toastError("Search failed", err); }
    renderTree();
  }, 150);
}

function setupTabs() {
  $("#btn-tab-new").addEventListener("click", () => openNewTab());
  $("#tree-search").addEventListener("input", (e) => onTreeSearch(e.target.value));
  registerCommand({ id: "tabs.new", label: "New tab…", icon: "new-folder", mobile: true, run: () => openNewTab() });
  // Ctrl+P lists every entry across every tab, like rofi's ALL mode.
  addQuickOpenProvider(() => tabsState.all.map((h) => ({ icon: "symbol-keyword", label: h.line, desc: h.label,
    run: () => selectTab(h.tab, h.index) })));
}
