"""Failure paths that must preserve a usable config on every supported host."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import copy
import io
import os
import subprocess
import sys
from unittest import mock

from test_regressions import ROOT, Workspace
from zjconfig import cli, common, install, kdl, launcher, preferences


class RobustnessTests(Workspace):
    def test_launcher_install_preserves_binary_and_directory_collisions(self):
        self.bin.mkdir()
        original = b'\xff\xfe\x00unrelated executable'
        (self.bin / 'zj').write_bytes(original)
        (self.bin / 'zj.cmd').mkdir()
        (self.bin / 'zj.cmd/keep').write_bytes(b'keep')
        install.install_launcher(ROOT, self.bin)
        self.assertEqual((self.bin / 'zj').read_bytes(), original)
        self.assertEqual((self.bin / 'zj.cmd/keep').read_bytes(), b'keep')
        self.assertEqual((self.bin / 'zj.ps1').read_bytes(), (ROOT / 'launcher/zj.ps1').read_bytes())
        self.assertTrue((self.bin / '.zellij-config/manage.py').is_file())

    def test_dangling_slashdash_is_a_configuration_error(self):
        for text in ['/-', 'node /-', 'plugins { item /-']:
            with self.subTest(text=text), self.assertRaises(common.ConfigError):
                kdl.parse(text)

    def test_version_schema_requires_an_integer(self):
        pins = common.load_versions(ROOT)
        for schema in [True, 1.0, '1']:
            invalid = copy.deepcopy(pins)
            invalid['schema'] = schema
            with self.subTest(schema=schema), self.assertRaises(common.ConfigError):
                common.validate_versions(invalid)

    def test_corrupt_deployment_ledger_reports_an_incomplete_scan(self):
        config = self.base / 'config.kdl'
        config.write_text('plugins {}\n', encoding='utf-8')
        ledger = self.base / '.zellij-config-versions.json'
        for data in [[], {'plugins': [None]}, {'schema': True, 'plugins': []}]:
            ledger.write_bytes(common.json_bytes(data))
            with self.subTest(data=data), mock.patch.object(launcher, 'github_release') as fetch, \
                    redirect_stdout(io.StringIO()) as output:
                self.assertEqual(launcher.launch(['--check-updates', str(config)]), 2)
                self.assertIn('Could not check plugin pins', output.getvalue())
                fetch.assert_not_called()

    def test_oversized_preference_change_preserves_existing_file_and_dry_run(self):
        config = self.base / 'config.kdl'
        config.write_bytes((ROOT / 'config.kdl').read_bytes())
        file = self.base / preferences.LOCAL_FILE
        previous = common.json_bytes({'schema': 1, 'theme': 'catppuccin-mocha'})
        file.write_bytes(previous)
        # Unicode makes encoded bytes exceed the budget before character count.
        for extra in [[], ['--dry-run']]:
            file.write_bytes(previous)
            with self.subTest(extra=extra), redirect_stderr(io.StringIO()) as error:
                result = cli.main(['configure', '--config-dir', str(self.base),
                                   '--theme', '雪' * 22000, *extra])
                self.assertEqual(result, 1)
                self.assertIn('64 KiB', error.getvalue())
                self.assertEqual(file.read_bytes(), previous)

    def test_source_edit_cannot_introduce_an_unverified_deployment_alias(self):
        source = self.clone()
        private_tempdir = install.private_tempdir
        changed = False

        def edit_after_validation(parent, prefix):
            nonlocal changed
            stage = private_tempdir(parent, prefix)
            if prefix.startswith(self.target.name + '.stage-') and not changed:
                changed = True
                config = source / 'config.kdl'
                old = common.plugin_url(common.load_versions(source)['plugins'][0])
                config.write_text(config.read_text(encoding='utf-8').replace(
                    old, 'https://example.invalid/unverified.wasm'), encoding='utf-8')
            return stage

        with mock.patch.object(install, 'private_tempdir', side_effect=edit_after_validation):
            self.setup_config(source)
        self.assertTrue(changed)
        locations = kdl.plugin_locations((self.target / 'config.kdl').read_text(encoding='utf-8'))
        self.assertTrue(all(location.startswith('file:') for location in locations), locations)

    def test_native_validation_decodes_utf8_diagnostics_without_a_utf8_locale(self):
        script = '''
from pathlib import Path
import subprocess, sys
from unittest import mock
from zjconfig import common, install
run = subprocess.run
def native(*args, **kwargs):
    return run([sys.executable, '-c',
                "import sys; sys.stdout.buffer.write(bytes.fromhex('e99baa')); sys.exit(1)"], **kwargs)
try:
    with mock.patch.object(install.subprocess, 'run', side_effect=native):
        install.validate_kdl(Path(sys.argv[1]), sys.executable)
except common.ConfigError as error:
    sys.stdout.buffer.write(str(error).encode('utf-8'))
else:
    raise AssertionError('Invalid config unexpectedly passed')
'''
        environment = dict(os.environ, PYTHONPATH=str(ROOT / 'tools'), PYTHONUTF8='0',
                           PYTHONCOERCECLOCALE='0', LC_ALL='C')
        result = subprocess.run([sys.executable, '-c', script, str(self.base)], env=environment,
                                capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('雪'.encode('utf-8'), result.stdout)
