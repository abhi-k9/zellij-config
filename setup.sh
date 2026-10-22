#!/bin/sh
# ─────────────────────────────────────────────────────────────────────────────
#  setup.sh — install this zellij config into your zellij config directory.
#
#  Usage:
#    ./setup.sh              install config.kdl, layouts/ and themes/, and the
#                            zj launcher (zellij + a monthly plugin update check)
#    ./setup.sh --offline    also install the pinned plugin .wasm files from
#                            plugins/ (downloading any that are missing) and
#                            rewrite the config to load them from disk (file:)
#    ./setup.sh --restore    put back the most recent backup (your current
#                            config is backed up first, so this is undoable)
#    ./setup.sh --dry-run    show what would happen, change nothing
#    ./setup.sh --help
#
#  Safe by design: any existing config is copied to a timestamped backup first
#  (real files, even if your config dir is a symlink into a dotfiles repo), so
#  nothing is ever lost. --offline verifies every plugin file against
#  plugins.sha256. Afterwards zellij itself reports which config dir it loads,
#  and parses the config and every layout. POSIX sh — Linux and macOS.
# ─────────────────────────────────────────────────────────────────────────────
set -eu

OFFLINE=0
DRYRUN=0
RESTORE=0
for arg in "$@"; do
    case "$arg" in
        --offline) OFFLINE=1 ;;
        --dry-run) DRYRUN=1 ;;
        --restore) RESTORE=1 ;;
        -h|--help)
            sed -n '2,21p' "$0" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *) echo "unknown option: $arg (try --help)" >&2; exit 2 ;;
    esac
done
if [ "$RESTORE" -eq 1 ] && [ "$OFFLINE" -eq 1 ]; then
    echo "--restore and --offline can't be combined (try --help)" >&2; exit 2
fi

# Where this script lives, so it works from any working directory. Clearing
# CDPATH stops cd from resolving via CDPATH (which could jump elsewhere), and
# `--` stops option parsing in case the path starts with a dash.
SRC=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
if [ ! -f "$SRC/config/config.kdl" ]; then
    echo "error: can't find config/config.kdl next to this script ($SRC)." >&2
    echo "Run setup.sh from inside the unpacked config archive." >&2
    exit 1
fi

# Resolve the target dir in the SAME order zellij 0.45.1 searches:
#   1. $ZELLIJ_CONFIG_DIR
#   2. ~/.config/zellij             — if it exists (wins even when XDG is set)
#   3. the platform dir             — if it exists. Linux/BSD:
#                                     ${XDG_CONFIG_HOME:-~/.config}/zellij; macOS:
#                                     ~/Library/Application Support/org.Zellij-Contributors.Zellij
#                                     (macOS zellij ignores XDG_CONFIG_HOME)
#   4. fresh machine                — the Linux/BSD platform dir; ~/.config/zellij on macOS
# Installing anywhere else would put the files where zellij never looks;
# verify_install below asks zellij to confirm.
if [ "$(uname -s)" = Darwin ]; then
    PLATFORM_DIR="$HOME/Library/Application Support/org.Zellij-Contributors.Zellij"
    FRESH_DIR=$HOME/.config/zellij
else
    PLATFORM_DIR=${XDG_CONFIG_HOME:-$HOME/.config}/zellij
    FRESH_DIR=$PLATFORM_DIR
fi
if [ -n "${ZELLIJ_CONFIG_DIR:-}" ]; then
    DEST=$ZELLIJ_CONFIG_DIR
elif [ -d "$HOME/.config/zellij" ]; then
    DEST=$HOME/.config/zellij
elif [ -d "$PLATFORM_DIR" ]; then
    DEST=$PLATFORM_DIR
else
    DEST=$FRESH_DIR
fi

say() { printf '%s\n' "$*"; }

