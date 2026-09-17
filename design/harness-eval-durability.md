# Durable native Eval Suites

September 16, 2026. Branch `feat/harness-eval-durability`, based on
`5cef7a99173597a096e4a020ecf6fa20699cf568` (`feat/harness-eval-suites`).
One capability branch; no pull request.

An Eval Suite now runs in the background and keeps its progress across page
reloads and application restarts. Candidate and scorer flows execute as ordinary
Workflows jobs. Both can pause for human input. The desktop workbench shows the
current case/phase, finished cases, approval actions, cancellation and retained
evidence above the case editor.

## Contract

- `POST /api/v1/projects/{project_id}/evaluations/runs` returns **202** with a
  persistent evaluation ID. The body still contains a client-generated `run_id`,
  `expected_revision` and `expected_candidate_digest`. A response is acceptance,
  not an evaluation verdict. Retry the same ID and original expected identity to
  retrieve that run, even after the saved suite changes. A different identity
  under that ID is rejected.
- `GET .../runs` returns the caller's latest 20 runs; `GET .../runs/{run_id}` reads
  one retained run. The response includes `status`, `passed`, `cancel_requested`,
  `error`, and `result` with the frozen suite, completed case evidence and current
  child (`job_id`, `phase`, `case_id`). The UI polls active runs after reload.
- A suspended parent exposes `pending_approval` with the existing child ID,
  candidate/scorer phase, case ID and actual Workflows human-input request.
  Submit the advertised decision through the existing
  `POST /api/v2/workflows/{child_job_id}/resume` API with its `request_id`.
  Duplicate/stale decisions return 409. The existing Human Input card renders
  the permitted actions and fields; evaluation does not invent another protocol.
- `POST .../runs/{run_id}/cancel` returns **202** after persisting cancellation
  intent. Poll until terminal. The coordinator stops the current child and does
  not launch another. Cancellation is cooperative for active tools; it does not
  undo completed effects. A cancelled or incomplete evaluation cannot pass.
- Reads and cancellation enforce project permission and job ownership. Execution
  rechecks the active account, project write access and current execution rights.
  Candidate and scorer dependency policies still use the Workflows host gates.

Only `completed` with `result.complete == true` and `passed == true` is passing.
A normal negative judgment completes with `passed == false`. Execution failure,
interruption, timeout or cancellation ends the parent incomplete, preserving
finished case evidence. These records cannot be used as comparable completed
runs. Provider costs remain unknown and a required cost measurement fails closed.

## Recovery and execution boundaries

The evaluation row commits its frozen suite, candidate archive and scorer archive
before acceptance. Parent progress and each new child row/checkpoint commit in
one transaction, guarded by a progress version. Competing coordinators and
cancellation cannot overwrite newer progress or commit two children for one
step. No new database table or second execution engine is introduced.

The coordinator is a lightweight task in the existing background service. It
observes child jobs and dispatches the next case/phase through the existing
bounded worker pool. Waiting for approval occupies no workflow worker. The
ordinary orphan sweep excludes these recoverable evaluation coordinators.

Queued children use the existing Workflows recovery path. An atomic execution
claim prevents a child from running twice when a startup sweep finds a job that
is also still waiting in another process's local queue. The claim records the
worker heartbeat with the transition. Cold startup also initializes the standard
Workflows frame source without requiring an earlier HTTP execution request.

Completed cases are preserved without executing them again. Suspended children
resume the original checkpoint, candidate and scorer, independent of later draft
edits or removal/replacement of the source mount. A missing, corrupt or disabled
candidate does not fall back to a draft. An interrupted **in-flight** child is
failed, not automatically replayed: its tools may already have acted. This does
not promise exactly-once external side effects or arbitrary mid-tool recovery.

## Supported profile and limits

- Authenticated authoring host with the developer Workflows API enabled and the
  **in-process** Workflows backend. New submissions reject the scaled/Redis
  profile rather than accepting work that this coordinator cannot run there.
  Serving end-user identity mode remains unsupported for private Eval Suites.
