# lfx-native

The native core of lfx, written in Rust. It is one crate, `lfx`, with one module per feature. The first module is `lfx::ops`, the flow operation engine. It applies, diffs, validates, repairs and hashes flow graphs.

The server and the editor use the same engine. A Python binding and a browser binding will publish it as `lfx-native`.

## Layout

```text
src/lfx-native/
  Cargo.toml             the Cargo workspace (not a uv workspace member)
  rust-toolchain.toml    the pinned Rust toolchain
  crates/lfx/            the `lfx` crate
    src/ops/             lfx::ops, the flow operation engine
    tests/fixtures/      runs every shared fixture file, one test per case
  fixtures/              the shared golden fixtures: the engine's specification
```

## Commands

Run these in `src/lfx-native/`:

```bash
cargo test
```

```bash
cargo clippy --all-targets -- -D warnings
```

```bash
cargo fmt --check
```

## Fixtures

The fixture files are the specification of the engine. Every runtime runs every file. The expected outputs come from the Python engine (`lfx.services.flow_operations`), never from the output of this crate.
