---
project: paster
type: flask-web-service
target_repo: /proj/myGits/bench/paster
strategy_hint: 'a control plane INSIDE the paster repo (control-plane/ beside bin/), first real adopter of the vsCodeFront + 4ColThems kits, started from vsCodeFront/skeleton. The rofi scripts stay the engine and the source of truth: the GUI only reads and rewrites entries/*/content.md and config.yaml in the exact format toggle.sh / tab-mode.sh / lib-config.sh already read, and asks those scripts (never re-implements them) whenever it needs their view of the files. Phase 0 scaffold → Phase 1 entries/tabs → Phase 2 config/preview/doctor → Phase 3 family integration (webterm, cldBar, bench docking, unit). One agent, phases in order, tests first.'
version: 1
date: '2026-09-14'
status: implemented 2026-09-14 (phases 0–3, all of §3–§13; 249 pytest + 85 bash checks green, coverage 95 %; the `paster` unit runs on 6012 and is docked in mainBench). Deviations: `toggle.sh --list-tabs` exits 0 with empty output on an empty entries/ (an empty list is an answer); stale revisions surface as fileio.StaleRevision with the current rev in the 409 body; the Q1–Q7 recommendations were taken as decided when the build was ordered ("build that fully"). The Changes view (§7: git status/diff/revert, `modules/git_util.py`, `/api/git/*`, `man/05-changes.md`) was built and removed the same day on request — git stays in the shell, never in the front; config.yaml's snapshot history became a History button in the Config view (§5), and the help pages are renumbered 00–06. The Preview view (§5's HTML mock, `preview.js`) was removed the same day as well: **Open popup** sits in the title bar on every view instead, and the Sessions view gained a **Shell in the repo** button (what the webterm strip's + does, named). Phase 4 (§15) untouched. Not git-committed.
---

# paster front — a control plane for the entries, the config and the install

> Goal: a web GUI, in the family's VS Code shape, that makes the day-to-day
> of paster comfortable: **add, edit, reorder, move and delete prompt entries
> and tabs**, edit `config.yaml` with validation and a live preview of the
> popup, see whether the hotkey is actually wired and every dependency is
> present, and reach all of it from the tailnet (phone included) through the
> mainBench shell like the other apps. The rofi side is untouched: what the
> GUI writes is exactly what `toggle.sh` rescans on the next hotkey press.

Prior art considered: the family's own pieces cover this shape end to end —
`vsCodeFront/skeleton` (the copy-to-start Flask app), solGit's Form/YAML
config editor (`vsCodeFront/reference/examples/solgit-config.js`), solSeed's
`frame_ancestors` for docking, soldo's `run.sh` for the launcher contract.
Generic snippet managers (clipboard managers, text expanders) were not
adopted: they bring their own store and their own popup, while the whole
point here is a GUI over the files rofi already reads.

## 0. Current state (what exists, 2026-09-14, this laptop)

- **paster v3** at the repo root: `bin/toggle.sh` (hotkey → rofi),
  `bin/tab-mode.sh` (one rofi script-mode per tab), `bin/paste-back.sh`
  (clipboard → refocus → keystroke), `bin/lib-config.sh` (flat `key: value`
  reader with validators and defaults), `install.sh` (deps + i3 wiring),
  `config.yaml`, `entries/<NN_Tab>/content.md`, `tests/run.sh` (bash, 52 + 23
  green). No `run.sh`, `.port`, venv, unit or solBench dependency: the repo
  is "not a service" in the bench's roster.
- **Data format** (the contract the GUI must keep): each subfolder of
  `entries/` with a `content.md` is a tab; folder order = tab order; a
  leading `NN_` is stripped from the label; `, : ' "` are dropped from the
  label; colliding labels get a ` 2`, ` 3` suffix; every **non-empty line**
  of `content.md` is one entry (`awk 'NF'`); no comments, no multi-line
  entries. `config.yaml` is flat, comment-rich, read by bash with `sed`.
- **Host facts that shape the design:**
  - `systemctl --user show-environment` carries `DISPLAY=:1`, `XAUTHORITY`
    and `I3SOCK` — a systemd user unit *can* open the real popup and talk to
    i3. `I3SOCK` goes stale when i3 restarts (the pid is in the name), so it
    must be re-resolved at call time, never trusted from the env.
  - Regolith i3 (`i3 -c /etc/regolith/i3/config`), picom running (real
    transparency), rofi 1.7.5, xdotool 3.2016, X11 session.
  - **The hotkey is not wired today**: `~/.config/regolith3/i3/config.d/`
    holds only `myConfs`; the `90_paster` drop-in the 2026-09-13 move log
    says was written is gone (the 2026-09-13 "clean local files" session is
    the likely cause), and `~/.config/i3/config` is back to the wizard
    stub. `./install.sh` restores it. This is exactly the class of drift
    the Doctor view (§6) exists to surface.
  - Free port: **6012** (6009 is reserved "don't reuse" in `myApps.md`).
  - vsCodeFront and 4ColThems are adopted by no app yet — this app would be
    the first, starting from the skeleton rather than carving an app.

## 1. Decisions

- **D1 — it lives in the paster repo.** `control-plane/` beside `bin/`,
  `run.sh` and `.port` at the root, like every app in the family
  (cldlab, soldo, solGit, mentora, resman, interpreta all have
  `control-plane/server.py`). The rofi scripts are the engine, the control
  plane is the GUI over the same files. A separate `pasterFront` repo was
  rejected: it would have to find `../paster` as a sibling, add a 13th
  repo to clone/move/register, and split one feature's history in two for
  no gain.
- **D2 — first adopter of the kits.** Start from `vsCodeFront/skeleton`;
  4ColThems + vsCodeFront + cldBar are **copy-ins, committed** (so a lone
  clone runs), refreshed by `run.sh` when solBench is present and
  drift-checked by a test (`install.sh --verify`). Kit gaps go upstream to
  solBench, never into the copied files.
- **D3 — the GUI invents no syntax.** It writes `content.md` as the
  non-empty lines plus a trailing newline, and folder names as `NN_Name`.
  No front-matter, no comments, no metadata file next to the entries.
  Anything the GUI needs beyond that (history, trash, later usage counts)
  lives under `~/.paster/`, outside the repo. Phase 1–3 change **no**
  runtime script except one additive `--list-tabs` flag on `toggle.sh`
  (D4).
- **D4 — bash is the truth; the server asks it.** Labels come from
  `bin/toggle.sh --list-tabs` (new, prints `label\tdir` and exits before
  any X work); config values and warnings come from sourcing
  `bin/lib-config.sh` on the file and dumping `PASTER_CFG_*`. The Python
  side keeps a small **schema** (key, type, range, default) only for
  form rendering and pre-flight feedback, and a parity test proves the
  schema agrees with bash on a fixture set. No second implementation of
  the validators is allowed to drift.
- **D5 — writes are safe by construction.** Atomic (`tmp` + `os.replace`);
  optimistic concurrency (every read returns a `rev` = sha256 of the file,
  every write carries `base_rev`, mismatch → 409 and the client reloads);
  a **snapshot** of the file into `~/.paster/history/` before every write
  (ring of 50 per file); tab deletion **moves** the folder to
  `~/.paster/trash/<ts>_<name>/`, never `rm -rf`. `config.yaml` edits are
  **in-place value replacement, line by line** (the file is flat), so
  comments and key order survive — the reason solGit needs a YAML mode
  does not apply here, but a Raw mode still exists for exotic edits.
- **D6 — per-action saves, no dirty buffer.** Every row action (add, edit,
  delete, reorder, move) is one `PUT` of the tab's line list. The phone
  case decided it: nothing to lose when the tab is closed, nothing to
  "Save" twice. The Config form is the exception (typed fields, one Save).
- **D7 — desktop actions are best-effort and gated.** "Open popup",
  "Apply hotkey (run `install.sh`)", "Run tests", "Clear stale state" run
  as argv subprocesses (no shell), with `DISPLAY`/`XAUTHORITY` taken from
  the server's own environment at call time and `I3SOCK` resolved fresh
  (`i3 --get-socketpath` under that `DISPLAY`). No `DISPLAY` → the buttons
  are disabled with the reason. One action at a time (a per-action lock)
  and a cooldown, so a double tap cannot open two popups or run two
  installers. Nothing host-specific (`:1`) is ever written in code.
- **D8 — same trust posture as the family.** No auth, `--public` on the
  tailnet, CSRF header `X-Requested-With: paster` on every mutating route,
  `Content-Security-Policy: script-src 'self'` (no inline scripts),
  `frame-ancestors` per solSeed's reference so mainBench can dock it,
  every file operation confined to `entries/` and `config.yaml` (tab ids
  validated by regex **and** the resolved path checked to stay under
  `ENTRIES_DIR`). The Doctor view lists every command it may run.
- **D9 — the control plane has no yaml of its own.** `config.yaml` stays
  the popup's file and the only one the Config view edits. The server's
  few settings are flags and env: `--port` › `.port` › code default,
  `--public`/`--host`, `PASTER_DATA_DIR` (default `~/.paster`),
  `PASTER_REMDEV_URL` (cldBar pin, unset by default), `PASTER_WEBTERM=0`.
- **D10 — port 6012, unit `paster`, app id `paster`.** The roster row in
  `solBench/myApps.md` and the mirror in `~/.config/mainbench/bench.toml`
  are host-policy edits the user makes when the unit goes live (Phase 3).

## 2. The GUI at a glance

```
title bar │ ▤ paster · Entries        │ [▶ Open popup] [Coding · 5 entries] │ ● connected · theme
──────────┼───────────────────────────┴─────────────────────────────────────┴────────────────
 ▤ Entries│ tabs (drag to reorder)   ║ Coding                 [+ Add] [⎘ Paste many] [🔍]
 ⚙ Config │  ALL            14       ║ ⋮ Explain this code step by step        ✎ ⧉ → 🗑 ⧘
 ♥ Doctor │  Coding          5  ✎ 🗑 ║ ⋮ Refactor this function for readab…    ✎ ⧉ → 🗑 ⧘
 ▣ Sessions│ Writing         4       ║ ⋮ Write unit tests for the following…   ✎ ⧉ → 🗑 ⧘
          │  General         4       ║ …
          │ [+ New tab]             ║
──────────┼─────────────────────────╨─────────────────────────────────────────────────
 ? Help   │ paster · Claude meters (cldBar)                      4 tabs · 18 entries · Log
```

Views are declared in markup the kit's way (one `.activity-item[data-view]`
+ one `section#panel-<view>`). The sidebar tree is the tab list for the
Entries view and is hidden (`data-sidebar="0"`) for Config, Doctor, Help.
`⧘` is the per-row **Copy** button: `navigator.clipboard` — the GUI doubles
as a remote paster from any device that can't run rofi.

