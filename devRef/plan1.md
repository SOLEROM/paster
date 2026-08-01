---
project: 'paster'
type: planning
target_repo: '.'
strategy_hint: ''
version: 2
date: '2026-07-31'
status: draft — proposed solution, awaiting review
---

# paster — plan

> Updated from `plan0.md` per the Prelog reading rules (block 1). `project` and
> `target_repo` were blank in plan0; filled here from `README.md`
> ("GuakeLike-Paster-Menu-Injector") and the fact that this repo currently
> holds only that README + plan0 — flagged under Open Questions in case that
> inference is wrong.

## 1. Feature: Prelog — plan file reading rules
<!-- solseed: block=prelog category=planning -->

*(unchanged from plan0 — carried forward verbatim so any future pass over
this file follows the same rules)*

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

### Findings from this pass

- **No literal identifiers/config filenames appear in plan0** — only prose
  typos (rule 2: "poping"→popping, "promtp"→prompt, "sentecne"→sentence,
  "clipaboard"→clipboard). Nothing to flag under rule 6.
- **No "later"/"stage2"/"TBD" markers exist anywhere in plan0** (rule 7).
  Nothing was deferred by the author — the whole thing is in scope for a
  first pass.
- **No hard contradictions found.** Feature 2's two halves (the plain-English
  ask, and the "what is guake style" breakdown) agree with each other — the
  breakdown even ends by recommending a lighter, composed-tools approach
  instead of a full custom Guake rebuild. That recommendation is treated as
  part of the source material, not invented by this plan (rule 5/8), and is
  the seed for Feature 4 below.
- **Environment was read as a referenced source (rule 5)**, since plan0 gives
  no target_repo/project and the only way to ground "best solution" in
  reality (not guesses) was to check what's actually available on this
  machine. Verified directly in this session:
  - Session type: **X11** (`XDG_SESSION_TYPE=x11`), desktop `Regolith` (i3-based).
  - Window manager: **i3** is installed and running (`i3`, `i3-msg` present).
  - Compositor: **picom is running now** (`picom --config /etc/regolith/picom/config --daemon`).
  - Already installed: `fzf` 0.44.1, `xdotool` 3.2016..., `wmctrl` 1.07, `xclip` 0.13 — the exact toolkit plan0's own "composed pieces" answer names.
  - Not installed: `rofi`, `dmenu`, `alacritty`, `kitty`, `sxhkd` — but `alacritty`/`kitty` are available via `apt` if wanted.
  - Terminal emulators present now: `gnome-terminal` (supports `--class`), `terminator` (supports `--role`, no `--class`).
  - This resolves the single biggest fork in plan0's own analysis — Wayland
    vs X11 — with a fact, not a guess: **X11, so global hotkey grabs and WM
    hints work natively; the Wayland caveat in plan0 doesn't apply here.**

### Definition of done
- Extracted scope is grounded in the plan0 and every source it references, with no silently invented requirements. ✅
- Every gap, contradiction, and suspect identifier is surfaced as an open question rather than resolved silently. ✅ (see Open Questions, bottom)

### Estimate
0.1d — done.

## 2. Feature: raw plan
<!-- solseed: custom -->

*(verbatim from plan0 — not rewritten, per rule 6/9; superseded in practice by
the resolved architecture in Feature 4)*

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

*(unchanged from plan0 — not executed this pass)*

Interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one. For each question, provide your recommended answer.

Ask the questions one at a time, waiting for feedback on each question before continuing. Asking multiple questions at once is bewildering.

If a question can be answered by exploring the codebase, explore the codebase instead.

### Tasks
- [ ] Interview the user about every aspect of the plan, one question at a time, with a recommended answer per question.
- [ ] Walk down each branch of the design tree, resolving dependencies between decisions one-by-one.
- [ ] Answer questions that the codebase can answer by exploring the codebase instead of asking.

