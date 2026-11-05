# Quick start: everyday workflows

Start with a named workspace, run your own tools, then detach and return later.
These examples use the shared defaults and the Zellij version pinned in
[VERSIONS.md](../VERSIONS.md).

## First launch

Install Git, Zellij and Python 3.10+. Use an **absent or empty** clone destination;
move any existing configuration aside first. No setup script is needed.

Linux, macOS or WSL (run inside WSL for its Linux configuration):

```sh
git clone https://github.com/abhi-k9/zellij-config.git "$HOME/.config/zellij"
"$HOME/.config/zellij/launcher/zj" -s first -n default
```

Native Windows: open **Windows Terminal**, select its PowerShell profile, then:

```powershell
git clone https://github.com/abhi-k9/zellij-config.git "$env:APPDATA\Zellij\config"
& "$env:APPDATA\Zellij\config\launcher\zj.cmd" -s first -n default
```

You should see `main` and `shell` tabs. Both contain shells; start your editor or
other commands yourself. Press **Ctrl+o, then d** to detach before continuing in
your original terminal.

Add the checkout's `launcher` directory to PATH for the daily commands below.
For Bash/Zsh, add `export PATH="$HOME/.config/zellij/launcher:$PATH"` to your shell
startup file; for Fish, run `fish_add_path "$HOME/.config/zellij/launcher"` once.
On Windows, add `%APPDATA%\Zellij\config\launcher` to your **user Path**. Open a
new terminal afterward. The [PATH instructions](../README.md#make-the-short-zj-command-available)
also cover standalone helper installation.

Use **`zj.cmd` instead of `zj` in every Windows example below**. It works with
PowerShell scripts disabled. A `Set-Alias` shortcut lasts only in its current
PowerShell session; adding the directory to user Path persists across restarts.

If your checkout is elsewhere, pass `--config-dir /path/to/checkout` on each
launch, even when invoking that checkout's launcher directly.

## Work on a project

In your terminal, change to your actual project directory before starting.
For example, replace the path and choose an unused session name:

```sh
cd /path/to/your/project
zj -s myproject -n dev
```

In PowerShell, use `Set-Location C:\path\to\your\project` and
`zj.cmd -s myproject -n dev` instead. New layout panes inherit the launch directory.

The `dev` layout opens `code`, `git` and `logs` tabs. Run your editor in the large
`code` pane, builds/tests in its smaller shell, Git commands in `git`, and your
own log/watch command in `logs`. No editor, Git interface or log watcher starts
automatically.

Choose the layout when **creating** a workspace with `-s NAME -n LAYOUT`:

| Layout | Good for |
| --- | --- |
| `default` | General work: `main` and a separate `shell` tab, compact bar |
| `dev` | Development: `code`, `git` and `logs` tabs with shell panes |
| `minimal` | One shell with a compact bar: `zj -s scratch -n minimal` |
| `zjstatus` | Two tabs with a richer status bar; [save this preference](#save-personal-choices) to coordinate frames |

`--layout` / `-l` can add tabs to an existing session; use `-n` for a fresh named
workspace. Session names are independent of tab names.

## Keys you will use most

Press the Ctrl combination, release it, then press the next key. Start in NORMAL
mode. Press `Esc` to leave Pane or Tab mode when done.

| Task | Keys |
| --- | --- |
| Split right / below | `Ctrl+p`, then `r` / `d` |
| Focus another pane | `Ctrl+p`, then an arrow key |
| Toggle pane fullscreen | `Ctrl+p`, then `f` |
| Select tab 1, 2 or 3 | `Ctrl+t`, then `1`, `2` or `3` |
| Create a tab | `Ctrl+t`, then `n` |
| Mark/unmark a pane | `Alt+p` |
| Pass shortcuts through to your application | `F12` to lock; `F12` again to unlock |
| Open keybinding help | `Ctrl+o`, then `h` |
| Leave the workspace running | `Ctrl+o`, then `d` |

Both presets use **F12**, leaving Ctrl+g available to Neovim and other applications.
If your keyboard requires it, press Fn+F12. If Ctrl+o / Ctrl+p print
`[111;5u` / `[112;5u` on Windows, check NORMAL mode and use Windows Terminal;
see [keyboard troubleshooting](CONFIGURATION.md#ctrl-keys-print-keyboard-reports-in-a-windows-console).

## Close several panes

Mark the focused pane with **Alt+p**, move with **Alt+arrows**, then mark others
with Alt+p. You can also **Alt+left-click** panes to mark/unmark them.

The **Multiple Pane Select** overlay shows the selected count and group actions.
Review it, then press **c** to close those panes immediately, or **Esc**
to cancel and clear marks. Save work first: closing panes stops their programs.
This uses Zellij's built-in visual grouping; no extra picker plugin is needed.

## Return to your workspace

After detaching, or from another terminal on the same machine:

```sh
zj list-sessions
zj attach myproject
```

If a reattached nested session has a blank strip along its border, check for a
smaller client still attached inside its parent. See the
[nested-session recovery steps](TROUBLESHOOTING.md#blank-border-after-reattaching-a-nested-session).

Use `zj attach --create myproject` to attach, resurrect or create it as needed.
When no running or recoverable session exists, creation uses your configured
default layout; an earlier `-n dev` command does not change that default. Saved
sessions can retain their previous structure after a restart; see
[recovery limits](CONFIGURATION.md#session-recovery-clipboard-and-terminal-behavior).

To quit, save your work, then press **Ctrl+o, then q**. The **Quit Zellij?** dialog
requires `y`; `n` or `Esc` cancels, and Enter does not confirm. On first use, grant
its `ChangeApplicationState` permission, then answer the separate quit question.
The current client closes; the session and its programs stop only if no other
active clients remain. `Ctrl+q` is unbound. Detach with `Ctrl+o, d` when you want
programs to keep running. See the [confirmation guide](QUIT_CONFIRMATION.md).

## Save personal choices

For example, adopt the richer status bar with its UTC clock. Run from the config
checkout, then start a fresh session with an unused name:

```sh
cd "$HOME/.config/zellij"
python3 tools/manage.py configure --config-dir . --layout zjstatus --timezone UTC --dry-run
python3 tools/manage.py configure --config-dir . --layout zjstatus --timezone UTC
./launcher/zj --config-dir . -s status-demo
```

Windows equivalents, also from the checkout:

```powershell
Set-Location "$env:APPDATA\Zellij\config"
python tools/manage.py configure --config-dir . --layout zjstatus --timezone UTC --dry-run
python tools/manage.py configure --config-dir . --layout zjstatus --timezone UTC
.\launcher\zj.cmd --config-dir . -s status-demo
```

This saves gitignored `.zellij-config-local.json` and coordinates pane frames
for zjstatus. If its permission prompt is truncated, click the bar to focus it
before responding; grant only the permissions needed for your chosen features.
The Git widget stays off by default.

Preferences apply through `zj` to **new sessions**. Reattaching keeps the existing
session's settings, and plain `zellij` ignores the local JSON. This command
selects a complete preference preset plus overrides; see
[all choices](GENERALIZATION.md#save-choices-outside-shared-kdl), including other
timezones, the classic workflow and `--reset` to remove local preferences.

## Start without a network connection

Keep the entire checkout, including `plugins/`, and use a fresh session name:

```sh
ZJ_OFFLINE=1 zj -s offline-work -n default
```

```powershell
$env:ZJ_OFFLINE = '1'
zj.cmd -s offline-work -n default
# After detaching, restore normal networking in this PowerShell session:
Remove-Item Env:ZJ_OFFLINE
```

This uses verified bundled/cached plugins and skips startup update requests.
Zellij must already be installed, and the launcher still needs writable private
state. For updating the checkout, managing pins or deploying a separate copy,
see the [main guide](../README.md#choose-when-to-upgrade).
