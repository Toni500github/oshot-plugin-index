#!/usr/bin/env python3
"""Take a new plugin submitted to the new-pr branch into plugins/.

A submission adds one plugins/<id>.toml to new-pr (copied or renamed from
template.toml) and changes nothing else. This checks that, makes sure the
plugin isn't in the index yet, and commits its entry to the branch checked
out here (main) as its submitter, so validate.py --base can check it like
any other change. Prints the entry's path.

Usage: submission.py [--allow-empty] NEW_PR_REPO BASE HEAD
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate  # noqa: E402
from validate import ROOT, report  # noqa: E402

TEMPLATE = "template.toml"


def git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, check=True).stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("repo", type=Path, help="a checkout of the new-pr branch")
    parser.add_argument("base", help="new-pr before the submission")
    parser.add_argument("head", help="new-pr with the submission")
    parser.add_argument("--allow-empty", action="store_true",
                        help="print nothing and succeed if no entry was added (a maintainer's change to new-pr)")
    args = parser.parse_args()

    added, others = [], []
    diff = git(args.repo, "diff", "--name-status", "--no-renames", f"{args.base}...{args.head}").decode()
    for line in diff.splitlines():
        status, name = line.split("\t", 1)
        if status == "A" and name.startswith("plugins/") and name.count("/") == 1 and name.endswith(".toml"):
            added.append(name)
        elif not (status == "D" and name == TEMPLATE):  # renamed to the entry
            others.append(name)

    if not added:
        if args.allow_empty:
            return 0
        report(TEMPLATE, "copy template.toml to plugins/<your plugin ID>.toml and fill it in")
        return 1
    for name in others:
        report(name, "a submission only adds plugins/<id>.toml, so this file can't change")
    if len(added) > 1:
        report(added[1], f"one plugin per pull request, please (this one adds {', '.join(added)})")
    if validate.errors:
        return 1

    name = added[0]
    dest = ROOT / name
    if dest.exists():
        report(name, "this plugin is already in the index: update it with a pull request against main")
        return 1
    dest.write_bytes(git(args.repo, "show", f"{args.head}:{name}"))

    author = git(args.repo, "log", "-1", "--diff-filter=A", "--format=%an <%ae>", args.head, "--", name)
    git(ROOT, "add", "--", name)
    git(ROOT, "commit", "-q", "-m", f"Add {Path(name).stem}",
        *(["--author", author.decode().strip()] if author.strip() else []))
    print(name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
