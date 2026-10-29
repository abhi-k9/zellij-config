"""Regression fixtures with mocked network; native cases run on available hosts.

Most installer cases mock Zellij validation to isolate transaction failures.
RealBinaryTests separately exercise the installed binary without opening a TUI.
"""
from __future__ import annotations

import hashlib
import base64
import io
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from zjconfig import check, cli, common, install, kdl, launcher, plugin_files, runtime, versions


class Workspace(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='zj-regression-')
        self.addCleanup(self.temp.cleanup)
        # macOS /var and Windows short temp paths can name the same physical
        # directory differently. Fault injection compares physical destinations.
        self.base = Path(self.temp.name).resolve()
        self.target = self.base / 'config'
        self.bin = self.base / 'bin'

    def clone(self):
        root = self.base / 'repository'
        shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns('.git', 'node_modules', '__pycache__', '.versions.lock'))
        return root

    def old(self):
        self.target.mkdir()
        (self.target / 'config.kdl').write_text('// ORIGINAL CONFIG\n', encoding='utf-8')

    def setup_config(self, root=ROOT, **kwargs):
        """Prepare an offline fixture; real-parser coverage lives in RealBinaryTests."""
        with mock.patch.object(install, 'validate'), mock.patch.object(install.shutil, 'which', return_value=sys.executable):
            install.install(root, target=kwargs.pop('target', self.target), offline=True,
                            no_launcher=kwargs.pop('no_launcher', True), **kwargs)

    def link(self, path, target, directory=False):
        try:
            path.symlink_to(target, target_is_directory=directory)
        except (OSError, NotImplementedError):
            self.skipTest('Creating symbolic links requires native permissions on this runner')


