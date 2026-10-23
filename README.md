# Zellij config

Catppuccin Mocha, three layouts, matching swap layouts and three verified plugins.
The configuration works with the Zellij version selected in
[VERSIONS.md](VERSIONS.md). **Python 3.10+** is required for the shared setup,
validation, launcher and explicit upgrade helpers; they use only the standard
library. Zellij itself runs independently of those helpers.

## Install

Install Python and Zellij, then clone this repository:

```sh
git clone https://github.com/abhi-k9/zellij-config.git
cd zellij-config
./setup.sh --dry-run
./setup.sh --offline
zj attach --create main
```

Linux/macOS setup installs the launcher in `~/.local/bin`; add that directory to
PATH if needed. To install the selected Zellij binary with archive verification:

```sh
python3 tools/manage.py install-zellij --bin-dir ~/.local/bin
```

On Windows, install Python 3.10+ and Zellij, then use Windows PowerShell 5.1+:

```powershell
./setup.ps1 -DryRun
./setup.ps1 -Offline
```

Windows setup puts the wrappers in
`%LOCALAPPDATA%\Programs\zellij-config\bin`; add it to PATH. You can also run the
shared helper directly with `python tools/manage.py install --offline`.

All installation modes verify plugin hashes before activation. `--offline`
forbids network downloads and uses the bundled files. Without it, missing pinned
plugins can be downloaded and verified. Config and layouts are validated with
your actual Zellij executable before the old configuration is moved.

## Choose when to upgrade

Versions are pinned for repeatability. They are **not permanently fixed**:

```sh
python3 tools/manage.py versions check
python3 tools/manage.py versions update --all
# Or select a component/tag explicitly:
python3 tools/manage.py versions update --plugin zjstatus=latest
python3 tools/manage.py versions update --zellij latest
```

The update command changes the repository's selected pins and verified plugin
files. Review `git diff`, run the checks, then explicitly install the selected
Zellij executable and rerun setup. It never silently upgrades a running setup.
Specific older tags work too. See [all version commands](VERSIONS.md).

## Recovery and symlinks

```sh
./setup.sh --restore
# Windows: ./setup.ps1 -Restore
```

Setup stages a complete tree privately, verifies it, retains the previous tree
inside a private `zellij.backup-*/tree/` snapshot, and publishes the staged tree.
It locks the target against another installer. Failed preparation leaves the
active config alone; publication errors trigger rollback. An interruption between
directory renames is recorded and recovered on the next setup invocation.

Managed file/directory symlinks are materialized in the new config; external
dotfiles targets are never overwritten. A symlink of the entire config directory
remains a symlink. Snapshots retain the old tree's links; later edits to an
external link target are not an independent historical byte snapshot of that
external file. Keep your dotfiles in version control as well.

Directory publication has a short rename gap; this is not an atomic exchange or
a power-loss durability guarantee. Running sessions may need a reload/restart to
notice a directory replacement; close Zellij on Windows if open handles prevent
renaming. Restore first validates its staged snapshot and saves the current tree,
so a second restore can undo the previous restore.

## Validate and contribute

```sh
./check.sh
python3 -m unittest discover -s tests -v
git config core.hooksPath hooks
```

Full validation requires Zellij. `./check.sh --static` explicitly omits its parser
checks. The optional hook validates staged content and fails when validation
cannot run. CI exercises the same regression tests and real Zellij on Linux,
macOS and Windows. Network-dependent checks run separately by manual dispatch.

See the [configuration guide](config/README.md), printable
[cheatsheets](cheatsheets/), [audit resolution map](docs/AUDIT_FIXES.md) and
[third-party notices](THIRD_PARTY_NOTICES.md).
