# Fixture checkers

The fixture files are the specification of the engine (see `../README.md`). Their expected outputs are reviewed data. These scripts check an engine against them. They never write a fixture file.

Each checker runs one engine over the inputs of every case that the engine can run. It prints each case whose result differs from the expected output, with the case's name, its rule, what the engine gave and what the case expects. It ends with the number of cases and differences per section, and exits with 1 when a case differs.

| Script | Engine it checks | Files it checks |
| --- | --- | --- |
| `check.py` | the Python engine (`lfx.services.flow_operations`, and the restore fix check and the save path of `langflow.services.flow_history`) | every file except `inverse_cases.json` and `editor_cases.json` |
| `check_editor.mjs` | the editor's TypeScript engine (`src/frontend/src/utils/flow-operations/`), for what only it has: inverses, the editor's table rules and the edge fixes | `inverse_cases.json`, `editor_cases.json` |

Both scripts run the Python and editor engines of the operation log stack, so run them from a checkout of its top branch, `oplog-history-ui`.

## Run them

`check.py` needs `lfx` and `langflow` importable. From the repository root, with its uv environment:

```bash
uv run python src/lfx-native/fixtures/tools/check.py
```

`check_editor.mjs` needs the TypeScript engine bundled into one CommonJS file that exports `applyFlowOperations`, `graphsEqual`, `edgeFixes`, `fixesForEdges`, `withTableRowIds`, `withNodesTableRowIds` and `appendTableRows`. In `src/frontend`, with an entry file that exports them:

```bash
npx esbuild entry.ts --bundle --platform=node --format=cjs --outfile=ts_engine.cjs
```

```bash
node ../lfx-native/fixtures/tools/check_editor.mjs ts_engine.cjs
```

## Compare the engines on real flows

`compare_engines.py` runs the Rust engine, through the Python binding, side by side with the Python engine on every starter project. Both engines must agree on hashes, violations, repair fixes, diffs and replay. Run it before the Python engine is deleted, in `src/lfx` of a checkout whose environment has both `lfx` and `lfx-native` installed:

```bash
uv run python ../lfx-native/fixtures/tools/compare_engines.py ..
```
