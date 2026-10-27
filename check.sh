#!/bin/sh
# Run full validation; use --static explicitly to omit real Zellij validation.
set -eu
root=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
helper=$root/tools/manage.py
if [ ! -f "$helper" ]; then echo "Check helper is missing: $helper. Keep check.sh in the complete checkout." >&2; exit 1; fi
if [ -n "${ZJ_PYTHON:-}" ]; then
    python=$ZJ_PYTHON
    if ! command -v "$python" >/dev/null 2>&1; then echo "ZJ_PYTHON executable is unavailable: $python. Set one Python 3.10+ executable path without arguments." >&2; exit 1; fi
elif command -v python3 >/dev/null 2>&1; then python=python3
elif command -v python >/dev/null 2>&1; then python=python
else echo 'Python 3.10+ is required.' >&2; exit 1; fi
if [ "${1:-}" = '--updates' ]; then
    if [ "$#" -gt 2 ]; then echo 'Usage: check.sh --updates [CONFIG_FILE]' >&2; exit 1; fi
    exec "$python" "$helper" launch -- --check-updates "${2-$root/config.kdl}"
fi
exec "$python" "$helper" check "$@"
