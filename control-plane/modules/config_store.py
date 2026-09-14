"""Read and rewrite ``config.yaml`` without losing a comment (plan D5).

The file is flat ``key: value`` with comments the user wrote, so a change
is a line-level replacement of the value part and nothing else. What the
popup will actually use comes from sourcing lib-config.sh (the bash dump);
its warnings ride back in every response so an invalid value is never
saved silently.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import bash_bridge, config_schema, fileio
from .paths import Paths

ADDED_MARKER = "# added by paster front"


class Invalid(ValueError):
    """Unknown key or a value of the wrong shape for the form."""


@dataclass(frozen=True)
class ConfigDoc:
    raw: str
    rev: str
    values: dict          # what the file says, per key present
    effective: dict       # what lib-config.sh resolves (defaults filled in)
    warnings: tuple       # lib-config.sh's "paster: config … invalid" lines
    missing: tuple        # schema keys absent from the file


def read_config(paths: Paths) -> ConfigDoc:
    text, rev = fileio.read_text(paths.config_file)
    return _doc(paths, text, rev)


def _doc(paths: Paths, text: str, rev: str) -> ConfigDoc:
    values = config_schema.parse_flat(text)
    dump = bash_bridge.dump_config(paths)
    missing = tuple(k for k in config_schema.KEYS if k not in values)
    return ConfigDoc(raw=text, rev=rev, values=values, effective=dump.values,
                     warnings=dump.warnings, missing=missing)


def replace_value(text: str, key: str, new_value: str) -> str | None:
    """``text`` with the first ``key:`` line's value swapped; None if absent."""
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if not line.startswith(f"{key}:"):
            continue
        body = line.rstrip("\r\n")
        newline = line[len(body):]
        prefix, _value, rest = config_schema.split_line(body)
        if not prefix.endswith((" ", "\t")):
            prefix += " "
        lines[i] = f"{prefix}{new_value}{rest}{newline}"
        return "".join(lines)
    return None


def set_values(text: str, changes: dict) -> str:
    """Apply ``{key: file-spelled value}``; keys the file lacks are appended
    under one marker comment."""
    out = text
    appended = []
    for key, spelled in changes.items():
        replaced = replace_value(out, key, spelled)
        if replaced is None:
            appended.append(f"{key}: {spelled}\n")
        else:
            out = replaced
    if appended:
        if out and not out.endswith("\n"):
            out += "\n"
        if ADDED_MARKER not in out:
            out += f"\n{ADDED_MARKER}\n"
        out += "".join(appended)
    return out


def spell_changes(values: object) -> dict:
    if not isinstance(values, dict):
        raise Invalid("'values' must be an object of key: value")
    spelled = {}
    for key, value in values.items():
        field = config_schema.FIELD_BY_KEY.get(str(key))
        if field is None:
            raise Invalid(f"unknown config key: {key!r}")
        if isinstance(value, (dict, list)) or value is None:
            raise Invalid(f"{key}: a single value is expected")
        text = str(value)
        if "\n" in text or "\r" in text:
            raise Invalid(f"{key}: one line only")
        if field.type != "bool" and '"' in text:
            raise Invalid(f"{key}: double quotes are not allowed in a value")
        spelled[key] = config_schema.to_file_value(field, value)
    return spelled


def write_values(paths: Paths, values: object, base_rev: str | None) -> ConfigDoc:
    spelled = spell_changes(values)
    with fileio.LOCK:
        text, rev = fileio.read_text(paths.config_file)
        if base_rev is not None and base_rev != rev:
            raise fileio.StaleRevision(rev)
        new_text = set_values(text, spelled)
        new_rev = fileio.checked_write(paths, fileio.CONFIG_RELPATH, new_text, rev)
        return _doc(paths, new_text, new_rev)


def write_raw(paths: Paths, text: object, base_rev: str | None) -> ConfigDoc:
    if not isinstance(text, str):
        raise Invalid("'text' must be a string")
    if "\0" in text:
        raise Invalid("binary content is not a config file")
    with fileio.LOCK:
        new_rev = fileio.checked_write(paths, fileio.CONFIG_RELPATH, text, base_rev)
        return _doc(paths, text, new_rev)


def preflight(values: object) -> dict:
    """{key: {ok, effective, message}} — the form's live feedback, from the
    schema mirror. The bash warnings after a save are the final word."""
    if not isinstance(values, dict):
        raise Invalid("'values' must be an object")
    out = {}
    for key, value in values.items():
        field = config_schema.FIELD_BY_KEY.get(str(key))
        if field is None:
            continue
        raw = config_schema.to_file_value(field, value).strip('"')
        v = config_schema.validate(field, raw)
        out[key] = {"ok": v.ok, "effective": v.effective, "message": v.message}
    return out
