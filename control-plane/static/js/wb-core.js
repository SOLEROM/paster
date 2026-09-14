/* ==========================================================================
   vsCodeFront — wb-core.js: the helpers every module of a workbench SPA uses
   ==========================================================================
   Classic script (no module, no bundler), loaded with `defer` FIRST among
   the app's scripts. It defines plain globals on purpose — that is the idiom
   every app in the family (resman, mentora, solGit, soldo) is written in, so
   a feature module ported from one of them runs unchanged:

       $, $$, el, esc, store, restore, api, wireButton, toggleRegion,
       restoreRegions, renderMarkdown, fmtAge, fmtSince, fmtDuration, fmtDate

   Render idiom used everywhere in these SPAs:
       loadX() → state → renderX() builds ONE template-literal string →
       a single innerHTML assignment → wireX(box) re-binds [data-act] listeners.
   Every interpolation goes through esc(); markdown goes through
   marked + DOMPurify. Nothing polls — socket events say "something moved"
   and the SPA asks what.

   PER-APP SETTINGS ride on <html>, never on edits to this file:
       <html data-app="soldo">   → localStorage prefix "soldo-…" and the
                                   X-Requested-With CSRF value; default "wb"
   ========================================================================== */
"use strict";

/** The app id: storage-key prefix and CSRF header value. */
const WB_APP = (document.documentElement.getAttribute("data-app") || "wb").trim() || "wb";

const $ = (sel, root) => (root || document).querySelector(sel);
const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

/** createElement with class + innerHTML in one call (caller escapes). */
const el = (tag, cls, html) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (html !== undefined) node.innerHTML = html;
  return node;
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
const esc = escapeHtml;

/* ----- Persistence -----
   localStorage is wrapped everywhere: it throws in private-mode browsers,
   and a UI preference is never worth breaking a render over. Keys are
   prefixed with the app id so two apps behind one origin do not overwrite
   each other's choices. */
function storageKey(key) { return `${WB_APP}-${key}`; }

function store(key, value) {
  try { localStorage.setItem(storageKey(key), value); } catch (_) { /* private mode */ }
}

function restore(key) {
  try { return localStorage.getItem(storageKey(key)); } catch (_) { return null; }
}

function forget(key) {
  try { localStorage.removeItem(storageKey(key)); } catch (_) { /* private mode */ }
}

/* ----- REST -----
   All fetch goes through here so the CSRF header is always set. The server
   side checks `X-Requested-With: <app>` on every mutating route — a browser
   cannot attach a custom header to a cross-origin form post, so a random
   page cannot drive the API. It is a CSRF guard, not authentication.
   Errors: the server answers {"error": "<message>"} with a 4xx/5xx; the
   thrown Error carries .status and .body. */
async function api(path, opts = {}) {
  const headers = {
    "Content-Type": "application/json",
    "X-Requested-With": WB_APP,
    ...(opts.headers || {}),
  };
  const init = { ...opts, headers };
  if (init.body && typeof init.body !== "string") init.body = JSON.stringify(init.body);
  const res = await fetch(path, init);
  let body = null;
  try { body = await res.json(); } catch (_) { body = null; }
  if (!res.ok) {
    const err = new Error((body && body.error) || `HTTP ${res.status}`);
    err.status = res.status;
    err.body = body;
    throw err;
  }
  return body;
}

/* ----- Accessibility helpers ----- */

/** Click + keyboard (Enter/Space) activation for a role="button" element —
    the shared wiring for every non-<button> toggle in the UI. */
function wireButton(node, onActivate) {
  if (!node) return;
  node.addEventListener("click", onActivate);
  node.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onActivate(e); }
  });
}

/** Collapsible region: class flip + aria-expanded mirror + "1"/"0" in
    storage under region-<data-region>, restored with persist=false.
    Markup: <section class="region" data-region="ops">
              <div class="region-head">…</div><div class="region-body">…</div> */
function toggleRegion(node, force, persist = true) {
  if (!node) return;
  const collapsed = force === undefined ? !node.classList.contains("collapsed") : force;
  node.classList.toggle("collapsed", collapsed);
  const head = node.querySelector(".region-head");
  if (head) head.setAttribute("aria-expanded", collapsed ? "false" : "true");
  if (persist && node.dataset.region) {
    store(`region-${node.dataset.region}`, collapsed ? "1" : "0");
  }
}

/** Restore every .region[data-region] under root. On a phone the regions
    default to collapsed except the one flagged data-region-open (actions one
    tap away rather than a scroll away); an explicit saved choice wins. */
function restoreRegions(root) {
  const narrow = typeof isMobile === "function" && isMobile();
  $$(".region[data-region]", root).forEach((node) => {
    const saved = restore(`region-${node.dataset.region}`);
    if (saved !== null) {
      toggleRegion(node, saved === "1", false);
    } else if (narrow && !node.hasAttribute("data-region-open")) {
      toggleRegion(node, true, false);
    }
  });
}

/* ----- Markdown -----
   Docs and item bodies are files on disk, but they still go through
   DOMPurify: marked has had no sanitize option since v5, and a body may be
   written by an agent. If either library is missing we degrade to escaped
   plain text rather than rendering unsafely. */
function renderMarkdown(target, text) {
  const canRender = window.marked && typeof window.marked.parse === "function";
  const canSanitize = window.DOMPurify && typeof window.DOMPurify.sanitize === "function";
  if (canRender && canSanitize) {
    target.innerHTML = window.DOMPurify.sanitize(window.marked.parse(text || ""));
  } else {
    target.innerHTML = `<pre>${esc(text || "")}</pre>`;
  }
}

/* ----- Formatting ----- */
function fmtAge(seconds) {
  if (seconds == null) return "";
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m${s % 60 ? ` ${s % 60}s` : ""}`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return `${Math.floor(s / 86400)}d`;
}

function fmtSince(iso) {
  if (!iso) return "";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  return `${fmtAge((Date.now() - t) / 1000)} ago`;
}

function fmtDuration(startIso, endIso) {
  if (!startIso) return "";
  const start = Date.parse(startIso);
  const end = endIso ? Date.parse(endIso) : Date.now();
  if (Number.isNaN(start) || Number.isNaN(end)) return "";
  return fmtAge((end - start) / 1000);
}

function fmtDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toISOString().slice(0, 10);
}

/** A status dot / pill pair every list view ends up needing. */
function stateDot(value) {
  return `<span class="tree-dot ${esc(value || "idle")}" title="${esc(value || "")}"></span>`;
}

function pill(text, kind = "neutral", icon = null) {
  const ic = icon ? `<span class="codicon codicon-${esc(icon)}"></span>` : "";
  return `<span class="pill ${esc(kind)}">${ic}${esc(text)}</span>`;
}
