# Zellij configuration guide

The config targets the version selected in [VERSIONS.md](../VERSIONS.md).
Catppuccin Mocha is built into Zellij; the custom theme file is an optional
template. Files use **KDL v1**, not KDL v2. Inline blocks need semicolons:
`pane { name "shell"; }`.

## Installation and updates

Clone directly into the chosen config directory and start the checked-in
`launcher/zj` (Unix) or `launcher/zj.cmd` (Windows, including PowerShell), as shown
in the [root guide](../README.md). No setup step is needed. Python 3.10+ is
required for the launcher/helpers. Plain Zellij can use the root config with
HTTPS aliases; the launcher implements automatic bundled fallback.

If PowerShell reports that `zj.ps1` cannot be loaded because running scripts is
disabled, run `zj.cmd` explicitly. PowerShell can select `.ps1` when you type
bare `zj`; the CMD wrapper runs the same Python helper without an execution-policy
change. For the current session, `Set-Alias -Name zj -Value zj.cmd` keeps the short
command. This alias does not survive closing PowerShell or opening a new terminal.
Putting it in `$PROFILE` normally persists it, but that profile is itself a script
subject to execution policy. With scripts disabled, keep using `zj.cmd` in new
sessions. If `setup.ps1` is blocked, use
`python tools/manage.py install --launcher-only` from the full source checkout,
or `python tools/manage.py install` for a separate deployment. See the
[Windows PowerShell workaround](../README.md#windows-powershell-says-scripts-are-disabled).

The repository root contains `config.kdl`, `layouts/`, `themes/` and backup
`plugins/`. `versions.json` selects the pinned artifacts; `plugins.sha256` and
`VERSIONS.md` are generated references. `docs/` contains documentation only.

The launcher first reuses a verified prior download, then attempts the pinned
HTTPS release, then verifies and uses the bundled backup if fetching fails.
Download/cache checksum errors cannot select unverified bytes. `ZJ_OFFLINE=1`
skips startup network access and uses a verified download cache or bundled files.
Private per-user config/layout snapshots leave the checkout untouched; restart a
session to apply source config edits or local preferences when using `zj`.
Missing downloads run concurrently, with at most three requests in flight.
Failed downloads have a five-minute per-pin cooldown, during which backups are
still hash-verified. Changed pins and unusable backups bypass the cooldown.
Unchanged backup snapshots are reused without rewriting their files.

To change versions when you choose:

```sh
python3 tools/manage.py versions check
python3 tools/manage.py versions update --all
python3 tools/manage.py versions update --plugin monocle=latest
python3 tools/manage.py versions update --zellij latest
./check.sh
```

Review the diff and install the selected Zellij executable if needed. A directly
cloned checkout needs no reinstall. For a separately deployed copy, run setup
again. The updater keeps pins, plugin bytes, notices and generated references
together and refuses a new artifact without a published or independently supplied
digest. Changed license terms require review.

## Config directory selection

`ZELLIJ_CONFIG_DIR` or the installer's `--config-dir` selects an explicit target.
Otherwise Unix uses an existing `~/.config/zellij` first. Linux then uses
`${XDG_CONFIG_HOME:-~/.config}/zellij`; macOS also recognizes the existing legacy
`~/Library/Application Support/org.Zellij-Contributors.Zellij` directory. Fresh
macOS installs use `~/.config/zellij`. Windows uses `%APPDATA%\Zellij\config`.

For direct cloning, that platform-specific config directory is the repository
root. For example, Linux uses `~/.config/zellij/config.kdl` and native Windows
uses `%APPDATA%\Zellij\config\config.kdl`. Both place `layouts/`, `themes/`,
`plugins/` and `launcher/` beside `config.kdl`. There is no additional internal
`config/` folder. The Windows path's final `config` is still required as part of
its default directory. See the [directory tree and PATH examples](../README.md#where-the-clone-lives).

For optional setup deployment, source and destination must be separate. Relative paths and trailing separators
are normalized. Quotes, backslashes, spaces and Unicode are escaped correctly in
generated KDL. Paths containing control characters are rejected before mutation.
Use `--bin-dir` to choose the launcher directory or `--no-launcher` for config
only. PowerShell equivalents are `-ConfigDir`, `-BinDir` and `-NoLauncher`.

For a direct clone, `./setup.sh --launcher-only` installs just the `zj` helpers
into `~/.local/bin`, leaving the configuration untouched. Choose another location
with `--bin-dir /path/to/bin`, or preview with `--dry-run`. Python 3.10+ is needed
for installation; Zellij is needed when launching. Windows uses `-LauncherOnly`
and defaults to `%LOCALAPPDATA%\Programs\zellij-config\bin`.

Fish can execute `./setup.sh` and `zj` directly using their `#!/bin/sh`
interpreter line. Do not source these scripts or invoke them with `fish`.
Use `fish_add_path "$HOME/.local/bin"` after installing the helpers, or
`fish_add_path "$HOME/.config/zellij/launcher"` for the direct-clone launcher.

`ZJ_PYTHON` selects one literal Python interpreter path for every wrapper;
`ZJ_ZELLIJ_BIN` selects one literal Zellij executable path for launch, setup and
full checks. Neither accepts command arguments. Unix tries `python3` then
`python`; Windows uses `py -3`/`python`. An unusable
Windows Python alias can be bypassed with `ZJ_PYTHON`. `ZJ_STATE_DIR` overrides
the private launcher state directory; otherwise platform state conventions apply.
Use real script paths or installed helpers, since external symlink entry points
are unsupported.

## Local preferences

The shared config leaves session names and pane environment variables unset,
keeps the standard `Ctrl+g` lock toggle, and gives zjstatus a UTC clock without
command widgets. Save personal choices separately with:

```sh
python3 tools/manage.py configure --config-dir . --timezone Europe/Paris --layout dev
```

This creates a gitignored `.zellij-config-local.json` in the selected directory.
It changes no shared KDL or version pins. The launcher renders private snapshots
from preferences beside the selected config file for new sessions. Plain Zellij
does not read this JSON. Optional setup deployment preserves the target's local
file, revalidates it against the updated config, and ignores the source checkout's
preferences. Deployed KDL retains portable defaults; use `zj` to apply preferences
to either direct or deployed configs.

For the previous workflow, use `configure --config-dir . --profile classic`.
It restores session `main` with automatic attachment, F12 locking, Denver time,
the startup-directory Git widget, and `RUST_BACKTRACE=1` in panes. Individual
options can override the preset. `--project-sessions` clears the singleton
session choice, `--reset` removes the local file, and `--dry-run` previews without
writing. Individual options retain unspecified existing choices, including
explicit overrides when changing profiles. Running `configure --config-dir .`
without changes prints effective settings without writing. See the
[options and migration checklist](GENERALIZATION.md).

## Layouts

| Layout | Behavior |
| --- | --- |
| `default` | Two tabs: `main` for work/editor and `shell` as a safety net |
| `dev` | Editor, terminal and log-oriented development tabs |
| `zjstatus` | Optional rich status bar; read the comments about frames and permissions |
| `minimal` | One shell with a compact bar, without a separate safety tab |

Every layout has a matching `.swap.kdl`, enabling `Alt+[` and `Alt+]`.
Create a separate project session with `zellij -s project -n dev`.
`--session project --layout dev` adds tabs to an existing session. The shared
config has no forced session name; `classic` or an explicit local session name
can make a bare `--layout dev` attach to that configured session instead.

## Keybindings

Zellij's defaults remain active except for the explicit customizations:

| Key | Action |
| --- | --- |
| `Ctrl+g` | Standard lock/unlock toggle; locking forwards other keys to the focused application |
| `Ctrl+q` | Unbound to prevent accidental quits |
| `Ctrl+o`, then `q` | Quit deliberately |
| `Ctrl+o`, then `d` | Detach and leave the session running |
| `Ctrl+o`, then `m` | Open/focus the monocle file finder |
| `Ctrl+o`, then `h` | Open the built-in configuration/keybinding screen |

`configure --lock-key F12` opts into F12 locking and releases `Ctrl+g` to the
application. The `classic` preset selects that behavior too. There is no
application-specific automatic locking.

The former third-party keybinding popup was removed because its redistribution
permission was unestablished. The built-in screen uses Zellij's actual bindings.

### Ctrl keys print keyboard reports in a Windows console

If `Ctrl+o` prints `[111;5u` or `Ctrl+p` prints `[112;5u` and the status bar does
not change mode, first check that Zellij shows **NORMAL**, not **LOCKED**. Unlock
with `Ctrl+g` for portable defaults, or `F12` for the classic local profile.
Locked mode forwards these keys to the application.

These strings resemble CSI-u keyboard reports. In the reported setup, the same
config works when PowerShell runs inside **Windows Terminal**, while the older
console window opened by **Windows PowerShell** prints the reports. PowerShell
is the shell; Windows Terminal is the terminal host. Open Windows Terminal and
choose its Windows PowerShell or PowerShell profile. This does not require
changing PowerShell's execution policy, Zellij keybindings or global settings.

From the full checkout, confirm the executable version in that terminal:

```powershell
if ($env:ZJ_ZELLIJ_BIN) { & $env:ZJ_ZELLIJ_BIN --version } else { zellij --version }
```

Start a fresh test session with an unused name:

```powershell
.\launcher\zj.cmd --config-dir . -s keyboard-test -n minimal
```

In NORMAL mode, press `Ctrl+o`, then `Esc`; press `Ctrl+p`, then `Esc`. The status
bar should enter Session and Pane mode respectively, without printing the
reports into the shell. Use `zj.cmd` again in new PowerShell windows: the
`Set-Alias` workaround above lasts only for the session where it was created.

Record the terminal host, actual Zellij version, and whether the executable is
native Windows or runs inside WSL when comparing results. WSL uses its Linux
executable, config paths and Unix launcher. Upstream has a similar
[Windows Ctrl-key report](https://github.com/zellij-org/zellij/issues/5017);
the [0.45.1 Windows input implementation](https://github.com/zellij-org/zellij/blob/v0.45.1/zellij-client/src/os_input_output_windows.rs#L12-L34)
shows the platform-specific detection used for its input path.

## Plugins and permissions

The three third-party aliases are `zjstatus`, `monocle` and `multitask`. Their
versions, URLs and hashes are listed once in [VERSIONS.md](../VERSIONS.md).
They load on demand rather than in a background `load_plugins` block.

The checked-in aliases use HTTPS. The launcher generates private config snapshots
with verified file locations and retains source pins for update checks. Optional
setup deployment records upstream pins in an installed versions ledger.
Plugin permissions are granted by Zellij, not by the installer. Grant only the
permissions needed for the features you intend to use. `RunCommands` permits
host commands; WASM is not a reason to grant it indiscriminately.

The optional zjstatus layout uses state access for its bar. Its one-row permission
prompt can be truncated: click the bar to focus it before responding. Set
`pane_frames false` or toggle frames for that session with `Ctrl+p`, then `z` to
avoid competing frame management. The clock defaults to UTC. Use
`configure --timezone Europe/Paris` for another IANA timezone; see the
[timezone dependency note](GENERALIZATION.md#timezones-and-optional-commands).

The Git widget is an explicit `configure --git-status on` opt-in, also selected
by `classic`. It requires Git on PATH and command-execution permission. Its
directory is the layout's startup directory, not the focused pane; changing
panes does not retarget it. No editor, log viewer or native clipboard command is
launched by default; platform-specific command examples remain opt-ins.

## Update notices

`zj` forwards arguments literally to Zellij and periodically checks the selected
config's pins. `--config`, `-c`, `--config-dir` and their environment equivalents
are respected. Checks are cached separately for each config and pinset: a
complete scan waits 30 days, and an incomplete scan retries after one day.
Known updates are still shown when a later request fails.
Automatic requests run in a detached worker with no terminal handles; startup
reads only cached results and schedules work when due. A notice is displayed once
on a later launch after the worker finishes. Rapid launches share a reservation;
if a worker crashes, scheduling can retry after ten minutes. Workers never change
pins or the configuration. Explicit checks below run live in the foreground.

```sh
zj --check-updates
zj --check-updates /path/to/config.kdl
./check.sh --updates /path/to/config.kdl
```

Exit status is 0 for current pins, 1 for a different latest release, and 2 for an
incomplete/unavailable check. A different tag is not necessarily newer. No check
changes files or interrupts startup for confirmation. `ZJ_NO_UPDATE_CHECK=1`
skips startup notices; `ZJ_OFFLINE=1` also skips plugin downloads. Both Windows wrappers use this same logic; tags and URLs
are compared case-sensitively. Requests follow bounded HTTPS redirects with
timeouts; ordinary CI tests use deterministic fixtures instead of live releases.
These two environment switches treat every nonempty value, including `0`, as
enabled. Unset the variable or set an empty value to disable it.

## Recovery and backups

For a direct checkout, use Git history to review and revert tracked config changes.
The optional setup installer provides the restore mode described in the
[root guide](../README.md) for separately deployed copies.
New snapshots contain `snapshot.json` metadata and the original `tree/` inside a
private directory. Creation order comes from numeric metadata, independent of
lexical filename ordering. Legacy `zellij.backup-YYYYMMDD-HHMMSS[-N]` snapshots
are also readable, with numeric suffix ordering.

Setup replaces the entire staged target on restore, so stale dotfiles, including
names beginning with two dots, do not survive. Private staging names are unique
and only owned resources are cleaned up. Dry runs create no lock, staging,
backup, network request or cleanup trap. Never delete a recovery journal or
snapshot while an installer is running.

## Session recovery, clipboard and terminal behavior

`session_serialization true` saves the session structure once per minute.
`serialize_pane_viewport false` keeps restored screens clean; the similarly
named `pane_viewport_serialization` is not the parser key. Use
`zj attach --create project` with your actual session name after a crash/reboot.
Plain `zellij` can create a
fresh session instead of resurrecting the saved one.

Restored applications may have no shell beneath them; the extra `shell` tab
helps keep the session alive after an editor exits. This is not a substitute for
an editor session plugin or backups of unsaved work. Verify crash/reboot recovery
in your own environment rather than inferring it from config parser success.
The `minimal` layout has one tab and does not provide the extra safety shell.

Clipboard copy defaults to OSC52 so it can work through SSH. Terminal support
still matters; the commented `pbcopy`, `wl-copy`, `xclip` and `clip.exe` examples
are platform-specific alternatives. Mouse, notifications, font glyphs and
clipboard behavior need the [on-machine checklist](../cheatsheets/verification-checklist.html).

## Validation and debugging

Full `./check.sh` requires Zellij and checks the required file inventory, active
KDL pins, exact bundled hashes, license notices, generated references, HTML
structure and Python syntax. It then parses the actual config, all layout/swap
pairs and example theme. `--static` explicitly omits the real-binary phase.
Read/checksum errors fail validation. The staged git hook also fails if its
checker is missing and prints the actual diagnostic output.

```sh
zellij --config-dir . setup --check
zellij --config-dir . --layout dev setup --check
python3 -m unittest discover -s tests -v
```

Zellij can silently ignore unknown option names, so parser success is not proof
that an arbitrary new option works. Compare it with the version's official
options/source. Likewise, parsing does not prove interactive recovery, permission
prompts or terminal rendering. See [the audit resolution map](../docs/AUDIT_FIXES.md)
for executable regressions and the remaining native/interactive boundaries.
