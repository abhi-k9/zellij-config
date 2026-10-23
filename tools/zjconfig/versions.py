"""Explicit version selection and verified Zellij/plugin artifact management."""
from __future__ import annotations

import hashlib
import io
from pathlib import Path
import platform
import re
import tarfile
import zipfile

from .common import ConfigError, FileLock, atomic_write, fetch_bytes, github_release, json_bytes, load_versions, plugin_url


def checksums(pins: dict) -> bytes:
    return ('# Generated from versions.json; update with tools/manage.py versions update.\n' +
            ''.join(f"{p['sha256']}  {plugin_url(p)}\n" for p in pins['plugins'])).encode()


def documentation(pins: dict) -> bytes:
    lines = ['# Selected versions', '', 'Generated from `versions.json`. Pins change only on an explicit update.', '',
             f"Zellij: **{pins['zellij']['tag']}**. These pins select artifacts; CI records validation.", '',
             '| Plugin | Tag | Release artifact | SHA-256 |', '| --- | --- | --- | --- |']
    lines += [f"| {p['name']} | {p['tag']} | {plugin_url(p)} | `{p['sha256']}` |" for p in pins['plugins']]
    lines += ['', '## Change versions when you choose', '', '```sh',
              'python3 tools/manage.py versions check',
              'python3 tools/manage.py versions update --all',
              'python3 tools/manage.py versions update --plugin zjstatus=latest',
              'python3 tools/manage.py versions update --plugin zjstatus=v0.25.0',
              'python3 tools/manage.py versions update --zellij latest',
              'python3 tools/manage.py versions update --zellij v0.45.1',
              'python3 tools/manage.py install-zellij --bin-dir ~/.local/bin',
              './check.sh', './setup.sh --offline', '```', '',
              'On Windows use `python` instead of `python3`, and `./setup.ps1 -Offline`.', '',
              'Update checks never change files. Update downloads and verifies all selected artifacts',
              'before changing pins, bundled bytes, license notices and generated references.',
              'Review `git diff` and run the checks before committing. Your installed Zellij executable',
              'and configuration change only when you explicitly install them.', '',
              'If a new plugin release has no published GitHub digest, provide a trusted digest with',
              '`--sha256 NAME=HEX`; the updater refuses to treat its own computed hash as independent',
              'verification. Updates never select prereleases through `latest`.', '']
    return '\n'.join(lines).encode()


def release_asset(release: dict, name: str) -> dict:
    found = [asset for asset in release['assets'] if asset['name'] == name]
    if len(found) != 1:
        raise ConfigError(f'Release must contain exactly one {name} asset')
    return found[0]


def published_digest(asset: dict, override: str | None = None) -> str:
    digest = asset.get('digest', '') or ''
    if override:
        if not re.fullmatch('[0-9a-f]{64}', override):
            raise ConfigError('Expected a lowercase SHA-256 digest')
        if digest and digest != 'sha256:' + override:
            raise ConfigError('Supplied checksum disagrees with the published digest')
        return override
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', digest):
        raise ConfigError('Upstream has no published SHA-256; supply a trusted --sha256 NAME=HEX value')
    return digest[7:]


def verified_asset(asset: dict, expected: str) -> bytes:
    data = fetch_bytes(asset['browser_download_url'])
    if hashlib.sha256(data).hexdigest() != expected:
        raise ConfigError(f'Checksum mismatch for {asset["name"]}')
    return data


def check_versions(root: Path) -> int:
    pins = load_versions(root)
    for repository, tag in [('zellij-org/zellij', pins['zellij']['tag']),
                            *[(p['repository'], p['tag']) for p in pins['plugins']]]:
        latest = github_release(repository)['tag_name']
        print(f'{repository}: pinned {tag}; latest {latest}' + (' (different)' if latest != tag else ' (current)'))
    return 0


