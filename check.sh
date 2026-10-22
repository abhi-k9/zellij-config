#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
#  check.sh — consistency linter for this zellij config repo.
#
#  WHY THIS EXISTS: the same fact lives in several files at once — config.kdl,
#  README.md, and the four cheatsheets. Every time one copy changed and another
#  didn't, a stale claim shipped (a removed plugin lingering across four files,
#  a mis-spelled option name, "resurrection: on" after it was turned off). This
#  script greps for that class of drift so a human doesn't have to remember to.
#
#  It is READ-ONLY: it changes nothing, just reports. Run it from anywhere (it
#  switches to its own directory, the repo root) before committing:
#
#      ./check.sh
#      ./check.sh --updates   (network) compare each pinned plugin with its
#                             latest GitHub release instead; see launcher/zj
#
#  Exit code 0 = clean, 1 = at least one issue worth a look. Every finding is a
#  heuristic pointing you at a spot to eyeball — not all are real bugs (some
#  mentions are intentional, e.g. the "why we DON'T use autolock" notes), so it
#  labels those as INFO rather than FAIL.
#
#  Dependencies: bash, grep, sed, awk — POSIX character classes only, no GNU-only
#  regex escapes, so BSD/macOS tools work (and Git Bash on Windows). Checks 8–10
#  and the swap-file comparison in 12 also use the `zellij` binary when it's on
#  PATH and are skipped otherwise. Colors are used only on a terminal (and never
#  when NO_COLOR is set).
# ═══════════════════════════════════════════════════════════════════════════
set -uo pipefail
cd "$(dirname "$0")" || exit 2

CFG="config/config.kdl"
README="config/README.md"
SHEETS=(cheatsheets/*.html)
LAYOUTS=(config/layouts/*.kdl)

fail=0
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  G=$'\033[32m' Y=$'\033[33m' C=$'\033[36m' B=$'\033[1m' R=$'\033[0m'
else
  G='' Y='' C='' B='' R=''
fi
ok()   { printf '  %sok%s   %s\n' "$G" "$R" "$*"; }
warn() { printf '  %sWARN%s %s\n' "$Y" "$R" "$*"; fail=1; }
info() { printf '  %sINFO%s %s\n' "$C" "$R" "$*"; }
sect() { printf '\n%s%s%s\n' "$B" "$*" "$R"; }

[ -f "$CFG" ] || { echo "Run me from the repo root (can't find $CFG)."; exit 2; }

case "${1:-}" in
  "") ;;
  --updates) exec sh launcher/zj --check-updates "$CFG" ;;
  *) echo "usage: ./check.sh [--updates]" >&2; exit 2 ;;
esac

# ── 1. KDL brace balance (quoted strings removed first, then // comments) ────
# Order matters: strip strings BEFORE comments, or a URL like "https://…" would
# be mistaken for a comment, and braces inside strings ("{mode}") would count.
sect "1. KDL brace balance"
for f in "$CFG" "${LAYOUTS[@]}" config/themes/*.example; do
  [ -f "$f" ] || continue
  # [{] / [}] rather than /{/: a bare { starts a {n,m} interval in a regex, and
  # BusyBox (and recent BSD/macOS) awk reject it — only GNU awk lets it slide.
  depth=$(awk '
    { line=$0; gsub(/"([^"\\]|\\.)*"/,"\"\"",line); sub(/\/\/.*/,"",line)
      n=gsub(/[{]/,"{",line); m=gsub(/[}]/,"}",line); d+=n-m }
    END { print d+0 }' "$f")
  if [ "$depth" = "0" ]; then ok "$f"; else warn "$f has unbalanced braces (net $depth)"; fi
done

# ── 2. HTML tag balance in cheatsheets (rough div/table/tr/td counts) ───────
sect "2. Cheatsheet tag balance (div/table/tr/td)"
for f in "${SHEETS[@]}"; do
  bad=""
  for tag in div table tr td; do
    o=$(grep -o "<${tag}[ >]" "$f" | wc -l | tr -d ' ')
    c=$(grep -o "</$tag>" "$f" | wc -l | tr -d ' ')
    [ "$o" = "$c" ] || bad="$bad $tag($o/$c)"
  done
  if [ -z "$bad" ]; then ok "$f"; else warn "$f tag mismatch:$bad"; fi
done

