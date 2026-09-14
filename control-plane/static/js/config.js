// paster — the Config view: a settings form over config.yaml (values
// replaced in place, comments kept) plus a Raw mode. lib-config.sh's own
// warnings come back with every save and sit under the field they name.
"use strict";

const CFG_MODE_KEY = "config-mode";
const cfgState = { mode: restore(CFG_MODE_KEY) === "raw" ? "raw" : "form", doc: null, working: {}, search: "",
                   preflight: {}, doctor: null };

async function loadConfigDoc() {
  cfgState.doc = await api("/api/config");
  cfgState.working = { ...cfgState.doc.values };
  cfgState.preflight = {};
  return cfgState.doc;
}

function cfgDirty() {
  const d = cfgState.doc;
  if (!d) return false;
  if (cfgState.mode === "raw") { const ta = $("#cfg-raw"); return !!ta && ta.value !== d.raw; }
  return Object.keys(cfgState.working).some((k) => (cfgState.working[k] ?? "") !== (d.values[k] ?? ""));
}

function changedValues() {
  const out = {};
  for (const [k, v] of Object.entries(cfgState.working)) if ((v ?? "") !== (cfgState.doc.values[k] ?? "")) out[k] = v;
  return out;
}

function onConfigChanged() {
  if (!cfgState.doc) return;
  if (cfgDirty()) { toast("config.yaml changed on disk — Discard to reload it", "warn"); return; }
  loadConfigDoc().then(() => { if (activeView() === "config") renderCfg(); }).catch(() => {});
}

async function loadConfigTab() {
  applyCfgMode();
  if (cfgState.doc && cfgDirty()) { renderCfg(); return; }
  await loadConfigDoc();
  loadBindingForBanner().catch(() => {});
  renderCfg();
}

async function loadBindingForBanner() {
  cfgState.doctor = await api("/api/doctor");
  renderHotkeyBanner();
}

function applyCfgMode() {
  const form = cfgState.mode === "form";
  $("#btn-cfg-form").classList.toggle("active", form);
  $("#btn-cfg-raw").classList.toggle("active", !form);
  $("#cfg-nav").hidden = !form;
  $("#cfg-content").hidden = !form;
  $("#cfg-raw-wrap").hidden = form;
  $("#cfg-search").hidden = !form;
}

function setCfgMode(mode) {
  if (cfgDirty() && !confirm("Discard the unsaved edits?")) return;
  cfgState.mode = mode;
  store(CFG_MODE_KEY, mode);
  loadConfigTab().catch((err) => toastError("Config failed", err));
}

// ---- rendering --------------------------------------------------------------

function warningFor(key) {
  const w = (cfgState.doc.warnings || []).find((line) => line.includes(`config ${key}=`));
  return w ? w.replace(/^paster: config /, "") : null;
}

function cfgInputHtml(field, value) {
  const key = esc(field.key);
  switch (field.type) {
    case "bool": {
      const on = (value === "" ? field.default : String(value)).toLowerCase();
      const checked = ["true", "yes", "on", "1"].includes(on);
      return `<label class="cfg-check"><input class="cfg-input" type="checkbox" data-key="${key}" ${checked ? "checked" : ""}>
        <span>${checked ? "enabled" : "disabled"}</span></label>`;
    }
    case "int":
      return `<input class="cfg-input" type="number" data-key="${key}" min="${field.min}" max="${field.max}" value="${esc(value)}" placeholder="${esc(field.default)}">`;
    case "color": {
      const hex = /^#[0-9a-f]{6}$/i.test(value) ? value : field.default;
      return `<div class="cfg-color"><input class="cfg-input cfg-color-pick" type="color" data-key="${key}" value="${esc(hex)}" aria-label="${esc(field.label)} colour">
        <input class="cfg-input cfg-color-hex" type="text" data-key="${key}" maxlength="7" value="${esc(value)}" placeholder="${esc(field.default)}" spellcheck="false"></div>`;
    }
    case "classes": {
      const chips = String(value || "").split("|").filter(Boolean);
      return `<div class="cfg-chips" data-key="${key}">${chips.map((c) => `<span class="chip">${esc(c)}<span class="chip-x codicon codicon-close" data-chip="${esc(c)}" title="Remove"></span></span>`).join("")}
        <input type="text" class="cfg-input toolbar-input cfg-chip-add" data-key="${key}" placeholder="add WM_CLASS, Enter" spellcheck="false"></div>
        <div class="cfg-effective">Empty = the default list (${field.default.split("|").length} terminals).</div>`;
    }
    default:
      return `<input class="cfg-input" type="text" data-key="${key}" value="${esc(value)}" placeholder="${esc(field.default) || "(auto)"}" spellcheck="false">`;
  }
}

