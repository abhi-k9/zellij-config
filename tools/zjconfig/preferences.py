"""Validated, optional local preferences for the checked-in portable config.

KDL does not interpolate arbitrary environment variables. Render only active
nodes, leaving documented examples and plugin pins untouched.
"""
from __future__ import annotations

import json
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .common import ConfigError
from .kdl import Node, parse, quote


LOCAL_FILE = '.zellij-config-local.json'
LAYOUTS = ('default', 'dev', 'zjstatus', 'minimal')
PRESETS = {
    'portable': {
        'timezone': 'UTC', 'git_status': False, 'session_name': None,
        'attach_to_session': False, 'rust_backtrace': False, 'lock_key': 'Ctrl g',
        'layout': 'default', 'theme': 'catppuccin-mocha', 'pane_frames': True,
    },
    'classic': {
        'timezone': 'America/Denver', 'git_status': True, 'session_name': 'main',
        'attach_to_session': True, 'rust_backtrace': True, 'lock_key': 'F12',
        'layout': 'default', 'theme': 'catppuccin-mocha', 'pane_frames': True,
    },
}


def _string(value, name: str) -> str:
    if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 for c in value):
        raise ConfigError(f'{name} must be a nonempty string without control characters')
    return value


def validate_settings(raw) -> dict:
    """Return effective settings; unknown keys and coercions fail explicitly."""
    if not isinstance(raw, dict):
        raise ConfigError('Local preferences must be a JSON object')
    allowed = {'schema', 'profile', *PRESETS['portable']}
    unknown = set(raw) - allowed
    if unknown:
        raise ConfigError('Unknown local preference: ' + ', '.join(sorted(map(str, unknown))))
    if type(raw.get('schema')) is not int or raw['schema'] != 1:
        raise ConfigError('Local preferences require "schema": 1')
    profile = raw.get('profile', 'portable')
    if not isinstance(profile, str) or profile not in PRESETS:
        raise ConfigError('profile must be portable or classic')
    result = {'schema': 1, 'profile': profile, **PRESETS[profile], **raw}
    for key in ['git_status', 'attach_to_session', 'rust_backtrace', 'pane_frames']:
        if type(result[key]) is not bool:
            raise ConfigError(f'{key} must be a boolean')
    if result['session_name'] is not None:
        _string(result['session_name'], 'session_name')
    if result['lock_key'] not in ['F12', 'Ctrl g']:
        raise ConfigError('lock_key must be F12 or Ctrl g')
    if result['layout'] not in LAYOUTS:
        raise ConfigError('layout must be ' + ', '.join(LAYOUTS))
    _string(result['theme'], 'theme')
    timezone = _string(result['timezone'], 'timezone')
    # Both shipped presets are known IANA names. Native Windows may have no
    # zoneinfo database, so these must remain usable without a Python package.
    if timezone not in ['UTC', 'Etc/UTC', 'America/Denver']:
        try:
            ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ConfigError(f'Unknown or unavailable IANA timezone {timezone!r}; '
                              'use UTC or install a system timezone database / Python tzdata') from error
    if 'pane_frames' not in raw and result['layout'] == 'zjstatus':
        result['pane_frames'] = False
    return result


def _unique_object(pairs):
    found = {}
    for name, value in pairs:
        if name in found:
            raise ConfigError(f'Duplicate local preference: {name}')
        found[name] = value
    return found


def read_settings(directory: Path) -> dict | None:
    """Read preferences beside config.kdl, returning None when not configured."""
    return settings_snapshot(directory)[0]