# ── 3. Target version consistency ───────────────────────────────────────────
sect "3. Version consistency"
# Canonical version = the one in the config header line "targeting vX.Y.Z".
ver=$(grep -oE 'targeting v[0-9]+\.[0-9]+\.[0-9]+' "$CFG" | head -1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
mm=${ver%.*}   # major.minor
if [ -z "$ver" ]; then warn "no 'targeting vX.Y.Z' line found in $CFG"; else
  ok "canonical target = $ver (from $CFG)"
  grep -q "\*\*$ver\*\*" "$README" || warn "$README intro doesn't mention $ver"
  # The changelog's verification record is titled with the version it was run on.
  if [ -f CHANGELOG.md ]; then
    if grep -qE "^## Verification status .*$ver" CHANGELOG.md; then
      ok "CHANGELOG.md verification record is for $ver"
    else
      warn "CHANGELOG.md verification record isn't for $ver — re-verify and update it"
    fi
  fi
  for f in "${SHEETS[@]}"; do
    if grep -q "v$mm" "$f" || grep -q "$ver" "$f"; then ok "$f references v$mm"; \
    else info "$f has no v$mm marker (may be fine if it shows no version)"; fi
  done
fi

# ── 4. serialize_pane_viewport name trap ────────────────────────────────────
sect "4. serialize_pane_viewport spelling"
if grep -qE '^[[:space:]]*serialize_pane_viewport[[:space:]]' "$CFG"; then
  ok "config uses the correct parser key serialize_pane_viewport"
else
  warn "config.kdl has no active serialize_pane_viewport line"
fi
# The docs' wrong name should only ever appear inside explanatory comments.
if grep -rn 'pane_viewport_serialization' "$CFG" "$README" "${SHEETS[@]}" >/dev/null 2>&1; then
  info "the docs-name 'pane_viewport_serialization' appears (expected: only in"
  info "     the NAME-TRAP explanations — check it's never used as a live key)"
fi

# ── 5. Background plugins, and autolock mentions ────────────────────────────
# A load_plugins block is legitimate (the docs explain how to add one), so it's
# reported, not flagged. autolock was removed on purpose; only "why we don't use
# it" notes should still mention it.
sect "5. Background plugins (load_plugins) and autolock mentions"
if grep -qE '^[[:space:]]*load_plugins[[:space:]]*\{' "$CFG"; then
  info "$CFG has a load_plugins block — those plugins start with every session"
  info "     (fine if intended; the shipped config has none)"
else
  ok "no load_plugins block (nothing starts in the background)"
fi
al=$(grep -rIl 'autolock' "$CFG" "$README" "${SHEETS[@]}" 2>/dev/null || true)
[ -n "$al" ] && info "autolock still mentioned in: $(echo "$al" | tr '\n' ' ')(should be" \
  && info "     explanatory 'why we don't use it' text only — verify, not a plugin ref)"

# ── 6. Resurrection state agreement ─────────────────────────────────────────
sect "6. session_serialization state agrees across files"
ss=$(grep -oE '^[[:space:]]*session_serialization[[:space:]]+(true|false)' "$CFG" | grep -oE '(true|false)$' | head -1)
if [ -z "$ss" ]; then warn "no active session_serialization line in $CFG"; else
  ok "config.kdl: session_serialization $ss"
  # The cheatsheets label resurrection with an on/off badge; it must match the
  # config in BOTH directions (the ON state used to go unchecked).
  if [ "$ss" = "true" ]; then wrong='off|disabled'; want=ON; else wrong='on|activated'; want=OFF; fi
  for f in "${SHEETS[@]}"; do
    if grep -Eiq "Resurrection[^<]*<[^>]*>($wrong)<" "$f"; then
      warn "$f labels Resurrection opposite to config ($want)"
    fi
  done
  ok "cheatsheet Resurrection badges checked against $want"
fi

# ── 7. Plugin pin agreement (every config.kdl pin vs README and cheatsheets) ─
# Each pinned .wasm URL in config.kdl should appear verbatim in the README (the
# offline-download table), and neither the README nor a cheatsheet should
# mention any OTHER version of the same plugin — the classic "bumped the config,
# forgot the docs" drift.
sect "7. Plugin version pins agree (config.kdl vs README and cheatsheets)"
pins=$(grep -oE 'https://github.com/[^"]+/releases/download/[^/"]+/[^/"]+\.wasm' "$CFG" | sort -u)
if [ -z "$pins" ]; then info "no pinned plugin URLs in $CFG"; fi
for url in $pins; do
  repo=${url%%/releases/*}; tag=${url#*/releases/download/}; tag=${tag%%/*}
  name=${repo##*/}
  if grep -qF "$url" "$README"; then ok "$name $tag — README matches"
  else warn "$name $tag — pinned URL not found in $README (offline table out of date?)"; fi
  for f in "$README" "${SHEETS[@]}"; do
    other=$(grep -oE "${repo//./\\.}/releases/download/[^/\` )\"<]+" "$f" | sed 's|.*/download/||' | grep -vxF "$tag" | grep -v '^\$' | sort -u || true)
    [ -n "$other" ] && warn "$f references $name version(s): $other (config pins $tag)"
  done
done

# ── 8–10 need the zellij binary; skipped (not failed) when it's absent ──────
ZJ=$(command -v zellij || true)

# ── 8. config.kdl and every layout parse ────────────────────────────────────
# --config-dir makes zellij read THIS repo's config and layouts (with --config
# alone it would report your installed layout dir). `setup --check` parses a
# layout — and the NAME.swap.kdl beside it — only when one is named with
# --layout; without that, a broken layout still says "Well defined".
sect "8. config.kdl and every layout parse (zellij setup --check)"
if [ -z "$ZJ" ]; then info "zellij not on PATH — skipped"
else
  out=$("$ZJ" --config-dir config setup --check 2>&1)
  case "$out" in
    *"Well defined"*) ok "$CFG — Well defined" ;;
    *) warn "$CFG fails to parse — run: zellij --config-dir config setup --check" ;;
  esac
  for f in "${LAYOUTS[@]}"; do
    case "$f" in *.swap.kdl) continue ;; esac
    if out=$("$ZJ" --config-dir config --layout "$f" setup --check 2>&1); then rc=0; else rc=$?; fi
    case "$rc:$out" in
      0:*"Well defined"*) ok "$(basename "$f") parses (with its swap file)" ;;
      *) warn "$(basename "$f") fails to parse — run: zellij --config-dir config --layout $f setup --check" ;;
    esac
  done
