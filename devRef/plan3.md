---
project: 'paster'
type: planning
target_repo: 'v2/'
strategy_hint: 'generalize, do not rewrite — keep i3 as one backend among several'
version: 4
date: '2026-08-01'
status: implemented in v2/ (recommended answers applied) — manual desktop matrix pending
---

# paster v2 — plan: run on any Ubuntu system, not necessarily i3

> Scope: **v2/ only**. v2 currently is a byte-identical copy of v1_i3tabs
> (verified with `diff -rq`), i.e. a working i3/X11 implementation. This plan
> turns that copy into a desktop-agnostic version that works on stock Ubuntu
> (GNOME), Kubuntu, Xubuntu, Lubuntu, MATE/Cinnamon flavors — while keeping
> i3/Regolith working exactly as before.

## 0. Why this plan is shaped the way it is (the plan for the plan)

Before deciding *what* to change, I audited v2 for every place it touches i3,
because the right strategy depends on how deep the coupling goes. The result:
the coupling is **shallow and localized**. The whole user-facing core — the
tabbed fzf menu loop, entries-as-folders, config.yaml reader, clipboard
copy, focus-restore, terminal-aware paste keystroke — is plain X11 tooling
(`fzf`, `xdotool`, `xclip`, `xprop`, `alacritty`) and already works under any
X11 window manager. i3 is only used for four narrow jobs:

| # | Job | Where in v2 | i3 mechanism used |
|---|-----|-------------|-------------------|
| 1 | Show / hide / single-instance popup | `bin/toggle.sh`, `bin/menu-loop.sh` (`hide()`), `bin/paste-back.sh` | scratchpad (`i3-msg '[class="Paster"] move scratchpad / scratchpad show'`) |
| 2 | Window behavior (floating, sticky, on-top, border) | `config/i3.conf.snippet` | `for_window [class="Paster"] …` rule |
| 3 | Global hotkey | `config/i3.conf.snippet`, wired by `install.sh` | `bindsym` in the i3 config |
| 4 | Popup geometry on the focused monitor | `bin/toggle.sh` `compute_geometry()` | `i3-msg -t get_workspaces` + `jq`, `i3-msg resize/move` |

Plus the installer itself (`install.sh`), which hard-requires i3, wires
Regolith drop-ins / `~/.config/i3/config`, and calls `i3-msg reload`.

Each of these four jobs has a well-known generic X11 equivalent (EWMH hints
via `wmctrl`, map/unmap via `xdotool`, per-DE hotkey registration). So the
strategy is **not** a rewrite and **not** dropping i3 — it is:

> **Put a thin backend abstraction under the four coupled jobs, keep the i3
> code as the `i3` backend, add a generic `ewmh` backend for every other X11
> desktop, and teach the installer to detect the session and wire the hotkey
> through whatever mechanism that desktop actually has.**

This preserves the two properties that make v2 good — instant re-show (the
menu-loop process stays alive between toggles) and zero custom GUI code —
on every desktop, instead of trading them away for generality.

### The Wayland reality check

"Any Ubuntu system" must confront one hard fact: stock Ubuntu ≥ 22.04 logs
into **GNOME on Wayland** by default. On Wayland, `xdotool` cannot read the
focused window of native apps, cannot restore focus to them, and cannot
inject keystrokes into them — so "auto-paste into the window you came from",
the heart of paster, is not implementable without a root-configured `ydotool`
daemon and still has no reliable "previous focused window" query. Therefore
the plan defines explicit **tiers** instead of pretending one code path fits
all:

- **Tier 1 — full experience (X11 session, any WM/DE):** everything v2 does
  today: popup, tabs, search, hide, focus-restore, auto-paste. Covers i3,
  Regolith, and every Ubuntu flavor when logged in via "Ubuntu on Xorg" /
  Xubuntu / MATE etc.
- **Tier 2 — degraded but useful (Wayland GNOME):** popup + tabs + search +
  copy-to-clipboard work; auto-paste is skipped and a notification tells the
  user to press Ctrl+V. Implemented by forcing alacritty onto XWayland
  (launch with `WAYLAND_DISPLAY` unset) so the popup itself and `xclip` still
  work, and registering the hotkey via `gsettings` (which works on Wayland).
