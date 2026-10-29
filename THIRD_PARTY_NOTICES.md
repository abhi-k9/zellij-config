# Third-party components

This repository redistributes three MIT-licensed WebAssembly plugins. The exact
copyright and permission notices accompany the binaries and are also copied into
installed configurations. Current versions, hashes and source URLs are in
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

`zellij-forgot` is no longer bundled or referenced by the active config because
its pinned upstream version supplied no established redistribution license.
`Ctrl+o`, then `h` opens Zellij's built-in configuration/keybinding screen.

Zellij itself is installed separately from its official release. This repository
pins its artifact hashes and provides an optional verified downloader.
