# Entries and tabs

## The format (the contract with the popup)

- `entries/<folder>/content.md` — one folder per tab. Folders without a
  `content.md` are ignored by the popup and listed as such in the sidebar.
- The tab label is the folder name minus a leading `NN_`; the characters
  `, : ' "` are dropped by rofi, so the GUI refuses names that contain
  them and names whose label would equal an existing tab's.
- Every **non-empty line** of `content.md` is one entry. Blank lines are
  dropped when the GUI rewrites the file; a line is never split or joined.
  There are no comments, titles or multi-line entries — the line *is* the
  prompt.
- Order = folder name order for tabs, line order for entries. Reordering
  tabs renumbers the prefixes to `10_, 20_, 30_ …` (three digits once there
  are ten or more tabs).

## Working with entries

- **Add** opens an editor row at the end; **Enter** saves, **Esc** cancels.
  Shift+Enter is refused: one entry is one line.
- Click a line (or its pencil) to edit it in place. Emptying it asks to
  delete it.
- **Paste many**: a text box, one entry per line, appended after the
  current ones — the way to bring in a list.
- Drag the grip to reorder on a desktop; ▲/▼ from the row menu on a phone.
- **→** moves the line to another tab (both files are checked before either
  is written).
- The copy icon puts the line on *this device's* clipboard — the GUI as a
  remote paster from a phone or another machine.
- **Sort A→Z** is explicit and asks first; the previous order stays in
  History.
- The **filter** box narrows the current tab; the **sidebar search** box
  searches every tab (`[Tab]  line`, like rofi's ALL) and clicking a hit
  jumps to it.
- Lines over 300 characters get a `long` chip: rofi shows them on one line.

## History

The clock icon in the toolbar lists the snapshots of the current tab's
file: view one, or restore it. A restore is itself snapshotted, so nothing
is ever lost by trying. The ring keeps 50 versions per file under
`~/.paster/history/entries/<folder>/content.md/`; delete that folder to
empty it.

## When two writers meet

The GUI reloads a tab within about two seconds of an edit made elsewhere
(vim, another browser). A save over a file that changed meanwhile is
refused and the panel reloads with your text back in the editor — save
again after a look. An open editor is never re-rendered underneath you;
the reload waits until it closes.