# run CMD ARGS… — execute, or in --dry-run print it instead. Arguments are passed
# through as-is ("$@"), never re-parsed by eval, so paths containing spaces,
# quotes, $ or backticks are handled literally and can't be executed.
run() {
    if [ "$DRYRUN" -eq 1 ]; then
        printf '  would:'; printf ' %s' "$@"; printf '\n'
    else
        "$@"
    fi
}

# download URL FILE — fetch with curl or wget into FILE.
download() {
    if command -v curl >/dev/null 2>&1; then curl -fsSL -o "$2" "$1"
    elif command -v wget >/dev/null 2>&1; then wget -qO "$2" "$1"
    else echo "    ✗ need curl or wget to download $1" >&2; return 1; fi
}

# replace_all FILE FROM TO — literal (not regex) string replacement, in place.
# Values travel through the environment, so no character in a path or URL
# (/ & | \ . etc.) needs escaping.
replace_all() {
    FROM=$2 TO=$3 awk '{
        out = ""; line = $0; from = ENVIRON["FROM"]; to = ENVIRON["TO"]
        while ((i = index(line, from)) > 0) {
            out = out substr(line, 1, i - 1) to
            line = substr(line, i + length(from))
        }
        print out line
    }' "$1" > "$1.tmp" && mv "$1.tmp" "$1"
}

# sha256_of FILE — print the file's SHA-256, using whichever tool this system
# has: sha256sum (Linux, BusyBox), shasum (macOS), or openssl.
sha256_of() {
    if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'
    elif command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | awk '{print $1}'
    elif command -v openssl >/dev/null 2>&1; then openssl dgst -sha256 -r "$1" | awk '{print $1}'
    else return 1; fi
}

# expected_sha URL — the pinned checksum for URL from plugins.sha256 (empty if
# none). The URL goes in via the environment so no character needs escaping.
expected_sha() {
    U=$1 awk '!/^#/ && $2 == ENVIRON["U"] { print $1; exit }' "$SRC/plugins.sha256"
}

# backup_current — copy the current config to a new timestamped backup. Copies
# the CONTENTS ("$DEST/.") so a symlinked config dir (dotfiles repo) yields a
# real copy, not a second link to the files about to change. A numeric suffix
# is added if a backup from the same second already exists.
backup_current() {
    BACKUP="$DEST.backup-$(date +%Y%m%d-%H%M%S)"
    n=1; base=$BACKUP
    while [ -e "$BACKUP" ]; do BACKUP="$base-$n"; n=$((n + 1)); done
    run mkdir -p "$BACKUP"
    run cp -R "$DEST/." "$BACKUP/"
}

# install_launcher — put launcher/zj where `zj` is found without editing PATH:
# ~/.local/bin when it's on PATH, else the folder holding zellij if writable,
# else ~/.local/bin anyway, with how to add it to PATH. Never replaces a `zj`
# that isn't this launcher. Sets ZJ_AT to the installed path.
ZJ_AT=""
install_launcher() {
    bin=""; on_path=1
    case ":$PATH:" in *":$HOME/.local/bin:"*|*":$HOME/.local/bin/:"*) bin=$HOME/.local/bin ;; esac
    if [ -z "$bin" ] && [ -n "$ZJ_BIN" ] && [ -w "$(dirname -- "$ZJ_BIN")" ]; then
        bin=$(dirname -- "$ZJ_BIN")
    fi
    if [ -z "$bin" ]; then bin=$HOME/.local/bin; on_path=0; fi
    if [ -e "$bin/zj" ] && ! grep -q 'zellij-config launcher' "$bin/zj" 2>/dev/null; then
        say "  note: $bin/zj exists and isn't this config's launcher — left alone."
        return 0
    fi
    run mkdir -p "$bin"
    run cp "$SRC/launcher/zj" "$bin/zj"
    run chmod 755 "$bin/zj"
    ZJ_AT=$bin/zj
    say "  installed the zj launcher (zellij + monthly plugin update check): $ZJ_AT"
    if [ "$on_path" -eq 0 ]; then
        say "  note: $bin isn't on your PATH yet. Add it once, then open a new shell:"
        say "          fish:      fish_add_path ~/.local/bin"
        say "          bash/zsh:  add  export PATH=\"\$HOME/.local/bin:\$PATH\"  to ~/.bashrc or ~/.zshrc"
    else
        found=$(command -v zj 2>/dev/null || true)
        if [ -n "$found" ] && [ "$found" != "$ZJ_AT" ]; then
            say "  note: another zj comes first on your PATH ($found)."
        fi
    fi
}