## 3. Feature: repo scaffold — `run.sh`, `.port`, control plane, kits, deploy kit
<!-- solseed: custom category=config -->

Turn the repo into a bench app without touching the rofi side.

### Tasks
- [ ] `.port` = `6012`; `.gitignore` (`.venv*`, `__pycache__/`, `.pytest_cache/`, `.coverage`).
- [ ] `run.sh` at the root, soldo's shape: `ROOT` from `BASH_SOURCE`; plan §2.1 `SOLBENCH_HOME` sibling lookup; `--vname`, `--public`, `--test`, `--skip-deps`, `-h`; venv create + `requirements.txt` sha stamp; `ensure_kits` (4ColThems `--css/--js/--data/--py`, vsCodeFront `--static`, cldBar `<static/js>`; only when `SOLBENCH_HOME` is set and not `--skip-deps`); plan §2.2 `ensure_webterm` on **every** start; `exec "$VENV/bin/python" control-plane/server.py "${FORWARD[@]}"`. Always `python -m pip`, never `bin/pip` (R2).
- [ ] `control-plane/` from `vsCodeFront/skeleton`: `server.py` (`create_app()`, flags `--port/--host/--public`, precedence `--port` › `.port` › code default `8790`), `requirements.txt` (flask, flask-socketio, simple-websocket), `templates/index.html` (the kit's head order and viewport meta), `static/` with the kit copy-ins + `app.css` + one JS module per view + `main.js`.
- [ ] `modules/paths.py`: `REPO_ROOT = Path(__file__).resolve().parents[2]`, `ENTRIES_DIR`, `CONFIG_FILE`, `BIN_DIR`, `DATA_DIR` from `PASTER_DATA_DIR`. No other module builds a path from a literal.
- [ ] `modules/webutil.py`: `error()` envelope, `csrf_required`, CSP with `frame_ancestors` (solSeed's `app/webutil.py` copied, docstring kept), `asset_rev`.
- [ ] Routes `GET /api/health` (`{ok, app, webterm, display}`), the help tree/page pair from the skeleton over `man/`, `GET /api/logs` (activity ring, 2000 entries) + `activity_logged` socket event.
- [ ] `deploy/systemd/install.sh` + `paster.service.template` + `README.md`: solSeed's installer (`--vname`, `--bench-origins` validated, `--no-start`, `--uninstall`, port echoed from `.port`), template with `ExecStart=__PROJECT_PATH__/run.sh --skip-deps --public`, the quoted `Environment="BENCH_SHELL_ORIGINS=…"` line, and the host's hardened lines from day one (`StartLimitIntervalSec=300`, `StartLimitBurst=5`, `Restart=always`) so a reinstall never regresses them.
- [ ] `tests/conftest.py` (`REPO_ROOT`, `solbench_home()` per plan §2.3, a `repo` fixture that copies `entries/` + `config.yaml` into `tmp_path` and points `paths` at it, `CSRF = {"X-Requested-With": "paster"}`), `tests/test_no_host_paths.py` (gridar's self-skipping copy), `tests/test_kit_drift.py` (`install.sh --verify` for both kits; skips on a lone clone).
- [ ] `run.sh --test` = `tests/run.sh` (bash) **then** `pytest --cov=control-plane/modules --cov-fail-under=80`; both must pass.
- [ ] `README.md`: a "Front — the control plane" section (run, port, views, what it never does); `devRef/README.md` planning history points at this plan; `man/01-overview.md`.

### Definition of done
- `./run.sh` on a fresh clone creates the venv, refreshes the kits, serves the empty shell on `127.0.0.1:6012` with Help working; `PASTER_WEBTERM=0` and a lone clone (no `../solBench`) both start cleanly.
- `deploy/systemd/install.sh` installs a unit whose only host-specific lines are `WorkingDirectory`/`ExecStart`; `systemctl --user cat paster` shows the hardened restart lines.
- `test_no_host_paths` and `test_kit_drift` pass; `tests/run.sh` still 52 + 23.

### Estimate
0.5d

## 4. Feature: entries and tabs — the editing core
<!-- solseed: custom category=input-validation -->

### Model (server, `modules/entries_store.py` + `modules/tab_labels.py`)

- `list_tabs()` → `[{id: "10_Coding", label: "Coding", order: 10, count: 5, rev, mtime}]`. Labels come from `bin/toggle.sh --list-tabs` (D4); folders without `content.md` are listed separately as `ignored` so the GUI can show "3 folders ignored: no content.md" instead of hiding them.
- `read_tab(id)` → `{lines, rev}`; `write_tab(id, lines, base_rev)` → new rev, after snapshot; blank lines dropped, `\r` stripped, each line must be non-empty and contain no `\n`; 409 on rev mismatch; 404 on a missing tab.
- `create_tab(name, after=None)` → folder `NN_<name>` with `NN` = the next free step of 10 after `after` (renumbering only when no gap is left); `rename_tab(id, name)` keeps the `NN_`; `reorder_tabs([ids])` renumbers `10, 20, 30…` in that order (a rename of every folder, so it is one operation behind a lock and reported as one activity line); `delete_tab(id)` → `~/.paster/trash/`.
- `move_entry(from_id, index, to_id, position, base_revs)` = one snapshot pair, two writes, both revs checked first.
- `search(q)` → `[{tab, label, index, line}]` over every tab, plain substring, case-insensitive — the GUI's ALL mode; fuzzy ranking stays rofi's business.
- **Name rules** (validated at the boundary, one regex): `^[A-Za-z0-9][A-Za-z0-9 _.-]{0,63}$` for the human name; the id is `NN_` + name with spaces kept (the folder is the label); the resolved path must stay under `ENTRIES_DIR`; names that would collapse to the same rofi label as an existing tab (after dropping `, : ' "` and the prefix) are refused with the explanation rather than silently suffixed.
- `modules/history.py`: `snapshot(path)` → `~/.paster/history/<relpath>/<ts>.md` (ring 50), `list_history(relpath)`, `restore(relpath, ts, base_rev)` (itself a snapshotting write).
- `modules/watcher.py`: a 2 s mtime poll of `entries/*/content.md`, the folder list and `config.yaml` → `entries_changed {tab}` / `tabs_changed` / `config_changed` socket events, so an edit made in vim (or by rofi's `paster-last-tab`… no, that is runtime state, not watched) shows up in an open GUI without a reload.

### API
`GET /api/tabs` · `POST /api/tabs {name, after?}` · `PATCH /api/tabs/<id> {name}` · `PUT /api/tabs/order {ids}` · `DELETE /api/tabs/<id>` · `GET /api/tabs/<id>/entries` · `PUT /api/tabs/<id>/entries {lines, base_rev}` · `POST /api/entries/move` · `GET /api/search?q=` · `GET /api/history?file=` · `POST /api/history/restore`. All mutations `@csrf_required`; every error `{"error": "…"}` with 400/404/409.

### GUI (`static/js/tabs.js`, `entries.js`)
- Sidebar: the tab list with counts, `ALL` first; drag to reorder (Pointer Events, the kit's `sidebar-resizer` idiom); `+ New tab`; per-row ✎ rename / 🗑 delete (modal confirm names the trash path); ignored folders as a muted group.
- Panel: one row per entry — grip, text, ✎ (inline `<textarea>` that grows; Enter saves, Shift+Enter is refused with a toast "entries are one line — use Paste many to add several"), ⧉ duplicate, → move-to-tab dropdown, 🗑, ⧘ copy. Toolbar: **Add**, **Paste many** (a modal textarea: one entry per non-empty line, preview of the count, appended or inserted at the selection), **Sort A→Z** (explicit, never automatic, undoable through history), a filter box, count, refresh.
- ALL mode: the filter box in the sidebar searches every tab; results show `[Tab]  line` like rofi's combi format; clicking a result opens that tab and flashes the row (`revealRow`/`flashRow`).
- 409 handling: toast "changed on disk — reloaded", the panel reloads, the user's edit is kept in the textarea for a retry.
- Long entries (> 300 chars) get a "long" chip: rofi shows them on one line, so the chip is the hint, not a block.
- Phone: rows collapse to text + ⋯ (the kit's sheet with the same actions); drag is replaced by ▲/▼ inside the sheet.

### Tasks
- [ ] `tests/test-toggle-list.sh` (bash, RED): `toggle.sh --list-tabs` on a temp `entries/` prints `label\tdir` for prefix stripping, dropped chars, the ` 2` collision suffix, ignored folders, empty dir → exit 1 and message. Then the flag in `toggle.sh`, placed before the `pkill` and before any X call.
- [ ] `tests/test_tab_labels.py`: parity — the same fixture folders through `toggle.sh --list-tabs` and through `tab_labels.py` (used only for pre-flight "would collide" feedback) agree.
- [ ] `tests/test_entries_store.py`: round-trip keeps bytes except the edit; CRLF stripped; blank lines dropped and documented; 409 on stale rev; path confinement (`..`, `/abs`, `.hidden`, a `/` in the name); create/rename/reorder/delete with the trash; move between tabs is atomic on rev failure (nothing written).
- [ ] `tests/test_history.py`: ring of 50, restore is itself snapshotted, relpath confinement.
- [ ] `tests/test_routes_entries.py`: envelope, CSRF 403, every status code above through the test client, `search`.
- [ ] `tests/test_watcher.py`: touching a file emits the event once; no event on a no-op write.
- [ ] Implement `tab_labels.py`, `entries_store.py`, `history.py`, `watcher.py`, `routes_entries.py`, then `tabs.js`, `entries.js`, `app.css` (tokens only, no raw hex — the kit's `test_css.py` rule applies to app CSS too).
- [ ] `man/02-entries.md`: the format contract (D3), what "Paste many" does with blank lines, where history and trash live and how to empty them.

### Definition of done
- Add, edit, duplicate, reorder, move across tabs, delete, bulk paste, rename/reorder/create/delete tabs — each followed by a real hotkey press showing the change in rofi with no reload (the rescan-on-toggle contract).
- An edit made in vim while the GUI is open appears in the GUI within 2 s; a GUI save over a file vim changed meanwhile is refused with 409 and nothing is overwritten.
- No write path exists that skips the snapshot; `~/.paster/history` shows one file per save.
- Coverage of `entries_store.py`, `tab_labels.py`, `history.py` ≥ 95 %.

### Estimate
1.5d

## 5. Feature: config editor and popup preview
<!-- solseed: custom category=error-handling -->

> **Preview view removed 2026-09-14**, right after the build, on request: no HTML mock of the popup. **Open the real popup** moved into the title bar (`#btn-popup-open`, palette `popup.open`), so the truth is one tap away from every view and from a phone. `preview.js` and its panel are gone; the config editor below stands.

### Model (`modules/config_schema.py`, `modules/config_store.py`)
- `SCHEMA`: one entry per key of `config.yaml` — `hotkey` (free text, the installer's `^[A-Za-z0-9_+\$]+$`), `width_pct` 20–100, `height_pct` 10–100, `opacity_pct` 10–100, `font_size` 6–72, `border_px` 0–20, `background`/`foreground` `#rrggbb`, `auto_paste`/`press_enter` bool, `paste_delay_ms` 0–5000, `paste_key`/`terminal_paste_key` `^[A-Za-z0-9_]+(\+[A-Za-z0-9_]+)*$`, `terminal_classes` `^[A-Za-z0-9_.-]+(\|[A-Za-z0-9_.-]+)*$` — with the same defaults as `lib-config.sh`, grouped into the README's sections (Hotkey · Size · Look · Paste behavior), each with the README's one-line description.
- `read_config()` → `{values, effective, warnings, raw, rev}`: `values` = what the file says (parsed like `paster_cfg`: first match, quotes, trailing comment), `effective` + `warnings` = what bash actually resolves, obtained by sourcing `lib-config.sh` with `PASTER_CONFIG_FILE` set and dumping `declare -p ${!PASTER_CFG_@}` (stdout) and the `paster: config …` lines (stderr). The two differ exactly when a value is invalid — the GUI shows the bash warning next to the field.
- `write_config(values, base_rev)`: for each changed key, replace the value on its `^key:` line, keeping the trailing `# comment`; quote strings that need it (colors, keystrokes, classes, hotkey); a key absent from the file is appended under a `# added by paster front` line; then the bash dump runs again and its warnings come back in the response so an invalid value never lands silently. `write_raw(text, base_rev)` for the Raw mode.
- The **parity test** (D4): a fixture set of good/bad values per key goes through the schema and through `lib-config.sh`; both must agree on valid/invalid and on the fallback default.

### GUI (`config.js`, `preview.js`)
- Form mode: the kit's `.cfg-*` settings editor (solGit's example, adapted): search, section nav, typed controls (number with min/max, colour input + hex field, switch, text with the regex hint, `terminal_classes` as removable chips with an add box), gold "modified" bars, **Save** / **Discard**, the bash warning as a `.banner.warn` under the field. Raw mode: the file as text with comments, Save, and the same post-save warnings.
- **Hotkey drift banner**: the Doctor's `installed_hotkey` (§6) vs `config.yaml`'s `hotkey`; when they differ: "Hotkey changed since the last install — run `./install.sh`" with an **Apply now** button (D7) that runs the installer and streams its `[paster]` lines into the activity log.
- **Preview view**: an HTML mock of the popup drawn from the *unsaved* form values and the real tab list — tab bar (`ALL` + labels, the collision suffixes included), prompt line, the selected tab's entries, `width_pct`/`height_pct` as the mock's box, `background` + `opacity_pct` as its `rgba`, `foreground`, `font_size`, `border_px`. Same geometry logic as `paster.rasi.tmpl`; it is a picture, not rofi, and says so. A **Open the real popup** button runs `bin/toggle.sh` (D7) for the truth.

### Tasks
- [ ] `tests/test_config_schema.py` (parity with bash, RED first), `tests/test_config_store.py` (in-place write keeps comments/order/other keys byte-exact; quoting; absent key appended; invalid value still written but warning returned; 409), `tests/test_routes_config.py`.
- [ ] Implement `config_schema.py`, `config_store.py`, `routes_config.py`; `GET/PUT /api/config`, `PUT /api/config/raw`, `GET /api/config/schema`.
- [ ] `config.js` (Form/Raw), `preview.js` (`renderPreview(values, tabs)` pure, unit-tested in `tests/js/preview.test.mjs` over the kit's DOM stub if node is present), the two panels in `index.html`.
- [ ] `man/03-config.md`: what applies on the next toggle vs the next Enter vs needs `install.sh` (copied from the README so the Help view has it).

### Definition of done
- Changing `opacity_pct` in the form updates the preview before saving; saving and pressing the hotkey shows the same change in rofi.
- Typing `#12345` into `background` shows bash's own warning text ("want "#rrggbb"") and the effective default, in the field, before and after saving.
- `git diff config.yaml` after a form save touches only the changed value lines; comments and order are intact (pinned by a test on the shipped file).
- Every key of `lib-config.sh` is in the schema (a test walks `PASTER_CFG_*` in the script and fails on a missing key — the guard against the next `plan5` adding a key the GUI doesn't know).

### Estimate
1.5d

## 6. Feature: Doctor — install state, dependencies, desktop actions
<!-- solseed: custom category=healthcheck -->

### Checks (`modules/doctor.py`, pure functions over injected `env`, `PATH` and file roots — testable with stub binaries like `test-paste-back.sh` does)
- **Session**: `XDG_SESSION_TYPE`/`DISPLAY` from the server env; Wayland → "paster v3 is X11 only"; no `DISPLAY` → desktop actions disabled.
- **i3**: process present (`pgrep -x i3` via argv); flavour = Regolith (`~/.config/regolith3/i3/config.d` exists) or plain; the socket resolved fresh (`i3 --get-socketpath`).
- **Binding**: Regolith → does `config.d/90_paster` exist, which `bindsym` and which `toggle.sh` path does it hold (a *different* path = a stale install from before the move); plain → the `# >>> paster v3 >>>` block in `~/.config/i3/config`; `installed_hotkey` extracted from it, compared with `config.yaml` → the drift the Config view banners. Older `paster v1`/`v0i3` blocks are reported as leftovers.
- **Dependencies**: `rofi` (version, ≥ 1.6), `xdotool`, `xclip`, `xprop` (`x11-utils`), each with the apt package name the installer would use; `picom`/any compositor process → "real transparency" vs "pseudo".
- **State files**: `$XDG_RUNTIME_DIR/paster-prev-win`, `paster-last-tab` (shows the remembered tab), `paster.rasi` (rendered theme, mtime) — with a **Clear** action.
- **Entries health**: tabs, entries, empty tabs, ignored folders, duplicate lines across tabs, lines > 300 chars, folder names whose label would be empty after the char drop.
- **Tests**: last result of `tests/run.sh` (bash) with a **Run tests** action streaming the output.
- **Service**: whether this server runs under the `paster` unit (`INVOCATION_ID` set), its port, `.port`, bind host.

### Actions (`modules/actions.py`, D7)
`open_popup` (`bin/toggle.sh`), `apply_install` (`install.sh`, no key argument — `config.yaml` is the source), `run_tests` (`tests/run.sh`), `clear_state`. Each: argv list, `timeout`, `env` = the server's env + fresh `I3SOCK`, one lock per action, a 2 s cooldown, output captured into the activity log and returned. `POST /api/actions/<name>` → `{ok, rc, output}` or 409 "already running" / 503 "no DISPLAY". `GET /api/doctor` → the checks; `doctor_changed` is emitted after any action.

### Tasks
- [ ] `tests/test_doctor.py` (stub `PATH` binaries and a fake home in `tmp_path`: every check in its green, red and "not applicable" state; the stale-path detection; the missing-drop-in case that is true on this host today).
- [ ] `tests/test_actions.py`: argv only (no `shell=True`, pinned by grepping the module), lock and cooldown, timeout, disabled without `DISPLAY`, `I3SOCK` re-resolved.
- [ ] Implement `doctor.py`, `actions.py`, `routes_doctor.py`; `doctor.js` with the checks as `.data-table` rows (`.ok/.warn/.fail`), the actions as toolbar buttons, the output pane (`.log-view`).
- [ ] `man/04-doctor.md`: what each row means and the fix for each red one (the README's Troubleshooting, reorganised per check).

### Definition of done
- On this laptop today the Doctor shows the drop-in as missing and **Apply now** restores it; a hotkey press then opens the popup.
- With `DISPLAY` removed from the env the actions are disabled and the reason is shown; nothing else degrades.
- No action can run twice concurrently (test), and every action's argv is visible in the Help page (the trust statement).

### Estimate
1d

## 7. Feature: Changes — see and undo what the GUI did
<!-- solseed: custom category=logging -->

> **Removed 2026-09-14**, right after the build, on request: git status, diff and revert happen in the shell (the Sessions view or a terminal), never in the front. `git_util.py`, `routes_git.py`, `changes.js`, `man/05-changes.md` and their tests are gone; the config.yaml snapshot **History** moved to a button in the Config view (§5). The activity log (§3) stays. The section is kept as the record of what was built.

The repo is git-tracked and the user commits by hand. The view makes the
working-tree state visible without pretending to be a git client.

- `modules/git_util.py`: argv wrappers (`git -C REPO status --porcelain=v1 -- entries config.yaml`, `git diff -- <file>`, `git checkout -- <file>` behind a confirm). No push, no commit in this phase (Q2).
- `GET /api/git/status`, `GET /api/git/diff?file=`, `POST /api/git/revert {file, base_rev}` (snapshotted first, so a revert is itself undoable from history).
- `changes.js`: file list with `M/A/D/??` chips, a diff pane (the kit's `.log-view` with `+`/`-` rows coloured by token), **Revert to HEAD**, and per file the **History** list (snapshots) with **Restore**.
- The activity log (§3) records every write with tab, count and rev, so the log alone answers "what did the phone change at 14:02".

### Tasks
- [ ] `tests/test_git_util.py` (a `tmp_path` repo with an initial commit; status/diff/revert; the confinement to `entries/` + `config.yaml`), `tests/test_routes_git.py`.
- [ ] Implement, plus the badge on the activity item (`setBadge("changes", n)`).
- [ ] `man/05-changes.md`.

### Definition of done
- Every edit made through §4–§5 shows up in Changes with a correct diff; Revert restores the file and history still holds the pre-revert version.

### Estimate
0.5d

## 8. Feature: family integration — webterm, cldBar, bench docking, the unit
<!-- solseed: custom category=integration-testing -->

- **Sessions view (webterm)**: the skeleton's `spawn_resolver` (one tmux session `shell` in `REPO_ROOT`; the client sends ids, never paths), `TerminalConfig(tmux_socket="paster-term", tmux_prefix="paster-")`, xterm palettes from 4ColThems' `terminal-themes.json`, `webterm-glue.js` as a module; `PASTER_WEBTERM=0` leaves it out with the kit's placeholder. Why it earns its place here: `./install.sh` and `git` from the phone, without SSH.
- **cldBar**: `cldbar.js` copy-in + app-owned `cldbar-glue.js` (mount in `#cldbar-slot`, theme map from the `themechange` event, `data-remdev-url` from `PASTER_REMDEV_URL`); verified on the `light` theme (the transparency pitfall).
- **Docking**: `frame_ancestors` already in `webutil.py` (§3); `X-Frame-Options` never set; `tests/test_bench_embed.py` copied from solSeed and adapted; the unit's quoted `BENCH_SHELL_ORIGINS` line.
- **Going live** (host steps, done by the user, recorded in the README): `echo 6012 > .port` (already, §3), `deploy/systemd/install.sh`, the `myApps.md` roster row (`6012 | paster | bench/paster | .port; the rofi prompt paster's control plane`), the `bench.toml` `[[apps]]` row (`id = "paster"`, `icon = "codicon-clippy"`), `~/.solgit/registry.yaml` needs nothing (the repo is already registered).

### Tasks
- [ ] `tests/test_webterm_keyboard.py` (the viewport meta contract), `tests/test_cldbar_embed.py` (the kit's pitfalls, calling `solbench_home()` inside the kit test), `tests/test_bench_embed.py`, `tests/test_summary_placement.py` (the status bar row carries nothing that grows with state; counts go to `#summary-strip`).
- [ ] Implement the terminal mount, the glue files, the panel; run the unit through the move checklist's verification steps (port answers, a second restart logs no `[setup] installing webterm`, the import check from a neutral cwd).
- [ ] `man/05-deployment.md` (unit, port, `--public` trust statement, the roster/bench.toml mirror rule), `man/06-troubleshooting.md`.

### Definition of done
- `systemctl --user is-active paster`; `curl :6012/api/health` on the tailnet; the app docks in mainBench with a green dot and a working Sessions terminal on a phone; `pytest -rs` on this host reports **no skips**.

### Estimate
1d

## 9. Feature: tests, coverage and the two suites
<!-- solseed: custom category=testing -->

- Two suites, one command: `./run.sh --test` runs `tests/run.sh` (bash: config, paste-back, and the new `test-toggle-list.sh`) then `pytest` with `--cov-fail-under=80`. The bash suite stays framework-free; the Python suite is hermetic (`tmp_path` copies of `entries/` + `config.yaml`, stub binaries on `PATH`, no X, no network, no `~/.paster` of the developer touched — `PASTER_DATA_DIR` is pointed at `tmp_path` by `conftest.py`).
- Contract tests the family expects, all listed in §3–§8: `test_no_host_paths`, `test_kit_drift`, `test_bench_embed`, `test_cldbar_embed`, `test_webterm_keyboard`, `test_summary_placement`, plus the parity tests (labels, config) that pin D4.
- Node behaviour tests (`tests/js/*.test.mjs` over the kit's `domstub.mjs`) for the pure front-end pieces: `renderPreview`, the bulk-paste splitter, the row reorder model. Skipped when node is absent, like the kits.

### Tasks
- [ ] `pytest.ini` (`testpaths = tests`, `-p no:cacheprovider` off, `addopts = -q`), `requirements-dev.txt`? — no: pytest + pytest-cov ride in `requirements.txt` like soldo, so `--test` needs no second venv.
- [ ] A `tests/README.md` paragraph: how to run each suite alone, what skips mean on a bench host (a skipped kit test is a failed check).

### Definition of done
- `./run.sh --test` green, coverage ≥ 80 % overall and ≥ 95 % on the two stores and `history.py`; `pytest -rs` shows zero skips on this laptop.

### Estimate
folded into §3–§8

## 10. Feature: docs and the README
<!-- solseed: custom category=docs -->

### Tasks
- [ ] `README.md`: the "Front" section (what it is, `./run.sh`, the port, the views in one table, the trust statement, "the GUI never changes the entry format"); the Layout tree gains `run.sh`, `.port`, `control-plane/`, `deploy/`, `man/`, `plans/`; Troubleshooting gains "the Doctor view shows this".
- [ ] `man/` pages named above (01–07) are the Help view's tree; `man/00-api.md` lists every route with its envelope and status codes.
- [ ] `devRef/README.md`: planning history line for `plans/pasterFrontPlan.md`.
- [ ] `solBench/myApps.md` and `solBench/readme.md` app table: the row (user-approved, Phase 3).

### Definition of done
- A reader of the README alone can run the front, dock it, and knows what it will and will not touch.

### Estimate
0.25d

## 11. Feature: security posture (what is and is not protected)
<!-- solseed: custom category=security -->

- No authentication, by family decision: the tailnet is the perimeter, `--public` is the unit's default, the README says so in the same words soldo uses.
- CSRF guard (`X-Requested-With: paster`) on every `POST/PUT/PATCH/DELETE`; strict CSP (`script-src 'self'`, `frame-src` for cldBar only, `frame-ancestors` per §8); `X-Content-Type-Options: nosniff`; `Referrer-Policy: no-referrer`.
- Input validation at the boundary for every field (§4 names, §5 schema, §6 action names from a fixed set); every filesystem path resolved and confined; every subprocess argv-only with a timeout; error messages carry the reason, never a traceback or an absolute host path.
- Rate limiting in the one place it matters for a single-user local app: the desktop actions (§13). API endpoints are not otherwise throttled, matching the family.

### Tasks
- [ ] `tests/test_security.py`: headers on `/`, CSRF 403 on each mutating route, no `shell=True` anywhere under `modules/` (grep), path confinement cases, action-name allow-list.
- [ ] `man/05-deployment.md` carries the trust statement.

### Definition of done
- The security test file passes and the README's trust statement matches the unit's flags.

### Estimate
folded into §3–§8

## 12. Feature: API envelope and error contract
<!-- solseed: custom category=api-envelope -->

One response shape for every route, so `api()` in `wb-core.js` and a curl
user see the same thing: success = the resource as JSON (`201` on create,
`{"ok": true}` on delete/actions); failure = `{"error": "<reason>"}` with
`400` (validation), `403` (CSRF), `404` (unknown tab/file/route), `409`
(stale `base_rev`, action already running), `503` (no `DISPLAY`), `500`
(logged with a traceback server-side, the reason only in the body). Every
read of a file carries `rev`; every write echoes the new one.

### Tasks
- [ ] `tests/test_envelope.py`: an unknown `/api/*` route answers JSON `404`, not HTML; a `405` and a `500` are JSON too; a body that is not JSON → `400` with the reason; every `rev` in a read reappears as `base_rev` in the matching write.
- [ ] `server.py`: `errorhandler(404/405/500)` returning the envelope for `/api/*`, `request.get_json(silent=True)` with an explicit `400` everywhere.
- [ ] `man/00-api.md`: every route, its verbs, the status codes above, one curl example per group.

### Definition of done
- No route can answer a non-JSON body under `/api/`; the man page lists every route the test client can reach (a test walks `app.url_map` and fails on an undocumented rule).

### Estimate
0.25d

## 13. Feature: action throttle — one desktop action at a time
<!-- solseed: custom category=rate-limiting -->

The desktop actions (§6) touch the user's screen and i3 config, so a
double tap on a phone must not open two popups or run two installers.

- One `threading.Lock` per action name, non-blocking `acquire`; a second
  request while it is held → `409 {"error": "open_popup is already running"}`.
- A 2 s cooldown after each run (per action), same `409` with the seconds
  left, so a bounced button does nothing twice.
- Timeouts per action (`open_popup` 5 s, `run_tests` 120 s, `apply_install`
  120 s — apt may run, `clear_state` 5 s); on timeout the child is killed,
  the output so far is returned with `rc = -1` and an activity `warn`.
- The rest of the API is deliberately unthrottled (single operator, tailnet
  perimeter, §11).

### Tasks
- [ ] `tests/test_actions.py` additions: the lock (a stub binary that sleeps, two concurrent requests, exactly one runs), the cooldown clock injected, the timeout path kills the child.
- [ ] `actions.py`: `run_action(name, *, clock, env)` with the lock table and cooldown map; `routes_doctor.py` maps the exceptions to `409`/`503`.

### Definition of done
- Two simultaneous "Open popup" requests open one rofi; the second gets a `409` the toast explains.

### Estimate
folded into §6

## 14. Open questions (decide before Phase 1)

- **Q1 — in-repo vs separate repo.** Recommendation: in-repo (D1).
- **Q2 — commit from the GUI?** Recommendation: no in Phases 1–3 (Changes shows and reverts only); a "Commit with message" button is a Phase 4 option, off by default, since the family rule is that the user commits. (Moot: the Changes view itself was removed the same day, see §7.)
- **Q3 — per-action saves (D6) vs a dirty buffer with one Save.** Recommendation: per-action; the history ring is the undo.
- **Q4 — opt-in usage log (Phase 4).** `usage_log: true` in `config.yaml` would make `paste-back.sh` append `ts\ttab\tline` to `~/.paster/usage.tsv`, and the GUI would show pick counts, sort-by-use and "unused since". It is the only feature that changes a runtime script's behaviour. Wanted?
- **Q5 — port 6012 and unit name `paster`.** Recommendation: yes; `paster` is already the repo id in the registry.
- **Q6 — webterm in this app.** Recommendation: yes in Phase 3 (cheap through §2.1/§2.2, and it is what makes `install.sh` reachable from a phone); `PASTER_WEBTERM=0` exists for a host without tmux.
- **Q7 — Preview fidelity.** The HTML mock will not match rofi pixel for pixel (font metrics, the tab bar's theme colours live in `paster.rasi.tmpl`, not `config.yaml`). Accept it as a size/colour preview, with "Open the real popup" for the truth? (Moot: the mock was removed the same day; the title-bar button is the preview.)

## 15. Later (Phase 4, each its own decision)

- Usage log and "most used" (Q4).
- Commit from the GUI (Q2).
- Import/export: one markdown bundle of every tab (`## Tab` headings, one line per entry) for backup or for seeding another machine; import merges with a preview.
- A raw editor for `config/paster.rasi.tmpl` (tab-bar colours) with the same in-place safety — only if the preview shows the need.
- Entry notes or titles: would need a syntax in `content.md` that `tab-mode.sh` ignores, i.e. a runtime change; not planned unless the one-line-is-the-prompt model stops being enough.

## 16. Non-goals

- Multi-line entries (the format is one line = one entry; the popup pastes one line).
- Replacing or wrapping rofi; Wayland; a daemon between hotkey presses.
- Authentication or a second config file for the front (D8, D9).
- Editing anything outside `entries/` and `config.yaml` from the GUI (the installer and the i3 config are reached only through `install.sh`, unchanged).

## 17. Phases and order

| phase | sections | estimate | exit check |
|-------|----------|----------|------------|
| 0 scaffold | §3, §12 | 0.75d | shell serves, unit installs, family tests green |
| 1 core | §4 | 1.5d | every entry/tab operation visible in rofi on the next toggle |
| 2 config + doctor | §5, §6, §13 | 2.5d | form ↔ bash parity, drift banner, drop-in restored from the GUI |
| 3 family | §7, §8, §10 | 1.75d | docked in mainBench, terminal on the phone, roster row |
| 4 later | §15 | — | per decision |

Total for 0–3: about 6.25 days of agent work, one agent, in order, tests first
(§9). Every phase ends with the working tree left **uncommitted** and reported
(`git status --short`, `git diff --stat`) — the user commits.

## 18. Verified facts this plan rests on (2026-09-14, this laptop)

- `systemctl --user show-environment` → `DISPLAY=:1`, `XAUTHORITY=/run/user/1000/gdm/Xauthority`, `I3SOCK=/run/user/1000/i3/ipc-socket.<pid>`, `XDG_SESSION_TYPE=x11`.
- `pgrep -a i3` → `i3 -c /etc/regolith/i3/config`; `picom` running; `rofi -version` 1.7.5; `xdotool` 3.20160805.1.
- `~/.config/regolith3/i3/config.d/` contains only `myConfs` (no `90_paster`); `~/.config/i3/config` is the i3 wizard stub.
- `tests/run.sh` → 52 + 23 passed; `git status` clean on `main` at `606370b`.
- `.port` files in the bench: 6001–6008, 6010, 6011, 6050 → 6012 is free.
- `vsCodeFront/readme.md` "Who uses it": no app runs the kit's files yet; `vsCodeFront/skeleton/run.sh` and `server.py` are the copy-to-start app.
- `solBench/plans/benchLayoutPlan.md` §2.1–§2.4 are the `run.sh`, `conftest.py` and `test_no_host_paths.py` contracts quoted in §3.
