# Evals

Evals runs a flow against a dataset of test cases, in the background, and scores
every answer. A **dataset** holds inputs and optional expected outputs. An
**evaluation** binds a flow, a dataset and a set of scorers. Each **run** of an
evaluation executes every item once against one pinned version of the flow and
keeps its results forever, so two runs can always be compared.

The model follows LangSmith (Dataset → Experiment → Evaluators), built on
Langflow primitives: the graph engine, flow versions and background jobs.

Off by default (`LANGFLOW_FEATURE_EVALS=false`). With the flag off, the routes
are not mounted and the UI hides every entry point.

## Ubiquitous language

| Term | Meaning |
|---|---|
| Dataset | A user-owned list of test cases. |
| Item | One test case: an input and an optional expected output. |
| Evaluation | Project-scoped config: flow, dataset, scorers, pass threshold, optional output component. |
| Run | One execution of an evaluation. Immutable once finished. |
| Result | One row of a run: the item's input and expected output (copied), the actual output, scores, tokens, cost, duration, trace id. |
| Scorer | A method that turns an answer into a 0–1 score: `exact_match`, `contains`, `similarity`, `llm_judge`. |
| Pass rule | A row passes when the weighted mean of its scores reaches the threshold. |
| Pinned version | The `flow_version` a run executes. Editing the flow afterwards never changes the run. |

## Where it lives

| Layer | Path |
|---|---|
| Models | `langflow/services/database/models/evaluation/` |
| Migrations | `alembic/versions/876a81df5a20_add_evals_tables.py` (EXPAND), `a1d7e3c5b9f2_backfill_dataset_system_role_permissions.py` (MIGRATE: `dataset:*` on the built-in roles) |
| Services | `langflow/services/evaluations/` |
| Routes | `langflow/api/v1/datasets.py`, `langflow/api/v1/evaluations.py` |
| Settings | `lfx/services/settings/groups/evals.py` |
| Memory guard | `lfx/memory/flow_context.py` (`set_evals_memory_isolated`) |
| Frontend | `pages/MainPage/pages/evalsPage/`, `modals/evaluateFlowModal/`, `controllers/API/queries/evals/` |

## Tables

All five tables are new. Every foreign key is indexed. Children are deleted
explicitly as well as by `ON DELETE CASCADE`, because SQLite does not enforce
cascades.

### `dataset`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID FK `user` CASCADE | Owner |
| `name` | VARCHAR(255) | Unique per user (`uq_dataset_user_name`) |
| `description` | TEXT NULL | |
| `revision` | INT | Bumped on every item change; lets the UI say "dataset changed since this run" |
| `created_at`, `updated_at` | TIMESTAMPTZ | |

### `dataset_item`

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `dataset_id` | UUID FK `dataset` CASCADE | |
| `position` | INT | Order within the dataset; indexed with `dataset_id` |
| `input` | JSON | `{"text": "..."}`; JSON leaves room for multi-field inputs |
| `expected_output` | JSON NULL | `{"text": "..."}` |
| `meta` | JSON NULL | Free; reserved for splits and filters |
| `source` | VARCHAR(16) | `manual`, `csv`, `logs` (CHECK) |

### `evaluation`

| Column | Type | Notes |
|---|---|---|
| `user_id` | UUID FK `user` CASCADE | Owner |
| `project_id` | UUID FK `folder` SET NULL | The flow's project at creation |
| `flow_id` | UUID FK `flow` SET NULL | Nulled when the flow is deleted; results stay readable |
| `dataset_id` | UUID FK `dataset` SET NULL | Nulled when the dataset is deleted |
| `output_vertex_id` | VARCHAR(255) NULL | Required only when the flow has more than one output |
| `scorers` | JSON | `[{type, name, weight, config}]` |
| `pass_threshold` | FLOAT | Default 0.5 |

### `evaluation_run`

| Column | Notes |
|---|---|
| `evaluation_id` | FK CASCADE |
| `job_id` | The `job` row (`JobType.EVALUATION`) that executes the run |
| `flow_version_id`, `flow_version_number`, `flow_version_source` | Pinned version; source is `latest` or `history` |
| `flow_name`, `dataset_name`, `dataset_revision` | Copies, so history reads after renames and deletes |
| `config` | Scorers, threshold and resolved output vertex at start; editing the evaluation never rewrites a run |
| `status` | `queued`, `running`, `completed`, `failed`, `cancelled` (CHECK) |
| `total_items`, `completed_items`, `failed_items`, `passed_items` | Counters updated atomically per row |
| `summary` | Aggregates written once at the end (see below) |
| `estimate` | The estimate shown before the run, kept for estimate-vs-actual |
| `error` | Why a run failed or stopped early |

