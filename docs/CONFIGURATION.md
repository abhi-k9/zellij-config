# Zellij configuration guide

The config targets the version selected in [VERSIONS.md](../VERSIONS.md).
Catppuccin Mocha is built into Zellij; the custom theme file is an optional
template. Files use **KDL v1**, not KDL v2. Inline blocks need semicolons:
`pane { name "shell"; }`.

## Installation and updates

Clone directly into the chosen config directory and start the checked-in
`launcher/zj` (Unix) or `launcher/zj.ps1` / `launcher/zj.cmd` (Windows), as shown
in the [root guide](../README.md). No setup step is needed. Python 3.10+ is
required for the launcher/helpers. Plain Zellij can use the root config with
HTTPS aliases; the launcher implements automatic bundled fallback.

The repository root contains `config.kdl`, `layouts/`, `themes/` and backup
`plugins/`. `versions.json` selects the pinned artifacts; `plugins.sha256` and
`VERSIONS.md` are generated references. `docs/` contains documentation only.

The launcher first reuses a verified prior download, then attempts the pinned
HTTPS release, then verifies and uses the bundled backup if fetching fails.
Download/cache checksum errors cannot select unverified bytes. `ZJ_OFFLINE=1`
skips startup network access and uses a verified download cache or bundled files.
Private per-user runtime snapshots leave the checkout untouched; restart a
session to apply source config edits when using `zj`.

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

For optional setup deployment, source and destination must be separate. Relative paths and trailing separators
are normalized. Quotes, backslashes, spaces and Unicode are escaped correctly in
generated KDL. Paths containing control characters are rejected before mutation.
Use `--bin-dir` to choose the launcher directory or `--no-launcher` for config
only. PowerShell equivalents are `-ConfigDir`, `-BinDir` and `-NoLauncher`.

## Layouts

| Layout | Behavior |
| --- | --- |
| `default` | Two tabs: `main` for work/editor and `shell` as a safety net |
| `dev` | Editor, terminal and log-oriented development tabs |
| `zjstatus` | Optional rich status bar; read the comments about frames and permissions |

Every layout has a matching `.swap.kdl`, enabling `Alt+[` and `Alt+]`.
Create a separate project session with `zellij -s project -n dev`.
`--session project --layout dev` adds tabs to an existing session; a bare
`--layout dev` may join the configured `main` session instead.

## Keybindings

Zellij's defaults remain active except for the explicit customizations:

| Key | Action |
| --- | --- |
| `F12` | Lock/unlock; locking forwards keys to the focused application |
| `Ctrl+g` | Unbound in normal and locked contexts; applications can receive it |
| `Ctrl+q` | Unbound to prevent accidental quits |
| `Ctrl+o`, then `q` | Quit deliberately |
| `Ctrl+o`, then `d` | Detach and leave the session running |
| `Ctrl+o`, then `m` | Open/focus the monocle file finder |
| `Ctrl+o`, then `h` | Open the built-in configuration/keybinding screen |

The former third-party keybinding popup was removed because its redistribution
permission was unestablished. The built-in screen uses Zellij's actual bindings.
Commented `Ctrl+o t` and `Ctrl+o e` examples remain Unix-only opt-ins. Read their
comments before enabling them: the multitask configuration uses comma-separated
values, and editor command strings with extra arguments need a wrapper.

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

The optional zjstatus layout requests state access and command execution for its
git widget. Its one-row permission prompt can be truncated: click the bar to
focus it before responding. Remove the `command_git_branch_*` settings if you do
not want that widget. Set `pane_frames false` or toggle frames for that session
with `Ctrl+p`, then `z` to avoid competing frame management. Its git directory is
the startup directory, not the focused pane. Its clock uses the explicit IANA
timezone in the layout; set it to your own timezone.

## Update notices

`zj` forwards arguments literally to Zellij and periodically checks the selected
config's pins. `--config`, `-c`, `--config-dir` and their environment equivalents
are respected. Checks are cached separately for each config and pinset: a
complete scan waits 30 days, and an incomplete scan retries after one day.
Known updates are still shown when a later request fails.

```sh
zj --check-updates
zj --check-updates /path/to/config.kdl
```

Exit status is 0 for current pins, 1 for a different latest release, and 2 for an
incomplete/unavailable check. A different tag is not necessarily newer. No check
changes files or interrupts startup for confirmation. `ZJ_NO_UPDATE_CHECK=1`
skips startup notices; `ZJ_OFFLINE=1` also skips plugin downloads. Both Windows wrappers use this same logic; tags and URLs
are compared case-sensitively. Requests follow bounded HTTPS redirects with
timeouts; ordinary CI tests use deterministic fixtures instead of live releases.

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
`zellij attach --create main` after a crash/reboot. Plain `zellij` can create a
fresh session instead of resurrecting the saved one.

Restored applications may have no shell beneath them; the extra `shell` tab
helps keep the session alive after an editor exits. This is not a substitute for
an editor session plugin or backups of unsaved work. Verify crash/reboot recovery
in your own environment rather than inferring it from config parser success.

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
