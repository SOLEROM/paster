# API reference

Every route lives under `/api/`. Success returns the resource as JSON
(`201` on create, `{"ok": true}` on delete and actions). Failure is always
`{"error": "<reason>"}` with the status below — never HTML, never a
traceback. Every mutating verb needs the header `X-Requested-With: paster`
(a CSRF guard, not authentication; `403` without it).

| status | meaning |
|--------|---------|
| 400 | validation failed (the reason names the field) |
| 403 | the CSRF header is missing or wrong |
| 404 | unknown tab, snapshot, page, action or route |
| 409 | stale `base_rev` (the reply carries `current`), a name clash, or an action already running / cooling down |
| 503 | a desktop action with no `DISPLAY` in the server's environment |
| 500 | a tool failed (bash, git) or an unexpected error — details in the server log only |

Every read of a file carries `rev` (sha256 of its bytes). Send it back as
`base_rev` on the matching write; a mismatch is refused with `409` and
nothing is written.

## Common

- `GET /api/health` → `{ok, app, webterm, display, port}`
- `GET /api/help/tree`, `GET /api/help/page?file=<rel>` — the pages under `man/`
- `GET /api/logs?limit=500` — the activity ring (also pushed as `activity_logged`)

## Tabs and entries

- `GET /api/tabs` → `{tabs: [{id, label, count, rev, mtime}], ignored, unlabeled}`
- `POST /api/tabs` `{name, after?}` → `201 {id, renames}` — creates `NN_<name>`; `after` is a tab id (default: last)
- `PATCH /api/tabs/<tab_id>` `{name}` → `{id}` — the `NN_` prefix is kept
- `PUT /api/tabs/order` `{ids}` → `{renames}` — every tab exactly once; prefixes renumbered 10, 20, 30 …
- `DELETE /api/tabs/<tab_id>` → `{ok, trash}` — the folder moves to `~/.paster/trash/`
- `GET /api/tabs/<tab_id>/entries` → `{id, label, lines, rev}`
- `PUT /api/tabs/<tab_id>/entries` `{lines, base_rev}` → `{rev, count}` — one entry per string, blanks dropped, no newlines inside
- `POST /api/entries/move` `{from, index, to, position?, base_from?, base_to?}` → `{rev_from, rev_to}`
- `GET /api/search?q=` → `{hits: [{tab, label, index, line}]}` — substring, case-insensitive, every tab
- `GET /api/history?file=<rel>` → `{file, snapshots: [{ts, size}]}` — `rel` is `config.yaml` or `entries/<tab>/content.md`
- `GET /api/history/snapshot?file=<rel>&ts=<ts>` → `{content}`
- `POST /api/history/restore` `{file, ts, base_rev?}` → `{rev}`

Socket.IO pushes: `tabs_changed`, `entries_changed {tab}`, `config_changed`,
`doctor_changed {action}`, `activity_logged {…}`. Clients re-fetch; the
events carry no state.

## Config

- `GET /api/config` → `{raw, rev, values, effective, warnings, missing, schema}` — `values` is what the file says, `effective` what `lib-config.sh` resolves, `warnings` its `paster: config …` lines
- `PUT /api/config` `{values: {key: value}, base_rev}` → the same document after the in-place write
- `PUT /api/config/raw` `{text, base_rev}` → the same document
- `GET /api/config/schema` → `{sections, fields}`
- `POST /api/config/preflight` `{values}` → `{fields: {key: {ok, effective, message}}}` — the schema mirror's opinion, before saving

## Doctor and actions

- `GET /api/doctor` → `{checks: [{id, title, status, detail, fix}], summary, display, flavour, binding, config_hotkey, hotkey_drift, entries, under_systemd, actions}`
- `GET /api/actions` → `{actions: [{name, title, description, argv, enabled, reason, running, last}]}`
- `POST /api/actions/<name>` → `{name, rc, output, started, duration_s, timed_out, ok}` — `open_popup`, `apply_install`, `run_tests`, `clear_state`

Examples:

```sh
curl -s localhost:6012/api/tabs | jq '.tabs[] | {id, count}'
curl -s -X PUT localhost:6012/api/tabs/10_Coding/entries \
  -H 'Content-Type: application/json' -H 'X-Requested-With: paster' \
  -d '{"lines": ["one", "two"], "base_rev": "<rev from GET>"}'
curl -s -X POST localhost:6012/api/actions/run_tests -H 'X-Requested-With: paster'
```
