#!/usr/bin/env python3
"""Merge plugins/*.toml into the index oshot downloads.

Writes <out>/index.toml (what oshot reads), <out>/index.json (the same, for
other tools) and a copy of the schema. Entries must already pass
validate.py. Versions come out newest first.

Usage: build_index.py [--out site]
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import shutil
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import ROOT, SCHEMA, load_toml, semver_key  # noqa: E402

INDEX_SCHEMA = 1
BARE_KEY = re.compile(r"^[A-Za-z0-9_-]+$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ----- a TOML writer for what the index contains: tables, arrays of tables,
# strings, integers, booleans, dates and arrays of strings -----
def toml_key(key: str) -> str:
    return key if BARE_KEY.match(key) else json.dumps(key)


def toml_value(key: str, value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        # Dates stay TOML dates. JSON string escapes are valid TOML basic strings
        return value if key == "date" and DATE.match(value) else json.dumps(value)
    if isinstance(value, list):
        return "[" + ", ".join(toml_value("", v) for v in value) + "]"
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{toml_key(k)} = {toml_value(k, v)}" for k, v in value.items()) + " }"
    raise TypeError(f"can't write {type(value).__name__} as TOML")


def is_table_array(value) -> bool:
    return isinstance(value, list) and value != [] and all(isinstance(v, dict) for v in value)


def write_table(lines: list[str], path: list[str], table: dict) -> None:
    scalars = {k: v for k, v in table.items() if not isinstance(v, dict) and not is_table_array(v)}
    tables = {k: v for k, v in table.items() if isinstance(v, dict)}
    arrays = {k: v for k, v in table.items() if is_table_array(v)}

    if path and (scalars or not (tables or arrays)):
        lines.append(f"\n[{'.'.join(toml_key(p) for p in path)}]")
    for k, v in scalars.items():
        lines.append(f"{toml_key(k)} = {toml_value(k, v)}")
    for k, v in tables.items():
        write_table(lines, path + [k], v)
    for k, items in arrays.items():
        for item in items:
            lines.append(f"\n[[{'.'.join(toml_key(p) for p in path + [k])}]]")
            # Small sub-tables (source, artifacts entries) read best inline
            for ik, iv in item.items():
                if isinstance(iv, dict) and all(isinstance(x, dict) for x in iv.values()) and iv:
                    continue
                lines.append(f"{toml_key(ik)} = {toml_value(ik, iv)}")
            for ik, iv in item.items():
                if isinstance(iv, dict) and all(isinstance(x, dict) for x in iv.values()) and iv:
                    lines.append(f"\n[{'.'.join(toml_key(p) for p in path + [k, ik])}]")
                    for tk, tv in iv.items():
                        lines.append(f"{toml_key(tk)} = {toml_value(tk, tv)}")


def build(entries: list[dict]) -> dict:
    plugins = {}
    for entry in sorted(entries, key=lambda e: e["id"]):
        entry = {k: v for k, v in entry.items() if k != "schema"}
        entry["versions"] = sorted(entry["versions"], key=lambda v: semver_key(v["version"]), reverse=True)
        plugins[entry["id"]] = {k: v for k, v in entry.items() if k != "id"}
    return {
        "schema": INDEX_SCHEMA,
        "generated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "plugins": plugins,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=ROOT / "site")
    args = parser.parse_args()

    entries = [load_toml(p.read_text()) for p in sorted((ROOT / "plugins").glob("*.toml"))]
    index = build(entries)

    lines = [
        "# The oshot plugin index, generated from https://github.com/Toni500github/oshot-plugin-index",
        "# Don't edit it. Change the entries in plugins/ instead.",
        f"schema = {index['schema']}",
        f"generated = {index['generated']}",
    ]
    if not index["plugins"]:
        lines.append("\n[plugins]")
    for plugin_id, plugin in index["plugins"].items():
        write_table(lines, ["plugins", plugin_id], plugin)
    text = "\n".join(lines) + "\n"

    # What oshot will read must parse back to the same data
    parsed = load_toml(text)
    parsed["generated"] = index["generated"]
    if parsed != json.loads(json.dumps(index)):
        sys.exit("internal error: index.toml doesn't round-trip")

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "index.toml").write_text(text)
    (args.out / "index.json").write_text(json.dumps(index, indent=1, ensure_ascii=False) + "\n")
    shutil.copy(SCHEMA, args.out / SCHEMA.name)
    print(f"Wrote {len(index['plugins'])} plugin(s) to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
