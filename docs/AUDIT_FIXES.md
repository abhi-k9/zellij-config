# Audit resolution and regression map

The 2026-10-22 audit reviewed revision `a7df238`. The fixes replace duplicated
shell/PowerShell policy with one Python 3.10+ standard-library implementation.
Shell and Windows entry points delegate literal arguments to that shared code.
The Zellij configuration itself remains usable independently of Python.

The 2026-10-23 direct-clone change places `config.kdl`, layouts and themes at the
repository root. The checked-in launcher prefers verified downloads and only
uses bundled plugins when a download is unavailable. It stores private runtime
snapshots outside the checkout; plain Zellij continues to use HTTPS aliases.

## Priority 1: user data and publication safety

| Audit ID | Resolution | Executable regression |
| --- | --- | --- |
| I1 | Replace managed symlinks in a staged tree; never write through external targets; preserve the old tree for restore | `test_file_symlink_never_overwrites_dotfiles`, `test_directory_and_nested_file_symlinks` |
| I2 | Verify all files and parse the complete staged config before publication; rollback publication failure | `test_bad_plugin_does_not_mutate_active_config`, `test_missing_pin_metadata_does_not_mutate`, `test_publication_failure_rolls_back` |
| I3 | Serialize KDL paths with escaped quotes/backslashes; validation failure is fatal | `test_quote_space_and_backslash_paths`, `test_actual_config_and_unusual_path_install` |
| I4 | Hash raw bytes with hashlib; no filename escape markers or external tool fallbacks | `test_quote_space_and_backslash_paths`, `test_hash_read_failure_is_not_success` |
| I5 | Normalize the physical target before deriving sibling staging/snapshot paths | `test_trailing_slash_reinstall` |
| I6 | Private unique staging and exclusive temporary files; atomic file replacement never opens an old destination link | `test_no_preexisting_temporary_symlink_is_written` |
| I7 | Private POSIX snapshot roots; restrictive user/SYSTEM ACLs on new Windows staging/snapshot directories | `test_backup_root_is_private` |
| I8 | Dry runs create no state; cleanup only owned staging resources | `test_dry_run_creates_nothing`, `test_interrupted_preparation_preserves_unrelated_parts` |
| I9 | OS file lock excludes simultaneous installers; unique backup roots and recovery journal | `test_exclusive_lock_and_os_release`, `test_recover_kill_between_renames` |
| I10 | Restore publishes an exact staged snapshot rather than deleting a partial glob | `test_install_restore_and_double_dot_cleanup` |
| I11 | Numeric snapshot metadata and numeric legacy suffix ordering | `test_legacy_snapshot_numeric_suffix` |

## Priority 2: validation and platform integrity

| Audit ID | Resolution | Verification |
| --- | --- | --- |
| C1 | Explicit Bash shell enables pipefail in every CI shell step; no piped installer assertions | actionlint plus the workflow's native jobs |
| C2 | Read/hash errors are fatal, including failures after a hash implementation was selected | `test_hash_read_failure_is_not_success` |
| C3 | Staged hook invokes the required checker with `sh`, without an executable-bit bypass; raw errors retained | native hook regression tests |
| C4 | Explicit required inventory rejects a missing individual sheet or helper | `test_missing_sheet_is_failure` |
| W1 | Windows setup uses the same validated stage and transaction as Unix; unsafe manual snippet removed | shared installer regressions and native PowerShell entry-point test |
| W2 | Shared Python URL/tag comparisons preserve case | `test_case_distinct_tags_are_distinct` |

## Priority 3: update notices and packaging

| Audit ID | Resolution | Verification |
| --- | --- | --- |
| P1 | Track completeness independently from available updates; incomplete scans retry after one day | `test_partial_failure_retries_next_day_while_showing_updates` |
| P2 | Resolve CLI file/directory selectors and environment precedence | `test_cli_config_precedence_and_literal_paths` |
| P3 | KDL-aware active-node reader handles block comments, slashdash and strings | `test_comments_raw_strings_and_slashdash`, `test_dead_comments_are_never_requested` |
| P4 | Cache keys include canonical file and pinset | `test_cache_is_per_config_and_pinset` |
| P5 | Bounded HTTPS GitHub API requests follow repository redirects; no first-redirect tag scraping | `test_https_downgrade_redirect_refused` plus mocked release responses |
| P6 | Report a different latest release without claiming version ordering | `test_no_newer_claim_when_latest_is_older` |
| L1 | Include exact MIT copyright/permission notices and copy them during installation | repository check and `test_license_inventory_is_required` |
| L2 | Remove the unlicensed popup binary/alias and use the built-in configuration screen | exact plugin inventory and real Zellij parsing |

## Additional improvements and upgrade control

`versions.json` is the canonical artifact inventory. The explicit updater stages
verified plugin bytes and exact upstream notices, synchronizes config pins and
generated references, and rolls back ordinary write failures. Download size,
connection and total-duration bounds apply; HTTPS downgrade redirects are denied.
The launcher can check local installed plugins using retained upstream metadata.

CI runs real pinned Zellij on Linux, macOS and Windows with Python 3.10 and 3.14.
Ordinary tests use deterministic network fixtures. Live latest-release requests
are a separate optional manual smoke job. CI has timeouts and cancellation of
superseded runs, pinned action commits, locked npm dependencies, hash-locked Ruff
wheels, verified actionlint, root README lint and HTML validation.
Local Markdown/HTML file links are checked without network access. Restore also
checks snapshot plugin hashes and works when the current source pins are damaged.
Upgrade regressions cover write rollback, edits during downloads and changed
license terms. Physical path normalization covers macOS temporary-directory
aliases, Windows short paths and configs reached through directory symlinks.

## Boundaries

Publication uses reversible directory renames with a short name gap and an
interruption recovery journal; it is not a filesystem-level atomic exchange or
a power-loss durability guarantee. External snapshot symlinks remain references
to their targets, which this installer never overwrites. Concurrent user edits
are not serialized by the installer lock.

Native Windows/macOS results come from the hosted CI for this change; local
development tests run in isolated Linux environments. Clipboard, terminal fonts,
mouse behavior, permission prompts and crash/reboot recovery require native
interactive checks. Parser success alone does not establish those behaviors.

Automatic bundled fallback requires the checked-in `zj` launcher. The pinned
[native loader](https://github.com/zellij-org/zellij/blob/v0.45.1/zellij-server/src/plugins/wasm_bridge.rs)
does not provide an HTTPS-to-bundled-file fallback. Launcher sessions use an
immutable startup config snapshot: source edits apply to a new session rather
than being watched live. Downloaded plugin caches are reused only after hash
verification; offline fallback never masquerades as a successful cached download.
