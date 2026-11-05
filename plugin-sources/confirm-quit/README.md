# Quit confirmation plugin

This bundled build adapts the quit-dialog pattern from
[qdelettre/zellij-confirm](https://github.com/qdelettre/zellij-confirm/tree/9d15b816523b92d98bcff0d921030ff26a044abf)
under its [MIT license](LICENSE). It is a local adaptation, not an upstream
release artifact. Source, dependencies and the toolchain are committed together.

The confirmation asks `Quit Zellij?`. Unmodified `y` performs Zellij's native
client Quit; `n` or `Esc` closes only the dialog. Enter does not confirm. Other
attached clients continue; quitting the last active client stops the session's
running programs. This plugin never invokes a shell or `kill-session`.

The alias configuration `display_style` accepts `popup` (default) or `status`.
Popup draws a centered question in a floating pane. Status moves that pane into
a borderless, pinned one-row overlay above the existing bottom bar, or at the
bottom of a barless workspace. It leaves tiled pane geometry and the original
bar intact and follows tab/pane geometry updates after a terminal resize.
Both styles use the same answer keys; this is one plugin with two render modes.

Both request `ChangeApplicationState`; status additionally requests
`ReadApplicationState` for positioning. Neither requests filesystem/network
access or executes host commands. Geometry subscriptions are established before
requesting permission so Zellij can deliver initial state on approval; key
subscription starts only after approval. The question must render before `y`
can confirm, so first-use permission approval never also confirms Quit.
Denial closes the plugin. Popup needs at least three content rows and 26 columns;
status needs one content row and 36 columns. Smaller panes refuse confirmation
while retaining `n`/`Esc` cancellation. Unknown styles also refuse confirmation.
See the [user configuration guide](../../docs/QUIT_CONFIRMATION.md#choose-a-display-style)
for CLI, JSON and direct KDL examples.

## Build and verify

Install Rust through the official Rust toolchain installer and Python 3.10+.
The checked-in `rust-toolchain.toml` selects Rust 1.95.0 and `wasm32-wasip1`.
From this directory, run:

```sh
python3 build.py
python3 build.py --check
```

On Windows use `python build.py`. The helper runs
`cargo build --locked --release --target wasm32-wasip1` with project and Cargo
cache paths normalized through `CARGO_ENCODED_RUSTFLAGS`, then prints the WASM's
SHA-256. It preserves proxy and CA settings. `Cargo.lock` pins registry sources
and checksums; `Cargo.toml` pins `zellij-tile` exactly to 0.45.1.
An explicit `--target-dir` keeps build output in this directory's `target/`
even when the environment or a global Cargo configuration selects another path.

Compare the hash with the bundled pin before replacing its binary. Source
changes require rebuilding and updating the pin together. Do not use an arbitrary
upstream `latest` artifact for this adapted plugin. A matching hash establishes
identity; it does not substitute for a real Zellij smoke test.
`--check` requires the rebuilt bytes to match any existing colocated
`confirm-quit.wasm` and the containing repository's `plugins/confirm-quit.wasm`.
It fails if no bundled copy is available or any comparison differs.
It also verifies the bundled MPL source archives against `Cargo.lock` and their
`mpl-sources/SHA256SUMS` inventory.

## Dependency notices and source availability

`THIRD_PARTY_LICENSES.txt` retains notices for the resolved non-development Cargo
dependency closure and the Rust standard library. These dependencies keep their
own license terms; the compiled binary is not described as MIT-only.
The SDK closure contains MPL-2.0 packages `colored` 3.1.1 and `option-ext` 0.2.0.
Their unmodified, checksum-verified source archives accompany this source tree in
`mpl-sources/`; its README supplies the versioned public source URLs as well.
Keep the combined notices and source availability information with redistributed
WASM copies. Source or lockfile updates require reviewing and refreshing these
notices and any required source offers along with the binary.

Before adopting a rebuild, test first-use permission grant, `n`, `Esc`, repeated
invocation, modified keys, Enter, narrow terminals and affirmative `y` in a
disposable session. Repeat both styles with compact-bar and zjstatus layouts,
terminal resizing and two attached clients. Cancelling must preserve all panes,
their geometry and the original bar; affirmative Quit must leave the other
client connected. Parser validation alone cannot establish these behaviors.
