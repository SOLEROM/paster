---
project: 'paster'
type: planning
target_repo: 'v3_rofi/'
strategy_hint: 'port, do not rewrite: keep config.yaml/entries/paste-back, swap the window+menu layer for rofi'
version: 5
date: '2026-08-01'
status: decisions locked, implemented in v3_rofi/ — manual desktop matrix (T9) pending
---

# paster v3 — rofi backend, plan

> Goal: a new `v3_rofi/` variant with **feature parity to `v1_i3tabs/`**
> (per user request, that version is the parity target — not v2), replacing
> the alacritty + fzf + i3-scratchpad machinery with **rofi**. The entries
> model, `config.yaml`, paste-back logic, and installer conventions carry
> over; only the popup/menu layer changes. Scope is i3/X11, like v1.
>
> Prelog reading rules: carried by reference from plan2.md §1.

## 1. Feature: Why rofi (architecture)
<!-- solseed: custom -->

plan3.md §0 audited exactly where paster touches i3 and found four jobs:
(1) show/hide/single-instance, (2) window behavior rules, (3) global hotkey,
(4) focused-monitor geometry. v2 answered that by abstracting all four
behind `lib-wm.sh` backends. rofi answers it by **deleting jobs 1, 2 and 4**:
rofi draws its own floating, borderless, top-anchored, correctly-placed
window and exits on selection. Only job 3 — the global hotkey — remains
WM-specific, and stays exactly v1's `bindsym` wiring.

What v1 needed five cooperating pieces for (alacritty host window, i3
scratchpad, a ~40-line geometry retry dance in `toggle.sh`, a persistent
`menu-loop.sh` process, picom for opacity) collapses into one rofi launch:

- Native tab bar: each `entries/` folder becomes a rofi **script mode**;
  `-sidebar-mode` renders a real mode-switcher bar (movable to the top via
  the theme's `mainbox { children: [...] }` order).
- ALL mode = rofi **combi** mode over the same script modes (entries shown
  with their tab prefix), included as one more tab in the cycle.
- Fuzzy matching: `-matching fuzzy` with `-sorting-method fzf` (fzf-style
  scoring, rofi ≥ 1.6).
- Theming: one generated `.rasi` file covers width %, height %, position,
  colors, font size, border, and opacity (true alpha via `rgba()` under
  picom, pseudo-transparency fallback without a compositor — v1 just lost
  transparency there).

Carried over byte-for-byte (or nearly) from v1_i3tabs:
`entries/<NN_Tab>/content.md` layout, `config.yaml` keys, `lib-config.sh`,
the clipboard→focus-restore→keystroke logic of `paste-back.sh`, and the
installer's Regolith-vs-plain-i3 wiring.

Out of scope now, noted for later (prelog rule 7): desktop-agnostic hotkey
wiring by adopting v2's installer detection (rofi removes every *other*
DE-specific piece, so that graft would make v3 run anywhere v2 does);
Wayland (rofi-wayland fork is the future path); slide animation.

## 2. Feature: parity map — every v1 behavior and its rofi mechanism
<!-- solseed: custom -->

| v1_i3tabs behavior | v3 mechanism |
|---|---|
| Hotkey toggles popup anywhere | i3 `bindsym` → `toggle.sh`: if a paster-rofi process is alive, kill it (= hide); else capture focus + launch rofi |
| Popup on the monitor you're working on | rofi `-m <relative monitor>` (special values; see task T2) — replaces the `i3-msg get_workspaces` + `jq` computation entirely |
| Tabs from `entries/<NN_Name>/content.md`, `NN_` stripped, sorted | `toggle.sh` scans folders, builds `-modi "Label:tab-mode.sh <dir>,…"` per launch |
| Rescan on every open, no reload | natural — the modi list is rebuilt at each launch; script mode re-reads `content.md` per invocation |
| ←/→ and Ctrl-h/l switch tabs | rofi defaults already give `Shift+←/→` + `Ctrl+Tab`; add `-kb-mode-next Ctrl+l -kb-mode-previous Ctrl+h` (plain arrows: open question Q1) |
| Ctrl-a ALL mode with `[Tab]` prefixes | `combi` mode over all tab modes, placed as the first tab in the cycle (open question Q2 on exact Ctrl-a parity) |
| Query preserved across tab switches | native — rofi keeps the filter text when cycling modes in one session |
| Remembers last tab between opens | `tab-mode.sh` records its tab to `$XDG_RUNTIME_DIR/paster-last-tab`; `toggle.sh` passes `-show <that>` |
| Enter → clipboard + refocus + Ctrl(+Shift)+V | script mode receives the pick (`ROFI_RETV=1`), pipes it to `paste-back.sh`, prints nothing → rofi exits; `paste-back.sh` unchanged minus the scratchpad-hide line |
| Esc hides without pasting, filter resets | rofi exits on Esc; next launch starts with an empty query — free |
| `config.yaml`: width/height %, opacity, colors, font, border, hotkey | rendered into `config/paster.rasi` (template + sed, same pattern as the i3 snippet); `border_px` moves from the i3 rule to rasi `window { border: … }` |
| Instant popup (pre-spawned scratchpad window) | dropped: rofi cold-starts in tens of ms; having no persistent process is the point |