### `evaluation_result`

One row per item per run. `UNIQUE(run_id, position)`. Holds copies of `input`
and `expected_output`, `actual_output` (capped at
`evals_actual_output_max_chars`, with `output_truncated`), `error`, `scores`
(`{name: {value, comment}}`), `passed`, `duration_ms`, `tokens_flow`,
`tokens_judge`, `cost_flow`, `cost_judge`, `trace_id`.

## Starting a run

`POST /api/v1/evaluations/{id}/runs` with an optional `{"flow_version_id": ...}`.

1. Loads the flow (execute permission) and the dataset (read permission).
2. Refuses a second active run of the same evaluation (409). A partial unique
   index (`uq_evaluation_run_one_active`) enforces it in the database, and the
   run row is inserted before the version is pinned, so concurrent starts
   cannot both win and a double click is harmless.
3. Checks the item count: 0 or more than `evals_max_items` is 422.
4. Pins the version:
   - **Latest** (no id): reuses the newest `flow_version` when its data hashes
     equal to the saved draft, otherwise snapshots the draft with
     `prune=False` and description "Evaluation run". A normal save does not
     create a version, so the snapshot is how "latest" becomes reproducible.
   - **History** (an id): loads that version of this flow (404 otherwise).
   - Either way the version is retained (`retained_reason="evaluation"`) unless
     already retained for another reason, so version pruning cannot remove it.
5. Runs the static flow checks on the **pinned** version (see below). Any
   blocking issue is 422 with `{"message", "issues": [{code, message, components}]}`.
6. Computes and stores the estimate on the run (`queued`), commits, then
   creates the job and launches the coordinator with
   `JobService.execute_with_status(..., keep_alive=True)`.

`POST /api/v1/evaluations?run=true` creates the evaluation and starts its first
run in one request; `flow_version_id` in the body picks a history version. A
start that fails leaves no evaluation behind.

Each row is saved in one short write-first transaction. On SQLite, very fast
rows (a flow without model calls finishes in milliseconds) commit so often,
together with the per-row trace, that another read-then-write request can
exhaust its lock retries; the Evals write routes retry and answer 503 with
`Retry-After` when they cannot, as the flow routes do. Rows that call a model
take far longer than the retry window, so this does not show in practice.

While a run is active, its dataset's items cannot be added, edited, deleted or
imported, and the dataset cannot be deleted (409): rows are matched to items by
position.

The frontend saves the flow before opening the Evaluate modal: autosave is
debounced, and "Latest" means the saved draft.

## Flow checks (`flow_checks.py`)

| Blocking code | Reason |
|---|---|
| `empty_flow` | No components |
| `human_in_the_loop` | A Human Input node or an approval-gated tool; an evaluation cannot answer |
| `no_input` | No Chat Input or Text Input |
| `no_output` | No Chat Output or Text Output |
| `multiple_outputs` | More than one output and none chosen |
| `output_not_found` | The chosen output is not in the pinned version |

| Warning code | Reason |
|---|---|
| `external_actions` | Components that usually act outside Langflow (email, Slack, webhooks, API request, MCP, SQL, ...) really run once per row |
| `external_memory` | A component exposing a `Memory` output; it is read and written for real and cannot be isolated |
| `frozen_components` | Frozen components return the same cached result for every row |

`GET /api/v1/evaluations/check?flow_id=` returns the same report for the saved draft.

## Coordinator (`runner.py`)

- Loads the run, the pinned version's data, the user and the rows not yet
  recorded (a resumed run never re-executes a finished row).
- Applies the caller-aware component policy (`prepare_flow_build_for_user`) and
  global-variable defaults once per run.
- Runs rows under two semaphores: `evals_row_concurrency` per run and
  `evals_max_concurrency` per process (one per event loop).
- Each row has `evals_row_timeout_s`; a timeout is recorded as a row error.
- A watcher polls the run status every 2 s, so a cancel written by any pod stops
  the rows in the pod that owns the run.
- At the end it writes `summary` and the terminal status. A cancel written
  meanwhile wins over a natural finish.

### One row (`row_runner.py`)

- Builds a fresh `Graph.from_payload` from the pinned data (graphs are stateful
  and never shared), stamps the `v1_run` execution principal, and binds the
  model-provider policy context for the flow's project.
- `graph.persist_messages = False`: no `message`, `vertex_build` or
  `transaction` rows. Traces are still written; `trace_id` is the row's run id.
