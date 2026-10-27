"""Portable/personal rendering contracts without launching applications."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock
from zoneinfo import ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from zjconfig import kdl, preferences  # noqa: E402
from zjconfig.common import ConfigError  # noqa: E402


def active(text):
    return {node.name: node for node in kdl.parse(text)}


def status_options(text):
    layout = active(text)['layout']
    template = next(node for node in layout.children if node.name == 'default_tab_template')
    pane = next(node for node in template.children if node.name == 'pane')
    plugin = next(node for node in pane.children if node.name == 'plugin')
    return {node.name: node for node in plugin.children}


class SchemaTests(unittest.TestCase):
    def test_preset_defaults_and_explicit_overrides(self):
        portable = preferences.validate_settings({'schema': 1})
        self.assertEqual((portable['session_name'], portable['lock_key'], portable['timezone']),
                         (None, 'Ctrl g', 'UTC'))
        self.assertFalse(portable['git_status'] or portable['rust_backtrace'] or portable['attach_to_session'])
        classic = preferences.validate_settings({'schema': 1, 'profile': 'classic'})
        self.assertEqual((classic['session_name'], classic['lock_key'], classic['timezone']),
                         ('main', 'F12', 'America/Denver'))
        self.assertTrue(classic['git_status'] and classic['rust_backtrace'] and classic['attach_to_session'])
        explicit = preferences.validate_settings({'schema': 1, 'profile': 'classic',
                                                   'session_name': None, 'git_status': False})
        self.assertIsNone(explicit['session_name'])
        self.assertFalse(explicit['git_status'])

    def test_status_frames_are_coordinated_without_overriding_explicit_choice(self):
        self.assertFalse(preferences.validate_settings({'schema': 1, 'layout': 'zjstatus'})['pane_frames'])
        self.assertTrue(preferences.validate_settings({'schema': 1, 'layout': 'zjstatus',
                                                        'pane_frames': True})['pane_frames'])

    def test_schema_rejects_unknown_and_ambiguous_values(self):
        invalid = [None, [], {}, {'schema': True}, {'schema': 2}, {'schema': 1, 'unknown': True},
                   {'schema': 1, 'profile': 'other'}, {'schema': 1, 'layout': '../dev'},
                   {'schema': 1, 'lock_key': 'Ctrl q'}, {'schema': 1, 'git_status': 1},
                   {'schema': 1, 'rust_backtrace': 'false'}, {'schema': 1, 'theme': ''},
                   {'schema': 1, 'session_name': 'bad\nname'}, {'schema': 1, 'timezone': '/etc/passwd'}]
        for raw in invalid:
            with self.subTest(raw=raw), self.assertRaises(ConfigError):
                preferences.validate_settings(raw)

    def test_builtin_zones_work_without_tzdata_and_other_zones_fail_helpfully(self):
        with mock.patch.object(preferences, 'ZoneInfo', side_effect=ZoneInfoNotFoundError):
            for zone in ['UTC', 'Etc/UTC', 'America/Denver']:
                self.assertEqual(preferences.validate_settings({'schema': 1, 'timezone': zone})['timezone'], zone)
            with self.assertRaisesRegex(ConfigError, 'tzdata'):
                preferences.validate_settings({'schema': 1, 'timezone': 'Europe/Paris'})

    def test_local_json_is_optional_and_duplicate_keys_fail(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.assertIsNone(preferences.read_settings(directory))
            file = directory / preferences.LOCAL_FILE
            file.write_text('{"schema": 1, "profile": "classic"}', encoding='utf-8')
            self.assertEqual(preferences.read_settings(directory)['session_name'], 'main')
            file.write_text('{"schema": 1, "git_status": true, "git_status": false}', encoding='utf-8')
            with self.assertRaisesRegex(ConfigError, 'Duplicate'):
                preferences.read_settings(directory)
            file.write_text('{broken', encoding='utf-8')
            with self.assertRaisesRegex(ConfigError, 'JSON'):
                preferences.read_settings(directory)

    def test_local_json_rejects_existing_and_broken_symlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            target = directory / 'actual.json'
            target.write_text('{"schema": 1}', encoding='utf-8')
            file = directory / preferences.LOCAL_FILE
            try:
                file.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest('Symlink creation requires native permissions')
            with self.assertRaisesRegex(ConfigError, 'symlink'):
                preferences.read_settings(directory)
            target.unlink()
            with self.assertRaisesRegex(ConfigError, 'symlink'):
                preferences.read_settings(directory)


class RenderingTests(unittest.TestCase):
    def setUp(self):
        self.config = (ROOT / 'config.kdl').read_text(encoding='utf-8')
        self.status = (ROOT / 'layouts/zjstatus.kdl').read_text(encoding='utf-8')
        self.portable = preferences.validate_settings({'schema': 1})
        self.classic = preferences.validate_settings({'schema': 1, 'profile': 'classic'})

    def test_checked_in_defaults_are_portable_and_commands_are_opt_in(self):
        roots = active(self.config)
        self.assertNotIn('session_name', roots)
        self.assertEqual(roots['attach_to_session'].arguments, ['false'])
        self.assertFalse(any(node.name == 'RUST_BACKTRACE' for node in roots['env'].children))
        options = status_options(self.status)
        self.assertEqual(options['datetime_timezone'].arguments, ['UTC'])
        self.assertFalse(any(name.startswith('command_git_branch') for name in options))
        self.assertNotIn('{command_git_branch}', options['format_right'].arguments[0])
        for file in (ROOT / 'layouts').glob('*.kdl'):
            def descendants(nodes):
                for node in nodes:
                    yield node
                    yield from descendants(node.children)
            self.assertFalse(any(node.name == 'command' for node in descendants(kdl.parse(file.read_text(encoding='utf-8')))))

    def test_classic_restores_workflow_and_portable_removes_it(self):
        classic = preferences.render_config(self.config, self.classic)
        roots = active(classic)
        self.assertEqual(roots['session_name'].arguments, ['main'])
        self.assertEqual(roots['attach_to_session'].arguments, ['true'])
        self.assertEqual(next(node for node in roots['env'].children if node.name == 'RUST_BACKTRACE').arguments, ['1'])
        for context in roots['keybinds'].children:
            if context.name == 'locked' or (context.name == 'shared_except' and context.arguments == ['locked']):
                self.assertTrue(any(node.name == 'unbind' and node.arguments == ['Ctrl g'] for node in context.children))
                self.assertTrue(any(node.name == 'bind' and node.arguments == ['F12'] for node in context.children))
        portable = active(preferences.render_config(classic, self.portable))
        self.assertNotIn('session_name', portable)
        self.assertFalse(any(node.name == 'RUST_BACKTRACE' for node in portable['env'].children))
        self.assertEqual(kdl.plugin_locations(classic), kdl.plugin_locations(self.config))

    def test_status_opt_in_and_portable_removal_are_complete(self):
        classic = preferences.render_layout(self.status, 'zjstatus', self.classic)
        options = status_options(classic)
        self.assertEqual(options['datetime_timezone'].arguments, ['America/Denver'])
        self.assertEqual(options['command_git_branch_command'].arguments, ['git rev-parse --abbrev-ref HEAD'])
        self.assertEqual(options['format_right'].arguments[0].count('{command_git_branch}'), 1)
        portable = status_options(preferences.render_layout(classic, 'zjstatus.kdl', self.portable))
        self.assertFalse(any(name.startswith('command_git_branch') for name in portable))
        self.assertNotIn('{command_git_branch}', portable['format_right'].arguments[0])

    def test_rendering_is_idempotent_and_user_settings_are_literal(self):
        settings = preferences.validate_settings({'schema': 1, 'profile': 'classic',
                                                   'session_name': 'repo [雪] "quoted"', 'theme': 'custom theme'})
        once = preferences.render_config(self.config, settings)
        self.assertEqual(preferences.render_config(once, settings), once)
        self.assertEqual(active(once)['session_name'].arguments, ['repo [雪] "quoted"'])
        status = preferences.render_layout(self.status, 'zjstatus', settings)
        self.assertEqual(preferences.render_layout(status, 'zjstatus', settings), status)

    def test_grouped_lock_bindings_preserve_unrelated_keys_and_actions(self):
        for profile in ['portable', 'classic']:
            settings = preferences.validate_settings({'schema': 1, 'profile': profile})
            for keys in ['"Ctrl g" r#"Ctrl w"#', 'r#"Ctrl w"# "F12" "Ctrl g"']:
                with self.subTest(profile=profile, keys=keys):
                    text = ('keybinds {\n'
                            '    locked {\n'
                            f'        bind {keys} {{ WriteChars "original"; }}\n'
                            '        unbind "Ctrl x" "F12" "Ctrl g"\n'
                            '    }\n'
                            '    shared_except "locked" {\n'
                            f'        bind {keys} /- "Ctrl z" {{ WriteChars "original"; }}\n'
                            '    }\n'
                            '}\n')
                    rendered = preferences.render_config(text, settings)
                    contexts = active(rendered)['keybinds'].children
                    for context in contexts:
                        binding = next(node for node in context.children
                                       if node.name == 'bind' and node.arguments == ['Ctrl w'])
                        self.assertEqual(binding.children[0].name, 'WriteChars')
                        self.assertEqual(binding.children[0].arguments, ['original'])
                        selected = next(node for node in context.children
                                        if node.name == 'bind' and node.arguments == [settings['lock_key']])
                        self.assertEqual(selected.children[0].name, 'SwitchToMode')
                    self.assertTrue(any(node.name == 'unbind' and node.arguments == ['Ctrl x']
                                        for node in contexts[0].children))
                    self.assertIn('r#"Ctrl w"#', rendered)
                    self.assertIn('/- "Ctrl z"', rendered)
                    self.assertEqual(preferences.render_config(rendered, settings), rendered)

    def test_active_node_replacement_preserves_examples_and_nested_settings(self):
        text = ('/* nested /* theme "ignored" */ still ignored */\n'
                '// theme "example"\n/- theme "slashdash"\n'
                'theme r#"old"#; // keep inline comment\n'
                'env { theme "nested"; }\n')
        rendered = preferences.set_root_nodes(text, {'theme': 'theme "new"', 'layout_dir': 'layout_dir "C:\\\\layouts"'})
        self.assertIn('// theme "example"', rendered)
        self.assertIn('/- theme "slashdash"', rendered)
        self.assertIn('/* nested /* theme "ignored" */ still ignored */', rendered)
        self.assertIn('env { theme "nested"; }', rendered)
        self.assertIn('// keep inline comment', rendered)
        self.assertEqual(active(rendered)['theme'].arguments, ['new'])
        self.assertEqual(active(rendered)['layout_dir'].arguments, ['C:\\layouts'])
        removed = preferences.set_root_nodes(rendered, {'theme': None})
        self.assertNotIn('theme', active(removed))
        self.assertIn('/- theme "slashdash"', removed)
        with self.assertRaises(ConfigError):
            preferences.set_root_nodes(text, {'theme': 'theme "new"; session_name "injected"'})

    def test_staged_rendering_uses_adjacent_preferences_without_mutating_them(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / 'config.kdl').write_text(self.config, encoding='utf-8')
            shutil.copytree(ROOT / 'layouts', directory / 'layouts')
            preferences.render_directory(directory)
            self.assertEqual((directory / 'config.kdl').read_text(encoding='utf-8'), self.config)
            file = directory / preferences.LOCAL_FILE
            contents = json.dumps({'schema': 1, 'profile': 'classic', 'layout': 'minimal'})
            file.write_text(contents, encoding='utf-8')
            preferences.render_directory(directory)
            self.assertEqual(active((directory / 'config.kdl').read_text(encoding='utf-8'))['default_layout'].arguments, ['minimal'])
            self.assertEqual(file.read_text(encoding='utf-8'), contents)
            self.assertTrue((directory / 'layouts/minimal.swap.kdl').is_file())


if __name__ == '__main__':
    unittest.main()
