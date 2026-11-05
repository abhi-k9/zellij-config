# Third-party components

This repository redistributes the upstream `zjstatus` and `multitask` releases,
plus repository builds of Monocle and a quit dialog. Their own sources are MIT
licensed; the source builds' SDK and other dependencies retain their separate
license terms.
The exact copyright and permission notices accompany the binaries and are also
copied into installed configurations. Current versions, hashes and source URLs are in
[VERSIONS.md](VERSIONS.md) and [versions.json](versions.json).

Normal setup deployment writes these notices to `third-party-licenses/` beside
the deployed config. Launcher-only installation copies helper code and pin
metadata; it does not deploy plugin binaries or their notices. A direct checkout
keeps the original notices in `licenses/`. Keep those files with redistributed
plugin copies.

| Component | Upstream | Verbatim notice |
| --- | --- | --- |
| zjstatus | <https://github.com/dj95/zjstatus> | [MIT notice](licenses/zjstatus.txt) |
| monocle | Compatibility build from [imsnif/monocle at ec980aba](https://github.com/imsnif/monocle/tree/ec980abab220a1ec0a4434b283ea160838219321) | [Original MIT and dependency notices](licenses/monocle.txt) |
| multitask | <https://github.com/leakec/multitask> | [MIT notice](licenses/multitask.txt) |
| confirm-quit | Adapted from [qdelettre/zellij-confirm at 9d15b816](https://github.com/qdelettre/zellij-confirm/tree/9d15b816523b92d98bcff0d921030ff26a044abf) | [Original MIT and dependency notices](licenses/confirm-quit.txt) |

The adapted dialog's source, locked dependencies, pinned Rust toolchain and build
instructions are in [plugin-sources/confirm-quit](plugin-sources/confirm-quit/README.md).
The original upstream MIT notice is preserved. The
[full dependency notices](plugin-sources/confirm-quit/THIRD_PARTY_LICENSES.txt)
are also included in `licenses/confirm-quit.txt`, so normal setup deploys the
complete notice with the binary. Corresponding source archives for the MPL-2.0
dependencies `colored` and `option-ext` accompany the build; see the
[MPL source record](plugin-sources/confirm-quit/mpl-sources/README.md).
Its reviewed build is pinned to an immutable artifact commit; it is not updated
through an upstream release query. See the [rebuild guide](docs/QUIT_CONFIRMATION.md#rebuild-and-publish-the-dialog).

Monocle's [compatibility source build](plugin-sources/monocle/README.md) preserves
the original MIT notice and records the exact SDK changes and dependency lock.
Its [dependency notices](plugin-sources/monocle/THIRD_PARTY_LICENSES.txt) are
included in `licenses/monocle.txt`, and its corresponding MPL sources are
recorded in [mpl-sources](plugin-sources/monocle/mpl-sources/README.md). Setup
copies this complete combined notice alongside the plugin too. The source build
is pinned to an immutable artifact commit and is not an upstream release.

`zellij-forgot` is no longer bundled or referenced by the active config because
its pinned upstream version supplied no established redistribution license.
`Ctrl+o`, then `h` opens Zellij's built-in configuration/keybinding screen.

Zellij itself is installed separately from its official release. This repository
pins its artifact hashes and provides an optional verified downloader.
