#!/bin/sh
# zellij-config installer; Python 3.10+ provides the shared cross-platform logic.
set -eu
root=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
if command -v python3 >/dev/null 2>&1; then python=python3
elif command -v python >/dev/null 2>&1; then python=python
else echo 'Python 3.10+ is required. Install Python, then rerun setup.' >&2; exit 1; fi
exec "$python" "$root/tools/manage.py" install "$@"