function cfgRowHtml(section, field) {
  const value = cfgState.working[field.key] ?? "";
  const modified = (value ?? "") !== (cfgState.doc.values[field.key] ?? "");
  const warning = warningFor(field.key);
  const pre = cfgState.preflight[field.key];
  const msg = pre && !pre.ok ? `${pre.message} — the popup would use ${pre.effective}` : warning;
  const search = `${section.title} ${field.label} ${field.key} ${field.desc}`.toLowerCase();
  // The kit's .setting-row/.setting-title/.setting-desc carry the spacing and
  // the bold title; .cfg-* is the settings-editor layer solGit uses too.
  return `<div class="setting-row cfg-row ${modified ? "modified" : ""}" data-key="${esc(field.key)}" data-search="${esc(search)}">
    <div class="cfg-row-head"><span class="setting-title cfg-label">${esc(field.label)}</span><code class="cfg-key">${esc(field.key)}</code>
      <span class="cfg-applies">applies: ${esc(field.applies)}</span></div>
    <div class="setting-desc cfg-desc">${esc(field.desc)}</div>
    ${cfgInputHtml(field, value)}
    ${msg ? `<div class="cfg-field-msg"><span class="codicon codicon-warning"></span> ${esc(msg)}</div>` : ""}
    ${!value && field.key in cfgState.doc.effective && field.type !== "classes" ? `<div class="cfg-effective">default: ${esc(cfgState.doc.effective[field.key] || "(auto)")}</div>` : ""}
  </div>`;
}

// Scroll-spy: the section under the top of the pane owns the accent border
// in the nav, as in solGit.
function updateCfgNavActive() {
  const pane = $("#cfg-content");
  if (!pane || pane.hidden) return;
  const top = pane.getBoundingClientRect().top + 24;
  let current = null;
  $$("#cfg-content .cfg-section").forEach((sec) => { if (sec.getBoundingClientRect().top <= top) current = sec.dataset.sec; });
  const items = $$("#cfg-nav .cfg-nav-item");
  if (!current && items.length) current = items[0].dataset.sec;
  items.forEach((b) => b.classList.toggle("active", b.dataset.sec === current));
}

function renderCfg() {
  const doc = cfgState.doc;
  if (!doc) return;
  applyCfgMode();
  if (cfgState.mode === "raw") {
    const ta = $("#cfg-raw");
    if (document.activeElement !== ta) ta.value = doc.raw;
  } else {
    const { sections, fields } = doc.schema;
    $("#cfg-content").innerHTML = `<div class="cfg-note">Editing <b>config.yaml</b>. Values are replaced in place — your comments and order stay.
        Look and size keys apply on the next toggle, paste keys on the next Enter, the hotkey after Apply (install.sh).</div>` +
      sections.map((s) => `<section class="cfg-section" data-sec="${esc(s.id)}">
        <div class="cfg-sec-head"><h3>${esc(s.title)}</h3></div><div class="cfg-sec-desc">${esc(s.desc)}</div>
        <div class="cfg-rows">${fields.filter((f) => f.section === s.id).map((f) => cfgRowHtml(s, f)).join("")}</div></section>`).join("");
    $("#cfg-nav").innerHTML = sections.map((s) => `<button class="settings-nav-item cfg-nav-item" data-sec="${esc(s.id)}"><span class="cfg-nav-dot"></span>${esc(s.title)}
        <span class="cfg-nav-count">${fields.filter((f) => f.section === s.id).length}</span></button>`).join("");
    $$("#cfg-nav .cfg-nav-item").forEach((b) => b.addEventListener("click", () => {
      const sec = $(`#cfg-content .cfg-section[data-sec="${b.dataset.sec}"]`); if (sec) sec.scrollIntoView({ block: "start", behavior: "smooth" }); }));
    $("#cfg-content").onscroll = updateCfgNavActive;
    updateCfgNavActive();
    wireCfgInputs();
    applyCfgFilter();
  }
  renderCfgWarnings();
  renderHotkeyBanner();
  updateCfgDirty();
}

