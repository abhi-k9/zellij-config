# Zellij config

Catppuccin Mocha, three layouts, matching swap layouts and three pinned plugins.
The repository root is a Zellij config directory: `config.kdl`, `layouts/`,
`themes/` and backup `plugins/` are ready to use after cloning.

## Clone directly and start

Install Git, Zellij and Python 3.10+. Choose an **absent or empty** destination;
move an existing config or nested checkout aside before cloning. Git will not
merge a clone into a nonempty directory.

Linux and macOS (this location takes precedence when present):

```sh
git clone https://github.com/abhi-k9/zellij-config.git "$HOME/.config/zellij"
"$HOME/.config/zellij/launcher/zj" attach --create main
```

Native Windows, using Windows PowerShell 5.1+:

```powershell
git clone https://github.com/abhi-k9/zellij-config.git "$env:APPDATA\Zellij\config"
& "$env:APPDATA\Zellij\config\launcher\zj.ps1" attach --create main
```

The Windows `launcher\zj.cmd` entry point also works. WSL uses the Linux paths
inside WSL. No setup script or launcher installation is required. For a custom
checkout location, pass `--config-dir /path/to/checkout` to the launcher.

Zellij itself can be started directly using the root configuration. It uses the
HTTPS aliases and its own download cache; **automatic bundled fallback is
provided by `zj`**, not by Zellij's native plugin loader. Python is required for
`zj` and the management helpers, not for plain Zellij.

### Where the clone lives

**The clone destination is both the repository root and Zellij's config
directory.** The entire checkout lives there, including `launcher/`, `tools/`
and documentation. Zellij reads `config.kdl` directly from that directory.

| Platform | Clone destination / config directory | Directory to add to PATH |
| --- | --- | --- |
| Linux / macOS, using the commands above | `~/.config/zellij` | `~/.config/zellij/launcher` |
| Native Windows | `%APPDATA%\Zellij\config` | `%APPDATA%\Zellij\config\launcher` |
| WSL | `~/.config/zellij` inside WSL | `~/.config/zellij/launcher` inside WSL |

The layout inside any of these destinations is the same:

```text
<clone destination>/
├── config.kdl
├── layouts/
├── themes/
├── plugins/
├── launcher/
├── tools/
└── docs/
```

On Windows, the final `config` in `%APPDATA%\Zellij\config` is part of Zellij's
platform-specific path. It remains even though the repository's former internal
`config/` folder was removed. On Linux/macOS, `config.kdl` is directly at
`~/.config/zellij/config.kdl`; do not add another `config/` or `zellij-config/`
level inside the destination. Git's explicit destination argument in the clone
commands above prevents the extra repository-name folder.

### Make the short zj command available

Add the checkout's **launcher subdirectory** to PATH. For the Linux/macOS paths
above, put this in `~/.bashrc` (Bash) or `~/.zshrc` (Zsh):

```sh
export PATH="$HOME/.config/zellij/launcher:$PATH"
```

For Fish, run this once to persistently add the launcher directory:

```fish
fish_add_path "$HOME/.config/zellij/launcher"
```

Run `./setup.sh` and `zj` normally from Fish. Their `#!/bin/sh` interpreter
line handles shell compatibility; do not source them or run `fish setup.sh`.

On Windows, add `%APPDATA%\Zellij\config\launcher` to your **user Path** through
Environment Variables. Open a new terminal after changing PATH, then run:

```sh
zj attach --create main
```

For a custom clone destination, add that destination's `launcher` subdirectory
instead. Keep the directory containing the actual `zellij` executable on PATH
as well; `zj` launches it.

Alternatively, install standalone launcher helpers from your checkout:

```sh
./setup.sh --launcher-only                    # Defaults to ~/.local/bin
./setup.sh --launcher-only --bin-dir ~/bin    # Choose another directory
```

This leaves your configuration untouched and requires only Python 3.10+ to
install. Running `zj` still requires Zellij. Add the chosen directory to PATH;
for a custom config location, pass `zj --config-dir /path/to/checkout`.
On Windows, use `./setup.ps1 -LauncherOnly` and optionally `-BinDir`; its default
is `%LOCALAPPDATA%\Programs\zellij-config\bin`. Rerun the command after updating
the checkout to refresh the installed helper copies. Use `--dry-run` / `-DryRun`
to preview without writing files.

From Fish, installing the helpers and adding their default directory is:

```fish
./setup.sh --launcher-only
fish_add_path "$HOME/.local/bin"
zj attach --create main
```

Use your chosen directory with `fish_add_path` when passing `--bin-dir`.

