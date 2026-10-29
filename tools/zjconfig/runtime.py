"""Prepare verified plugins and local preference snapshots outside the checkout."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import shutil
import time

from .common import ConfigError, FileLock, atomic_write, json_bytes, plugin_url, private_tempdir, read_json, validate_versions
from .kdl import parse, plugin_locations, quote, replace_plugin_locations
from .plugin_files import acquire, verified


def needs_plugins(arguments: list[str]) -> bool:
    """Classify session startup using the selected Zellij CLI's known grammar.

    This also controls preference preparation and automatic notices. Review the
    command/option tables when upgrading Zellij; it is not a general CLI parser.
    """
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


def resource_directory(arguments: list[str], file: Path) -> Path:
    """Follow native config-directory selection without changing its argv."""
    selected = os.environ.get('ZELLIJ_CONFIG_DIR')
    index = 0
    while index < len(arguments):
        item = arguments[index]
        if item == '--':
            break
        if item == '--config-dir':
            if index + 1 >= len(arguments):
                raise ConfigError('Missing value for --config-dir')
            index += 1
            selected = arguments[index]
        elif item.startswith('--config-dir='):
            selected = item.split('=', 1)[1]
        index += 1
    return Path(selected).expanduser().resolve() if selected else file.parent


def snapshot_layouts(text: str, arguments: list[str], file: Path, directory: Path, settings: dict) -> str:
    """Snapshot available named KDL resources; retain older content generations.

    layout_dir selects the snapshot without rewriting explicit layout-file argv.
    Pair completeness is enforced by the repository checker, not by this copy.
    """
    from .preferences import render_layout, set_root_nodes
    source = resource_directory(arguments, file) / 'layouts'
    configured = [node for node in parse(text) if node.name == 'layout_dir']
    if configured and configured[-1].arguments:
        source = Path(configured[-1].arguments[0]).expanduser().resolve()
    rendered = {}
    for path in sorted(source.glob('*.kdl')):
        if path.is_file():
            rendered[path.name] = render_layout(path.read_text(encoding='utf-8'), path.name, settings).encode('utf-8')
    if settings['layout'] in ['dev', 'zjstatus', 'minimal'] and settings['layout'] + '.kdl' not in rendered:
        raise ConfigError(f'Layout {settings["layout"]} is missing from {source}')
    identity = hashlib.sha256(json_bytes({name: hashlib.sha256(data).hexdigest()
                                         for name, data in rendered.items()})).hexdigest()
    destination = directory / ('layouts-' + identity)
    if destination.is_symlink() or (destination.exists() and not destination.is_dir()):
        raise ConfigError(f'Unsafe runtime layout directory: {destination}')
    if not destination.exists():
        stage = private_tempdir(directory, '.layouts-')
        try:
            for name, data in rendered.items():
                atomic_write(stage / name, data)
            os.replace(stage, destination)
        finally:
            if stage.exists():
                shutil.rmtree(stage)
    else:
        for name, data in rendered.items():
            path = destination / name
            if path.is_symlink() or not path.is_file() or path.read_bytes() != data:
                raise ConfigError(f'Runtime layout snapshot changed: {path}')
    return set_root_nodes(text, {'layout_dir': 'layout_dir ' + quote(destination.as_posix())})


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
    """Return startup argv for a verified config generation, preserving source bytes.

    Only aliases matching adjacent pin metadata get managed plugin fallback.
    Preferences can apply without a manifest. No real Zellij parsing happens
    here; the installer/checker provide that separate validation step.
    """
    from .preferences import LOCAL_FILE, settings_snapshot, render_config
    now = int(time.time()) if now is None else now
    file = file.resolve()
    settings_file = file.parent / LOCAL_FILE
    settings, settings_bytes = settings_snapshot(file.parent)
    if settings is not None and settings['git_status'] and not shutil.which('git'):
        print('zj: Git status disabled for this launch: git is not on PATH.', flush=True)
        settings = {**settings, 'git_status': False}
    manifest = next((path for path in [file.parent / 'versions.json',
                                      file.parent / '.zellij-config-versions.json']
                     if path.is_file() and not path.is_symlink()), None)
    if manifest is None and settings is None:
        return arguments
    pins = validate_versions(read_json(manifest)) if manifest else {'plugins': []}
    text = file.read_text(encoding='utf-8')
    active = set(plugin_locations(text))
    selected = []
    for pin in pins['plugins']:
        aliases = {plugin_url(pin), 'file:' + (file.parent / 'plugins' / pin['asset']).as_posix()}
        if active & aliases:
            selected.append((pin, active & aliases))
    if not selected and settings is None:
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
        configured = replace_plugin_locations(text, replacements)
        if settings is not None:
            configured = render_config(configured, settings)
            configured = snapshot_layouts(configured, arguments, file, directory, settings)
        rendered = configured.encode('utf-8')
        # Source config, pins and local preferences can change during downloads.
        current_settings = settings_file.read_bytes() if settings_file.is_file() else None
        if (file.read_text(encoding='utf-8') != text
                or (manifest is not None and validate_versions(read_json(manifest)) != pins)
                or current_settings != settings_bytes):
            raise ConfigError('Config or pins changed during plugin preparation; rerun zj')
        # Keep generations immutable: another launch must not switch the active
        # session's plugin selection or replace the config it watches.
        generation = hashlib.sha256(rendered).hexdigest()
        output = directory / (generation + '.kdl')
        store_if_changed(output, rendered)
    return arguments_for_config(arguments, file, output)