class InstallerTests(Workspace):
    def test_launcher_only_installs_helpers_without_touching_config(self):
        self.old()
        with mock.patch.object(install, 'default_directory', return_value=ROOT), \
                mock.patch.object(install.shutil, 'which', return_value=None):
            self.assertEqual(cli.main(['install', '--launcher-only', '--bin-dir', str(self.bin)]), 0)
        self.assertEqual((self.target / 'config.kdl').read_text(), '// ORIGINAL CONFIG\n')
        for name in ['zj', 'zj.cmd', 'zj.ps1']:
            self.assertEqual((self.bin / name).read_bytes(), (ROOT / 'launcher' / name).read_bytes())
        # Execute the copied Python helper, proving its imports and pins are present.
        result = subprocess.run([sys.executable, str(self.bin / '.zellij-config/manage.py'),
                                 'launch', '--help'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('usage:', result.stdout)
        self.assertFalse((self.bin / 'config.kdl').exists())

    def test_launcher_only_default_dry_run_and_conflicts(self):
        with mock.patch.object(install, 'default_binary_directory', return_value=self.bin):
            self.assertEqual(cli.main(['install', '--launcher-only', '--dry-run']), 0)
            self.assertFalse(self.bin.exists())
            for args in [['--restore'], ['--no-launcher'], ['--config-dir', str(self.target)]]:
                self.assertEqual(cli.main(['install', '--launcher-only', *args]), 1)
            self.assertFalse(self.bin.exists())
            self.assertEqual(cli.main(['install', '--launcher-only']), 0)
        self.assertTrue((self.bin / 'zj').is_file())

    def test_install_restore_and_double_dot_cleanup(self):
        self.old()
        self.setup_config()
        (self.target / '..stale').write_text('not in original snapshot')
        install_text = (self.target / 'config.kdl').read_text(encoding='utf-8')
        self.assertEqual(install_text.count('location="file:'), 3)
        with mock.patch.object(install, 'validate'), mock.patch.object(install.shutil, 'which', return_value=sys.executable):
            install.install(ROOT, target=self.target, restore=True)
        self.assertEqual((self.target / 'config.kdl').read_text(), '// ORIGINAL CONFIG\n')
        self.assertFalse((self.target / '..stale').exists())

    def test_restore_does_not_depend_on_current_source_pins(self):
        root = self.clone()
        self.old()
        self.setup_config(root)
        (root / 'versions.json').unlink()
        (root / 'config.kdl').unlink()
        self.setup_config(root, restore=True)
        self.assertEqual((self.target / 'config.kdl').read_text(), '// ORIGINAL CONFIG\n')

    def test_corrupt_snapshot_plugin_cannot_replace_active_config(self):
        self.setup_config()
        self.setup_config()
        snapshot = install.snapshots(self.target)[-1][3]
        (snapshot / 'plugins/monocle.wasm').write_bytes(b'corrupt snapshot')
        active = (self.target / 'config.kdl').read_bytes()
        with self.assertRaisesRegex(common.ConfigError, 'Snapshot plugin checksum'):
            self.setup_config(restore=True)
        self.assertEqual((self.target / 'config.kdl').read_bytes(), active)
        self.assertFalse(list(self.base.glob('config.stage-*')))

    def test_file_symlink_never_overwrites_dotfiles(self):
        self.target.mkdir()
        original = self.base / 'dotfiles.kdl'
        original.write_text('// precious original\n')
        self.link(self.target / 'config.kdl', original)
        self.setup_config()
        self.assertEqual(original.read_text(), '// precious original\n')
        self.assertFalse((self.target / 'config.kdl').is_symlink())
        with mock.patch.object(install, 'validate'), mock.patch.object(install.shutil, 'which', return_value=sys.executable):
            install.install(ROOT, target=self.target, restore=True)
        self.assertTrue((self.target / 'config.kdl').is_symlink())
        self.assertEqual(original.read_text(), '// precious original\n')

    def test_directory_and_nested_file_symlinks(self):
        physical = self.base / 'dotfiles'
        physical.mkdir()
        self.link(self.target, physical, True)
        outside = self.base / 'outside'
        outside.mkdir()
        content = outside / 'default.kdl'
        content.write_text('// original layout\n')
        self.link(physical / 'layouts', outside, True)
        self.setup_config()
        self.assertTrue(self.target.is_symlink())
        self.assertFalse((physical / 'layouts').is_symlink())
        self.assertEqual(content.read_text(), '// original layout\n')

    def test_no_preexisting_temporary_symlink_is_written(self):
        self.old()
        directory = self.target / 'plugins'
        directory.mkdir()
        victim = self.base / 'victim'
        victim.write_text('UNRELATED')
        self.link(directory / 'monocle.wasm.part', victim)
        self.link(self.target / 'config.kdl.tmp', victim)
        self.setup_config()
        self.assertEqual(victim.read_text(), 'UNRELATED')

    @unittest.skipIf(os.name == 'nt', 'Quote/backslash filenames are Unix-specific')
    def test_quote_space_and_backslash_paths(self):
        target = self.base / 'path with "quote\\slash'
        self.setup_config(target=target)
        parsed = kdl.plugin_locations((target / 'config.kdl').read_text())
        self.assertTrue(all(url.startswith('file:' + target.resolve().as_posix()) for url in parsed))

    def test_trailing_slash_reinstall(self):
        self.old()
        self.setup_config(target=Path(str(self.target) + os.sep))
        self.assertTrue(install.snapshots(self.target))
        self.assertFalse(any(p.name.startswith('.backup-') for p in self.target.iterdir()))

    def test_bad_plugin_does_not_mutate_active_config(self):
        root = self.clone()
        (root / 'plugins/monocle.wasm').write_bytes(b'corrupt')
        self.old()
        with self.assertRaises(common.ConfigError), mock.patch.object(plugin_files, 'fetch_bytes') as fetch:
            self.setup_config(root)
        fetch.assert_not_called()
        self.assertEqual((self.target / 'config.kdl').read_text(), '// ORIGINAL CONFIG\n')
        self.assertEqual(install.snapshots(self.target), [])
        self.assertFalse(list(self.base.glob('config.stage-*')))

    def test_missing_pin_metadata_does_not_mutate(self):
        root = self.clone()
        (root / 'versions.json').unlink()
        self.old()
        with self.assertRaises(FileNotFoundError):
            self.setup_config(root)
        self.assertEqual((self.target / 'config.kdl').read_text(), '// ORIGINAL CONFIG\n')

    def test_validation_failure_has_no_active_changes(self):
        self.old()
        with mock.patch.object(install, 'validate', side_effect=common.ConfigError('bad layout')), \
                mock.patch.object(install.shutil, 'which', return_value=sys.executable), self.assertRaises(common.ConfigError):
            install.install(ROOT, target=self.target, offline=True, no_launcher=True)
        self.assertEqual((self.target / 'config.kdl').read_text(), '// ORIGINAL CONFIG\n')
        self.assertEqual(install.snapshots(self.target), [])

    def test_publication_failure_rolls_back(self):
        self.old()
        replace = os.replace

        def fail_new(source, target):
            if '.stage-' in Path(source).name and Path(target) == self.target:
                raise OSError('injected publication failure')
            return replace(source, target)

        with mock.patch.object(install.os, 'replace', side_effect=fail_new), self.assertRaises(OSError):
            self.setup_config()
        self.assertEqual((self.target / 'config.kdl').read_text(), '// ORIGINAL CONFIG\n')
        self.assertFalse((self.base / '.config.zj-journal.json').exists())

    def test_interrupt_after_publication_retains_previous_snapshot(self):
        self.old()
        replace = install.os.replace

        def interrupt_after_rename(source, target):
            result = replace(source, target)
            if '.stage-' in Path(source).name and Path(target) == self.target:
                raise KeyboardInterrupt('signal immediately after publication')
            return result

        with mock.patch.object(install.os, 'replace', side_effect=interrupt_after_rename), \
                self.assertRaises(KeyboardInterrupt):
            self.setup_config()
        self.assertIn('location="file:', (self.target / 'config.kdl').read_text())
        saved = install.snapshots(self.target)[-1][3]
        self.assertEqual((saved / 'config.kdl').read_text(), '// ORIGINAL CONFIG\n')
        self.setup_config(restore=True)
        self.assertEqual((self.target / 'config.kdl').read_text(), '// ORIGINAL CONFIG\n')

    def test_interrupted_preparation_preserves_unrelated_parts(self):
        self.old()
        (self.target / 'unrelated.part').write_text('keep')
        with mock.patch.object(install, 'validate', side_effect=KeyboardInterrupt), \
                mock.patch.object(install.shutil, 'which', return_value=sys.executable), self.assertRaises(KeyboardInterrupt):
            install.install(ROOT, target=self.target, offline=True, no_launcher=True)
        self.assertEqual((self.target / 'unrelated.part').read_text(), 'keep')
        self.assertFalse(list(self.base.glob('config.stage-*')))

    def test_dry_run_creates_nothing(self):
        absent = self.base / 'missing-parent/config'
        install.install(ROOT, target=absent, dry_run=True, offline=True)
        self.assertFalse(absent.parent.exists())

    def test_backup_root_is_private(self):
        self.old()
        self.setup_config()
        snapshot = install.snapshots(self.target)[-1][2]
        if os.name != 'nt':
            self.assertEqual(snapshot.stat().st_mode & 0o777, 0o700)
        else:
            result = subprocess.run(['icacls', str(snapshot)], capture_output=True, check=True)
            self.assertNotIn(b'(I)', result.stdout)

    def test_legacy_snapshot_numeric_suffix(self):
        self.old()
        for suffix in [9, 10]:
            folder = self.base / f'config.backup-20000101-000000-{suffix}'
            folder.mkdir()
            (folder / 'config.kdl').write_text(f'// snapshot {suffix}\n')
        with mock.patch.object(install, 'validate'), mock.patch.object(install.shutil, 'which', return_value=sys.executable):
            install.install(ROOT, target=self.target, restore=True)
        self.assertEqual((self.target / 'config.kdl').read_text(), '// snapshot 10\n')

    def test_exclusive_lock_and_os_release(self):
        path = self.base / 'lock'
        with common.FileLock(path):
            with self.assertRaises(OSError):
                with common.FileLock(path):
                    self.fail('Concurrent lock acquired')
        with common.FileLock(path):
            self.assertTrue(path.exists())

    def test_recover_kill_between_renames(self):
        stage = self.base / 'config.stage-fixture'
        stage.mkdir()
        backup = self.base / 'config.backup-fixture'
        (backup / 'tree').mkdir(parents=True)
        (backup / 'tree/config.kdl').write_text('// recovered\n')
        (self.base / '.config.zj-journal.json').write_bytes(common.json_bytes(
            {'target': str(self.target), 'stage': str(stage), 'backup': str(backup), 'fresh': False}))
        install.recover(self.target)
        self.assertEqual((self.target / 'config.kdl').read_text(), '// recovered\n')
        self.assertFalse(stage.exists())

    def test_reject_forged_recovery_paths(self):
        (self.base / '.config.zj-journal.json').write_bytes(common.json_bytes(
            {'target': str(self.target), 'stage': str(self.base / 'unrelated'),
             'backup': str(self.base / 'unrelated-backup'), 'fresh': False}))
        with self.assertRaises(common.ConfigError):
            install.recover(self.target)

    def test_source_and_root_targets_rejected(self):
        for path in [ROOT / 'config', ROOT, Path(ROOT.anchor)]:
            with self.assertRaises(common.ConfigError):
                install.install(ROOT, target=path, dry_run=True)

    def test_offline_does_not_download(self):
        with mock.patch.object(plugin_files, 'fetch_bytes') as fetch:
            self.setup_config()
        fetch.assert_not_called()

    def test_installed_helper_and_unrelated_launcher(self):
        self.bin.mkdir()
        (self.bin / 'zj').write_text('#!/bin/sh\n# my unrelated launcher\n')
        self.setup_config(no_launcher=False, bin_dir=self.bin)
        self.assertIn('unrelated', (self.bin / 'zj').read_text())
        result = subprocess.run([sys.executable, str(self.bin / '.zellij-config/manage.py'), '--help'], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)


class KDLTests(unittest.TestCase):
    def test_replace_only_active_locations_including_raw_and_escaped_values(self):
        text = ('// "https://example.com/a"\nplugins {\n'
                '  /- dead location="https://example.com/a"\n'
                '  active location=r#"https://example.com/a"#\n'
                '  escaped location="https:\\/\\/example.com/a"\n}\n')
        target = 'file:/path with "quote"/雪.wasm'
        changed = kdl.replace_plugin_locations(text, {'https://example.com/a': target})
        self.assertEqual(kdl.plugin_locations(changed), [target])
        self.assertIn('/- dead location="https://example.com/a"', changed)
        self.assertTrue(changed.startswith('// "https://example.com/a"'))

    def test_comments_raw_strings_and_slashdash(self):
        source = '''plugins {
        /* nested /* inner */ comment */
        /- dead location="https://github.com/dead/repo/releases/download/v1/x.wasm";
        live /- location="bad" location=r#"https://github.com/owner/repo/releases/download/vA/x.wasm"#;
        other location="https://github.com/owner/repo/releases/download/va/x.wasm";
        }
        /- plugins { unused location="bad"; }
        '''
        self.assertEqual(len(kdl.plugin_locations(source)), 2)
        self.assertEqual(kdl.plugin_locations(source)[0].split('/')[-2], 'vA')

    def test_unclosed_comments_strings_and_nodes_fail(self):
        for text in ['/* missing', 'plugins {', 'plugins { x location="missing; }',
                     'x "\\u{41', 'x "\\u{D800}"', 'x "\\u{110000}"']:
            with self.subTest(text=text), self.assertRaises(common.ConfigError):
                kdl.parse(text)

    def test_escaped_path_round_trip(self):
        value = 'file:/some "quoted"/back\\slash/é.wasm'
        self.assertEqual(kdl.plugin_locations('plugins { x location=' + kdl.quote(value) + '; }'), [value])

    def test_control_paths_fail_before_serialization(self):
        with self.assertRaises(common.ConfigError):
            kdl.quote('line\nbreak')


class LauncherTests(Workspace):
    def test_background_dispatch_does_not_run_network_in_foreground(self):
        file = self.config()
        with mock.patch.object(launcher, 'state_directory', return_value=self.base / 'state'), \
                mock.patch.object(launcher, 'spawn_detached') as spawn, \
                mock.patch.object(launcher, 'scan', side_effect=AssertionError('Network on startup')):
            launcher.background_updates(file, launcher.locations(file), now=100)
            launcher.background_updates(file, launcher.locations(file), now=101)
            self.assertEqual(spawn.call_count, 1)
            launcher.background_updates(file, launcher.locations(file), now=701)
            self.assertEqual(spawn.call_count, 2)

    def test_completed_background_notice_is_displayed_once_from_cache(self):
        file = self.config()
        urls = launcher.locations(file)
        with mock.patch.object(launcher, 'state_directory', return_value=self.base / 'state'), \
                mock.patch.object(launcher, 'github_release', return_value={'tag_name': 'v2'}):
            launcher.cached_scan(file, urls, now=100)
        with mock.patch.object(launcher, 'state_directory', return_value=self.base / 'state'), \
                mock.patch.object(launcher, 'spawn_detached') as spawn:
            self.assertTrue(launcher.background_updates(file, urls, now=101).different)
            self.assertIsNone(launcher.background_updates(file, urls, now=102))
        spawn.assert_not_called()

    def test_background_worker_lock_never_blocks_startup(self):
        file = self.config()
        urls = launcher.locations(file)
        with mock.patch.object(launcher, 'state_directory', return_value=self.base / 'state'), \
                mock.patch.object(launcher, 'spawn_detached') as spawn:
            _, lock = launcher.scan_cache(file, urls)
            with common.FileLock(lock):
                self.assertIsNone(launcher.background_updates(file, urls, now=100))
        spawn.assert_not_called()

    def test_failed_background_spawn_can_be_retried(self):
        file = self.config()
        urls = launcher.locations(file)
        with mock.patch.object(launcher, 'state_directory', return_value=self.base / 'state'), \
                mock.patch.object(launcher, 'spawn_detached', side_effect=OSError('unavailable')) as spawn:
            launcher.background_updates(file, urls, now=100)
            launcher.background_updates(file, urls, now=101)
            self.assertEqual(spawn.call_count, 2)
            stamp, _ = launcher.scan_cache(file, urls)
            self.assertNotIn('worker_until', common.read_json(stamp))

    def test_background_reservation_lock_is_released_before_dispatch(self):
        file = self.config()
        urls = launcher.locations(file)
        with mock.patch.object(launcher, 'state_directory', return_value=self.base / 'state'):
            _, lock = launcher.scan_cache(file, urls)

            def dispatch(command):
                with common.FileLock(lock):
                    pass  # A worker can acquire the cache lock immediately.

            with mock.patch.object(launcher, 'spawn_detached', side_effect=dispatch) as spawn:
                launcher.background_updates(file, urls, now=100)
            spawn.assert_called_once()

    def config(self, name='one', tags=('v1',)):
        file = self.base / name / 'config.kdl'
        file.parent.mkdir()
        file.write_text('plugins {\n' + ''.join(
            f'x{i} location="https://github.com/owner/repo{i}/releases/download/{tag}/x.wasm";\n'
            for i, tag in enumerate(tags)) + '}\n')
        return file

    def test_partial_failure_retries_next_day_while_showing_updates(self):
        file = self.config(tags=('v1', 'v1'))
        with mock.patch.object(launcher, 'github_release', side_effect=[{'tag_name': 'v2'}, common.ConfigError('offline')]), \
                mock.patch.object(launcher, 'state_directory', return_value=self.base / 'state'):
            result = launcher.cached_scan(file, launcher.locations(file), now=100)
        self.assertTrue(result.different)
        self.assertEqual(result.code, 2)
        stamp = next((self.base / 'state').glob('*.json'))
        self.assertEqual(common.read_json(stamp)['next'], 100 + 86400)

    def test_cli_config_precedence_and_literal_paths(self):
        file = self.base / 'space [literal]/config.kdl'
        with mock.patch.dict(os.environ, {'ZELLIJ_CONFIG_FILE': str(self.base / 'wrong.kdl')}):
            for args in [['-c', str(file)], ['--config=' + str(file)], ['-c' + str(file)]]:
                self.assertEqual(launcher.config_file(args), file.resolve())
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(launcher.config_file(['--config-dir', str(file.parent)]), file.resolve())

    def test_cache_is_per_config_and_pinset(self):
        a, b = self.config(), self.config('two')
        with mock.patch.object(launcher, 'state_directory', return_value=self.base / 'state'), \
                mock.patch.object(launcher, 'github_release', return_value={'tag_name': 'v1'}) as fetch:
            for file in [a, b, a]:
                launcher.cached_scan(file, launcher.locations(file), now=100)
            self.assertEqual(fetch.call_count, 2)
            a.write_text(a.read_text().replace('/v1/', '/v2/'))
            launcher.cached_scan(a, launcher.locations(a), now=101)
            self.assertEqual(fetch.call_count, 3)

    def test_case_distinct_tags_are_distinct(self):
        file = self.config(tags=('vA', 'va'))
        with mock.patch.object(launcher, 'github_release', return_value={'tag_name': 'va'}):
            result = launcher.scan(file)
        self.assertTrue(result.different)
        self.assertEqual(result.checked, 2)

    def test_dead_comments_are_never_requested(self):
        file = self.config()
        file.write_text('plugins { /* dead location="bad"; */ /- gone location="bad";\n'
                        'live location="https://github.com/owner/live/releases/download/v1/x.wasm"; }')
        with mock.patch.object(launcher, 'github_release', return_value={'tag_name': 'v1'}) as fetch:
            self.assertEqual(launcher.scan(file).code, 0)
        fetch.assert_called_once_with('owner/live')

    def test_local_installs_keep_upstream_update_metadata(self):
        self.setup_config()
        self.assertEqual(launcher.locations(self.target / 'config.kdl'),
                         sorted(common.plugin_url(p) for p in common.load_versions(ROOT)['plugins']))

    def test_installed_update_metadata_through_directory_alias(self):
        self.setup_config()
        alias = self.base / 'config-alias'
        self.link(alias, self.target, True)
        self.assertEqual(launcher.locations(alias / 'config.kdl'),
                         sorted(common.plugin_url(p) for p in common.load_versions(ROOT)['plugins']))

    def test_no_newer_claim_when_latest_is_older(self):
        file = self.config(tags=('v2.0.0',))
        with mock.patch.object(launcher, 'github_release', return_value={'tag_name': 'v1.9.0'}):
            result = launcher.scan(file)
        self.assertIn('different latest release', '\n'.join(result.lines))
        self.assertNotIn('newer', '\n'.join(result.lines))

    def test_https_downgrade_redirect_refused(self):
        with self.assertRaises(common.ConfigError):
            common.HTTPSRedirects().redirect_request(None, None, 302, '', {}, 'http://example.org/insecure')

    def test_unreadable_explicit_config_has_incomplete_exit_status(self):
        self.assertEqual(launcher.launch(['--check-updates', str(self.base / 'missing.kdl')]), 2)

    def test_powershell_transport_preserves_empty_quotes_and_unicode(self):
        arguments = ['run', '', 'space name', 'a"quoted"value', 'é', '$literal;']
        encoded = base64.b64encode(json.dumps(arguments).encode()).decode()
        with mock.patch.object(launcher, 'launch', return_value=0) as run:
            self.assertEqual(cli.main(['launch', '--argv64', encoded]), 0)
        run.assert_called_once_with(arguments)


class RuntimeTests(Workspace):
    def managed(self):
        root = self.base / 'checkout with spaces 雪'
        root.mkdir()
        (root / 'plugins').mkdir()
        pins = common.load_versions(ROOT)
        pins['plugins'] = pins['plugins'][:1]
        pin = pins['plugins'][0]
        data = b'\0asm\x01\0\0\0verified fixture'
        pin['sha256'] = hashlib.sha256(data).hexdigest()
        (root / 'versions.json').write_bytes(common.json_bytes(pins))
        (root / 'plugins' / pin['asset']).write_bytes(data)
        config = root / 'config.kdl'
        config.write_text('plugins { example location=' + kdl.quote(common.plugin_url(pin)) + '; }\n', encoding='utf-8')
        return root, config, pin, data

    def prepare(self, config, arguments=None, **kwargs):
        args = runtime.prepare(config, arguments or [], self.base / 'state', **kwargs)
        file = Path(args[1])
        return args, file, kdl.plugin_locations(file.read_text(encoding='utf-8'))

    def test_online_download_preferred_to_corrupt_bundle_without_editing_checkout(self):
        root, config, pin, data = self.managed()
        before = config.read_bytes()
        (root / 'plugins' / pin['asset']).write_bytes(b'corrupt backup')
        with mock.patch.object(plugin_files, 'fetch_bytes', return_value=data) as fetch:
            args, generated, locations = self.prepare(config)
        fetch.assert_called_once()
        self.assertEqual(Path(locations[0][5:]).read_bytes(), data)
        self.assertNotIn('.bundled.wasm', locations[0])
        self.assertEqual(config.read_bytes(), before)
        self.assertFalse(generated.is_relative_to(root))
        self.assertIn(str(root), args)

    def test_failed_download_uses_verified_bundle(self):
        _, config, _, data = self.managed()
        with mock.patch.object(plugin_files, 'fetch_bytes', side_effect=common.ConfigError('offline')):
            _, _, locations = self.prepare(config)
        self.assertIn('.bundled.wasm', locations[0])
        self.assertEqual(Path(locations[0][5:]).read_bytes(), data)

    def test_bad_download_checksum_uses_verified_bundle(self):
        _, config, _, data = self.managed()
        with mock.patch.object(plugin_files, 'fetch_bytes', return_value=b'wrong upstream bytes'):
            _, _, locations = self.prepare(config)
        self.assertEqual(Path(locations[0][5:]).read_bytes(), data)
        self.assertIn('.bundled.wasm', locations[0])

    def test_no_usable_download_or_bundle_fails_closed(self):
        root, config, pin, _ = self.managed()
        before = config.read_bytes()
        (root / 'plugins' / pin['asset']).unlink()
        with mock.patch.object(plugin_files, 'fetch_bytes', side_effect=common.ConfigError('offline')), \
                self.assertRaisesRegex(common.ConfigError, 'no valid bundled fallback'):
            self.prepare(config)
        self.assertEqual(config.read_bytes(), before)

    def test_explicit_offline_mode_never_fetches(self):
        _, config, _, _ = self.managed()
        with mock.patch.object(plugin_files, 'fetch_bytes') as fetch:
            self.prepare(config, offline=True)
        fetch.assert_not_called()

    def test_verified_prior_download_is_reused_before_bundle(self):
        root, config, pin, data = self.managed()
        with mock.patch.object(plugin_files, 'fetch_bytes', return_value=data):
            _, first, _ = self.prepare(config)
        (root / 'plugins' / pin['asset']).unlink()
        with mock.patch.object(plugin_files, 'fetch_bytes') as fetch:
            _, again, _ = self.prepare(config, offline=True)
        fetch.assert_not_called()
        self.assertEqual(first, again)

    def test_corrupt_download_cache_is_verified_and_repaired(self):
        _, config, _, data = self.managed()
        with mock.patch.object(plugin_files, 'fetch_bytes', return_value=data):
            _, _, locations = self.prepare(config)
        cache = Path(locations[0][5:])
        cache.write_bytes(b'corrupted cache')
        with mock.patch.object(plugin_files, 'fetch_bytes', return_value=data) as fetch:
            self.prepare(config)
        fetch.assert_called_once()
        self.assertEqual(cache.read_bytes(), data)

    def test_fallback_retries_after_cooldown_and_retains_old_generation(self):
        _, config, _, data = self.managed()
        with mock.patch.object(plugin_files, 'fetch_bytes', side_effect=common.ConfigError('offline')):
            _, fallback, _ = self.prepare(config, now=100)
        old = fallback.read_bytes()
        with mock.patch.object(plugin_files, 'fetch_bytes') as fetch, \
                mock.patch.object(runtime, 'atomic_write', side_effect=AssertionError('Rewriting unchanged files')):
            _, again, _ = self.prepare(config, now=101)
        fetch.assert_not_called()
        self.assertEqual(again, fallback)
        with mock.patch.object(plugin_files, 'fetch_bytes', return_value=data) as fetch:
            _, online, locations = self.prepare(config, now=401)
        fetch.assert_called_once()
        self.assertNotEqual(online, fallback)
        self.assertNotIn('.bundled.wasm', locations[0])
        self.assertEqual(fallback.read_bytes(), old)

    def test_cooldown_does_not_block_recovery_when_backup_is_missing(self):
        root, config, pin, data = self.managed()
        with mock.patch.object(plugin_files, 'fetch_bytes', side_effect=common.ConfigError('offline')):
            self.prepare(config, now=100)
        (root / 'plugins' / pin['asset']).unlink()
        with mock.patch.object(plugin_files, 'fetch_bytes', return_value=data) as fetch:
            _, _, locations = self.prepare(config, now=101)
        fetch.assert_called_once()
        self.assertNotIn('.bundled.wasm', locations[0])

    def test_changed_pin_url_bypasses_previous_download_cooldown(self):
        root, config, pin, data = self.managed()
        with mock.patch.object(plugin_files, 'fetch_bytes', side_effect=common.ConfigError('offline')):
            self.prepare(config, now=100)
        previous = common.plugin_url(pin)
        pins = common.read_json(root / 'versions.json')
        pins['plugins'][0]['tag'] = 'vNewTag'
        (root / 'versions.json').write_bytes(common.json_bytes(pins))
        config.write_text(kdl.replace_plugin_locations(config.read_text(encoding='utf-8'),
                          {previous: common.plugin_url(pins['plugins'][0])}), encoding='utf-8')
        with mock.patch.object(plugin_files, 'fetch_bytes', return_value=data) as fetch:
            self.prepare(config, now=101)
        fetch.assert_called_once()

    def test_missing_plugins_download_concurrently(self):
        root = self.clone()
        pins = common.load_versions(root)['plugins']
        payloads = {common.plugin_url(pin): (root / 'plugins' / pin['asset']).read_bytes() for pin in pins}
        barrier = threading.Barrier(3)

        def fetch(url, **kwargs):
            barrier.wait(timeout=5)
            return payloads[url]

        with mock.patch.object(plugin_files, 'fetch_bytes', side_effect=fetch) as download:
            _, _, locations = self.prepare(root / 'config.kdl')
        self.assertEqual(download.call_count, 3)
        self.assertEqual(len(locations), 3)
        self.assertTrue(all('.bundled.wasm' not in location for location in locations))

    def test_source_edits_during_download_are_not_overwritten(self):
        _, config, _, data = self.managed()
        edited = config.read_bytes() + b'// user edit\n'

        def fetch(*args, **kwargs):
            config.write_bytes(edited)
            return data

        with mock.patch.object(plugin_files, 'fetch_bytes', side_effect=fetch), \
                self.assertRaisesRegex(common.ConfigError, 'changed during plugin preparation'):
            self.prepare(config)
        self.assertEqual(config.read_bytes(), edited)

    def test_literal_arguments_and_config_directory_survive_override(self):
        _, config, _, _ = self.managed()
        original = ['--config=' + str(config), '--config-dir', 'other layouts 雪',
                    'attach', 'session with spaces', '--', '', '--config', 'literal"argument']
        args, generated, _ = self.prepare(config, original, offline=True)
        self.assertEqual(args, ['--config', str(generated), *original[1:]])
        self.assertEqual(runtime.arguments_for_config(['-c' + str(config), 'attach'], config, generated),
                         ['--config', str(generated), '--config-dir', str(config.parent), 'attach'])

    def test_help_version_and_validation_do_not_prepare_or_check_network(self):
        with mock.patch.object(launcher.shutil, 'which', return_value=sys.executable), \
                mock.patch.object(launcher.os, 'execv'), mock.patch.object(launcher.subprocess, 'call', return_value=0), \
                mock.patch.object(runtime, 'prepare') as prepare, mock.patch.object(launcher, 'background_updates') as scan:
            for args in [['--version'], ['--help'], ['setup', '--check']]:
                launcher.launch(args)
        prepare.assert_not_called()
        scan.assert_not_called()

    def test_command_words_in_option_values_or_session_names_are_not_commands(self):
        for arguments in [['--session', 'run'], ['--config-dir', 'setup'], ['attach', 'run']]:
            self.assertTrue(runtime.needs_plugins(arguments))
        for arguments in [['--config-dir', 'elsewhere', 'setup', '--check'], ['ls'], ['options', '--clean']]:
            self.assertFalse(runtime.needs_plugins(arguments))

    def test_explicit_environment_config_directory_is_preserved(self):
        with mock.patch.dict(os.environ, {'ZELLIJ_CONFIG_DIR': str(self.base / 'other layouts')}):
            args = runtime.arguments_for_config([], self.base / 'checkout/config.kdl', self.base / 'generated.kdl')
        self.assertEqual(args, ['--config', str(self.base / 'generated.kdl'),
                                '--config-dir', str(self.base / 'other layouts')])

    def test_startup_notices_scan_source_pins_after_runtime_override(self):
        _, config, pin, data = self.managed()
        with mock.patch.dict(os.environ, {'ZJ_OFFLINE': '', 'ZJ_NO_UPDATE_CHECK': ''}), \
                mock.patch.object(plugin_files, 'fetch_bytes', return_value=data), \
                mock.patch.object(launcher, 'state_directory', return_value=self.base / 'state'), \
                mock.patch.object(launcher.shutil, 'which', return_value=sys.executable), \
                mock.patch.object(launcher.os, 'execv'), mock.patch.object(launcher.subprocess, 'call', return_value=0), \
                mock.patch.object(launcher, 'background_updates', return_value=None) as scan:
            launcher.launch(['--config', str(config)])
        scan.assert_called_once_with(config.resolve(), [common.plugin_url(pin)])

    def test_optional_install_also_prefers_downloads(self):
        data = [(ROOT / 'plugins' / pin['asset']).read_bytes() for pin in common.load_versions(ROOT)['plugins']]
        with mock.patch.object(plugin_files, 'fetch_bytes', side_effect=data) as fetch, \
                mock.patch.object(install, 'validate'), mock.patch.object(install.shutil, 'which', return_value=sys.executable):
            install.install(ROOT, target=self.target, no_launcher=True)
        self.assertEqual(fetch.call_count, 3)
        self.assertTrue((self.target / 'config.kdl').is_file())


class CheckerTests(Workspace):
    def test_broken_local_documentation_link_fails(self):
        root = self.clone()
        with (root / 'README.md').open('a', encoding='utf-8') as stream:
            stream.write('\n[Missing guide](docs/does-not-exist.md)\n')
        with self.assertRaisesRegex(common.ConfigError, 'Broken local link'):
            check.check(root, static=True)

    def test_malformed_version_field_types_fail_cleanly(self):
        for value in [None, [], {'schema': 1, 'plugins': [None]},
                      {'schema': 1, 'plugins': [{'name': []}]}]:
            with self.subTest(value=value), self.assertRaises(common.ConfigError):
                common.validate_versions(value)

    def test_missing_sheet_is_failure(self):
        root = self.clone()
        (root / 'cheatsheets/kdl-syntax-cheatsheet.html').unlink()
        with self.assertRaises(common.ConfigError):
            check.check(root, static=True)

    def test_hash_read_failure_is_not_success(self):
        with mock.patch.object(check, 'sha256', side_effect=OSError('injected I/O failure')), self.assertRaises(OSError):
            check.check(ROOT, static=True)

    def test_license_inventory_is_required(self):
        root = self.clone()
        (root / 'licenses/monocle.txt').unlink()
        with self.assertRaises(FileNotFoundError):
            check.check(root, static=True)


class VersionTests(Workspace):
    def release(self, root, tag='v999'):
        pin = common.load_versions(root)['plugins'][0]
        data = b'\0asm\x01\0\0\0new release bytes'
        digest = hashlib.sha256(data).hexdigest()
        asset = {'name': pin['asset'], 'digest': 'sha256:' + digest,
                 'browser_download_url': 'https://github.com/owner/repo/releases/download/' + tag + '/' + pin['asset']}
        return pin, data, {'tag_name': tag, 'assets': [asset]}

    def test_explicit_update_keeps_manifest_config_bytes_and_docs_together(self):
        root = self.clone()
        pin, data, release = self.release(root)
        notice = (root / 'licenses' / (pin['name'] + '.txt')).read_bytes()
        with mock.patch.object(versions, 'github_release', return_value=release), \
                mock.patch.object(versions, 'fetch_bytes', side_effect=[data, notice]):
            versions.update(root, {pin['name']: 'latest'}, None)
        current = common.load_versions(root)
        self.assertEqual(current['plugins'][0]['tag'], 'v999')
        self.assertIn('/v999/', (root / 'config.kdl').read_text())
        self.assertEqual((root / 'plugins.sha256').read_bytes(), versions.checksums(current))
        self.assertEqual((root / 'VERSIONS.md').read_bytes(), versions.documentation(current))

    def test_bad_download_leaves_pins_and_config_unchanged(self):
        root = self.clone()
        pin, _, release = self.release(root)
        before = (root / 'versions.json').read_bytes(), (root / 'config.kdl').read_bytes()
        with mock.patch.object(versions, 'github_release', return_value=release), \
                mock.patch.object(versions, 'fetch_bytes', return_value=b'corrupt'), self.assertRaises(common.ConfigError):
            versions.update(root, {pin['name']: 'latest'}, None)
        self.assertEqual(before, ((root / 'versions.json').read_bytes(), (root / 'config.kdl').read_bytes()))

    def test_update_write_failure_restores_all_previous_bytes(self):
        root = self.clone()
        pin, data, release = self.release(root)
        paths = ['versions.json', 'config.kdl', 'plugins.sha256', 'VERSIONS.md',
                 'plugins/' + pin['asset'], 'licenses/' + pin['name'] + '.txt']
        before = {path: (root / path).read_bytes() for path in paths}
        replace = versions.atomic_write

        def fail_config(path, *args):
            if path == root / 'config.kdl':
                raise OSError('injected config write failure')
            return replace(path, *args)

        with mock.patch.object(versions, 'github_release', return_value=release), \
                mock.patch.object(versions, 'fetch_bytes', side_effect=[data, before['licenses/' + pin['name'] + '.txt']]), \
                mock.patch.object(versions, 'atomic_write', side_effect=fail_config), self.assertRaises(OSError):
            versions.update(root, {pin['name']: 'latest'}, None)
        self.assertEqual(before, {path: (root / path).read_bytes() for path in paths})

    def test_update_does_not_overwrite_edits_made_during_download(self):
        root = self.clone()
        pin, data, release = self.release(root)
        before = (root / 'versions.json').read_bytes()
        notice = (root / 'licenses' / (pin['name'] + '.txt')).read_bytes()
        config = root / 'config.kdl'
        edited = config.read_bytes() + b'\n// concurrent user edit\n'

        def fetch(url, *args):
            config.write_bytes(edited)
            return notice if 'raw.githubusercontent.com' in url else data

        with mock.patch.object(versions, 'github_release', return_value=release), \
                mock.patch.object(versions, 'fetch_bytes', side_effect=fetch), \
                self.assertRaisesRegex(common.ConfigError, 'changed during the download'):
            versions.update(root, {pin['name']: 'latest'}, None)
        self.assertEqual(config.read_bytes(), edited)
        self.assertEqual((root / 'versions.json').read_bytes(), before)

    def test_missing_published_digest_needs_trusted_override(self):
        with self.assertRaises(common.ConfigError):
            versions.published_digest({'digest': None})
        digest = 'a' * 64
        self.assertEqual(versions.published_digest({'digest': None}, digest), digest)

    def test_changed_license_is_not_automatically_relicensed(self):
        root = self.clone()
        pin, data, release = self.release(root)
        before = (root / 'versions.json').read_bytes()
        original = (root / 'licenses' / (pin['name'] + '.txt')).read_bytes()
        for notice in [b'All rights reserved', original + b'\nCommercial use prohibited.\n']:
            with self.subTest(notice=notice[-40:]), \
                    mock.patch.object(versions, 'github_release', return_value=release), \
                    mock.patch.object(versions, 'fetch_bytes', side_effect=[data, notice]), self.assertRaises(common.ConfigError):
                versions.update(root, {pin['name']: 'latest'}, None)
            self.assertEqual((root / 'versions.json').read_bytes(), before)

    def test_added_license_restriction_requires_review(self):
        notice = (ROOT / 'licenses/monocle.txt').read_bytes()
        renamed = notice.replace(b'2023 Aram Drevekenin', b'2026 Example Contributors')
        self.assertEqual(versions.license_terms(notice), versions.license_terms(renamed))
        self.assertNotEqual(versions.license_terms(notice),
                            versions.license_terms(notice + b'\nCommercial use prohibited.\n'))

    def test_zellij_archive_verified_before_payload_install(self):
        root = self.clone()
        payload = b'#!/bin/sh\necho verified fixture\n'
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w:gz') as tar:
            info = tarfile.TarInfo('zellij')
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
        data = stream.getvalue()
        pins = common.load_versions(root)
        pins['zellij']['assets']['zellij-x86_64-unknown-linux-musl.tar.gz'] = hashlib.sha256(data).hexdigest()
        (root / 'versions.json').write_bytes(common.json_bytes(pins))
        with mock.patch.object(versions.platform, 'system', return_value='Linux'), \
                mock.patch.object(versions.platform, 'machine', return_value='x86_64'), \
                mock.patch.object(versions, 'fetch_bytes', return_value=data):
            path = versions.install_zellij(root, self.bin)
        self.assertEqual(path.read_bytes(), payload)


class NativeBackgroundTests(Workspace):
    def wait_for(self, path):
        deadline = time.monotonic() + 10
        while not path.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(path.exists(), f'Background worker did not create {path.name}')

    def test_native_detached_worker_preserves_arguments_and_does_not_wait(self):
        worker = self.base / 'worker with spaces 雪.py'
        started, release, done = [self.base / name for name in ['started', 'release', 'done']]
        worker.write_text(
            'import json, os, pathlib, sys, time\n'
            'started, release, done = map(pathlib.Path, sys.argv[1:4])\n'
            'started.write_text("ready")\n'
            'deadline = time.monotonic() + 10\n'
            'while not release.exists() and time.monotonic() < deadline: time.sleep(0.01)\n'
            'console = sys.stdout.isatty()\n'
            'if os.name == "nt":\n'
            '    import ctypes, msvcrt\n'
            '    mode = ctypes.c_ulong()\n'
            '    handle = ctypes.c_void_p(msvcrt.get_osfhandle(sys.stdout.fileno()))\n'
            '    console = bool(ctypes.windll.kernel32.GetConsoleMode(handle, ctypes.byref(mode)))\n'
            'result = {"arguments": sys.argv[4:], "stdin": sys.stdin.read(), "stdout_console": console}\n'
            'temporary = done.with_suffix(".tmp")\n'
            'temporary.write_text(json.dumps(result), encoding="utf-8")\n'
            'os.replace(temporary, done)\n', encoding='utf-8')
        arguments = ['', 'quote"', 'back\\slash', 'spaces and 雪', '$semi;tick`']
        common.spawn_detached([sys.executable, str(worker), str(started), str(release), str(done), *arguments])
        # The worker cannot complete until this process releases it. Returning
        # here establishes dispatch didn't wait for the background work.
        self.assertFalse(done.exists())
        self.wait_for(started)
        release.write_text('continue')
        self.wait_for(done)
        result = common.read_json(done)
        self.assertEqual(result['arguments'], arguments)
        self.assertEqual(result['stdin'], '')
        # Windows CRT isatty() is also true for NUL; GetConsoleMode above
        # distinguishes an actual console handle from that redirected device.
        self.assertFalse(result['stdout_console'])

    def test_native_update_worker_persists_results_without_network(self):
        config = self.base / 'config with spaces 雪.kdl'
        config.write_text('plugins {}\n', encoding='utf-8')
        environment = {'XDG_STATE_HOME': str(self.base / 'state'),
                       'LOCALAPPDATA': str(self.base / 'state'),
                       'ZJ_NO_UPDATE_CHECK': '', 'ZJ_OFFLINE': ''}
        with mock.patch.dict(os.environ, environment):
            stamp, lock = launcher.scan_cache(config, [])
            launcher.background_updates(config, [])
            deadline = time.monotonic() + 10
            while 'notice' not in launcher.cache_data(stamp) and time.monotonic() < deadline:
                time.sleep(0.01)
            result = launcher.cache_data(stamp)
            # The atomic result appears just before the worker closes its lock.
            # Wait for that close before Windows removes this temporary tree.
            released = False
            while time.monotonic() < deadline:
                try:
                    with common.FileLock(lock):
                        released = True
                    break
                except OSError:
                    time.sleep(0.01)
        self.assertIn('notice', result)
        self.assertTrue(released)
        self.assertEqual(result['notice']['checked'], 0)
        self.assertFalse(result['complete'])
        self.assertNotIn('worker_until', result)


class RealBinaryTests(Workspace):
    def test_direct_git_clone_and_offline_runtime_without_setup(self):
        binary = shutil.which('zellij')
        if not binary or not shutil.which('git'):
            self.skipTest('Native Git and Zellij required')
        source = self.clone()
        subprocess.run(['git', 'init', '-q', str(source)], check=True, capture_output=True)
        subprocess.run(['git', '-C', str(source), 'add', '.'], check=True, capture_output=True)
        subprocess.run(['git', '-C', str(source), '-c', 'user.name=Test Fixture',
                        '-c', 'user.email=fixture@example.invalid', '-c', 'commit.gpgsign=false',
                        'commit', '-qm', 'direct clone fixture'], check=True, capture_output=True)
        checkout = self.base / ('Zellij/config' if os.name == 'nt' else 'zellij')
        subprocess.run(['git', 'clone', '-q', '--no-local', str(source), str(checkout)],
                       check=True, capture_output=True)
        self.assertTrue((checkout / 'config.kdl').is_file())
        self.assertFalse((checkout / 'config').exists())
        env = dict(os.environ, ZELLIJ_CONFIG_DIR=str(checkout), ZJ_OFFLINE='1',
                   XDG_CACHE_HOME=str(self.base / 'cache'), XDG_DATA_HOME=str(self.base / 'data'),
                   XDG_STATE_HOME=str(self.base / 'state'))
        result = subprocess.run([binary, 'setup', '--check'], env=env, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b'[CONFIG FILE]: Well defined.', result.stdout)
        with mock.patch.object(plugin_files, 'fetch_bytes') as fetch:
            args = runtime.prepare(checkout / 'config.kdl', [], self.base / 'runtime', offline=True)
        fetch.assert_not_called()
        result = subprocess.run([binary, *args, '--layout', 'dev', 'setup', '--check'],
                                env=env, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([sys.executable, str(checkout / 'tools/manage.py'), 'check'],
                                env=env, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        status = subprocess.check_output(['git', '-C', str(checkout), 'status', '--porcelain'])
        self.assertEqual(status, b'')

    def test_actual_config_and_unusual_path_install(self):
        binary = shutil.which('zellij')
        if not binary:
            self.skipTest('Real Zellij is required for integration checks (CI installs it)')
        target = self.base / ('config with spaces' if os.name == 'nt' else 'config "quoted" \\path')
        install.install(ROOT, target=target, offline=True, no_launcher=True)
        install.validate(target, binary)

    @unittest.skipIf(os.name == 'nt', 'Unix shell entry point')
    def test_native_shell_setup_and_installed_launcher(self):
        if not shutil.which('zellij'):
            self.skipTest('Zellij required')
        result = subprocess.run(['sh', str(ROOT / 'setup.sh'), '--offline', '--config-dir', str(self.target),
                                 '--bin-dir', str(self.bin)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run(['sh', str(self.bin / 'zj'), '--version'],
                                env=dict(os.environ, ZJ_NO_UPDATE_CHECK='1'), capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b'zellij', result.stdout)

    @unittest.skipUnless(os.name == 'nt', 'Native Windows PowerShell/cmd entry points')
    def test_native_windows_setup_and_both_wrappers(self):
        if not shutil.which('zellij'):
            self.skipTest('Zellij required')
        result = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                                 '-File', str(ROOT / 'setup.ps1'), '-Offline', '-ConfigDir', str(self.target),
                                 '-BinDir', str(self.bin)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        env = dict(os.environ, ZJ_NO_UPDATE_CHECK='1')
        for args in [[str(self.bin / 'zj.cmd'), '--version'],
                     ['powershell', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                      '-File', str(self.bin / 'zj.ps1'), '--version']]:
            result = subprocess.run(args, env=env, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(b'zellij', result.stdout)

    @unittest.skipUnless(os.name == 'nt', 'Native Windows PowerShell argument transport')
    def test_powershell_literal_arguments_reach_helper(self):
        self.bin.mkdir()
        wrapper = self.bin / 'zj.ps1'
        shutil.copy2(ROOT / 'launcher/zj.ps1', wrapper)
        helper = self.bin / '.zellij-config'
        helper.mkdir()
        (helper / 'manage.py').write_text(
            'import base64, json, sys\n'
            'print(json.dumps(json.loads(base64.b64decode(sys.argv[-1])), ensure_ascii=True))\n', encoding='utf-8')
        expected = ['', 'a"b', 'with spaces', 'back\\slash', '雪', '--config', "dollar$semi;tick`quote'"]

        def quoted(value):
            return "'" + value.replace("'", "''") + "'"

        command = '& ' + quoted(str(wrapper)) + ' ' + ' '.join(map(quoted, expected))
        result = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                                 '-Command', command], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), expected)


class HookTests(Workspace):
    def staged(self):
        if not shutil.which('git') or not shutil.which('sh') or not shutil.which('zellij'):
            self.skipTest('Native git, sh and Zellij required')
        root = self.clone()
        subprocess.run(['git', 'init', '-q', str(root)], check=True, capture_output=True)
        subprocess.run(['git', '-C', str(root), 'add', '.'], check=True, capture_output=True)
        return root

    def hook(self, root):
        return subprocess.run(['sh', 'hooks/pre-commit'], cwd=root, capture_output=True)

    def test_nonexecutable_checker_does_not_skip_broken_staged_input(self):
        root = self.staged()
        with (root / 'config.kdl').open('a') as file:
            file.write('\nbroken {\n')
        subprocess.run(['git', '-C', str(root), 'add', 'config.kdl'], check=True)
        subprocess.run(['git', '-C', str(root), 'update-index', '--chmod=-x', 'check.sh'], check=True)
        result = self.hook(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(b'skipping', result.stderr)

    def test_missing_checker_blocks_commit(self):
        root = self.staged()
        subprocess.run(['git', '-C', str(root), 'rm', '--cached', 'check.sh'], check=True, capture_output=True)
        result = self.hook(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'missing', result.stderr)

    def test_staged_good_with_unstaged_break_passes(self):
        root = self.staged()
        with (root / 'config.kdl').open('a') as file:
            file.write('\nbroken {\n')
        result = self.hook(root)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_staged_break_with_unstaged_repair_fails(self):
        root = self.staged()
        original = (root / 'config.kdl').read_bytes()
        (root / 'config.kdl').write_bytes(original + b'\nbroken {\n')
        subprocess.run(['git', '-C', str(root), 'add', 'config.kdl'], check=True)
        (root / 'config.kdl').write_bytes(original)
        self.assertNotEqual(self.hook(root).returncode, 0)


@unittest.skipIf(os.name == 'nt', 'POSIX signal delivery')
class SignalTests(Workspace):
    def test_real_sigterm_during_dry_run_preserves_files(self):
        self.old()
        (self.target / 'unrelated.part').write_text('keep')
        marker = self.base / 'ready'
        script = '''import sys,time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from zjconfig import install,cli
original=install.quote
def paused(value):
 Path(sys.argv[2]).write_text('ready')
 time.sleep(30)
 return original(value)
install.quote=paused
raise SystemExit(cli.main(['install','--dry-run','--config-dir',sys.argv[3]]))
'''
        process = subprocess.Popen([sys.executable, '-c', script, str(ROOT / 'tools'), str(marker), str(self.target)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 5
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(marker.exists())
            process.send_signal(signal.SIGTERM)
            process.communicate(timeout=5)
            self.assertEqual(process.returncode, 130)
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
        self.assertEqual((self.target / 'unrelated.part').read_text(), 'keep')
        self.assertFalse(list(self.base.glob('config.stage-*')))


if __name__ == '__main__':
    unittest.main()
