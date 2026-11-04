"""Repository-built plugins never become implicit downloads or release upgrades."""
from __future__ import annotations

from contextlib import redirect_stdout
import copy
import hashlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from zjconfig import common, plugin_files, runtime, versions  # noqa: E402


class BundledPluginTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='zj-bundled-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.wasm = b'\0asm\x01\0\0\0test fixture'
        self.bundled = {
            'name': 'guard', 'source': 'bundled', 'repository': 'example/source',
            'tag': 'a' * 40, 'asset': 'guard.wasm',
            'sha256': hashlib.sha256(self.wasm).hexdigest(),
            'license': 'MIT', 'license_path': 'LICENSE',
        }
        self.release = {
            'name': 'release', 'repository': 'example/release', 'tag': 'v1',
            'asset': 'release.wasm', 'sha256': '1' * 64,
            'license': 'MIT', 'license_path': 'LICENSE',
        }
        self.pins = {'schema': 1, 'plugins': [self.release, self.bundled],
                     'zellij': {'tag': 'v1', 'assets': {'tool.tar.gz': '0' * 64}}}

    def test_bundled_source_requires_an_immutable_commit(self):
        self.assertIs(common.validate_versions(self.pins), self.pins)
        self.assertEqual(common.plugin_url(self.bundled),
                         'https://raw.githubusercontent.com/example/source/' + 'a' * 40 + '/plugins/guard.wasm')
        self.assertEqual(common.plugin_url(self.release),
                         'https://github.com/example/release/releases/download/v1/release.wasm')
        for source in [None, True, 'release', 'remote', {}]:
            pins = copy.deepcopy(self.pins)
            pins['plugins'][1]['source'] = source
            with self.subTest(source=source), self.assertRaises(common.ConfigError):
                common.validate_versions(pins)
        for commit in ['main', 'v1', 'a' * 39, 'A' * 40, '../' + 'a' * 40]:
            pins = copy.deepcopy(self.pins)
            pins['plugins'][1]['tag'] = commit
            with self.subTest(commit=commit), self.assertRaises(common.ConfigError):
                common.validate_versions(pins)

    def test_bundled_acquisition_never_downloads_even_when_online(self):
        path = self.root / 'guard.wasm'
        path.write_bytes(self.wasm)
        with mock.patch.object(plugin_files, 'fetch_bytes') as fetch:
            for offline in [False, True]:
                self.assertEqual(plugin_files.acquire(self.bundled, path, offline=offline),
                                 (self.wasm, 'bundle'))
            fetch.assert_not_called()

    def test_optional_artifact_path_is_a_safe_repository_path_to_the_same_asset(self):
        pins = copy.deepcopy(self.pins)
        bundled = pins['plugins'][1]
        bundled['artifact_path'] = 'plugin-sources/guard/guard.wasm'
        common.validate_versions(pins)
        self.assertEqual(common.plugin_url(bundled),
                         'https://raw.githubusercontent.com/example/source/' + 'a' * 40 +
                         '/plugin-sources/guard/guard.wasm')
        invalid = ['', None, '/guard.wasm', '../guard.wasm', 'a/../guard.wasm',
                   'a/./guard.wasm', 'a//guard.wasm', 'a/guard.wasm/',
                   'a/other.wasm', 'a\\guard.wasm', 'a/\nguard.wasm',
                   'a/雪/guard.wasm', 'a/%2e%2e/guard.wasm', 'https://host/guard.wasm']
        for path in invalid:
            bundled['artifact_path'] = path
            with self.subTest(path=path), self.assertRaises(common.ConfigError):
                common.validate_versions(pins)
        pins = copy.deepcopy(self.pins)
        pins['plugins'][0]['artifact_path'] = 'plugins/release.wasm'
        with self.assertRaisesRegex(common.ConfigError, 'Only bundled source plugins'):
            common.validate_versions(pins)

    def test_missing_or_corrupt_bundled_build_fails_without_network_repair(self):
        path = self.root / 'guard.wasm'
        with mock.patch.object(plugin_files, 'fetch_bytes') as fetch:
            with self.assertRaisesRegex(common.ConfigError, 'No valid bundled build'):
                plugin_files.acquire(self.bundled, path)
            path.write_bytes(b'corrupt')
            with self.assertRaisesRegex(common.ConfigError, 'checksum mismatch'):
                plugin_files.acquire(self.bundled, path)
            fetch.assert_not_called()

    def test_release_acquisition_still_prefers_verified_downloads(self):
        pin = {key: value for key, value in self.bundled.items() if key != 'source'}
        pin['tag'] = 'v1'
        with mock.patch.object(plugin_files, 'fetch_bytes', return_value=self.wasm) as fetch:
            self.assertEqual(plugin_files.acquire(pin, self.root / 'missing'), (self.wasm, 'download'))
            self.assertEqual(fetch.call_args.args[0], common.plugin_url(pin))

    def test_version_check_reports_build_without_querying_its_repository(self):
        output = io.StringIO()
        with mock.patch.object(versions, 'load_versions', return_value=self.pins), \
                mock.patch.object(versions, 'github_release', return_value={'tag_name': 'v1'}) as release, \
                redirect_stdout(output):
            self.assertEqual(versions.check_versions(self.root), 0)
        self.assertEqual(release.call_args_list,
                         [mock.call('zellij-org/zellij'), mock.call('example/release')])
        self.assertIn('guard: bundled build pinned to ' + 'a' * 40, output.getvalue())

    def write_source(self):
        (self.root / 'versions.json').write_bytes(common.json_bytes(self.pins))
        (self.root / 'config.kdl').write_text('// source unchanged\n', encoding='utf-8')
        return {name: (self.root / name).read_bytes() for name in ['versions.json', 'config.kdl']}

    def assert_source_unchanged(self, original):
        for name, data in original.items():
            self.assertEqual((self.root / name).read_bytes(), data)

    def test_explicit_bundled_update_rejects_before_network_or_source_changes(self):
        original = self.write_source()
        with mock.patch.object(versions, 'github_release') as release, \
                mock.patch.object(versions, 'fetch_bytes') as fetch:
            for all_latest in [False, True]:
                with self.subTest(all_latest=all_latest), \
                        self.assertRaisesRegex(common.ConfigError, 'reviewed manual rebuild: guard'):
                    versions.update(self.root, {'guard': 'latest'}, None, all_latest=all_latest)
            release.assert_not_called()
            fetch.assert_not_called()
        self.assert_source_unchanged(original)

    def test_update_all_checks_release_components_and_leaves_bundled_build_alone(self):
        self.write_source()
        (self.root / 'config.kdl').write_text(
            'plugins { release location="' + common.plugin_url(self.release) + '"; '
            'guard location="' + common.plugin_url(self.bundled) + '"; }\n', encoding='utf-8')
        (self.root / 'plugins').mkdir()
        build = self.root / 'plugins/guard.wasm'
        build.write_bytes(self.wasm)
        (self.root / 'licenses').mkdir()
        notice = b'Copyright 2026 Example\nPermission is hereby granted, free of charge\n'
        (self.root / 'licenses/release.txt').write_bytes(notice)
        download = 'https://github.com/example/release/releases/download/v2/release.wasm'

        def latest(repository, tag='latest'):
            if repository == 'example/release':
                return {'tag_name': 'v2', 'assets': [{'name': 'release.wasm',
                        'digest': 'sha256:' + hashlib.sha256(self.wasm).hexdigest(),
                        'browser_download_url': download}]}
            if repository == 'zellij-org/zellij':
                return {'tag_name': 'v1', 'assets': [{'name': 'tool.tar.gz', 'digest': 'sha256:' + '0' * 64}]}
            self.fail(f'Unexpected release lookup for {repository}')

        def fetch_artifact(url, *args):
            if url == download:
                return self.wasm
            if url == 'https://raw.githubusercontent.com/example/release/v2/LICENSE':
                return notice
            self.fail(f'Unexpected artifact request for {url}')

        with mock.patch.object(versions, 'github_release', side_effect=latest) as release, \
                mock.patch.object(versions, 'fetch_bytes', side_effect=fetch_artifact) as fetch, \
                redirect_stdout(io.StringIO()):
            versions.update(self.root, {}, None, all_latest=True)
            self.assertEqual(release.call_args_list,
                             [mock.call('example/release', 'latest'), mock.call('zellij-org/zellij', 'latest')])
            self.assertEqual(fetch.call_count, 2)
        updated = common.load_versions(self.root)
        self.assertEqual(updated['plugins'][0]['tag'], 'v2')
        self.assertEqual(updated['plugins'][1], self.bundled)
        self.assertEqual(build.read_bytes(), self.wasm)
        self.assertIn(common.plugin_url(self.bundled), (self.root / 'config.kdl').read_text(encoding='utf-8'))

    def test_runtime_local_build_does_not_create_download_retry_state(self):
        pins = {**self.pins, 'plugins': [self.bundled]}
        (self.root / 'versions.json').write_bytes(common.json_bytes(pins))
        config = self.root / 'config.kdl'
        config.write_text('plugins { guard location="' + common.plugin_url(self.bundled) + '"; }\n',
                          encoding='utf-8')
        (self.root / 'plugins').mkdir()
        (self.root / 'plugins/guard.wasm').write_bytes(self.wasm)
        state = self.root / 'state'
        with mock.patch.object(plugin_files, 'fetch_bytes') as fetch, redirect_stdout(io.StringIO()):
            arguments = runtime.prepare(config, [], state)
            fetch.assert_not_called()
        self.assertEqual(arguments[0], '--config')
        self.assertFalse(list(state.rglob('*.retry.json')))
        self.assertTrue(list(state.rglob('*.bundled.wasm')))
