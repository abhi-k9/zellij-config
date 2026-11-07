"""Protect native argv and user data at helper transaction boundaries."""
from __future__ import annotations

from contextlib import redirect_stdout
import io
import os
import subprocess
import sys
from unittest import mock

from test_regressions import ROOT, Workspace
from zjconfig import cli, common, install, launcher, preferences, runtime


class TransactionTests(Workspace):
    def test_setup_cannot_replace_a_config_while_preferences_are_being_saved(self):
        self.old()
        write = cli.atomic_write

        def during_save(*args):
            result = subprocess.run(
                [sys.executable, str(ROOT / 'tools/manage.py'), 'install', '--offline',
                 '--no-launcher', '--config-dir', str(self.target)],
                capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn('in use', result.stderr)
            write(*args)

        with mock.patch.object(cli, 'atomic_write', side_effect=during_save), redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(['configure', '--config-dir', str(self.target), '--theme', 'catppuccin-latte']), 0)
        self.assertEqual(preferences.read_settings(self.target)['theme'], 'catppuccin-latte')
        self.assertEqual((self.target / 'config.kdl').read_text(), '// ORIGINAL CONFIG\n')

    def test_configure_during_setup_cannot_silently_lose_a_saved_change(self):
        self.old()
        preference_file = self.target / preferences.LOCAL_FILE
        original = common.json_bytes({'schema': 1, 'theme': 'catppuccin-mocha'})
        for changes in [['--theme', 'catppuccin-latte'], ['--reset']]:
            with self.subTest(changes=changes):
                preference_file.write_bytes(original)
                results = []
                acquire = install.acquire

                def during_staging(*args, **kwargs):
                    if not results:
                        results.append(subprocess.run(
                            [sys.executable, str(ROOT / 'tools/manage.py'), 'configure',
                             '--config-dir', str(self.target), *changes],
                            capture_output=True, text=True, timeout=20))
                    return acquire(*args, **kwargs)

                with mock.patch.object(install, 'acquire', side_effect=during_staging), redirect_stdout(io.StringIO()):
                    self.setup_config()
                self.assertEqual(results[0].returncode, 1, results[0].stdout)
                self.assertIn('in use', results[0].stderr)
                self.assertEqual(preference_file.read_bytes(), original)
                # After the transaction completes, retrying the same command works.
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(cli.main(['configure', '--config-dir', str(self.target), *changes]), 0)
                if changes == ['--reset']:
                    self.assertFalse(preference_file.exists())
                else:
                    self.assertEqual(preferences.read_settings(self.target)['theme'], 'catppuccin-latte')

    def test_malformed_recovery_metadata_leaves_every_path_untouched(self):
        self.old()
        stage = self.base / 'config.stage-fixture'
        stage.mkdir()
        (stage / 'keep').write_bytes(b'keep')
        backup = self.base / 'config.backup-fixture'
        (backup / 'tree').mkdir(parents=True)
        journal = self.base / '.config.zj-journal.json'
        valid = {'target': str(self.target), 'stage': str(stage), 'backup': str(backup), 'fresh': False}
        for metadata in [[], None, {}, {**valid, 'stage': 7}, {**valid, 'fresh': 'false'}]:
            journal.write_bytes(common.json_bytes(metadata))
            with self.subTest(metadata=metadata), self.assertRaisesRegex(common.ConfigError, 'journal'):
                install.recover(self.target)
            self.assertEqual((stage / 'keep').read_bytes(), b'keep')
            self.assertTrue((backup / 'tree').is_dir())
            self.assertTrue(journal.is_file())
            self.assertEqual((self.target / 'config.kdl').read_text(), '// ORIGINAL CONFIG\n')

    def test_malformed_snapshot_metadata_is_an_actionable_error(self):
        backup = self.base / 'config.backup-fixture'
        (backup / 'tree').mkdir(parents=True)
        valid = {'format': 'zjconfig-backup-v1', 'created_ns': 1, 'has_tree': True}
        for metadata in [[], None, {**valid, 'created_ns': True}, {**valid, 'has_tree': 'false'}]:
            (backup / 'snapshot.json').write_bytes(common.json_bytes(metadata))
            with self.subTest(metadata=metadata), self.assertRaisesRegex(common.ConfigError, 'snapshot metadata'):
                install.snapshots(self.target)

    def test_recovery_refuses_a_link_instead_of_the_saved_tree(self):
        external = self.base / 'external'
        external.mkdir()
        (external / 'keep').write_bytes(b'keep')
        stage = self.base / 'config.stage-fixture'
        stage.mkdir()
        backup = self.base / 'config.backup-fixture'
        backup.mkdir()
        self.link(backup / 'tree', external, directory=True)
        journal = self.base / '.config.zj-journal.json'
        journal.write_bytes(common.json_bytes(
            {'target': str(self.target), 'stage': str(stage), 'backup': str(backup), 'fresh': False}))
        with self.assertRaisesRegex(common.ConfigError, 'journal'):
            install.recover(self.target)
        self.assertFalse(self.target.exists())
        self.assertTrue((backup / 'tree').is_symlink())
        self.assertTrue(journal.is_file())
        self.assertTrue(stage.is_dir())
        self.assertEqual((external / 'keep').read_bytes(), b'keep')


