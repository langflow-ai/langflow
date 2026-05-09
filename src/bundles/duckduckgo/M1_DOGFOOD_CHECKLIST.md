# M1 dogfood checklist — `lfx-duckduckgo` pilot bundle

Per the [Bundle Separation Developer Guide §6 LE-1023], the M1 proof-of-delivery
gate has two halves:

1. **Deserialize-side** — automated, lives in
   [`src/lfx/tests/integration/extension/test_pilot_duckduckgo_upgrade.py`](../../lfx/tests/integration/extension/test_pilot_duckduckgo_upgrade.py).
   The migration table rewrites every legacy reference form
   (bare class name, full import path, package-level import path,
   pre-Phase-A slot ID) to
   `ext:duckduckgo:DuckDuckGoSearchComponent@official`, and the
   `lfx-duckduckgo` distribution is importable + ships its manifest in a
   location `importlib.metadata.files` can discover.

2. **Runtime-side** — manual.  The pre-merge dogfood gate.  This file is
   the checklist for that half.

The gate is "save a flow on pre-migration Langflow, upgrade, confirm it
loads AND RUNS identically."  A unit-style integration test cannot prove
this because it would have to span a Python environment swap.  A real
dogfood run by an engineer who is *not* on the Extension team is what
actually closes LE-1023.

---

## Dogfood run

| Field | Value |
| --- | --- |
| Run by | _engineer name + handle_ |
| Date | _YYYY-MM-DD_ |
| Pre-migration Langflow version | `1.9.x` (last release before the pilot landed) |
| Post-migration Langflow version | this branch / `1.10.x` |
| Result | _pass / fail_ |
| Notes | _free text_ |

### Steps

1. **Pre-migration save.**
   - [ ] `pip install langflow==<pre-migration version>` in a clean venv
   - [ ] `langflow run` and open the UI
   - [ ] Drag a **DuckDuckGo Search** component onto the canvas, set
         `query` to a string that produces deterministic-enough output
         (e.g. `"site:wikipedia.org claude shannon"`)
   - [ ] Wire it into a minimal flow that prints the result list
   - [ ] **Save the flow** — record the resulting JSON to disk
         (download from the UI or read out of the SQLite store)

2. **Pre-migration run.**
   - [ ] Run the flow once and **record the output** (titles + URLs) to
         a file alongside the saved flow JSON

3. **Upgrade.**
   - [ ] In a separate clean venv: `pip install langflow==<this branch>`
         (which transitively pulls in `lfx-duckduckgo`)
   - [ ] Confirm `lfx extension list --format=json` shows
         `lfx-duckduckgo` at slot `@official`

4. **Post-migration load.**
   - [ ] `langflow run`, open the saved flow JSON from step 1
   - [ ] Confirm the canvas renders the DuckDuckGo node intact
         (no red placeholder; no "component not found" toast)
   - [ ] Inspect the loaded node's `data.type` field — it should be
         `ext:duckduckgo:DuckDuckGoSearchComponent@official`
         (rewritten by the migration table on load)

5. **Post-migration run.**
   - [ ] Execute the flow with the same `query` value from step 1
   - [ ] Compare the output to the recording from step 2
   - [ ] **Pass criterion:** the result set is materially equivalent.
         DuckDuckGo's ranking can drift between calls, so an exact
         byte-for-byte match is not the bar; "the top results overlap
         and the schema is identical" is enough.  The point of this
         check is "the component still works against a real network",
         not "search results are deterministic."

6. **Sign-off.**
   - [ ] Paste this completed checklist as a comment on the LE-1023
         ticket
   - [ ] Cross-link the comment in the PR description under
         "M1 dogfood evidence"

---

## What "fail" looks like

Any of:

- The pre-migration flow JSON does not load (red placeholder, "component
  not found", typed `component-not-found-with-hint` toast).
- The migration table rewrites the node to a non-canonical or wrong
  target.
- Post-migration execution raises an exception that did not exist
  pre-migration.
- The result schema differs (different fields, different shape) — note
  that this is different from "different ranking", which is fine.

If any of these fail, **do not merge**.  File a follow-up that captures
the failure mode in
[`test_pilot_duckduckgo_upgrade.py`](../../lfx/tests/integration/extension/test_pilot_duckduckgo_upgrade.py)
so the regression is locked in.
