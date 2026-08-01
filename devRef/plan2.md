---
project: 'paster'
type: planning
target_repo: '.'
strategy_hint: ''
version: 3
date: '2026-07-31'
status: ready — decisions locked, ready for implementation
---

# paster — plan

> plan1.md's Grilling interview (Feature 3) has now been run, one question at
> a time, per its own Definition of Done. All 6 open questions from plan1 are
> resolved below. This version turns Feature 4 from a recommendation-with-
> open-questions into a concrete, decision-locked implementation plan.

## 1. Feature: Prelog — plan file reading rules
<!-- solseed: block=prelog category=planning -->

*(unchanged from plan0/plan1 — carried forward verbatim)*

### Reading rules

1. **Read every line of the whole file before drawing conclusions.** Ideas are
   not in final order — a detail near the bottom may change the meaning of
   something at the top.
2. **Ignore typos, spelling, and grammar.** Extract the intended idea, not the
   literal words. If a word is garbled, pick the interpretation that fits the
   surrounding context (e.g. "withard" → "wizard").
3. **Treat headings as loose groupings, not structure.** Sections may overlap,
   be misplaced, or be incomplete. The real structure is yours to propose later.
4. **Bullet order is not priority order.** Do not assume the first item is the
   most important or that items form a sequence, unless the text says so.
5. **Follow every referenced path or project.** If the plan points to a file,
   skill, or reference project, read it — those references usually carry more
   detail than the plan itself. Base your scope estimation on them, not on
   guesses.
6. **Keep names, paths, and identifiers verbatim.** Even if they look
   misspelled (e.g. a config filename), do not "fix" them — they may be
   intentional. Flag suspected typos in identifiers as a question instead.
7. **Separate "now" from "later".** Items marked as a later stage ("stage2",
   "will be defined later", "TBD") are out of scope for the first pass. Note
   their existence, reserve a place for them, but do not plan them in detail.
8. **Do not invent requirements.** If something is not stated and cannot be
   derived from a referenced source, list it as an open question. Never fill
   gaps with silent assumptions.
9. **Flag contradictions, don't resolve them silently.** If two lines conflict,
   surface both and ask — do not pick one on your own.

### Tasks
- [x] Read the whole plan0 end to end applying every reading rule above.
- [x] List open questions, suspected identifier typos, and contradictions found while reading.
- [x] Note "later"-stage items (stage2 / TBD) without planning them in detail.

### Definition of done
- Extracted scope is grounded in the plan0 and every source it references, with no silently invented requirements. ✅
- Every gap, contradiction, and suspect identifier is surfaced as an open question rather than resolved silently. ✅

### Estimate
0.1d — done.

## 2. Feature: raw plan
<!-- solseed: custom -->

*(verbatim from plan0 — not rewritten, per rule 6/9)*

the paster app is a desktop linux app that is poping on demand and key press and show many options of predefined promtp lines words or sentecne that i can commonly use
when some line is selected it will go to the clipaboard , the paster will closed and that clipboard will be paste on the current place we were before we called paster.

how would it look and act?

* it will be a layer app like the guake that pops down from top and hides back there on key press and it a half clear window on top of all others.
* it will use something like the fzf menu that enable keyboard search that limit the option choosed until enter selecte the right line

what is the guake style?

● The Guake-style "drop-down overlay" effect is really a stack of several distinct layers, each doing one job:

  1. Terminal emulation core — VTE (libvte, same widget GNOME Terminal uses). Owns the PTY, parses ANSI/escape sequences, renders glyphs. This part has nothing to do with the popup behavior.
  2. GUI toolkit — GTK (Guake is Python + GTK3). Provides the window, the event loop, and embeds the VTE widget as a normal child widget.
  3. Window manager hinting (EWMH/ICCCM on X11) — the "float above everything, no decorations, on every workspace" behavior isn't drawn by the app itself, it's requested from the WM via hints: _NET_WM_STATE_ABOVE (always on top), _NET_WM_STATE_STICKY
  (visible on all workspaces), _NET_WM_STATE_SKIP_TASKBAR/PAGER, and no titlebar (override-redirect or GDK_WINDOW_TYPE_HINT_DOCK/SPLASHSCREEN). The WM has to cooperate for this to look "system-level" rather than like a regular app window.
  4. Compositor — the semi-transparent "half clear screen" look needs alpha blending, which is the X11 compositor's job (picom/xcompmgr, or built into the DE like Mutter/KWin). Without a compositor running, transparency just doesn't render.
  5. Animation loop — the slide up/down is just a GLib timer nudging the window's Y position each tick until it reaches its target — no special API, just repeated move() calls on a short interval.
  6. Global hotkey grab — to toggle from anywhere, the app registers a system-wide key grab (X11: XGrabKey/keybinder-3.0). This is the piece that doesn't translate well to Wayland — compositors don't let arbitrary clients grab global hotkeys, so
  Wayland-native drop-downs (e.g. foot+layer-shell) instead implement this via zwlr_layer_shell_v1, and the hotkey binding has to live in the compositor/DE config, not the app.
  7. Single-instance + IPC — a background daemon process (D-Bus service in Guake's case) so the hotkey doesn't spawn a new terminal each time — it just tells the already-running instance to show/hide.

  For a lighter "paster"-style tool, you don't need to reimplement most of this — the common shortcut is to skip building your own terminal/GTK app and instead compose existing pieces: any terminal emulator that supports a --class flag (alacritty, kitty,
  urxvt), a WM rule that floats+pins that class, xdotool/wmctrl to toggle visibility and geometry, and sxhkd or your WM's own keybinder for the hotkey — the classic tdrop approach. That gets you 90% of the Guake feel without writing a VTE/GTK app at all.

