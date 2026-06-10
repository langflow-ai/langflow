# M1 dogfood checklist — `lfx-duckduckgo` pilot bundle

> **Status:** :hourglass: **OPEN** — the runtime half of the DuckDuckGo
> pilot has not been signed off. A non-Extension-team engineer must
> complete the steps below and paste the filled-in checklist into the
> PR before merge. Until that happens, the M1 proof-of-delivery gate is
> incomplete even if every automated check is green.

Per the Bundle Separation Developer Guide, the M1 proof-of-delivery
gate has two halves:

1. **Deserialize + build pipeline (automated)** — lives in
   [`src/lfx/tests/integration/extension/test_pilot_duckduckgo_upgrade.py`](../../lfx/tests/integration/extension/test_pilot_duckduckgo_upgrade.py)
   and covers:
   - Every legacy reference form (bare class name, full import path,
     package-level import path, pre-Phase-A slot ID) rewrites to
     `ext:duckduckgo:DuckDuckGoSearchComponent@official`.
   - The `lfx-duckduckgo` distribution is importable and ships its
     manifest where `importlib.metadata.files()` can discover it.
   - The loader resolves the migration target to a
     `DuckDuckGoSearchComponent` class built from the same source file as
     the bundle export — with the canonical `input_value` input and
     `dataframe` output preserved so existing flows' wiring stays valid.
   - **The loaded class's build pipeline runs end-to-end against a
     stubbed network wrapper** to the canonical output schema:
     `content` / `snippet` columns are present, `max_results` slicing
     and `max_snippet_length` truncation behave correctly, and the
     wrapper is called with the canonical `"<query> (site:*)"` template.

2. **Real cross-version swap (manual)** — the pre-merge dogfood gate.
   This file is the checklist for that half.

The remaining question for the dogfood is therefore narrow: with the
load-and-run pipeline now locked in by automated tests against a stub,
the human gate only needs to answer "do real DuckDuckGo search results
look materially the same between the pre- and post-migration releases?"
A unit-style integration test cannot answer that because it would have
to span a Python environment swap and touch the live DuckDuckGo
backend.  A real dogfood run by an engineer who is *not* on the
Extension team is what actually closes the DuckDuckGo pilot.

The checklist below is intentionally a template — fill it in, do not edit it
in advance. A pre-checked checklist is not evidence.

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
   - [ ] Cross-link the completed checklist in the PR description
         under "M1 dogfood evidence"

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