- **Stage 2 (out of scope now, reserved):** true Wayland auto-paste via
  `ydotool`/portals; sway/layer-shell backend.

Everything below is organized so Tier 1 is the deliverable and Tier 2 is a
thin, clearly-labeled best-effort layer on top.

## 1. Feature: WM backend abstraction (`bin/lib-wm.sh`)

### Why

Jobs 1, 2, and 4 from the audit table are the only i3 calls in the three
runtime scripts. If they go through one sourced library with a detected
backend, the runtime scripts stop knowing what a WM is.

### Design

New file `bin/lib-wm.sh`, sourced by `toggle.sh`, `menu-loop.sh`,
`paste-back.sh`. It exposes:

- `wm_backend` — detection, run per invocation (cheap, no install-time state
  to go stale): `i3-msg -t get_version` succeeds → `i3`; else
  `XDG_SESSION_TYPE=wayland` → `wayland-degraded`; else `ewmh`.
- `wm_hide` — i3: `move scratchpad` (verbatim today's call); ewmh:
  `xdotool windowunmap` on the Paster window. Unmap keeps the menu-loop
  process alive, so the instant-reshow property is preserved without i3.
- `wm_show_or_spawn` — i3: `scratchpad show` / spawn (today's code moves
  here); ewmh: `xdotool windowmap` + `windowactivate`, or spawn if absent.
- `wm_place W H X Y` — i3: `i3-msg resize set / move absolute`; ewmh:
  `xdotool windowsize` + `windowmove` (`wmctrl -e` as fallback).
- `wm_apply_window_props` — replaces the i3 `for_window` rule for non-i3:
  after the window maps, `wmctrl -r Paster -b add,above,sticky` and
  `add,skip_taskbar,skip_pager`. Floating needs no action outside tiling
  WMs; alacritty is already undecorated (`decorations = "None"`), so
  `border_px` becomes documented as i3-only and is ignored elsewhere.
- `wm_kill_paster` — used by the installer; i3: `[class="Paster"] kill`;
  ewmh: `xdotool search --class '^Paster$' | xargs -r xdotool windowkill`.

Geometry source for ewmh (job 4 without `i3-msg`/`jq`): find the monitor
under the mouse pointer (`xdotool getmouselocation` + parse
`xrandr --listactivemonitors`), compute `width_pct`/`height_pct` of that
monitor's rect, top-anchored and horizontally centered — same semantics as
today's focused-workspace math, minus bar awareness (acceptable: the popup
overlaps a top panel by at most panel-height; noted in README).

### Tasks
- [x] Write `bin/lib-wm.sh` with the API above; move all existing `i3-msg` calls into the `i3` backend unchanged.
- [x] Convert `toggle.sh`, `menu-loop.sh` (`hide()`), `paste-back.sh` to call only `wm_*` functions — zero direct `i3-msg`/WM calls left in them.
- [x] Implement the `ewmh` backend (unmap/map, wmctrl props, xrandr geometry).
- [x] `jq` becomes an i3-backend-only dependency; `wmctrl` becomes an ewmh-backend dependency (installer feature handles both).

### Definition of done
- `grep -r i3-msg bin/` matches only inside `lib-wm.sh`.
- On a non-i3 X11 session: hotkey toggles the popup, popup is on-top/sticky/undecorated, re-show after first spawn is instant (process survives hide), select → paste works — identical UX to i3.
- On i3/Regolith: behavior is bit-identical to current v2 (regression check).

### Estimate
0.5–0.75d.

## 2. Feature: installer generalization (session detection + per-DE hotkey)

### Why

Job 3 (global hotkey) is the one job with **no** generic X11 answer — every
desktop has its own registration mechanism, and this is exactly what an
installer is for. Today `install.sh` hard-dies without i3; instead it must
detect the session and pick a wiring strategy.

### Design

Detection order in `install.sh`:

1. **i3 / Regolith** (i3 socket reachable or Regolith config.d present) —
   current logic kept verbatim, including v0i3/v1 marker cleanup.
