"""Prepare verified plugin locations at startup without modifying the checkout."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import time

from .common import ConfigError, FileLock, atomic_write, json_bytes, plugin_url, private_tempdir, read_json, validate_versions
from .kdl import plugin_locations, quote, replace_plugin_locations
from .plugin_files import acquire, verified


def needs_plugins(arguments: list[str]) -> bool:
    prefix = arguments[:arguments.index('--')] if '--' in arguments else arguments
    if any(item in ['--version', '-V', '--help', '-h', '--clean'] for item in prefix):
        return False
    # These commands inspect or control a server; they don't start a new one.
    commands = {'setup', 'list-sessions', 'ls', 'list-aliases', 'la', 'kill-session', 'k',
                'kill-all-sessions', 'ka', 'delete-session', 'd', 'delete-all-sessions', 'da',
                'action', 'ac', 'plugin', 'p', 'pipe', 'edit', 'e', 'run', 'r',
                'web', 'watch', 'w', 'subscribe', 'help'}
    values = {'--config', '-c', '--config-dir', '--session', '-s', '--layout', '-l',
              '--new-session-with-layout', '-n', '--data-dir', '--max-panes', '--layout-string'}
    index = 0
    while index < len(prefix):
        item = prefix[index]
        if item in values:
            index += 2
        elif item.startswith('-'):
            index += 1
        else:
            return item not in commands
    return True


def arguments_for_config(arguments: list[str], file: Path, runtime: Path) -> list[str]:
    """Replace the config-file selector, preserving layout/theme dir and argv."""
    result = []
    directory = False
    index = 0
    while index < len(arguments):
        item = arguments[index]
        if item == '--':
            break
        if item in ['--config', '-c']:
            if index + 1 >= len(arguments):
                raise ConfigError(f'Missing value for {item}')
            index += 2
            continue
        if item.startswith('--config=') or (item.startswith('-c') and len(item) > 2):
            index += 1
            continue
        if item == '--config-dir':
            if index + 1 >= len(arguments):
                raise ConfigError('Missing value for --config-dir')
            result.extend(arguments[index:index + 2])
            directory = True
            index += 2
            continue
        if item.startswith('--config-dir='):
            directory = True
        result.append(item)
        index += 1
    prefix = ['--config', str(runtime)]
    if not directory:
        # An explicit environment directory may intentionally supply different
        # layouts/themes from the selected config file's own directory.
        selected = Path(os.environ['ZELLIJ_CONFIG_DIR']).expanduser() if os.environ.get('ZELLIJ_CONFIG_DIR') else file.parent
        prefix += ['--config-dir', str(selected)]
    return [*prefix, *result, *arguments[index:]]


RETRY_SECONDS = 300


def store_if_changed(path: Path, data: bytes) -> None:
    if path.is_symlink() or not path.exists() or path.read_bytes() != data:
        atomic_write(path, data)


def retry_later(path: Path, pin: dict, now: int) -> bool:
    try:
        data = read_json(path)
        until = data.get('until') if isinstance(data, dict) else None
        return (isinstance(until, int) and data.get('url') == plugin_url(pin)
                and now < until <= now + RETRY_SECONDS)
    except (OSError, ValueError):
        return False


def prepare(file: Path, arguments: list[str], state: Path, *, offline=False, now=None) -> list[str]:
    now = int(time.time()) if now is None else now
    file = file.resolve()
    manifest = next((path for path in [file.parent / 'versions.json',
                                      file.parent / '.zellij-config-versions.json']
                     if path.is_file() and not path.is_symlink()), None)
    if manifest is None:
        return arguments
    pins = validate_versions(read_json(manifest))
    text = file.read_text(encoding='utf-8')
    active = set(plugin_locations(text))
    selected = []
    for pin in pins['plugins']:
        aliases = {plugin_url(pin), 'file:' + (file.parent / 'plugins' / pin['asset']).as_posix()}
        if active & aliases:
            selected.append((pin, active & aliases))
    if not selected:
        return arguments
    quote(str(file))  # Reject control characters before creating state.
    if state.is_symlink():
        raise ConfigError(f'Refusing an update/runtime state symlink: {state}')
    state.mkdir(parents=True, mode=0o700, exist_ok=True)
    key = hashlib.sha256(str(file).encode('utf-8')).hexdigest()
    directory = state / ('runtime-' + key)
    with FileLock(state / ('runtime-' + key + '.lock')):
        if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
            raise ConfigError(f'Unsafe runtime directory: {directory}')
        if not directory.exists():
            temporary = private_tempdir(state, '.runtime-')
            try:
                os.replace(temporary, directory)
            finally:
                if temporary.exists():
                    temporary.rmdir()
        if os.name != 'nt':
            if directory.stat().st_uid != os.getuid():
                raise ConfigError(f'Runtime directory belongs to another user: {directory}')
            directory.chmod(0o700)
        replacements = {}
        missing = []
        for pin, aliases in selected:
            destination = directory / (pin['sha256'] + '.wasm')
            try:
                # A verified prior download is preferred over the bundled copy.
                # Failed downloads/bundled fallbacks are never cached as online.
                if destination.is_symlink():
                    raise ConfigError('Refusing a plugin cache symlink')
                verified(destination.read_bytes(), pin)
                for alias in aliases:
                    replacements[alias] = 'file:' + destination.as_posix()
            except (OSError, ConfigError):
                retry = directory / (pin['name'] + '-' + pin['sha256'] + '.retry.json')
                cooling = not offline and retry_later(retry, pin, now)
                missing.append((pin, aliases, destination, retry, cooling))

        def resolve(item):
            pin, _, _, _, cooling = item
            bundled = file.parent / 'plugins' / pin['asset']
            attempted = not offline and not cooling
            try:
                data, origin = acquire(pin, bundled, offline=offline or cooling)
            except ConfigError:
                if not cooling:
                    raise
                # A missing/bad backup must not prevent trying an available
                # network just because an earlier request failed.
                attempted = True
                data, origin = acquire(pin, bundled)
            return data, origin, attempted

        if missing:
            # Threads perform only reads/downloads. The lock owner publishes
            # verified results serially; at most three network requests run.
            with ThreadPoolExecutor(max_workers=min(3, len(missing))) as pool:
                resolved = list(pool.map(resolve, missing))
            for (pin, aliases, destination, retry, _), (data, origin, attempted) in zip(missing, resolved):
                if origin == 'download':
                    atomic_write(destination, data)
                    chosen = destination
                    retry.unlink(missing_ok=True)
                else:
                    # Snapshot verified fallback bytes outside the checkout too;
                    # later git pulls cannot change a running session's files.
                    chosen = directory / (pin['sha256'] + '.bundled.wasm')
                    store_if_changed(chosen, data)
                    if attempted:
                        atomic_write(retry, json_bytes({'url': plugin_url(pin), 'until': now + RETRY_SECONDS}))
                    print(f'zj: {pin["name"]}: using verified bundled fallback', flush=True)
                for alias in aliases:
                    replacements[alias] = 'file:' + chosen.as_posix()
        rendered = replace_plugin_locations(text, replacements).encode('utf-8')
        # The source and pins can be edited while downloads are in flight.
        if file.read_text(encoding='utf-8') != text or validate_versions(read_json(manifest)) != pins:
            raise ConfigError('Config or pins changed during plugin preparation; rerun zj')
        # Keep generations immutable: another launch must not switch the active
        # session's plugin selection or replace the config it watches.
        generation = hashlib.sha256(rendered).hexdigest()
        output = directory / (generation + '.kdl')
        store_if_changed(output, rendered)
    return arguments_for_config(arguments, file, output)
