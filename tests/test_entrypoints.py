"""Native entry-point discovery and argument forwarding without real installs."""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class EntrypointTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='zj-entrypoints-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / 'checkout with spaces 雪'
        self.root.mkdir()
        (self.root / 'launcher').mkdir()
        (self.root / 'tools').mkdir()
        for name in ['setup.sh', 'setup.ps1', 'check.sh', 'launcher/zj', 'launcher/zj.cmd', 'launcher/zj.ps1']:
            shutil.copy2(ROOT / name, self.root / name)
        self.helper = self.root / 'tools/manage.py'
        self.helper.write_text(
            'import json, os, sys\n'
            'print(json.dumps(sys.argv[1:], ensure_ascii=True))\n'
            'raise SystemExit(int(os.environ.get("ZJ_TEST_EXIT", "0")))\n', encoding='utf-8')
        self.environment = dict(os.environ, ZJ_PYTHON=sys.executable, PYTHONDONTWRITEBYTECODE='1')

    def run_entry(self, command, **kwargs):
        return subprocess.run(command, env=kwargs.pop('env', self.environment), capture_output=True,
                              text=True, encoding='utf-8', errors='replace', **kwargs)

    def arguments(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    @unittest.skipIf(os.name == 'nt', 'Unix shell entry points')
    def test_shell_override_preserves_arguments_and_exit_status(self):
        executable = self.root / 'selected python 雪'
        executable.symlink_to(sys.executable)
        self.environment['ZJ_PYTHON'] = str(executable)
        received = ['', 'with spaces', 'quote"value', 'back\\slash', '雪', '$semi;tick`', '--config', 'literal']
        for name, prefix in [('launcher/zj', ['launch', '--']), ('setup.sh', ['install']), ('check.sh', ['check'])]:
            with self.subTest(entry=name):
                command = ['sh', str(self.root / name), *received]
                self.assertEqual(self.arguments(self.run_entry(command)), [*prefix, *received])
                failed = self.run_entry(command, env=dict(self.environment, ZJ_TEST_EXIT='37'))
                self.assertEqual(failed.returncode, 37, failed.stderr)

    @unittest.skipIf(os.name == 'nt', 'Unix shell entry points')
    def test_shell_default_discovery_remains_available(self):
        environment = dict(self.environment, ZJ_PYTHON='')
        for name, prefix in [('launcher/zj', ['launch', '--']), ('setup.sh', ['install']), ('check.sh', ['check'])]:
            result = self.run_entry(['sh', str(self.root / name), '--help'], env=environment)
            self.assertEqual(self.arguments(result), [*prefix, '--help'])

    @unittest.skipIf(os.name == 'nt', 'Unix shell entry points')
    def test_shell_override_is_one_executable_not_a_command_string(self):
        for name in ['launcher/zj', 'setup.sh', 'check.sh']:
            for invalid in [str(self.root / 'missing python'), sys.executable + ' -u']:
                with self.subTest(entry=name, selector=invalid):
                    result = self.run_entry(['sh', str(self.root / name)],
                                            env=dict(self.environment, ZJ_PYTHON=invalid))
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('ZJ_PYTHON executable is unavailable', result.stderr)
                    self.assertEqual(result.stdout, '')

    @unittest.skipIf(os.name == 'nt', 'Unix shell entry points')
    def test_missing_helpers_have_actionable_diagnostics(self):
        self.helper.unlink()
        for name in ['launcher/zj', 'setup.sh', 'check.sh']:
            with self.subTest(entry=name):
                result = self.run_entry(['sh', str(self.root / name)])
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('helper is missing', result.stderr)

    @unittest.skipIf(os.name == 'nt', 'Unix check wrapper')
    def test_check_updates_selects_optional_file_and_rejects_extra_arguments(self):
        check = ['sh', str(self.root / 'check.sh'), '--updates']
        self.assertEqual(self.arguments(self.run_entry(check)),
                         ['launch', '--', '--check-updates', str(self.root / 'config.kdl')])
        selected = str(self.root / 'other config 雪.kdl')
        self.assertEqual(self.arguments(self.run_entry([*check, selected])),
                         ['launch', '--', '--check-updates', selected])
        result = self.run_entry([*check, selected, 'unexpected'])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Usage: check.sh --updates [CONFIG_FILE]', result.stderr)
        self.assertEqual(result.stdout, '')

    @unittest.skipIf(os.name == 'nt', 'Unix Fish invocation')
    def test_fish_can_invoke_launcher_and_setup(self):
        fish = shutil.which('fish')
        if not fish:
            self.skipTest('Fish is not installed')
        for name, prefix in [('launcher/zj', ['launch', '--']), ('setup.sh', ['install'])]:
            result = self.run_entry([fish, '-c', '$argv[1] $argv[2..-1]', str(self.root / name), '--dry-run'])
            self.assertEqual(self.arguments(result), [*prefix, '--dry-run'])

    @unittest.skipUnless(os.name == 'nt', 'Native Windows entry points')
    def test_windows_override_preserves_arguments_and_exit_status(self):
        powershell = ['powershell', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File']
        arguments = ['with spaces', 'back\\slash', '雪', '--config', 'literal']
        command = [str(self.root / 'launcher/zj.cmd'), *arguments]
        self.assertEqual(self.arguments(self.run_entry(command)), ['launch', '--', *arguments])
        result = self.run_entry(command, env=dict(self.environment, ZJ_TEST_EXIT='37'))
        self.assertEqual(result.returncode, 37, result.stderr)
        command = [*powershell, str(self.root / 'launcher/zj.ps1'), *arguments]
        # Empty strings and quotes are exercised with a literal PowerShell call
        # below, preserving the values before native -File argument conversion.
        forwarded = self.arguments(self.run_entry(command))
        self.assertEqual(forwarded[:2], ['launch', '--argv64'])
        self.assertEqual(json.loads(base64.b64decode(forwarded[2])), arguments)
        result = self.run_entry(command, env=dict(self.environment, ZJ_TEST_EXIT='37'))
        self.assertEqual(result.returncode, 37, result.stderr)
        selected = str(self.root / 'different config 雪')
        result = self.run_entry([*powershell, str(self.root / 'setup.ps1'), '-LauncherOnly', '-DryRun', '-BinDir', selected])
        self.assertEqual(self.arguments(result), ['install', '--dry-run', '--launcher-only', '--bin-dir', selected])

    @unittest.skipUnless(os.name == 'nt', 'Native Windows delayed expansion')
    def test_cmd_inherited_delayed_expansion_preserves_helper_and_interpreter_paths(self):
        root = self.root.with_name('checkout!bang with spaces 雪')
        self.root.rename(root)
        interpreter = root / 'python!selected!.cmd'
        interpreter.write_bytes(
            b'@echo off\r\nsetlocal DisableDelayedExpansion\r\n'
            b'"%ZJ_TEST_REAL_PYTHON%" %*\r\nexit /b %errorlevel%\r\n')
        environment = dict(self.environment, ZJ_PYTHON=str(interpreter), ZJ_TEST_REAL_PYTHON=sys.executable)
        # The relative entry-point name keeps the parent shell from expanding
        # the path before the wrapper can disable its inherited /v:on setting.
        result = self.run_entry(['cmd', '/d', '/v:on', '/c', 'zj.cmd', 'literal'],
                                cwd=root / 'launcher', env=environment)
        self.assertEqual(self.arguments(result), ['launch', '--', 'literal'])

    @unittest.skipUnless(os.name == 'nt', 'Native Windows literal executable paths')
    def test_powershell_interpreter_path_with_brackets_is_literal(self):
        interpreter = self.root / 'python[chosen].cmd'
        interpreter.write_bytes(
            b'@echo off\r\nsetlocal DisableDelayedExpansion\r\n'
            b'"%ZJ_TEST_REAL_PYTHON%" %*\r\nexit /b %errorlevel%\r\n')
        environment = dict(self.environment, ZJ_PYTHON=str(interpreter), ZJ_TEST_REAL_PYTHON=sys.executable)
        command = ['powershell', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File']
        result = self.run_entry([*command, str(self.root / 'launcher/zj.ps1'), '--version'], env=environment)
        forwarded = self.arguments(result)
        self.assertEqual(forwarded[:2], ['launch', '--argv64'])
        self.assertEqual(json.loads(base64.b64decode(forwarded[2])), ['--version'])
        result = self.run_entry([*command, str(self.root / 'setup.ps1'), '-LauncherOnly'], env=environment)
        self.assertEqual(self.arguments(result), ['install', '--launcher-only'])

    @unittest.skipUnless(os.name == 'nt', 'Native Windows PowerShell argument transport')
    def test_powershell_override_preserves_literal_quotes_empty_and_unicode(self):
        expected = ['', 'a"b', 'with spaces', 'back\\slash', '雪', '--config', "dollar$semi;tick`quote'"]

        def quoted(value):
            return "'" + value.replace("'", "''") + "'"

        command = '& ' + quoted(str(self.root / 'launcher/zj.ps1')) + ' ' + ' '.join(map(quoted, expected))
        result = self.run_entry(['powershell', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                                 '-Command', command])
        forwarded = self.arguments(result)
        self.assertEqual(forwarded[:2], ['launch', '--argv64'])
        self.assertEqual(json.loads(base64.b64decode(forwarded[2])), expected)

    @unittest.skipUnless(os.name == 'nt', 'Native Windows entry points')
    def test_windows_missing_override_and_helper_fail_clearly(self):
        powershell = ['powershell', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File']
        entries = [[str(self.root / 'launcher/zj.cmd')],
                   [*powershell, str(self.root / 'launcher/zj.ps1')],
                   [*powershell, str(self.root / 'setup.ps1')]]
        for entry in entries:
            result = self.run_entry(entry, env=dict(self.environment, ZJ_PYTHON=sys.executable + ' -u'))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('ZJ_PYTHON executable is unavailable', result.stderr)
        self.helper.unlink()
        for entry in entries:
            result = self.run_entry(entry)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('helper is missing', result.stderr)


if __name__ == '__main__':
    unittest.main()
