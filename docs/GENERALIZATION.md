# Portable defaults and local preferences

The shared files provide independent sessions, Zellij's standard `Ctrl+g` lock
toggle, no pane debug export, and a UTC zjstatus clock with no Git command.
Application commands in commented examples remain opt-ins. The default layout
still has `main` and `shell` tabs; these names do not force a session called
`main`. The `minimal` layout has a single shell and compact bar.

## Save choices outside shared KDL

Run from the checkout, using `python` instead of `python3` on Windows and
`.\launcher\zj.cmd` for launcher examples. If bare `zj` selects a policy-blocked
PowerShell script, use the [CMD workaround](../README.md#windows-powershell-says-scripts-are-disabled).

```sh
python3 tools/manage.py configure --config-dir . --profile portable --dry-run
python3 tools/manage.py configure --config-dir . --timezone Europe/Paris --layout zjstatus
./launcher/zj --config-dir . -s project -n zjstatus
```

`configure` saves preferences in `.zellij-config-local.json` in the chosen config
directory. This gitignored file uses schema version 1; unknown fields and invalid
values are rejected. A missing file selects shared defaults. CLI options are
optional, and explicit preferences override the selected preset.
Changing one option preserves unspecified existing choices. Switching profiles
also preserves explicit overrides; use `--reset` first to discard them. Running
`configure --config-dir DIRECTORY` without preference options prints effective
settings without writing. `--project-sessions` cannot be combined with
`--session-name` or `--attach-to-session`; `--reset` cannot be combined with
preference changes.

`zj` renders private config and layout snapshots for each new session. Source
files and version pins stay unchanged; already running sessions retain their
snapshots. Plain `zellij` reads KDL directly and always ignores local JSON. Setup
for a separate deployed directory preserves that target's preferences and
validates a rendered temporary copy, without baking choices into deployed KDL
or copying preferences from the source checkout. `zj` applies the target's JSON
on startup; `--reset` restores shared defaults for the next new session.

Preferences are read beside the selected config file. Explicit config-directory
selection can still supply separate layouts/themes. The launcher snapshots
layout pairs and keeps theme lookup in the selected resource directory. An
explicit layout file path is outside these layout preference overrides, including
paths to shipped files. Use a named layout such as `--layout zjstatus` to apply
the rendered timezone and Git settings.

| Option | Choice |
| --- | --- |
| `--config-dir DIRECTORY` | Select the config directory containing the local file |
| `--profile portable` | Independent sessions, `Ctrl+g`, UTC, no Git/debug export |
| `--profile classic` | Session `main` with autoattach, F12, Denver, Git widget and debug export |
| `--timezone ZONE` | IANA clock timezone, such as `Europe/Paris` or `Etc/UTC` |
| `--git-status on/off` | Enable/disable the startup-directory Git widget |
| `--layout NAME` | `default`, `dev`, `zjstatus` or `minimal` |
| `--session-name NAME` | Choose a fixed session name |
| `--attach-to-session on/off` | Enable/disable automatic attachment to that session |
| `--project-sessions` | Clear the fixed session name and automatic attachment |
| `--rust-backtrace on/off` | Enable/disable the `RUST_BACKTRACE=1` pane export |
| `--lock-key "Ctrl g"` or `--lock-key F12` | Select the lock toggle |
| `--theme NAME` | Select a Zellij theme; default is `catppuccin-mocha` |
| `--pane-frames on/off` | Select pane frames; defaults off for a selected zjstatus layout |
| `--dry-run` | Preview without writing |
| `--reset` | Remove the local file and return to shared defaults |

For example, keep the previous workflow but choose a different clock:

```sh
python3 tools/manage.py configure --config-dir . --profile classic --timezone Europe/Paris
./launcher/zj --config-dir . attach --create main
```

## Executables and paths

Config directories still follow Zellij's platform conventions. Explicit
`--config`, `--config-dir`, `ZELLIJ_CONFIG_FILE` and `ZELLIJ_CONFIG_DIR` selectors
retain their roles; see [directory selection](CONFIGURATION.md#config-directory-selection).

`ZJ_PYTHON` accepts one Python 3.10+ interpreter path, without arguments.
`ZJ_ZELLIJ_BIN` accepts one Zellij executable path and is shared by launch,
setup and full validation. `ZJ_STATE_DIR` selects the private launcher runtime
and update-state directory. These overrides support paths with spaces. Otherwise
the wrappers try Unix `python3` then `python`, or Windows `py -3`/`python`, with
Zellij on PATH. Invoke real script paths or install helpers with
`--launcher-only`; external symlink entry points are unsupported.

Default launcher state lives under `${XDG_STATE_HOME:-~/.local/state}/zellij-config`
on Unix or `%LOCALAPPDATA%\zellij-config` on Windows.

`ZJ_OFFLINE` and `ZJ_NO_UPDATE_CHECK` keep their existing semantics: every
nonempty value, including `0`, enables them. Unset them or use an empty value
to turn them off. `./check.sh --updates [CONFIG_FILE]` performs an explicit live
release check; ordinary checks remain deterministic and use the selected pins.

On native Windows, use PowerShell inside Windows Terminal if the older console
host prints `[111;5u`/`[112;5u` for `Ctrl+o`/`Ctrl+p` without changing Zellij's
mode. Confirm NORMAL rather than LOCKED first; portable unlocks with `Ctrl+g`,
classic with `F12`. PowerShell is the shell, and Windows Terminal supplies the
terminal host. See the [keyboard checks](CONFIGURATION.md#ctrl-keys-print-keyboard-reports-in-a-windows-console)
for a fresh-session test and actual executable-version check. The reported setup
works in Windows Terminal without preference or global keyboard-setting changes.

## Timezones and optional commands

UTC and the `classic` Denver zone work without an extra Python package. Other
explicit IANA zones are validated using Python's `zoneinfo` database. Unix
usually supplies it through the OS; Windows may need the optional `tzdata`
package installed into the selected interpreter. An unavailable zone produces a
diagnostic rather than silently selecting a different clock.

The Git widget requires Git on PATH and Zellij command-execution permission.
If Git is missing, `zj` disables the widget for that launch with a diagnostic;
the saved preference stays unchanged.
It observes the layout's startup directory, not the focused pane. It is disabled
by default; `--git-status on` or `classic` opts in. Editor, log viewer, clipboard
and shell examples require the applications and shell syntax you choose to
enable. The shared config does not install or auto-select those applications.

The `theme` preference selects Zellij's theme. The optional zjstatus layout keeps
its own Mocha palette; changing the Zellij theme does not recolor that palette.

Plugin pins remain zjstatus `v0.25.0`, monocle `v0.100.2`, and multitask `v0.45.1`.
They were checked against current stable releases and freshly downloaded bytes;
no version or checksum changes were needed. See [VERSIONS.md](../VERSIONS.md).

## Migration and validation checklist

1. Inspect local edits before pulling. Keep personal KDL edits until the desired
   choices are represented by local preferences.
2. Preview `configure --config-dir DIRECTORY --profile classic --dry-run` if
   preserving the old workflow, or choose individual portable preferences.
3. Save the choices, then start a new named `zj` session with an explicit layout.
   Reattach to existing sessions by their actual names; do not infer the session
   name from a tab called `main`.
4. Run `./check.sh` and `python3 -m unittest discover -s tests -v` with the
   selected Zellij executable. `./check.sh --static` omits real-binary parsing.
5. For a separate deployment, preview and rerun setup against that target. Check
   that its own preferences survive, then exercise restore in a scratch target.
6. On the target terminal, check lock/unlock, clipboard locally and over SSH,
   fonts, permissions, Git cwd, timezone, detach/reattach and recovery. Test the
   single-tab exit behavior when choosing `minimal`.

Native CI covers Linux/macOS/Windows helpers and parser regressions. It does not
establish interactive clipboard, font, permission or crash/reboot behavior; use
the [on-machine checklist](../cheatsheets/verification-checklist.html).
