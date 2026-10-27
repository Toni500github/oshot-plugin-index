<!-- New plugins go against the new-pr branch, updates against main. See the README. One plugin per pull request. -->

**Plugin:** <!-- its ID, e.g. io.github.user.translate -->

- [ ] I'm one of the `owners` in the entry (or a maintainer).
- [ ] The source of this version is public, at the tag and commit in the entry.
- [ ] Every artifact is built from that source, and its `sha256` is the file's (`sha256sum file`).
- [ ] `[capabilities]` lists everything the plugin does on its own (`network`, `files`, `processes`), with the real reason for each.
- [ ] I tested this version with oshot.
