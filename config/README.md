# Zellij Configuration

A sensible, well-commented zellij **0.45.1** config, themed with Catppuccin
Mocha and ready to extend. The config and layouts work on Linux, macOS and
Windows. The helper scripts are Unix tools: `setup.sh` targets Linux and macOS,
and `check.sh` and the git hook also run under Git Bash on Windows. Two opt-in
keybinds in `config.kdl` (`Ctrl+o t`, `Ctrl+o e`) are Unix-only too. The
exception is the `zj` launcher (zellij plus a monthly check for plugin updates),
which comes in both kinds: `launcher/zj` for Linux and macOS, from any shell
including fish, and `zj.cmd` + `zj.ps1` for Windows.

## What's in here

```text
config/
├── config.kdl                        # main configuration (commented; `// default` = zellij's own value)
├── README.md                         # this file
├── layouts/
│   ├── default.kdl                   # plain `zellij`: "main" + "shell" tabs
│   ├── dev.kdl                       # editor + terminal + log strip (3 tabs)
│   ├── zjstatus.kdl                  # opt-in rich status bar (see Plugin recommendations)
│   └── *.swap.kdl                    # pane arrangements for Alt+[ / Alt+] (one per layout)
└── themes/
    └── example-custom.kdl.example   # starter template for your own theme
                                      # (Catppuccin itself is built into zellij)

cheatsheets/                          # printable HTML references (open in a browser)
├── zellij-cheatsheet.html            # keybindings, CLI, layout & config reference
├── zellij-plugins-cheatsheet.html    # plugins + themes reference
├── kdl-syntax-cheatsheet.html        # KDL syntax — how to read/edit these files
└── verification-checklist.html       # on-machine checks (clipboard, mouse, crash recovery)

setup.sh                              # installer: ./setup.sh [--offline | --restore]
plugins/                              # the pinned plugin .wasm files, for offline installs
plugins.sha256                        # their checksums; setup.sh --offline verifies against them
launcher/                             # zj: starts zellij, checking monthly for plugin updates
├── zj                                # Linux/macOS (POSIX sh: works from fish, bash, zsh)
├── zj.cmd                            # Windows: the command you run
└── zj.ps1                            # Windows: the check itself (zj.cmd runs it when due)
check.sh                              # consistency linter — run before committing edits
hooks/pre-commit                      # optional git hook: runs check.sh on the staged files
.github/workflows/check.yml           # CI: all checks on Linux, portability on macOS, zj on Windows
.gitattributes                        # line endings: LF everywhere (even on Windows), CRLF for zj.cmd
.markdownlint.jsonc                   # Markdown lint settings used by CI
CHANGELOG.md                          # what's verified, what changed, bugs fixed
```

## Install

**What each OS needs.** Everything here uses tools the OS already has:

- **Linux and macOS:** `sh` for `setup.sh` and `zj`, and bash 3.2+ for
  `check.sh`. `zj`'s update check uses `curl` or `wget`, and `--offline`
  verifies files with `sha256sum`, `shasum` or `openssl`.
- **Windows:** Windows PowerShell 5.1, which is built in, for the install
  steps and `zj`. `check.sh` and the git hook are optional and run under Git
  Bash; `setup.sh` is Linux/macOS only, so Windows uses the PowerShell steps
  below.

### Unpack the archive

The archive has no top-level folder: `config/`, `setup.sh` and the rest sit at
its root. So unpack it **into a folder of its own**. (The commands here use
`28_zellij_audited_2026-10-14.zip`, or whatever you renamed the file to.)

```bash
# Linux / macOS
mkdir -p ~/src/zellij-config
unzip 28_zellij_audited_2026-10-14.zip -d ~/src/zellij-config
cd ~/src/zellij-config
```

```powershell
# Windows
Expand-Archive 28_zellij_audited_2026-10-14.zip "$HOME\src\zellij-config"
cd "$HOME\src\zellij-config"
```

No `unzip` (Arch-based distros such as CachyOS don't install it by default)?
`bsdtar -xf 28_zellij_audited_2026-10-14.zip -C ~/src/zellij-config` reads
zips too, and comes with pacman. Both keep the scripts executable. If another
tool drops that (`permission
denied` on `./setup.sh`), run `chmod +x setup.sh check.sh hooks/pre-commit
launcher/zj`, or start them as `sh ./setup.sh` and `bash ./check.sh`.

On Windows you can instead unpack straight into `%APPDATA%\Zellij`: there, the
archive's `config\` folder *is* zellij's config dir, so that one step installs
it. See [Using the archive in place](#using-the-archive-in-place).

### Install it

**Quickest — the installer (Linux/macOS):** from the unpacked archive, run

```bash
./setup.sh              # copies config.kdl, layouts/, themes/ into your zellij dir,
                        # and installs the zj launcher (see Checking for plugin updates)
./setup.sh --offline    # also installs the bundled plugins/ and points the
                        # config at them (file:) — for air-gapped machines