## Downloads and offline fallback

At startup, `zj` selects plugins in this order:

1. A previously downloaded file that still matches the pinned SHA-256.
2. An HTTPS download of the pinned release, verified before use.
3. The bundled backup, verified against the same hash, if downloading fails.

A bad checksum, timeout or missing release triggers the verified backup. If
neither source is valid, startup fails with a diagnostic instead of running
unverified bytes. Missing downloads run concurrently (at most three), with size,
socket and elapsed-time limits. After a failed download, that plugin uses its
verified backup for five minutes before retrying. A changed pin bypasses this
cooldown, as does a missing or corrupt backup. Unchanged backup snapshots are
reused without rewriting them.

Periodic release checks run in a detached background worker, so they cannot hold
up terminal startup. Results are cached per config and pinset; any update or
incomplete-check notice appears once on a later launch. Complete checks wait
30 days and incomplete checks retry after one day. For an immediate live check:

```sh
zj --check-updates
```

`ZJ_NO_UPDATE_CHECK=1` disables automatic update workers/notices while keeping
plugin downloads and fallback enabled. Cold startup can still wait for the
parallel plugin downloads; a verified download cache avoids that work.

For a deliberately disconnected system, skip all startup network requests:

```sh
ZJ_OFFLINE=1 "$HOME/.config/zellij/launcher/zj" attach --create main
```

```powershell
$env:ZJ_OFFLINE = '1'
& "$env:APPDATA\Zellij\config\launcher\zj.ps1" attach --create main
```

Keep the entire checkout, including `plugins/`, when copying to an air-gapped
machine. Downloads and generated runtime configs live in private per-user state,
not in the checkout. Plugin preparation does not change tracked files. Each
startup uses a snapshot of `config.kdl`; restart a session to apply source edits
or a `git pull` when using `zj`. Old runtime generations remain available to
running sessions. Plain Zellij can watch the root config directly.

## Choose when to upgrade

Versions are pinned in [VERSIONS.md](VERSIONS.md). From the checkout:

```sh
python3 tools/manage.py versions check
python3 tools/manage.py versions update --all
# Or select a component/tag explicitly:
python3 tools/manage.py versions update --plugin zjstatus=latest
python3 tools/manage.py versions update --zellij v0.45.1
```

The updater verifies selected plugin artifacts and licenses and synchronizes
root `config.kdl`, backup binaries, pins and generated references. Review the
diff and run checks before committing. A direct checkout is the live source;
`git pull` and version updates change it immediately. New `zj` sessions use those
changes. The Zellij executable changes only through an explicit installation:

```sh
python3 tools/manage.py install-zellij --bin-dir ~/.local/bin
```

On Windows use `python` and choose a binary directory on PATH. Updating helper
copies installed by an older setup requires rerunning that optional installation;
the checked-in launcher always uses the helper code from its own checkout.

## Optional deployment to a separate directory

A separate checkout can still deploy a verified copy with private backups:

```sh
./setup.sh --dry-run
./setup.sh                       # Downloads first, bundled fallback on failure
./setup.sh --offline             # Bundled files only; no downloads
./setup.sh --restore
```

Windows equivalents are `./setup.ps1`, `-DryRun`, `-Offline` and `-Restore`.
Setup requires Python 3.10+ and an installed Zellij executable. It validates
plugins, config and layouts before activation. It refuses to replace its own
checkout; a directly cloned config needs no deployment.

Setup installs launchers in `~/.local/bin` on Unix or
`%LOCALAPPDATA%\Programs\zellij-config\bin` on Windows. Use `--bin-dir` / `-BinDir`
to override that, or `--no-launcher` / `-NoLauncher` for config only.

Publication uses reversible directory renames, a per-target lock, private
snapshots and an interruption recovery journal. It has a short name gap and is
not a power-loss durability guarantee. Managed symlinks are materialized without
writing external dotfiles; snapshots retain the original links. See the
[configuration and recovery guide](docs/CONFIGURATION.md).

## Validate and contribute

```sh
./check.sh
python3 -m unittest discover -s tests -v
git config core.hooksPath hooks
zellij setup --check
```

Full repository validation requires Zellij. `./check.sh --static` explicitly
omits its parser checks. CI tests direct clones, optional deployment and native
entry points on Linux, macOS and Windows. Network-dependent checks run separately.

See the [configuration guide](docs/CONFIGURATION.md), printable
[cheatsheets](cheatsheets/), [audit resolution map](docs/AUDIT_FIXES.md) and
[third-party notices](THIRD_PARTY_NOTICES.md).
