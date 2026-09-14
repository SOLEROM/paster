# Deployment

```sh
./run.sh                         # 127.0.0.1, port: --port › .port › 8790
./run.sh --public                # the tailnet
./deploy/systemd/install.sh      # the `paster` user unit, public, port from .port
```

`run.sh` creates `.venv`, installs `control-plane/requirements.txt`,
refreshes the kit copy-ins (4ColThems, vsCodeFront, cldBar) from the
sibling `../solBench` checkout and installs webterm editable from it —
every start, so a moved solBench repairs itself. `--skip-deps` (what the
unit passes) skips the kit refresh only. `--test` runs `tests/run.sh` and
pytest with the 80 % coverage gate. A lone clone without solBench beside
it runs without a terminal and without the refresh.

Settings are flags and env, on purpose — `config.yaml` stays the popup's
file:

| what | where |
|------|-------|
| port | `--port` › `.port` (6012 on the bench) › 8790 |
| bind | `--public` = 0.0.0.0, else `--host` or 127.0.0.1 |
| data dir | `PASTER_DATA_DIR` (default `~/.paster`: history, trash) |
| Claude meters origin | `PASTER_REMDEV_URL` — leave unset; the browser derives remdev's address from its own |
| terminal | `PASTER_WEBTERM=0` turns the Sessions view off |
| cross-host shell | `BENCH_SHELL_ORIGINS` via `deploy/systemd/install.sh --bench-origins` — only for a mainBench shell on another machine |

## Trust statement

There is no authentication. `--public` is the unit's default like every
app in the family; the perimeter is the tailnet. The Sessions view is a
real shell as the service user, and the Doctor's actions run scripts on
the laptop. Do not expose the port beyond a network you trust.

## Docking in mainBench

The app always sends `frame-ancestors 'self' http://<its own host>:*
https://<its own host>:*`, so a shell on the same machine docks it after
a plain restart. Add the roster row in `solBench/myApps.md` and mirror it
into `~/.config/mainbench/bench.toml` (`id = "paster"`, port 6012).
