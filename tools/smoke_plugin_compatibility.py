#!/usr/bin/env python3
"""Exercise Monocle's real mouse-event ABI through an isolated Linux zj session."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import select
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time

from zjconfig.common import load_versions, zellij_executable
from zjconfig.plugin_files import verified


ROOT = Path(__file__).resolve().parents[1]
ANSI = re.compile(r'\x1b\][^\x07]*?(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]')


class SmokeSession:
    def __init__(self, directory: Path, executable: str):
        # These imports are Linux-only; importing this helper remains harmless
        # on the other platforms covered by ordinary regression tests.
        import fcntl
        import pty
        import termios

        self.executable = executable
        self.name = 'abi-' + directory.name
        self.directory = directory
        self.log = bytearray()
        self.fd = None
        self.pid = None
        self.deadline = time.monotonic() + 35
        self.environment = dict(os.environ)
        for name in ['ZELLIJ', 'ZELLIJ_SESSION_NAME', 'ZELLIJ_PANE_ID',
                     'ZELLIJ_CONFIG_FILE', 'ZELLIJ_CONFIG_DIR', 'ENV', 'BASH_ENV']:
            self.environment.pop(name, None)
        for name in ['XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME',
                     'XDG_STATE_HOME', 'XDG_RUNTIME_DIR', 'ZJ_STATE_DIR', 'ZELLIJ_SOCKET_DIR']:
            path = directory / name.lower()
            path.mkdir(mode=0o700)
            self.environment[name] = str(path)
        self.environment.update(TERM='xterm-256color', COLORTERM='truecolor',
                                SHELL='/bin/sh', ZJ_OFFLINE='1', ZJ_NO_UPDATE_CHECK='1',
                                ZJ_ZELLIJ_BIN=executable, ZJ_PYTHON=sys.executable)
        config = directory / 'configuration'
        config.mkdir()
        for name in ['layouts', 'themes', 'plugins']:
            shutil.copytree(ROOT / name, config / name)
        shutil.copy2(ROOT / 'versions.json', config / 'versions.json')
        (config / 'config.kdl').write_text(
            (ROOT / 'config.kdl').read_text(encoding='utf-8').replace(
                'show_release_notes true', 'show_release_notes false'), encoding='utf-8')
        self.project = directory / 'project'
        self.project.mkdir()
        (self.project / 'fixture-search.txt').write_text(
            'needle-content-xyzw nottyped-suffix-98765\n', encoding='utf-8')
        self.pid, self.fd = pty.fork()
        if self.pid == 0:
            os.chdir(self.project)
            fcntl.ioctl(0, termios.TIOCSWINSZ, struct.pack('HHHH', 40, 150, 0, 0))
            launcher = str(ROOT / 'launcher/zj')
            os.execve(launcher, [launcher, '--config-dir', str(config),
                                '-s', self.name, '-n', 'minimal'], self.environment)
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack('HHHH', 40, 150, 0, 0))

    def drain(self, duration=0.05):
        end = time.monotonic() + duration
        while self.fd is not None and time.monotonic() < end:
            ready, _, _ = select.select([self.fd], [], [], max(0, end - time.monotonic()))
            if not ready:
                continue
            try:
                data = os.read(self.fd, 65536)
            except OSError:
                data = b''
            if not data:
                os.close(self.fd)
                self.fd = None
                break
            self.log.extend(data)
            if b'\x1b[6n' in data:
                os.write(self.fd, b'\x1b[1;1R')

    def text(self, start=0):
        return ANSI.sub('', bytes(self.log[start:]).decode(errors='replace'))

    def wait(self, condition, message):
        while time.monotonic() < self.deadline:
            self.drain()
            if 'ERROR IN PLUGIN' in self.text():
                raise RuntimeError('Monocle crashed while handling native input')
            if self.fd is None:
                raise RuntimeError('The smoke-test client exited unexpectedly')
            if condition():
                return
        raise RuntimeError(message)

    def key(self, value):
        os.write(self.fd, value)
        self.drain()

    def cli(self, *arguments, check=True):
        process = subprocess.Popen([self.executable, '--session', self.name, *arguments],
                                   env=self.environment, cwd=self.project,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        end = time.monotonic() + 5
        while True:
            try:
                output, error = process.communicate(timeout=0.05)
                break
            except subprocess.TimeoutExpired:
                self.drain()
                if time.monotonic() >= end:
                    process.kill()
                    process.communicate()
                    raise RuntimeError('Zellij CLI timed out: ' + ' '.join(arguments))
        if check and process.returncode:
            raise RuntimeError(error or output)
        return process.returncode, output

    def run(self):
        def ready():
            code, output = self.cli('action', 'list-panes', '--json', check=False)
            return not code and any(not pane['is_plugin'] for pane in json.loads(output))
        self.wait(ready, 'The isolated Zellij session did not start')
        self.key(b'\x0f')
        self.key(b'm')
        self.wait(lambda: 'OpenFiles' in self.text() or 'Allow?' in self.text(),
                  'Monocle did not request its first-use permissions')
        self.key(b'y')
        self.wait(lambda: 'SEARCH:' in self.text() or 'FILE NAMES AND CONTENTS' in self.text(),
                  'Monocle search UI did not appear')
        for x in [50, 60, 70, 80, 90]:
            self.key(f'\x1b[<35;{x};17M'.encode())
        for event in [b'\x1b[<0;70;18M', b'\x1b[<0;70;18m',
                      b'\x1b[<64;70;18M', b'\x1b[<65;70;18M']:
            self.key(event)
        start = len(self.log)
        self.key(b'fixture-search')
        self.wait(lambda: 'fixture-search.txt' in self.text(start), 'Filename search returned no fixture')
        start = len(self.log)
        self.key(b'\x1b')  # Clear the query without hiding the plugin.
        # Observe the repaint before another key: otherwise ESC followed too
        # quickly by the next query's n can be decoded as the Alt+n shortcut.
        self.wait(lambda: re.search(r'SEARCH: {2,}', self.text(start)),
                  'Escape did not clear the filename query')
        start = len(self.log)
        self.key(b'needle-content-xyzw')
        self.wait(lambda: 'nottyped-suffix-98765' in self.text(start),
                  'Content search did not render the non-query fixture suffix')
        start = len(self.log)
        self.key(b'\x1b')
        self.wait(lambda: re.search(r'SEARCH: {2,}', self.text(start)),
                  'Escape did not clear the content query')
        self.key(b'\x1b')
        self.wait(lambda: ready(), 'The terminal session did not survive plugin dismissal')

    def close(self):
        # Name and socket directory belong only to this helper's private session.
        try:
            self.cli('kill-session', self.name, check=False)
        finally:
            if self.pid is not None:
                pid, _ = os.waitpid(self.pid, os.WNOHANG)
                if not pid:
                    try:
                        os.kill(self.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    os.waitpid(self.pid, 0)
            if self.fd is not None:
                os.close(self.fd)
                self.fd = None


def main():
    if not sys.platform.startswith('linux'):
        raise SystemExit('This real PTY smoke helper requires Linux; use native terminal checks elsewhere.')
    executable = str(Path(zellij_executable()).resolve())
    pin = next(pin for pin in load_versions(ROOT)['plugins'] if pin['name'] == 'monocle')
    verified((ROOT / 'plugins' / pin['asset']).read_bytes(), pin)
    # Keep Unix socket paths comfortably below sockaddr_un's pathname limit.
    with tempfile.TemporaryDirectory(prefix='zj-abi-', dir='/tmp') as directory:
        session = SmokeSession(Path(directory), executable)
        try:
            session.run()
            print('Monocle native ABI smoke passed: permission, mouse events, filename/content search and dismissal.')
        except Exception:
            print(session.text()[-12000:], file=sys.stderr)
            raise
        finally:
            session.close()


if __name__ == '__main__':
    main()
