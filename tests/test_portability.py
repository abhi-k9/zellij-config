"""Directory precedence, executable overrides and installed-helper boundaries."""
from __future__ import annotations

from contextlib import contextmanager, redirect_stderr
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
from unittest import mock

from test_regressions import ROOT, Workspace
from zjconfig import check, cli, common, install, launcher


class DirectoryTests(Workspace):
    @contextmanager
    def platform(self, name='posix', platform='linux', **environment):
        home = self.base / 'home'
        home.mkdir(exist_ok=True)
        # Replace module references instead of os.name globally: pathlib must
        # continue using paths supported by the actual host running the tests.
        selected = SimpleNamespace(name=name, environ=environment)
        with mock.patch.object(install, 'os', selected), mock.patch.object(launcher, 'os', selected), \
                mock.patch.object(Path, 'home', return_value=home), mock.patch.object(sys, 'platform', platform), \
                mock.patch.dict(os.environ, {'HOME': str(home), 'USERPROFILE': str(home)}):
            yield home

    def test_linux_config_precedence_with_coexisting_roots(self):
        xdg, explicit = self.base / 'xdg', self.base / 'explicit'
        with self.platform(XDG_CONFIG_HOME=str(xdg)) as home:
            self.assertEqual(install.default_directory(), xdg / 'zellij')
            (home / '.config/zellij').mkdir(parents=True)
            self.assertEqual(install.default_directory(), home / '.config/zellij')
        with self.platform(XDG_CONFIG_HOME=str(xdg), ZELLIJ_CONFIG_DIR=str(explicit)):
            self.assertEqual(install.default_directory(), explicit)

    def test_linux_default_and_expanded_explicit_config(self):
        with self.platform() as home:
            self.assertEqual(install.default_directory(), home / '.config/zellij')
            self.assertEqual(install.default_binary_directory(), home / '.local/bin')
        with self.platform(ZELLIJ_CONFIG_DIR='~/custom config') as home:
            self.assertEqual(install.default_directory(), home / 'custom config')

    def test_macos_existing_and_fresh_config_roots(self):
        with self.platform(platform='darwin', XDG_CONFIG_HOME=str(self.base / 'ignored')) as home:
            self.assertEqual(install.default_directory(), home / '.config/zellij')
            native = home / 'Library/Application Support/org.Zellij-Contributors.Zellij'
            native.mkdir(parents=True)
            self.assertEqual(install.default_directory(), native)
            (home / '.config/zellij').mkdir(parents=True)
            self.assertEqual(install.default_directory(), home / '.config/zellij')

    def test_windows_config_and_binary_roots_and_fallbacks(self):
        roaming, local = self.base / 'roaming', self.base / 'local'
        with self.platform(name='nt', platform='win32', APPDATA=str(roaming), LOCALAPPDATA=str(local)):
            self.assertEqual(install.default_directory(), roaming / 'Zellij/config')
            self.assertEqual(install.default_binary_directory(), local / 'Programs/zellij-config/bin')
        with self.platform(name='nt', platform='win32') as home:
            self.assertEqual(install.default_directory(), home / 'AppData/Roaming/Zellij/config')
            self.assertEqual(install.default_binary_directory(), home / 'AppData/Local/Programs/zellij-config/bin')
        with self.platform(name='nt', platform='win32', APPDATA=str(roaming), ZELLIJ_CONFIG_DIR=str(self.target)):
            self.assertEqual(install.default_directory(), self.target)

    def test_state_directory_platform_defaults_and_override(self):
        state, local = self.base / 'xdg state', self.base / 'local'
        with self.platform(XDG_STATE_HOME=str(state)):
            self.assertEqual(launcher.state_directory(), state / 'zellij-config')
        with self.platform() as home:
            self.assertEqual(launcher.state_directory(), home / '.local/state/zellij-config')
        with self.platform(name='nt', platform='win32', LOCALAPPDATA=str(local)):
            self.assertEqual(launcher.state_directory(), local / 'zellij-config')
        with self.platform(name='nt', platform='win32') as home:
            self.assertEqual(launcher.state_directory(), home / 'AppData/Local/zellij-config')
        for name in ['posix', 'nt']:
            with self.platform(name=name, ZJ_STATE_DIR='~/chosen state', XDG_STATE_HOME=str(state), LOCALAPPDATA=str(local)) as home:
                self.assertEqual(launcher.state_directory(), home / 'chosen state')

    def test_state_override_retains_symlink_rejection(self):
        destination = self.base / 'other state'
        destination.mkdir()
        selected = self.base / 'state link'
        self.link(selected, destination, directory=True)
        with mock.patch.dict(os.environ, {'ZJ_STATE_DIR': str(selected)}), \
                self.assertRaisesRegex(common.ConfigError, 'symlink'):
            launcher.scan_cache(self.target / 'config.kdl', [])
        self.assertEqual(list(destination.iterdir()), [])