### Status this pass
Not run as a live interview — the request that produced plan1 ("save updated
plan1.md with suggestion of the best solution") asked for a written
recommendation instead. Rule 3's "codebase can answer instead of asking" was
applied wherever possible (see environment findings above, e.g. X11-vs-Wayland
is now settled by fact). The **Open Questions** list at the bottom of this
file is exactly the question queue this task would walk through, one at a
time, whenever the user wants to run it.

### Definition of done
- Every branch of the design tree has been walked and its decisions resolved to a shared understanding. — deferred, see above
- No open question remains that was neither asked nor answered from the codebase. — partially satisfied: codebase/environment answered what it could; the rest is queued below.

### Estimate
0.1d

## 4. Feature: Proposed solution — composed-tools paster on i3/X11
<!-- solseed: custom -->

### Recommendation

Build **`paster`** as a small shell-script layer over the tools already
installed on this machine (`fzf`, `xdotool`, `wmctrl`, `xclip`) plus i3's own
**scratchpad** feature for the show/hide behavior — not a custom GTK/VTE
application. This is the approach plan0's own analysis already pointed to
("the common shortcut is to skip building your own terminal/GTK app..."); this
plan grounds it in the actual environment instead of leaving it generic:

- X11 is confirmed, so global hotkey grabs and EWMH/ICCCM window hints (rule
  3, 6, 2 from plan0's guake breakdown) work with zero extra plumbing.
- picom is already running, so alpha transparency ("half clear window") is
  free — no compositor code to write (item 4 from plan0's breakdown).
- i3's **scratchpad** (`move scratchpad` / `scratchpad show`) *is* a built-in
  "float a pinned, always-on-top, single window and toggle it from anywhere"
  primitive. It replaces plan0's items 3 (WM hinting), 6 (hotkey grab —
  `bindsym` is native to i3), and 7 (single-instance/IPC — one scratchpad
  window, i3 owns showing/hiding it, no daemon or D-Bus service needed).
- `fzf` directly satisfies "something like the fzf menu... keyboard search
  that limits the option" — because it literally is that tool, run inside
  whatever terminal emulator hosts it.
- The only piece with no off-the-shelf equivalent is item 5, the slide
  animation — i3 scratchpad show/hide is an instant toggle, not a slide. See
  Open Questions below; this is a real, named trade-off, not silently dropped.

### Component design

1. **Entries source** — a plain UTF-8 text file, one prompt/sentence per
   line (`~/.config/paster/entries.txt` or similar), read straight into `fzf`.
   Simplest format that fzf handles natively; format/location not specified
   in plan0, so flagged as an open question rather than assumed final.
2. **Host window** — a terminal emulator launched with a distinct WM class
   (e.g. `gnome-terminal --class=Paster -- fzf < entries.txt`, or install
   `alacritty`/`kitty` for faster startup and native per-window opacity).
   i3 rule: `for_window [class="Paster"] floating enable, sticky enable, move scratchpad`.
3. **Toggle script**, bound to a global i3 `bindsym`:
   - If the Paster window exists and is shown → `i3-msg 'scratchpad show'` again to hide it (same command toggles), i.e. no separate hide path needed.
   - If not yet spawned → before showing, capture the currently focused window with `xdotool getactivewindow` and stash its id (temp file / env var) so focus can be restored after selection — this is what makes "paste back where we were" possible.
   - Then spawn/show the Paster window on top, pinned, semi-transparent (via picom + terminal opacity setting).
4. **Selection → clipboard → paste-back**:
   - `fzf` writes the chosen line to stdout → piped to `xclip -selection clipboard`.
   - Script hides the Paster window (scratchpad again) and restores focus to the stashed window id (`xdotool windowactivate`).
   - Sends a simulated paste. **Which keystroke is itself an open question** — `Ctrl+V` for most GUI apps vs `Ctrl+Shift+V` for most terminal apps — see Open Questions.
5. **Single instance** — handled for free by i3 scratchpad (one window, i3
   manages show/hide); no background daemon/D-Bus service is needed, unlike
   real Guake. This is a meaningful scope reduction versus plan0's guake
   breakdown item 7.

### Tasks
- [ ] Decide entries file format/location (see Open Questions #1) and create it.
- [ ] Write `toggle.sh`: focus-capture → show/hide via i3 scratchpad → fzf → clipboard.
- [ ] Write `paste-back.sh`: restore focus → simulate paste (mechanism per Open Questions #3).
- [ ] Add i3 config: `for_window` rule for the Paster window class + `bindsym` for the global hotkey (key combo per Open Questions #4) + `bindsym` for toggle.
- [ ] Decide + optionally install terminal emulator (alacritty/kitty vs keep gnome-terminal) per Open Questions #2.
- [ ] Manual test pass: toggle from a terminal, a GUI text editor, and a browser address bar, confirming paste lands correctly in each.

### Definition of done
- Hotkey shows a pinned, semi-transparent, fzf-searchable list from anywhere on the desktop.
- Selecting an entry (Enter) closes the popup, restores focus to the previously active window, and the entry's text ends up pasted there.
- Pressing the hotkey again while open hides it without selecting anything.
- Works across at least one terminal-based and one GUI-based target app.

### Estimate
0.5–1d for the MVP described above (excludes slide-animation, which is a separate, larger effort — see Open Questions #5).

## Open questions

*(per rule 8/9 — none of these were answered by assumption; each needs a decision)*

1. **Entries file format & location.** Plan0 never specifies how "predefined prompt lines/words/sentences" are stored or edited. Recommended default: plain text, one entry per line, at `~/.config/paster/entries.txt`. Confirm or override.
2. **Terminal emulator choice.** `gnome-terminal`/`terminator` are installed now; `alacritty`/`kitty` are not but are better suited (native `--class`, native background opacity, faster startup) and are one `apt install` away. Recommended: install `alacritty`. Confirm or keep zero-new-installs with `gnome-terminal`.
3. **Paste delivery mechanism.** Plan0 literally says "clipboard... then pasted" — but the paste keystroke differs by target app (`Ctrl+V` in most GUI apps vs `Ctrl+Shift+V` in most terminal emulators), and `xdotool type` (typing the text directly, bypassing the clipboard and any paste shortcut) is a more universally reliable alternative at the cost of overwriting the clipboard's own semantics. Recommended: implement literal clipboard+`Ctrl+V` first (matches the stated spec) with `xdotool type` as a documented fallback mode. Confirm.
4. **Hotkey combo.** Not specified in plan0. Needs a concrete key combo that doesn't collide with existing Regolith/i3 bindings.
5. **Is the slide-up/down animation a hard requirement, or is an instant show/hide (i3 scratchpad's native behavior) acceptable?** Plan0 explicitly asks for "pops down from top... hides back" (visual language matching Guake's slide), but the composed-tools approach recommended here (and in plan0's own analysis) only gets an instant toggle for free. A real slide animation would require going back to a custom GTK/GDK window with a manual position-timer loop (plan0's guake-breakdown item 5) — i.e. abandoning the lightweight approach for the animated portion only. Recommended: accept instant toggle for the MVP, revisit animation as a follow-on if it's actually missed in use. Confirm.
6. **`project`/`target_repo` in frontmatter.** Both were blank in plan0. This file fills them (`paster`, `.`) from `README.md` and the repo's current contents — flagging in case this repo isn't actually meant to be the implementation target.

Next step: run Feature 3 (Grilling) against this question list, one question at a time, whenever the user is ready — or answer them inline and this plan gets revised into an execution-ready plan2.