- `session_id = "eval:{run_id}:{position}"`.
- Runs `run_graph_internal` with the item's text (`type="any"`, so Chat Input
  and Text Input both receive it) and reads the text of the chosen output vertex.
- Tokens are the sum of `_token_usage` over non-output vertices (Chat Output
  re-sums upstream usage). Cost uses the model selection on each vertex; one
  unpriced model makes the row's cost unknown rather than partial.

### Memory isolation

Each row's own session is the primary isolation: the engine applies the run's
session to every vertex with a `session_id`, overriding a fixed value on a
Message History component (verified by test). As defense in depth, the row
binds `set_evals_memory_isolated(True)` and `aget_messages`/`get_messages` in
`langflow.memory` return `[]` while it is set. The guard lives at the storage
read, not in components, so saved flows that embed old component code are
covered. Outside an Evals row the contextvar is unset and nothing changes.

### Early stop (`failure_breaker.py`)

When `evals_abort_after_identical_failures` consecutive rows (default 3) fail
with the same error, the run stops with status `failed` and an `error` that
names the cause, using the provider's own sentence when the error carries one
(for example a retired model). A row "fails" when the flow errored, timed out,
or an `llm_judge` call failed. Request ids, hashes and numbers are ignored when
comparing. Different errors never stop the run. `0` disables the check. Every
other row task is cancelled before the run is closed.

## Scorers (`scorers/`)

| Type | Score | Needs expected output |
|---|---|---|
| `exact_match` | 1 when equal after NFKC normalization, whitespace collapse and case folding (`config.case_sensitive` keeps case) | yes |
| `contains` | 1 when the expected text is inside the answer | yes |
| `similarity` | `difflib.SequenceMatcher` ratio, inputs capped at 2000 characters, computed off the event loop | yes |
| `llm_judge` | Structured `{score, reason}` from `config.model`, with optional `config.rubric` | no |

A scorer that cannot judge a row (no expected output) returns `value: null`
and is left out of the pass rule instead of failing the row. A scorer that
raises records `value: null` and a "Scorer failed: ..." comment; the row is
not failed by it.

The judge prompt fences the question, the expected answer and the answer as
data and tells the model to ignore instructions inside them. Output is capped by
`evals_judge_max_output_tokens`. An unparseable verdict scores `null`; there is
no regex fallback.

**Pass rule:** an errored row never passes. Otherwise the row passes when the
weighted mean of the scores that judged it reaches `pass_threshold`; when no
scorer could judge it, `passed` is `null`.

## Summary

Written at the end of a run; computed on read (never stored) while a run is
active, so the UI shows live aggregates.

```json
{
  "scores": {"exact_match": {"mean": 0.8, "p50": 1.0, "p90": 1.0}},
  "duration_ms": {"mean": 412, "p50": 300, "p90": 900},
  "tokens": {"flow": 1800, "judge": 6400, "total": 8200},
  "cost_usd": {"flow": 0.0004, "judge": 0.0021, "total": 0.0025, "complete": true},
  "pass_rate": 0.75,
  "rows": {"total": 10, "errored": 0, "decided": 8}
}
```

Percentiles are nearest-rank. `cost_usd.*` is `null` when any priced part is
unknown, so a partial total never looks complete.

## Estimate

`POST /api/v1/evaluations/estimate` with `{flow_id, dataset_id, scorers}`.

- **Flow part:** from this flow's last completed run (per-row tokens and cost,
  ×0.8 to ×1.25) when there is one; otherwise from the flow's LLM components,
  the prompt text, and the dataset's character counts (about 4 characters per
  token; answers sized from the expected outputs). Agents assume up to three
  model calls per row at the high end.
- **Judge part:** always from the model estimate, bounded by the judge's output
  cap.
- Prices come only from catalog metadata or the models.dev snapshot.
  `unpriced_models` lists models without a price; their cost is `null`.

The UI shows the range, the flow/judge breakdown and the basis, and asks for
confirmation before any run that makes model calls (`llm_calls > 0`), including
a Re-run.

## API

All routes need an authenticated user. Lists are paginated (`page`, `size`).
Domain errors map to 404 (not found or not visible; never 403, so ids stay
private), 409 (conflict) and 422 (cannot run, with `issues`).