## 3. Feature: Grilling — relentless plan interview
<!-- solseed: block=grilling category=planning -->

*(unchanged rules — status updated below: this pass ran it for real)*

Interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one. For each question, provide your recommended answer.

Ask the questions one at a time, waiting for feedback on each question before continuing. Asking multiple questions at once is bewildering.

If a question can be answered by exploring the codebase, explore the codebase instead.

### Tasks
- [x] Interview the user about every aspect of the plan, one question at a time, with a recommended answer per question.
- [x] Walk down each branch of the design tree, resolving dependencies between decisions one-by-one (started from the architecture-defining question — animation — before drilling into details that only matter once that fork was resolved).
- [x] Answer questions that the codebase can answer by exploring the codebase instead of asking (done in plan1: X11-vs-Wayland, installed tools, compositor state — answered from the environment, not asked).

### Interview results

| # | Question | Answer |
|---|---|---|
| 1 | Slide animation a hard requirement? | No — instant i3-scratchpad toggle is acceptable. **Confirms composed-tools architecture over custom GTK.** |
| 2 | Terminal emulator? | Install `alacritty` (`--class`, native opacity, fast startup). |
| 3 | Paste delivery mechanism? | Clipboard (`xclip`) + simulated keystroke; `Ctrl+V` for GUI targets, `Ctrl+Shift+V` when the previously-focused window is itself terminal-class. |
| 4 | Hotkey combo? | `$mod+p`, bound in i3. |
| 5 | Entries file format/location? | Plain text, one prompt per line — **stored in this repo** (not `~/.config/`), i.e. version-controlled alongside the scripts. |
| 6 | Is this repo the implementation target? | Yes — `/proj/agents/paster`, `project: paster`. |

### Definition of done
- Every branch of the design tree has been walked and its decisions resolved to a shared understanding. ✅
- No open question remains that was neither asked nor answered from the codebase. ✅

### Estimate
0.1d — done.

## 4. Feature: paster implementation — composed-tools on i3/X11
<!-- solseed: custom -->

### Architecture (locked)

Small shell-script layer over already-installed tools (`fzf`, `xdotool`,
`wmctrl`, `xclip`) plus `alacritty` (to be installed) and i3's native
**scratchpad**, all confirmed against the real environment (X11, i3, picom
running) rather than assumed. No custom GTK/VTE app, no daemon/IPC — i3
scratchpad natively provides single-instance + show/hide + always-on-top +
sticky, which is what plan0's own guake-breakdown items 3, 6, and 7 required
manual work for.

### Repo layout (proposed, all within this repo per decision #6)

```
paster/
├── entries.txt              # one prompt per line, decision #5
├── bin/
│   ├── toggle.sh             # hotkey target: show/hide + capture focus
│   └── paste-back.sh         # called on fzf selection: clipboard + focus-restore + paste
├── config/
│   └── i3.conf.snippet       # for_window rule + bindsym, to append to ~/.config/i3/config
└── README.md                 # existing — update with setup instructions
```

### Component design (decisions applied)

1. **Entries** — `entries.txt` at repo root, one prompt per line, git-tracked.
2. **Host window** — `alacritty --class Paster -e fzf --prompt='paster> ' < entries.txt`, opacity set in an alacritty profile/config dedicated to this class.
3. **i3 rule** — `for_window [class="Paster"] floating enable, sticky enable, move scratchpad`.
4. **Hotkey** — `bindsym $mod+p exec --no-startup-id /proj/agents/paster/bin/toggle.sh`.
5. **`toggle.sh`** — on invocation: if the Paster window is already shown, `i3-msg 'scratchpad show'` hides it (no-op otherwise); if not yet spawned, first `xdotool getactivewindow` and stash the id (e.g. `/tmp/paster-prev-win`), then launch/show the Paster window.
6. **Selection → `paste-back.sh`** (fzf's `--bind` or a wrapping `execute` action pipes the chosen line here): `xclip -selection clipboard`, hide the Paster window via scratchpad, `xdotool windowactivate "$(cat /tmp/paster-prev-win)"`, then send `ctrl+shift+v` if the restored window's class is a known terminal class, else `ctrl+v`.

### Tasks
- [ ] `sudo apt install alacritty`; create a Paster-specific alacritty config profile with `opacity` set.
- [ ] Create `entries.txt` at repo root with initial set of prompts (content TBD by user — not specified anywhere in plan0/interview, so left as an empty/starter file, not invented).
- [ ] Write `bin/toggle.sh` (focus-capture + scratchpad show/hide + spawn-if-needed).
- [ ] Write `bin/paste-back.sh` (clipboard + focus-restore + terminal-aware paste keystroke).
- [ ] Write `config/i3.conf.snippet` (the `for_window` + `bindsym` lines) and document appending it to `~/.config/i3/config` + `i3-msg reload`.
- [ ] Update `README.md` with setup/usage instructions.
- [ ] Manual test pass: toggle from a terminal, a GUI text editor, and a browser address bar; confirm correct paste keystroke fires in each; confirm hotkey toggles hide when pressed again mid-open.

### Definition of done
- `$mod+p` shows a pinned, semi-transparent, fzf-searchable list from anywhere on the desktop.
- Selecting an entry (Enter) closes the popup, restores focus to the previously active window, and the entry's text ends up pasted there via the correct keystroke for that app type.
- Pressing `$mod+p` again while open hides it without selecting anything.
- Verified across at least one terminal-based and one GUI-based target app.

### Estimate
0.5–1d.

## Resolved decisions (formerly "Open questions" in plan1)

All 6 are closed — see the Interview results table in Feature 3. Nothing
remains open per plan0's Grilling Definition of Done.

Next step: implement Feature 4's task list.
