"""Filesystem and network primitives shared by setup, validation and upgrades."""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request


class ConfigError(Exception):
    """An actionable error suitable for the command line."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path):
    with path.open(encoding='utf-8') as stream:
        return json.load(stream)


def atomic_write(path: Path, data: bytes, mode: int = 0o600) -> None:
    """Replace a file without opening an existing destination symlink."""
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)


def json_bytes(value) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode('utf-8')


class FileLock:
    """An OS-released lock; the inode deliberately survives release to avoid races."""

    def __init__(self, path: Path):
        self.path = path
        self.fd = None

    def __enter__(self):
        if self.path.is_symlink():
            raise ConfigError(f'Refusing a lock symlink: {self.path}')
        flags = os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0)
        self.fd = os.open(self.path, flags, 0o600)
        try:
            info = os.fstat(self.fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ConfigError(f'Unsafe lock file: {self.path}')
            if hasattr(os, 'getuid') and info.st_uid != os.getuid():
                raise ConfigError(f'Lock belongs to another user: {self.path}')
            if os.name == 'nt':
                import msvcrt
                if info.st_size == 0:
                    os.write(self.fd, b'0')
                os.lseek(self.fd, 0, os.SEEK_SET)
                msvcrt.locking(self.fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            os.close(self.fd)
            self.fd = None
            raise
        return self

    def __exit__(self, *_):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


def private_tempdir(parent: Path, prefix: str) -> Path:
    """Private from creation on POSIX; restrict inherited Windows ACLs before use."""
    path = Path(tempfile.mkdtemp(prefix=prefix, dir=parent))
    try:
        if os.name == 'nt':
            identity = subprocess.run(['whoami', '/user', '/fo', 'csv', '/nh'],
                                      capture_output=True, check=True, timeout=10)
            match = re.search(rb'S-1-(?:\d+-)*\d+', identity.stdout)
            if not match:
                raise ConfigError('Could not establish the current Windows user SID')
            sid = match.group().decode('ascii')
            subprocess.run(['icacls', str(path), '/inheritance:r', '/grant:r',
                            f'*{sid}:(OI)(CI)F', '*S-1-5-18:(OI)(CI)F'],
                           capture_output=True, check=True, timeout=10)
        else:
            path.chmod(0o700)
    except BaseException:
        path.rmdir()
        raise
    return path


def load_versions(root: Path) -> dict:
    return validate_versions(read_json(root / 'versions.json'))


def validate_versions(pins: dict) -> dict:
    if not isinstance(pins, dict) or pins.get('schema') != 1 or not isinstance(pins.get('plugins'), list):
        raise ConfigError('Unsupported versions.json schema')

    def text(value, label, pattern=None):
        if (not isinstance(value, str) or not value or any(ord(c) < 32 for c in value)
                or (pattern and not re.fullmatch(pattern, value))):
            raise ConfigError(f'Invalid {label} in version metadata')
        return value

    names, assets = set(), set()
    for plugin in pins['plugins']:
        if not isinstance(plugin, dict):
            raise ConfigError('Invalid plugin metadata')
        name = text(plugin.get('name'), 'plugin name', r'[A-Za-z0-9_-]+')
        asset = text(plugin.get('asset'), 'plugin asset', r'[A-Za-z0-9_.-]+\.wasm')
        if name in names:
            raise ConfigError(f'Invalid or duplicate plugin name: {name}')
        if asset in assets:
            raise ConfigError(f'Invalid or duplicate plugin asset: {asset}')
        text(plugin.get('repository'), 'GitHub repository', r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+')
        text(plugin.get('tag'), 'plugin tag')
        text(plugin.get('sha256'), 'plugin digest', r'[0-9a-f]{64}')
        notice = text(plugin.get('license_path'), 'upstream license path', r'[A-Za-z0-9_./-]+')
        if notice.startswith('/') or any(part in ['', '.', '..'] for part in notice.split('/')):
            raise ConfigError('Invalid upstream license path')
        if plugin.get('license') != 'MIT':
            raise ConfigError(f'Review redistribution permission before bundling {name}')
        names.add(name)
        assets.add(asset)
    zellij = pins.get('zellij')
    if not isinstance(zellij, dict) or not isinstance(zellij.get('assets'), dict) or not zellij['assets']:
        raise ConfigError('Invalid Zellij metadata')
    text(zellij.get('tag'), 'Zellij tag')
    for asset, digest in zellij['assets'].items():
        text(asset, 'Zellij asset name', r'[A-Za-z0-9_.-]+')
        text(digest, 'Zellij digest', r'[0-9a-f]{64}')
    return pins


def plugin_url(plugin: dict) -> str:
    tag = urllib.parse.quote(plugin['tag'], safe='')
    return f"https://github.com/{plugin['repository']}/releases/download/{tag}/{plugin['asset']}"


class HTTPSRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme != 'https':
            raise ConfigError('Refusing an HTTPS downgrade redirect')
        return super().redirect_request(request, fp, code, message, headers, newurl)


def fetch_bytes(url: str, limit: int = 128 * 1024 * 1024, *, timeout=10, budget=45, attempts=2) -> bytes:
    """Bounded HTTPS fetch; preserve inherited proxy and system CA settings."""
    if urllib.parse.urlsplit(url).scheme != 'https':
        raise ConfigError('Only HTTPS download URLs are supported')
    opener = urllib.request.build_opener(HTTPSRedirects())
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'zellij-config/1'})
            deadline = time.monotonic() + budget
            with opener.open(request, timeout=timeout) as response:
                result = bytearray()
                while True:
                    if time.monotonic() > deadline:
                        raise TimeoutError(f'Download exceeded {budget} seconds')
                    block = response.read(min(65536, limit - len(result) + 1))
                    if not block:
                        return bytes(result)
                    result.extend(block)
                    if len(result) > limit:
                        raise ConfigError('Download exceeds the size limit')
        except urllib.error.HTTPError as error:
            if error.code < 500 or attempt + 1 == attempts:
                raise ConfigError(f'HTTP {error.code} fetching {url}') from error
        except (OSError, urllib.error.URLError) as error:
            if attempt + 1 == attempts:
                raise ConfigError(f'Could not download {url}: {error}') from error
        time.sleep(0.25)
    raise ConfigError(f'Could not download {url}')


def github_release(repository: str, tag: str = 'latest') -> dict:
    endpoint = 'latest' if tag == 'latest' else 'tags/' + urllib.parse.quote(tag, safe='')
    return json.loads(fetch_bytes(f'https://api.github.com/repos/{repository}/releases/{endpoint}', 4 * 1024 * 1024))
