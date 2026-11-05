# Terminal and plugin troubleshooting

These notes cover the selected Zellij 0.45.1 and the plugins listed in
[VERSIONS.md](../VERSIONS.md). Check the executable actually used by the launcher
before comparing results:

```sh
zj --version
fish --version
```

Use `zj.cmd --version` on native Windows; the Fish command applies only where you
use Fish. Record the terminal application and its version too. The manifest
does not replace an installed executable or override `ZJ_ZELLIJ_BIN`.

## Monocle payload error

The published Monocle `v0.100.2` WASM was built with `zellij-tile` 0.41.2.
With Zellij 0.45.1, mouse events can crash that artifact with:

```text
ERROR: <NO PAYLOAD>
PanicHookInfo
file: "src/main.rs"
line: 16
ERROR IN PLUGIN
```

That line is the plugin registration macro. In the reproduced case, the crash
comes from interpreting a newer mouse-event payload using the older plugin API;
it is not a missing file-search payload or a Windows path problem. The same
published artifact is used across platforms.

[Upstream PR #20](https://github.com/imsnif/monocle/pull/20) identifies this API
mismatch and updates the SDK and affected file-opening calls. This repository
ships a compatible source build using the exact Zellij 0.45.1 SDK and the two
required file-opening-call changes. Its refreshed dependency lock also avoids
the upstream lock's affected `crossbeam-channel` 0.5.14. The
[source and build instructions](../plugin-sources/monocle/README.md) identify the
upstream baseline and complete local changes; [VERSIONS.md](../VERSIONS.md)
records the selected artifact and hash. This is a repository build, not a newly
published upstream release.

Update the checkout, refresh any standalone installed helpers using your original
`--bin-dir`, and start a **fresh session** through `zj` / `zj.cmd`. Existing
sessions retain their old plugin locations. A separate deployed configuration
also needs setup again. No broad cache deletion is needed: the compatible build
has a different immutable artifact location.

Until the compatible build is active, keyboard-only Monocle use avoids the reproduced
mouse trigger: open it with `Ctrl+o`, then `m`, and keep the pointer outside the
popup. Disabling mouse support for the entire workspace changes unrelated pane
selection, scrolling and resizing behavior.

## RGB text at the Fish prompt

Text such as `11;rgb:2e2e/3434/4040` is a terminal background-color reply: OSC 11
reporting `#2e3440`. It should be consumed by the terminal-query handler, but can
reach the shell as input. This can happen in a fresh session without nesting.
Press **Ctrl+u** to clear the affected command line before typing a command.

This symptom matches the Zellij 0.45.1 startup-query ownership bug described in
[issue #5566](https://github.com/zellij-org/zellij/issues/5566). The upstream fix,
[PR #5655](https://github.com/zellij-org/zellij/pull/5655), merged after 0.45.1.
At this investigation, 0.45.1 was still the latest stable release. That release
does not contain the fix, so selecting "latest" alone did not resolve it. Check
the selected executable's version and release notes. See the
[maintainer's explanation](https://github.com/zellij-org/zellij/issues/5164#issuecomment-5818465567)
of startup replies mixing with forwarded pane queries.

The pinned client always sends its OSC 10/11 startup queries. Changing the theme,
OSC8 hyperlinks or Kitty keyboard/graphics settings does not reliably stop these
color replies. No shared configuration change is applied for this core bug.

An optional Fish startup delay has been reported upstream:

```fish
if set -q ZELLIJ
    sleep 0.15
end
```

This is a timing workaround, not a guarantee; it delays every affected Fish
startup. It is not installed by this repository. Prefer a stable Zellij release
that includes the fix. A deliberately selected development build should contain
commit `3e470a43dcdbe548d91429bf63d6a9488efdd7c5` and needs separate validation;
the helpers do not silently replace the pinned stable executable with one.

## Blank border after reattaching a nested session

Detaching an outer session keeps its panes running. If one pane contains an
attached inner Zellij client, that client remains connected even after you
attach to the inner session from a separate, larger terminal.

Zellij sizes a shared tab to the smallest client viewing that tab. For example,
a 40-row terminal can give its nested client only 37 rows. The later standalone
attachment still uses 37 rows while that smaller client is attached, leaving a
blank strip. A terminal resize alone cannot remove the smaller client's limit.
This is different from restoring a saved layout with only one attached client.

From the reattached inner session, inspect the attached clients:

```sh
zj action list-clients
```

From an ordinary terminal outside Zellij, name the target session explicitly:

```sh
zj --session inner action list-clients
```

Replace `inner` with your session name; use `zj.cmd` on native Windows.

In NORMAL mode, keep your current attachment and disconnect the others:

**From the reattached inner session: Ctrl+o → w → Ctrl+x → Esc.**

1. Press **Ctrl+o, then w** to open the built-in session manager.
2. Press **Ctrl+x** to disconnect other clients of the current session.
3. Press **Esc** to close the manager.

**Ctrl+x disconnects all other clients of this session.** Use it only when that
is intended; collaborators will also be detached. Their session programs keep
running. Alternatively, return to the outer session and detach only its inner
client. Do not kill or delete the parent session to clear the gap.

In the Linux PTY reproduction, the tab expanded immediately from 37×118 to
40×120 after the old client disconnected, and the parent server remained alive.
A genuine shutdown followed by one-client resurrection used the full size.
No permanent padding change to the shipped layouts was needed. See
[upstream issue #5624](https://github.com/zellij-org/zellij/issues/5624), the
[per-tab size calculation](https://github.com/zellij-org/zellij/blob/v0.45.1/zellij-server/src/screen.rs#L2387)
and the [session-manager shortcut](https://github.com/zellij-org/zellij/blob/v0.45.1/default-plugins/session-manager/src/main.rs#L655).

## Validation boundaries

On Linux, `python3 tools/smoke_plugin_compatibility.py` exercises the compatible
Monocle through the offline launcher, including mouse events and real search
results. CI runs this separately from parser and checksum checks.

The old Monocle mouse crash and nested-client geometry were reproduced with the
pinned binary in disposable Linux PTY sessions. Injecting an OSC 11 reply into
Fish reproduced the literal command-line text; that test does not reproduce the
timing of Zellij's startup race. Windows GUI input and terminal-specific timing
still need checks on the affected machine. Use the
[on-machine checklist](../cheatsheets/verification-checklist.html).