def update(root: Path, selections: dict[str, str], zellij_tag: str | None,
           all_latest=False, overrides: dict[str, str] | None = None) -> None:
    overrides = overrides or {}
    with FileLock(root / '.versions.lock'):
        pins = load_versions(root)
        original = json_bytes(pins)
        if all_latest:
            selections = {p['name']: 'latest' for p in pins['plugins']} | selections
            zellij_tag = zellij_tag or 'latest'
        unknown = set(selections) - {p['name'] for p in pins['plugins']}
        if unknown:
            raise ConfigError('Unknown plugin(s): ' + ', '.join(sorted(unknown)))
        if not selections and not zellij_tag:
            raise ConfigError('Select --all, --plugin NAME=TAG, or --zellij TAG')
        changes: dict[Path, bytes] = {}
        config = root / 'config/config.kdl'
        original_config = config.read_bytes()
        text = original_config.decode('utf-8')
        for plugin in pins['plugins']:
            if plugin['name'] not in selections:
                continue
            release = github_release(plugin['repository'], selections[plugin['name']])
            tag = release['tag_name']
            if tag == plugin['tag']:
                print(f'{plugin["name"]}: already pinned to {tag}')
                continue
            old_url = plugin_url(plugin)
            asset = release_asset(release, plugin['asset'])
            digest = published_digest(asset, overrides.get(plugin['name']))
            data = verified_asset(asset, digest)
            if not data.startswith(b'\0asm\x01\0\0\0'):
                raise ConfigError('Downloaded plugin is not WebAssembly v1')
            # Retain the exact pinned upstream notice, rather than inventing one.
            from urllib.parse import quote
            notice = fetch_bytes(f"https://raw.githubusercontent.com/{plugin['repository']}/{quote(tag, safe='')}/{plugin['license_path']}", 256 * 1024)
            if 'Permission is hereby granted, free of charge' not in notice.decode('utf-8'):
                raise ConfigError(f'Review the changed license for {plugin["name"]} before updating')
            plugin['tag'], plugin['sha256'] = tag, digest
            text = text.replace(old_url, plugin_url(plugin))
            changes[root / 'plugins' / plugin['asset']] = data
            changes[root / 'licenses' / (plugin['name'] + '.txt')] = notice
        if zellij_tag:
            release = github_release('zellij-org/zellij', zellij_tag)
            old_tag = pins['zellij']['tag']
            pins['zellij']['tag'] = release['tag_name']
            for name in pins['zellij']['assets']:
                pins['zellij']['assets'][name] = published_digest(release_asset(release, name))
            text = text.replace('targeting ' + old_tag, 'targeting ' + release['tag_name'])
        if json_bytes(pins) == original:
            print('All selected pins are already current; no files changed.')
            return
        changes[config] = text.encode('utf-8')
        changes[root / 'versions.json'] = json_bytes(pins)
        changes[root / 'plugins.sha256'] = checksums(pins)
        changes[root / 'VERSIONS.md'] = documentation(pins)
        if config.read_bytes() != original_config or json_bytes(load_versions(root)) != original:
            raise ConfigError('The configuration changed during the download; retry after reviewing local edits')
        old = {path: path.read_bytes() if path.exists() else None for path in changes}
        written = []
        try:
            for path, data in changes.items():
                atomic_write(path, data, 0o644)
                written.append(path)
        except BaseException:
            for path in reversed(written):
                if old[path] is None:
                    path.unlink(missing_ok=True)
                else:
                    atomic_write(path, old[path], 0o644)
            raise
        print('Updated repository pins, verified plugins and notices. Review git diff, run checks, then explicitly reinstall.')


def install_zellij(root: Path, binary_dir: Path) -> Path:
    pins = load_versions(root)
    system, machine = platform.system(), platform.machine().lower()
    arch = 'aarch64' if machine in ['aarch64', 'arm64'] else 'x86_64' if machine in ['x86_64', 'amd64'] else None
    target = {'Linux': 'unknown-linux-musl', 'Darwin': 'apple-darwin', 'Windows': 'pc-windows-msvc'}.get(system)
    if not arch or not target:
        raise ConfigError(f'Unsupported Zellij binary platform: {system}/{machine}')
    name = f'zellij-{arch}-{target}.' + ('zip' if system == 'Windows' else 'tar.gz')
    if name not in pins['zellij']['assets']:
        raise ConfigError(f'No pinned Zellij artifact for {name}')
    url = f"https://github.com/zellij-org/zellij/releases/download/{pins['zellij']['tag']}/{name}"
    data = verified_asset({'name': name, 'browser_download_url': url}, pins['zellij']['assets'][name])
    executable = 'zellij.exe' if system == 'Windows' else 'zellij'
    if system == 'Windows':
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = [info for info in archive.infolist() if Path(info.filename).name == executable]
            if len(members) != 1 or members[0].file_size > 150 * 1024 * 1024:
                raise ConfigError('Invalid Zellij archive member')
            payload = archive.read(members[0])
    else:
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
            member = archive.getmember('zellij')
            if not member.isfile() or member.size > 150 * 1024 * 1024:
                raise ConfigError('Invalid Zellij archive member')
            payload = archive.extractfile(member).read()
    binary_dir = binary_dir.expanduser().resolve()
    binary_dir.mkdir(parents=True, exist_ok=True)
    with FileLock(binary_dir / '.zj-binary.lock'):
        destination = binary_dir / executable
        atomic_write(destination, payload, 0o755)
    print(f'Installed verified {pins["zellij"]["tag"]}: {destination}')
    return destination
