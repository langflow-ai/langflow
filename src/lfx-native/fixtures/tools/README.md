# Fixture generators

The fixture files are the specification of the engine. Their expected outputs come from the current engines, never from the Rust engine. These two scripts record them.

| Script | Engine it runs | Files it writes |
| --- | --- | --- |
| `generate.py` | the Python engine (`lfx.services.flow_operations` and the pure parts of `langflow.services.flow_history`) | `canonical_cases.json`, `validation_cases.json`, `repair_cases.json`, `table_cases.json`, `envelope_cases.json`, `replay_cases.json`, `restore_cases.json`, `write_cases.json` |
| `generate_editor.mjs` | the editor's TypeScript engine (`src/frontend/src/utils/flow-operations/`), for what only it has: inverses, the editor's table rules and the edge fixes | `inverse_cases.json`, `editor_cases.json` |

The other files (`apply_cases.json`, `diff_cases.json`, `merge_cases.json`, `property_cases.json`) were moved from the lfx tests unchanged.

The reference for both engines is `ad19da0df4` on `oplog-history-ui`.

## Conventions

- A graph whose number text matters (a number JavaScript reads as Infinity, or `1.0` against `1`) is stored as JSON text in a `*_json` field. A runner gives the engine that exact text.
- An id the engine draws at random is stored as `<generated edge id>` or `<generated row id>`. A runner accepts any id of that shape there.

## Run them

`generate.py` needs `lfx` and `langflow` importable at the reference commit, for example from a checkout of `oplog-history-ui` with its uv environment:

```bash
uv run python ../lfx-native/fixtures/tools/generate.py
```

`generate_editor.mjs` needs the TypeScript engine bundled into one CommonJS file that exports `applyFlowOperations`, `graphsEqual`, `edgeFixes`, `fixesForEdges`, `withTableRowIds`, `withNodesTableRowIds` and `appendTableRows`. In `src/frontend` of the same checkout, with an entry file that exports them:

```bash
npx esbuild entry.ts --bundle --platform=node --format=cjs --outfile=ts_engine.cjs
```

```bash
node ../lfx-native/fixtures/tools/generate_editor.mjs ts_engine.cjs
```