# real_dir DIR — DIR's absolute physical path (symlinks resolved), or nothing.
real_dir() { (CDPATH='' cd -- "$1" 2>/dev/null && pwd -P); }

# verify_install WHAT — with the real zellij: confirm the config dir zellij
# discovers on its own is $DEST (not just that the file we wrote parses), then
# parse the config and each layout together with its .swap.kdl. Warns only.
verify_install() {
    if [ "$DRYRUN" -eq 1 ] || [ -z "$ZJ_BIN" ]; then return 0; fi
    out=$("$ZJ_BIN" setup --check 2>&1 || true)
    found=$(printf '%s\n' "$out" | sed -n 's/^\[CONFIG DIR\]: "\(.*\)"$/\1/p')
    if [ -z "$found" ] || [ "$(real_dir "$found")" != "$(real_dir "$DEST")" ]; then
        echo "warning: zellij loads its config from '${found:-nowhere}', not $DEST." >&2
        echo "         Export ZELLIJ_CONFIG_DIR=\"$DEST\" in your shell profile, or rerun" >&2
        echo "         setup.sh with ZELLIJ_CONFIG_DIR set to the dir zellij uses." >&2
    fi
    out=$("$ZJ_BIN" --config-dir "$DEST" setup --check 2>&1 || true)
    case "$out" in
        *"Well defined"*) say "  verified: zellij parses the $1 config.kdl." ;;
        *) echo "warning: zellij could not parse the $1 config — run:" >&2
           echo "         zellij --config-dir \"$DEST\" setup --check" >&2 ;;
    esac
    for f in "$DEST/layouts/"*.kdl; do
        case "$f" in *.swap.kdl) continue ;; esac
        [ -f "$f" ] || continue
        if out=$("$ZJ_BIN" --config-dir "$DEST" --layout "$f" setup --check 2>&1); then rc=0; else rc=$?; fi
        case "$rc:$out" in
            0:*"Well defined"*) say "  verified: layouts/${f##*/} parses." ;;
            *) echo "warning: zellij rejects layouts/${f##*/} — run:" >&2
               echo "         zellij --config-dir \"$DEST\" --layout \"$f\" setup --check" >&2 ;;
        esac
    done
}

# With ZELLIJ_CONFIG_DIR pointing at this archive's own config/ (using the repo
# in place), zellij already reads these files: installing would copy each one
# onto itself, and --offline would rewrite the repo's own config.kdl.
if [ -d "$DEST" ] && [ "$(real_dir "$DEST")" = "$(real_dir "$SRC/config")" ]; then
    echo "error: the target is this archive's own config/ ($DEST) — zellij already reads it." >&2
    echo "       Nothing to install. For the zj launcher: ln -sf \"$SRC/launcher/zj\" ~/.local/bin/zj" >&2
    exit 1
fi

say "zellij config installer"
say "  source: $SRC"
say "  target: $DEST"
if [ "$DRYRUN" -eq 1 ]; then say "  (dry run — no changes)"; fi

ZJ_BIN=$(command -v zellij 2>/dev/null || true)
if [ -z "$ZJ_BIN" ]; then
    say "  note: 'zellij' isn't on your PATH yet — install it, then this config applies."
