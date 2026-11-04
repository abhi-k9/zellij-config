# Third-party components

This repository redistributes three upstream MIT-licensed WebAssembly plugins
and a repository-built quit dialog. The dialog's own source is an MIT-licensed
adaptation; its SDK and other dependencies retain their separate license terms.
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
| monocle | <https://github.com/imsnif/monocle> | [MIT notice](licenses/monocle.txt) |
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

`zellij-forgot` is no longer bundled or referenced by the active config because
its pinned upstream version supplied no established redistribution license.
`Ctrl+o`, then `h` opens Zellij's built-in configuration/keybinding screen.

Zellij itself is installed separately from its official release. This repository
pins its artifact hashes and provides an optional verified downloader.