class NativeArgumentTests(Workspace):
    def test_short_option_clusters_preserve_debug_and_attached_config_values(self):
        config = self.base / 'chosen config.kdl'
        generated = self.base / 'runtime.kdl'
        for selector in [['-dc' + str(config)], ['-dc', str(config)], ['-dc=' + str(config)]]:
            args = [*selector, 'attach', '-c', 'project']
            with self.subTest(selector=selector), mock.patch.dict(os.environ, {}, clear=True):
                self.assertEqual(launcher.config_file(args), config)
                self.assertEqual(runtime.arguments_for_config(args, config, generated),
                                 ['--config', str(generated), '--config-dir', str(self.base),
                                  '-d', 'attach', '-c', 'project'])
                self.assertTrue(runtime.needs_plugins(args))
                self.assertFalse(runtime.needs_plugins([*selector, 'setup', '--check']))
        self.assertFalse(runtime.needs_plugins(['-dV']))
        self.assertFalse(runtime.needs_plugins(['-dh']))

    def test_attach_create_is_never_treated_as_a_config_selector(self):
        config = self.base / 'chosen config.kdl'
        generated = self.base / 'runtime.kdl'
        for suffix in [['attach', '-c', 'project'], ['a', '-c'],
                       ['attach', '-cb', 'project'],
                       ['attach', '-c', 'project', '--', '--config', 'literal value']]:
            arguments = ['--config-dir', str(self.base), '-c', str(config), *suffix]
            with self.subTest(suffix=suffix), mock.patch.dict(os.environ, {}, clear=True):
                self.assertEqual(launcher.config_file(arguments), config)
                self.assertEqual(runtime.arguments_for_config(arguments, config, generated),
                                 ['--config', str(generated), '--config-dir', str(self.base), *suffix])
                self.assertTrue(runtime.needs_plugins(arguments))

    def test_option_values_are_not_reinterpreted_as_selectors(self):
        config = self.base / 'config.kdl'
        generated = self.base / 'runtime.kdl'
        for argument in ['--config=literal', '--config-dir=literal']:
            args = ['--config-dir', str(self.base), '--layout', argument, 'attach', '-c', 'project']
            with self.subTest(argument=argument), mock.patch.dict(os.environ, {}, clear=True):
                self.assertEqual(launcher.config_file(args), config)
                self.assertEqual(runtime.resource_directory(args, config), self.base)
                self.assertEqual(runtime.arguments_for_config(args, config, generated),
                                 ['--config', str(generated), *args])
