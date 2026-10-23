"""Read active plugin locations in KDL v1 without regex comment stripping.

This is a small tokenizer/node reader, not a replacement for Zellij's validator.
It handles nested block comments, slashdash nodes/entries, escaped and raw strings,
and line continuations. Unsupported or malformed input fails explicitly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import re

from .common import ConfigError


@dataclass
class Token:
    kind: str
    value: str


@dataclass
class Node:
    name: str
    properties: dict[str, str] = field(default_factory=dict)
    arguments: list[str] = field(default_factory=list)
    children: list['Node'] = field(default_factory=list)


def tokens(text: str) -> list[Token]:
    if len(text) > 8 * 1024 * 1024:
        raise ConfigError('KDL input exceeds the 8 MiB helper limit')
    result = []
    i = 0
    while i < len(text):
        c = text[i]
        if c in ' \t\r\ufeff':
            i += 1
        elif text.startswith('//', i):
            end = text.find('\n', i)
            i = len(text) if end < 0 else end
        elif text.startswith('/*', i):
            depth = 1
            i += 2
            while i < len(text) and depth:
                if text.startswith('/*', i):
                    depth += 1
                    i += 2
                elif text.startswith('*/', i):
                    depth -= 1
                    i += 2
                else:
                    i += 1
            if depth:
                raise ConfigError('Unclosed KDL block comment')
        elif text.startswith('/-', i):
            result.append(Token('skip', '/-'))
            i += 2
        elif c == '\\':
            end = text.find('\n', i)
            tail = text[i + 1:end if end >= 0 else len(text)].strip()
            if end < 0 or (tail and not tail.startswith('//')):
                raise ConfigError('Invalid KDL line continuation')
            i = end + 1
        elif c in '\n;{}=()':
            result.append(Token(c, c))
            i += 1
        elif c == '"' or (c == 'r' and re.match(r'r#*"', text[i:])):
            raw = re.match(r'r(#+)?"', text[i:]) if c == 'r' else None
            if raw:
                hashes = raw.group(1) or ''
                start = i + len(raw.group(0))
                end = text.find('"' + hashes, start)
                if end < 0:
                    raise ConfigError('Unclosed KDL raw string')
                value = text[start:end]
                i = end + 1 + len(hashes)
            else:
                start = i + 1
                i = start
                value = ''
                escapes = {'n': '\n', 'r': '\r', 't': '\t', 'b': '\b', 'f': '\f', '"': '"', '\\': '\\', '/': '/'}
                while i < len(text) and text[i] != '"':
                    if text[i] == '\\':
                        i += 1
                        if i >= len(text):
                            raise ConfigError('Unclosed KDL escape')
                        if text.startswith('u{', i):
                            end = text.find('}', i + 2)
                            digits = text[i + 2:end]
                            if end < 0 or not re.fullmatch(r'[0-9a-fA-F]{1,6}', digits):
                                raise ConfigError('Invalid KDL Unicode escape')
                            try:
                                number = int(digits, 16)
                                if 0xD800 <= number <= 0xDFFF:
                                    raise ValueError('Surrogate is not a Unicode scalar')
                                value += chr(number)
                            except (ValueError, OverflowError) as error:
                                raise ConfigError('Invalid KDL Unicode escape') from error
                            i = end + 1
                        elif text[i] in escapes:
                            value += escapes[text[i]]
                            i += 1
                        else:
                            raise ConfigError('Unsupported KDL string escape')
                    else:
                        value += text[i]
                        i += 1
                if i >= len(text):
                    raise ConfigError('Unclosed KDL string')
                i += 1
            result.append(Token('value', value))
        else:
            start = i
            while i < len(text) and text[i] not in ' \t\r\n;{}=()"\\':
                if text.startswith(('//', '/*', '/-'), i):
                    break
                i += 1
            if start == i:
                raise ConfigError(f'Unsupported KDL character at offset {i}')
            result.append(Token('value', text[start:i]))
    return result


def parse(text: str) -> list[Node]:
    stream = tokens(text)
    pos = 0

    def value() -> str:
        nonlocal pos
        if pos < len(stream) and stream[pos].kind == '(':
            pos += 1
            if pos + 1 >= len(stream) or stream[pos].kind != 'value' or stream[pos + 1].kind != ')':
                raise ConfigError('Invalid KDL type annotation')
            pos += 2
        if pos >= len(stream) or stream[pos].kind != 'value':
            raise ConfigError('Expected KDL value')
        item = stream[pos].value
        pos += 1
        return item

    def nodes(nested=False, depth=0) -> list[Node]:
        nonlocal pos
        if depth > 128:
            raise ConfigError('KDL node nesting exceeds the helper limit')
        found = []
        while pos < len(stream):
            while pos < len(stream) and stream[pos].kind in ['\n', ';']:
                pos += 1
            if pos == len(stream):
                break
            if stream[pos].kind == '}':
                if not nested:
                    raise ConfigError('Unexpected KDL closing brace')
                pos += 1
                return found
            omit = stream[pos].kind == 'skip'
            if omit:
                pos += 1
            node = Node(value())
            while pos < len(stream) and stream[pos].kind not in ['\n', ';', '}']:
                discard = stream[pos].kind == 'skip'
                if discard:
                    pos += 1
                if pos < len(stream) and stream[pos].kind == '{':
                    pos += 1
                    children = nodes(True, depth + 1)
                    if not discard:
                        node.children.extend(children)
                    break
                key = value()
                if pos < len(stream) and stream[pos].kind == '=':
                    pos += 1
                    item = value()
                    if not discard:
                        node.properties[key] = item
                elif not discard:
                    node.arguments.append(key)
            if not omit:
                found.append(node)
        if nested:
            raise ConfigError('Unclosed KDL node')
        return found

    return nodes()


def plugin_locations(text: str) -> list[str]:
    roots = parse(text)
    return sorted({node.properties['location'] for root in roots if root.name == 'plugins'
                   for node in root.children if 'location' in node.properties})


def quote(value: str) -> str:
    if any(ord(c) < 32 for c in value):
        raise ConfigError('Control characters in config paths are unsupported')
    return json.dumps(value, ensure_ascii=False)
