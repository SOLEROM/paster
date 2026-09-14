# Config — config.yaml

The Config view edits the popup's `config.yaml`, the same flat
`key: value` file `bin/lib-config.sh` reads. **Form** renders one control
per key; **Raw** shows the file. Both write the file in place — a form
save replaces the value on the key's own line and keeps every comment and
the order; a key the file lacks is appended under one
`# added by paster front` line.

| key | applies |
|-----|---------|
| `hotkey` | after `./install.sh` (Doctor › Apply, or the banner's Apply now) — it lives in the i3 config |
| `width_pct`, `height_pct`, `opacity_pct`, `background`, `foreground`, `font_size`, `border_px` | on the next toggle — the theme is re-rendered every time the popup opens |
| `auto_paste`, `paste_delay_ms`, `paste_key`, `terminal_paste_key`, `terminal_classes`, `press_enter` | on the next Enter — `paste-back.sh` re-reads the file on every paste |

## Validation

The form checks each value as you type, with the same rules as
`lib-config.sh` (integer ranges, `#rrggbb`, `true/false/yes/no/on/off/1/0`,
xdotool key syntax, `|`-separated WM_CLASS names). An invalid value is
**still saved** — the file is yours — but the popup falls back to the
default for that key, and the message under the field says so, in
lib-config.sh's own words: the server sources the script on the saved file
and returns what it warned about. The hotkey is the one key the script
does not validate; the form applies the installer's rule so `install.sh`
does not refuse it later.

## The hotkey banner

The Doctor reads which key i3 actually binds (the Regolith drop-in or the
paster block in `~/.config/i3/config`). When that differs from
`config.yaml`, or no binding exists, a banner says so and **Apply now**
runs `./install.sh` and reloads i3 — on the laptop, from the GUI, so a
hotkey change made from a phone lands without a terminal. The button is
disabled when the server has no display.

## History

The clock icon in the toolbar lists the snapshots of `config.yaml`: view
one, or restore it. The ring is the same one the entries use (50 versions
under `~/.paster/history/config.yaml/`), and a restore is itself
snapshotted. Pending form edits must be saved or discarded first.

## Seeing the result

There is no picture of the popup. After Save, **Open popup** in the title
bar runs `bin/toggle.sh` on the laptop's screen, which is the truth for
size, colours and font. The tab-bar colours come from
`config/paster.rasi.tmpl`, not from `config.yaml`, and are not editable
here.
