// paster — the Entries view: one tab's lines, editable in place. Every row
// action is one PUT of the whole line list (plan D6); the server refuses a
// save over a file that changed meanwhile (409) and the panel reloads.
"use strict";

const LONG_LINE = 300;
const entriesState = { id: null, label: "", lines: [], rev: null, filter: "", editing: null, adding: false,
                       draft: null, pendingReload: false, selected: null };

function renderEntriesEmpty(message) {
  $("#entries-body").innerHTML = `<p class="empty">${esc(message)}</p>`;
  $("#entries-count").textContent = "";
}

function editorOpen() { return entriesState.editing !== null || entriesState.adding; }

// True when the open editor holds nothing worth keeping (unchanged text, or
// an empty new row): it is then closed so a tab switch can proceed.
function discardEditIfClean() {
  if (!editorOpen()) return true;
  const draft = entriesState.draft;
  const original = entriesState.adding ? "" : entriesState.lines[entriesState.editing];
  if (draft !== null && draft.trim() !== original.trim()) return false;
  entriesState.editing = null; entriesState.adding = false; entriesState.draft = null; entriesState.pendingReload = false;
  return true;
}

async function loadEntries(id) {
  if (editorOpen()) {
    // A same-tab reload waits for the editor (never re-render under it); a
    // different tab is only loaded once the editor is closed (selectTab).
    if (id === entriesState.id) { entriesState.pendingReload = true; return; }
    if (!discardEditIfClean()) return;
  }
  const data = await api(`/api/tabs/${encodeURIComponent(id)}/entries`);
  Object.assign(entriesState, { id: data.id, label: data.label, lines: data.lines || [], rev: data.rev, pendingReload: false });
  renderEntries();
}

function onEntriesChanged(tab) {
  if (tab && tab === entriesState.id) loadEntries(tab).catch(() => {});
  refreshTabCounts().catch(() => {});
}

async function refreshTabCounts() {
  const d = await api("/api/tabs");
  tabsState.tabs = d.tabs || [];
  tabsState.ignored = d.ignored || [];
  tabsState.unlabeled = d.unlabeled || [];
  if (!tabsState.search) renderTree();
  updateSummary();
}

function visibleIndexes() {
  const q = entriesState.filter.trim().toLowerCase();
  return entriesState.lines.map((l, i) => i).filter((i) => !q || entriesState.lines[i].toLowerCase().includes(q));
}

function rowActionsHtml(i, last) {
  if (isMobile()) {
    return `<button class="icon-btn" data-act="more" title="Actions"><span class="codicon codicon-ellipsis"></span></button>`;
  }
  return `
    <button class="icon-btn" data-act="copy" title="Copy to clipboard"><span class="codicon codicon-copy"></span></button>
    <button class="icon-btn" data-act="edit" title="Edit"><span class="codicon codicon-edit"></span></button>
    <button class="icon-btn" data-act="dup" title="Duplicate"><span class="codicon codicon-files"></span></button>
    <button class="icon-btn" data-act="move" title="Move to another tab"><span class="codicon codicon-arrow-right"></span></button>
    <button class="icon-btn desktop-only" data-act="up" title="Move up" ${i === 0 ? "disabled" : ""}><span class="codicon codicon-arrow-up"></span></button>
    <button class="icon-btn desktop-only" data-act="down" title="Move down" ${last ? "disabled" : ""}><span class="codicon codicon-arrow-down"></span></button>
    <button class="icon-btn" data-act="del" title="Delete"><span class="codicon codicon-trash"></span></button>`;
}

function editorHtml(i, value) {
  return `<textarea class="entry-editor" data-index="${i}" rows="2" spellcheck="false">${esc(value)}</textarea>`;
}

function entryRowHtml(i) {
  const line = entriesState.lines[i];
  const editing = entriesState.editing === i;
  const draft = editing && entriesState.draft !== null ? entriesState.draft : line;
  const last = i === entriesState.lines.length - 1;
  return `<div class="entry-row ${editing ? "editing" : ""} ${entriesState.selected === i ? "selected" : ""}" data-index="${i}" draggable="${editing ? "false" : "true"}">
    <span class="entry-grip codicon codicon-menu" title="Drag to reorder"></span>
    <span class="entry-index">${i + 1}</span>
    ${editing ? editorHtml(i, draft) : `<span class="entry-text" data-act="edit">${esc(line)}</span>`}
    ${line.length > LONG_LINE ? `<span class="chip" title="rofi shows it on one line">long</span>` : ""}
    <span class="entry-actions">${editing
      ? `<button class="icon-btn" data-act="commit" title="Save (Enter)"><span class="codicon codicon-check"></span></button>
         <button class="icon-btn" data-act="cancel" title="Cancel (Esc)"><span class="codicon codicon-close"></span></button>`
      : rowActionsHtml(i, last)}</span>
  </div>`;
}

