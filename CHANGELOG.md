# Changelog & verification record

`docs/CONFIGURATION.md` is the how-to: install, use, troubleshoot. This file is the
record behind it — what has been verified against the real zellij binary, what
changed and why, and which bugs were found along the way. Nothing here is needed
to *use* the config; it's for when you want to know how much to trust a claim,
or why something is the way it is.

Entries describe the implementation at the time of each change. In particular,
the archive-era records below mention removed plugins, an internal `config/`
directory, old shell implementations and numbered checks that no longer exist.
Use [the configuration guide](docs/CONFIGURATION.md) and
[the current validation map](docs/AUDIT_FIXES.md) for today's commands and
guarantees. Historical interactive results are retained as recorded, not claimed
as freshly repeated by each documentation review.

---

## Unreleased — documentation and comment review

- Checked the current guides, generated references, cheatsheets, KDL examples,
  wrappers and Python comments against the implementation and selected Zellij
  binary. Corrected removed-shortcut references and clarified preference
  precedence, runtime snapshots, deployment ownership and validation limits.
- Distinguished current instructions from the historical archive verification
  records below. This review adds explanations without changing application or
  launcher behavior.

## 2026-10-26 — portable defaults and local preferences

- Removed the shared singleton `main` session, `RUST_BACKTRACE` pane export,
  F12 lock override, Denver timezone and Git status command. Standard `Ctrl+g`
  locking and a UTC zjstatus clock are the portable defaults.
- Added schema-1 `.zellij-config-local.json` preferences with a `configure`
  command, preview/reset support and a `classic` compatibility preset. The
  launcher renders private config/layout snapshots; setup preserves and validates
  the target's preferences without baking them into deployed KDL or importing
  source preferences. Plain Zellij always ignores local JSON.
- Added a single-shell `minimal` layout with matching swaps, and explicit
  `ZJ_PYTHON`, `ZJ_ZELLIJ_BIN` and `ZJ_STATE_DIR` overrides. Restored
  `check.sh --updates [CONFIG_FILE]` forwarding.
- Added portability/preference/entry-point regressions and a migration checklist.
  Native interactive behavior remains an on-machine validation task.
- Checked current stable plugin releases and freshly downloaded artifacts.
  Existing zjstatus, monocle and multitask pins and checksums remain unchanged.

## 2026-10-23 — direct clones and download-first plugin fallback

- Improved launcher startup: parallel missing downloads, a five-minute failure
  cooldown, reuse of unchanged backup files, and detached background release
  checks with cached notices. Live explicit update checks remain available.
- Moved `config.kdl`, layouts and themes to the repository root so the checkout
  itself can be the active config directory on Linux, macOS and Windows.
- Made the checked-in launcher prepare plugins at startup, without a setup step:
  verified prior download, verified HTTPS download, then verified bundled backup.
  Added `ZJ_OFFLINE=1` for deliberately disconnected systems.
- Kept generated config snapshots and plugin downloads in private per-user state,
  preserving tracked files and previous running sessions' selected generations.
- Updated optional deployment, explicit upgrades, checks, docs and native CI for
  the root layout. Optional online deployment also prefers downloads to backups.
- Added regressions for direct Git clones without setup, real parser validation,
  bad/unavailable downloads, offline operation, cache corruption, source edits,
  literal arguments and KDL location rewriting.

## 2026-10-22 — audit fixes and explicit version upgrades

- Replaced duplicated installer/launcher policy with shared Python 3.10+
  standard-library helpers and retained shell/PowerShell/cmd entry points.
- Staged and validated the full installation before publication; added private
  snapshots, exclusive OS locks, rollback, interruption recovery, safe symlink
  handling, exact restores and numeric legacy backup ordering.
- Made hashing/input failures fatal and removed fail-open hook/CI paths.
- Fixed config selection, comment parsing, case-sensitive tag identity,
  per-config/pinset cache keys, redirect handling and incomplete-scan retries.
- Included upstream MIT notices. Removed the unlicensed zellij-forgot binary
  and opened Zellij's built-in keybinding screen from the same shortcut.
- Added canonical versions.json, generated references and explicit verified
  upgrade/install commands. Existing app/plugin version pins remain selected
  until an update command is run deliberately.
- Added deterministic fault-path tests, real binary/entry-point tests and
  native Linux/macOS/Windows CI with Python 3.10 and 3.14. Tooling dependencies
  are locked; network smoke checks are separated from regression tests.

The following verification records describe historical archive versions. Current
checks and platform boundaries are documented in `docs/AUDIT_FIXES.md` and CI.

## Historical verification status — zellij 0.45.1

Everything below was run against the real 0.45.1 binary, not reasoned about.
Where the 2026-10-14 audit found a claim broader than what was actually tested,
or the config has changed since, the line says so ("corrected 2026-10-14").

**Config and files**

- `zellij setup --check` passes ("Well defined"). That check validates enum
  values, keybind actions and modes (bogus ones error) but *not* unknown option
  keys or theme names, so those were checked separately: every option key diffed
  against `zellij options --help`, and `catppuccin-mocha` (plus every theme the
  README suggests) confirmed built into the binary.
