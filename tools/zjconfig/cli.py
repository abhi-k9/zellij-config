"""Command-line interface; all mutations are explicit subcommands."""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import signal
import subprocess
import sys

from .common import ConfigError


def root_directory() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / 'versions.json').is_file():
            return parent
    raise ConfigError('Cannot find versions.json alongside the helper package')


def assignments(values: list[str]) -> dict[str, str]:
    result = {}
    for value in values:
        key, separator, item = value.partition('=')
        if not separator or not key or not item or key in result:
            raise ConfigError('Expected distinct NAME=VALUE assignments')
        result[key] = item
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Install, verify and explicitly update this Zellij configuration.')
    commands = parser.add_subparsers(dest='command', required=True)
    setup = commands.add_parser('install')
    setup.add_argument('--offline', action='store_true', help='Never fetch missing plugins')
    setup.add_argument('--restore', action='store_true', help='Restore the latest validated snapshot')
    setup.add_argument('--dry-run', action='store_true', help='Print the plan; create no files or downloads')
    setup.add_argument('--config-dir', type=Path)
    setup.add_argument('--bin-dir', type=Path)
    setup.add_argument('--no-launcher', action='store_true')
    verify = commands.add_parser('check')
    verify.add_argument('--static', action='store_true')
    start = commands.add_parser('launch')
    start.add_argument('--argv64', help=argparse.SUPPRESS)
    start.add_argument('arguments', nargs=argparse.REMAINDER)
    versions = commands.add_parser('versions').add_subparsers(dest='version_command', required=True)
    versions.add_parser('check')
    update = versions.add_parser('update')
    update.add_argument('--all', action='store_true')
    update.add_argument('--plugin', action='append', default=[], metavar='NAME=TAG')
    update.add_argument('--zellij', metavar='TAG')
    update.add_argument('--sha256', action='append', default=[], metavar='NAME=HEX')
    binary = commands.add_parser('install-zellij')
    binary.add_argument('--bin-dir', type=Path, required=True)
    options = parser.parse_args(argv)

    def interrupted(_signum, _frame):
        raise KeyboardInterrupt('Interrupted')

    signal.signal(signal.SIGTERM, interrupted)
    try:
        root = root_directory()
        if options.command == 'install':
            from .install import install
            if options.offline and options.restore:
                raise ConfigError('--restore and --offline cannot be combined')
            install(root, target=options.config_dir, offline=options.offline,
                    restore=options.restore, dry_run=options.dry_run,
                    bin_dir=options.bin_dir, no_launcher=options.no_launcher)
        elif options.command == 'check':
            from .check import check
            check(root, options.static)
        elif options.command == 'launch':
            from .launcher import launch
            arguments = options.arguments
            if options.argv64:
                if len(options.argv64) > 8 * 1024 * 1024:
                    raise ConfigError('Encoded argument list exceeds the helper limit')
                arguments = json.loads(base64.b64decode(options.argv64, validate=True))
                if not isinstance(arguments, list) or not all(isinstance(item, str) for item in arguments):
                    raise ConfigError('Invalid encoded launcher arguments')
            return launch(arguments)
        elif options.command == 'versions':
            from .versions import check_versions, update
            if options.version_command == 'check':
                return check_versions(root)
            update(root, assignments(options.plugin), options.zellij, options.all, assignments(options.sha256))
        elif options.command == 'install-zellij':
            from .versions import install_zellij
            install_zellij(root, options.bin_dir)
    except KeyboardInterrupt:
        print('Interrupted; owned staging resources were cleaned up. Rerun setup to recover an interrupted publication.', file=sys.stderr)
        return 130
    except (ConfigError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print(f'error: {error}', file=sys.stderr)
        return 1
    return 0