function renderEntries() {
  const body = $("#entries-body");
  const shown = visibleIndexes();
  const total = entriesState.lines.length;
  $("#entries-count").textContent = entriesState.filter ? `${shown.length} of ${total}` : `${total} entr${total === 1 ? "y" : "ies"}`;
  const rows = shown.map(entryRowHtml).join("");
  const adding = entriesState.adding ? `<div class="entry-row editing" data-index="${total}">
      <span class="entry-grip codicon codicon-menu"></span><span class="entry-index">${total + 1}</span>
      ${editorHtml(total, entriesState.draft || "")}
      <span class="entry-actions">
        <button class="icon-btn" data-act="commit" title="Save (Enter)"><span class="codicon codicon-check"></span></button>
        <button class="icon-btn" data-act="cancel" title="Cancel (Esc)"><span class="codicon codicon-close"></span></button></span></div>` : "";
  body.innerHTML = `<div class="entry-list">${rows}${adding}</div>` +
    (!total && !entriesState.adding ? `<p class="empty">No entries in ${esc(entriesState.label)} — Add one, or Paste many.</p>` : "") +
    (editorOpen() ? `<p class="entry-hint">Enter saves · Esc cancels · one entry is one line (Paste many adds several)</p>` : "");
  $$("#entries-body .entry-row").forEach(wireEntryRow);
  const editor = $("#entries-body .entry-editor");
  if (editor) { editor.focus(); editor.setSelectionRange(editor.value.length, editor.value.length); }
}

function wireEntryRow(row) {
  const i = Number(row.dataset.index);
  row.addEventListener("click", (e) => {
    const act = e.target.closest("[data-act]");
    if (act) { e.stopPropagation(); entryAction(act.dataset.act, i, act); return; }
    if (!row.classList.contains("editing")) { entriesState.selected = i; $$("#entries-body .entry-row").forEach((r) => r.classList.toggle("selected", r === row)); }
  });
  const editor = row.querySelector(".entry-editor");
  if (editor) {
    editor.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); commitEdit(i, editor.value); }
      else if (e.key === "Enter" && e.shiftKey) { e.preventDefault(); toast("Entries are one line — use Paste many to add several", "warn"); }
      else if (e.key === "Escape") { e.preventDefault(); cancelEdit(); }
    });
    editor.addEventListener("input", () => { entriesState.draft = editor.value; });
    return;
  }
  // drag to reorder (desktop)
  row.addEventListener("dragstart", (e) => { e.dataTransfer.setData("text/paster-entry", String(i)); e.dataTransfer.effectAllowed = "move"; row.classList.add("dragging"); });
  row.addEventListener("dragend", () => { row.classList.remove("dragging"); $$("#entries-body .entry-row").forEach((r) => r.classList.remove("drop-before", "drop-after")); });
  row.addEventListener("dragover", (e) => {
    if (!e.dataTransfer.types.includes("text/paster-entry")) return;
    e.preventDefault();
    const before = e.offsetY < row.offsetHeight / 2;
    row.classList.toggle("drop-before", before);
    row.classList.toggle("drop-after", !before);
  });
  row.addEventListener("dragleave", () => row.classList.remove("drop-before", "drop-after"));
  row.addEventListener("drop", (e) => {
    const from = Number(e.dataTransfer.getData("text/paster-entry"));
    if (Number.isNaN(from) || from === i) return;
    e.preventDefault();
    const before = e.offsetY < row.offsetHeight / 2;
    reorderEntry(from, before ? i : i + 1);
  });
}