- At most 10 cases, processed sequentially within each suite. Children share the
  host's existing worker concurrency limit. There is no distributed evaluation
  admission quota or suite-wide elapsed deadline in this slice.
- Each active candidate/scorer pass has a 300-second execution ceiling, lowered
  by a smaller configured `background_job_timeout`. Resuming starts a fresh pass.
  Queueing and human waiting are outside that execution clock. Suspended jobs
  inherit the existing `background_input_deadline_s` policy; its default can wait
  indefinitely. Operators must choose a deadline appropriate to their installation.
- The case's `latency_ms` is elapsed time from candidate child creation through
  completion, including queueing and approval waiting. The form labels this
  explicitly. An elapsed budget assesses the measurement; it is not a kill timer.
- Existing 48 KB retained response and 64 KiB-character scorer-input bounds remain.
  Provider cost accounting, portable suite archives and evaluation-gated releases
  remain separate work. External evaluation integrations are postponed.

Live-provider acceptance and verification on the intended deployed topology
remain production gates. Local PostgreSQL and concurrent-service tests do not
satisfy those gates. Deployment topology work remains deferred by the user.

## Verification

- **25 evaluation API tests passed**: 12 existing regression cases, a scaled-profile
  refusal check, and six
  lifecycle scenarios on each of SQLite and PostgreSQL. These exercise real
  graphs, authorization, jobs, checkpoints and APIs; the provider is deterministic.
  Coverage includes candidate approval after service restart and changed drafts,
  a fresh process preserving a completed case and resuming the next approval,
  scorer approval with the original recorded response, private cancellation,
  interrupted work without replay, and two services racing queued recovery.
- The queued recovery test first observed nine model turns instead of six (a
  repeated research workflow), and passes with exactly six after the execution
  claim. Cold recovery without an HTTP-initialized runner first timed out and
  passes after lazy host initialization. These are retained regression cases.
- **72 Workflows/job regression tests passed**, with 10 environment-dependent
  skips, covering the existing background service, job service and candidate API.
- **70 frontend tests passed** across the Eval Suite, lifecycle controls, Harness
  form and existing Human Input card. Coverage includes page-reload polling,
  exact child/request IDs, cancellation, unconfirmed decisions without automatic
  replay or lost form input, stale approvals, comparison and existing form behavior.
- Typecheck still reports **255 diagnostics**, byte-identical to the preceding
  Eval Suite branch's captured typecheck. It is not a clean repository typecheck.
- Desktop smoke uses an isolated database and deterministic provider: restored
  one completed case plus a pending second-case approval after a page reload,
  then approved it through the real UI and observed the retained result.
- PostgreSQL lifecycle tests are included in the existing migration-validation
  CI job. Local verification used PostgreSQL 17.11; this branch's CI run has not
  been claimed as passing.

Reproduce from the repository root:

```sh
# Without this variable, PostgreSQL variants are explicitly skipped. The API
# fixture creates/drops a fresh database; the account needs CREATEDB.
export LANGFLOW_TEST_DATABASE_URI='postgresql+psycopg://USER@127.0.0.1:PORT/postgres'
LANGFLOW_UPDATE_STARTER_PROJECTS=false uv run --no-sync pytest \
  src/backend/tests/unit/api/v1/test_eval_durability.py \
  src/backend/tests/unit/api/v1/test_eval_suites.py -q

LANGFLOW_UPDATE_STARTER_PROJECTS=false uv run --no-sync pytest \
  src/backend/tests/unit/services/background_execution \
  src/backend/tests/unit/services/jobs \
  src/backend/tests/unit/api/v2/test_workflow_candidates.py -q

cd src/frontend
npx jest src/pages/MainPage/pages/harnessPage/__tests__/eval-progress.test.tsx \
  src/pages/MainPage/pages/harnessPage/__tests__/eval-suite.test.tsx \
  src/pages/MainPage/pages/harnessPage/__tests__/harness-page.test.tsx \
  src/components/core/chatComponents/__tests__/HumanInputCard.test.tsx --runInBand
```
