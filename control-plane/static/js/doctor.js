// paster — the Doctor view: install state, dependencies, stale state, entry
// health, plus the gated desktop actions (open the popup, apply the hotkey,
// run the bash tests, clear state). Every action's argv is shown.
"use strict";

const doctorState = { data: null, running: null };
const STATUS_KIND = { ok: "ok", warn: "warn", fail: "error", na: "neutral" };
const ACTION_ICON = { open_popup: "play", apply_install: "rocket", run_tests: "beaker", clear_state: "clear-all" };

async function loadDoctor() {
  doctorState.data = await api("/api/doctor");
  renderDoctor();
}

function renderDoctor() {
  const d = doctorState.data;
  if (!d) return;
  const s = d.summary;
  $("#doctor-summary").textContent = `${s.ok} ok · ${s.warn} warn · ${s.fail} fail · ${d.flavour} i3 · ${d.display ? "display" : "no display"}`;
  setBadge("doctor", s.fail + s.warn);
  $("#doctor-body").innerHTML = `<table class="data-table doctor-table"><thead><tr><th>Status</th><th>Check</th><th>Detail</th></tr></thead><tbody>
    ${d.checks.map((c) => `<tr class="${esc(c.status)}"><td>${pill(c.status, STATUS_KIND[c.status] || "neutral")}</td>
      <td>${esc(c.title)}</td><td>${esc(c.detail)}${c.fix ? `<div class="doctor-fix">${esc(c.fix)}</div>` : ""}</td></tr>`).join("")}
    </tbody></table>`;
  $("#doctor-actions").innerHTML = (d.actions || []).map((a) => `
    <button class="btn btn-sm ${a.name === "apply_install" ? "" : "secondary"}" data-action="${esc(a.name)}" ${a.enabled && !a.running ? "" : "disabled"}
      title="${esc(a.reason || a.description)}&#10;${esc(a.argv.join(" "))}">
      <span class="codicon codicon-${ACTION_ICON[a.name] || "play"}"></span>${esc(a.title)}</button>`).join("");
  $$("#doctor-actions [data-action]").forEach((b) => b.addEventListener("click", () => runAction(b.dataset.action)));
}

function showActionOutput(result) {
  const box = $("#doctor-output");
  if (!box) return;
  box.hidden = false;
  box.textContent = `$ ${result.name}  (rc=${result.rc}${result.timed_out ? ", timed out" : ""}, ${result.duration_s}s)\n${result.output || "(no output)"}`;
}

// Shared by the title bar's Open popup, the Doctor's action row and
// Config's Apply now.
async function runAction(name) {
  const spec = (doctorState.data && doctorState.data.actions || []).find((a) => a.name === name);
  if (name === "apply_install") {
    const ok = await new Promise((resolve) => openModal("Apply the hotkey", `<p>This runs <code>./install.sh</code>: it rewrites the paster block of the i3 config
        from config.yaml and reloads i3 on the laptop.</p><p class="form-help">Missing rofi/xdotool/xclip would be apt-installed, which needs sudo and would fail here — the Doctor lists them.</p>`,
      [{ label: "Cancel", secondary: true, onClick: () => { closeModal(); resolve(false); } },
       { label: "Apply", onClick: () => { closeModal(); resolve(true); } }]));
    if (!ok) return null;
  }
  if (name === "open_popup") toast("Opening the popup on the laptop's screen…", "info", 2000);
  doctorState.running = name;
  try {
    const result = await api(`/api/actions/${encodeURIComponent(name)}`, { method: "POST" });
    showActionOutput(result);
    toast(`${spec ? spec.title : name}: ${result.ok ? "done" : `failed (rc=${result.rc})`}`, result.ok ? "ok" : "warn");
    if (activeView() === "doctor") loadDoctor().catch(() => {});
    return result;
  } catch (err) {
    toastError(spec ? spec.title : name, err);
    return null;
  } finally {
    doctorState.running = null;
  }
}

// "Open the real popup" lives in the title bar, so it is one tap away on
// every view — from a phone it is a remote trigger for the laptop's screen.
function setupPopupLaunch() {
  $("#btn-popup-open").addEventListener("click", () => runAction("open_popup"));
  registerCommand({ id: "popup.open", label: "Open the real popup", icon: "play", mobile: true, run: () => runAction("open_popup") });
}

function syncPopupLaunch(display) {
  const b = $("#btn-popup-open");
  if (!b) return;
  b.disabled = !display;
  b.title = display ? "Open the real popup — runs bin/toggle.sh on the laptop's screen"
                    : "Disabled: the server has no DISPLAY (see Doctor)";
}

function setupDoctor() {
  $("#btn-doctor-refresh").addEventListener("click", () => loadDoctor().catch((e) => toastError("Doctor failed", e)));
  registerCommand({ id: "doctor.tests", label: "Run the bash tests", icon: "beaker", run: () => { switchView("doctor"); runAction("run_tests"); } });
  registerCommand({ id: "doctor.apply", label: "Apply hotkey (install.sh)", icon: "rocket", run: () => runAction("apply_install") });
}