function wireCfgInputs() {
  $$("#cfg-content .cfg-input").forEach((input) => {
    const key = input.dataset.key;
    if (input.classList.contains("cfg-chip-add")) {
      input.addEventListener("keydown", (e) => {
        if (e.key !== "Enter" && e.key !== ",") return;
        e.preventDefault();
        const token = input.value.trim().replace(/,$/, "");
        if (!token) return;
        const chips = String(cfgState.working[key] || "").split("|").filter(Boolean);
        if (!chips.includes(token)) chips.push(token);
        setWorking(key, chips.join("|"), true);
      });
      return;
    }
    input.addEventListener("input", () => {
      const value = input.type === "checkbox" ? (input.checked ? "true" : "false") : input.value;
      if (input.type === "checkbox") input.parentElement.querySelector("span").textContent = input.checked ? "enabled" : "disabled";
      if (input.classList.contains("cfg-color-pick")) { const hex = input.parentElement.querySelector(".cfg-color-hex"); if (hex) hex.value = value; }
      if (input.classList.contains("cfg-color-hex") && /^#[0-9a-f]{6}$/i.test(value)) { const pick = input.parentElement.querySelector(".cfg-color-pick"); if (pick) pick.value = value; }
      setWorking(key, value, false);
    });
  });
  $$("#cfg-content .chip-x").forEach((x) => x.addEventListener("click", () => {
    const key = x.closest(".cfg-chips").dataset.key;
    const chips = String(cfgState.working[key] || "").split("|").filter((c) => c && c !== x.dataset.chip);
    setWorking(key, chips.join("|"), true);
  }));
}

let preflightTimer = null;
function setWorking(key, value, rerender) {
  cfgState.working = { ...cfgState.working, [key]: value };
  const row = $(`#cfg-content .cfg-row[data-key="${key}"]`);
  if (row) row.classList.toggle("modified", (value ?? "") !== (cfgState.doc.values[key] ?? ""));
  updateCfgDirty();
  clearTimeout(preflightTimer);
  preflightTimer = setTimeout(async () => {
    try {
      const d = await api("/api/config/preflight", { method: "POST", body: { values: { [key]: value } } });
      cfgState.preflight = { ...cfgState.preflight, ...d.fields };
    } catch (_) { /* the save reports the truth anyway */ }
    if (rerender || document.activeElement === document.body || !document.activeElement.closest(`.cfg-row[data-key="${key}"]`)) renderCfg();
    else updateFieldMessage(key);
  }, rerender ? 0 : 300);
  if (rerender) renderCfg();
}

function updateFieldMessage(key) {
  const row = $(`#cfg-content .cfg-row[data-key="${key}"]`);
  if (!row) return;
  const old = row.querySelector(".cfg-field-msg");
  const pre = cfgState.preflight[key];
  const msg = pre && !pre.ok ? `${pre.message} — the popup would use ${pre.effective}` : null;
  if (old) old.remove();
  if (msg) row.appendChild(el("div", "cfg-field-msg", `<span class="codicon codicon-warning"></span> ${esc(msg)}`));
}

function applyCfgFilter() {
  const q = cfgState.search.trim().toLowerCase();
  const counts = {};
  $$("#cfg-content .cfg-row").forEach((row) => {
    const show = !q || row.dataset.search.includes(q);
    row.hidden = !show;
    const sec = row.closest(".cfg-section").dataset.sec;
    counts[sec] = (counts[sec] || 0) + (show ? 1 : 0);
  });
  $$("#cfg-content .cfg-section").forEach((s) => { s.hidden = q && !counts[s.dataset.sec]; });
  $$("#cfg-nav .cfg-nav-item").forEach((b) => { b.hidden = q && !counts[b.dataset.sec]; b.querySelector(".cfg-nav-count").textContent = counts[b.dataset.sec] || 0; });
}

function renderCfgWarnings() {
  const box = $("#config-warnings");
  const w = cfgState.doc.warnings || [];
  box.hidden = w.length === 0;
  box.innerHTML = w.length ? `<b>lib-config.sh warns:</b> ${w.map((l) => esc(l.replace(/^paster: config /, ""))).join(" · ")}` : "";
}

function renderHotkeyBanner() {
  const box = $("#hotkey-banner");
  const d = cfgState.doctor;
  if (!d || !cfgState.doc) { box.hidden = true; return; }
  const wanted = cfgState.working.hotkey || d.config_hotkey;
  let text = null;
  if (!d.binding.present) text = `The hotkey is not wired — ${esc(d.binding.file)} is missing. Apply runs ./install.sh and reloads i3.`;
  else if (d.binding.stale) text = `The i3 binding points at another checkout (${esc(d.binding.script)}). Apply rebinds it to this one.`;
  else if (wanted && d.binding.hotkey && wanted !== d.binding.hotkey) text = `config.yaml says <b>${esc(wanted)}</b> but i3 binds <b>${esc(d.binding.hotkey)}</b>. Save, then Apply to rebind.`;
  box.hidden = !text;
  if (!text) return;
  box.innerHTML = `<span class="codicon codicon-warning"></span> ${text}
    <button class="btn btn-sm" id="btn-hotkey-apply" ${d.display ? "" : 'disabled title="no DISPLAY in the server environment"'}>Apply now</button>`;
  const btn = $("#btn-hotkey-apply");
  if (btn) btn.addEventListener("click", async () => {
    if (cfgDirty()) { toast("Save the config first, then Apply", "warn"); return; }
    await runAction("apply_install");
    loadBindingForBanner().catch(() => {});
  });
}

function updateCfgDirty() {
  const dirty = cfgDirty();
  $("#btn-config-save").disabled = !dirty;
  $("#btn-config-discard").disabled = !dirty;
  const n = cfgState.mode === "form" ? Object.keys(changedValues()).length : (dirty ? 1 : 0);
  $("#config-status").textContent = dirty ? `${n} unsaved change${n === 1 ? "" : "s"}` : "";
  setBadge("config", n);
}

// ---- save / discard ---------------------------------------------------------

async function saveConfig() {
  const doc = cfgState.doc;
  try {
    let saved;
    if (cfgState.mode === "raw") {
      saved = await api("/api/config/raw", { method: "PUT", body: { text: $("#cfg-raw").value, base_rev: doc.rev } });
    } else {
      const values = changedValues();
      if (!Object.keys(values).length) return;
      saved = await api("/api/config", { method: "PUT", body: { values, base_rev: doc.rev } });
    }
    cfgState.doc = saved;
    cfgState.working = { ...saved.values };
    cfgState.preflight = {};
    renderCfg();
    toast(saved.warnings.length ? `Saved with ${saved.warnings.length} warning(s) — see the banner` : "Saved", saved.warnings.length ? "warn" : "ok");
    loadBindingForBanner().catch(() => {});
  } catch (err) {
    if (err.status === 409) toast("config.yaml changed on disk meanwhile — Discard to reload, then redo the edit", "warn");
    else toastError("Save failed", err);
  }
}

function discardConfig() {
  cfgState.working = { ...cfgState.doc.values };
  cfgState.preflight = {};
  const ta = $("#cfg-raw"); if (ta) ta.value = cfgState.doc.raw;
  loadConfigDoc().then(renderCfg).catch(() => renderCfg());
}

// The snapshot ring for config.yaml (plan D5), in the same modal the Entries
// view uses — so a bad save, or an edit made with vim, can be taken back.
function openConfigHistory() {
  if (!cfgState.doc) return;
  if (cfgDirty()) { toast("Save or Discard the pending edits first", "warn"); return; }
  openHistoryModal("config.yaml", "config.yaml", () => cfgState.doc.rev,
    async () => { await loadConfigDoc(); renderCfg(); loadBindingForBanner().catch(() => {}); });
}

function setupConfig() {
  $("#btn-cfg-form").addEventListener("click", () => setCfgMode("form"));
  $("#btn-cfg-raw").addEventListener("click", () => setCfgMode("raw"));
  $("#btn-config-save").addEventListener("click", saveConfig);
  $("#btn-config-discard").addEventListener("click", discardConfig);
  $("#btn-config-history").addEventListener("click", openConfigHistory);
  $("#cfg-search").addEventListener("input", (e) => { cfgState.search = e.target.value; applyCfgFilter(); });
  $("#cfg-raw").addEventListener("input", updateCfgDirty);
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "s" && activeView() === "config") { e.preventDefault(); if (cfgDirty()) saveConfig(); }
  });
  window.addEventListener("beforeunload", (e) => { if (cfgDirty()) { e.preventDefault(); e.returnValue = ""; } });
}
