# Zellij config

Configuration for **Zellij 0.45.1**, imported from
`28_zellij_audited_2026-10-14.zip`. Uses Catppuccin Mocha, three layouts with
matching swap layouts, and four pinned plugins.

## Get started

Install Zellij 0.45.1 first, then clone this repository:

```sh
git clone https://github.com/abhi-k9/zellij-config.git
cd zellij-config
./setup.sh --dry-run
./setup.sh --offline
zj attach --create main
```

On Linux and macOS, `setup.sh` backs up an existing configuration before copying
the config, layouts and theme template into Zellij's config directory. It also
installs the `zj` launcher. `--offline` uses the bundled plugins after verifying
their SHA-256 checksums; it downloads a plugin only if its bundled copy is missing
or fails verification. Run `./setup.sh` without `--offline` to load plugins from
their pinned release URLs instead.

For Windows installation, config discovery, recovery, and customization, see the
[full configuration guide](config/README.md). The [changelog](CHANGELOG.md)
preserves the archive's audit history.

## Layouts and references

- `config/config.kdl`: main settings and key bindings.
- `config/layouts/`: default, development and zjstatus layouts, each with a swap
  layout for changing pane arrangements.
- `config/themes/`: an optional custom theme template; Catppuccin is built in.
- `plugins/` and `plugins.sha256`: pinned WebAssembly plugins and checksums.
- `launcher/`: the `zj` launcher for Linux, macOS and Windows; checks monthly for
  plugin updates without changing pins.
- `cheatsheets/`: HTML references and a checklist for terminal behavior.

## Validate changes

```sh
./check.sh
git config core.hooksPath hooks
```

`check.sh` checks consistency and bundled plugin hashes. With Zellij on `PATH`,
it also parses the config, layouts and example theme and checks documented
shortcuts. The optional pre-commit hook checks staged files. GitHub Actions runs
the supplied Linux, macOS and Windows checks.

Clipboard, rendering, mouse input and session recovery still need verification
in your own terminal; use [the checklist](cheatsheets/verification-checklist.html).

## Restore

```sh
./setup.sh --restore
```

Restores the most recent configuration backup and backs up the current config
first. See the full guide for launcher removal and Windows recovery.