def settings_snapshot(directory: Path) -> tuple[dict | None, bytes | None]:
    """Pair validated preferences with the exact bytes used to render them."""
    file = Path(directory) / LOCAL_FILE
    if file.is_symlink():
        raise ConfigError(f'Refusing a local preferences symlink: {file}')
    try:
        data = file.read_bytes()
    except FileNotFoundError:
        return None, None
    except (OSError, UnicodeError) as error:
        raise ConfigError(f'Cannot read local preferences {file}: {error}') from error
    if len(data) > 64 * 1024:
        raise ConfigError('Local preferences exceed the 64 KiB limit')
    try:
        raw = json.loads(data.decode('utf-8'), object_pairs_hook=_unique_object)
    except (json.JSONDecodeError, UnicodeError) as error:
        raise ConfigError(f'Invalid local preferences JSON in {file}: {error}') from error
    return validate_settings(raw), data


def _edits(text: str, edits: list[tuple[int, int, str]]) -> str:
    for start, end, replacement in sorted(edits, reverse=True):
        text = text[:start] + replacement + text[end:]
    return text


def _settings_edits(nodes: list[Node], mapping: dict[str, str | None]):
    edits = []
    missing = dict(mapping)
    for node in nodes:
        if node.name in mapping:
            value = missing.pop(node.name, None)
            edits.append((node.start, node.end, value or ''))
    return edits, [value for value in missing.values() if value is not None]


def set_root_nodes(text: str, mapping: dict[str, str | None]) -> str:
    """Set/remove active root nodes, preserving comments and slashdash nodes."""
    for name, value in mapping.items():
        if value is not None:
            nodes = parse(value)
            if len(nodes) != 1 or nodes[0].name != name:
                raise ConfigError(f'Expected exactly one replacement KDL node named {name}')
    edits, additions = _settings_edits(parse(text), mapping)
    result = _edits(text, edits)
    if additions:
        result = result.rstrip() + '\n\n' + '\n'.join(additions) + '\n'
    return result


def _set_children(text: str, parent: Node, mapping: dict[str, str | None], indent: str) -> str:
    edits, additions = _settings_edits(parent.children, mapping)
    if additions:
        edits.append((parent.end - 1, parent.end - 1,
                      '\n' + '\n'.join(indent + node for node in additions) + '\n' + indent[:-4]))
    return _edits(text, edits)


def _lock_bindings(text: str, key: str) -> str:
    roots = parse(text)
    keybinds = next((node for node in roots if node.name == 'keybinds'), None)
    if keybinds is None:
        text = set_root_nodes(text, {'keybinds': 'keybinds {\n}\n'})
        keybinds = next(node for node in parse(text) if node.name == 'keybinds')
    contexts = [('locked', [], 'Normal'), ('shared_except', ['locked'], 'Locked')]
    for name, arguments, mode in contexts:
        keybinds = next(node for node in parse(text) if node.name == 'keybinds')
        context = next((node for node in keybinds.children
                        if node.name == name and node.arguments == arguments), None)
        contents = []
        if key == 'F12':
            contents.append('unbind "Ctrl g"')
        contents.append(f'bind {quote(key)} {{ SwitchToMode {quote(mode)}; }}')
        if context is None:
            header = name + ''.join(' ' + quote(value) for value in arguments)
            addition = '\n    ' + header + ' {\n' + '\n'.join('        ' + line for line in contents) + '\n    }\n'
            text = _edits(text, [(keybinds.end - 1, keybinds.end - 1, addition)])
        else:
            desired = [(parse(line)[0], line) for line in contents]
            edits = []
            for node in context.children:
                managed = {'F12', 'Ctrl g'}
                if node.name not in ['bind', 'unbind'] or not managed.intersection(node.arguments):
                    continue
                if any(argument not in managed for argument in node.arguments):
                    # A grouped binding shares one action body. Keep that body,
                    # unrelated keys, comments and inactive arguments intact;
                    # add the selected lock action as a separate binding below.
                    edits.extend((start, end, '')
                                 for argument, (start, end) in zip(node.arguments, node.argument_spans)
                                 if argument in managed)
                    continue
                match = next((index for index, (wanted, _) in enumerate(desired)
                              if node.name == wanted.name and wanted.arguments[0] in node.arguments), None)
                replacement = desired.pop(match)[1] if match is not None else ''
                edits.append((node.start, node.end, replacement))
            if desired:
                edits.append((context.end - 1, context.end - 1,
                              '\n' + '\n'.join('        ' + line for _, line in desired) + '\n    '))
            text = _edits(text, edits)
    return text


