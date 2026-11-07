"""Identify root options in the pinned Zellij CLI without parsing subcommands.

Attach owns its own -c/--create flag. Stop at the first command or --, and
consume option values as single arguments. Review this table on Zellij upgrades.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterator

from .common import ConfigError


VALUE_OPTIONS = {'--config', '-c', '--config-dir', '--session', '-s', '--layout', '-l',
                 '--new-session-with-layout', '-n', '--data-dir', '--max-panes', '--layout-string'}


@dataclass(frozen=True)
class GlobalOption:
    name: str
    value: str | None
    start: int
    stop: int
    # Flags preceding a config selector in a short cluster, e.g. -dcFILE.
    retained: str = ''


def global_options(arguments: list[str]) -> Iterator[GlobalOption]:
    index = 0
    while index < len(arguments):
        item = arguments[index]
        if item in ['--', '-'] or not item.startswith('-'):
            return
        start = index
        index += 1
        if item.startswith('--'):
            name, separator, value = item.partition('=')
            if name in VALUE_OPTIONS:
                if not separator:
                    if index >= len(arguments):
                        raise ConfigError(f'Missing value for {name}')
                    value = arguments[index]
                    index += 1
                yield GlobalOption(name, value, start, index)
            else:
                yield GlobalOption(item, None, start, index)
            continue
        for position, flag in enumerate(item[1:], 1):
            name = '-' + flag
            if name in VALUE_OPTIONS:
                value = item[position + 1:]
                if value:
                    value = value.removeprefix('=')
                else:
                    if index >= len(arguments):
                        raise ConfigError(f'Missing value for {name}')
                    value = arguments[index]
                    index += 1
                retained = item[:position] if position > 1 else ''
                yield GlobalOption(name, value, start, index, retained)
                break
            if flag not in 'dhV':
                # Let Zellij diagnose unknown options; never guess their arity.
                yield GlobalOption(item, None, start, index)
                break
            yield GlobalOption(name, None, start, index)
