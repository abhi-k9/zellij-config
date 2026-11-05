# Quit confirmation

Press **Ctrl+o, then q** to display **Quit Zellij?**:

- `y` confirms.
- `n` or `Esc` cancels.
- Enter and modified `y` keys do not confirm.

Both display styles work with the compact bar or zjstatus and with pane frames
disabled. Each invocation creates a fresh confirmation; it cannot remember a
previous affirmative answer. Confirmation stays disabled until the question and
answer keys can be displayed. Enlarge a terminal that is too small, or cancel.

## Choose a display style

The default is `popup` in the shared KDL and both preference presets. Choose
`status` for a borderless, single-line question immediately **above** the existing
status bar. The line temporarily overlays the bottom row of the workspace; it
does not replace the bar, resize tiled panes or stop their processes. Cancelling
reveals the underlying row. Without a bottom bar, it uses the last workspace row.
The focused confirmation receives keys until it is answered or cancelled.

From the full checkout, save a local preference:

```sh
python3 tools/manage.py configure --config-dir . --quit-confirmation status
./launcher/zj --config-dir . -s confirmation-demo -n minimal
```

Use `--quit-confirmation popup` to switch back, or `--dry-run` to preview. On
Windows, use `python` and `.\launcher\zj.cmd`. The saved JSON field is
`"quit_confirmation": "status"`. As with other
[local preferences](GENERALIZATION.md#save-choices-outside-shared-kdl), `zj`
applies it to new sessions; reattachment keeps the existing snapshot and plain
`zellij` ignores the JSON. Refresh separately installed helpers before using a
new preference option.

For plain Zellij or a manually maintained config, change this child option inside
the existing `confirm-quit` alias in [config.kdl](../config.kdl), preserving its
pinned `location`:

```kdl
display_style "status" // "popup" is the default when omitted
```

Local JSON overrides this alias option when using `zj`.
An invalid `display_style` cannot confirm Quit and displays a cancellation hint.

| Style | Space needed to confirm | Permissions |
| --- | --- | --- |
| `popup` | At least 26 columns and 3 content rows | `ChangeApplicationState` |
| `status` | At least 36 columns and 1 content row | `ChangeApplicationState`, `ReadApplicationState` |

`ChangeApplicationState` lets the plugin invoke native Quit and position its own
line. Status style additionally reads tab/pane geometry to follow terminal
resizes and stay above the bar. Neither style runs host commands or requests
filesystem or network access.

On first use, Zellij presents its own permission prompt, which can still be a
popup when status style is selected. Approving permission does not answer the
quit question. Wait for **Quit Zellij?**, then answer separately. Denying
permission closes the confirmation without quitting. A newly required permission
can prompt again when switching styles.

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
`versions update --all` leaves it and the bundled Monocle build unchanged while
updating the two upstream release plugins and core pins. An explicit
version-update request for a bundled build is rejected; its source and build
must be reviewed together. Monocle has its own
[build instructions](../plugin-sources/monocle/README.md).

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

Before adopting a changed build, use disposable sessions to check both styles,
cancel, affirmative Quit, first-use permission approval and denial, repeated
invocations, terminal resizing, a small pane, both status bars and two connected
clients. Cancellation must preserve the original bar and tiled pane geometry. The
[on-machine checklist](../cheatsheets/verification-checklist.html#item-13)
describes the confirmation checks. Parser success alone does not establish these
interactive behaviors.