def render_config(text: str, settings: dict) -> str:
    settings = validate_settings(settings)
    text = set_root_nodes(text, {
        'theme': 'theme ' + quote(settings['theme']),
        'default_layout': 'default_layout ' + quote(settings['layout']),
        'session_name': ('session_name ' + quote(settings['session_name'])
                         if settings['session_name'] is not None else None),
        'attach_to_session': 'attach_to_session ' + str(settings['attach_to_session']).lower(),
        'pane_frames': 'pane_frames ' + str(settings['pane_frames']).lower(),
    })
    env = next((node for node in parse(text) if node.name == 'env'), None)
    if env:
        text = _set_children(text, env, {
            'RUST_BACKTRACE': 'RUST_BACKTRACE "1"' if settings['rust_backtrace'] else None,
        }, '    ')
    elif settings['rust_backtrace']:
        text = set_root_nodes(text, {'env': 'env {\n    RUST_BACKTRACE "1"\n}'})
    return _lock_bindings(text, settings['lock_key'])


def render_layout(text: str, name: str, settings: dict) -> str:
    settings = validate_settings(settings)
    if name.removesuffix('.kdl') != 'zjstatus':
        return text
    for root in parse(text):
        if root.name != 'layout':
            continue
        for template in root.children:
            if template.name != 'default_tab_template':
                continue
            for pane in template.children:
                for plugin in pane.children:
                    if plugin.name != 'plugin' or plugin.properties.get('location') != 'zjstatus':
                        continue
                    right = next((node.arguments[0] for node in plugin.children
                                  if node.name == 'format_right' and node.arguments), '{swap_layout}{datetime}')
                    right = right.replace('{command_git_branch}', '')
                    if settings['git_status']:
                        marker = '{swap_layout}'
                        right = (right.replace(marker, marker + '{command_git_branch}', 1)
                                 if marker in right else '{command_git_branch}' + right)
                    return _set_children(text, plugin, {
                        'datetime_timezone': 'datetime_timezone ' + quote(settings['timezone']),
                        'format_right': 'format_right ' + quote(right),
                        'command_git_branch_command': ('command_git_branch_command "git rev-parse --abbrev-ref HEAD"'
                                                       if settings['git_status'] else None),
                        'command_git_branch_format': ('command_git_branch_format "#[fg=$green,bg=$bg]  {stdout} "'
                                                      if settings['git_status'] else None),
                        'command_git_branch_interval': 'command_git_branch_interval "15"' if settings['git_status'] else None,
                        'command_git_branch_rendermode': ('command_git_branch_rendermode "static"'
                                                         if settings['git_status'] else None),
                        'command_git_branch_cwd': None if not settings['git_status'] else next(
                            (text[node.start:node.end] for node in plugin.children
                             if node.name == 'command_git_branch_cwd'), None),
                    }, '                ')
    raise ConfigError('Cannot render zjstatus preferences: expected the zjstatus plugin in its default tab template')


def render_directory(directory: Path, settings: dict | None = None) -> None:
    """Render staged managed config/layouts; never create a local settings file."""
    directory = Path(directory)
    settings = read_settings(directory) if settings is None else validate_settings(settings)
    if settings is None:
        return
    config = directory / 'config.kdl'
    rendered = {config: render_config(config.read_text(encoding='utf-8'), settings)}
    for name in LAYOUTS:
        file = directory / 'layouts' / (name + '.kdl')
        if file.is_file():
            rendered[file] = render_layout(file.read_text(encoding='utf-8'), name, settings)
    # Compute every result before publishing any; syntax/schema failures cannot
    # leave a partly rendered staging tree.
    for file, text in rendered.items():
        file.write_text(text, encoding='utf-8')
