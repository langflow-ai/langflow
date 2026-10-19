# Fixture generators

The fixture files are the specification of the engine. Their expected outputs come from the current engines, never from the Rust engine. These two scripts record them.

| Script | Engine it runs | Files it writes |
| --- | --- | --- |
| `generate.py` | the Python engine (`lfx.services.flow_operations` and the pure parts of `langflow.services.flow_history`) | `canonical_cases.json`, `validation_cases.json`, `repair_cases.json`, `table_cases.json`, `envelope_cases.json`, `replay_cases.json`, `restore_cases.json`, `write_cases.json`, and `limit_cases.json` |
| `generate_editor.mjs` | the editor's TypeScript engine (`src/frontend/src/utils/flow-operations/`), for what only it has: inverses, the editor's table rules and the edge fixes | `inverse_cases.json`, `editor_cases.json` |

`limit_cases.json` is the exception: the docs decide its expectations, not the Python engine. The Python engine accepts lone surrogates and any depth. The Rust engine refuses both, as the docs decide: a Rust string cannot hold a lone surrogate, and one depth limit holds in every runtime. `generate.py` writes the file from cases that state those expectations.

The other files are not generated. `apply_cases.json`, `diff_cases.json` and `merge_cases.json` are written by hand, and the docs decide their expectations. `property_cases.json` comes from `property_cases.py` in the lfx tests.

Both scripts run the Python and editor engines of the operation log stack, so run them from a checkout of its top branch, `oplog-history-ui`. A run that changes no rule leaves every file as it is, so after a rule change, the diff of a run shows exactly what the change does.

## Conventions

- A graph whose number text matters (a number JavaScript reads as Infinity, or `1.0` against `1`) is stored as JSON text in a `*_json` field. A runner gives the engine that exact text.
- An id the engine draws at random is stored as `<generated edge id>` or `<generated row id>`. A runner accepts any id of that shape there.

## Run them

`generate.py` needs `lfx` and `langflow` importable. From the repository root, with its uv environment:

```bash
uv run python src/lfx-native/fixtures/tools/generate.py
```

`generate_editor.mjs` needs the TypeScript engine bundled into one CommonJS file that exports `applyFlowOperations`, `graphsEqual`, `edgeFixes`, `fixesForEdges`, `withTableRowIds`, `withNodesTableRowIds` and `appendTableRows`. In `src/frontend`, with an entry file that exports them:

```bash
npx esbuild entry.ts --bundle --platform=node --format=cjs --outfile=ts_engine.cjs
```

```bash
node ../lfx-native/fixtures/tools/generate_editor.mjs ts_engine.cjs
```

## Compare the engines on real flows

`compare_engines.py` runs the Rust engine, through the Python binding, side by side with the Python engine on every starter project. Both engines must agree on hashes, violations, repair fixes, diffs and replay. Run it before the Python engine is deleted, in `src/lfx` of a checkout whose environment has both `lfx` and `lfx-native` installed:

```bash
uv run python ../lfx-native/fixtures/tools/compare_engines.py ..
```