fi

# ── 9. Example theme parses ─────────────────────────────────────────────────
# zellij 0.45 rejects a theme component unless it sets base AND emphasis_0..3;
# the example shipped broken once, so load it for real.
sect "9. Example theme parses"
THEME="config/themes/example-custom.kdl.example"
if [ -z "$ZJ" ]; then info "zellij not on PATH — skipped"
elif [ ! -f "$THEME" ]; then info "no $THEME"
else
  tname=$(grep -oE '^[[:space:]]{4}[A-Za-z0-9_-]+ \{' "$THEME" | head -1 | tr -d ' {')
  # Explicit template: works with GNU, BusyBox and BSD/macOS mktemp alike.
  tmp=$(mktemp "${TMPDIR:-/tmp}/zellij-check.XXXXXX"); trap 'rm -f "$tmp"' EXIT
  { printf 'theme "%s"\n' "$tname"; cat "$THEME"; } > "$tmp"
  if "$ZJ" --config "$tmp" setup --check 2>&1 | grep -q "Well defined"; then ok "theme \"$tname\" parses"
  else warn "$THEME fails to parse (missing emphasis_0..3 on a component?)"; fi
  rm -f "$tmp"
fi

# ── 10. Every documented shortcut is really bound ───────────────────────────
# Collects the Alt / Ctrl / F-key shortcuts mentioned in README, config, layouts
# and cheatsheets, and checks each against zellij's default bindings + this
# config. A shortcut this config UNBINDS is fine (the docs say so). A few
# mentions are deliberate and not zellij bindings — listed in ALLOW with the
# reason. Commented-out lines of config.kdl are ignored when collecting binds: a
# `// bind "Alt z" …` in a comment does not make Alt+z real. (Limitation: a key
# counts as bound if ANY mode binds it; the check doesn't verify the mode the
# docs name, nor the keys typed after a mode prefix like Ctrl+o.)
sect "10. Documented shortcuts exist"
# ctrl a: a key inside zellij's config screen | ctrl w: the shell's word-delete |
# ctrl y: the keybinding popup's former key, named in "why it moved" notes
ALLOW="ctrl a|ctrl w|ctrl y"
if [ -z "$ZJ" ]; then info "zellij not on PATH — skipped"
else
  active_cfg=$(grep -vE '^[[:space:]]*//' "$CFG" | sed 's#//.*##')
  bound=$({ "$ZJ" setup --dump-config 2>/dev/null | grep -vE '^[[:space:]]*//'; printf '%s\n' "$active_cfg"; } \
          | grep -oE '(^|[^n])bind( +"[^"]+")+' | grep -oE '"[^"]+"' | tr -d '"' | tr '[:upper:]' '[:lower:]' | sort -u)
  unbound=$(printf '%s\n' "$active_cfg" | grep -oE 'unbind "[^"]+"' | grep -oE '"[^"]+"' | tr -d '"' | tr '[:upper:]' '[:lower:]' | sort -u)
  # Recognized forms: "Alt+t", "Ctrl + g", and the space form the popup list uses
  # ("Alt n", "Alt ["). The key is ONE letter/digit not followed by another word
  # char (portable stand-in for GNU's \b), or one of ] = [ - . F-keys ("F12")
  # stand alone; a leading # keeps hex colors out.
  text=$(cat "$README" "$CFG" "${LAYOUTS[@]}" "${SHEETS[@]}" | sed 's/<[^>]*>//g; s/&nbsp;/ /g')
  docs=$({ printf '%s\n' "$text" \
             | grep -oE '(Alt|Ctrl)( ?\+ ?| )([A-Za-z0-9]([^A-Za-z0-9_]|$)|[]=[-])' \
             | sed -E 's/^(Alt|Ctrl)( ?\+ ?| )(.).*$/\1 \3/'
           printf '%s\n' "$text" | grep -oE '(^|[^A-Za-z0-9#])F[0-9]{1,2}([^0-9]|$)' | grep -oE 'F[0-9]+'
         } | tr '[:upper:]' '[:lower:]' | sort -u)
  bad=0
  # read loop, not `for k in $docs`: keys like "alt [" must not be split or globbed.
  while IFS= read -r k; do
    [ -n "$k" ] || continue
    if printf '%s\n' "$bound" | grep -qxF "$k" || printf '%s\n' "$unbound" | grep -qxF "$k" \
       || printf '%s\n' "$k" | grep -qxE "$ALLOW"; then :
    else warn "documented shortcut \"$k\" is not bound anywhere"; bad=1; fi
  done <<EOF
