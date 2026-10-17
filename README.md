# oshot plugin index

The list of plugins that [oshot](https://github.com/Toni500github/oshot) can browse and install. Each plugin is one
file, [`plugins/<id>.toml`](plugins), added and updated through pull requests. On every merge, the entries are merged
into one index that oshot downloads:

- https://toni500github.github.io/oshot-plugin-index/index.toml (what oshot reads)
- https://toni500github.github.io/oshot-plugin-index/index.json (the same, for other tools)

> [!IMPORTANT]
> **Listed doesn't mean audited.** Plugins are native code that runs with oshot's permissions. A pull request is
> checked for a correct entry, a public source and matching checksums, and looked over by a maintainer, but nobody
> reviews every line of every plugin. Only install plugins from people you trust.

> [!NOTE]
> **Status: draft.** oshot doesn't read this index yet: installing from it, yank warnings and `source.subdir` arrive
> with that support. Until then, entries can be added and checked, and plugins are installed with `oshotpm install`.

Plugins are still experimental in oshot: see [Writing oshot plugins](https://github.com/Toni500github/oshot/blob/main/docs/plugins.md)
for how to make one.

## Adding a plugin

1. Release your plugin: tag a commit in a public git repository and, if you can, attach prebuilt libraries (or
   oshotpm prebuilt archives) for the platforms you support. Prebuilt files are what most people need: building from
   source needs git, a compiler and oshot's SDK, which few Windows and macOS users have.
2. Fork this repository and add `plugins/<your plugin ID>.toml`, starting from an existing entry such as
   [`plugins/io.github.toni500github.plugin-test.toml`](plugins/io.github.toni500github.plugin-test.toml), the
   [test plugin](https://github.com/Toni500github/oshot-plugin-test) whose release workflow builds every target.
3. Open a pull request. The checks below run on it; fix what they report.

One plugin per pull request, please.

### Plugin IDs

The ID is the one compiled into the plugin (`oshot_plugin_t.id`) and written in its `oshot-plugin.toml`, and the
entry's file name. Use a reverse domain you control:

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
network     = false                          # optional: whether it connects to the internet (shown before installing)

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

- A version needs a `source`, `artifacts`, or both. oshot uses the artifact for the person's platform, and builds from
  source when there's none.
- `source.commit` is what reviewers look at: it must be the commit the tag points to. If the plugin isn't at the root
  of the repository, set `source.subdir` to the folder with its `oshot-plugin.toml`.
- An artifact is either the plugin library itself (`.so`, `.dll`, `.dylib`) or an
  [oshotpm prebuilt archive](https://github.com/Toni500github/oshot/blob/main/docs/plugins.md#distributing)
  (`.zip`, `.tar.gz`, `.tgz`, `.tar.xz`, `.txz`). Get its checksum with `sha256sum <file>`.
- Targets are `<platform>-<arch>` as in oshot: platforms `linux`, `macos`, `windows`, `freebsd`, `openbsd`, `netbsd`,
  `dragonfly`; architectures `x86_64`, `aarch64`, `i686`, `armv7`, `riscv64`, `ppc64le`, `s390x`.

## Updating a plugin

Add a new `[[versions]]` table and open a pull request from one of the `owners`.

Released versions can't be changed or removed, so what was reviewed stays what people install. To withdraw one,
yank it: oshot no longer offers it and warns people who have it installed.

```toml
yanked        = true
yanked-reason = "Crashed when the OCR output was empty"
```

To hand a plugin over, have a current owner add the new one to `owners`.

## What a pull request is checked for

[`scripts/validate.py`](scripts/validate.py) runs on every pull request and checks:

- the entry against the schema, and that its file is named after its ID;
- that the pull request's author is an owner (a maintainer, listed in [`.github/maintainers`](.github/maintainers),
  may change any entry);
- that released versions are unchanged, apart from yanking;
- for each new version: every artifact downloads and matches its `sha256`, the tag points to the commit, and the
  `linux-x86_64` build, if any, has the entry's ID, ABI and ImGui version compiled in.

A maintainer then looks the plugin over before merging. A plugin is refused or removed if it hides what it does
(obfuscated code, artifacts that don't match the source), sends data somewhere without saying so in its description
and `network`, or harms people's computers.

Run the checks yourself (Python 3.11+):

```sh
pip install -r scripts/requirements.txt
python scripts/validate.py plugins/<id>.toml           # the entry
python scripts/validate.py --base origin/main --author <your GitHub user> --network --inspect   # like CI
python scripts/build_index.py --out site               # the index oshot downloads
```

## License

The scripts and schema are under the [BSD 3-Clause license](LICENSE). By adding an entry, you agree to it being
published under the same license. The plugins themselves are under their own licenses.