```
Datasets (owner scope; `dataset` authz resource)
  GET    /api/v1/datasets/?search=&page=&size=
  POST   /api/v1/datasets/                          409 on a duplicate name
  GET    /api/v1/datasets/{id}
  PATCH  /api/v1/datasets/{id}
  DELETE /api/v1/datasets/{id}                      evaluations keep their results
  POST   /api/v1/datasets/{id}/duplicate            "<name> (copy)", "<name> (copy) 2", ...
  GET    /api/v1/datasets/{id}/items?search=&page=&size=   size up to 5000
  POST   /api/v1/datasets/{id}/items                1..500 items
  PATCH  /api/v1/datasets/{id}/items/{item_id}      clear_expected_output=true removes it
  POST   /api/v1/datasets/{id}/items/delete         {ids: [...]}
  POST   /api/v1/datasets/{id}/import/preview       multipart file → headers, first rows, total
  POST   /api/v1/datasets/{id}/import               file + input_column [+ expected_column] → {imported, skipped}
  GET    /api/v1/datasets/{id}/export               text/csv, formula-safe

Evaluations
  GET    /api/v1/evaluations?project_id=&flow_id=&page=&size=
  POST   /api/v1/evaluations[?run=true]             run=true starts the first run on Latest
  GET    /api/v1/evaluations/check?flow_id=&output_vertex_id=
  POST   /api/v1/evaluations/estimate
  GET    /api/v1/evaluations/{id}
  PATCH  /api/v1/evaluations/{id}
  DELETE /api/v1/evaluations/{id}                   refused while a run is active; releases retained versions
  POST   /api/v1/evaluations/{id}/runs              {flow_version_id?} → 202 run
  GET    /api/v1/evaluations/{id}/runs

Runs
  GET    /api/v1/evaluation-runs/{run_id}
  POST   /api/v1/evaluation-runs/{run_id}/cancel    409 when already finished
  GET    /api/v1/evaluation-runs/{run_id}/results?passed=&page=&size=   size up to 5000; texts are 500-character previews (`preview: true`)
  GET    /api/v1/evaluation-runs/{run_id}/results/{result_id}           one result with full texts
  GET    /api/v1/evaluation-runs/{run_id}/export    text/csv, one value and one comment column per scorer
```

### CSV import

UTF-8 only (a BOM is stripped; other encodings are rejected with a clear
message). The delimiter is taken from the header row only, among `,`, `;`, tab and `|`;
a header without any of them is a single column, so commas in the text are kept.
The first non-blank row is the header. Rows with an empty input are skipped and reported
with their row number, as are cells longer than 100,000 characters; rows past
`evals_csv_max_rows` are reported as one entry with their count. Uploads are
capped at `evals_csv_max_bytes` and parsed off the event loop. Export
prefixes a cell starting with `=`, `+`, `-` or `@` with `'`
(`langflow.utils.csv_safety.csv_safe_cell`, shared with the audit export).

## Authorization

- Datasets are a resource type (`DatasetAction`: read, write, create, delete;
  `ensure_dataset_permission`). Without a plugin the OSS floor applies: owner
  or superuser. With `LANGFLOW_AUTHZ_ENABLED=true` and only the OSS stub,
  visibility does not widen.
- Evaluations are owner-scoped; a run is readable by whoever can read its
  evaluation. Creating or duplicating a dataset checks `DatasetAction.CREATE`,
  and a duplicate lands in the caller's account. Starting a run re-checks
  `FlowAction.EXECUTE` on the flow and read on the dataset every time, so a
  user who lost access cannot start runs.
- Fetches go through `authorized_or_owner_scoped`, so a registered plugin with
  cross-user fetch can widen dataset and flow access; plugin denials (403) surface as 404; other guard errors, such as a 503 from the
  plugin, are returned unchanged.

## Lifecycle and deletion

| Event | Effect |
|---|---|
| Flow deleted | `evaluation.flow_id` and `evaluation_run.flow_version_id` set to NULL and the flow's project is frozen on the evaluation; results stay readable; Re-run is refused (422) |
| Dataset deleted | `evaluation.dataset_id` set to NULL; results keep their copies |
| Project deleted | Evaluations of the flows currently in it (and of deleted flows that were in it) are deleted with their runs and results; a flow moved to another project keeps its evaluations. A run still executing on another worker stops writing once its run row is gone |
| Evaluation deleted | Its runs and results are deleted; versions retained only for those runs are released |
| Server or pod stopped mid-run | The job is lost when it is no longer queued or in progress, or when its heartbeat is older than `background_lease_ttl_s` (a dead pod leaves its job in progress until some process restarts); the next read of the run (or the next start, delete or dataset edit that checks for active runs) marks it `failed` with "The server stopped while this run was in progress"; a run younger than 30 seconds without a job row is still launching and is left alone. Finished rows are kept; the in-flight row is not replayed |
| GDPR erase of a user | Results, runs, evaluations, items and datasets of that user are deleted; runs the user started on someone else's evaluation move to that evaluation's owner (`data_subjects/evaluation_steps.py`) |