- All four layouts then shipped loaded (with a broken-layout negative control).
  `welcome.kdl` has since been removed — zellij's built-in `welcome` layout is
  the same — and `check.sh` check 8 now parses the remaining three, each with its
  swap file (corrected 2026-10-14).
- All four plugin pins download as valid Wasm and load on 0.45.1; multitask is
  pinned to its matching v0.45.1 build.
- The runtime `--debug` log shows no config-caused warnings.
- The example theme parses.

**Behavior** (driven through tmux `send-keys` / `capture-pane`)

- Plain `zellij` opens session `main` in Normal mode with `main` + `shell` tabs.
- F12 locks and unlocks; locked mode really passes Alt-keys through; Ctrl+g does
  nothing in either mode; Ctrl+q is unbound; `Ctrl+o q` quits; `Ctrl+o d` detaches.
- `Ctrl+t` then `n` adds a tab; the forgot popup opened with the curated list.
  (Then on Ctrl+y; moved to `Ctrl+o h` on 2026-10-14, which was parse-checked but
  not driven through tmux.)
- `env { RUST_BACKTRACE }` reaches panes; `on_force_close "detach"` survives a
  killed client; rounded frames render.
- Closing the working tab's pane (what `:qa` does) leaves the session alive in the
  `shell` tab.

**Crash recovery** (corrected — an earlier version of this record overstated it)

- After `kill -9` of the zellij server, `zellij ls` lists `main` as "EXITED -
  attach to resurrect"; the stale socket left behind blocks nothing.
- Which command resurrects was proven with a marked snapshot (an extra tab added
  to the saved file): `zellij attach main` and `zellij attach --create main`
  resurrect it; **plain `zellij` starts a fresh `main` and discards the saved
  one**. (The earlier "comes back with `main` and `shell`" check couldn't tell the
  two apart — a fresh session has those tabs too.)
- **zellij 0.45.1 doesn't reliably keep the saved copy current.** In several runs
  `session-layout.kdl` stayed frozen at startup while `session-metadata.kdl` kept
  updating (the symptom in upstream issue #4536), including after a resurrection
  with the built-in layout; in other runs, with the shipped settings, later
  changes (a newly started nvim) were saved. The results were inconsistent and
  couldn't be reduced to a firm rule, so the docs state only that recent changes
  may be missing.
- The welcome layout's layout-level `session_serialization false` works: a
  welcome session writes no snapshot and is not offered for resurrection.
  (Tested with the shipped `welcome.kdl`, a copy of the built-in, which carries
  the same line.)

**zjstatus**

- Every widget renders once permission is granted: mode, session, tabs, git
  branch, date/clock; new tabs inherit the bar.
- The grant is stored in `permissions.kdl` in zellij's cache dir
  (`~/.cache/zellij` on Linux), keyed by the plugin URL — which is why a version
  bump asks again, and why the cache-clear steps keep that file.
- Layout-level `pane_frames` is not possible: inside the `layout {}` block it
  breaks the layout, and after the block it is silently ignored.
- The zjstatus layout's two tabs (`main` + `shell`) both render in the bar,
  closing `main`'s pane leaves the session alive in `shell`, and both tabs come
  back after a crash + reattach.

**Protocol level** (raw PTY capture)

- The kitty-keyboard enable sequence is emitted only when the option is on.
- OSC 9/99 notifications are forwarded with `host_notification_protocol "auto"`
  and stripped with `"off"`.

**Docs and tooling**

- Keybinds and `zellij` subcommands cited in the docs were cross-checked against
  the binary, and KDL snippets parse- or load-tested — but not exhaustively
  (corrected 2026-10-14): that audit still found a zjstatus snippet using keys
  zjstatus doesn't have, resize keys described as acting on all panes, and a
  `.multitask` example with `//` comments. `check.sh` check 10 now covers every
  shortcut spelling in all docs.
- All fourteen `check.sh` checks negative-tested (each catches a planted bug);
  checks 5, 7, 8, 10 and 12, changed on 2026-10-14, were negative-tested again,
  and check 14 (new that day) flags a corrupted, a missing and an unpinned file
  in `plugins/`.
- Both scripts are shellcheck-clean, and both run with BusyBox's minimal tools
  (a stand-in for macOS/BSD); `check.sh` uses nothing newer than bash 3.2.
  (The 2026-10-14 launcher changes to `setup.sh` and `check.sh`, and
  `launcher/zj` itself, are shellchecked by CI only; no shellcheck was
  available locally.)
- The `zj` launcher and `setup.sh --offline` from the bundled `plugins/`: see
  the 2026-10-14 "Plugin update check" entry below for what was run.
- `setup.sh`: default, `--offline` (curl and wget paths), `--dry-run`, re-run
  backups and a symlinked config dir all verified; the README's Windows block
  verified in real PowerShell 7.4 (install, then backup on re-run, no nesting).
- The cheatsheets pass the `tidy` HTML validator with no errors or warnings; the
  README and CHANGELOG render correctly in a strict CommonMark renderer.
- Swap layouts: `Alt+]` rearranges panes in the default, dev and zjstatus
  layouts, with exactly one status bar each; the zjstatus bar names the active one.
- `Ctrl+o m` opens monocle (floating, rooted at the focused pane's directory; search
  works) and `Ctrl+o t` opens multitask for that directory, exactly like the
  command in multitask's README (that bind is commented out since 2026-10-14:
  opt-in, Unix-only). Not verifiable here: multitask running commands on save —
  its own documented command didn't either (see the checklist).