2. **GNOME family** (`XDG_CURRENT_DESKTOP` contains GNOME/Unity/ubuntu, or
   Cinnamon/MATE with their schema variants) — register a custom shortcut
   via `gsettings` media-keys custom-keybindings: name `paster`, command
   `<abs path>/bin/toggle.sh`, binding converted from config.yaml. Works on
   both Xorg and Wayland GNOME. Idempotent: find-or-replace the entry whose
   name is `paster` instead of blindly appending.
3. **XFCE** — `xfconf-query -c xfce4-keyboard-shortcuts -p
   "/commands/custom/<key>" -s <toggle.sh>` (create or overwrite).
4. **Anything else (KDE, LXQt, unknown)** — no fragile automation: print
   exact manual instructions ("bind key X to command Y in System Settings →
   Shortcuts"), and offer `sxhkd` as an opt-in fallback
   (`./install.sh --sxhkd`): apt-install sxhkd, write
   `~/.config/sxhkd/sxhkdrc` block with paster markers, add an autostart
   .desktop entry. (Rationale for not automating KDE: kglobalaccel config
   file formats shift between Plasma versions; a wrong write can eat user
   shortcuts. Manual is safer — revisit in stage 2.)

Hotkey format conversion: config.yaml keeps one canonical i3-style value
(e.g. `Ctrl+space`); a small mapper in `install.sh` converts it per target
(`<Ctrl>space` / `<Primary>space` for gsettings/xfconf, `ctrl + space` for
sxhkd), validating against a supported modifier set and failing loudly on
keys it can't translate.

Environment gate changes: the current "die on Wayland / die without i3"
check is replaced by the tier logic — Wayland + GNOME proceeds as Tier 2
with a prominent warning; Wayland + anything else dies with a message
naming the supported paths ("log in with an Xorg session").

Dependency step: `fzf xdotool xclip xprop` always; `wmctrl` when non-i3;
`jq` when i3; `alacritty` apt-installed if missing (unchanged). All are in
Ubuntu main/universe on every flavor, so `apt-get install` offers to fix
anything missing instead of just dying.

### Tasks
- [x] Restructure `install.sh`: detect → select wiring strategy → wire → close stale Paster window (`wm_kill_paster`) → report the active hotkey and tier.
- [x] Implement gsettings wiring (GNOME/Cinnamon/MATE schema variants), idempotent by shortcut name.
- [x] Implement xfconf wiring for XFCE.
- [x] Implement manual-instructions path + optional `--sxhkd` fallback with markered sxhkdrc block and autostart entry.
- [x] Write the hotkey format mapper with validation (`bin/lib-hotkey.sh` + `tests/test-hotkey.sh`, 19 cases green).
- [x] Add `./install.sh --uninstall` that reverses whichever wiring was applied — with per-DE writes, "re-run to overwrite" is no longer enough to undo.

### Definition of done
- On stock Ubuntu (GNOME/Xorg), Xubuntu, and i3: `./install.sh` completes without manual edits and the hotkey pops the menu.
- On KDE: installer prints correct copy-pasteable manual instructions; `--sxhkd` path works.
- Re-running the installer never duplicates shortcuts or config blocks; uninstall removes them.

### Estimate
0.75–1d (the per-DE wiring matrix is where the real-world variance lives).

## 3. Feature: Wayland-GNOME degraded tier

### Why

It's the Ubuntu default login. Refusing to run at all would fail the "any
Ubuntu system" goal; pretending auto-paste works there would fail honesty.

### Design

Backend `wayland-degraded` in `lib-wm.sh`:
- Spawn alacritty with `WAYLAND_DISPLAY` unset in its environment → it runs
  on XWayland, so `xdotool` map/unmap/place and `xclip` keep working on the
  popup itself; Mutter syncs the X clipboard to the Wayland clipboard.
- `toggle.sh` skips previous-window capture (meaningless for native Wayland
  windows); `paste-back.sh` stops after the clipboard copy and fires
  `notify-send 'paster' 'Copied — press Ctrl+V to paste'` instead of the
  keystroke.
- Hotkey via the gsettings path from Feature 2 (Wayland-safe).
- README labels this tier experimental; on-top/sticky hints are best-effort
  under Mutter/XWayland.

### Tasks
- [x] Add the `wayland-degraded` backend + spawn-env handling.
- [x] Gate focus-capture and paste-keystroke on tier; add the notification.
- [ ] Verify clipboard sync XWayland→Wayland on a real GNOME Wayland session. *(needs a real Wayland login — pending)*

### Definition of done
- On Ubuntu Wayland: hotkey pops the styled menu, Enter copies the line, notification appears, popup hides; nothing errors in the journal.

### Estimate
0.5d.

## 4. Feature: docs + identity cleanup

### Why

v2's files still call themselves "paster v1" (README title, script headers,
`# >>> paster v1 >>>` markers). A version that behaves differently per
desktop also needs its requirements/troubleshooting rewritten per tier —
stale docs are how a general tool gets branded "broken" on the desktop the
author didn't use.

