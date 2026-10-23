#!/usr/bin/env python3
"""Repository and installed-launcher entry point (Python 3.10+)."""
import sys

if sys.version_info < (3, 10):
    raise SystemExit('Python 3.10 or newer is required for zellij-config helpers.')

from zjconfig.cli import main

if __name__ == '__main__':
    raise SystemExit(main())
