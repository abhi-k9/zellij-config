"""Prefer verified downloads; bundled WASM files are an offline fallback."""
from __future__ import annotations

import hashlib
from pathlib import Path

from .common import ConfigError, fetch_bytes, plugin_url


def verified(data: bytes, pin: dict) -> bytes:
    """Check trusted pinned bytes and the WASM header, not plugin safety/behavior."""
    if hashlib.sha256(data).hexdigest() != pin['sha256']:
        raise ConfigError(f'Plugin checksum mismatch: {pin["name"]}')
    if not data.startswith(b'\0asm\x01\0\0\0'):
        raise ConfigError(f'Not a WebAssembly v1 plugin: {pin["asset"]}')
    return data


def acquire(pin: dict, bundled: Path, *, offline=False) -> tuple[bytes, str]:
    """Try a verified download, then the verified bundle; offline skips fetching."""
    error = None
    if not offline:
        try:
            data = fetch_bytes(plugin_url(pin), timeout=3, budget=8, attempts=1)
            return verified(data, pin), 'download'
        except (ConfigError, OSError, ValueError) as failure:
            error = failure
    try:
        return verified(bundled.read_bytes(), pin), 'bundle'
    except (ConfigError, OSError) as failure:
        reason = f'Download unavailable ({error}); ' if error else 'Offline mode; '
        raise ConfigError(reason + f'no valid bundled fallback for {pin["name"]}: {failure}') from failure
