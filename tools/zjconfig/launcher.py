"""On-demand release notices; never edits pins or installed plugin files."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.parse

from .common import ConfigError, FileLock, atomic_write, github_release, json_bytes, plugin_url, read_json, spawn_detached
from .install import default_directory
from .kdl import plugin_locations


def config_file(arguments: list[str]) -> Path:
    selected, directory = None, None
    index = 0
    while index < len(arguments):
        argument = arguments[index]
        if argument == '--':
            break
        if argument in ['--config', '-c', '--config-dir']:
            index += 1
            if index >= len(arguments):
                raise ConfigError(f'Missing value for {argument}')
            if argument == '--config-dir':
                directory = arguments[index]
            else:
                selected = arguments[index]
        elif argument.startswith('--config='):
            selected = argument.split('=', 1)[1]
        elif argument.startswith('--config-dir='):
            directory = argument.split('=', 1)[1]
        elif argument.startswith('-c') and len(argument) > 2:
            selected = argument[2:]
        index += 1
    # --config is a file selector; config-dir supplies layouts/themes, rather
    # than overriding an explicit file supplied through the environment.
    selected = selected or os.environ.get('ZELLIJ_CONFIG_FILE')
    return (Path(selected).expanduser() if selected else
            Path(directory).expanduser() / 'config.kdl' if directory else
            default_directory() / 'config.kdl').resolve()


def locations(file: Path) -> list[str]:
    file = file.resolve()
    found = plugin_locations(file.read_text(encoding='utf-8'))
    # Verified local installs retain their exact upstream pins for update checks.
    ledger = file.parent / '.zellij-config-versions.json'
    if ledger.is_file() and not ledger.is_symlink():
        pins = read_json(ledger)
        mapping = {'file:' + (file.parent / 'plugins' / pin['asset']).as_posix(): plugin_url(pin)
                   for pin in pins.get('plugins', [])}
        found = [mapping.get(location, location) for location in found]
    return sorted(set(found))  # Python strings preserve case-sensitive tag identity.


@dataclass
class Scan:
    lines: list[str] = field(default_factory=list)
    different: bool = False
    incomplete: bool = False
    checked: int = 0

    @property
    def code(self):
        return 2 if self.incomplete or not self.checked else 1 if self.different else 0


def scan(file: Path, urls: list[str] | None = None) -> Scan:
    result = Scan(lines=[f'Plugin pins in {file}:'])
    for location in locations(file) if urls is None else urls:
        parsed = urllib.parse.urlsplit(location)
        parts = parsed.path.strip('/').split('/')
        if (parsed.scheme != 'https' or parsed.hostname != 'github.com' or len(parts) != 6
                or parts[2:4] != ['releases', 'download']):
            result.lines.append(f'  {location}: no GitHub release pin to check')
            continue
        repository, pin = '/'.join(parts[:2]), urllib.parse.unquote(parts[4])
        try:
            release = github_release(repository)
            latest = release['tag_name']
            if not isinstance(latest, str) or not latest:
                raise ConfigError('Release has no tag name')
            result.checked += 1
            if latest == pin:
                result.lines.append(f'  {parts[1]:16} {pin:10} current')
            else:
                result.different = True
                result.lines.append(f'  {parts[1]:16} {pin:10} -> {latest} (different latest release)')
        except (ConfigError, KeyError, ValueError) as error:
            result.incomplete = True
            result.lines.append(f'  {repository}: could not check ({error})')
            # Bound offline startup to one failing request, including redirects.
            break
    return result


def state_directory() -> Path:
    if os.name == 'nt':
        return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'zellij-config'
    return Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'zellij-config'


def scan_cache(file: Path, urls: list[str]) -> tuple[Path, Path]:
    key = hashlib.sha256(json_bytes([str(file.resolve()), urls])).hexdigest()
    directory = state_directory()
    if directory.is_symlink():
        raise ConfigError('Refusing a symlink for the update state directory')
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    return directory / (key + '.json'), directory / (key + '.lock')


def cache_data(stamp: Path) -> dict:
    try:
        data = read_json(stamp)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def cached_scan(file: Path, urls: list[str], now: int | None = None) -> Scan | None:
    now = int(time.time()) if now is None else now
    stamp, lock = scan_cache(file, urls)
    with FileLock(lock):
        data = cache_data(stamp)
        if isinstance(data.get('next'), int) and now < data['next']:
            return None
        result = scan(file, urls)
        wait = 86400 if result.code == 2 else 2592000
        atomic_write(stamp, json_bytes({'next': now + wait, 'complete': result.code != 2,
                                      'notice': asdict(result), 'shown': False}))
        return result


def background_updates(file: Path, urls: list[str], now=None) -> Scan | None:
    """Only local cache I/O at startup; the detached worker owns network I/O."""
    now = int(time.time()) if now is None else now
    stamp, lock = scan_cache(file, urls)
    result, command = None, None
    try:
        with FileLock(lock):
            data = cache_data(stamp)
            result = None
            notice = data.get('notice')
            if isinstance(notice, dict) and not data.get('shown'):
                lines = notice.get('lines')
                if (isinstance(lines, list) and all(isinstance(line, str) for line in lines)
                        and isinstance(notice.get('checked'), int)
                        and isinstance(notice.get('different'), bool)
                        and isinstance(notice.get('incomplete'), bool)):
                    result = Scan(**{key: notice[key] for key in ['lines', 'checked', 'different', 'incomplete']})
                data['shown'] = True
                atomic_write(stamp, json_bytes(data))
            due = not isinstance(data.get('next'), int) or now >= data['next']
            pending = isinstance(data.get('worker_until'), int) and now < data['worker_until'] <= now + 600
            if due and not pending:
                # Reserve before spawning; rapid launches don't create a worker
                # per terminal. A crashed worker can be retried after 10 minutes.
                data['worker_until'] = now + 600
                atomic_write(stamp, json_bytes(data))
                command = [sys.executable, str(Path(__file__).resolve().parents[1] / 'manage.py'),
                           'launch', '--update-worker', str(file.resolve())]
        # Release the reservation lock before the worker starts: a very fast
        # child must be able to acquire the same lock to refresh the cache.
        if command:
            try:
                spawn_detached(command)
            except OSError:
                with FileLock(lock):
                    current = cache_data(stamp)
                    if current.get('worker_until') == now + 600:
                        current.pop('worker_until')
                        atomic_write(stamp, json_bytes(current))
    except OSError:
        # Includes a worker holding the nonblocking cache lock: skip immediately.
        pass
    return result


def launch(arguments: list[str]) -> int:
    if arguments and arguments[0] == '--':
        arguments = arguments[1:]
    if arguments and arguments[0] == '--check-updates':
        if os.environ.get('ZJ_OFFLINE'):
            print('Plugin update checks are disabled by ZJ_OFFLINE.')
            return 2
        if len(arguments) > 2:
            raise ConfigError('Usage: zj --check-updates [FILE]')
        file = Path(arguments[1]).expanduser().resolve() if len(arguments) == 2 else config_file([])
        try:
            result = scan(file)
        except (OSError, ConfigError, ValueError) as error:
            print(f'Could not check plugin pins: {error}')
            return 2
        print('\n'.join(result.lines))
        return result.code
    executable = shutil.which('zellij')
    if not executable:
        raise ConfigError('zellij is not on PATH')
    from .runtime import needs_plugins, prepare
    startup = needs_plugins(arguments)
    file = None
    if startup:
        file = config_file(arguments)
        if file.is_file():
            arguments = prepare(file, arguments, state_directory(), offline=bool(os.environ.get('ZJ_OFFLINE')))
    if not os.environ.get('ZJ_NO_UPDATE_CHECK') and not os.environ.get('ZJ_OFFLINE') and file is not None:
        try:
            if file.is_file():
                result = background_updates(file, locations(file))
                if result and (result.different or result.incomplete):
                    print('\n'.join(result.lines), flush=True)
                    print('Pins are unchanged. Use the repository version command to review an upgrade.', flush=True)
        except (ConfigError, OSError, ValueError) as error:
            # Update-notification trouble must not prevent opening the terminal.
            print(f'zj: update check skipped: {error}', flush=True)
    if os.name == 'nt':
        return subprocess.call([executable, *arguments])
    os.execv(executable, [executable, *arguments])
    return 127
