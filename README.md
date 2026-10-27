# Submitting a plugin to the oshot plugin index

This branch is where new plugins are submitted, like Flathub's `new-pr`. The index itself, its rules and its scripts
are on [`main`](https://github.com/Toni500github/oshot-plugin-index); read its README first.

1. Fork the repository with **Copy the `main` branch only** unchecked, clone this branch and start one for your plugin:

   ```sh
   git clone --branch new-pr --single-branch https://github.com/<your GitHub user>/oshot-plugin-index oshot-plugin-submission
   cd oshot-plugin-submission
   git checkout -b <your plugin ID>
   ```

2. Copy or rename [`template.toml`](template.toml) to `plugins/<your plugin ID>.toml` and fill it in. Change nothing
   else.
3. Push the branch and open a pull request against `new-pr`. The checks run with the scripts from `main`; fix what
   they report.

When a maintainer merges the pull request, the entry is committed to `plugins/` on `main` in your name, this branch
goes back to the template, and the index is rebuilt. Later versions are pull requests against `main`.

One plugin per pull request, please.
