# oshot plugin index

The list of plugins that [oshot](https://github.com/Toni500github/oshot) can browse and install. Each plugin is one
file, [`plugins/<id>.toml`](plugins), submitted to the
[`new-pr`](https://github.com/Toni500github/oshot-plugin-index/tree/new-pr) branch and updated through pull requests.
Every change combines the entries into one index that oshot downloads:

- https://toni500github.github.io/oshot-plugin-index/index.toml (what oshot reads)
- https://toni500github.github.io/oshot-plugin-index/index.json (the same, for other tools)

> [!IMPORTANT]
> **Listed doesn't mean audited.** Plugins are native code that runs with oshot's permissions. A pull request is
> checked for a correct entry, a public source and matching checksums, and looked over by a maintainer, but nobody
> reviews every line of every plugin. Only install plugins from people you trust.

> [!NOTE]
> oshot reads this index from its next release on (it's in the development builds already). Open it with Tools >
> Browse Plugins in the `-plugins` builds, or use `oshotpm search` and `oshotpm install <ID>`.

Plugins are still experimental in oshot. See [Writing oshot plugins](https://github.com/Toni500github/oshot/blob/main/docs/plugins.md)
for how to make one.

## Adding a plugin

1. Release your plugin: tag a commit in a public git repository and, if you can, attach prebuilt libraries (or
   oshotpm prebuilt archives) for the platforms you support. Prebuilt files are what most people need, since building
   from source needs git, a compiler and oshot's SDK, which few Windows and macOS users have.
2. Fork this repository with **Copy the `main` branch only** unchecked, so that your fork has the `new-pr` branch.
   Like Flathub's `new-pr`, it only holds a template entry. Clone it and start a branch for your plugin:

   ```sh
   git clone --branch new-pr --single-branch https://github.com/<your GitHub user>/oshot-plugin-index oshot-plugin-submission
   cd oshot-plugin-submission
   git checkout -b <your plugin ID>
   ```

3. Copy or rename `template.toml` to `plugins/<your plugin ID>.toml` and fill it in (it's [the entry](#the-entry)
   below). [`plugins/io.github.toni500github.plugin-test.toml`](plugins/io.github.toni500github.plugin-test.toml), the
   entry of the [test plugin](https://github.com/Toni500github/oshot-plugin-test) whose release workflow builds every
   target, is a complete example.
4. Push the branch and open a pull request against `new-pr`, not `main`. The checks below run on it; fix what they
   report.

When a maintainer merges it, the entry is committed to `plugins/` on `main` in your name, `new-pr` goes back to the
template, and the index is rebuilt. One plugin per pull request, please.

### Plugin IDs

The ID is the one compiled into the plugin (`oshot_plugin_t.id`) and written in its `oshot-plugin.toml`. It's also
the entry's file name. Use a reverse domain you control:

- `io.github.<your GitHub user>.<plugin>`: the user must be one of the entry's `owners`;
- or a domain of yours, e.g. `org.example.translate`.

The first entry for an ID claims it.

## The entry

The full definition, with every field's rules, is [`schema/plugin.schema.json`](schema/plugin.schema.json).

```toml
schema = 1                                   # entry format version

id          = "io.github.toni500github.plugin-test"
name        = "Uppercase (test plugin)"
description = "Uppercases the extracted text. A small plugin for testing oshot's plugin system"
owners      = ["Toni500github"]              # GitHub accounts that may change this entry
homepage    = "https://github.com/Toni500github/oshot-plugin-test"
license     = "Unlicense"                    # SPDX expression
authors     = ["Toni500github"]              # optional, if not the same as owners
tags        = ["test", "text"]               # optional, up to 8

[[versions]]                                 # newest first, by convention
version = "1.0.0"                            # semantic version
date    = 2026-10-17
abi     = 1                                  # OSHOT_API_VERSION it's built for
imgui   = 19284                              # OSHOT_IMGUI_VERSION, or 0 without ImGui
changes = "First release on the reworked plugin API"   # optional
source  = { git = "https://github.com/Toni500github/oshot-plugin-test", tag = "v1.0.0", commit = "<40 hex digits>" }

  [versions.artifacts]                       # optional if source is given: prebuilt files per target
  linux-x86_64   = { url = "https://github.com/.../oshot-plugin-test-linux-x86_64.so", sha256 = "<64 hex digits>" }
  windows-x86_64 = { url = "https://github.com/.../oshot-plugin-test-windows-x86_64.dll", sha256 = "<64 hex digits>" }
  macos-aarch64  = { url = "https://github.com/.../oshot-plugin-test-macos-aarch64.dylib", sha256 = "<64 hex digits>" }
```

- A `[capabilities]` table declares what the plugin does beyond oshot's API, each with the reason it needs to:
  `network` (connects to the internet), `files` (reads or writes files outside its own folder and oshot's cache) and
  `processes` (runs other programs, `run_process()` included). oshot shows them before installing and in its plugin
  lists. Nothing can enforce them, since plugins are native code, so they must match what the plugin does. Use the
  same ones as the plugin's `oshot-plugin.toml`. The test plugin needs none; a translator would have:

  ```toml
  [capabilities]
  network = "Sends the text to translate.example.com to translate it"
  ```
- A version needs a `source`, `artifacts`, or both. oshot uses the artifact for the person's platform, and builds from
  source when there's none.
- `source.commit` is what reviewers look at, so it must be the commit the tag points to. If the plugin isn't at the root
  of the repository, set `source.subdir` to the folder with its `oshot-plugin.toml`.
- An artifact is either the plugin library itself (`.so`, `.dll`, `.dylib`) or an
  [oshotpm prebuilt archive](https://github.com/Toni500github/oshot/blob/main/docs/plugins.md#distributing)
  (`.zip`, `.tar.gz`, `.tgz`, `.tar.xz`, `.txz`). Get its checksum with `sha256sum <file>`.
- Targets are `<platform>-<arch>` as in oshot: platforms `linux`, `macos`, `windows`, `freebsd`, `openbsd`, `netbsd`,
  `dragonfly`; architectures `x86_64`, `aarch64`, `i686`, `armv7`, `riscv64`, `ppc64le`, `s390x`.

## Updating a plugin

Add a new `[[versions]]` table to `plugins/<id>.toml` and open a pull request against `main` from one of the
`owners`.

Once its checks pass, it's merged on its own after 24 hours, so a maintainer has time to look at it. That's if it
only adds versions to your entry, or yanks some, builds them from the same git repository and downloads them from the
same places as before (the same GitHub or Codeberg repository, or else the same server). Anything else waits for a
maintainer: changing `owners`, `[capabilities]` or another field, moving the artifacts somewhere new, or changing other
files. A yank doesn't wait. [`scripts/automerge.py`](scripts/automerge.py) has the exact rules.

Released versions can't be changed or removed, so what was reviewed stays what people install. To withdraw one,
yank it, so oshot stops offering it and warns people who have it installed.

```toml
yanked        = true
yanked-reason = "Crashed when the OCR output was empty"
```

To hand a plugin over, have a current owner add the new one to `owners`.

## What a pull request is checked for

[`scripts/validate.py`](scripts/validate.py) runs on every pull request and checks:

- the entry against the schema, and that its file is named after its ID;
- against `new-pr`, that the pull request only adds `plugins/<id>.toml` and the plugin isn't in the index yet; against
  `main`, that it adds no new entries, unless it's from a maintainer;
- that the pull request's author is an owner (a maintainer, listed in [`.github/maintainers`](.github/maintainers),
  may change any entry);
- that released versions are unchanged, apart from yanking;
- for each new version: every artifact downloads and matches its `sha256`, the tag points to the commit, and the
  `linux-x86_64` build, if any, has the entry's ID, ABI and ImGui version compiled in.

A maintainer then looks a new plugin over before merging it, and can stop an update from being merged on its own
with the `no-auto-merge` label. A plugin is refused or removed if it hides what it does
(obfuscated code, artifacts that don't match the source), does more than its description and `capabilities` say
(e.g. sends data somewhere without declaring `network`), or harms people's computers.

Run the checks yourself (Python 3.11+):

```sh
pip install -r scripts/requirements.txt
python scripts/validate.py plugins/<id>.toml           # the entry
python scripts/validate.py ../oshot-plugin-submission/plugins/<id>.toml   # a submission, from a clone of main
python scripts/validate.py --base origin/main --author <your GitHub user> --network --inspect   # like CI, for an update
python scripts/build_index.py --out site               # the index oshot downloads
```

## License

The scripts and schema are under the [BSD 3-Clause license](LICENSE). By adding an entry, you agree to it being
published under the same license. The plugins themselves are under their own licenses.