$docs
EOF
  [ "$bad" = 0 ] && ok "$(printf '%s\n' "$docs" | grep -c .) distinct shortcuts, all bound (or intentionally unbound)"
fi

# ── 11. One-line KDL blocks end every node with ';' ─────────────────────────
# zellij's parser does NOT treat `}` as ending a node on the same line:
# `ui { pane_frames { rounded_corners true } }` and `pane { name "x" }` both
# fail to load (config AND layouts); it must be `…true; }; }` / `{ name "x"; }`.
# Scans KDL code only — README ```kdl fences, cheatsheet <pre>/<code>, and the
# .kdl files — ignoring quoted strings, `{ ... }` placeholders and zjstatus
# `{widget}` tokens. Deliberate wrong examples go in <code class="bad">, which
# this skips. No zellij needed.
sect "11. One-line blocks terminate every node with ';'"
kdl_code() {
  awk '/^```kdl/{f=1;next} /^```/{f=0} f' "$README"
  for h in "${SHEETS[@]}"; do
    awk '/<pre/{f=1} f{print} /<\/pre>/{f=0}' "$h"
    grep -oE '<code>[^<]*\{[^<]*</code>' "$h"
  done
  cat "$CFG" "${LAYOUTS[@]}" config/themes/*.example 2>/dev/null | grep -vE '^[[:space:]]*//'
}
semi_bad=$(kdl_code | sed -E 's/<[^>]*>//g; s/&quot;/"/g; s/&lt;/</g; s/&gt;/>/g; s/&amp;/\&/g' \
  | sed -E 's#[[:space:]]//.*$##; s/"([^"\\]|\\.)*"/""/g' \
  | sed -E 's/\{[A-Za-z_*]+\}//g' | grep '{' | grep -vE '\.\.\.|…|\$\{' | grep -E '[^;{[:space:]][[:space:]]*\}' || true)
if [ -z "$semi_bad" ]; then ok "no one-line block is missing a ';'"
else while IFS= read -r l; do warn "missing ';' before '}': $(echo "$l" | sed -E 's/^[[:space:]]+//')"; done <<< "$semi_bad"; fi

# ── 12. Every layout has its swap layouts, and they're current ──────────────
# zellij pairs NAME.kdl with NAME.swap.kdl; without it Alt+[ / Alt+] silently do
# nothing (they did, until the swap files were added). The swap files are
# zellij's built-in "compact" swap layouts, verbatim apart from the bar plugin
# in tab_template, so with zellij present they're compared (comments, blank
# lines and plugin locations aside) against `setup --dump-swap-layout compact`
# — a zellij upgrade that changes the built-ins then gets noticed.
sect "12. Swap layouts present and current (Alt+[ / Alt+])"
for f in "${LAYOUTS[@]}"; do
  case "$f" in *.swap.kdl) continue ;; esac
  sw="${f%.kdl}.swap.kdl"
  if [ -f "$sw" ]; then ok "$(basename "$f") → $(basename "$sw")"
  else warn "$(basename "$f") has no $(basename "$sw") — Alt+[ / Alt+] will do nothing in it"; fi
