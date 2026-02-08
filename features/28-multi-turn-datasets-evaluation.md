# Feature: Multi-Turn Datasets & Evaluation

## Overview

Add support for multi-turn (conversational) datasets alongside the existing single-turn datasets. When evaluating with a multi-turn dataset, turns within the same conversation share a session, so chat history accumulates naturally through Langflow's existing message storage and agent memory retrieval.

---

## How It Works (Core Concept)

A multi-turn dataset is a flat list of items with a `conversation_id` column that groups turns:

```csv
conversation_id,input,expected_output
1,"hi","Hello! How can I help you?"
1,"what's the weather in SF?","It's currently sunny in San Francisco."
1,"what about tomorrow?","Tomorrow's forecast shows rain."
2,"tell me a joke","Why did the chicken cross the road?"
2,"another one","Knock knock..."
```

During evaluation:
- Items with the same `conversation_id` share ONE `session_id`
- Turns run **sequentially** within a conversation
- Chat Input stores each user message in the DB (existing behavior via `should_store_message=True`)
- Agent stores its response in the DB (existing behavior)
- On the next turn, Agent's `get_memory_data()` retrieves all prior messages by `session_id` — history accumulates naturally
- Each turn is scored individually against its `expected_output`

**No changes needed to graph execution, agent memory, or message storage.** The only change is reusing `session_id` across turns instead of generating a new one per item.

---

## Data Model Changes

### Dataset Model

**File:** `src/backend/base/langflow/services/database/models/dataset/model.py`

Add to `Dataset`:
```python
dataset_type: str = Field(default="single_turn")  # "single_turn" or "multi_turn"
```

Add to `DatasetItem`:
```python
conversation_id: str | None = Field(default=None)  # Groups turns in multi-turn datasets
```

Add to `DatasetCreate` / `DatasetRead`:
```python
dataset_type: str = "single_turn"
```

Add to `DatasetItemCreate`:
```python
conversation_id: str | None = None
```

### Alembic Migration

New migration adding:
- `dataset_type` column to `dataset` table (VARCHAR, default "single_turn")
- `conversation_id` column to `dataset_item` table (VARCHAR, nullable)

---

## CSV Import Changes

**File:** `src/backend/base/langflow/api/v1/datasets.py`

### Auto-Detection

When importing a CSV:
1. Check if a `conversation_id` column exists
2. If yes → set `dataset_type = "multi_turn"`, populate `conversation_id` on each item
3. If no → set `dataset_type = "single_turn"` (current behavior)

### Validation

For multi-turn CSVs:
- `conversation_id` column is required (but auto-detected)
- `input` and `expected_output` columns still required
- Items are ordered by `conversation_id` first, then by row order within each conversation
- `conversation_id` values can be any string/number — they're just grouping keys

### Item Ordering

When creating items from CSV:
```python
# Sort by conversation_id, then by original row order
# Assign order field: items within a conversation get sequential order values
# This ensures they run in the right sequence during evaluation
```

---

## Evaluation Runner Changes

**File:** `src/backend/base/langflow/api/v1/evaluations.py`

### `run_single_evaluation_item` Signature Change

Add optional `session_id` parameter:
```python
async def run_single_evaluation_item(
    flow_data: dict,
    flow_id: UUID,
    flow_name: str,
    user_id: UUID,
    input_value: str,
    scoring_methods: list[str],
    expected_output: str,
    llm_judge_prompt: str | None = None,
    llm_judge_model: dict | None = None,
    session_id: str | None = None,  # NEW — if provided, reuse instead of generating
) -> dict:
```

If `session_id` is None (single-turn), generate a new UUID as before.
If `session_id` is provided (multi-turn), use it directly.

### `run_evaluation_background` Changes

```python
if dataset.dataset_type == "multi_turn":
    # Group items by conversation_id, preserving order within each conversation
    conversations = {}
    for item in sorted_items:
        conv_id = item.conversation_id or "default"
        conversations.setdefault(conv_id, []).append(item)

    item_index = 0
    for conv_id, turns in conversations.items():
        # One session per conversation
        conv_session_id = str(uuid4())

        for turn in turns:
            item_result = await run_single_evaluation_item(
                flow_data=flow.data,
                flow_id=flow.id,
                flow_name=flow.name,
                user_id=user_id,
                input_value=turn.input,
                scoring_methods=evaluation.scoring_methods,
                expected_output=turn.expected_output,
                llm_judge_prompt=evaluation.llm_judge_prompt,
                llm_judge_model=evaluation.llm_judge_model,
                session_id=conv_session_id,  # Shared within conversation
            )
            # Save result, update progress (same as current code)
            # ...
            item_index += 1
else:
    # Current behavior — each item gets its own session
    for idx, item in enumerate(sorted_items):
        item_result = await run_single_evaluation_item(...)
```

### Parallelization Note

Different conversations CAN run in parallel (they have independent session_ids). Turns within a conversation MUST be sequential. For V1, run everything sequentially (current behavior). Parallel conversations can be a future optimization.

---

## Frontend Changes

### Dataset Detail Page

**File:** `src/frontend/src/pages/MainPage/pages/datasetDetailPage/index.tsx`

