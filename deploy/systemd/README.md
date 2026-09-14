# paster front — systemd user service

```sh
./deploy/systemd/install.sh              # public by default, like the apps
./deploy/systemd/install.sh --uninstall
```

The unit is **generated** from `paster.service.template`; never hand-edit
`~/.config/systemd/user/paster.service` — re-run the installer. It runs
`run.sh --vname <venv> --skip-deps --public` from the repo, so the port is
`.port` (6012 on the bench) and the kit copy-ins are not refreshed on every
restart (run `./run.sh` once by hand after pulling a kit change).

The desktop actions of the Doctor view (open the popup, apply the hotkey)
need `DISPLAY`/`XAUTHORITY`. A systemd *user* unit inherits the user
manager's environment, which an X11 login populates (check with
`systemctl --user show-environment`). Nothing host-specific is written into
the unit. On a host without a display the actions are disabled and the
Doctor says why.

Logs: `journalctl --user -u paster -f`. A second restart must not log
`[setup] installing webterm` again — if it does, the sibling solBench
checkout moved and the editable install is being repaired.