function entryAction(act, i, anchor) {
  const line = entriesState.lines[i];
  switch (act) {
    case "copy": return copyText(line);
    case "edit": return startEdit(i);
    case "commit": { const ed = $(`#entries-body .entry-editor[data-index="${i}"]`); return commitEdit(i, ed ? ed.value : ""); }
    case "cancel": return cancelEdit();
    case "dup": return saveLines([...entriesState.lines.slice(0, i + 1), line, ...entriesState.lines.slice(i + 1)], "Duplicated");
    case "move": return openMoveMenu(anchor, i);
    case "up": return reorderEntry(i, i - 1);
    case "down": return reorderEntry(i, i + 2);
    case "del": return confirmDeleteEntry(i);
    case "more": return showDropdown(anchor, [
      { label: "Copy", icon: "copy", action: () => copyText(line) },
      { label: "Edit", icon: "edit", action: () => startEdit(i) },
      { label: "Duplicate", icon: "files", action: () => entryAction("dup", i) },
      { label: "Move to tab…", icon: "arrow-right", action: () => openMoveMenu(anchor, i) },
      "sep",
      { label: "Move up", icon: "arrow-up", action: () => reorderEntry(i, i - 1) },
      { label: "Move down", icon: "arrow-down", action: () => reorderEntry(i, i + 2) },
      "sep",
      { label: "Delete…", icon: "trash", action: () => confirmDeleteEntry(i) },
    ]);
    default: return undefined;
  }
}

function startEdit(i) {
  if (editorOpen()) return;
  entriesState.editing = i;
  entriesState.draft = null;
  renderEntries();
}

function cancelEdit() {
  entriesState.editing = null;
  entriesState.adding = false;
  entriesState.draft = null;
  renderEntries();
  if (entriesState.pendingReload) loadEntries(entriesState.id).catch(() => {});
}

async function commitEdit(i, value) {
  const text = value.replace(/\r/g, "").trim();
  const wasAdding = entriesState.adding;
  if (text.includes("\n")) { toast("One entry is one line — use Paste many for several", "warn"); return; }
  if (!text) {
    if (wasAdding) { cancelEdit(); return; }
    return confirmDeleteEntry(i);
  }
  const lines = wasAdding ? [...entriesState.lines, text]
                          : entriesState.lines.map((l, k) => (k === i ? text : l));
  if (!wasAdding && lines[i] === entriesState.lines[i]) { cancelEdit(); return; }
  const ok = await saveLines(lines, wasAdding ? "Added" : "Saved", { keepDraft: { index: i, text } });
  if (ok) { entriesState.editing = null; entriesState.adding = false; entriesState.draft = null; renderEntries(); }
}

function addEntry() {
  if (editorOpen()) return;
  entriesState.adding = true;
  entriesState.draft = "";
  renderEntries();
  $("#entries-body").scrollTop = $("#entries-body").scrollHeight;
}

async function saveLines(lines, message, opts = {}) {
  try {
    const d = await api(`/api/tabs/${encodeURIComponent(entriesState.id)}/entries`,
                        { method: "PUT", body: { lines, base_rev: entriesState.rev } });
    entriesState.lines = lines.filter((l) => l.trim());
    entriesState.rev = d.rev;
    entriesState.editing = null; entriesState.adding = false; entriesState.draft = null;
    renderEntries();
    if (message) toast(message, "ok");
    refreshTabCounts().catch(() => {});
    return true;
  } catch (err) {
    if (err.status === 409) {
      toast("This tab changed on disk meanwhile — reloaded. Your edit is back in the editor; save again.", "warn");
      entriesState.editing = null; entriesState.adding = false;
      await loadEntries(entriesState.id);
      if (opts.keepDraft && opts.keepDraft.index <= entriesState.lines.length) {
        if (opts.keepDraft.index === entriesState.lines.length) { entriesState.adding = true; }
        else { entriesState.editing = opts.keepDraft.index; }
        entriesState.draft = opts.keepDraft.text;
        renderEntries();
      }
    } else {
      toastError("Save failed", err);
    }
    return false;
  }
}

function reorderEntry(from, to) {
  // `to` is the insertion index in the ORIGINAL list (before removal)
  const lines = [...entriesState.lines];
  if (from < 0 || from >= lines.length) return;
  const [line] = lines.splice(from, 1);
  const at = Math.max(0, Math.min(to > from ? to - 1 : to, lines.length));
  lines.splice(at, 0, line);
  if (lines.every((l, k) => l === entriesState.lines[k])) return;
  entriesState.selected = at;
  return saveLines(lines, null);
}