done
if [ -n "$ZJ" ]; then
  swap_norm() { tr -d '\r' | grep -vE '^[[:space:]]*(//|$)' | sed -E 's/location="[^"]*"/location="BAR"/'; }
  ref=$("$ZJ" setup --dump-swap-layout compact 2>/dev/null | swap_norm)
  if [ -z "$ref" ]; then info "couldn't dump zellij's built-in swap layouts — comparison skipped"
  else
    for sw in config/layouts/*.swap.kdl; do
      [ -f "$sw" ] || continue
      if [ "$(swap_norm < "$sw")" = "$ref" ]; then ok "$(basename "$sw") matches zellij's built-in compact swap layouts"
      else warn "$(basename "$sw") differs from \`zellij setup --dump-swap-layout compact\` — re-dump it (see its header)"; fi
    done
  fi
fi

# ── 13. Every pinned plugin has a checksum ──────────────────────────────────
# setup.sh --offline refuses any download without a matching line in
# plugins.sha256, so bumping a pin in config.kdl without updating the checksum
# would break offline installs. Also flags malformed hashes and stale lines.
sect "13. Plugin checksums (plugins.sha256)"
SUMS=plugins.sha256
if [ ! -f "$SUMS" ]; then warn "$SUMS is missing — setup.sh --offline needs it"
else
  for url in $pins; do
    h=$(awk -v u="$url" '!/^#/ && $2 == u { print $1; exit }' "$SUMS")
    if [ -z "$h" ]; then warn "no checksum for $url in $SUMS"
    elif ! printf '%s' "$h" | grep -qE '^[0-9a-f]{64}$'; then warn "malformed checksum for ${url##*/}: $h"
    else ok "${url##*/} has a checksum"; fi
  done
  while read -r h u; do
    case "$h" in ''|\#*) continue ;; esac
    printf '%s\n' "$pins" | grep -qxF "$u" || warn "$SUMS has a line for $u, which config.kdl no longer pins"
  done < "$SUMS"
fi

# ── 14. Bundled plugin files ────────────────────────────────────────────────
# The archive carries every pinned plugin in plugins/ so an offline machine
# needs no download (setup.sh --offline installs from there). After a pin bump
# the old file would quietly ship, so each must match plugins.sha256; and
# names must be unique, since installs store plugins by file name.
sect "14. Bundled plugins (plugins/*.wasm) match plugins.sha256"
sha_of() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}' | tr -d '\134'
  elif command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | awk '{print $1}'
  elif command -v openssl >/dev/null 2>&1; then openssl dgst -sha256 -r "$1" | awk '{print $1}'
  fi
}
dups=$(for url in $pins; do printf '%s\n' "${url##*/}"; done | sort | uniq -d | tr '\n' ' ')
[ -n "$dups" ] && warn "pins share a file name (${dups% }) — plugins/ and setup.sh --offline store them by name"
for url in $pins; do
  name=${url##*/}; f=plugins/$name
  want=$(awk -v u="$url" '!/^#/ && $2 == u { print $1; exit }' "$SUMS" 2>/dev/null)
  if [ ! -f "$f" ]; then warn "$f is missing — download it: curl -fLo $f $url"
  elif [ -z "$want" ]; then warn "$f has no checksum to compare with (see check 13)"
  else
    got=$(sha_of "$f")
    if [ -z "$got" ]; then info "no sha256sum, shasum or openssl — $f not verified"
    elif [ "$got" = "$want" ]; then ok "$f matches its checksum"
    else warn "$f doesn't match plugins.sha256 — stale copy? curl -fLo $f $url"; fi
  fi
done
for f in plugins/*.wasm; do
  [ -f "$f" ] || continue
  known=0
  for url in $pins; do [ "${url##*/}" = "${f##*/}" ] && known=1; done
  [ "$known" = 1 ] || warn "$f isn't pinned in config.kdl — remove it, or add its pin"
done

sect "Result"
if [ "$fail" = "0" ]; then printf '%sAll consistency checks passed.%s\n' "$G" "$R"
else printf '%sSome checks flagged — review the WARN lines above.%s\n' "$Y" "$R"; fi
exit "$fail"
