# lfx-native

The native core of lfx, written in Rust. It is one crate, `lfx`, with one module per feature. The first module is `lfx::ops`, the flow operation engine. It applies, diffs, validates, repairs and hashes flow graphs. It knows flow graphs, not storage: the flow history service owns stored rows, revision numbers, requests, actors and damaged history.

The server and the editor use the same engine, through two thin bindings:

- `lfx-python`: the Python package `lfx-native` (`import lfx_native`).
- `lfx-wasm`: the npm package `lfx-native`, a WebAssembly build for the editor and for Node.

The bindings hold no rules. Each binding function calls one function of `lfx::ops::api`, which takes JSON text and returns JSON text.

## Layout

```text
src/lfx-native/
  Cargo.toml             the Cargo workspace (not a uv workspace member)
  rust-toolchain.toml    the pinned Rust toolchain, with the wasm32 target
  crates/
    lfx/                 the `lfx` crate
      src/ops/           lfx::ops, the flow operation engine
      tests/fixtures/    runs every shared fixture file, one test per case
    lfx-python/          the Python binding (PyO3, maturin)
      python/lfx_native/ the Python package around the native module
      tests/             runs every shared fixture file through Python
    lfx-wasm/            the browser binding (wasm-bindgen)
      tests/             runs every shared fixture file through Node
  fixtures/              the shared golden fixtures: the engine's specification
    tools/               the scripts that check an engine against them
```

The modules of `lfx::ops`:

| Module | What it holds |
| --- | --- |
| `api` | JSON in, JSON out: the functions the bindings call |
| `ops` | operation types, the strict parser, and the dump |
| `state` | `GraphState`, the indexed graph that apply works on, kept between batches |
| `apply` | apply, with inverses |
| `diff` | diff, and the check that its operations replay to the target |
| `validate` | graph rules and violations, with codes and resolutions |
| `repair` | the repairs of violations that have one fix |
| `edges` | edge rules and handle reading |
| `entry` | what the engine reads from untyped nodes, edges and rows: ids, templates |
| `keyed` | keyed lists and table rows |
| `schema` | the node schema (`node_schema.json`, embedded) |
| `canonical` | canonical form, number printing, `graph_hash` |
| `restore` | restore fixes, from both sides |
| `write` | the engine's part of a save, in one call |
| `ids` | random ids in the editor's formats |
| `error` | errors, with a kind and a stable code |

## Who uses what

This table maps each part of the engine to its callers today, in the Python engine and the editor's engine at `ad19da0df4` (`oplog-history-ui`). After the switch, the same callers use the bindings.

### Used by both sides

| Part | Python (`lfx_native.ops`) | Browser (`lfx-native`) | Backend callers | Editor callers |
| --- | --- | --- | --- | --- |
| Apply operations | `apply`, `GraphState.apply` | `apply`, `GraphState.apply` | replay (`flow_history/replay.py`), restore fixes (`flow_history/restore_fixes.py`) | history playback (`flow-operations/history.ts`) |
| Assign row ids to a table | `assign_row_ids`, `assign_changed_table_row_ids` | `assignRowIds`, `assignChangedTableRowIds`, `assignChangedNodeTableRowIds` | the assistant (`agentic/utils/assistant_runner.py`, `flow_component.py`), the MCP patch (`lfx/mcp/server.py`) | `flowStore.ts`, `use-add-flow.ts`, template hooks, `mutate-template.ts`, `TableNodeComponent` |
| Strip row ids and order rows | `strip_row_keys`, `strip_flow_table_row_keys`, `ordered_rows` | `stripRowKeys`, `stripFlowTableRowKeys`, `orderedRows` | flow export (`api/utils/core.py`), MCP export, the component run (`lfx/graph/vertex/param_handler.py`), the refresh endpoint (`api/v1/endpoints.py`) | download and export (`reactflowUtils.ts`), `TableNodeComponent` |
| Canonical equality | `graphs_equal`, `values_equal` | `graphsEqual`, `valuesEqual` | the save's no-op check and the check that the stored graph matches its latest revision (`flow_history/recorder.py`) | inside the editor's engine only |
| Node schema | `table_fields`, `node_schema` | `tableFields`, `nodeSchema` | the refresh endpoint finds table fields (`api/v1/endpoints.py`) | inside the editor's engine only |

### Used only by the backend

| Part | Python (`lfx_native.ops`) | Backend callers |
| --- | --- | --- |
| The save: validate, repair, derive | `prepare_write`, or `validate`, `repair`, `derive` | `flow_history/recorder.py` (every graph write: PATCH, PUT, import, version activation, the assistant, file sync). The recorder numbers the operations and packs them into rows itself. |
| Diff | `diff` | through `derive` in the recorder |
| Graph hash | `graph_hash` | checkpoints and the check that the stored graph matches its latest revision (`recorder.py`), replay (`flow_history/replay.py`) |
| Restore fix check | `apply_restore_fixes` | revision restore (`api/v1/flow_revisions.py`), version restore (`api/v1/flow_version.py`) |
| New edge ids | `new_edge_id` | flow expansion (`processing/expand_flow.py`), the flow builder (`lfx/graph/flow_builder/connect.py`) |

### Used only by the editor

| Part | Browser (`lfx-native`) | Editor callers |
| --- | --- | --- |
| Inverses, and applying them | `GraphState.apply` with `inverse` and `restoring` | history timeline (`buildHistoryTimeline` and `graphAt` in `history.ts`) |
| Changed nodes and edges | the `changed_nodes` and `changed_edges` of an apply | none yet; for history playback on the canvas |
| Append rows, and renumber a full gap | `appendTableRows`, and `assignRowIds` with renumbering (the default in the browser) | `TableNodeComponent` |
| Edge fixes for a refused restore | `edgeFixes`, `fixesForEdges` | `use-flow-version-sidebar.ts`, `refused-restore.ts` |

These stay in TypeScript, because they are not engine rules: the history descriptions (`describe.ts`), node changes (`changes.ts`), names (`names.ts`) and timeline folding (`fold.ts`).

Only the editor renumbers table positions. The server never changes a position, so the Python binding's table functions do not renumber unless a caller passes `editor=True`.

## Commands

Run these in `src/lfx-native/`.

Test, lint and format the crate:

```bash
cargo test
```

```bash
cargo clippy --workspace --all-targets -- -D warnings
```

```bash
cargo fmt --check
```

Build the Python binding into a virtual environment, and run its fixture runner. `VIRTUAL_ENV` names the environment to install into:

```bash
maturin develop --release --uv --manifest-path crates/lfx-python/Cargo.toml
```

```bash
python -m pytest crates/lfx-python
```

Build the browser binding and run its fixture runner. This needs `wasm-bindgen-cli` at the version of the `wasm-bindgen` crate:

```bash
npm --prefix crates/lfx-wasm run build
```

```bash
npm --prefix crates/lfx-wasm test
```

## Fixtures

The fixture files are the specification of the engine. Their expected outputs are written data that people review, and every engine must meet them. Every runtime runs every file: the Rust runner, the Python runner and the Node runner. Each case names the rule it checks, and every runner fails on a case without one.

To add or change a case, write it by hand with its rule, as `fixtures/README.md` says. A rule change is a reviewed edit to the cases of that rule. The tools in `fixtures/tools/` only check an engine against the fixtures, and never write them.