function confirmDeleteEntry(i) {
  const line = entriesState.lines[i];
  openModal("Delete entry", `<p>Delete this entry from <b>${esc(entriesState.label)}</b>?</p>
    <pre class="entry-text">${esc(line)}</pre>
    <p class="form-help">History keeps the previous version of the file (toolbar › clock icon).</p>`, [
    { label: "Cancel", secondary: true, onClick: () => { closeModal(); if (editorOpen()) cancelEdit(); } },
    { label: "Delete", danger: true, onClick: () => {
      closeModal();
      saveLines(entriesState.lines.filter((_, k) => k !== i), "Deleted");
      return false;
    } }]);
}

function openMoveMenu(anchor, i) {
  const others = tabsState.tabs.filter((t) => t.id !== entriesState.id);
  if (!others.length) { toast("There is no other tab to move to", "warn"); return; }
  showDropdown(anchor, others.map((t) => ({ label: t.label, icon: "folder", hint: `${t.count}`, action: () => moveEntryTo(i, t.id) })));
}

async function moveEntryTo(i, toId) {
  try {
    const target = await api(`/api/tabs/${encodeURIComponent(toId)}/entries`);
    await api("/api/entries/move", { method: "POST", body: {
      from: entriesState.id, index: i, to: toId, position: null, base_from: entriesState.rev, base_to: target.rev } });
    toast(`Moved to ${tabById(toId) ? tabById(toId).label : toId}`, "ok");
    await loadEntries(entriesState.id);
    refreshTabCounts().catch(() => {});
  } catch (err) {
    if (err.status === 409) { toast("Changed on disk meanwhile — reloaded, nothing moved", "warn"); loadEntries(entriesState.id).catch(() => {}); }
    else toastError("Move failed", err);
  }
}

async function copyText(text) {
  try {
    if (navigator.clipboard && window.isSecureContext) { await navigator.clipboard.writeText(text); }
    else {
      const ta = el("textarea"); ta.value = text; ta.setAttribute("readonly", ""); ta.style.position = "fixed"; ta.style.top = "-1000px";
      document.body.appendChild(ta); ta.select(); document.execCommand("copy"); ta.remove();
    }
    toast("Copied to the clipboard", "ok", 1500);
  } catch (err) { toastError("Copy failed", err); }
}

function splitPasteLines(text) {
  return String(text || "").replace(/\r/g, "").split("\n").map((l) => l.trim()).filter(Boolean);
}

function openPasteMany() {
  const body = openModal(`Paste many into ${esc(entriesState.label)}`, `
    <p class="form-help">One entry per line; blank lines are skipped. They are appended after the current entries.</p>
    <textarea id="paste-many" class="paste-many" spellcheck="false" placeholder="Explain this code step by step&#10;Write unit tests for the following code"></textarea>
    <p class="muted small" id="paste-many-count">0 entries</p>`, [
    { label: "Cancel", secondary: true, onClick: closeModal },
    { label: "Append", onClick: () => {
      const lines = splitPasteLines($("#paste-many").value);
      if (!lines.length) { modalError("Nothing to add."); return false; }
      closeModal();
      saveLines([...entriesState.lines, ...lines], `Added ${lines.length} entr${lines.length === 1 ? "y" : "ies"}`);
      return false;
    } }]);
  if (!body) return;
  const ta = $("#paste-many", body);
  ta.addEventListener("input", () => { const n = splitPasteLines(ta.value).length; $("#paste-many-count").textContent = `${n} entr${n === 1 ? "y" : "ies"}`; });
  ta.focus();
}

function sortEntries() {
  const sorted = [...entriesState.lines].sort((a, b) => a.localeCompare(b, undefined, { sensitivity: "base" }));
  if (sorted.every((l, k) => l === entriesState.lines[k])) { toast("Already sorted", "info"); return; }
  openModal("Sort A→Z", `<p>Sort the ${entriesState.lines.length} entries of <b>${esc(entriesState.label)}</b> alphabetically?</p>
    <p class="form-help">The current order is kept in History.</p>`, [
    { label: "Cancel", secondary: true, onClick: closeModal },
    { label: "Sort", onClick: () => { closeModal(); saveLines(sorted, "Sorted"); return false; } }]);
}

