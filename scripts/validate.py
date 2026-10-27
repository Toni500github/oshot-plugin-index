#!/usr/bin/env python3
"""Validate oshot plugin index entries (plugins/<id>.toml).

Checks every entry against schema/plugin.schema.json, plus what a schema
can't express. With --base, also checks a pull request's changes against
the base branch: who may change an entry, and that released versions stay
as they were. --network downloads the new versions' artifacts and checks
their sha256 and git tags; --inspect also loads new linux-x86_64 builds to
compare the ID, ABI and ImGui version compiled into them.

Usage:
    validate.py [FILE...]                    every entry, or the given files
    validate.py --base origin/main --author LOGIN [--network] [--inspect]
"""

from __future__ import annotations

import argparse
import ctypes
import datetime
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import urllib.request
import zipfile
from pathlib import Path

try:
    import jsonschema
except ImportError:
    sys.exit("jsonschema is missing: pip install -r scripts/requirements.txt")

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "schema" / "plugin.schema.json"
MAINTAINERS = ROOT / ".github" / "maintainers"
MAX_DOWNLOAD = 200 * 1024 * 1024
# Fields of a released version that may still change
MUTABLE_VERSION_FIELDS = {"yanked", "yanked-reason"}

errors = 0


def report(path: Path | str, msg: str, level: str = "error") -> None:
    global errors
    if level == "error":
        errors += 1
    rel = os.path.relpath(path) if isinstance(path, Path) else path
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::{level} file={rel}::{msg}")
    else:
        print(f"{rel}: {level}: {msg}")


def jsonable(value):
    """TOML dates and times to strings, as the schema expects them."""
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [jsonable(v) for v in value]
    if isinstance(value, (datetime.date, datetime.datetime, datetime.time)):
        return value.isoformat()
    return value


def load_toml(text: str) -> dict:
    return jsonable(tomllib.loads(text))


def semver_key(version: str):
    """Sort key: 1.10.0 > 1.9.0, and 2.0.0 > 2.0.0-beta.2 > 2.0.0-beta.1"""
    core, _, pre = version.partition("-")
    nums = tuple(int(n) for n in core.split("."))
    pre_parts = tuple((0, int(p), "") if p.isdigit() else (1, 0, p) for p in pre.split(".")) if pre else ()
    return nums, not pre, pre_parts


def schema_message(err) -> str:
    """jsonschema's message, or a readable one where it would only quote a regex"""
    path = list(err.absolute_path)
    if err.validator == "anyOf" and len(path) == 2 and path[0] == "versions":
        return "a version needs a source, artifacts, or both"
    if err.validator == "pattern":
        if path and path[-1] == "url" and err.validator_value.startswith("\\."):
            return f"{err.instance!r} must end in .so, .dll, .dylib, .zip, .tar.gz, .tgz, .tar.xz or .txz"
        if desc := err.schema.get("description"):
            return f"{err.instance!r} is not valid: {desc}"
    return err.message


# ----- one entry on its own -----
def check_entry(path: Path, entry: dict, validator) -> bool:
    ok = True
    for err in sorted(validator.iter_errors(entry), key=lambda e: [str(p) for p in e.absolute_path]):
        where = "/".join(str(p) for p in err.absolute_path) or "(top level)"
        report(path, f"{where}: {schema_message(err)}")
        ok = False
    if not ok:
        return False

    if path.parent.name == "plugins" and path.stem != entry["id"]:
        report(path, f"the file must be named {entry['id']}.toml")
        ok = False

    # io.github.<user>.* belongs to that GitHub user, so nobody else can take it
    parts = entry["id"].split(".")
    if len(parts) >= 3 and parts[0] == "io" and parts[1] == "github":
        if parts[2] not in {o.lower() for o in entry["owners"]}:
            report(path, f"an io.github.{parts[2]}.* ID needs '{parts[2]}' in owners")
            ok = False

    seen = set()
    for v in entry["versions"]:
        if v["version"] in seen:
            report(path, f"version {v['version']} is listed twice")
            ok = False
        seen.add(v["version"])
        if "yanked-reason" in v and not v.get("yanked"):
            report(path, f"version {v['version']} has a yanked-reason but isn't yanked")
            ok = False
    return ok


