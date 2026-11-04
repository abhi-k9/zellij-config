# Unmodified MPL 2.0 dependency sources

These original crates.io source archives accompany the adapted quit plugin.
They contain the complete unmodified package sources and MPL 2.0 license texts.
Their hashes match the package checksums in the plugin's `Cargo.lock` and the
adjacent `SHA256SUMS`; `python3 ../build.py --check` verifies both identities.

| Package | Source archive | SHA-256 |
| --- | --- | --- |
| colored 3.1.1 | https://static.crates.io/crates/colored/colored-3.1.1.crate | `faf9468729b8cbcea668e36183cb69d317348c2e08e994829fb56ebfdfbaac34` |
| option-ext 0.2.0 | https://static.crates.io/crates/option-ext/option-ext-0.2.0.crate | `04744f49eae99ab78e0d5c0b603ab218f515ea8cfe5a456d7629ad883a3b6e7d` |

Extract a `.crate` archive with a gzip/tar reader. These files are source offers
for the MPL-covered dependencies, not alternative plugin binaries. The plugin's
own source remains under its accompanying MIT license. Preserve the notices and
source availability information when redistributing its compiled WASM.
