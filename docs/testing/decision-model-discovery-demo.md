# Decision model discovery demo

Branch: `feat/le-3188-openrouter-decisions`  
Committed baseline: `268d92d2bf2`, plus local Copilot fixes and multi-question support  
Worktree: `/Users/jordan.frazier/Documents/Langflow/langflow-le-3188`

This walkthrough tests dynamic OpenRouter and TypeSafe catalogs, manual OpenRouter IDs, persistence, single-question execution, and mixed questions through tables or JSON. It is a manual test plan, not a record of a completed browser demo.

## Before starting

Use this branch for both frontend and backend. Have an OpenRouter key and, for the TypeSafe section, a TypeSafe key. Use a disposable flow/project. Do not put keys in the flow, screenshots, or this document.

OpenRouter key validation uses its authentication endpoint without inference. Saving a TypeSafe key performs discovery and a minimal decision validation, which may be billed. Running either provider's Decision Model component may also be billed.

### Local stack on separate ports

These commands reuse the Python environment already installed in the Decision Models worktree and the frontend dependencies already available in this worktree. They use a separate database and ports to avoid touching another local Langflow instance.

Backend terminal:

```bash
cd /Users/jordan.frazier/Documents/Langflow/langflow-le-3188
mkdir -p /tmp/langflow-decision-discovery-demo/config
PYTHON_DOTENV_DISABLED=1 \
LANGFLOW_AUTO_LOGIN=true \
LANGFLOW_DATABASE_URL=sqlite:////tmp/langflow-decision-discovery-demo/langflow.db \
LANGFLOW_CONFIG_DIR=/tmp/langflow-decision-discovery-demo/config \
DO_NOT_TRACK=true \
LFX_DEV=1 \
PYTHONPATH=src/backend/base:src/lfx/src \
/tmp/le3117-uv-tool/bin/uv run --no-project \
  --python /Users/jordan.frazier/Documents/Langflow/langflow-le-3117/.venv/bin/python \
  python -m uvicorn --factory langflow.main:create_app \
  --host localhost --port 7861 --loop asyncio
```

Frontend terminal:

```bash
cd /Users/jordan.frazier/Documents/Langflow/langflow-le-3188/src/frontend
VITE_PROXY_TARGET=http://localhost:7861 VITE_PORT=3001 npm start
```

Open http://localhost:3001. These startup commands have been checked against the repository configuration but have not been run for this demo. If dependencies are missing, install the repository's development dependencies first. Environment-configured provider keys can make providers appear configured immediately even with a fresh database.

## Component table sanity check (no provider call)

Add a fresh Decision Model node from the updated backend. Choice should open **Options** containing **Option A / Option B**. Edit those choices, then switch to Score: its separate **Levels** table should contain **Low / Medium / High**. Edit the score levels. Switch Choice → Score → Boolean → Choice: each table must retain its own edits, and Boolean hides both tables. Running Choice must use only Options; running Score must use only Levels.

For an existing node, update its component code first. Old Score nodes stored their rubric in the shared table; updating migrates those rows into Levels. Existing Choice rows stay in Options. Nodes already using separate tables must retain both tables when updated again.

## 1. OpenRouter discovery

1. Create a blank flow and add **Decision Model**.
2. Open provider setup from its **Decision Model** field, or open **Settings → Model Providers** and select the decision-model view.
3. Select **OpenRouter**. It should be available even before credentials are configured.
4. Save a valid OpenRouter key.
5. Inspect its decision list. It should contain models from several authors, including any aliases and free variants OpenRouter currently lists. Chat-only models must not appear in the decision list.
6. Enable a model if necessary, close the dialog, and select it in the node.

Expected: discovered models are selectable under OpenRouter without adding model names to Langflow source. The provider remains OpenRouter even when the author is TypeSafe, OpenAI, or Perplexity.

Optional public comparison (no key or inference):

```bash
curl --fail --silent --show-error \
  'https://openrouter.ai/api/v1/models?output_modalities=decisions'
```

