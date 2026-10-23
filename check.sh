#!/bin/sh
# Run full validation; use --static explicitly to omit real Zellij validation.
set -eu
root=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
if command -v python3 >/dev/null 2>&1; then python=python3
elif command -v python >/dev/null 2>&1; then python=python
else echo 'Python 3.10+ is required.' >&2; exit 1; fi
if [ "${1:-}" = '--updates' ]; then
    exec "$python" "$root/tools/manage.py" launch -- --check-updates "$root/config/config.kdl"
fi
exec "$python" "$root/tools/manage.py" check "$@"