./setup.sh --restore    # undo: put the most recent backup back
```

It picks the config dir in the same order zellij searches:
`$ZELLIJ_CONFIG_DIR`, else `~/.config/zellij` if it exists, else the OS dir if it
exists (`${XDG_CONFIG_HOME:-~/.config}/zellij` on Linux; on macOS, which ignores
XDG, `~/Library/Application Support/org.Zellij-Contributors.Zellij`). On a fresh
machine that's `$XDG_CONFIG_HOME/zellij` (if set) on Linux, else
`~/.config/zellij`. It backs up any existing config to a timestamped copy first — a real copy of the
files even when your config dir is a symlink into a dotfiles repo — so nothing is
ever clobbered. After installing, if zellij is on your PATH, it asks zellij which
config dir it will actually read (`zellij setup --check`) and warns if that isn't
the one it installed into, then parses the installed config and every layout. It
also warns if your zellij is older than 0.45, and supports `--dry-run` and `--help`.

**`--restore`** puts back the most recent backup. It first saves your current
config as a new backup, so running `--restore` again undoes it, and it keeps a
symlinked config dir a symlink. Older backups sit next to your config dir
(`zellij.backup-YYYYMMDD-HHMMSS`) if you need one by hand.

**`--offline` needs no network and verifies every plugin file.** It takes each
plugin from the archive's `plugins/` folder, downloading only one that's missing
there or doesn't match. Either way the file is checked against its SHA-256 in
`plugins.sha256` before it's used; a mismatch or a missing entry stops the
install and leaves your config on its https URLs. (Without `--offline`, zellij
downloads plugins itself and no checksum is involved.) It installs
*on top of* your existing dir, so extra files of your own (say, another layout)
stay put; only the shipped files are replaced.

**The `zj` launcher needs no PATH edit.** setup.sh puts it in `~/.local/bin`
when that's on your PATH, else next to `zellij` if that folder is writable.
Failing both, it still uses `~/.local/bin` and prints the line that adds it to
your PATH (fish: `fish_add_path ~/.local/bin`). An existing `zj` that isn't this
launcher is left alone, and `--restore` doesn't touch the launcher.

The manual steps below differ slightly: they **move** the old config aside and
copy in a fresh one (so your extra files end up only in the backup), and they also
copy `README.md`, which zellij simply ignores.

The directory in this archive is named `config/` — its *contents* go into
zellij's config directory.

**Linux and macOS (manual):**

```bash
# Back up any existing config first (timestamped, so re-runs never clobber).
# Same name format as setup.sh uses, so `./setup.sh --restore` can find it:
[ -d ~/.config/zellij ] && mv ~/.config/zellij ~/.config/zellij.backup-"$(date +%Y%m%d-%H%M%S)"
cp -rT config ~/.config/zellij     # BSD/macOS cp lacks -T: use `cp -R config/ ~/.config/zellij` (note the trailing slash)
```

zellij checks `~/.config/zellij` **first** on macOS too. The legacy
`~/Library/Application Support/org.Zellij-Contributors.Zellij/` location also
works, but anything you put there is silently shadowed if `~/.config/zellij`
exists — so prefer `~/.config/zellij`.

**Windows (PowerShell),** from the archive unpacked anywhere *except*
`%APPDATA%\Zellij` (these steps move the old config aside, which there would be
the copy they're about to install):

```powershell
# Zellij on Windows has no ~/.config convention — it uses Roaming AppData:
$dest = "$env:APPDATA\Zellij\config"
if (Test-Path $dest) { Move-Item $dest "$dest.backup-$(Get-Date -Format yyyyMMdd-HHmmss)" }
New-Item -ItemType Directory -Force (Split-Path $dest) | Out-Null
Copy-Item -Recurse config $dest
# The zj launcher, next to zellij.exe. That folder is already on your PATH
# (it's how `zellij` is found), so `zj` works with no PATH edit:
Copy-Item launcher\zj.cmd, launcher\zj.ps1 (Split-Path (Get-Command zellij).Source)
```

For an air-gapped Windows machine, also do the PowerShell steps under
[Offline / air-gapped machines](#offline--air-gapped-machines).

Verify it parses:

```bash
zellij setup --check
```

> Note: `setup --check` catches KDL syntax errors but **not** misspelled
> option names — zellij silently ignores unknown config keys. It also skips
> layouts unless you name one: `zellij --layout dev setup --check` parses
> `dev.kdl` and its `dev.swap.kdl` (`./check.sh` does this for every layout).

### Using the archive in place

Instead of installing a copy, you can have zellij read the archive's own
`config/`. Then edits you make there are live, and the repo is the only copy.

- **Windows:** unpack into `%APPDATA%\Zellij`. Its `config\` subfolder is
  where zellij looks, so nothing else is needed but the launcher. (If
  `%APPDATA%\Zellij\config` already exists, use the in-place steps under
  [Updating to a newer archive](#updating-to-a-newer-archive) instead: they back
  it up first.)

  ```powershell
  Expand-Archive 28_zellij_audited_2026-10-14.zip "$env:APPDATA\Zellij"
  Copy-Item "$env:APPDATA\Zellij\launcher\zj.cmd", "$env:APPDATA\Zellij\launcher\zj.ps1" (Split-Path (Get-Command zellij).Source)
  zellij setup --check
  ```

- **Linux and macOS:** point zellij at it with `ZELLIJ_CONFIG_DIR`, and link
  the launcher, so that updating the repo updates `zj` too:

  ```bash
  mkdir -p ~/.local/bin && ln -sf ~/src/zellij-config/launcher/zj ~/.local/bin/zj
  # fish (once; it persists):
  set -Ux ZELLIJ_CONFIG_DIR ~/src/zellij-config/config
  # bash / zsh: add to ~/.bashrc or ~/.zshrc
  export ZELLIJ_CONFIG_DIR="$HOME/src/zellij-config/config"
  ```

  Don't run `setup.sh` then: there's nothing to copy, and it says so and stops.

### Updating to a newer archive

Check the newest entry in `CHANGELOG.md` first. It lists behavior changes
(moved keybindings and the like) and any file the new version removed.

- **Linux and macOS:** unpack the new archive into a *new* folder and run
  `./setup.sh` from it (`--offline` if that's how you installed). It backs up
  your current config, installs on top so your own extra files stay, points
  out leftovers it knows of, and replaces the `zj` launcher.
- **Windows, installed copy:** unpack the new archive anywhere but
  `%APPDATA%\Zellij`, and re-run the [Windows install steps](#install-it) from
  it, plus the offline steps if you use them. The old config is moved to a
  timestamped backup.
- **In place (either OS):** back up, unpack the new archive over the old one,
  then delete the files the CHANGELOG says were removed. Unpacking replaces and
  adds files but never deletes any. On Windows, re-copy the launcher afterwards;
  a symlinked `zj` on Linux/macOS needs nothing:

  ```powershell
  # Windows
  $z = "$env:APPDATA\Zellij"
  Copy-Item -Recurse "$z\config" "$z\config.backup-$(Get-Date -Format yyyyMMdd-HHmmss)"
  Expand-Archive -Force 28_zellij_audited_2026-10-14.zip $z
  Remove-Item "$z\config\layouts\welcome.kdl" -ErrorAction SilentlyContinue   # removed 2026-10-14
  Copy-Item "$z\launcher\zj.cmd", "$z\launcher\zj.ps1" (Split-Path (Get-Command zellij).Source)
  zellij setup --check
  ```

  ```bash
  # Linux / macOS
  cp -R ~/src/zellij-config ~/src/zellij-config.backup-"$(date +%Y%m%d-%H%M%S)"
  unzip -o 28_zellij_audited_2026-10-14.zip -d ~/src/zellij-config
  rm -f ~/src/zellij-config/config/layouts/welcome.kdl                        # removed 2026-10-14
  zellij setup --check
  ```

Running sessions pick up `config.kdl` changes by themselves; layout changes
apply to sessions started afterwards.

### Undoing an install

- **Linux and macOS:** `./setup.sh --restore` puts back the most recent backup
  (see above).
- **Windows:** the install steps leave `config.backup-YYYYMMDD-HHMMSS` next to
  your config. To swap the newest one back in (run it again to undo):

  ```powershell
  $dest = "$env:APPDATA\Zellij\config"
  $last = Get-Item "$dest.backup-*" | Where-Object PSIsContainer | Sort-Object Name | Select-Object -Last 1
  Move-Item $dest "$dest.backup-$(Get-Date -Format yyyyMMdd-HHmmss)"
  Move-Item $last.FullName $dest
  ```

- The `zj` launcher stays either way; see below to remove it.

### Removing this config

To stop using this config but keep zellij:

1. **Move the config dir aside.** `zellij setup --check` prints the one it
   loads (`[CONFIG DIR]`). Once it's gone, zellij runs on its built-in
   defaults. The name below matches the installers' backups, so
   `./setup.sh --restore` or the Windows undo steps above bring it back.

   ```bash
   # Linux / macOS (use the dir zellij printed)
   mv ~/.config/zellij ~/.config/zellij.backup-"$(date +%Y%m%d-%H%M%S)"
   ```

   ```powershell
   # Windows
   $dest = "$env:APPDATA\Zellij\config"
   Move-Item $dest "$dest.backup-$(Get-Date -Format yyyyMMdd-HHmmss)"
   ```

   Used in place via `ZELLIJ_CONFIG_DIR`? Unset it instead (fish:
   `set -Ue ZELLIJ_CONFIG_DIR`; bash/zsh: delete the `export` line). On Windows
   in place, the rest of `%APPDATA%\Zellij` (scripts, cheatsheets, `launcher\`,
   `plugins\`) is just the archive; zellij never reads it.
2. **Remove the launcher** and its state (only the date of the last check):
   - Linux/macOS: `rm ~/.local/bin/zj` (or wherever `command -v zj` points), and
     `~/.local/state/zellij-config/`. Also
     `~/.local/share/zellij-config/`, if an offline install put plugins there.
   - Windows: `$d = Split-Path (Get-Command zellij).Source; Remove-Item "$d\zj.cmd", "$d\zj.ps1"`,
     and `%LOCALAPPDATA%\zellij-config\`.
   - Unset `ZJ_NO_UPDATE_CHECK` if you set it.
3. **Leave zellij's cache alone** unless you mean to: it holds your saved
   sessions and plugin permission grants, which belong to zellij, not this
   config. Old `*.backup-*` folders next to the config dir can be deleted once
   you don't need them.

## How zellij works (the 60-second tour)

Zellij is **modal**, like vim. Press a `Ctrl+<letter>` prefix to enter a mode,
then individual keys do things.

| Prefix     | Mode    | What it's for                                 |
| ---------- | ------- | --------------------------------------------- |
| `Ctrl+p`   | pane    | Split, close, focus, rename, fullscreen       |
| `Ctrl+t`   | tab     | Create, switch, rename, reorder               |
| `Ctrl+n`   | resize  | Grow/shrink the focused pane                  |
| `Ctrl+h`   | move    | Move the focused pane around the grid         |
| `Ctrl+s`   | scroll  | Scroll back and search the buffer             |
| `Ctrl+o`   | session | Detach, switch sessions, session manager      |
| `F12`      | locked  | Pass *everything* through to the inner app    |
| `Ctrl+q`   | —       | Quit (unbound here; use `Ctrl+o` then `q`, a custom bind in this config) |

Inside a mode, lowercase letters are usually action initials (`n` = new,
`x` = close, `f` = fullscreen). The status bar reminds you what's available.

Everything this config changes from stock zellij (all other lines in
`config.kdl` restate zellij's defaults and are marked `// default`):

