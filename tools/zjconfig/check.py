"""Fail-closed repository inventory, pin, license and real-parser checks."""
from __future__ import annotations

import ast
from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.parse import unquote, urlsplit

from .common import ConfigError, load_versions, plugin_url, sha256
from .install import validate
from .kdl import parse, plugin_locations
from .versions import checksums, documentation


REQUIRED = [
    'README.md', 'VERSIONS.md', 'docs/CONFIGURATION.md', 'config.kdl',
    'themes/example-custom.kdl.example', 'versions.json', 'plugins.sha256',
    'setup.sh', 'setup.ps1', 'check.sh', 'tools/manage.py',
    'launcher/zj', 'launcher/zj.cmd', 'launcher/zj.ps1',
    'hooks/pre-commit', '.github/workflows/check.yml', 'THIRD_PARTY_NOTICES.md',
    'ci-tools.json', 'tools/lint_workflow.py', 'requirements-dev.txt',
    'package.json', 'package-lock.json', 'pyproject.toml', 'tests/test_regressions.py',
    'docs/AUDIT_FIXES.md',
    *['layouts/' + name + suffix for name in ['default', 'dev', 'zjstatus']
      for suffix in ['.kdl', '.swap.kdl']],
    *['cheatsheets/' + name + '.html' for name in
      ['zellij-cheatsheet', 'zellij-plugins-cheatsheet', 'kdl-syntax-cheatsheet', 'verification-checklist']],
    *['tools/zjconfig/' + name + '.py' for name in
      ['__init__', 'cli', 'common', 'install', 'kdl', 'launcher', 'plugin_files', 'runtime', 'versions', 'check']],
]


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        self.links.extend(value for key, value in attrs if key in ['href', 'src'] and value)
        if tag in ['div', 'table', 'tr', 'td']:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in ['div', 'table', 'tr', 'td']:
            if not self.stack or self.stack.pop() != tag:
                raise ConfigError(f'Mismatched HTML tag: {tag}')


def local_link(root: Path, source: Path, destination: str) -> None:
    parsed = urlsplit(destination)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return
    path = unquote(parsed.path)
    target = root / path.lstrip('/') if path.startswith('/') else source.parent / path
    if not target.exists():
        raise ConfigError(f'Broken local link in {source.relative_to(root)}: {destination}')


def check(root: Path, static=False) -> None:
    for name in REQUIRED:
        path = root / name
        if not path.is_file():
            raise ConfigError(f'Required file missing: {name}')
        path.read_bytes()  # Readability/I/O errors are failures, not skipped checks.
    pins = load_versions(root)
    locations = plugin_locations((root / 'config.kdl').read_text(encoding='utf-8'))
    expected = sorted(plugin_url(pin) for pin in pins['plugins'])
    if locations != expected:
        raise ConfigError('Config plugin pins differ from versions.json')
    if (root / 'plugins.sha256').read_bytes() != checksums(pins):
        raise ConfigError('plugins.sha256 drifted; regenerate it from versions.json')
    if (root / 'VERSIONS.md').read_bytes() != documentation(pins):
        raise ConfigError('VERSIONS.md drifted; regenerate it from versions.json')
    expected_assets = {pin['asset'] for pin in pins['plugins']}
    actual_assets = {path.name for path in (root / 'plugins').glob('*.wasm')}
    if expected_assets != actual_assets:
        raise ConfigError('The bundled plugin inventory differs from versions.json')
    for pin in pins['plugins']:
        if sha256(root / 'plugins' / pin['asset']) != pin['sha256']:
            raise ConfigError(f'Bundled plugin checksum mismatch: {pin["asset"]}')
        notice = (root / 'licenses' / (pin['name'] + '.txt')).read_text(encoding='utf-8')
        if 'Copyright' not in notice or 'Permission is hereby granted, free of charge' not in notice:
            raise ConfigError(f'Missing upstream MIT notice: {pin["name"]}')
    for path in [root / 'config.kdl', *(root / 'layouts').glob('*.kdl'), *(root / 'themes').glob('*.kdl')]:
        parse(path.read_text(encoding='utf-8'))
    for path in (root / 'cheatsheets').glob('*.html'):
        parser = Tags()
        parser.feed(path.read_text(encoding='utf-8'))
        if parser.stack:
            raise ConfigError(f'Unclosed HTML tags in {path}')
        for destination in parser.links:
            local_link(root, path, destination)
    for path in [*root.glob('*.md'), *root.glob('docs/*.md')]:
        # Inline links used in this repository; fenced examples are not links.
        text = re.sub(r'(?ms)^```.*?^```[^\n]*$', '', path.read_text(encoding='utf-8'))
        for destination in re.findall(r'\[[^\]\n]*\]\(([^)\n]+)\)', text):
            local_link(root, path, destination.strip('<>'))
    for path in (root / 'tools').rglob('*.py'):
        ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    print('Inventory, active KDL pins, checksums, licenses, generated docs, local links, HTML and Python syntax passed.')
    if static:
        print('Static checks only; Zellij config/layout/theme validation was explicitly omitted.')
        return
    zellij = shutil.which('zellij')
    if not zellij:
        raise ConfigError('Zellij is required for full validation; use --static explicitly for static checks only')
    validate(root, zellij)
    with tempfile.TemporaryDirectory(prefix='zellij-theme-') as directory:
        file = Path(directory) / 'theme.kdl'
        file.write_text('theme "my-custom"\n' + (root / 'themes/example-custom.kdl.example').read_text(encoding='utf-8'), encoding='utf-8')
        result = subprocess.run([zellij, '--config', str(file), 'setup', '--check'],
                                capture_output=True, timeout=30)
        if result.returncode:
            raise ConfigError('The example custom theme failed to parse')
    print('Real Zellij config, every layout/swap pair and example theme validation passed.')