For multi-turn datasets:
- Show a "Conversation" column in the items table
- Group rows visually by conversation_id (alternating background, separator, or collapsible groups)
- Show conversation count in dataset summary (e.g., "12 items in 3 conversations")

### Datasets List Page

**File:** `src/frontend/src/pages/MainPage/pages/datasetsPage/`

- Show dataset type badge ("Single-turn" / "Multi-turn") in the datasets table
- No other changes needed — creation flow stays the same (import CSV)

### CSV Import

**File:** `src/frontend/src/pages/MainPage/pages/datasetsPage/index.tsx` (or the import modal)

- Auto-detect `conversation_id` column → show info message: "Detected multi-turn dataset with N conversations"
- No manual toggle needed — the presence of `conversation_id` column determines the type

### Create Evaluation Modal

**File:** `src/frontend/src/modals/createEvaluationModal/index.tsx`

- When a multi-turn dataset is selected, show an info note: "Multi-turn dataset: turns within each conversation will share chat history"
- No other changes needed — scoring methods work the same per-turn

### Evaluation Results Page

**File:** `src/frontend/src/pages/FlowPage/components/EvaluationsMainContent/index.tsx`

For multi-turn evaluations:
- Add a "Conversation" column showing the conversation_id
- Visual grouping of rows by conversation (alternating bg or separator between conversations)
- Summary footer: show per-conversation pass rate in addition to overall

### Evaluation Results Model

Add to `EvaluationResult`:
```python
conversation_id: str | None = Field(default=None)
```

Add to `EvaluationResultRead`:
```python
conversation_id: str | None = None
```

Store this when creating result records so the frontend can group them.

---

## API Changes

### Dataset Endpoints

`POST /api/v1/datasets/upload` — no signature changes, auto-detects type from CSV columns

`GET /api/v1/datasets/{id}` — response now includes `dataset_type` field

`GET /api/v1/datasets/{id}/items` — response items now include `conversation_id` field

### Evaluation Endpoints

No API changes needed — the evaluation runner handles multi-turn internally based on the dataset type.

---

## Edge Cases & Considerations

### 1. Flow Without Agent/Memory
Multi-turn still "works" but each turn is effectively independent since nothing reads the session history. This is fine — the scoring still works per-turn. Could show a warning in the UI if a multi-turn dataset is used with a flow that has no memory-aware components.

### 2. `should_store_message` on Chat Input
Must be `True` (the default) for history to accumulate between turns. If the user's flow has it set to `False`, multi-turn won't provide context. Document this.

### 3. Turn Failure Mid-Conversation
If Turn 2 fails (graph error), Turn 3 still runs — but only with Turn 1's history since Turn 2 didn't produce output. Record the error on Turn 2, continue with Turn 3. Don't abort the whole conversation.

### 4. Message Cleanup
Each conversation uses a unique UUID session_id, so evaluation messages are orphaned after the run. They won't interfere with real conversations. For cleanup: optionally delete messages by session_id after evaluation completes. Not critical for V1 — the messages are small and the session_ids are unique.

### 5. Single-Turn Datasets Are Unchanged
Everything is backward-compatible. Existing datasets default to `dataset_type="single_turn"` and `conversation_id=None`. Evaluation behavior is identical to current.

### 6. conversation_id Values
Can be any string — "1", "2", "conv_a", "session_xyz". They're just grouping keys within a dataset. No need for them to be sequential or numeric.

---

## Files to Modify (Summary)

### Backend
| File | Change |
|------|--------|
| `services/database/models/dataset/model.py` | Add `dataset_type` to Dataset, `conversation_id` to DatasetItem |
| `alembic/versions/new_migration.py` | New migration for the two columns |
| `api/v1/datasets.py` | Auto-detect `conversation_id` column in CSV import, set dataset_type |
| `api/v1/evaluations.py` | Add `session_id` param to `run_single_evaluation_item`, group by conversation in `run_evaluation_background` |
| `services/database/models/evaluation/model.py` | Add `conversation_id` to EvaluationResult |

### Frontend
| File | Change |
|------|--------|
| `pages/MainPage/pages/datasetDetailPage/index.tsx` | Show conversation column, visual grouping |
| `pages/MainPage/pages/datasetsPage/` | Dataset type badge in list |
| `modals/createEvaluationModal/index.tsx` | Info note for multi-turn datasets |
| `pages/FlowPage/components/EvaluationsMainContent/index.tsx` | Conversation column, row grouping in results |
| `controllers/API/queries/evaluations/use-get-evaluations.ts` | Add conversation_id to type |
| `controllers/API/queries/datasets/` | Add dataset_type, conversation_id to types |

---

## Implementation Order

1. **Backend model + migration** — Add fields to Dataset, DatasetItem, EvaluationResult
2. **CSV import** — Auto-detect conversation_id column, set dataset_type
3. **Evaluation runner** — Group by conversation, share session_id
4. **Frontend dataset pages** — Show type badge, conversation grouping in detail page
5. **Frontend evaluation results** — Conversation column and grouping
6. **Testing** — Create a multi-turn CSV, import it, run evaluation against an agent flow
