# Monocle compatibility build

This repository build retains Monocle's file/content search behavior while
matching its plugin SDK to the selected Zellij host. The original source is
[Monocle v0.100.2](https://github.com/imsnif/monocle/tree/ec980abab220a1ec0a4434b283ea160838219321),
with its [MIT notice](LICENSE.md) preserved. The upstream tag still declares
Cargo package version 0.100.1; this build does not invent an upstream release.

The upstream WASM uses zellij-tile 0.41.2. Newer Zellij mouse-hover events fail
to deserialize in that SDK and panic at `register_plugin!(State)`. The local
source changes are recorded in [UPSTREAM_CHANGES.patch](UPSTREAM_CHANGES.patch):
exact zellij-tile 0.45.1, plus two semicolons where updated SDK functions now
return a pane ID. The refreshed Cargo lock also avoids the upstream lock's
known-affected crossbeam-channel 0.5.14 (RUSTSEC-2025-0024).

The [original README](README.upstream.md) and [development layout](dev.kdl) are
retained as upstream reference material. Use the instructions below for the
selected toolchain.

## Build and verify

Install Rust with its official toolchain installer and Python 3.10+. This
project selects Rust 1.95.0 and wasm32-wasip1 through rust-toolchain.toml.
Run from this directory:

```sh
python3 build.py
python3 build.py --check
```

Use `python` on Windows. The helper fixes Cargo's output directory explicitly,
normalizes source/cache paths for the compiled output, and uses Cargo.lock.
Check mode verifies the bundled MPL source archives against Cargo.lock and
compares the rebuilt WASM with the colocated and repository plugin copies.

The plugin source is MIT licensed; dependency code retains its own terms.
[THIRD_PARTY_LICENSES.txt](THIRD_PARTY_LICENSES.txt) includes the complete
dependency notices and source availability details. Unmodified MPL source
archives are retained in [mpl-sources](mpl-sources/README.md).

## Behavioral validation

Parser success does not test plugin compatibility. In a disposable session,
launch the built WASM, approve its existing permissions, search a known file
name and a marker in its contents, then inject or exercise mouse hover, click
and scroll events in the floating pane. The search UI must remain usable and
never show `ERROR IN PLUGIN`. Repeat with the actual launcher after updating
the managed artifact pin. Native Windows mouse input still needs an on-machine
check; a Linux PTY test does not establish Windows terminal behavior.