else
    # The config targets 0.45.x; older versions reject some of its values.
    ver=$("$ZJ_BIN" --version 2>/dev/null | awk '{print $2}')
    case "$ver" in
        0.4[5-9]*|0.[5-9]*|[1-9]*) ;;
        *) say "  warning: zellij $ver found — this config targets 0.45.1; some settings may fail on older versions." ;;
    esac
fi

# --restore: put the most recent backup back, then stop (no install).
# The newest backup is chosen BEFORE the current config is itself backed up —
# otherwise that fresh backup would be "the newest". Backup names embed a
# sortable timestamp, so the last match of the (sorted) glob is the latest. Your current config is
# saved first, so running --restore again undoes a restore.
if [ "$RESTORE" -eq 1 ]; then
    latest=""
    for b in "$DEST".backup-*; do     # the shell sorts glob matches; keep the last
        if [ -d "$b" ]; then latest=$b; fi
    done
    if [ -z "$latest" ]; then
        echo "error: no backups found (looked for $DEST.backup-*)." >&2; exit 1
    fi
    say "  restoring from: $latest"
    if [ -d "$DEST" ]; then
        backup_current
        say "  current config saved to: $BACKUP  (run --restore again to undo)"
        # Empty the dir's CONTENTS rather than the dir itself, so a symlinked
        # config dir stays a symlink. Safe: everything was just backed up.
        for item in "$DEST"/* "$DEST"/.[!.]*; do
            if [ -e "$item" ] || [ -L "$item" ]; then run rm -rf "$item"; fi
        done
    else
        run mkdir -p "$DEST"
    fi
    run cp -R "$latest/." "$DEST/"
    if [ -f "$DEST/config.kdl" ]; then verify_install restored; fi
    say ""; say "Restored. Running sessions pick up config changes automatically."
    exit 0
fi

# Back up an existing config so nothing is ever clobbered (see backup_current).
if [ -e "$DEST/config.kdl" ] || [ -d "$DEST/layouts" ] || [ -d "$DEST/themes" ]; then
    backup_current
    say "  existing config found — backed up to: $BACKUP"
fi

# Install. (On top of the existing dir: your own extra files stay put.)
run mkdir -p "$DEST/layouts" "$DEST/themes"
run cp "$SRC/config/config.kdl" "$DEST/config.kdl"
run cp "$SRC/config/layouts/"*.kdl "$DEST/layouts/"
for t in "$SRC/config/themes/"*; do
    if [ -e "$t" ]; then run cp "$t" "$DEST/themes/"; fi
done
say "  installed config.kdl, layouts/, themes/"
if [ -f "$DEST/layouts/welcome.kdl" ] && [ ! -f "$SRC/config/layouts/welcome.kdl" ]; then
    say "  note: layouts/welcome.kdl is left over from an older version of this config."
    say "        zellij's built-in 'welcome' layout is the same; delete the file to use it."
fi

# Offline mode: install the pinned plugins, then point the config at the local
# files. Each comes from the archive's plugins/ folder when that copy matches
# plugins.sha256 (so an offline machine needs no network), else it's
# downloaded. All files must be in place and verified BEFORE the config is
# touched, so a failure leaves a consistent config (every plugin still on its
# https URL) instead of a mix.
if [ "$OFFLINE" -eq 1 ]; then
    if [ ! -f "$SRC/plugins.sha256" ]; then
        echo "error: plugins.sha256 is missing — --offline verifies every plugin file against it." >&2; exit 1
    fi
    if ! command -v sha256sum >/dev/null 2>&1 && ! command -v shasum >/dev/null 2>&1 \
       && ! command -v openssl >/dev/null 2>&1; then
        echo "error: need sha256sum, shasum or openssl to verify the plugin files." >&2; exit 1
    fi
    # zellij's handling of spaces in file: paths is untested, and on macOS the
    # config dir can be ".../Application Support/...", so plugins go to a
    # space-free folder in that case.
    PLUGINS=$DEST/plugins
    case "$PLUGINS" in
        *[[:space:]]*) PLUGINS=${XDG_DATA_HOME:-$HOME/.local/share}/zellij-config/plugins ;;
    esac
    case "$PLUGINS" in
        *[[:space:]]*) echo "error: no space-free folder for the plugin files ($PLUGINS)." >&2; exit 1 ;;
    esac
    urls=$(grep -oE 'location="https://[^"]+\.wasm"' "$SRC/config/config.kdl" \
             | sed 's/^location="//; s/"$//' | sort -u)
    say "  --offline: installing pinned plugins to $PLUGINS/"
    run mkdir -p "$PLUGINS"
    # If you press Ctrl+C midway, remove any half-written .part file instead of
    # leaving it behind (130 = the usual "interrupted" exit code).
    trap 'rm -f "$PLUGINS"/*.part; echo "" >&2; echo "interrupted — no plugins changed." >&2; exit 130' INT TERM
    failed=""
    for url in $urls; do
        name=${url##*/}
        say "    $name"
        want=$(expected_sha "$url")
        if [ -z "$want" ]; then
            echo "    ✗ no checksum for $url in plugins.sha256" >&2; failed="$failed $name"; continue
        fi
        bundled=""
        if [ -f "$SRC/plugins/$name" ]; then
            if [ "$(sha256_of "$SRC/plugins/$name")" = "$want" ]; then bundled=$SRC/plugins/$name
            else say "      bundled plugins/$name doesn't match plugins.sha256 — downloading instead"; fi
        fi
        if [ "$DRYRUN" -eq 1 ]; then
            if [ -n "$bundled" ]; then run cp "$bundled" "$PLUGINS/$name"
            else run download "$url" "$PLUGINS/$name"; fi
            continue
        fi
        # Stage as .part and verify its checksum, THEN rename: neither an
        # interrupted copy or fetch nor a tampered or changed file ever lands
        # where zellij would load it. A missing or mismatched checksum counts as
        # a failure, so the config below stays untouched.
        if [ -n "$bundled" ]; then cp "$bundled" "$PLUGINS/$name.part"; from="from plugins/"
        elif download "$url" "$PLUGINS/$name.part"; then from="downloaded"
        else rm -f "$PLUGINS/$name.part"; failed="$failed $name"; continue; fi
        got=$(sha256_of "$PLUGINS/$name.part")
        if [ "$got" = "$want" ]; then
            mv "$PLUGINS/$name.part" "$PLUGINS/$name"
            say "      checksum ok ($from)"
        else
            rm -f "$PLUGINS/$name.part"; failed="$failed $name"
            echo "    ✗ checksum MISMATCH for $name — expected $want, got $got" >&2
        fi
    done
    if [ -n "$failed" ]; then
        echo "error: no verified copy of:$failed" >&2
        echo "       config left unchanged — plugins still load from their https URLs." >&2
        exit 1
    fi
    if [ "$DRYRUN" -eq 0 ]; then
        for url in $urls; do
            replace_all "$DEST/config.kdl" "location=\"$url\"" "location=\"file:$PLUGINS/${url##*/}\""
        done
    fi
    say "  plugins installed and config rewritten to load them from disk."
fi

install_launcher

verify_install installed

say ""
if [ -n "$ZJ_AT" ]; then
    say "Done. Start zellij with:  zj attach --create main"
    say "  (zj runs zellij, first checking monthly for newer plugin releases)"
else
    say "Done. Start zellij with:  zellij attach --create main"
fi
say "  (opens the 'main' session with the default two-tab layout — and, after a"
say "   crash or reboot, brings the saved one back, which plain 'zellij' would"
say "   replace; see README 'Session recovery')"
if [ "$OFFLINE" -eq 0 ]; then
    say "  plugins download automatically on first use; --offline installs the"
    say "  copies bundled in plugins/ instead (no network needed)."
fi
# Explicit success. (A trailing `[ … ] && cmd` would make the script exit 1
# whenever the test is false — e.g. on every --offline run.)
exit 0