| Change                        | Effect                                              |
| ----------------------------- | --------------------------------------------------- |
| `Ctrl+q` unbound              | Stops the accidental-quit footgun                   |
| `Ctrl+o` then `q`             | Deliberate two-step quit (replaces `Ctrl+q`)        |
| `Ctrl+g` unbound, `F12` toggles lock | Default lock key clashes with nvim (and is stolen from the app while locked); `F12` is free in nvim/terminals and toggles lock both ways |
| `Ctrl+o` then `h`             | Pop up the zellij-forgot keybinding list (floating; `Esc` closes it) |
| `Ctrl+o` then `m`             | monocle: find files and contents, rooted at the focused pane's directory |
| `Ctrl+o` then `t` / `e`       | Opt-in and Unix-only (commented out): multitask in the current directory / edit `config.kdl` |
| `session_name "main"` + `attach_to_session true` | Plain `zellij` joins or creates one persistent `main` session |
| Default layout: `main` + `shell` tabs, `compact-bar` | Keeps nvim's `:qa` from ending a resurrected session (see **Session recovery**) |
| `theme "catppuccin-mocha"`, `pane_frame_style "full"`, `rounded_corners true` | The look: full rounded frames (zellij 0.45's default style is `"titles"`) |
| `env { RUST_BACKTRACE "1" }`  | Rust programs you run in panes print backtraces     |
| `plugins { … }` aliases       | zjstatus, monocle, multitask, forgot — pinned, loaded only on demand |

**Locking is manual.** Zellij's `Alt+…` bindings (`Alt+h/j/k/l`, `Alt+f`, `Alt+n`)
collide with nvim and readline, so press `F12` when you enter an editor or TUI and
`F12` again when you leave. Nothing auto-locks for you, and the failure is silent —
forget, and zellij eats the keystroke instead of passing it through.

If that gets old, two ways out — in ascending order of disruption:

1. **Let nvim lock for you.** `VimEnter` / `VimLeave` autocmds calling
   `zellij action switch-mode locked` / `normal`. This is the least invasive fix
   and it's immune to the resurrected-pane problem, because nvim's own startup is
   the trigger rather than a guess about what's in the pane. Recommended if the
   manual F12 dance wears thin.
2. **Switch to the non-colliding (Unlock-First) preset.** In-app: `Ctrl+o` → `c`
   → *Change Mode Behavior* → *Unlock-First* → `Ctrl+a` to persist. Note what this
   costs: it is **not** a single config setting — saving dumps the entire preset
   into `config.kdl`, **reintroduces `Ctrl+g` as the unlock key** (the one this
   config deliberately unbinds for nvim), and replaces the custom `F12`,
   `Ctrl+o q`, `Ctrl+o h` and `Ctrl+o m` binds. It's an either/or with the setup
   shipped here, not an addition to it — adopt it only if you want zellij's
   unlock-first model wholesale.

The rest of zellij's default keybindings are kept intact. For the everyday ones,
press `Ctrl+o` then `h` inside zellij (the popup), or open
`cheatsheets/zellij-cheatsheet.html` for the full reference. The popup's list in
`config.kdl` is the master copy; the cheatsheet mirrors it by hand, and
`./check.sh` (check 10) flags any `Alt`, `Ctrl` or `F` key the docs mention that
isn't actually bound.

## Theme

Set in `config.kdl` to `catppuccin-mocha`, which ships **built-in** with zellij
— no theme file required. To switch flavors, change one line:

```kdl
theme "catppuccin-latte"      // light
theme "catppuccin-frappe"     // medium-dark
theme "catppuccin-macchiato"  // dark
theme "catppuccin-mocha"      // darkest (default in this config)
```

In zellij 0.44.2+ you can have it follow your terminal's light/dark mode by
setting both `theme_dark` and `theme_light` (the terminal must report its mode
via CSI 2031; with only one of the two set, the static `theme` stays in charge).
`explicit_theme_hue` (0.45.1) does the opposite: it **pins** the session to
`"dark"` or `"light"` and ignores the terminal's reports — it is not a fallback
for terminals that stay silent. See the commented lines in `config.kdl`. Other
excellent built-ins: `tokyo-night`, `gruvbox-dark`, `nord`, `kanagawa`,
`dracula`, `everforest-dark`.

## Layouts

Run them like this (verified against zellij 0.45.1):

```bash
zellij -s proj -n dev        # NEW "proj" session with the dev layout (3 tabs)
zellij -n welcome            # new session with zellij's built-in session picker
zellij                       # attaches to / creates "main" (default layout)
```

**Swap layouts.** `Alt+[` / `Alt+]` cycle the panes of a tab through preset
arrangements (vertical, horizontal, stacked, half-stacked). zellij looks for them
in a `NAME.swap.kdl` file next to each layout — its built-in layouts come with
one, but a custom layout doesn't, and without it the keys silently do nothing.
So `default`, `dev` and `zjstatus` each have a `.swap.kdl` (zellij's own
"compact" swap layouts). If you add a layout of your own, copy the swap file
whose bar matches yours to `yourname.swap.kdl` — `default.swap.kdl` for a
`compact-bar` layout, `zjstatus.swap.kdl` for zjstatus. The swap file's
`tab_template` has to name the same bar plugin as your layout, or zellij can't
tell the bar apart from your panes. `./check.sh` compares the swap files with
`zellij setup --dump-swap-layout compact`, so a zellij upgrade that changes the
built-in arrangements gets flagged.

`-n` is `--new-session-with-layout`. Because `config.kdl` sets `session_name
"main"` + `attach_to_session true`, a bare `zellij --layout dev` (`-l dev`) does
**not** give you a new session: if `main` isn't running it creates `main` with
the dev layout, but if `main` is already running it just attaches and **silently
ignores the layout** (verified on 0.45.1). Use `-s <name> -n <layout>` for a
separate project session. Note that `zellij --session proj --layout dev` does **not**
create a session: with `--session`, `--layout` means "add these tabs to an
existing session" and errors if it doesn't exist.

Or set one as your default in `config.kdl`:

```kdl
default_layout "dev"
```

Inside a session you can also press `Ctrl+o` then `l` to open the **layout
manager** (new in 0.44.0) and apply any layout to the current tab on the fly.

## Plugin recommendations

The config **aliases** these (i.e. registers a short name → URL) so you can
launch them on demand. None are loaded by default; pick what you actually
want. URLs are **pinned to specific release tags** for reproducibility — see
[Updating a pinned plugin](#updating-a-pinned-plugin) below for the bump
procedure.

**Load one in a floating pane** from inside zellij:

```text
zellij plugin --floating -- zjstatus       # uses the alias
```

| Plugin               | Pinned   | What it does                                                       | Repo                                                  |
| -------------------- | -------- | ------------------------------------------------------------------ | ----------------------------------------------------- |
| **zjstatus**         | v0.25.0  | Tmux-line-style customizable status bar with modules, colors, etc. | https://github.com/dj95/zjstatus                      |
| **monocle**          | v0.100.2 | Fuzzy file/content finder, rooted at the focused pane's directory  | https://github.com/imsnif/monocle                     |
| **multitask**        | v0.45.1  | "Mini-CI": run commands in parallel steps from a `.multitask` file | https://github.com/leakec/multitask (moved from imsnif) |
| **zellij-forgot**    | 0.4.2    | Keybinding popup — **bound to `Ctrl+o` then `h`** (curated list; auto-load off) | https://github.com/karimould/zellij-forgot      |

> **Nothing is auto-loaded.** Plugins start when you ask for them: `forgot` with
> `Ctrl+o` then `h`, monocle with `Ctrl+o` then `m` (floating, rooted at the
> focused pane's directory). multitask opens a new tab with `$EDITOR` on a
> `.multitask` file for the directory you launch it in — run
> `zellij action start-or-reload-plugin multitask --configuration "shell=$SHELL,ccwd=$(pwd)"`
> in a pane, or uncomment the Unix-only `Ctrl+o` then `t` bind in `config.kdl`.
> zjstatus is used by its layout. To run a plugin in the background from startup,
> add a `load_plugins { … }` block to `config.kdl` (`./check.sh` lists it as INFO).
>
> **Ready-made zjstatus status bar: `layouts/zjstatus.kdl`.** An opt-in layout
> that swaps the built-in compact-bar for a Catppuccin-Mocha zjstatus bar (mode,
> session, tabs, active swap layout, git branch, clock). Try it with `zellij -s zjs -n zjstatus`; adopt
> it with `default_layout "zjstatus"` in `config.kdl`. Three things to expect, each
> covered under **Troubleshooting**:
>
> - it manages pane frames itself: set `pane_frames false`, or press `Ctrl+p` then
>   `z` per session (there's no way to set frames per layout);
> - the first run asks for permission inside the one-row bar — click the bar, then `y`;
> - the git branch is for the directory you started zellij in, not the focused pane.
>
> **Not here: [zellij-autolock](https://github.com/fresh2dev/zellij-autolock).**
> It auto-locks when nvim/vim/lazygit is focused, which sounds ideal — but it
> decides the mode by reading the focused pane's running command, and forces
> Normal mode whenever it *doesn't* see a trigger. In a pane restored from
> session resurrection the command doesn't read back as `nvim`, so it will
> yank you out of Locked mode a fraction of a second after you press `F12`.
> This config uses a plain manual `F12` toggle instead.

### Checking for plugin updates

Pinned plugins never update on their own; that's the point of pinning. To hear
about new releases anyway, start zellij as **`zj`**, the launcher in
`launcher/`. It takes the same arguments as `zellij` and passes them through.
About once a month, before starting zellij, it asks GitHub for the latest
release of every pinned plugin. If one is newer it shows this and waits for
Enter; otherwise it says nothing:

```text
Plugin pins in /home/you/.config/zellij/config.kdl:
  zjstatus         v0.25.0    -> v0.26.0 available: https://github.com/dj95/zjstatus/releases/tag/v0.26.0
  monocle          v0.100.2   current
  zellij-forgot    0.4.2      current
  multitask        v0.45.1    current

Newer plugin releases exist. Nothing was changed; to update, see the
README section "Updating a pinned plugin".
Press Enter to start zellij...
```

It never edits anything: updating stays the manual steps below, because a newer
release may need a newer zellij.

**Install it once:**

- **Linux and macOS:** `./setup.sh` does it (see **Install**); by hand,
  `mkdir -p ~/.local/bin && install -m 755 launcher/zj ~/.local/bin/zj`. It's a `#!/bin/sh` script, so it
  behaves the same whether your shell is fish, bash or zsh. If `~/.local/bin`
  isn't on your PATH yet: in fish run `fish_add_path ~/.local/bin` once (it
  persists); in bash or zsh add `export PATH="$HOME/.local/bin:$PATH"` to
  `~/.bashrc` or `~/.zshrc`.
- **Windows:** copy `zj.cmd` and `zj.ps1` next to `zellij.exe` (the last line of
  the Windows install steps). That folder is already on your PATH, so `zj`
  works in cmd, PowerShell and Windows Terminal. On most starts `zj.cmd` only
  compares a file date, adding about a quarter of a second; PowerShell runs only
  when a check is due, with `-ExecutionPolicy Bypass` so a strict script policy
  doesn't stop it.

**How it decides:**

- A check is due 30 days after the last one that reached GitHub. When GitHub
  can't be reached (offline, a proxy), zj starts zellij without a word and tries
  again the next day. Each request gives up after 8 seconds, and zj stops at the
  first one that fails.
- There's no plugin list to maintain: zj reads every
  `location="https://github.com/OWNER/REPO/releases/download/TAG/FILE"` in the
  config zellij loads, so a plugin you add the same way is covered too. Plugins
  loaded from disk (`file:`, as after an offline install) or from other hosts
  are listed as "not checked"; check those from the repo with
  `./check.sh --updates` on a machine with network.
- "Latest" is GitHub's latest release, which leaves out prereleases. zj can't
  tell whether that release supports your zellij version; step 2 below covers
  that.

**Commands and settings:**

- `zj --check-updates` checks now and prints the full report for the config
  zellij loads; `zj --check-updates FILE` checks another file. Exit code 0 means
  all current, 1 newer releases, 2 couldn't check.
- `./check.sh --updates` prints the same report for the repo's `config.kdl`.
- `ZJ_NO_UPDATE_CHECK=1` turns the startup check off (fish:
  `set -Ux ZJ_NO_UPDATE_CHECK 1`; Windows:
  `[Environment]::SetEnvironmentVariable('ZJ_NO_UPDATE_CHECK', '1', 'User')`).
  Or simply run `zellij` instead of `zj`.
- The date of the last check is kept in
  `~/.local/state/zellij-config/plugin-update-check` (under `$XDG_STATE_HOME`
  if set), or `%LOCALAPPDATA%\zellij-config\plugin-update-check` on Windows.
  Delete it to check on the next start.

### Updating a pinned plugin

1. **Find the latest tag.** `./check.sh --updates` lists every pin next to its
   latest release (see [Checking for plugin updates](#checking-for-plugin-updates)).
   Without Git Bash on Windows, `zj --check-updates` gives the same list for
   your installed config.
   Open the plugin's GitHub releases page (linked in the table above) to read
   the notes and confirm the release ships a `.wasm` asset. To test whether a
   particular tag exists, probe its download URL (GitHub's API is rate-limited,
   but asset URLs aren't) — a `200` means it does:

   ```bash
   for t in v0.26.0 v0.25.1 v0.25.0; do
     printf '%s: ' "$t"
     curl -s -o /dev/null -w '%{http_code}\n' -L \
       "https://github.com/dj95/zjstatus/releases/download/$t/zjstatus.wasm"
   done
   ```

2. **Check compatibility before bumping.** Plugins are built against a
   specific zellij plugin API:
   - **multitask** releases are named after the zellij version they target —
     match your zellij version (e.g. v0.45.1 ↔ zellij 0.45.1).
   - **zjstatus** lists supported zellij versions in its release notes /
     wiki — read them before jumping a minor version (e.g. v0.25.0 needs ≥0.45.0).
   - When in doubt, prefer a release published *after* your zellij version.
3. **Edit the URL** in the `plugins {}` block of `config.kdl` — change only
   the tag segment, e.g.
   `…/releases/download/v0.25.0/zjstatus.wasm` → `…/releases/download/v0.26.0/zjstatus.wasm`.
4. **Update the version in the docs too, then lint.** The version also appears in
   this README's plugin table and the offline-download table (and the plugins
   cheatsheet). Change them to match, then run `./check.sh` (on Windows, from
   Git Bash) — it flags any plugin
   pin that drifts between `config.kdl`, the README and the cheatsheets (all four
   plugins), catching the easy mistake of editing one and forgetting the others.
   **Also refresh the bundled copy in `plugins/`** (what offline installs use)
   **and its line in `plugins.sha256`**, both at the repo root. Download the new
   file over the old one, then print its checksum:

   ```bash
   # Linux / macOS (macOS: shasum -a 256 instead of sha256sum)
   curl -fLo plugins/zjstatus.wasm <new-url>
   sha256sum plugins/zjstatus.wasm
   ```

   ```powershell
   # Windows
   Invoke-WebRequest <new-url> -OutFile plugins\zjstatus.wasm -UseBasicParsing
   (Get-FileHash plugins\zjstatus.wasm).Hash.ToLower()
   ```

   Put the value and the new URL on the plugin's line in `plugins.sha256`
   (`<sha256>  <url>`). If the release page on GitHub shows a `sha256:` digest
   for the file, it should match. `./check.sh` warns if a pin has no checksum
   (check 13), and if a file in `plugins/` doesn't match its checksum or isn't
   pinned (check 14).
5. **Clear the plugin cache** — zellij caches downloaded `.wasm` files and
   compiled artifacts, and a stale cache is the #1 cause of "I updated but
   nothing changed" (and of post-upgrade crashes). Use the commands in
   [Clearing the plugin cache](#clearing-the-plugin-cache): they keep your saved
   sessions, which deleting the whole cache dir would throw away.
6. **Restart the sessions that use the plugin.** A session started after the
   change loads the new version. `zellij kill-all-sessions` restarts everything
   at once, but ⚠ a killed session is gone for good — it can't be resurrected
   (see **Session recovery**) — so save your work first, or kill only the
   sessions you can spare (`zellij kill-session <name>`). On first load the plugin
   re-downloads and may prompt once for permissions — focus its pane and press
   `y`. **zjstatus specifically** re-asks on every version bump (the grant is
   keyed by URL); its prompt shows truncated in the one-row bar, so click the bar
   to focus it, then `y`.

**Offline / air-gapped installs.** If you installed with `./setup.sh --offline`
(the installed config points at `file:` paths), do steps 1–4 in the *repo* on a
machine with network, including the new file in `plugins/`, and carry the repo
over. Then re-run `./setup.sh --offline`: it installs the new copy and rewrites
the installed config's `file:` paths for you. On Windows, repeat the PowerShell
steps under [Offline / air-gapped machines](#offline--air-gapped-machines).
Then clear the cache (step 5) and restart.

If the new version misbehaves, roll back: the pin makes that a one-line
revert in `config.kdl` (plus the cache clear again).

**Adding a plugin** follows the same pattern: pin its release URL in
`plugins {}`, add it to the table under
[Offline / air-gapped machines](#offline--air-gapped-machines), add its
checksum to `plugins.sha256` and the file to `plugins/`. `./check.sh` flags
whichever you forget, and `zj` checks the new pin for updates with no further
setup.

### Clearing the plugin cache

Zellij caches each plugin's `.wasm` after first download, keyed by its URL,
along with compiled artifacts. A stale cache is the usual reason a URL change
"does nothing," and clearing it is also how you force a re-download.

⚠ **Don't delete the whole cache dir.** It also holds your saved sessions
(`contract_version_1/`, which `zellij attach` resurrects from) and your plugin
permission grants (`permissions.kdl`). These commands remove everything else:

```bash
# Linux. On macOS use c=~/Library/Caches/org.Zellij-Contributors.Zellij
c="${XDG_CACHE_HOME:-$HOME/.cache}/zellij"
find "$c" -mindepth 1 -maxdepth 1 ! -name contract_version_1 ! -name permissions.kdl -exec rm -rf {} +
```

```powershell
# Windows
Get-ChildItem "$env:LOCALAPPDATA\Zellij\cache" -Force |
    Where-Object Name -notin 'contract_version_1', 'permissions.kdl' |
    Remove-Item -Recurse -Force
```

Then restart the sessions that use the plugin (see step 6 above for what a
restart costs). Running sessions keep the copy they already loaded.

### Offline / air-gapped machines

The `location` URLs are only fetched on **first** use, then cached. With no
network that first fetch fails, so this archive carries the pinned files in
**`plugins/`**, each matching its checksum in `plugins.sha256` (`./check.sh`
confirms). Install them next to your config and point the aliases at them with
`file:` paths:

**Linux and macOS:** `./setup.sh --offline` does all of it, with no network. It
copies the files to `plugins/` in your config dir, verifies each one, and
rewrites the installed config's `location`s. (If the config dir's path contains
a space, as macOS's `~/Library/Application Support/…` does, the files go to
`~/.local/share/zellij-config/plugins/` instead.)

**Windows (PowerShell),** from the unpacked archive, after the install steps.
If you use the archive in place, this edits the archive's own `config.kdl`, so
on that machine `./check.sh` will report the plugins as unpinned; that's
expected.

```powershell
$dest = "$env:APPDATA\Zellij\config"
New-Item -ItemType Directory -Force "$dest\plugins" | Out-Null
Copy-Item plugins\*.wasm "$dest\plugins"
# Point each https location at its local copy. Forward slashes, because KDL reads
# \ as an escape; ReadAllText/WriteAllText, because PowerShell 5.1's
# Get-Content/Set-Content would re-encode the UTF-8 file.
$dir = "$dest\plugins" -replace '\\', '/'
$text = [IO.File]::ReadAllText("$dest\config.kdl")
$text = $text -replace 'location="https://github\.com/[^"]*/([^"/]+\.wasm)"', "location=`"file:$dir/`$1`""
[IO.File]::WriteAllText("$dest\config.kdl", $text)
# Confirm each copy against plugins.sha256 (prints ok or MISMATCH per file):
Get-Content plugins.sha256 | Where-Object { $_ -match '^[0-9a-f]{64}\s' } | ForEach-Object {
    $sha, $url = -split $_
    $f = "$dest\plugins\" + $url.Split('/')[-1]
    if ((Get-FileHash $f -Algorithm SHA256).Hash -eq $sha) { "ok        $f" } else { "MISMATCH  $f" }
}
zellij setup --check
```

**By hand, any OS:** the files and their pinned URLs, if you'd rather fetch
fresh copies:

| File                   | URL                                                                                  |
| ---------------------- | ------------------------------------------------------------------------------------ |
| `zjstatus.wasm`        | https://github.com/dj95/zjstatus/releases/download/v0.25.0/zjstatus.wasm              |
| `monocle.wasm`         | https://github.com/imsnif/monocle/releases/download/v0.100.2/monocle.wasm             |
| `multitask.wasm`       | https://github.com/leakec/multitask/releases/download/v0.45.1/multitask.wasm   |
| `zellij_forgot.wasm`   | https://github.com/karimould/zellij-forgot/releases/download/0.4.2/zellij_forgot.wasm |

Put them in a `plugins/` folder inside your config dir and change each alias's
`location` from `https://…` to a `file:` path (Linux paths shown):

```kdl
plugins {
    zjstatus  location="file:~/.config/zellij/plugins/zjstatus.wasm"
    monocle   location="file:~/.config/zellij/plugins/monocle.wasm"
    multitask location="file:~/.config/zellij/plugins/multitask.wasm"
    forgot    location="file:~/.config/zellij/plugins/zellij_forgot.wasm"
}
```

- **Path forms.** `file:~/…` works on every OS (`~` is your home folder). On
  Windows, `file:C:/Users/you/…` works too, but `file:/C:/…` does **not**:
  zellij 0.45.1 reads it as `C:/C:/…` and the plugin fails to load (both checked
  on Windows).
- ⚠ **On macOS and Windows, don't create `~/.config/zellij` just to hold the
  files.** zellij looks in that folder before the OS's own config dir (see
  **Config not picked up** under Troubleshooting), so once it exists your real
  config is ignored. Earlier versions of this README advised exactly that.
- The `Ctrl+o h` keybind references `forgot` by alias name, so it keeps
  working unchanged.

Once the config points at `file:` paths, no download happens — the plugins load
straight from disk. (If you previously loaded them online, clear the cache once
— see above — so zellij picks up the new `file:` locations.)

A couple worth knowing about (not aliased above, but easy to add):

- **room** — project picker / session switcher (`https://github.com/rvcas/room`)
- **harpoon** — jump-to-pane bookmarks (`https://github.com/Nacho114/harpoon`)
- **theme-tester** — live-edit theme files and see results
  (`https://github.com/imsnif/theme-tester`)

**Want zjstatus as your everyday bar?** Use the ready-made `layouts/zjstatus.kdl`
(`default_layout "zjstatus"`, see above) rather than editing `default.kdl`. The
bar is one row (`size=1`) and carries the whole widget configuration, and the
swap file must name the same bar — `zjstatus.swap.kdl` already does, while
`default.swap.kdl` names `compact-bar`.

## Clipboard

This config uses **OSC52** by default — an escape sequence that asks the
terminal emulator to copy text to the system clipboard. It works on:
Windows Terminal, Wezterm, Alacritty, Kitty, Ghostty, iTerm2, modern
gnome-terminal/foot, and transparently through SSH.

If your terminal doesn't support OSC52, uncomment the right `copy_command`
line in `config.kdl` for your platform.

## Session recovery (ON, made nvim-safe by the two-tab default)

**Session serialization is ON** (`session_serialization true`). zellij saves each
session — tabs, panes, cwds, and the command running in each pane — to disk and
resurrects it on reattach or after a reboot/crash.

**After a crash or reboot, use `zellij attach --create main`** — not plain
`zellij`. Plain `zellij` only attaches to a `main` that is still *running*; if
`main` crashed, it starts a **fresh** `main` and the saved one is discarded.
`zellij attach --create main` resurrects the saved session, joins it if it's
running, and creates it if there's none — the right thing in every case, so it
makes a good everyday habit (e.g. `alias zj='zellij attach --create main'`).
(All three verified on 0.45.1 with a marked snapshot.)

**Don't count on recent changes being saved (zellij 0.45.1).** A recovered
session may be older than what you had — see the first entry under **Known
issues (zellij 0.45.1)**. Your editor's own session manager is what reliably
restores the files you had open.

**The nvim catch, and how this config defuses it.** zellij saves the command it
sees running in a pane, not the shell underneath. For an editor it goes further:
`nvim a.txt` typed in a shell is saved as an *edit pane* (`edit="a.txt"`), which
on resurrection opens the file in an editor directly — with **no parent shell
under it**. On its own, `:qa`
from that pane closes the pane, and if it were the last pane in the last tab it
would end the whole session. That's what originally made serialization painful.

The fix here is structural, not a hook: **the default layout opens a separate
`shell` tab** (see `layouts/default.kdl`), so your working `main` tab is never the
last tab. When you `:qa`, nvim's pane (and its tab) closes and you land in the
shell tab — the session, and its reboot/crash recovery, live on. A separate tab
(rather than a split pane) gives nvim the full screen and is far less tempting to
close by reflex. Verified against the binary: closing the working tab's pane leaves
the session alive in the other tab.

**Limitation — this is a *soft* guarantee.** It holds only while the shell tab
exists. If you close the shell tab and then `:qa` from a lone nvim, the session
ends. Because serialization is on, that ended session is still *resurrectable*
(`zellij attach <name>`; verified on 0.45.1 — unlike `zellij kill-session`, which
discards it), so you don't lose your context permanently — but you do get bounced
to the terminal. Two ways to make it hard:

- **nvim session plugin** (recommended, zero coupling): persistence.nvim,
  auto-session, or `:mksession`. It never talks to zellij, and it means that
  however nvim comes back — resurrected, or relaunched by you after a session ends
  — your buffers return. Also survives a full-machine crash regardless of zellij.
- **`post_command_discovery_hook`** (pane/tab-count independent): zellij runs this
  command every time it saves the session, passes each pane's running command in
  `$RESURRECT_COMMAND` (e.g. `nvim a.txt`), and saves whatever it prints instead.
  Having it print `zellij-resume nvim a.txt` — where `zellij-resume` is a tiny
  script that runs its arguments and then `exec "$SHELL"` — brings nvim back
  *inside your own shell*, so `:qa` drops to a prompt. Tested on 0.45.1 with bash,
  zsh and fish (the hook always runs under `sh`, and handing off to `$SHELL`
  needs no shell-specific syntax). Not shipped, for three reasons: zellij passes
  the command as one flattened string, so a filename with spaces comes back split
  in two; each restored pane waits for Enter; and it needs two extra scripts
  installed at known paths.

## Things to try first

1. **Detach and reattach.** `Ctrl+o`, then `d`. Run `zellij attach` to come back.
   (This works while zellij is running — independent of serialization.)
2. **Resurrect after reboot.** `session_serialization` is **on** — close your
   terminal, reboot, run `zellij attach --create main` (not plain `zellij`, which
   would start a fresh session and discard the saved one). What comes back is the
   last copy zellij managed to save, which may be older — see the zellij 0.45.1
   note under **Session recovery**. Panes come back blank rather than showing their last screen
   (`serialize_pane_viewport` is off). See **Session recovery** above for the nvim
   `:qa` behavior.
3. **Use the layout manager.** `Ctrl+o`, then `l`. Apply `dev` to your
   current tab without restarting.
4. **Float a pane.** `Alt+f` toggles floating panes; open a new one with
   pane mode (`Ctrl+p`, then `n`) while floating is active — handy for a
   throwaway `git diff` over your work.

## Upgrading

This config targets **zellij 0.45.1**. When you move to a newer zellij:

1. **Read the release notes** (zellij shows them in a popup on first launch).
   Look for renamed or removed options and changed defaults; the popup can also
   add newly introduced default keybindings to your config.
2. **Bump multitask to the matching tag.** Its releases are named after the zellij
   version they target (v0.45.1 ↔ zellij 0.45.1). Check the other plugins' release
   notes for a minimum zellij version too — see **Updating a pinned plugin**.
3. **Clear the plugin cache** and restart, so the new zellij recompiles the plugins
   (use the session-preserving commands in **Clearing the plugin cache**).
4. **Validate:** `zellij setup --check`, then `./check.sh`.
5. **Refresh the swap layouts** if zellij's built-in ones changed — `./check.sh`
   (check 12) says so. `zellij setup --dump-swap-layout compact` prints them; see
   the header of `layouts/default.swap.kdl`.
6. **Re-test session saving** (zellij issue #4536): open a new tab, wait a minute,
   then check that `session-layout.kdl` lists it, in
   `contract_version_1/session_info/main/` under the cache dir
   (`~/.cache/zellij` on Linux, `~/Library/Caches/org.Zellij-Contributors.Zellij`
   on macOS, `%LOCALAPPDATA%\Zellij\cache` on Windows). Repeat a few times — the
   problem is intermittent. If it reliably does, that entry under **Known issues**
   can go.
7. **Re-check the rest of Known issues** below; each entry says what to look for.

What changed in this config when moving from 0.44.x to 0.45.1 is recorded in
`CHANGELOG.md`.

## Known issues (zellij 0.45.1)

zellij behaviors this config works around or documents. One place, so an upgrade
only needs one pass.

- **The saved session isn't reliably kept current** (upstream
  [#4536](https://github.com/zellij-org/zellij/issues/4536),
  [#4129](https://github.com/zellij-org/zellij/issues/4129)). zellij is meant to
  re-save every `serialization_interval` (60 s here), but in testing tabs, panes
  and directory changes made after startup were sometimes never written, while
  other changes (a newly started nvim) were. No firm rule emerged, and no config
  fixes it. Re-test with step 6 of **Upgrading**.
- **`serialize_pane_viewport` vs the docs' `pane_viewport_serialization`**
  ([#3987](https://github.com/zellij-org/zellij/issues/3987)). The parser accepts
  only the former; the docs name is silently ignored. Don't "fix" it.
- **A top-level `unbind` misses keys bound in several contexts** — `Ctrl+g` in
  particular, so this config unbinds it inside each block (see **Debugging**).
- **The mouse wheel enters Scroll mode** (since 0.45.0). `scroll_mode_sync false`
  restores the old behavior; it's commented in `config.kdl`.
- **`explicit_theme_hue` is a pin, not a fallback** — it overrides what the
  terminal reports (see **Theme**).
- **`zellij setup --check` misses two things**: unknown option keys (silently
  ignored) and layouts, unless you pass `--layout <name>`.
- **Windows: `kill-session` errors or `attach` hangs** after a terminal crash
  orphans a server ([#4915](https://github.com/zellij-org/zellij/issues/4915)) —
  see **Troubleshooting**.

## Debugging

Zellij fails *quietly* far more often than it errors — an unknown or misspelled
config key is silently ignored (this is the single most common "my change did
nothing"). Tools, roughly in order of use:

1. **Validate the config.** `zellij setup --check` reports syntax errors and some
   problems. Note it does **not** flag unknown option keys, so a typo'd option
   passes clean while doing nothing, and it parses a layout only when you name it:
   `zellij --layout dev setup --check`.
2. **Diff against the real option names.** `zellij setup --dump-config` prints the
   full default config with the *exact* key names the parser accepts. When a
   setting seems ignored, grep that output for it — if your spelling isn't there,
   that's your bug. (This is how you'd catch the `serialize_pane_viewport` vs
   `pane_viewport_serialization` docs trap: the dump has the former, the docs say
   the latter.)
3. **Read the log.** It lives in the temp dir, not the cache dir:
   `/tmp/zellij-$(id -u)/zellij-log/zellij.log` on Linux and macOS,
   `$env:TEMP\zellij\zellij-log\zellij.log` on Windows. Plugin errors, panics, and
   command failures land here. (The `RUST_BACKTRACE` in `config.kdl` only reaches
   programs in panes, not zellij itself.)
4. **Run verbose.** `zellij --debug` writes much more detail to the log — use it
   when chasing plugin or resurrection behavior.
5. **Inspect a resurrected session.** Serialized sessions are just layouts under
   the cache dir (`contract_version_1/session_info/<name>/session-layout.kdl`).
   Open one as a separate session with `zellij -s inspect -n <path>` to see
   exactly what zellij thinks was running (useful when a command comes back
   "wrong"). Not `zellij --layout <path>`: with this config that just joins a
   running `main` and ignores the layout (see **Layouts**).
6. **Plugin cache.** If a plugin behaves oddly after a version bump, clear the
   plugin cache with the commands in **Clearing the plugin cache** (they keep your
   saved sessions) and restart — zellij re-downloads.

**Rule of thumb:** if an option "does nothing," suspect a name mismatch first
(step 2), not a bug. The config's own comments flag every key where the docs and
the parser disagree.

**Unbinding a default key that doesn't stick?** A top-level `unbind "Some key"`
does not reliably remove a key that the defaults bind in more than one context
(e.g. Ctrl+g, bound in both `shared_except "locked"` and `locked`). It'll parse
fine and silently do nothing. Unbind it *inside each mode block where the default
binds it* instead — that's why this config unbinds Ctrl+g in the `locked` and
`shared_except "locked"` blocks, not at the top level. To find where a key is
bound by default, `zellij setup --dump-config | grep -n "Your key"`.

**A one-line block that won't load?** zellij's KDL parser does not treat a
closing `}` as the end of a node on the same line. `pane { name "x" }` and
`ui { pane_frames { rounded_corners true } }` both fail — in `config.kdl` *and*
in layouts. On one line, end every node with `;`, including the last one and each
closed block: `pane { name "x"; }`, `ui { pane_frames { rounded_corners true; }; }`.
Spread over several lines, newlines do this and no `;` is needed. Also: zellij
0.45.1 reads **KDL v1 only** — v2 syntax like `#true` is a parse error. (Both
verified on 0.45.1; `check.sh` check 11 flags the missing-`;` case.)

**Before committing edits, run the consistency linter.** `./check.sh` (from any
directory) catches the drift this repo is prone to — the same fact in `config.kdl`,
the README and the cheatsheets, with one copy gone stale. It checks:

- version strings, the `serialize_pane_viewport` spelling, and the cheatsheets'
  resurrection badges against the config;
- every plugin pin matching the README and the cheatsheets;
- KDL brace and HTML tag balance;
- one-line KDL blocks missing their `;` (see the tip above);
- every layout having its `.swap.kdl`, so `Alt+[` / `Alt+]` work;
- every pinned plugin having a well-formed checksum in `plugins.sha256`, and
  the bundled copy in `plugins/` matching it (none missing, stale or unpinned);
- with `zellij` on your PATH: that `config.kdl`, every layout (with its swap
  file) and the example theme parse; that the swap files still match zellij's
  built-in ones; and that every `Alt`/`Ctrl`/`F` shortcut the docs mention
  (`Alt+n`, `Alt + [`, `Ctrl p`, `F12`, …) is actually bound. Without zellij
  these are skipped, not failed.

It's read-only and portable (bash 3.2+, grep, sed, awk — tested with BusyBox's
minimal tools as a stand-in for macOS/BSD, and under Git Bash on Windows).
Exit 0 means clean; INFO lines mark intentional cases (like the "why we don't use
autolock" notes, or a `load_plugins` block) so you can tell them apart from real
drift. `./check.sh --updates` is separate and needs the network: it lists each
pinned plugin next to its latest GitHub release, like `zj --check-updates`.

**Run it automatically.** `hooks/pre-commit` runs `check.sh` before every commit
and blocks the commit if it flags anything (showing just the failing checks). It
checks exactly what you **staged** — the content the commit will contain — not
your working folder, so an unstaged fix can't hide a broken staged file, and an
unrelated unstaged edit can't block a good commit.
Enable it once per clone with `git config core.hooksPath hooks`; skip it for one
commit with `git commit --no-verify`. The same works on Windows: Git for Windows
runs the hook with its own bundled shell, so `git commit` from PowerShell or
cmd runs it too.

**Continuous integration.** If the repo lives on GitHub,
`.github/workflows/check.yml` runs on every push and pull request. A Linux job
runs every check with zellij installed, shellcheck on the scripts, the `tidy` HTML
validator (errors fail the build; warnings, which vary between tidy versions, are
shown as annotations), markdownlint (settings in `.markdownlint.jsonc`), a real install
through `setup.sh --offline` (from `plugins/` with the network blocked, and by
download) and `--restore`, and the `zj` launcher. A macOS job runs `check.sh`
under macOS's own bash 3.2, and `setup.sh` and `zj` under `/bin/sh`, covering
the BSD tools the scripts promise to support. A Windows job runs `zj.cmd` and
`zj.ps1` under Windows PowerShell 5.1 against a stand-in zellij, and checks
they print the same reports as `launcher/zj` under Git Bash. The downloaded zellij binary is checked against a
pinned SHA-256 and the actions are pinned by commit, like the plugins. If you bump
zellij, update `ZELLIJ_VERSION` and the two `ZELLIJ_SHA256_*` values in the
workflow too.

**How much of this is verified?** A lot, but not everything. `CHANGELOG.md` (at the
repo root) records what was run against the real zellij 0.45.1 binary and when,
and which claims were later found wrong — the 2026-10-14 audit corrected 32
errors in the docs, config and scripts that earlier passes had missed (cache-clear
steps that deleted saved sessions, wrong log paths, a zjstatus example with
made-up keys, among others). Treat a claim without a
CHANGELOG entry as unverified. `cheatsheets/verification-checklist.html` covers
what only your own machine can confirm (colors, clipboard, mouse, notifications).

## Troubleshooting

- **"Theme not found"** — verify the name with `zellij setup --dump-config | grep theme`,
  or list built-ins: https://zellij.dev/documentation/theme-list.html
- **Status bar shows garbled icons** — your font lacks Nerd Font glyphs. Either
  install a Nerd Font (recommended) or uncomment `simplified_ui true` in `config.kdl`.
- **Copy doesn't work** — your terminal probably doesn't support OSC52. See
  the Clipboard section above.
- **Config not picked up** — check the search order with `zellij setup --check`.
  The first existing path among `$ZELLIJ_CONFIG_DIR`, `~/.config/zellij`
  (Linux **and** macOS, and going by zellij's source Windows too — it wins even
  when `XDG_CONFIG_HOME` is set), then
  `$XDG_CONFIG_HOME/zellij` on Linux, the OS default (`~/Library/Application Support/org.Zellij-Contributors.Zellij`
  on macOS, `%APPDATA%\Zellij\config` on Windows), and the
  system dir (`/etc/zellij`, or `C:\ProgramData\Zellij` on Windows) wins.
- **A setting seems ignored** — zellij silently skips unknown option names, and
  `setup --check` won't flag them. Diff against `zellij setup --dump-config`
  to verify spelling.
- **Scroll mode `e` (edit scrollback) does nothing** — it just snaps back to
  Normal mode. That action opens the buffer in `$EDITOR`/`$VISUAL`; if neither
  is set (common on Windows) there's nothing to launch. Set `$EDITOR` in your
  environment (`export EDITOR=nvim`, or on Windows
  `[Environment]::SetEnvironmentVariable("EDITOR","notepad","User")` then
  restart), or uncomment `scrollback_editor` in `config.kdl`.
- **A plugin won't load / hangs on first use** — it's fetched from its URL on
  first use, so this is almost always no network (or a corporate proxy). Either
  get on a network for that one launch, or set it up to load from disk — see
  [Offline / air-gapped machines](#offline--air-gapped-machines). If you changed
  a plugin URL and the old one still loads, it's the cache — see
  [Clearing the plugin cache](#clearing-the-plugin-cache).
- **Alt+key does nothing inside nvim / the shell eats it** — you're in Normal
  mode and zellij is intercepting `Alt+h/j/k/l`, `Alt+f`, `Alt+n`. Locking is
  manual: press `F12` on entering the editor, `F12` again on leaving. The status
  bar shows `LOCKED` when zellij is passing everything through.
- **F12 does nothing** — a few terminals bind F12 themselves (or it's swallowed
  by a window manager). Re-add `bind "Ctrl g"` in the `locked` and
  `shared_except "locked"` blocks, or pick another free key.
- **zellij-forgot popup — formatting / completeness** — the plugin's auto-load
  of live bindings renders ragged `Mode: X, Action: Y` rows, de-dupes multi-key
  actions, shows custom binds as "Unknown Action", and its search box rejects
  `+` (type `ctrl s`, not `Ctrl+s`). So this config sets `LOAD_ZELLIJ_BINDINGS
  "false"` and instead supplies a single curated, uniformly-formatted, searchable
  list in the `Ctrl+o h` bind (search the label text — "pane", "scroll", etc.).
  Edit that list to add anything you want; set the flag back to `"true"` if you'd
  rather have auto-load. For an exhaustive, version-exact reference,
  `zellij setup --dump-config` prints **every** default binding, and the bundled
  `cheatsheets/*.html` are the searchable full reference (Ctrl+F).
- **Windows: `kill-session`/`kill-all-sessions` errors with `Os { code: 2 …
  cannot find the file specified }`, or `attach` hangs forever**, and the
  session keeps showing in `zellij ls`. Known zellij Windows bug
  (zellij-org/zellij#4915), not the config — usually after a terminal crash
  orphans a server. `zellij ls` lists *active* sessions by reading the socket
  dir, which on Windows lives in **`%TEMP%\zellij\contract_version_1\`** (e.g.
  `C:\Users\<you>\AppData\Local\Temp\zellij\…`) — **not** in AppData/cache.
  Clear it in this order:
  1. **Kill the process first** (a live server recreates its socket):
     `taskkill /F /IM zellij.exe`, then confirm with
     `tasklist | findstr /i zellij` (should print nothing).
  2. **Delete the socket dir** that backs the listing:
     `Remove-Item -Recurse -Force "$env:TEMP\zellij"`. (Type `$env:TEMP` on its
     own to see where that is. This also removes zellij's log, which lives there.)
  3. `zellij ls` — should now report no active sessions. A *resurrectable*
     entry is separate; clear those with `zellij delete-all-sessions`, or by
     deleting `%LOCALAPPDATA%\Zellij\cache\contract_version_1\session_info\<name>`.
- **zjstatus: no git branch in the bar** — the widget runs `git` in the directory
  zellij was *started* from, not the focused pane's (zjstatus has no way to follow
  panes). Start zellij inside the repo, or pin one with an absolute path:
  `command_git_branch_cwd "/abs/path/to/repo"` in `layouts/zjstatus.kdl`. Outside a
  repo the widget is simply blank.
- **zjstatus: the bar shows only `/n)` (or a truncated `…Allow? (y/n)`)** — that's
  zjstatus's permission prompt, shown inside the one-row bar so only its tail is
  visible. It's asking to allow ReadApplicationState, ChangeApplicationState and
  RunCommands (the last for the git-branch widget). Pressing `y` from your shell
  does nothing — the keystroke goes to the shell. **Click on the status bar** to
  focus the plugin (mouse_mode is on), then press `y`; the bar renders right after.
  Re-grant after any zjstatus version bump (the wasm changes, resetting the grant).
  To avoid the RunCommands request entirely, delete the `command_git_branch_*`
  lines in `layouts/zjstatus.kdl`.
- **"Failed to parse layout" after editing a layout** — most often a one-line
  block missing its `;`: `tab name="x" { pane }` fails, `tab name="x" { pane; }`
  (or the multi-line form) works. See the one-line-block tip under **Debugging**;
  `./check.sh` flags these.
- **zjstatus: frames flicker, or a stray frame around a single pane** — zjstatus
  manages pane frames itself, so it needs `pane_frames false` in `config.kdl`
  (keep `pane_frame_style "full"` + `rounded_corners` — they still style the
  frames zjstatus toggles on when a tab splits). Don't want it global? Leave
  `pane_frames true` and press `Ctrl+p` then `z` to toggle frames off for the
  current session only. See the ⚠ FRAMES note in `layouts/zjstatus.kdl`.
- **`setup.sh` — "can't find config/config.kdl"** — run it from inside the
  unpacked archive (it installs the files sitting next to it). For a different
  target dir, set `ZELLIJ_CONFIG_DIR` before running. `--offline` installs
  from `plugins/` and needs `curl` or `wget` only for a file that's missing
  there or doesn't match its checksum. It has *every* plugin in place and
  verified before touching the config: if one fails it says which, exits 1, and
  leaves the config on its https URLs (never half-rewritten). `--dry-run` shows
  what it would do without touching anything.
- **Windows: `check.sh` says plugins.sha256 has lines "config.kdl no longer
  pins", or a script fails with `$'\r': command not found`** — the files have
  Windows (CRLF) line endings. That happens in a git clone made without this
  repo's `.gitattributes` (Git for Windows converts by default), or after an
  editor converted them. Unpack the archive again, or re-clone; `.gitattributes`
  now makes every checkout LF.
- **`zj` never says anything** — that's normal: it's silent unless a newer
  plugin release exists, and checks only once a month. Run
  `zj --check-updates` for the full report. Exit code 2 there means it couldn't
  reach GitHub: curl and wget honor `https_proxy`, and on Windows the system
  proxy settings apply. `zj: command not found` means the launcher isn't on
  your PATH — see [Checking for plugin updates](#checking-for-plugin-updates).
