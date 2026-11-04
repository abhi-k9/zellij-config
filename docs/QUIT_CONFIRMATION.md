# Quit confirmation

Press **Ctrl+o, then q** to open a floating **Quit Zellij?** dialog:

- `y` confirms.
- `n` or `Esc` cancels.
- Enter and modified `y` keys do not confirm.

The question is drawn inside the pane, so it remains visible with the compact
bar or zjstatus and with pane frames disabled. It needs at least 26 columns and
3 rows; below that size, enlarge the pane or cancel. Confirmation stays disabled
until the question can be displayed. Each invocation creates a fresh dialog.

On first use, Zellij asks for `ChangeApplicationState`. That permission lets the
plugin invoke native Quit; approving it does not answer the quit question. Wait
for **Quit Zellij?**, then answer separately. The dialog runs no host commands
and requests no filesystem, network or application-state-reading permission.

## What quitting means

Confirmation performs Zellij's native **client Quit**. Your connected client
closes. If it was the last active client, the session ends and its programs stop.
If another client is still connected, it and the running session remain alive.
This is different from `kill-session`, which terminates the whole session.

Use **Ctrl+o, then d** to detach when you want your workspace to keep running.
Save work before confirming Quit. The dialog guards the configured quit binding;
it does not intercept shell exit, closing panes/tabs, group close, CLI kill
commands or custom bindings that invoke Quit directly.

Create a fresh session after updating the configuration. Reattaching to an old
session retains its startup bindings. Refresh separately installed launcher
helpers and redeploy separate config copies as described in the
[main guide](../README.md#choose-when-to-upgrade).

Zellij periodically saves floating plugins as part of a session layout. If it
saves while the question is open, a resurrected session can reopen the dialog;
it never quits automatically, and `n` / `Esc` dismisses it. Cancelling or quitting
does not guarantee that a newer layout has been saved before the next periodic
serialization.

## Artifact and source

`confirm-quit` is adapted from
[qdelettre/zellij-confirm at 9d15b816523b92d98bcff0d921030ff26a044abf](https://github.com/qdelettre/zellij-confirm/tree/9d15b816523b92d98bcff0d921030ff26a044abf),
with the original MIT notice preserved. Its auditable source and build inputs
live in [plugin-sources/confirm-quit](../plugin-sources/confirm-quit/README.md).
It uses the exact `zellij-tile` 0.45.1 SDK, locked Cargo dependencies, Rust 1.95.0
and the `wasm32-wasip1` target. Rust is needed only for rebuilding, not for use.

The dialog's own source is MIT-licensed; its dependencies retain their separate
terms. The build includes [full dependency notices](../plugin-sources/confirm-quit/THIRD_PARTY_LICENSES.txt)
and corresponding source archives for the MPL-2.0 dependencies `colored` and
`option-ext`, documented in the [MPL source record](../plugin-sources/confirm-quit/mpl-sources/README.md).
The original MIT and dependency notices are combined in
[licenses/confirm-quit.txt](../licenses/confirm-quit.txt) for redistribution and
normal setup deployment.

The inventory entry in [versions.json](../versions.json) has `source: "bundled"`,
an immutable artifact commit/path and a SHA-256. `zj` and setup always verify and
use the bundled bytes without downloading this plugin or running an external
command. Missing or corrupt bytes fail instead of silently selecting a different
build. Plain Zellij uses the commit-pinned HTTPS alias and its native download
cache; automatic checksum verification and bundled fallback are launcher
features.

`versions check` skips upstream release queries for this entry, and
`versions update --all` leaves it unchanged while updating the three upstream
release plugins and core pins. An explicit version-update request for the bundled
dialog is rejected; its source and build must be reviewed together.

## Rebuild and publish the dialog

Follow the [source build instructions](../plugin-sources/confirm-quit/README.md)
for toolchain installation. From the repository root, verify the committed build:

```sh
python3 plugin-sources/confirm-quit/build.py --check
```

Use `python` instead of `python3` on Windows. Check mode rebuilds from the pinned
inputs and compares the result with the committed artifact; it does not prove
interactive behavior or approve changes to the source. A deliberate source
change needs a reviewed rebuild and a two-step publication:

1. Review the source and dependency changes. Build the WASM using the pinned
   toolchain, retain the original license, complete dependency notices and
   required source archives, and commit them with the source and colocated
   `confirm-quit.wasm` artifact under `plugin-sources/confirm-quit/`.
2. Copy those same bytes to `plugins/confirm-quit.wasm`. Update the inventory's
   source commit, artifact path and SHA-256 to reference that first immutable
   commit. Keep the root alias, notices, generated version guide and checksum
   reference synchronized, including the complete deployment notice, then commit
   the integration changes. Push the integration head once to publish both
   commits together.

The separate artifact commit avoids a commit referring to its own unknown SHA.
Do not use a mutable branch URL for the plugin alias. Check the rebuilt bytes
against both committed copies, run `./check.sh`, and review the resulting diff.

Before adopting a changed build, use disposable sessions to check cancel,
affirmative Quit, first-use permission approval, repeated invocations, a small
pane, both status bars and two connected clients. The
[on-machine checklist](../cheatsheets/verification-checklist.html#item-13)
describes the confirmation checks. Parser success alone does not establish these
interactive behaviors.