Use this live response rather than expecting a fixed number of models. The implemented fetch returned 29 models during development. Catalog responses are cached in the backend for 120 seconds; reopen/refetch after expiry or restart the demo backend when checking upstream changes. A browser reload alone does not invalidate the server cache.

## 2. Manually add a model ID and verify persistence

1. With OpenRouter configured, open the **decision** view and use **Search or add a model ID…**.
2. Enter `demo/not-a-real-model`. This deliberately nonexistent ID tests persistence without relying on a real model being absent from discovery.
3. Click **Add decision model "demo/not-a-real-model"**.
4. Close and reopen Model Providers, then reload the page.
5. Confirm the custom ID remains listed as a decision model and can be selected in the Decision Model field.
6. Turn it off. Confirm it is no longer offered in the node's picker after refreshing the node/model options.

Expected: adding an ID stores it in Langflow. It does not publish anything to OpenRouter or prove that OpenRouter can execute it. Account/key validation can succeed even for a nonexistent model ID; the provider validates the ID when it is run.

To demonstrate a real model absent from discovery, use a known callable ID from your OpenRouter account. Do not assume an arbitrary routing suffix is supported for decision requests.

Switch to the **All** and **language-model** views and search for a new chat ID. Neither view should offer **Add decision model**. Return to the decision view to add decision IDs.

## 3. Run one OpenRouter decision (optional, potentially billed)

Select an actual model from the current live list, then set:

| Field | Value |
| --- | --- |
| Decision Type | Boolean |
| Context | I was charged twice for the same order. Please refund the duplicate payment. |
| Question | Is the customer requesting a refund? |
| What Yes Means / What No Means | Leave both blank |

Run the node and inspect **Decision Result**.

Expected: a Boolean result with `provider: OpenRouter`, the returned model identity, and a numeric probability between 0 and 1. Do not require an exact probability or alias resolution. Provider-supplied usage/request ID may also be present.

Then, as a local validation check, fill only **What Yes Means** and leave **What No Means** blank. Run again. Expected: a configuration error asking for both descriptions, before an inference request is sent. Clear both fields afterward.

Optional failure check: run `demo/not-a-real-model` from section 2. Expected: a provider error, not a successful decision or silent substitution with another model. The precise error/status is provider-controlled and this case still sends a request.

## 4. TypeSafe discovery

1. Open Model Providers and configure TypeSafe with a valid key. Saving it can invoke a minimal billed validation decision.
2. Inspect TypeSafe's decision models. Expected: names from the authenticated account's `GET /v1/models`, replacing the bootstrap seed list.
3. During development the endpoint returned `jev-latest` and `jev-preview`; use the current response as the source of truth.
4. Confirm these entries are absent from the language-model list.
5. Optionally select a returned TypeSafe model and run the Boolean example above. Expected: a TypeSafe decision result with its returned model identity.

Discovery is cached for 120 seconds per credential fingerprint. Changing accounts must not reuse the previous account's catalog. Pinned TypeSafe IDs in existing flows can execute even when the listing endpoint only returns aliases; execution does not require a fresh catalog read.

## 5. Boundaries and regression checks

- Disable one discovered decision model, reopen Model Providers, and verify the toggle stays off and the node picker excludes it.
- Native OpenAI and Perplexity decision lists remain static: their documented model-list APIs do not establish decision capability. Their OpenRouter-hosted models are discovered under OpenRouter.
- Existing language-model selections should remain available. Decision enablement is stored separately from language-model enablement.
- An invalid TypeSafe key or unavailable catalog must produce a visible error rather than silently present a successful stale discovery result. A still-valid cached response can delay a new request until its 120-second TTL expires.
- Provider/model policy denial tests are automated; testing those manually requires an installation with policy enforcement configured.

## 6. Discovery outage and recovery (no inference)

Prerequisite: configure OpenRouter or TypeSafe while online, plus a native provider such as OpenAI so its decision option is available. Save the disposable flow with an OpenRouter selection. Do not run a node during this check.

