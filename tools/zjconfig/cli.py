"""Shared CLI for source management, local preferences and launcher state.

Source upgrades and deployment require explicit commands. Launching also writes
private cache/snapshot state and may schedule a release-notice worker.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

from .common import ConfigError, FileLock, atomic_write, json_bytes, read_json


def root_directory() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / 'versions.json').is_file():
            return parent
    raise ConfigError('Cannot find versions.json alongside the helper package')


def require_repository(root: Path, command: str) -> None:
    """Installed launch helpers carry pins, but no editable source inventory."""
    if not all((root / name).is_file() for name in ['config.kdl', 'tools/manage.py', 'setup.sh', 'plugins.sha256']):
        raise ConfigError(f'{command} requires the full zellij-config source checkout; '
                          'run tools/manage.py from that checkout. Installed helpers do not include repository sources.')


def assignments(values: list[str]) -> dict[str, str]:
    result = {}
    for value in values:
        key, separator, item = value.partition('=')
        if not separator or not key or not item or key in result:
            raise ConfigError('Expected distinct NAME=VALUE assignments')
        result[key] = item
    return result


def configure(options) -> int:
    """Persist only user-owned preferences; zj renders the managed KDL later."""
    from .install import default_directory
    from .kdl import parse, quote
    from .preferences import LOCAL_FILE, read_settings, render_config, render_layout, validate_settings
    directory = (options.config_dir or default_directory()).expanduser().resolve()
    quote(str(directory))
    config = directory / 'config.kdl'
    if not config.is_file():
        raise ConfigError(f'No config.kdl in {directory}; select an existing config with --config-dir')
    file = directory / LOCAL_FILE
    if file.is_symlink():
        raise ConfigError(f'Refusing a local preferences symlink: {file}')
    keys = ['profile', 'timezone', 'git_status', 'session_name', 'attach_to_session',
            'rust_backtrace', 'lock_key', 'layout', 'theme', 'pane_frames']
    updates = {key: getattr(options, key) for key in keys if getattr(options, key) is not None}
    for key in ['git_status', 'attach_to_session', 'rust_backtrace', 'pane_frames']:
        if key in updates:
            updates[key] = updates[key] == 'on'
    if options.project_sessions:
        if options.session_name is not None or options.attach_to_session is not None:
            raise ConfigError('--project-sessions cannot be combined with --session-name or --attach-to-session')
        updates.update(session_name=None, attach_to_session=False)
    if options.reset and updates:
        raise ConfigError('--reset cannot be combined with preference changes')

    def candidate():
        read_settings(directory)  # Includes duplicate-key and size checks.
        raw = read_json(file) if file.exists() else {'schema': 1}
        validate_settings(raw)
        raw.update(updates)
        effective = validate_settings(raw)
        # Render and check helper-level syntax without Zellij or network access.
        # This does not validate theme availability, Zellij option semantics or
        # the interactive behavior of commands in a selected layout.
        parse(render_config(config.read_text(encoding='utf-8'), effective))
        for layout in (directory / 'layouts').glob('*.kdl'):
            parse(render_layout(layout.read_text(encoding='utf-8'), layout.name, effective))
        if effective['layout'] in ['dev', 'zjstatus', 'minimal'] and not (directory / 'layouts' / (effective['layout'] + '.kdl')).is_file():
            raise ConfigError(f'Layout {effective["layout"]} is missing from {directory / "layouts"}')
        return raw, effective

    if options.reset:
        if options.dry_run:
            print(f'Would remove {file}; no files changed.')
        else:
            with FileLock(directory / '.zj-preferences.lock'):
                if file.is_symlink():
                    raise ConfigError(f'Refusing a local preferences symlink: {file}')
                file.unlink(missing_ok=True)
            print(f'Removed local preferences from {directory}; new zj sessions use the source defaults.')
        return 0
    if not updates:
        print(json_bytes(read_settings(directory) or validate_settings({'schema': 1})).decode(), end='')
        return 0
    if options.dry_run:
        raw, _ = candidate()
        print(f'Would write {file}:')
        print(json_bytes(raw).decode(), end='')
        print('No files, locks or downloads created.')
        return 0
    with FileLock(directory / '.zj-preferences.lock'):
        if file.is_symlink():
            raise ConfigError(f'Refusing a local preferences symlink: {file}')
        raw, _ = candidate()
        atomic_write(file, json_bytes(raw))
    print(f'Saved {file}; restart the session through zj to apply preferences.')
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description='Install, verify and explicitly update this Zellij configuration.',
        epilog='Installed launcher helpers support launch and configure; other commands require the full source checkout.')
    commands = parser.add_subparsers(dest='command', required=True)
    setup = commands.add_parser('install')
    setup.add_argument('--offline', action='store_true', help='Never fetch missing plugins')
    setup.add_argument('--restore', action='store_true', help='Restore the latest validated snapshot')
    setup.add_argument('--dry-run', action='store_true', help='Print the plan; create no files or downloads')
    setup.add_argument('--config-dir', type=Path)
    setup.add_argument('--bin-dir', type=Path)
    setup.add_argument('--no-launcher', action='store_true')
    setup.add_argument('--launcher-only', action='store_true', help='Install only zj helpers; leave configuration untouched')
    verify = commands.add_parser('check')
    verify.add_argument('--static', action='store_true')
    preferences = commands.add_parser('configure', help='Save local preferences without editing tracked KDL')
    preferences.add_argument('--config-dir', type=Path)
    preferences.add_argument('--profile', choices=['portable', 'classic'])
    preferences.add_argument('--timezone')
    preferences.add_argument('--git-status', choices=['on', 'off'])
    preferences.add_argument('--session-name')
    preferences.add_argument('--attach-to-session', choices=['on', 'off'])
    preferences.add_argument('--project-sessions', action='store_true')
    preferences.add_argument('--rust-backtrace', choices=['on', 'off'])
    preferences.add_argument('--lock-key', choices=['Ctrl g', 'F12'])
    preferences.add_argument('--layout', choices=['default', 'dev', 'zjstatus', 'minimal'])
    preferences.add_argument('--theme')
    preferences.add_argument('--pane-frames', choices=['on', 'off'])
    preferences.add_argument('--reset', action='store_true')
    preferences.add_argument('--dry-run', action='store_true')
    start = commands.add_parser('launch')
    start.add_argument('--argv64', help=argparse.SUPPRESS)
    start.add_argument('--update-worker', type=Path, help=argparse.SUPPRESS)
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
        if options.command not in ['launch', 'configure']:
            require_repository(root, options.command)
        if options.command == 'install':
            from .install import default_binary_directory, install, install_launcher
            if options.launcher_only:
                if options.restore or options.no_launcher or options.config_dir is not None:
                    raise ConfigError('--launcher-only cannot be combined with --restore, --no-launcher or --config-dir')
                directory = (options.bin_dir or default_binary_directory()).expanduser().resolve()
                if options.dry_run:
                    print(f'Would install launcher helpers in {directory}')
                    print('No files, locks, backups or downloads created.')
                else:
                    install_launcher(root, directory)
                return 0
            if options.offline and options.restore:
                raise ConfigError('--restore and --offline cannot be combined')
            install(root, target=options.config_dir, offline=options.offline,
                    restore=options.restore, dry_run=options.dry_run,
                    bin_dir=options.bin_dir, no_launcher=options.no_launcher)
        elif options.command == 'configure':
            return configure(options)
        elif options.command == 'check':
            from .check import check
            check(root, options.static)
        elif options.command == 'launch':
            if options.update_worker:
                if os.environ.get('ZJ_OFFLINE') or os.environ.get('ZJ_NO_UPDATE_CHECK'):
                    return 0
                from .launcher import cached_scan, locations
                file = options.update_worker.resolve()
                cached_scan(file, locations(file))
                return 0
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
