#!/usr/bin/env python3
"""Decide whether a pull request against main can be merged without a maintainer.

It runs with the scripts on main, in a job that can write to the repository,
so it only reads the pull request with git and never runs its code. A pull
request qualifies when its author is one of the owners and it only adds new
versions to one entry, or yanks some of its versions. Nothing else may change:
no other file, no new entry, and the entry's other fields (owners,
capabilities, homepage...) stay as they were. New versions must also come from
where the earlier ones came from, the same git repository and the same places
for artifacts. Whether the artifacts and tags check out is for the Validate
workflow, which must have passed for the same commit.

Prints why the pull request doesn't qualify and exits with 1, or prints what
it does ("versions" or "yank") and exits with 0.

Usage: automerge.py BASE HEAD AUTHOR
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate  # noqa: E402
from validate import MAINTAINERS, ROOT, SCHEMA, load_toml  # noqa: E402

# Hosts where a file's home is its repository, not the whole host
REPO_HOSTS = {"github.com", "codeberg.org"}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def home(url: str) -> str:
    """Where a file or repository is hosted: a repository on REPO_HOSTS, or else the server"""
    u = urllib.parse.urlsplit(url)
    host = (u.hostname or "").lower()
    parts = u.path.strip("/").removesuffix(".git").lower().split("/")
    if host in REPO_HOSTS and len(parts) >= 2:
        return f"{u.scheme}://{host}/{parts[0]}/{parts[1]}"
    return f"{u.scheme}://{host}"


def check(base: str, head: str, author: str) -> tuple[list[str], str]:
    """The reasons the pull request needs a maintainer, and what it does"""
    changes = []
    for line in git("diff", "--name-status", "--no-renames", f"{base}...{head}").splitlines():
        status, name = line.split("\t", 1)
        changes.append((status[0], name))
    if len(changes) != 1:
        return [f"it changes {len(changes)} files, not one entry"], ""
    status, name = changes[0]
    if status != "M" or not name.startswith("plugins/") or name.count("/") != 1 or not name.endswith(".toml"):
        return [f"it changes {name} ({status}), not an entry already in the index"], ""

    path = ROOT / name
    old = load_toml(git("show", f"{base}:{name}"))
    new = load_toml(git("show", f"{head}:{name}"))

    # The same checks as Validate, without the network ones
    schema = json.loads(SCHEMA.read_text())
    validator = validate.jsonschema.Draft202012Validator(
        schema, format_checker=validate.jsonschema.Draft202012Validator.FORMAT_CHECKER)
    maintainers = {l.strip().lower() for l in MAINTAINERS.read_text().splitlines()
                   if l.strip() and not l.startswith("#")} if MAINTAINERS.exists() else set()
    if not validate.check_entry(path, new, validator):
        return ["the entry isn't valid"], ""
    added = validate.check_change(path, "M", new, base, author, maintainers, allow_new=False)
    if validate.errors:
        return ["the change isn't valid"], ""

    reasons = []
    for key in sorted(set(old) | set(new)):
        if key != "versions" and old.get(key) != new.get(key):
            reasons.append(f"it changes '{key}'")

    new_by_name = {v["version"]: v for v in new["versions"]}
    for v in old["versions"]:
        if v.get("yanked") and not new_by_name[v["version"]].get("yanked"):
            reasons.append(f"it takes back the yanking of {v['version']}")

    gits = {home(v["source"]["git"]) for v in old["versions"] if "source" in v}
    hosts = gits | {home(a["url"]) for v in old["versions"] for a in v.get("artifacts", {}).values()}
    for v in added:
        if "source" in v and home(v["source"]["git"]) not in gits:
            reasons.append(f"{v['version']} is built from {v['source']['git']}, a new repository")
        for target, art in v.get("artifacts", {}).items():
            if home(art["url"]) not in hosts:
                reasons.append(f"{v['version']} {target} is downloaded from {home(art['url'])}, a new place")

    return reasons, "versions" if added else "yank"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("base", help="the branch the pull request is against, e.g. origin/main")
    parser.add_argument("head", help="the pull request's head commit")
    parser.add_argument("author", help="GitHub login of the pull request's author")
    args = parser.parse_args()

    reasons, kind = check(args.base, args.head, args.author)
    for r in reasons:
        print(f"needs a maintainer: {r}")
    if reasons:
        return 1
    print(kind)
    return 0


if __name__ == "__main__":
    sys.exit(main())
