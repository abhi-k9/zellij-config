"""Staged installs and reversible directory publication on Unix and Windows."""
from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
import time

from .common import ConfigError, FileLock, atomic_write, json_bytes, load_versions, plugin_url, private_tempdir, read_json, sha256, validate_versions, zellij_executable
from .kdl import plugin_locations, quote, replace_plugin_locations
from .plugin_files import acquire


def default_directory() -> Path:
    if os.environ.get('ZELLIJ_CONFIG_DIR'):
        return Path(os.environ['ZELLIJ_CONFIG_DIR']).expanduser()
    home = Path.home()
    if os.name == 'nt':
        return Path(os.environ.get('APPDATA', home / 'AppData/Roaming')) / 'Zellij/config'
    legacy = home / '.config/zellij'
    if legacy.is_dir():
        return legacy
    if __import__('sys').platform == 'darwin':
        platform = home / 'Library/Application Support/org.Zellij-Contributors.Zellij'
        return platform if platform.is_dir() else legacy
    return Path(os.environ.get('XDG_CONFIG_HOME', home / '.config')) / 'zellij'


def remove(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def validate(directory: Path, zellij: str) -> None:
    """Check shipped files and effective preferences without baking local values."""
    validate_kdl(directory, zellij)
    from .preferences import read_settings, render_directory
    settings = read_settings(directory)
    if settings is not None:
        with tempfile.TemporaryDirectory(prefix='zj-preferences-') as temporary:
            staged = Path(temporary)
            shutil.copy2(directory / 'config.kdl', staged / 'config.kdl')
            for name in ['layouts', 'themes']:
                if (directory / name).is_dir():
                    shutil.copytree(directory / name, staged / name)
            render_directory(staged, settings)
            validate_kdl(staged, zellij)


def validate_kdl(directory: Path, zellij: str) -> None:
    for layout in [None, *sorted((directory / 'layouts').glob('*.kdl'))]:
        if layout and layout.name.endswith('.swap.kdl'):
            continue
        args = [zellij, '--config', str(directory / 'config.kdl'), '--config-dir', str(directory)]
        if layout:
            args.extend(['--layout', str(layout)])
        result = subprocess.run(args + ['setup', '--check'], text=True, capture_output=True, timeout=30)
        if result.returncode:
            raise ConfigError(f'Zellij rejected {layout or directory / "config.kdl"}:\n{result.stdout}{result.stderr}')


def materialize(directory: Path) -> None:
    """Copy a managed directory link's contents, without following nested links."""
    if directory.is_symlink():
        if not directory.is_dir():
            raise ConfigError(f'Managed directory link has no readable target: {directory}')
        staged = private_tempdir(directory.parent, directory.name + '.materialized-')
        shutil.copytree(directory.resolve(), staged, symlinks=True, dirs_exist_ok=True)
        directory.unlink()
        os.replace(staged, directory)
    elif directory.exists() and not directory.is_dir():
        raise ConfigError(f'Expected a directory: {directory}')
    else:
        directory.mkdir(exist_ok=True)


def snapshots(target: Path) -> list[tuple[int, int, Path, Path]]:
    found = []
    # iterdir avoids treating brackets or other legal path characters as globs.
    for entry in target.parent.iterdir():
        if not entry.name.startswith(target.name + '.backup-') or entry.is_symlink() or not entry.is_dir():
            continue
        legacy = re.fullmatch(re.escape(target.name) + r'\.backup-(\d{8}-\d{6})(?:-(\d+))?', entry.name)
        if legacy and (entry / 'config.kdl').is_file():
            stamp = int(datetime.strptime(legacy[1], '%Y%m%d-%H%M%S').timestamp()) * 10**9
            found.append((stamp, int(legacy[2] or 0), entry, entry))
            continue
        metadata = entry / 'snapshot.json'
        if metadata.is_file() and not metadata.is_symlink():
            data = read_json(metadata)
            if data.get('format') != 'zjconfig-backup-v1' or not isinstance(data.get('created_ns'), int):
                raise ConfigError(f'Invalid snapshot metadata: {metadata}')
            tree = entry / 'tree'
            if data.get('has_tree') is False and not tree.exists():
                continue
            if not tree.is_dir() or tree.is_symlink():
                raise ConfigError(f'Invalid snapshot tree: {entry}')
            found.append((data['created_ns'], 0, entry, tree))
    return sorted(found, key=lambda item: (item[0], item[1], str(item[2])))


def recover(target: Path) -> None:
    journal = target.parent / ('.' + target.name + '.zj-journal.json')
    if not journal.exists():
        return
    if journal.is_symlink():
        raise ConfigError(f'Unsafe recovery journal: {journal}')
    data = read_json(journal)
    stage, backup = Path(data['stage']), Path(data['backup'])
    if (data.get('target') != str(target) or stage.parent != target.parent or backup.parent != target.parent
            or not stage.name.startswith(target.name + '.stage-')
            or not backup.name.startswith(target.name + '.backup-')
            or stage.is_symlink() or backup.is_symlink()):
        raise ConfigError(f'Review the recovery journal manually: {journal}')
    if not target.exists() and (backup / 'tree').is_dir():
        os.replace(backup / 'tree', target)
        print(f'Recovered the previous config after an interrupted publication: {target}')
    if not target.exists() and not data.get('fresh'):
        raise ConfigError(f'Recovery needs manual attention: {backup}')
    remove(stage)
    if backup.exists() and not (backup / 'tree').exists():
        remove(backup)
    journal.unlink()


def publish(target: Path, stage: Path) -> Path | None:
    """Rollback on exceptions/signals; retain a private snapshot of the old tree.

    There is a short directory-name gap between the two renames. A durable
    journal allows the next invocation to recover a process killed in that gap.
    This is not an atomic exchange or a power-loss durability guarantee.
    """
    previous = snapshots(target)
    created = max(time.time_ns(), previous[-1][0] + 1 if previous else 0)
    backup = private_tempdir(target.parent, target.name + '.backup-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '-')
    journal = target.parent / ('.' + target.name + '.zj-journal.json')
    fresh = not target.exists()
    moved = False
    try:
        atomic_write(backup / 'snapshot.json', json_bytes({'format': 'zjconfig-backup-v1', 'created_ns': created, 'has_tree': not fresh}))
        atomic_write(journal, json_bytes({'target': str(target), 'stage': str(stage), 'backup': str(backup), 'fresh': fresh}))
        if not fresh:
            os.replace(target, backup / 'tree')
            moved = True
        os.replace(stage, target)
    except BaseException:
        if moved and not target.exists():
            os.replace(backup / 'tree', target)
        if target.exists() or fresh:
            journal.unlink(missing_ok=True)
            # A signal can arrive after the final rename has succeeded. The
            # new tree is then active; retain the old tree as a valid snapshot.
            if not (backup / 'tree').exists():
                remove(backup)
        raise
    try:
        journal.unlink()
    except OSError as error:
        print(f'Publication completed; journal cleanup will be retried next time: {error}')
    if fresh:
        try:
            remove(backup)
        except OSError as error:
            print(f'Publication completed; empty snapshot cleanup needs attention: {backup}: {error}')
        return None
    return backup


def default_binary_directory() -> Path:
    return (Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'Programs/zellij-config/bin'
            if os.name == 'nt' else Path.home() / '.local/bin')


def install_launcher(root: Path, binary_dir: Path) -> None:
    binary_dir.mkdir(parents=True, exist_ok=True)
    with FileLock(binary_dir / '.zj-helper.lock'):
        stage = private_tempdir(binary_dir, '.zj-helper-')
        helper = binary_dir / '.zellij-config'
        old = stage / 'old'
        try:
            new = stage / 'new'
            new.mkdir()
            shutil.copy2(root / 'tools/manage.py', new / 'manage.py')
            shutil.copytree(root / 'tools/zjconfig', new / 'zjconfig', ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copy2(root / 'versions.json', new / 'versions.json')
            if helper.is_symlink():
                raise ConfigError(f'Refusing to replace helper symlink: {helper}')
            if helper.exists():
                os.replace(helper, old)
            try:
                os.replace(new, helper)
            except BaseException:
                if old.exists():
                    os.replace(old, helper)
                raise
            for name in ['zj', 'zj.cmd', 'zj.ps1']:
                destination = binary_dir / name
                if destination.exists() or destination.is_symlink():
                    if destination.is_symlink() or 'zellij-config launcher' not in destination.read_text(encoding='utf-8'):
                        print(f'Kept an existing unrelated launcher: {destination}')
                        continue
                atomic_write(destination, (root / 'launcher' / name).read_bytes(), 0o755)
        finally:
            remove(stage)
    print(f'Installed launcher helpers in {binary_dir}; add that directory to PATH if needed.')


def install(root: Path, *, target: Path | None = None, offline=False, restore=False,
            dry_run=False, bin_dir: Path | None = None, no_launcher=False) -> None:
    source = root.resolve()
    requested = (target or default_directory()).expanduser()
    # resolve also normalizes trailing slashes and preserves a whole-directory
    # symlink by operating on its physical target, never on the link itself.
    target = requested.resolve()
    if target == Path(target.anchor) or target == source or target in source.parents or source in target.parents:
        raise ConfigError('The installation target must be outside the source tree and cannot be a filesystem root')
    quote(target.as_posix())  # reject unsupported control characters before mutation
    if target.exists() and not target.is_dir():
        raise ConfigError(f'Target is not a directory: {target}')
    if dry_run:
        print(f'Would {"restore the latest snapshot into" if restore else "stage, validate and install into"} {target}')
        print('No files, locks, backups or downloads created.')
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    handler = signal.getsignal(signal.SIGTERM)

    def interrupted(_signum, _frame):
        raise KeyboardInterrupt('Installation interrupted')

    signal.signal(signal.SIGTERM, interrupted)
    try:
        with FileLock(target.parent / ('.' + target.name + '.zj-install.lock')):
            recover(target)
            zellij = zellij_executable(shutil.which)
            if not restore:
                pins = load_versions(root)
                source_text = (source / 'config.kdl').read_text(encoding='utf-8')
                if plugin_locations(source_text) != sorted(plugin_url(pin) for pin in pins['plugins']):
                    raise ConfigError('Source config pins differ from versions.json; update the canonical inventory first')
                # Reject invalid target-owned preferences before acquiring any
                # plugins. The source checkout's machine settings are not copied.
                from .preferences import read_settings
                read_settings(target)
                notices = {}
                for pin in pins['plugins']:
                    notice = (root / 'licenses' / (pin['name'] + '.txt')).read_bytes()
                    if b'Copyright' not in notice or b'Permission is hereby granted, free of charge' not in notice:
                        raise ConfigError(f'Missing required MIT notice for {pin["name"]}')
                    notices[pin['name'] + '.txt'] = notice
            stage = private_tempdir(target.parent, target.name + '.stage-')
            try:
                if restore:
                    choices = snapshots(target)
                    logical = requested.absolute()
                    if logical != target:
                        choices.extend(snapshots(logical))
                        choices.sort(key=lambda item: (item[0], item[1], str(item[2])))
                    if not choices:
                        raise ConfigError(f'No snapshots found for {target}')
                    selected = choices[-1]
                    shutil.copytree(selected[3], stage, symlinks=True, dirs_exist_ok=True)
                    ledger = stage / '.zellij-config-versions.json'
                    if ledger.is_file():
                        recorded = validate_versions(read_json(ledger))
                        for pin in recorded['plugins']:
                            if sha256(stage / 'plugins' / pin['asset']) != pin['sha256']:
                                raise ConfigError(f'Snapshot plugin checksum mismatch: {pin["asset"]}')
                    print(f'Restoring snapshot: {selected[2]}')
                else:
                    if target.exists():
                        shutil.copytree(target, stage, symlinks=True, dirs_exist_ok=True)
                    for directory in ['layouts', 'themes', 'plugins']:
                        materialize(stage / directory)
                    atomic_write(stage / 'config.kdl', (source / 'config.kdl').read_bytes())
                    for directory in ['layouts', 'themes']:
                        for file in (source / directory).iterdir():
                            if file.is_file():
                                atomic_write(stage / directory / file.name, file.read_bytes())
                    text = (stage / 'config.kdl').read_text(encoding='utf-8')
                    locations = {}
                    for plugin in pins['plugins']:
                        bundled = root / 'plugins' / plugin['asset']
                        output = stage / 'plugins' / plugin['asset']
                        data, origin = acquire(plugin, bundled, offline=offline)
                        atomic_write(output, data)
                        print(f'{plugin["name"]}: verified {origin}')
                        locations[plugin_url(plugin)] = 'file:' + (target / 'plugins' / plugin['asset']).as_posix()
                    text = replace_plugin_locations(text, locations)
                    atomic_write(stage / 'config.kdl', text.encode('utf-8'))
                    atomic_write(stage / '.zellij-config-versions.json', json_bytes(pins))
                    license_dir = stage / 'third-party-licenses'
                    materialize(license_dir)
                    for name, notice in notices.items():
                        atomic_write(license_dir / name, notice)
                validate(stage, zellij)
                if not restore and not no_launcher:
                    if bin_dir is None:
                        bin_dir = default_binary_directory()
                    install_launcher(root, bin_dir.expanduser().resolve())
                backup = publish(target, stage)
                if backup:
                    print(f'Previous configuration saved privately in {backup / "tree"}')
                print(f'{"Restored" if restore else "Installed and verified"}: {requested}')
            finally:
                remove(stage)
    finally:
        signal.signal(signal.SIGTERM, handler)
