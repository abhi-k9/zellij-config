#!/usr/bin/env python3
"""Build the locked WASM with source/cache paths normalized before hashing."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--check', action='store_true',
                    help='Require rebuilt bytes to match existing bundled copies')
options = parser.parse_args()
if options.check:
    # Only the package blocks/quoted scalar fields needed for archive identity;
    # keep the helper usable with Python 3.10 (which has no tomllib).
    checksums = {}
    for block in re.split(r'(?m)^\[\[package\]\]$', (root / 'Cargo.lock').read_text()):
        fields = dict(re.findall(r'(?m)^(name|version|checksum) = "([^"\n]+)"$', block))
        if all(name in fields for name in ('name', 'version', 'checksum')):
            checksums[fields['name'] + '-' + fields['version'] + '.crate'] = fields['checksum']
    manifest = root / 'mpl-sources/SHA256SUMS'
    expected = {}
    for line in manifest.read_text().splitlines():
        digest, name = line.split()
        expected[name] = digest
    archives = {path.name: path for path in (root / 'mpl-sources').glob('*.crate')}
    if set(archives) != set(expected):
        raise SystemExit('MPL source archive inventory differs from SHA256SUMS')
    for name, path in archives.items():
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != expected[name] or digest != checksums.get(name):
            raise SystemExit(f'MPL source archive does not match Cargo.lock: {name}')
cargo_home = Path(os.environ.get('CARGO_HOME', Path.home() / '.cargo')).resolve()
environment = os.environ.copy()
# The encoded form preserves paths containing spaces without shell parsing.
environment['CARGO_ENCODED_RUSTFLAGS'] = '\x1f'.join([
    f'--remap-path-prefix={root}=/src',
    f'--remap-path-prefix={cargo_home}=/cargo',
])
subprocess.run(['cargo', 'build', '--locked', '--release', '--target', 'wasm32-wasip1',
                '--target-dir', str(root / 'target')],
               cwd=root, env=environment, check=True)
artifact = root / 'target/wasm32-wasip1/release/monocle.wasm'
data = artifact.read_bytes()
print(hashlib.sha256(data).hexdigest() + '  ' + str(artifact))
if options.check:
    bundled = []
    if (root / 'monocle.wasm').is_file():
        bundled.append(root / 'monocle.wasm')
    for directory in root.parents:
        if (directory / 'versions.json').is_file():
            deployed = directory / 'plugins/monocle.wasm'
            if deployed.is_file():
                bundled.append(deployed)
            break
    if not bundled:
        raise SystemExit('No bundled monocle.wasm found to compare with the rebuild')
    for copy in bundled:
        if copy.read_bytes() != data:
            raise SystemExit(f'Rebuilt WASM differs from {copy}; review source and pin updates')
        print(f'Rebuild matches {copy}')