# ----- a pull request's changes -----
def git_show(ref: str, path: Path) -> str | None:
    rel = os.path.relpath(path, ROOT)
    r = subprocess.run(["git", "show", f"{ref}:{rel}"], cwd=ROOT, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def changed_entries(base: str) -> list[tuple[Path, str]]:
    """(path, status) of the entries changed since `base`: A, M or D"""
    r = subprocess.run(
        ["git", "diff", "--name-status", "--no-renames", f"{base}...HEAD", "--", "plugins/"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    out = []
    for line in r.stdout.splitlines():
        status, name = line.split("\t", 1)
        if name.endswith(".toml"):
            out.append((ROOT / name, status[0]))
        elif not name.endswith(".gitkeep"):
            report(ROOT / name, "only <id>.toml files belong in plugins/")
    return out


def check_change(path: Path, status: str, entry: dict | None, base: str, author: str | None,
                 maintainers: set[str]) -> list[dict]:
    """Checks a change against the base branch and returns the versions it adds."""
    old_text = git_show(base, path) if status != "A" else None
    old = load_toml(old_text) if old_text else None
    is_maintainer = author is not None and author.lower() in maintainers

    def allowed(owners):
        return author is None or is_maintainer or author.lower() in {o.lower() for o in owners}

    if status == "D":
        if old and not allowed(old["owners"]):
            report(path, f"only its owners ({', '.join(old['owners'])}) or a maintainer can remove this entry")
        return []

    if old is None:
        if not allowed(entry["owners"]):
            report(path, f"the pull request's author ({author}) must be one of the owners")
        return entry["versions"]

    if not allowed(old["owners"]):
        report(path, f"only its owners ({', '.join(old['owners'])}) or a maintainer can change this entry")
    if old.get("id") != entry["id"]:
        report(path, "the ID can't change: add a new entry instead")

    new_versions = {v["version"]: v for v in entry["versions"]}
    for v in old.get("versions", []):
        new = new_versions.get(v["version"])
        if new is None:
            report(path, f"version {v['version']} was removed: yank it instead (yanked = true)")
            continue
        strip = lambda d: {k: val for k, val in d.items() if k not in MUTABLE_VERSION_FIELDS}
        if strip(v) != strip(new):
            report(path, f"version {v['version']} was changed: released versions can only be yanked, "
                         "release a new version instead")

    old_names = {v["version"] for v in old.get("versions", [])}
    return [v for v in entry["versions"] if v["version"] not in old_names]


# ----- network checks -----
def download(url: str, dest: Path) -> str:
    """Downloads `url` to `dest` and returns its sha256."""
    h = hashlib.sha256()
    size = 0
    req = urllib.request.Request(url, headers={"User-Agent": "oshot-plugin-index-validator"})
    with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as f:
        while chunk := resp.read(1 << 16):
            size += len(chunk)
            if size > MAX_DOWNLOAD:
                raise ValueError(f"bigger than {MAX_DOWNLOAD // (1024 * 1024)} MiB")
            h.update(chunk)
            f.write(chunk)
    return h.hexdigest()


def check_source(path: Path, version: dict) -> None:
    src = version["source"]
    r = subprocess.run(
        ["git", "ls-remote", src["git"], f"refs/tags/{src['tag']}", f"refs/tags/{src['tag']}^{{}}"],
        capture_output=True, text=True, timeout=120,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    if r.returncode != 0:
        report(path, f"{version['version']}: can't read {src['git']}: {r.stderr.strip()}")
        return
    commits = {line.split("\t")[0] for line in r.stdout.splitlines() if line}
    if not commits:
        report(path, f"{version['version']}: tag '{src['tag']}' doesn't exist in {src['git']}")
    elif src["commit"] not in commits:
        report(path, f"{version['version']}: tag '{src['tag']}' points to {', '.join(sorted(commits))}, "
                     f"not {src['commit']}")


def find_library_in_archive(archive: Path, plugin_id: str, workdir: Path) -> Path | None:
    """The linux-x86_64 library an oshotpm prebuilt archive installs for `plugin_id`"""
    out = workdir / "extracted"
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            z.extractall(out)
    else:
        with tarfile.open(archive) as t:
            t.extractall(out, filter="data")

    root = out
    if not (root / "oshot-plugin.toml").exists():
        entries = list(out.iterdir())
        if len(entries) == 1 and (entries[0] / "oshot-plugin.toml").exists():
            root = entries[0]
    manifest = tomllib.loads((root / "oshot-plugin.toml").read_text())
    for name, table in manifest.items():
        if not isinstance(table, dict) or table.get("id") != plugin_id:
            continue
        rel = table.get("prebuilt", {}).get("linux-x86_64")
        if rel:
            return root / rel
        libs = [p for p in (root / table.get("output-dir", ".")).iterdir() if p.suffix == ".so"]
        return libs[0] if len(libs) == 1 else None
    return None


class OshotPlugin(ctypes.Structure):
    # The start of oshot_plugin_t in oshot_plugin.h
    _fields_ = [
        ("struct_size", ctypes.c_uint32),
        ("abi_version", ctypes.c_uint32),
        ("imgui_version", ctypes.c_uint32),
        ("id", ctypes.c_char_p),
        ("name", ctypes.c_char_p),
    ]


def inspect_library(path: Path, lib: Path, entry: dict, version: dict) -> None:
    """Loads a linux-x86_64 plugin and compares its descriptor with the entry.
    RTLD_LAZY: its cimgui functions only resolve when called, which never happens here."""
    try:
        handle = ctypes.CDLL(str(lib), mode=os.RTLD_LAZY | os.RTLD_LOCAL)
        entry_fn = handle.oshot_plugin_entry
    except (OSError, AttributeError) as e:
        report(path, f"{version['version']}: linux-x86_64 library can't be loaded or doesn't export "
                     f"oshot_plugin_entry(): {e}")
        return
    entry_fn.restype = ctypes.POINTER(OshotPlugin)
    desc = entry_fn().contents
    found = {
        "id": (desc.id or b"").decode(errors="replace"),
        "abi": desc.abi_version,
        "imgui": desc.imgui_version,
    }
    expected = {"id": entry["id"], "abi": version["abi"], "imgui": version["imgui"]}
    for key in expected:
        if found[key] != expected[key]:
            report(path, f"{version['version']}: the linux-x86_64 library's {key} is {found[key]}, "
                         f"the entry says {expected[key]}")


def check_network(path: Path, entry: dict, versions: list[dict], inspect: bool) -> None:
    can_inspect = inspect and sys.platform == "linux" and platform.machine() == "x86_64"
    for v in versions:
        if "source" in v:
            check_source(path, v)
        for target, art in v.get("artifacts", {}).items():
            with tempfile.TemporaryDirectory() as tmp:
                dest = Path(tmp) / Path(art["url"]).name
                try:
                    digest = download(art["url"], dest)
                except Exception as e:  # noqa: BLE001 (any download failure is the entry's problem)
                    report(path, f"{v['version']} {target}: can't download {art['url']}: {e}")
                    continue
                if digest != art["sha256"]:
                    report(path, f"{v['version']} {target}: sha256 is {digest}, the entry says {art['sha256']}")
                    continue
                if target != "linux-x86_64" or not can_inspect:
                    continue
                lib = dest
                if dest.suffix != ".so":
                    try:
                        lib = find_library_in_archive(dest, entry["id"], Path(tmp))
                    except Exception as e:  # noqa: BLE001
                        report(path, f"{v['version']} {target}: can't read the archive: {e}")
                        continue
                    if lib is None or not lib.exists():
                        report(path, f"{v['version']} {target}: the archive has no linux-x86_64 library for "
                                     f"{entry['id']}")
                        continue
                inspect_library(path, lib, entry, v)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="*", type=Path, help="entries to check (default: all of plugins/)")
    parser.add_argument("--base", help="git ref to compare against, e.g. origin/main")
    parser.add_argument("--author", help="GitHub login of the pull request's author")
    parser.add_argument("--network", action="store_true", help="download new artifacts and check git tags")
    parser.add_argument("--inspect", action="store_true", help="load new linux-x86_64 builds (implies --network)")
    args = parser.parse_args()

    validator_cls = jsonschema.Draft202012Validator
    schema = json.loads(SCHEMA.read_text())
    validator_cls.check_schema(schema)
    validator = validator_cls(schema, format_checker=validator_cls.FORMAT_CHECKER)

    maintainers = set()
    if MAINTAINERS.exists():
        maintainers = {l.strip().lower() for l in MAINTAINERS.read_text().splitlines()
                       if l.strip() and not l.startswith("#")}

    files = [p.resolve() for p in args.files] or sorted((ROOT / "plugins").glob("*.toml"))

    entries: dict[Path, dict] = {}
    for path in files:
        try:
            entry = load_toml(path.read_text())
        except (OSError, tomllib.TOMLDecodeError) as e:
            report(path, f"not valid TOML: {e}")
            continue
        if check_entry(path, entry, validator):
            entries[path] = entry

    if args.base:
        for path, status in changed_entries(args.base):
            if status != "D" and path not in entries:
                continue  # invalid, already reported
            new_versions = check_change(path, status, entries.get(path), args.base, args.author, maintainers)
            if (args.network or args.inspect) and new_versions:
                check_network(path, entries[path], new_versions, args.inspect)

    checked = len(entries)
    if errors:
        print(f"{errors} error(s) in {len(files)} file(s)")
        return 1
    print(f"OK: {checked} entr{'y' if checked == 1 else 'ies'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