## Settings (`LANGFLOW_` prefix)

| Setting | Default | Meaning |
|---|---|---|
| `FEATURE_EVALS` | `false` | Mounts the routes and shows the UI |
| `EVALS_MAX_ITEMS` | 1000 | Most items one run may execute |
| `EVALS_ROW_CONCURRENCY` | 2 | Rows of one run at the same time |
| `EVALS_MAX_CONCURRENCY` | 4 | Rows at the same time across all runs in a process |
| `EVALS_ROW_TIMEOUT_S` | 300 | Seconds per row (flow plus scoring) |
| `EVALS_ACTUAL_OUTPUT_MAX_CHARS` | 20000 | Output kept per result; the full output stays in the trace |
| `EVALS_CSV_MAX_ROWS` | 5000 | Rows one CSV import may add |
| `EVALS_CSV_MAX_BYTES` | 20971520 | Largest CSV upload, in bytes |
| `EVALS_JUDGE_MAX_OUTPUT_TOKENS` | 300 | Output cap per judge call |
| `EVALS_ABORT_AFTER_IDENTICAL_FAILURES` | 3 | Consecutive identical failures before a run stops; 0 never stops |

## Frontend

- Sidebar: **Datasets** and **Evaluations** under Assets, behind the flag
  (`EvalsRoute` redirects to Flows when it is off).
- Datasets and items use the shared `DataTableTab` (AG Grid), like Knowledge and
  Files: search, row action menu, multi-select delete, empty state with actions.
- CSV import: drop zone, file card, column mapping with a preview of the mapped
  columns, result summary with skipped rows.
- Evaluate: the canvas button (between Playground and Share) saves the flow and
  opens the modal; **New evaluation** on the Evaluations page opens the same
  modal with a searchable flow picker. The modal shows flow checks, the estimate
  and, for runs with model calls, a confirmation.
- Evaluation page: runs table (version, pass rate, tokens and change against
  the previous run, cost), metric cards, Passed/Failed/Errored filter, and a row
  detail dialog with the full texts and each score's reason. Active runs poll
  every 5 s.
- All strings are in the eight locale files; every screen passes the Jest axe
  and Playwright `runA11yScan` checks.

## Invariants

- A run executes exactly one pinned flow version, and editing the flow or the
  evaluation never changes a finished or running run.
- Results hold their own copy of the input and expected output.
- An evaluation row never persists chat messages and never reads stored chat
  history.
- Cost is never guessed: unknown prices make costs `null`.
- One active run per evaluation.
- Nothing in `lfx` changes behavior; `lfx serve` has no database, so the
  feature is not offered there.

## Out of scope

- Comparing two runs row by row, baselines, dashboards over time.
- Embedding similarity, latency or token thresholds as scorers, and a flow used
  as the judge.
- Importing items from chat logs; multi-turn and multi-field items.
- Resuming a run after a restart (the coordinator already skips finished rows,
  which a resume would build on).
- A shared worker queue across pods: a run executes on the pod that started it.
- Datasets and evaluations in project export and import.

## Platform compatibility

- SQLite and PostgreSQL: plain tables and JSON columns; the migration is tested
  on both (`test_no_phantom_migrations`), and child rows are deleted explicitly
  because SQLite does not enforce cascades.
- Linux, macOS, Windows: no subprocesses, paths or shell; CSV and text I/O are
  UTF-8 in memory.
- Python 3.10+: timeouts use `asyncio.wait_for`.
- Server, Docker and API share the same code; Desktop starts the same backend.
- Multi-pod: data, progress and cancel live in the database; execution stays on
  the starting pod.

## Tests

- Backend unit: `src/backend/tests/unit/services/evaluations/` (scorers, pass
  rule, CSV, summary, flow checks, estimate model, early stop).
- Backend integration: `src/backend/tests/unit/api/v1/evals/` (datasets, runs,
  memory isolation, versions, guards, cancel, timeout, restart, deletions, early
  stop, estimate, GDPR erase, a 300-row stress run). `test_llm_judge_live.py`
  needs `OPENAI_API_KEY`.
- Frontend: Jest under `evalsPage/__tests__` and `evaluateFlowModal/__tests__`;
  Playwright `tests/core/features/evals.spec.ts` (requires
  `LANGFLOW_FEATURE_EVALS=true`).