Net effect on the i3 snippet: the `for_window` rule disappears — only the
`bindsym` line remains. Bonus over v1: look changes in `config.yaml` apply
on the next toggle (rasi is re-rendered per launch), no `./install.sh` rerun.

## 3. Feature: v3_rofi layout + implementation tasks
<!-- solseed: custom -->

```
v3_rofi/
├── config.yaml                  # same keys as v1 (semantics per parity map)
├── entries/                     # copied from v1_i3tabs (versions stay self-contained)
├── bin/
│   ├── toggle.sh                # ~30 lines: focus capture, kill-or-launch, modi assembly
│   ├── tab-mode.sh              # rofi script-mode backend: list lines / handle pick
│   ├── paste-back.sh            # from v1, minus i3 scratchpad hide
│   └── lib-config.sh            # from v1, unchanged
├── config/
│   ├── i3.conf.snippet          # bindsym only, markers ">>> paster v3 >>>"
│   └── paster.rasi.tmpl         # theme template rendered from config.yaml
├── install.sh                   # v1 installer with: deps={rofi,xdotool,xclip,xprop},
│                                #   apt-install rofi if missing, MARKER_NAMES+=('paster v3'),
│                                #   kill leftover v0/v1 scratchpad window
└── README.md
```

### Tasks
- [x] T1 Scaffold `v3_rofi/` (copy `entries/`, `config.yaml`, `lib-config.sh`, `paste-back.sh` from `v1_i3tabs/`; strip the scratchpad-hide from paste-back).
- [x] T2 Spike — done against the actual Ubuntu 24.04 package (rofi not yet installed on this box; manpages pulled from the exact `1.7.5-0.1build2` .deb apt will install). Findings:
  - `-m -4` = "the monitor with the focused window" — matches v1's semantic; used.
  - `-combi-display-format` exists (default `{mode} {text}`) → `'[{mode}]  {text}'` gives v1's `[Tab]` look.
  - Default keybinds confirmed: `kb-move-char-back/forward` own `Left`/`Right`, `kb-remove-char-back` owns `Control+h`, `kb-mode-complete` owns `Control+l` — all four remapped/cleared so plain arrows + Ctrl-h/l can switch tabs (Q1).
  - Script-mode contract confirmed: "If the script returns no entries, rofi quits"; `ROFI_RETV` 0/1/2.
  - Not verifiable headless (needs the live desktop, folded into T9): filter surviving tab cycling, mode-switcher placement, grab/paste timing.