1. Stop the demo backend with Ctrl-C to clear its discovery cache. Leave the frontend running.
2. Temporarily disconnect this Mac from the internet (Wi-Fi off and any Ethernet disconnected). Localhost must remain accessible. This affects other internet apps until you reconnect.
3. Restart the backend using the same command above. Reopen Model Providers. Failed requests can take time to finish; failed discovery is not cached and a combined listing can perform multiple probes.
4. Confirm the provider list loads. Select the failed provider: credentials remain editable, and a visible warning says decision models could not be loaded. It must not show the static seed as a successfully discovered list. Existing manually added IDs can remain listed.
5. Confirm native OpenAI language models remain listed. TypeSafe must not appear in the language-model view.
6. Close settings and refresh the Decision Model node's model options. Healthy static-provider options should remain available. Inspect the Decision Model field's help tooltip: it should name the failed provider and explain that discovery failed. The previously saved OpenRouter selection must not silently change to a different model.
7. Reconnect the internet. Reopen settings and refresh the node's options. Discovered options should return and the discovery warning should clear. If the browser still shows cached data, reload the page and refresh again.

Pass: an unavailable discovery service does not prevent access to healthy providers or credential repair. The warning is explicit; no stale seed list is presented as a successful fetch. Runtime availability is separate and is not tested by this section.

## 7. Keyless standalone picker (offline, no inference)

This check uses an isolated process with no provider keys and replaces the outbound discovery call with a guard that fails if contacted. It does not change your saved Langflow credentials or require disconnecting the Mac.

```bash
cd /Users/jordan.frazier/Documents/Langflow/langflow-le-3188
PYTHON_DOTENV_DISABLED=1 PYTHONPATH=src/lfx/src \
/tmp/le3117-uv-tool/bin/uv run --no-project \
  --python /Users/jordan.frazier/Documents/Langflow/langflow-le-3117/src/lfx/.venv/bin/python \
  python - <<'PYCODE'
import os
from unittest.mock import patch
from lfx.base.models.unified_models import get_decision_model_options
for name in ("OPENROUTER_API_KEY", "LANGFLOW_OPENROUTER_API_KEY",
             "TYPESAFE_API_KEY", "LANGFLOW_TYPESAFE_API_KEY"):
    os.environ.pop(name, None)
with patch("lfx.base.models.model_utils.get_live_models_for_provider",
           side_effect=AssertionError("Keyless picker must not discover")):
    options = get_decision_model_options()
    assert any(row["provider"] == "OpenAI" for row in options)
    assert not any(row["provider"] == "OpenRouter" for row in options)
print("PASS: keyless standalone picker retains static options without discovery")
PYCODE
```

## Record your results

| Check | Result / evidence |
| --- | --- |
| OpenRouter live list and node selection | Not run |
| Manual decision ID persists; no add control in All/chat | Not run |
| Optional billed decision | Not run |
| TypeSafe live list and language-model separation | Not run |
| Outage: settings remain usable and warning appears | Not run |
| Outage: node picker preserves healthy options and saved selection | Not run |
| Recovery clears warnings and restores discovered options | Not run |
| Keyless standalone guard | Not run |

Record provider/model IDs and the visible error text, but never API keys. Treat this table as your manual evidence, independent of automated checks.

## Automated evidence

Previous development checks verified live OpenRouter public and TypeSafe authenticated discovery. The committed API/UI isolation fix passed scoped tests. The local picker fix adds a real build-config refresh test with only the HTTP boundary faked: configured-provider outage, healthy options retained, saved selection retained, and warning cleared after recovery.

No paid inference or full browser walkthrough has been performed for this demo. Startup commands are specific to the existing local development environments listed above.

## Cleanup

Disable/remove the deliberately invalid model from your demo configuration and stop both terminals with Ctrl-C. The isolated demo data remains under `/tmp/langflow-decision-discovery-demo`; it can be removed later once nothing in it is needed.

## Multiple mixed-type questions in one Decision Model

Use a new Decision Model node, or update an existing node to load the latest component code. Existing nodes default to **Questions Mode → Single** and retain their original question, Choice options, and Score levels.

1. Select an enabled decision model and set **Questions Mode → Multiple**.
2. Enter Context: `Our invoice was charged twice and we need this resolved today. Work can continue while we wait.`
3. Open **Questions** and add these rows. Leave both Boolean description columns blank for this cross-provider example.