function fmtSnapshotTs(ts) {
  const m = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})/.exec(ts || "");
  return m ? `${m[1]}-${m[2]}-${m[3]} ${m[4]}:${m[5]}:${m[6]} UTC` : ts;
}

// Shared by the Entries toolbar and the Config view: the snapshot ring of
// one file, with a Restore per row. baseRev() (sync or async) supplies the
// rev the file has now, so a restore over a concurrent edit is refused;
// after() runs once a restore succeeded.
async function openHistoryModal(relpath, title, baseRev, after) {
  let data;
  try { data = await api(`/api/history?file=${encodeURIComponent(relpath)}`); }
  catch (err) { toastError("History failed", err); return; }
  const snaps = data.snapshots || [];
  openModal(`History — ${title}`, `<p class="form-help">Every version the front replaced, newest first (last ${50}). Restoring is itself kept.</p>
    <div class="history-list">${snaps.map((s) => `<div class="history-row">
      <code>${esc(fmtSnapshotTs(s.ts))}</code><span class="muted small">${s.size} B</span>
      <button class="btn btn-sm secondary" data-ts="${esc(s.ts)}" data-act="view">View</button>
      <button class="btn btn-sm" data-ts="${esc(s.ts)}" data-act="restore">Restore</button></div>`).join("")
      || `<p class="empty">No snapshots yet — the first save creates one.</p>`}</div>
    <pre id="history-view" class="entry-text" hidden></pre>`, [{ label: "Close", secondary: true, onClick: closeModal }]);
  $$("#modal-body [data-act=view]").forEach((b) => b.addEventListener("click", async () => {
    try {
      const d = await api(`/api/history/snapshot?file=${encodeURIComponent(relpath)}&ts=${encodeURIComponent(b.dataset.ts)}`);
      const pre = $("#history-view"); pre.hidden = false; pre.textContent = d.content;
    } catch (err) { modalError(err.message); }
  }));
  $$("#modal-body [data-act=restore]").forEach((b) => b.addEventListener("click", async () => {
    try {
      await api("/api/history/restore", { method: "POST", body: { file: relpath, ts: b.dataset.ts, base_rev: await baseRev() } });
      closeModal(); toast("Restored", "ok");
      if (after) await after();
    } catch (err) { modalError(err.message); }
  }));
}

function openEntriesHistory() {
  if (!entriesState.id) return;
  const id = entriesState.id;
  openHistoryModal(`entries/${id}/content.md`, entriesState.label, () => entriesState.rev,
    async () => { entriesState.editing = null; entriesState.adding = false; await loadEntries(id); refreshTabCounts().catch(() => {}); });
}

function revealEntry(index) {
  const row = $(`#entries-body .entry-row[data-index="${index}"]`);
  if (row) { entriesState.selected = index; revealRow(row); }
}

function setupEntries() {
  $("#btn-entry-add").addEventListener("click", addEntry);
  $("#btn-entry-paste").addEventListener("click", openPasteMany);
  $("#btn-entry-sort").addEventListener("click", sortEntries);
  $("#btn-entry-history").addEventListener("click", openEntriesHistory);
  $("#btn-entries-refresh").addEventListener("click", () => { entriesState.editing = null; entriesState.adding = false;
    loadEntries(entriesState.id).catch((e) => toastError("Reload failed", e)); });
  $("#entries-filter").addEventListener("input", (e) => { entriesState.filter = e.target.value; renderEntries(); });
  registerCommand({ id: "entries.add", label: "Add entry", icon: "add", mobile: true, run: () => { switchView("entries"); addEntry(); } });
  registerCommand({ id: "entries.paste", label: "Paste many entries…", icon: "new-file", mobile: true, run: () => { switchView("entries"); openPasteMany(); } });
  window.addEventListener("resize", () => { if (activeView() === "entries" && !editorOpen()) renderEntries(); });
  // Escape closes an open editor even when focus has wandered off it (a
  // refused tab switch leaves focus on the sidebar); overlays go first.
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape" || !editorOpen()) return;
    if ((typeof modalOpen === "function" && modalOpen()) || (typeof dropdownOpen === "function" && dropdownOpen())
        || (typeof quickOpenOpen === "function" && quickOpenOpen())) return;
    cancelEdit();
  });
}
