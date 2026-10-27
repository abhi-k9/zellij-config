# Zellij config

Catppuccin Mocha, four layouts, matching swap layouts and three pinned plugins.
The repository root is a Zellij config directory: `config.kdl`, `layouts/`,
`themes/` and backup `plugins/` are ready to use after cloning.

## Clone directly and start

Install Git, Zellij and Python 3.10+. Choose an **absent or empty** destination;
move an existing config or nested checkout aside before cloning. Git will not
merge a clone into a nonempty directory.

Linux and macOS (this location takes precedence when present):

```sh
git clone https://github.com/abhi-k9/zellij-config.git "$HOME/.config/zellij"
"$HOME/.config/zellij/launcher/zj" -s project -n default
```

Native Windows, using Windows PowerShell 5.1+:

```powershell
git clone https://github.com/abhi-k9/zellij-config.git "$env:APPDATA\Zellij\config"
& "$env:APPDATA\Zellij\config\launcher\zj.cmd" -s project -n default
```

The Windows CMD launcher also works from PowerShell without changing its script
execution policy. The `launcher\zj.ps1` alternative requires a policy that allows
PowerShell scripts. WSL uses the Linux paths
inside WSL. No setup script or launcher installation is required. For a custom
checkout location, pass `--config-dir /path/to/checkout` to the launcher.

The shared defaults create independent sessions, keep Zellij's `Ctrl+g` lock
toggle, leave pane environments alone, and use a UTC clock without a Git widget
in the optional zjstatus layout. The `main` and `shell` names are tabs, not a
forced session name. Choose `minimal` for a single shell with a compact bar.

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

```powershell
zj.cmd -s project -n default
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
On Windows, run `python tools/manage.py install --launcher-only` from the source
checkout, optionally with `--bin-dir`. Its default is
`%LOCALAPPDATA%\Programs\zellij-config\bin`. The PowerShell equivalent is
`./setup.ps1 -LauncherOnly` with optional `-BinDir`, where scripts are allowed.
Rerun the command after updating
the checkout to refresh the installed helper copies. Use `--dry-run` / `-DryRun`
to preview without writing files.

From Fish, installing the helpers and adding their default directory is:

```fish
./setup.sh --launcher-only
fish_add_path "$HOME/.local/bin"
zj -s project -n default
```

Use your chosen directory with `fish_add_path` when passing `--bin-dir`.

### Windows PowerShell says scripts are disabled

If `zj` fails with `zj.ps1 cannot be loaded because running scripts is disabled`,
PowerShell is selecting the `.ps1` wrapper. Select the bundled CMD launcher
explicitly instead:

```powershell
zj.cmd
# Or choose a named session:
zj.cmd attach --create main
```

Both launchers run the same Python helper. This works for checked-in launchers
and standalone helpers installed in a custom `bin` directory. To keep typing
`zj` in the current PowerShell session:

```powershell
Set-Alias -Name zj -Value zj.cmd
```

The alias lasts only for that session. No administrator access or execution-policy
change is needed. If `setup.ps1` is also blocked, run
`python tools/manage.py install --launcher-only` from the full source checkout;
use the shared CLI options such as `--bin-dir` and `--dry-run`.

## Personal preferences

From the checkout, preview or save choices for its config directory:

```sh
python3 tools/manage.py configure --config-dir . --timezone Europe/Paris --dry-run
python3 tools/manage.py configure --config-dir . --timezone Europe/Paris --layout dev
./launcher/zj --config-dir . -s project -n dev
```

`configure` saves choices in the gitignored `.zellij-config-local.json`. It leaves
shared KDL and plugin pins unchanged. `zj` applies those choices to private
config/layout snapshots for new sessions. Plain `zellij` reads KDL directly and
does not read this JSON. Use `python` in place of `python3` on Windows.

To restore the previous singleton-session workflow, F12 lock key, Denver clock,
Git widget and pane debug export, opt into the compatibility preset:

```sh
python3 tools/manage.py configure --config-dir . --profile classic
./launcher/zj --config-dir . attach --create main
```

`--project-sessions` clears the fixed session name and automatic attachment.
`--reset` removes the local preferences file. Both support `--dry-run`.
Individual options preserve existing choices; switching profiles keeps explicit
overrides. Use `--reset` first to discard those overrides.
See the [preference options and migration checklist](docs/GENERALIZATION.md).

### Executable and state overrides

| Variable | Purpose |
| --- | --- |
| `ZJ_PYTHON` | Literal Python 3.10+ interpreter path for the shell/Windows wrappers |
| `ZJ_ZELLIJ_BIN` | Literal Zellij executable path, shared by launch, setup and full checks |
| `ZJ_STATE_DIR` | Directory for private launcher runtime files and update-check state |

These executable overrides accept a path without command arguments. They are
useful for virtual environments, multiple installed versions, and Windows Python
aliases. Otherwise Unix tries `python3` then `python`; Windows uses `py -3`/`python`
discovery, and Zellij is found on PATH. Run checked-in scripts from their real
location or install helpers with `--launcher-only`; external symlink entry
points are unsupported.

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
ZJ_OFFLINE=1 "$HOME/.config/zellij/launcher/zj" -s project -n default
```

```powershell
$env:ZJ_OFFLINE = '1'
& "$env:APPDATA\Zellij\config\launcher\zj.cmd" -s project -n default
```

Keep the entire checkout, including `plugins/`, when copying to an air-gapped
machine. Downloads and generated runtime configs live in private per-user state,
not in the checkout. Plugin preparation does not change tracked files. Each
startup uses a snapshot of `config.kdl`; restart a session to apply source edits
or local preference changes when using `zj`. Old runtime generations remain available to
running sessions. Plain Zellij can watch the root config directly.

`ZJ_OFFLINE` and `ZJ_NO_UPDATE_CHECK` are enabled by any nonempty value,
including `0`; unset them or use an empty value to disable them.

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
If scripts are disabled, use `python tools/manage.py install` from the source
checkout with `--dry-run`, `--offline` or `--restore` instead; see the
[PowerShell workaround](#windows-powershell-says-scripts-are-disabled).
Setup requires Python 3.10+ and an installed Zellij executable. It validates
plugins, config and layouts before activation. It refuses to replace its own
checkout; a directly cloned config needs no deployment.

Deployment keeps the target directory's local preferences and revalidates them
against the updated config. It does not import the source checkout's preferences
or bake choices into deployed KDL. Use `zj` for local preferences with either a
direct checkout or a deployed copy; plain `zellij` always ignores the JSON.

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
./check.sh --updates                 # Optional live release check
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
