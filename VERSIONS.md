# Selected versions

Generated from `versions.json`. Pins change only on an explicit update.

Zellij: **v0.45.1**. These pins select artifacts; CI records validation.

| Plugin | Tag | Release artifact | SHA-256 |
| --- | --- | --- | --- |
| zjstatus | v0.25.0 | https://github.com/dj95/zjstatus/releases/download/v0.25.0/zjstatus.wasm | `282ceab219e56e1908c9fac33907241fe6c3e1ef7d85faab3e5f438cef87b8fe` |
| monocle | v0.100.2 | https://github.com/imsnif/monocle/releases/download/v0.100.2/monocle.wasm | `4cb7e2cc912d975b4e755c93e44e7f0de62ef9240a09a89b735490cf4713792c` |
| multitask | v0.45.1 | https://github.com/leakec/multitask/releases/download/v0.45.1/multitask.wasm | `d2c6dadef431065efcc307cd573550031a9d11348ffde9d331f96136b7d60a9d` |

## Change versions when you choose

```sh
python3 tools/manage.py versions check
python3 tools/manage.py versions update --all
python3 tools/manage.py versions update --plugin zjstatus=latest
python3 tools/manage.py versions update --plugin zjstatus=v0.25.0
python3 tools/manage.py versions update --zellij latest
python3 tools/manage.py versions update --zellij v0.45.1
python3 tools/manage.py install-zellij --bin-dir ~/.local/bin
./check.sh
./launcher/zj attach --create main
```

On Windows use `python` instead of `python3` and `launcher/zj.cmd` to start.

Update checks never change files. Update downloads and verifies all selected artifacts
before changing pins, bundled bytes, license notices and generated references.
Review `git diff` and run the checks before committing. A direct checkout is the live
source configuration; new launcher sessions use its updated pins without setup.
A separately deployed copy needs setup again. The Zellij executable changes only
through the explicit install-zellij command (or your package manager).

If a new plugin release has no published GitHub digest, provide a trusted digest with
`--sha256 NAME=HEX`; the updater refuses to treat its own computed hash as independent
verification. Updates never select prereleases through `latest`.