### Tasks
- [x] Rebrand all v2-internal "v1" references to v2; installer marker list becomes `('paster v2' 'paster v1' 'paster v0i3')` so installing v2 cleanly supersedes both prior versions on i3.
- [x] Rewrite `README.md`: tier table (what works where), per-desktop install notes, per-desktop troubleshooting (no transparency on bare i3 → picom; hotkey conflicts per DE; Wayland limitations).
- [x] Update `config.yaml` comments: hotkey is canonical i3-style and translated per desktop; `border_px` marked i3-only.

### Definition of done
- No occurrence of "v1" inside `v2/` except in the historical-supersession marker list; README accurately states behavior per tier.

### Estimate
0.25d.

## 5. Verification plan

Automated (runs anywhere, CI-able):
- `bash -n` + `shellcheck` on all scripts.
- A `--dry-run` installer mode printing detection result + intended wiring,
  testable by faking `XDG_CURRENT_DESKTOP`/`XDG_SESSION_TYPE`.
- Unit-ish test for the hotkey format mapper (pure bash, table-driven).

Manual matrix (the part that can't be faked):

| Environment | Expect |
|---|---|
| i3 / Regolith (X11) | identical to today — regression gate |
| Ubuntu GNOME on Xorg | Tier 1 full flow incl. auto-paste to terminal + GUI app |
| Xubuntu (XFCE) | Tier 1 full flow, xfconf hotkey |
| Kubuntu (KDE) | manual-instruction path; Tier 1 after binding (or `--sxhkd`) |
| Ubuntu GNOME on Wayland | Tier 2: popup + copy + notification, no paste keystroke |

### Estimate
0.5d spread across the features.

## Open questions (recommended answer stated; assumed unless overridden)

1. **Wayland scope** — ship the degraded Tier 2 now (recommended), or hard-
   require X11 and defer all Wayland work to stage 2? Recommended: ship
   Tier 2; it's ~0.5d and covers the Ubuntu default login.
2. **KDE hotkey automation** — manual instructions + optional sxhkd
   (recommended) vs writing kglobalshortcutsrc directly? Recommended: manual;
   direct writes are Plasma-version-fragile and can clobber user shortcuts.
3. **Host terminal** — keep alacritty (recommended; apt-installable on all
   flavors, `--class`, native opacity) vs auto-detecting an existing
   terminal? Recommended: keep — one terminal, one styling path.
4. **Backend choice timing** — detect per toggle (recommended, survives the
   user switching session types without reinstalling) vs freeze at install?
   Recommended: per toggle; detection is a couple of cheap checks.
5. **`border_px` outside i3** — silently ignore with a README note
   (recommended) vs emulate via alacritty padding/colors? Recommended:
   ignore; a fake border isn't worth a styling hack.

## Sequencing & total estimate

Feature 1 (abstraction) → Feature 2 (installer) → Feature 3 (Wayland tier)
→ Feature 4 (docs) with Feature 5 checks after each. Feature 1 must land
first: it's what makes 2 and 3 small. **Total: ~2–2.5d**, of which the
i3-regression risk is near zero because the i3 code paths move but do not
change.