- `setup.sh --offline` verifies all four plugins against `plugins.sha256` with
  `sha256sum`, `shasum` (macOS) and `openssl`; a tampered or missing checksum is
  refused and the config left untouched. `--restore` brings back the latest
  backup exactly, is undone by a second `--restore`, keeps a symlinked config dir
  a symlink, and works under BusyBox.
- `hooks/pre-commit` blocks a commit with a planted bug (showing only the failing
  checks), passes a clean one in about half a second, and is skipped by
  `--no-verify`.
- CI workflow: passes actionlint; every Linux-job step run locally passes, and
  planted problems (broken HTML, bad Markdown, an unquoted shell variable) fail
  it at the right step. The macOS job can only run on GitHub. The launcher
  steps added on 2026-10-14 were run locally only on Windows: the Windows job's
  script passes, while the Linux and macOS `zj` steps run first on GitHub.

**Not verifiable headless** — confirm on your own machine with
`cheatsheets/verification-checklist.html`: exact theme colors, clipboard (local
and over SSH), mouse behavior, desktop notifications, and nvim itself inside a
resurrected pane.

---

## History

Newest first. Entries before 2026-10-14 are grouped by piece of work and
weren't dated.

### Canonical archive name (2026-10-14)

The README's unpack, in-place and update examples now use
`28_zellij_audited_2026-10-14.zip` (the name in `#bk\`), with a note that the
file can be renamed.

### Removing this config (2026-10-14)

The README's Install section gained **Removing this config**, for Linux, macOS
and Windows. It moves the config dir aside under the installers' backup name,
so `./setup.sh --restore` or the Windows undo steps bring it back. It also
covers unsetting `ZELLIJ_CONFIG_DIR` for in-place use, removing the `zj`
launcher and its state, and leaving zellij's cache (saved sessions, plugin
grants) alone. Verified on Windows against a scratch dir: once the config dir
is moved aside zellij falls back to its defaults, and the undo steps restore
it unchanged, even with no current config dir. The Linux/macOS commands are
plain `mv`/`rm` and weren't run here.

### Setup, update and undo steps for every OS (2026-10-14)

**Docs.** The README's Install section now covers each step on Linux, macOS
and Windows:

- what each OS needs;
- unpacking the archive, which has no top-level folder;
- installing it;
- using the archive in place: unpacked into `%APPDATA%\Zellij` on Windows, or
  with `ZELLIJ_CONFIG_DIR` on Linux and macOS;
- updating to a newer archive, either installed or in place, including
  deleting files a release removed;
- undoing an install. Windows had no restore steps; it now has PowerShell ones.

Updating a pinned plugin gained PowerShell commands for the download and the
checksum. The docs also say that the git hook works from PowerShell and cmd.

**Fixes**

- **`check.sh` failed in any git clone on Windows.** Git for Windows checks
  text files out with CRLF line endings by default, so each `plugins.sha256`
  line ended in a CR and check 13 reported every pin as missing. The hook
  blocked a clean commit for the same reason. `.gitattributes` now checks every
  text file out with LF, except `zj.cmd`, which stays CRLF.
- **`setup.sh` refuses to install the archive onto itself.** With
  `ZELLIJ_CONFIG_DIR` pointing at the archive's own `config/` (the new in-place
  mode), it would have copied each file over itself, and `--offline` would have
  rewritten the repo's `config.kdl`. It now says zellij already reads those
  files, and stops.

**Verified** (Windows 11, zellij 0.45.1; Linux/macOS commands under Git Bash):

- **Windows steps, against scratch folders:** `Expand-Archive` unpacking (every
  file intact, `zj.cmd` still CRLF); the install steps (the old config backed
  up, the new one parses); undo, and undoing the undo.
- **Windows in place:** a first install, and an update over a copy of the
  2026-10-14 audit archive. After the update, `welcome.kdl` is gone, every file
  matches the new archive, the backup holds the old config, and the config
  parses.
- **The git hook from PowerShell:** before the fix it blocked a clean commit,
  and now it passes it. It still blocks a planted brace error.
- **Linux/macOS commands:** `unzip -d` into a new folder; the in-place update
  (`cp -R` backup, `unzip -o`, `rm`) leaves a tree identical to a fresh unpack.
  With `ZELLIJ_CONFIG_DIR` set, zellij reports the repo's `config/`, and
  `setup.sh` and `setup.sh --offline` stop with exit 1, leaving the repo's
  config untouched.
- **A clone with `core.autocrlf=true`:** text files come out LF, `zj.cmd` CRLF
  and the `.wasm` files unchanged, and `check.sh` passes in it.
- **Not verified:** the commands on real Linux and macOS, and `zj` in in-place
  mode end to end (its two halves were checked separately).

### Plugin update check and bundled plugins (2026-10-14)

Pinning keeps the plugins from changing under you, but it also means nothing
tells you when they're out of date. This adds a monthly check, and carries the
plugin files themselves so an offline machine needs no download.

**New**

- **`zj`, a launcher that checks monthly for newer plugin releases.** zellij
  has no startup hook, so `zj` starts zellij itself. There are two versions:
  `launcher/zj` (POSIX sh) for Linux and macOS from any shell, fish included,
  and `zj.cmd` + `zj.ps1` for Windows. (Windows panes run cmd.exe, which has no
  profile, and a PowerShell profile hook would be blocked under an AllSigned
  policy.) Every 30 days it compares each pinned GitHub release URL in the
  config zellij loads with that repo's latest release. It reads the tag from
  where `releases/latest` redirects, which isn't rate-limited like the API. It
  lists newer releases before starting zellij and changes nothing. A check that
  can't reach GitHub is silent and is retried a day later. There's no plugin
  list, so a pin added the same way is covered automatically.
  `zj --check-updates` and `./check.sh --updates` report on demand. A single
  Python script for every OS was considered and rejected: Windows has no Python
  by default, and an offline machine is the hardest place to get one.
- **The four pinned plugins ship in `plugins/`** (about 10 MB). `setup.sh
  --offline` installs them from there, downloading only a file that's missing
  or doesn't match its checksum, so with a complete bundle it no longer needs
  curl or wget. If the config dir's path contains a space (macOS's
  `Application Support`), the files go to `~/.local/share/zellij-config/plugins/`
  instead, because zellij's handling of spaces in `file:` paths is untested.
- `setup.sh` installs `zj` without a PATH edit. It uses `~/.local/bin` if
  that's on PATH, else the folder holding `zellij` if writable. Failing both,
  it uses `~/.local/bin` and prints how to add it to PATH, fish included. It
  never replaces a `zj` that isn't this launcher.
- `check.sh` check 14: every file in `plugins/` matches `plugins.sha256`, none
  is missing or unpinned, and no two pins share a file name.
- CI: shellcheck covers `launcher/zj`. The Linux job installs `--offline` from
  `plugins/` with the network blocked, and by download from a copy without
  `plugins/`, then runs `zj`. The macOS job runs `zj` under `/bin/sh`. A new
  Windows job runs `zj.cmd`/`zj.ps1` under Windows PowerShell 5.1 with a stub
  in place of zellij, and requires their reports to match `launcher/zj`'s byte
  for byte.
- `.gitattributes` fixes line endings: LF for the sh scripts (a CRLF checkout
  breaks `#!/bin/sh`), CRLF for `zj.cmd`.

**Doc bugs found**

- **The offline steps said to create `~/.config/zellij/plugins/` "on every
  OS".** zellij uses `~/.config/zellij` first whenever it exists. On macOS
  (documented) and Windows (from zellij's source), that folder would replace
  the real config dir with one holding no `config.kdl`. The Windows case wasn't
  tried here, because it would have hidden this machine's live config. The
  README and plugins cheatsheet now keep the files in the config dir.
- **The README's Windows example `file:/C:/…` doesn't load.** zellij 0.45.1 on
  Windows turns it into `C:/C:/…` (os error 123). `file:C:/…` and `file:~/…`
  load; all three were tried with a real plugin.
- The README had no Windows offline steps; it now has PowerShell ones.

**Verified** (Windows 11, zellij 0.45.1; the sh scripts under Git Bash)

- `launcher/zj --check-updates`: exits 0 for the shipped pins, and 1 for an
  older zjstatus pin, naming the newer tag. It exits 2 behind a dead proxy
  (after about 4 s) and for a repo that doesn't exist. `file:` paths (with
  spaces) and non-GitHub URLs are listed as not checked. Without FILE it reads
  the config zellij reports.
- `launcher/zj` at startup: a due start shows the report, then runs zellij, and
  sets the next check 30 days out; the second start doesn't check. An offline
  due start is silent and retries a day later. `ZJ_NO_UPDATE_CHECK` is honored
  and arguments pass through.
- `zj.cmd` + `zj.ps1` (Windows PowerShell 5.1): the same behavior. A stamp 29
  days old doesn't check and 31 days old does. Quoted arguments with spaces pass
  through. A start with no check due takes about 0.3 s, against 0.09 s for
  plain zellij. Its reports are byte-identical to `launcher/zj`'s on the same
  files.
- `setup.sh`, launcher install: on PATH, next to zellij, neither (prints the
  PATH advice), a foreign `zj` kept, a shadowing `zj` noted, re-install,
  `--dry-run`, and `--restore` leaving it alone.
- `setup.sh --offline` with the network blocked installs all four plugins from
  `plugins/`, with matching checksums. With one bundled file corrupted, one
  missing and no network, it names both and leaves the config on https. A
  config dir with a space puts the files in the fallback dir.
- The README's Windows offline steps, run on a scratch copy of the config: the
  locations are rewritten, the UTF-8 is kept with no BOM added, and it parses.
- `check.sh`: check 14's three failure cases; `--updates`; an unknown argument
  exits 2.
- The Windows CI job's script passes locally.
- **Not verified here:** Linux and macOS natively (CI covers Ubuntu's dash and
  macOS's `/bin/sh`), and fish. `zj` is an executable with a `#!/bin/sh` line,
  so the calling shell shouldn't matter. Also not verified: shellcheck on the
  changed scripts (CI only), and whether zellij accepts spaces in `file:`
  paths (avoided instead).

### Audit fixes (2026-10-14)

A full audit of the previous archive found 32 problems in the docs, config and
scripts, and the fixes turned up three more. All are fixed here.

**Behavior changes**

- **The keybinding popup moved from a global Ctrl+y to `Ctrl+o h`.** Ctrl+y
  took readline's yank, and nvim's `<C-y>` (scroll up; accept completion)
  whenever F12 wasn't pressed first. The docs' suggested alternative, `Ctrl+o f`,
  would have overridden 0.45.1's own `f` (ToggleHostFullscreen); `h` is free.
- **`Ctrl+o t` (multitask) is opt-in** — commented out like `Ctrl+o e`. It runs
  `sh -c` with `$SHELL` and `$(pwd)`, so it's Unix-only, and a second press
  restarts multitask rather than focusing it.
- **`layouts/welcome.kdl` is gone.** It was a copy of zellij's built-in welcome
  layout (same plugin, same `session_serialization false`), so it could only
  drift; `zellij -n welcome` still works. `setup.sh` points out a leftover copy
  from an earlier install.
- **zjstatus layout:** formats for all 14 modes (Move, Search, EnterSearch,
  RenameTab, RenamePane and Prompt had none); the git branch refreshes every
  15 s instead of 5 (each tab's bar is its own plugin instance, so N tabs ran
  `git` N times); `datetime_timezone "America/Denver"` — change it to yours.
- The layouts spell the bar `compact-bar`, like the swap files and zellij's
  built-ins (two used `zellij:compact-bar`; both resolve).

**Config**

- `config.kdl` went from 576 to 364 lines. Restated defaults carry a trailing
  `// default`, so the real customizations stand out. Fixed comments: the
  inverted `hide_session_name` note, the mouse block (three options, not two,
  and what each does), a dangling "below", the "INTENTIONALLY MINIMAL" heading
  over 180 lines, and the session-mode list (0.45.1 also binds `s`, `f`, `[`,
  `]`). `simplified_ui` and `post_command_discovery_hook` are now listed.
- New finding: `explicit_theme_hue` *pins* dark or light and overrides what the
  terminal reports. The docs called it a fallback for terminals that don't
  report their mode; corrected everywhere, including the Migration entry below.

**Docs**

- **The cache-clear steps deleted saved sessions and plugin grants.** The cache
  dir also holds `contract_version_1/` (resurrection data) and `permissions.kdl`.
  The steps now keep both, with bash and PowerShell commands and a warning.
- **The log path was wrong on every OS.** It's `/tmp/zellij-<UID>/zellij-log/`
  on Linux and macOS and `%TEMP%\zellij\zellij-log\` on Windows, not the cache.
- New finding: the README said `env { RUST_BACKTRACE }` makes zellij's own
  crashes log backtraces. It only reaches programs in panes.
- Plugins cheatsheet: the zjstatus example used keys zjstatus doesn't have
  (`color_mode_*`, `format_tab*`, `datetime_fg`, a strftime pattern in
  `datetime`); it's now an excerpt of the shipped layout plus a widget table.
  The `.multitask` example used `//` comments in what is a shell script. URLs no
  longer break across lines inside KDL strings. Layout cards show the two-tab
  default and `zjstatus.kdl`.
- Main cheatsheet: the "complete delta from stock" now is complete; resize `=`
  and `-` act on the focused pane, not all panes; the wheel enters Scroll mode
  (0.45); session mode's `s`, `f`, `[`, `]` added; `Alt+.` dropped from the
  collision list (zellij doesn't bind it); the `unbind` note matches the
  per-block Ctrl+g finding; the legend reads "new in 0.44 / 0.45".
- README: a **Known issues (zellij 0.45.1)** section now collects every
  caveat; the "changes from stock" table is complete; the hand-kept "most
  useful keys" table is gone (the popup and the cheatsheet are the lists, and
  check 10 polices both); "inspect a resurrected session" uses
  `zellij -s inspect -n <path>` (plain `--layout` attaches to `main`); the
  zjstatus and swap-copy advice is current; `load_plugins` advice agrees with
  check 5; "cross-platform" is scoped to the config and layouts; the URL-bump
  example keeps `/releases/`; PowerShell uses `$env:TEMP`.
- Checklist: POSIX `printf '\033…'`; item 9 says to uncomment `Ctrl+o t` first;
  the timezone note matches the layout; the intro and footer no longer claim
  everything else was verified.
- The cheatsheets no longer fetch Google Fonts; local fonts are listed as
  fallbacks.
- This file: claims the audit showed were broader than what was tested are
  marked "corrected 2026-10-14" above.

**Scripts and CI**

- `setup.sh` no longer installs into `$XDG_CONFIG_HOME/zellij` on macOS, which
  macOS zellij ignores; it follows zellij's per-OS search order, including the
  macOS `Library` dir. After installing or restoring, it asks zellij which config
  dir it discovers on its own (`setup --check`'s `[CONFIG DIR]`) and warns if
  that isn't the one it wrote, then parses the config and every layout.
- `check.sh` check 8 parses each layout with its swap file (`--layout …
  setup --check`; plain `setup --check` never reads layouts, so a planted
  `split_direction="diagonal"` passed) and uses `--config-dir config`, so it
  tests the repo rather than your installed dir. Check 10 now also recognizes
  the KDL spelling (`"Alt m"`, no `+`), the `Alt+[ ] = -` keys and F-keys, which
  it used to skip — new finding: it then caught the plugins cheatsheet's unbound
  `Alt m` example. Check 11 accepts zjstatus's `{command_NAME}` placeholder
  spelling. Check 12 diffs each swap
  file against `zellij setup --dump-swap-layout compact`. Check 7 compares pins
  in the cheatsheets too. Check 5 reports `load_plugins` as INFO, not a WARN
  that contradicted the docs. The header counts four cheatsheets.
- CI pins `actions/checkout` by commit (v6.1.0), checks the zellij binary against
  the SHA-256 the release publishes before using it, and fails the `setup.sh`
  steps on any warning.

**Verified for this entry** (Windows 11, zellij 0.45.1, Git Bash):
`zellij --config-dir config setup --check` and each layout with `--layout` say
"Well defined"; `check.sh` passes clean; planted bugs — an invalid layout value,
a drifted swap file, a stale pin in a cheatsheet, three unbound shortcut
spellings — are each caught by the right check, and a `load_plugins` block is
INFO; `setup.sh` install, re-install backup, `--offline` (all four checksums),
`--restore`, `--dry-run`, the leftover-`welcome.kdl` note, a rejected layout and
a mismatched config dir (zellij shown a different dir) all behave as described;
the workflow YAML parses and the zellij checksums match the release's
`.sha256sum` files. **Not run:** the new `Ctrl+o h` popup and the zjstatus mode
colors weren't driven live; the CI jobs, macOS, shellcheck, tidy and
markdownlint weren't run here.

### Cheatsheet text contrast

- The muted grey used for notes and secondary text (`--muted`) changed from
  Catppuccin `overlay0` (#6c7086) to `overlay2` (#9399b2) in all four cheatsheets.
  Measured in a browser on every rendered text node: text below the WCAG AA
  guideline (4.5:1) dropped from about 5,080 characters to 168, and the checklist
  now passes fully. Notes on cards went from 3.4–3.6:1 to about 6:1.
- Not quite there: note text on the semi-transparent badges measures 4.45:1 (the
  estimate beforehand was about 5:1), and the separate `--subtle` grey used for
  footers and file-name links (unchanged) measures 4.44:1.
- Code examples that use #6c7086 as a real color value (the zjstatus snippet) are
  untouched; only the CSS variable changed. Print output was already dark-on-white.

### Second full test pass

- **The docs recommended plain `zellij` for recovery — which discards the saved
  session.** It only joins a *running* `main`; after a crash it starts a fresh one.
  README, `config.kdl`, `setup.sh`'s closing message, the cheatsheet and the
  checklist now say `zellij attach --create main` (resurrects, joins or creates).
- **Documented that zellij 0.45.1 doesn't reliably keep the saved session
  current** (upstream #4536/#4129) everywhere recovery is described, with an
  Upgrading step to re-test it. (A first draft stated a precise "only the startup
  state is saved" rule; later runs contradicted it, so it was softened to what the
  evidence supports.)
- **The pre-commit hook checked the working folder, not the commit.** A broken
  staged file slipped through when the fix was only in the working folder, and an
  unrelated unstaged edit blocked a good commit. It now checks the staged snapshot
  (`git checkout-index` into a temp dir).
- **CI:** `actions/checkout` v4 (Node 20) → v6, with `persist-credentials: false`;
  `apt-get update` before installing tidy; tidy errors fail the build while
  warnings (which vary between tidy versions) become annotations.
- **`setup.sh`:** a real Ctrl+C during `--offline` left a `.part` file; it now
  cleans up and exits 130.
- **`--restore` couldn't find backups from the README's manual install** (named
  `zellij.bak.<epoch>`); the manual steps now use `setup.sh`'s name format.
- `check.sh` uses an explicit `mktemp` template (older BSD `mktemp` needs one);
  the `Ctrl+o t` comment notes that a comma in a folder name can't be passed.

### Additions: shortcuts, restore, checksums, hook, CI

- **`Ctrl+o` then `m` / `t`** launch monocle and multitask, next to zellij's own
  session-mode plugin launchers (`w`, `c`, `l`, `p`, `a`); both keys were unused
  there. multitask needs the project directory at launch, which a plain plugin
  binding can't pass, so its binding runs multitask's documented launch command
  in a self-closing floating pane that opens in the focused pane's directory.
- **zjstatus bar shows the active swap layout** (hidden with a single pane;
  clicking it switches to the next one).
- **`setup.sh --restore`** puts back the most recent backup, saving the current
  config first so the restore can be undone.
- **`setup.sh --offline` verifies checksums** from the new `plugins.sha256`, and
  refuses a mismatched or unlisted file. `check.sh` check 13 keeps that file in
  step with the pins in `config.kdl`.
- **`hooks/pre-commit`** runs `check.sh` before each commit (opt-in:
  `git config core.hooksPath hooks`).
- **`.github/workflows/check.yml`**: all checks on Linux, plus a macOS job for
  bash 3.2 and BSD tools; `.markdownlint.jsonc` holds the Markdown settings.

### Full test pass of every file

- **`Alt+[` / `Alt+]` (swap layouts) did nothing** in all three layouts, although
  the docs and the keybinding popup list them. zellij pairs `NAME.kdl` with
  `NAME.swap.kdl`; its built-in layouts have one, ours didn't. Added
  `default/dev/zjstatus.swap.kdl` (zellij's own "compact" swap layouts), which
  also gives `auto_layout true` something to apply. Guarded by `check.sh` check 12.
- `auto_layout` and swap layouts were described as "golden-ratio splits" — they
  are vertical / horizontal / stacked / half-stacked arrangements.
- `check.sh` check 1 silently failed on non-GNU awk (BusyBox; likely recent
  macOS): `gsub(/{/…)` is an invalid regex there. Now `/[{]/`.
- The checklist's 8 checkboxes had no accessible name (a screen reader said just
  "checkbox"); each is now labelled by its item title.
- A `config.kdl` comment pointed to a README "Keybindings" table that doesn't
  exist; it's in "How zellij works".
- The edit-config binding now also honors `$ZELLIJ_CONFIG_FILE` when you set it
  (zellij reads that variable; it just never sets it).
- Minor: README Markdown formatting (blank lines around lists/headings, labelled
  code fences) — rendering verified unchanged; one unquoted `$(date +%s)`.
- Verified current at the time: zellij 0.45.1 and all four plugin pins were the
  latest releases (re-checked 2026-10-14: still the latest).

### Sweep of the cheatsheets and examples

- **Text was clipped off the right edge of many cards.** One CSS rule
  (`td:first-child{white-space:nowrap}`, meant for the key column) also hit
  full-width rows — which have a single cell, so it's the first child — and,
  because `white-space` inherits, every cell of tables nested inside one. Long
  notes couldn't wrap, stretched the table, and the card (`overflow:hidden`) cut
  everything off: up to 1410px on the main cheatsheet's Session Mode card, and the
  KDL cheatsheet's gotchas card lost its whole right column. Fixed in all three
  cheatsheets; measured clean in a browser from 700 to 1600px wide and when
  printed on A4 in both orientations.
- Main cheatsheet, search submode: `w` and `o` were swapped — `w` toggles
  wrap-around and `o` whole-word.
- The example theme's instructions didn't say the `.example` ending must go;
  zellij only loads `*.kdl`, and a `.kdl.example` file is silently ignored. Now
  explicit in the file and the plugins cheatsheet.
- Verified, no change needed: every keybinding row in the cheatsheets, checked
  against the real binding in the mode it names; every `zellij` command and flag;
  every stated option value; every config snippet still parses; and the example
  theme really applies once copied to `themes/my-custom.kdl` (its colors render).

### Sweep of the config folder

- The commented "edit this config" binding (`Ctrl+o` then `e`) relied only on
  `$ZELLIJ_CONFIG_FILE`, so it opened the default path unless you had set that
  yourself (zellij *reads* the variable but never sets it for panes). It now tries
  `$ZELLIJ_CONFIG_FILE`, then `$ZELLIJ_CONFIG_DIR/config.kdl`, then the default,
  and says plainly that a `--config` flag can't be followed. All three verified
  live.
- The README's reasons for not shipping `post_command_discovery_hook` were out of
  date ("every wrapper bakes in a shell assumption"); replaced with the tested
  facts and real trade-offs. It also now describes the resurrection mechanism
  precisely (an editor is saved as an *edit pane*).
- `dev.kdl` promised a "Press ENTER to run" banner; the actual prompt is "Waiting
  to run" with Enter / Esc.
- Verified, no change needed: all ten commented settings parse and are real option
  names; uncommenting the `EDITOR` line and the `dev.kdl` command examples works;
  all 32 entries of the keybinding popup (then on Ctrl+y) are correct in their
  stated mode; no custom
  binding overrides a zellij default; every `zellij …` command and flag in the
  folder exists; config edits hot-reload without a restart; a session ended by its
  last pane closing is resurrectable (`kill-session` is not).

### zjstatus "single tab" limitation was a misdiagnosis

The docs claimed zjstatus couldn't be combined with tabs declared in the layout,
so `layouts/zjstatus.kdl` started with one tab and you had to add the `shell` tab
by hand. The real cause was the one-line-block rule: the test layouts wrote
`tab name="main" { pane }` without a `;`, which fails to load with *any* status
bar (so did the "can't pre-declare a second pane either" test). With the tabs
written multi-line, zjstatus works with explicit tabs. The zjstatus layout now
ships the same `main` + `shell` tabs as the default, and the "retest on a newer
zellij" upgrade step is gone.

### Code audit of the scripts

`setup.sh`:

- A config dir that is a **symlink** (dotfiles repo) produced a "backup" that was
  just another link to the files about to be overwritten — the original config
  was lost. It now copies the real files (`cp -R "$DEST/." …`).
- Paths went through `eval`: a `$` in the path installed to the wrong directory
  while reporting success, and a backtick ran as a command. `eval` removed.
- With `XDG_CONFIG_HOME` set and `~/.config/zellij` present, it installed where
  zellij doesn't look. It now mirrors zellij's verified search order (on Linux;
  macOS still went wrong — see the 2026-10-14 entry).
- Two runs in the same second nested one backup inside the other; backup names
  now get a numeric suffix.
- A failed `--offline` download left the config half-rewritten. All downloads now
  finish (to `.part` files) before the config is touched.
- New: validates the installed config with `zellij setup --check` and warns on a
  zellij older than 0.45.

`check.sh`:

- Check 10 counted commented-out binds (and `unbind` lines) as real bindings.
- Check 6 verified nothing while serialization was on; it now checks both ways.
- Check 1 claimed to be quote-aware but wasn't; it now is, and covers the theme.
- Replaced GNU-only regex; colors only on a terminal; runs from any directory.

### zjstatus git branch never showed

The layout set `command_git_branch_cwd "{focused_pane_cwd}"` — a placeholder
that doesn't exist (zjstatus's cwd option takes a fixed absolute path), so `git`
ran in a nonexistent directory. Line removed; the branch now reflects the
directory zellij was started in, and the docs say so.

### Full-zip audit of the docs

Cheatsheet examples that could not work as printed:

- One-line blocks without `;` — zellij does not treat `}` as ending a node on the
  same line; the main cheatsheet's layout-anatomy example failed to load. Now
  guarded by `check.sh` check 11.
- The plugins cheatsheet still showed the proven-broken top-level
  `unbind "Ctrl g"`.
- A second shorthand theme snippet (see below).
- A claim that zellij reads KDL v2; 0.45.1 is v1-only.
- `zellij -l <layout>` described as "start with a layout" — with this config it
  silently attaches to a running `main` and ignores the layout. Use
  `zellij -s <name> -n <layout>`.
- The cheatsheet said plain `zellij` makes a new randomly named session; with this
  config it attaches to or creates `main`.
- Mouse options misdescribed: `advanced_mouse_actions` doesn't control resizing;
  Ctrl+scroll resize is `mouse_scroll_resize` (0.45); tiled panes resize by a plain
  border drag (Ctrl+drag is for floating panes).

### Earlier fixes

- Docs said to press **Alt+t** for a new tab; no such binding exists. It is
  `Ctrl+t` then `n`. Guarded by `check.sh` check 10.
- The example theme failed to parse: 0.45.1 requires every component to set
  `base` and all four `emphasis_0..3`. Guarded by check 9.
- A top-level `unbind "Ctrl g"` silently didn't work (Ctrl+g is bound in two
  contexts); now unbound inside each block.
- A comment cited the non-existent `zellij config --help`; now
  `zellij setup --dump-config`.
- `config.kdl` had drifted to `default_layout "zjstatus"`, `pane_frames false` and
  `default_mode "locked"` without being asked for. Restored to `"default"`, `true`
  and `"normal"` (verified against the original).

### Plugin pins

- multitask `v0.44.3_hotfix` → `v0.45.1`, matching zellij (multitask is versioned
  in lockstep with zellij). zjstatus v0.25.0, monocle v0.100.2 and forgot 0.4.2
  confirmed as the latest releases.

### Design decisions

- **Session serialization** went on → off → on. zellij restores the *foreground
  command* of a pane, not its shell, so a resurrected nvim has no parent shell and
  `:qa` could end the session. Rather than a hook that rewrites the command (tested and working in bash, zsh
  and fish, but it splits filenames with spaces, waits for Enter on each restored
  pane, and needs extra scripts), the default layout opens a second `shell` tab so
  `:qa` never closes the last tab. A two-pane version was tried first; a tab was
  chosen because it gives nvim the full screen and is less likely to be closed by
  reflex.
- **zjstatus is opt-in**, not the default: it needs `pane_frames false` globally
  and asks for permission on first run. Its layout has the same `main` + `shell`
  tabs as the default.
- **No autolock plugin**: locking is manual with F12 (see the plugins cheatsheet).

### Migration from zellij 0.44.x to 0.45.1

- **Pane frames restyled (0.45.0).** The default frame style became a single title
  line (`"titles"`). This config sets `pane_frame_style "full"` to keep the classic
  border — `rounded_corners` only applies to a full border.
- **zjstatus → v0.25.0**, required for zellij ≥ 0.45.0 (fixes frame flicker under
  the new frame model).
- **Mouse wheel enters scroll mode (0.45.0).** 0.45.1 added the opt-out
  `scroll_mode_sync false`, documented (commented) in `config.kdl`.
- **`explicit_theme_hue` (0.45.1)** — pins dark or light, overriding what the
  terminal reports; noted next to `theme_dark`/`theme_light`. (Corrected
  2026-10-14: this entry and the docs had called it a fallback for terminals
  that don't report their mode.)
- **The `serialize_pane_viewport` name trap is unchanged** — the docs still call
  it `pane_viewport_serialization` (zellij-org/zellij#3987).