| ID | Type | Question |
| --- | --- | --- |
| team | Choice | Which team should handle this message? |
| urgent | Boolean | Does the customer request action today? |
| impact | Score | How much is the customer's work disrupted? |

4. In **Choice Options**, add:

| Question ID | ID | Label | Description |
| --- | --- | --- | --- |
| team | billing | Billing | Invoices, charges, refunds, or payments |
| team | support | Support | Product usage or technical help |

5. In **Score Levels**, add these rows in order:

| Question ID | ID | Label | Description |
| --- | --- | --- | --- |
| impact | low | Low | Work can continue normally |
| impact | medium | Medium | Work continues with a workaround |
| impact | high | High | Core work is blocked |

6. Run the component and inspect Decision Result.

Expected contract:

- `answers.team` contains `kind: "choice"`, probabilities keyed by `billing` and `support`, and a selected option when supplied by the provider.
- `answers.urgent` contains `kind: "boolean"` and `probability_true`.
- `answers.impact` contains `kind: "score"`, probabilities keyed by `low`, `medium`, and `high`, and a score between 0 and 2.
- There is one shared `usage` block when the provider supplies usage. The token badge must not multiply the request usage by three.
- Langflow sends one request with all three questions. It does not run a separate inference for each row.
- Exact probabilities and labels are not assertions: model judgments may vary. A provider refusal is preserved for the individual question rather than converted into a false answer.

## Paste the equivalent Questions JSON

Switch **Questions Mode → JSON**. The **Questions JSON** editor appears; paste:

```json
{
  "team": {
    "kind": "choice",
    "question": "Which team should handle this message?",
    "options": [
      {"id": "billing", "label": "Billing", "description": "Invoices, charges, refunds, or payments"},
      {"id": "support", "label": "Support", "description": "Product usage or technical help"}
    ]
  },
  "urgent": {
    "kind": "boolean",
    "question": "Does the customer request action today?"
  },
  "impact": {
    "kind": "score",
    "question": "How much is the customer's work disrupted?",
    "levels": [
      {"id": "low", "label": "Low", "description": "Work can continue normally"},
      {"id": "medium", "label": "Medium", "description": "Work continues with a workaround"},
      {"id": "high", "label": "High", "description": "Core work is blocked"}
    ]
  }
}
```

This is Langflow's provider-neutral question format, not a raw provider request or JSON Schema. Do not wrap it in `questions`, add `context`, or include credentials. Context and model remain separate component inputs. Boolean definitions can optionally include `yes_description` and `no_description`, subject to the selected provider's support.

Run again. Expect the same answer structure; numerical results need not be identical across runs. JSON mode uses only the pasted definitions. Switching back to Multiple should restore the unchanged table values; JSON and tables do not automatically synchronize. Switching back to Single should restore its independent options and levels.

## Multiple-question validation and saved-flow checks

- Duplicate a question ID in the Questions table: execution must stop before inference.
- Give a Choice Options row an unknown Question ID, or attach Score Levels to a Choice question: execution must stop with a configuration error.
- In JSON mode, try `{}`, malformed JSON, or duplicate object keys: execution must stop without inference, rather than ignore or overwrite a question.
- Leave the hidden single Question blank in Multiple/JSON mode: the mixed-question run should still work.
- Save and reload the flow in Multiple and JSON modes. Check all rows/text remain intact. Update the node code and verify its active fields still match the saved mode.
- Verify a Single-mode saved flow still returns the original flat result shape, without an `answers` wrapper.
- Smart Router remains single-question. Multiple-question routing and custom output-schema compilation are outside this change.

Provider compatibility errors still stop the run. No automatic splitting or retry into separate questions is performed. Grouping can affect results and billing, especially with Perplexity; this test verifies the response contract, not equality with three separate calls.

Local automated validation uses fixed HTTP responses, including mixed answers for all four providers and the actual component/runtime/adapter path. This manual walkthrough remains to be run against live providers and the browser UI.