class ExecutableTests(Workspace):
    def test_explicit_executable_with_spaces_and_unicode(self):
        binary = self.base / ('zellij custom 雪.exe' if os.name == 'nt' else 'zellij custom 雪')
        shutil.copy2(sys.executable, binary)
        with mock.patch.dict(os.environ, {'ZJ_ZELLIJ_BIN': str(binary)}):
            self.assertEqual(Path(common.zellij_executable()).resolve(), binary.resolve())

    def test_override_is_one_literal_value_and_never_falls_back(self):
        requested = str(self.base / 'missing executable --flag')
        with mock.patch.dict(os.environ, {'ZJ_ZELLIJ_BIN': requested}), \
                mock.patch.object(common.shutil, 'which', return_value=None) as which, \
                self.assertRaisesRegex(common.ConfigError, 'ZJ_ZELLIJ_BIN'):
            common.zellij_executable()
        which.assert_called_once_with(requested)

    def test_relative_executable_selector_retains_current_directory(self):
        with mock.patch.dict(os.environ, {'ZJ_ZELLIJ_BIN': './chosen'}), \
                mock.patch.object(common.shutil, 'which', return_value='./chosen') as which:
            self.assertEqual(common.zellij_executable(), './chosen')
        which.assert_called_once_with('./chosen')

    def test_nonexecutable_override_is_rejected(self):
        if os.name == 'nt':
            self.skipTest('POSIX executable mode bits')
        binary = self.base / 'not executable'
        binary.write_text('plain data\n', encoding='utf-8')
        binary.chmod(0o600)
        with mock.patch.dict(os.environ, {'ZJ_ZELLIJ_BIN': str(binary)}), \
                self.assertRaisesRegex(common.ConfigError, 'ZJ_ZELLIJ_BIN'):
            common.zellij_executable()

    def test_override_expands_home_and_default_uses_path(self):
        with mock.patch.dict(os.environ, {'ZJ_ZELLIJ_BIN': '~/bin/custom', 'HOME': str(self.base), 'USERPROFILE': str(self.base)}), \
                mock.patch.object(common.shutil, 'which', return_value=sys.executable) as which:
            self.assertEqual(common.zellij_executable(), sys.executable)
            which.assert_called_once_with(str(self.base / 'bin/custom'))
        with mock.patch.dict(os.environ, {'ZJ_ZELLIJ_BIN': ''}), \
                mock.patch.object(common.shutil, 'which', return_value=None) as which, \
                self.assertRaisesRegex(common.ConfigError, 'not on PATH'):
            common.zellij_executable()
        which.assert_called_once_with('zellij')

    def test_launcher_uses_override_without_argument_reparsing(self):
        requested = str(self.base / 'chosen binary')
        with mock.patch.dict(os.environ, {'ZJ_ZELLIJ_BIN': requested}), \
                mock.patch.object(launcher.shutil, 'which', return_value=sys.executable) as which, \
                mock.patch.object(launcher.os, 'execv') as execute, \
                mock.patch.object(launcher.subprocess, 'call', return_value=0) as call:
            launcher.launch(['--version'])
        which.assert_called_once_with(requested)
        if os.name == 'nt':
            call.assert_called_once_with([sys.executable, '--version'])
        else:
            execute.assert_called_once_with(sys.executable, [sys.executable, '--version'])

    def test_full_check_uses_selected_executable(self):
        requested = str(self.base / 'chosen binary')
        with mock.patch.dict(os.environ, {'ZJ_ZELLIJ_BIN': requested}), \
                mock.patch.object(check.shutil, 'which', return_value=sys.executable) as which, \
                mock.patch.object(check, 'validate') as validate, \
                mock.patch.object(check.subprocess, 'run', return_value=SimpleNamespace(returncode=0)):
            check.check(ROOT)
        which.assert_called_once_with(requested)
        validate.assert_any_call(ROOT, sys.executable)
        self.assertTrue(all(call.args[1] == sys.executable for call in validate.call_args_list))


class HelperCapabilityTests(Workspace):
    def test_copied_helper_rejects_repository_commands_before_mutation(self):
        helper = self.base / 'installed helper'
        helper.mkdir()
        shutil.copy2(ROOT / 'versions.json', helper / 'versions.json')
        for arguments in [['install', '--dry-run'], ['install', '--launcher-only'], ['check', '--static'],
                          ['versions', 'check'], ['versions', 'update', '--all'],
                          ['install-zellij', '--bin-dir', str(self.bin)]]:
            error = io.StringIO()
            with self.subTest(arguments=arguments), mock.patch.object(cli, 'root_directory', return_value=helper), redirect_stderr(error):
                self.assertEqual(cli.main(arguments), 1)
                self.assertIn('requires the full zellij-config source checkout', error.getvalue())
        self.assertEqual(sorted(path.name for path in helper.iterdir()), ['versions.json'])
        self.assertFalse(self.bin.exists())

    def test_copied_helper_still_allows_launch(self):
        helper = self.base / 'installed helper'
        with mock.patch.object(cli, 'root_directory', return_value=helper), \
                mock.patch.object(launcher, 'launch', return_value=0) as launch:
            self.assertEqual(cli.main(['launch', '--', '--version']), 0)
        launch.assert_called_once_with(['--', '--version'])

    def test_real_copied_helper_repository_diagnostic(self):
        install.install_launcher(ROOT, self.bin)
        result = subprocess.run([sys.executable, str(self.bin / '.zellij-config/manage.py'), 'check', '--static'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('requires the full zellij-config source checkout', result.stderr)


class LayoutInventoryTests(Workspace):
    def test_additional_layout_requires_matching_swap(self):
        root = self.clone()
        (root / 'layouts/custom.kdl').write_text('layout { pane }\n', encoding='utf-8')
        with self.assertRaisesRegex(common.ConfigError, 'custom.kdl needs custom.swap.kdl'):
            check.check(root, static=True)

    def test_orphan_swap_requires_matching_layout(self):
        root = self.clone()
        (root / 'layouts/custom.swap.kdl').write_text('// orphan\n', encoding='utf-8')
        with self.assertRaisesRegex(common.ConfigError, 'custom.swap.kdl needs custom.kdl'):
            check.check(root, static=True)
