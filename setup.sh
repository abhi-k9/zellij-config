#!/bin/sh
# zellij-config installer; Python 3.10+ provides the shared cross-platform logic.
set -eu
root=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
helper=$root/tools/manage.py
if [ ! -f "$helper" ]; then echo "Setup helper is missing: $helper. Keep setup.sh in the complete checkout." >&2; exit 1; fi
if [ -n "${ZJ_PYTHON:-}" ]; then
    python=$ZJ_PYTHON
    if ! command -v "$python" >/dev/null 2>&1; then echo "ZJ_PYTHON executable is unavailable: $python. Set one Python 3.10+ executable path without arguments." >&2; exit 1; fi
elif command -v python3 >/dev/null 2>&1; then python=python3
elif command -v python >/dev/null 2>&1; then python=python
else echo 'Python 3.10+ is required. Install Python, then rerun setup.' >&2; exit 1; fi
exec "$python" "$helper" install "$@"
