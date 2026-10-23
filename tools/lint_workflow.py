#!/usr/bin/env python3
"""Run the pinned official actionlint artifact; never extract arbitrary paths."""
import hashlib
import io
from pathlib import Path
import subprocess
import tarfile
import tempfile

from zjconfig.common import ConfigError, fetch_bytes, read_json


def main():
    root = Path(__file__).resolve().parents[1]
    pin = read_json(root / 'ci-tools.json')['actionlint']
    archive = fetch_bytes(pin['url'], 32 * 1024 * 1024)
    if hashlib.sha256(archive).hexdigest() != pin['sha256']:
        raise ConfigError('actionlint archive checksum mismatch')
    with tempfile.TemporaryDirectory(prefix='zj-actionlint-') as directory:
        binary = Path(directory) / 'actionlint'
        with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as bundle:
            member = bundle.getmember('actionlint')
            if not member.isfile() or member.size > 32 * 1024 * 1024:
                raise ConfigError('Invalid actionlint archive member')
            binary.write_bytes(bundle.extractfile(member).read())
        binary.chmod(0o700)
        return subprocess.call([str(binary)], cwd=root)


if __name__ == '__main__':
    raise SystemExit(main())
