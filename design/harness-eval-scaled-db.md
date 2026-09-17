# Eval Suites on the database-backed Workflows queue

September 16, 2026. Branch `feat/harness-eval-scaled-db`, stacked on
`5c30b23769` (`feat/harness-eval-durability`). One capability branch, no PR.

The branch ports the scoped changes from
[PR #13508](https://github.com/langflow-ai/langflow/pull/13508) at
`bee10cf935cb7f1b0c3fad68b9f4dfbd04343ca8`, then connects Eval Suite coordination
to that backend. The source PR and other branches are unchanged. The port is
commit `a8a0413838`; the following commit contains evaluation integration and
its tests. This is a source port, not a merge of the entire release branch.

## Behavior

Set `LANGFLOW_BACKGROUND_BACKEND=scaled` on the API and worker processes.
The shared database's `QUEUED` Workflows rows are the queue; `langflow worker`
claims and executes them. PostgreSQL is the multi-host database. SQLite is
supported for a single host. No Redis broker is needed, and setting the legacy
`LANGFLOW_JOB_QUEUE_TYPE=redis` does not select scaled background execution.

The existing evaluation and Workflows API contracts are unchanged:

- Submitting an evaluation commits its frozen candidate, scorer and suite before
  returning 202. Each child job, candidate checkpoint and parent progress update
  commit together. Two API coordinators cannot commit two children for one step.
- Candidate and scorer flows run in worker processes as ordinary Workflows jobs.
  The API coordinates progress without executing the flow or holding a worker
  while a human decides. Startup starts coordination even before the first
  execution request, including on a replacement API process.
- Resume retains the existing child/request IDs, authorization and conflict
  checks. The decision is durable before the child is made claimable again.
  Cancelled or failed evaluations cannot pass or launch another case.
- Workers reconstruct encrypted globals, retained candidate archives and graph
  checkpoints from the database. Editing drafts or removing the original source
  artifact does not change an accepted run. Scorer execution still consumes the
  recorded candidate response.
- Both backends apply the smaller of the host timeout and the server-owned
  evaluation ceiling (300 seconds per active pass). Resuming starts a new pass;
  queue and human waiting time are outside that clock. The worker now also passes
  the configured human-input deadline to the existing runner.

## Host requirements and limits

API replicas and workers need the same database and `LANGFLOW_SECRET_KEY`,
compatible runtime/component versions, provider credentials, and consistent
authorization, resource and candidate-disable policies. The initial submission
still requires an executable mounted candidate on the authoring API. Already
accepted work carries its archive in database checkpoints; a worker does not need
that original file mounted to reconstruct it.

At least one API process must remain available to advance evaluations between
children and enforce human-input deadlines. If all APIs stop, workers can finish
already queued children; further coordination waits for API startup. At least one
worker must be running to drain queued children. Each worker loop executes one job
at a time; scale the worker processes for capacity.

The existing authoring-only identity boundary, ten-case limit, response bounds
and sequential case execution remain. There is no distributed evaluation
admission quota, suite-wide elapsed deadline or measured provider cost accounting.
An interrupted in-flight child fails with `worker_lost`; evaluations do not opt
into replay of potentially effectful provider/tool calls. This is not an
exactly-once guarantee for external effects.

The database queue retains #13508's polling and contention tradeoffs. This branch
does not add queue retention, fleet metrics or `SKIP LOCKED`. Production sizing
and verification on the actual deployment topology remain open. Live-provider
acceptance remains open. External evaluation-platform integrations remain deferred.

## Migrations

The port retains #13508's `f1c5e7a9b3d0` job-claim index migration unchanged.
`d6a4e8b2c091` joins it with the existing project-type head `b8e1c47d3f56`.
Neither existing revision is rewritten. The resulting history has one head.

## Verification

All tests use real graphs, jobs, checkpoints, authorization and database access;
evaluation tests replace only the external model provider.

| Selection | Local result |
|---|---|
| Scaled Eval API and separate worker process scenarios | 16 passed across SQLite and PostgreSQL |
| Existing Eval Suite, durability and candidate API scenarios | 45 passed, including the corrected zero-timeout regression rerun |
| Existing background real-service scenarios | 288 passed |
| Background service/job tests, including the real worker subprocess tests | 93 passed |
| Additional competing human-deadline watchdog scenario | 2 passed, SQLite and PostgreSQL |
| Runtime settings selection and composition | 45 passed using the repository's `LFX_TEST_ALLOW_LANGFLOW=1` option |
| Migration execution and model consistency | 22 passed; one PostgreSQL-only case skipped on its SQLite parameter |

The new cases exercise competing API coordinators and workers, idempotent
submission, candidate and scorer approvals, private cancellation, both execution
timeout sources, human-input expiry, and API/worker replacement with frozen
artifacts. The worker-process tests run the real CLI in another OS process with
no candidate mount. They retain a completed case across replacement and assert
that a killed in-flight provider call is not repeated.

Tests first reproduced the scaled-mode rejection, missing worker evaluation
timeout and missing worker human-input deadline. The common timeout helper's
zero-ceiling behavior was caught by an existing regression and corrected before
delivery. No frontend source changed in this slice. CI includes the PostgreSQL
scaled evaluation and separate-worker tests; a hosted CI result is not claimed.

Reproduce the new evaluation checks from the repository root:

```sh
export LANGFLOW_TEST_DATABASE_URI='postgresql+psycopg://USER@HOST:PORT/postgres'
LANGFLOW_UPDATE_STARTER_PROJECTS=false uv run --no-sync pytest \
  src/backend/tests/unit/api/v1/test_eval_scaled.py \
  src/backend/tests/unit/api/v1/test_eval_scaled_process.py -q
```

The test database account needs permission to create disposable databases.
Without that URI the PostgreSQL parameters explicitly skip. Local validation used
PostgreSQL 17.11 on a disposable cluster, not the user's application database.
