"""Preference ownership, real-parser integration and captured startup arguments.

The native startup fixture captures argv instead of opening an interactive TUI;
terminal key handling, rendering and application recovery need on-machine tests.
"""
from __future__ import annotations

import json
from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
from unittest import mock

from test_regressions import ROOT, Workspace
from zjconfig import cli, common, install, kdl, plugin_files, preferences, runtime


class ConfigurationTests(Workspace):
    def source(self):
        directory = self.base / 'source with spaces 雪'
        directory.mkdir()
        shutil.copy2(ROOT / 'config.kdl', directory / 'config.kdl')
        shutil.copy2(ROOT / 'versions.json', directory / 'versions.json')
        shutil.copytree(ROOT / 'layouts', directory / 'layouts')
        shutil.copytree(ROOT / 'plugins', directory / 'plugins')
        return directory

    def configure(self, directory, *arguments):
        return cli.main(['configure', '--config-dir', str(directory), *arguments])

    def test_configure_dry_run_merge_and_reset_leave_source_kdl_untouched(self):
        source = self.source()
        before = {p: p.read_bytes() for p in source.rglob('*.kdl')}
        self.assertEqual(self.configure(source, '--profile', 'classic', '--dry-run'), 0)
        self.assertFalse((source / preferences.LOCAL_FILE).exists())
        self.assertFalse((source / '.zj-preferences.lock').exists())
        self.assertEqual(self.configure(source, '--profile', 'classic'), 0)
        self.assertEqual(self.configure(source, '--timezone', 'UTC', '--git-status', 'off'), 0)
        raw = common.read_json(source / preferences.LOCAL_FILE)
        self.assertEqual(raw['profile'], 'classic')
        self.assertEqual(raw['timezone'], 'UTC')
        self.assertFalse(raw['git_status'])
        self.assertEqual(self.configure(source, '--reset', '--dry-run'), 0)
        self.assertTrue((source / preferences.LOCAL_FILE).is_file())
        self.assertEqual(self.configure(source, '--reset'), 0)
        self.assertFalse((source / preferences.LOCAL_FILE).exists())
        self.assertEqual(before, {p: p.read_bytes() for p in source.rglob('*.kdl')})

    def test_invalid_changes_do_not_replace_existing_preferences(self):
        source = self.source()
        self.assertEqual(self.configure(source, '--profile', 'classic'), 0)
        file = source / preferences.LOCAL_FILE
        previous = file.read_bytes()
        self.assertEqual(self.configure(source, '--timezone', 'Not/ARealTimezone'), 1)
        self.assertEqual(self.configure(source, '--reset', '--profile', 'portable'), 1)
        self.assertEqual(self.configure(source, '--project-sessions', '--session-name', 'conflict'), 1)
        self.assertEqual(file.read_bytes(), previous)
        self.assertEqual(self.configure(source, '--project-sessions'), 0)
        self.assertIsNone(preferences.read_settings(source)['session_name'])
        self.assertFalse(preferences.read_settings(source)['attach_to_session'])

    def test_runtime_profiles_keep_config_directory_and_immutable_layout_pairs(self):
        source = self.source()
        config = source / 'config.kdl'
        before = config.read_bytes()
        resources = self.base / 'separate resources'
        shutil.copytree(source / 'layouts', resources / 'layouts')
        (resources / 'layouts/custom.kdl').write_text('layout { pane; }\n', encoding='utf-8')
        arguments = ['--config-dir', str(resources), '--session', 'project', '--layout', 'zjstatus']
        self.assertEqual(self.configure(source, '--profile', 'classic', '--layout', 'zjstatus'), 0)
        with mock.patch.object(plugin_files, 'fetch_bytes') as fetch:
            prepared = runtime.prepare(config, arguments, self.base / 'state', offline=True)
        fetch.assert_not_called()
        self.assertIn(str(resources), prepared)
        first = Path(prepared[prepared.index('--config') + 1])
        text = first.read_text(encoding='utf-8')
        self.assertIn('session_name "main"', text)
        self.assertIn('RUST_BACKTRACE "1"', text)
        layouts = Path(next(n.arguments[0] for n in kdl.parse(text) if n.name == 'layout_dir'))
        old_layout = (layouts / 'zjstatus.kdl').read_bytes()
        self.assertIn(b'America/Denver', old_layout)
        self.assertIn(b'command_git_branch_command', old_layout)
        self.assertTrue((layouts / 'zjstatus.swap.kdl').is_file())
        self.assertTrue((layouts / 'custom.kdl').is_file())
        self.assertEqual(self.configure(source, '--timezone', 'UTC', '--git-status', 'off'), 0)
        updated = runtime.prepare(config, arguments, self.base / 'state', offline=True)
        second = Path(updated[updated.index('--config') + 1])
        self.assertNotEqual(first, second)
        newer = Path(next(n.arguments[0] for n in kdl.parse(second.read_text()) if n.name == 'layout_dir'))
        self.assertNotIn('command_git_branch_command', (newer / 'zjstatus.kdl').read_text())
        self.assertEqual((layouts / 'zjstatus.kdl').read_bytes(), old_layout)
        self.assertEqual(config.read_bytes(), before)

    def test_preferences_apply_without_managed_plugins(self):
        source = self.source()
        (source / 'versions.json').unlink()
        (source / 'config.kdl').write_text('plugins {}\n', encoding='utf-8')
        self.assertEqual(self.configure(source, '--profile', 'classic'), 0)
        with mock.patch.object(plugin_files, 'fetch_bytes') as fetch:
            prepared = runtime.prepare(source / 'config.kdl', [], self.base / 'state', offline=True)
        fetch.assert_not_called()
        self.assertIn('session_name "main"', Path(prepared[1]).read_text())

    def test_explicit_layout_files_keep_their_own_contents(self):
        source = self.source()
        self.configure(source, '--profile', 'classic', '--layout', 'zjstatus')
        selected = source / 'layouts/zjstatus.kdl'
        before = selected.read_bytes()
        arguments = ['--layout', str(selected)]
        prepared = runtime.prepare(source / 'config.kdl', arguments, self.base / 'state', offline=True)
        self.assertEqual(prepared[prepared.index('--layout') + 1], str(selected))
        self.assertEqual(selected.read_bytes(), before)
        self.assertNotIn('command_git_branch_command', selected.read_text())

    def test_missing_optional_git_disables_widget_with_a_diagnostic(self):
        source = self.source()
        self.configure(source, '--profile', 'classic', '--layout', 'zjstatus')
        output = io.StringIO()
        with mock.patch.object(runtime.shutil, 'which', return_value=None), redirect_stdout(output):
            prepared = runtime.prepare(source / 'config.kdl', [], self.base / 'state', offline=True)
        self.assertIn('Git status disabled', output.getvalue())
        text = Path(prepared[1]).read_text()
        directory = Path(next(n.arguments[0] for n in kdl.parse(text) if n.name == 'layout_dir'))
        self.assertNotIn('command_git_branch_command', (directory / 'zjstatus.kdl').read_text())
        self.assertTrue(preferences.read_settings(source)['git_status'])

    def test_malformed_preferences_fail_before_runtime_network_or_state(self):
        source = self.source()
        (source / preferences.LOCAL_FILE).write_text('{"schema": 1, "unknown": true}', encoding='utf-8')
        with mock.patch.object(plugin_files, 'fetch_bytes') as fetch, self.assertRaises(common.ConfigError):
            runtime.prepare(source / 'config.kdl', [], self.base / 'state')
        fetch.assert_not_called()
        self.assertFalse((self.base / 'state').exists())

    def test_preferences_edit_during_plugin_acquisition_requires_retry(self):
        source = self.source()
        self.configure(source, '--profile', 'classic')
        original = plugin_files.acquire

        def changed(pin, bundled, **kwargs):
            (source / preferences.LOCAL_FILE).write_text('{"schema": 1, "profile": "portable"}', encoding='utf-8')
            return original(pin, bundled, **kwargs)

        with mock.patch.object(runtime, 'acquire', side_effect=changed), self.assertRaisesRegex(common.ConfigError, 'changed'):
            runtime.prepare(source / 'config.kdl', [], self.base / 'state', offline=True)

    def test_deployment_preserves_and_reapplies_target_preferences(self):
        self.setup_config()
        self.configure(self.target, '--profile', 'classic', '--layout', 'zjstatus')
        raw = (self.target / preferences.LOCAL_FILE).read_bytes()
        self.setup_config()
        self.assertEqual((self.target / preferences.LOCAL_FILE).read_bytes(), raw)
        prepared = runtime.prepare(self.target / 'config.kdl', [], self.base / 'state', offline=True)
        text = Path(prepared[1]).read_text()
        self.assertIn('session_name "main"', text)
        layout_directory = Path(next(n.arguments[0] for n in kdl.parse(text) if n.name == 'layout_dir'))
        layout = (layout_directory / 'zjstatus.kdl').read_text()
        self.assertIn('command_git_branch_command', layout)
        self.assertIn('America/Denver', layout)
        # Reset must work immediately after redeployment, without another setup.
        self.configure(self.target, '--reset')
        prepared = runtime.prepare(self.target / 'config.kdl', [], self.base / 'state', offline=True)
        active = kdl.parse(Path(prepared[1]).read_text())
        self.assertNotIn('session_name', [node.name for node in active])

    def test_invalid_target_preferences_prevent_download_and_publication(self):
        self.setup_config()
        before = (self.target / 'config.kdl').read_bytes()
        (self.target / preferences.LOCAL_FILE).write_text('{"schema": 99}', encoding='utf-8')
        with mock.patch.object(install.shutil, 'which', return_value=sys.executable), \
                mock.patch.object(install, 'acquire') as acquire, self.assertRaises(common.ConfigError):
            install.install(ROOT, target=self.target, no_launcher=True)
        acquire.assert_not_called()
        self.assertEqual((self.target / 'config.kdl').read_bytes(), before)

    def test_installed_helper_can_configure_the_selected_directory(self):
        source = self.source()
        install.install_launcher(ROOT, self.bin)
        result = subprocess.run([sys.executable, str(self.bin / '.zellij-config/manage.py'),
                                 'configure', '--config-dir', str(source), '--profile', 'classic'],
                                capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(preferences.read_settings(source)['profile'], 'classic')

    def test_source_preferences_are_not_imported_into_a_deployment(self):
        source = self.source()
        # A minimal full source fixture needs notices for normal installation.
        shutil.copytree(ROOT / 'licenses', source / 'licenses')
        shutil.copytree(ROOT / 'themes', source / 'themes')
        self.configure(source, '--profile', 'classic')
        self.setup_config(source)
        self.assertFalse((self.target / preferences.LOCAL_FILE).exists())
        self.assertNotIn('session_name', [node.name for node in kdl.parse((self.target / 'config.kdl').read_text())])

    def test_real_zellij_accepts_each_profile_and_its_runtime_layouts(self):
        binary = shutil.which('zellij')
        if not binary:
            self.skipTest('Zellij required for real preference validation')
        source = self.source()
        for profile in ['portable', 'classic']:
            self.configure(source, '--profile', profile, '--layout', 'zjstatus')
            prepared = runtime.prepare(source / 'config.kdl', [], self.base / 'state', offline=True)
            for layout in ['default', 'dev', 'zjstatus', 'minimal']:
                result = subprocess.run([binary, *prepared, '--layout', layout, 'setup', '--check'],
                                        capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_native_normal_start_uses_selected_binary_and_rendered_resources(self):
        if os.name == 'nt':
            self.skipTest('POSIX executable fixture; Windows wrapper transport has separate tests')
        source = self.source()
        self.configure(source, '--profile', 'classic', '--layout', 'zjstatus')
        binary = self.base / 'zellij with spaces 雪'
        binary.write_text('#!' + sys.executable + '\nimport json, sys\nprint(json.dumps(sys.argv[1:]))\n', encoding='utf-8')
        binary.chmod(0o700)
        environment = dict(os.environ, ZJ_PYTHON=sys.executable, ZJ_ZELLIJ_BIN=str(binary),
                           ZJ_STATE_DIR=str(self.base / 'state'), ZJ_OFFLINE='1')
        result = subprocess.run(['sh', str(ROOT / 'launcher/zj'), '--config-dir', str(source),
                                 '--session', 'project 雪', '--layout', 'zjstatus'],
                                env=environment, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        arguments = json.loads(result.stdout.splitlines()[-1])
        text = Path(arguments[arguments.index('--config') + 1]).read_text()
        self.assertIn('session_name "main"', text)
        self.assertIn(str(source), arguments)
        self.assertIn('project 雪', arguments)
        self.assertIn('layout_dir', text)