- [x] T3 `tab-mode.sh` — with one design change found during implementation: the selection handler must NOT run paste-back synchronously (rofi still holds the keyboard grab and reads the script's stdout; the injected keystroke would be swallowed). It stamps last-tab, then detaches paste-back via `setsid -f` with all fds closed, waiting for the rofi process to vanish first. Last-tab is stamped on selection only (`ROFI_RETV=1`), not on listing — combi calls every tab script at startup and would corrupt the memory.
- [x] T4 `toggle.sh` — as planned, plus: the i3 hotkey can't fire while rofi holds the keyboard grab, so "hotkey closes the popup" is implemented by translating the i3 hotkey (`Ctrl`→`Control`, `Mod1`→`Alt`, `Mod4`/`$mod`→`Super`) and appending it to `-kb-cancel`; the pkill kill-if-running remains as a grab-less-race safety net.
- [x] T5 `paster.rasi.tmpl` — as planned; tab bar on top via `mainbox { children: [ mode-switcher, inputbar, listview ]; }`, v1 palette (blue tabs, bold red current).
- [x] T6 `install.sh` — as planned; per user request it now apt-installs ALL missing deps in one shot (`rofi xdotool xclip x11-utils`), not just rofi.
- [x] T7 `v3_rofi/README.md` — includes a "Differences from v1" section (arrows vs query cursor, ALL-as-tab, last-pick tab memory, grab/cancel behavior).
- [x] T8 Root `README.md`: v3_rofi added to the version table, planning history extended with `plan4.md`.
- [ ] T9 Manual test matrix (needs the live desktop; headless part done — see below): paste into terminal / GUI editor / browser bar; hotkey-toggle-while-open; Esc; tab switch keeps query; ALL search; new entries folder appears without reload; multi-monitor placement; look change without reinstall; install over a live v1_i3tabs (old binding replaced, old scratchpad window gone).

### Code-review round (2026-08-01, fixes applied)

A reviewer ran the shipped launch command against the real rofi 1.7.5
binary under Xvfb and found it dead on arrival; root-causing corrected its
diagnosis and all findings are fixed:

- **CRITICAL (fixed, diagnosis corrected):** the popup showed rofi's error
  view instead of entries. The reviewer blamed the bare `←/→` bindings, but
  bisecting proved those are fine — the real cause was the translated
  hotkey `Control+space` appended to `-kb-cancel` colliding with rofi's
  default `kb-row-select` binding (rofi refuses duplicate bindings).
  toggle.sh now strips the hotkey combo from every action that holds it —
  its own overrides plus rofi's defaults, queried live via
  `rofi -no-config -dump-config` — so any hotkey is safe, version-proof.
  **Q1's plain-arrow tab switching survives.**
- **HIGH (fixed):** an entries/ folder name containing `'` broke that
  mode's command spec silently — paths in `-modi` are now escaped
  (`'…'\''…'`); the PASTER_DIR single-quote refusal was dropped in favor of
  the same escaping.
- **HIGH (fixed):** install.sh rendered the i3 snippet via sed with the
  free-text hotkey unvalidated — a `|`/`&`/`\` could corrupt or truncate
  the Regolith drop-in. Now: hotkey allowlist-validated
  (`^[A-Za-z0-9_+$]+$`), PASTER_DIR/KEY sed-escaped, drop-in written to a
  temp file and `mv`ed atomically.
- **MEDIUM (fixed):** two folders sanitizing to the same label hid one of
  them — duplicates now get a numeric suffix (`Coding`, `Coding 2`).
- **LOW (fixed):** literal dots in `TERMINAL_CLASSES` are escaped at match
  time in paste-back.sh.

End-to-end re-test under Xvfb with real rofi 1.7.5 (real toggle.sh, test
folder `40_Te'st` + duplicate `15_Coding` present): rofi starts with the
full keybinding set, `←` reaches ALL, typing filters, Enter delivers the
quoted-folder entry to the clipboard, `paster-last-tab` stamps, rofi exits.
Side effect of the review: rofi 1.7.5 is now installed on this machine, so
the installer's dep step is already satisfied here.

### Headless verification done (2026-08-01)
- `bash -n` + shellcheck (warning level) clean on all five scripts (SC2034 in
  `lib-config.sh` is the known sourcing false positive, same as v1).
- `toggle.sh` run against a stub `rofi`: argv assembly correct (combi first,
  quoted script specs, `Ctrl+space`→`Control+space` on kb-cancel), theme
  rendered with `rgba ( 16, 20, 26, 85 % )`, focus captured to
  `paster-prev-win`.
- `tab-mode.sh` `ROFI_RETV=0` lists entries; `ROFI_RETV=1` prints nothing,
  stamps `paster-last-tab`, and the detached paste-back delivered the
  selection to the clipboard; next `toggle.sh` run reopened on that tab.

### Definition of done
- Every row of the §2 parity map demonstrably works, modulo the keybinding
  deviations agreed in Q1/Q2.
- v1's five runtime pieces are reduced to rofi + two short scripts +
  paste-back; no persistent paster process between toggles.
- `./install.sh` on a machine with a live v1_i3tabs (or v0i3) install
  cleanly supersedes it.

### Estimate
0.5–1d, T2 spike first (its findings can only shrink the rest).

## 4. Resolved questions (answered by the user, 2026-08-01)

**Q1 — plain ←/→ for tab switching?** **Resolved: yes — plain arrows
switch tabs** (user chose full v1 muscle-memory parity over the
recommendation). Implemented by remapping rofi's defaults: query-cursor
movement moves to `Control+b`/`Control+f`, `Control+h` freed from
remove-char-back, `Control+l` freed from mode-complete; tab switching is
`←/→`, `Ctrl+h/l`, `Shift+←/→`, `Ctrl+Tab`.

**Q2 — Ctrl-a ALL toggle vs ALL-as-a-tab?** **Resolved: recommendation
accepted — ALL (combi) is the first tab in the cycle**; no Ctrl-a
mechanism, no wrapper relaunch.
