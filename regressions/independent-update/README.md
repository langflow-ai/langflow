# Independent job payload UPDATE audit (#16404)

Baseline: release-1.14.0 at 68e8338f3a6063c696fe25a1814cb15fc00c88ac.
The implementation changes only JobService._set_live_payload, used by
set_live_result and set_live_error in background_execution/runner.py. Each call
already commits its own scope before returning. Its sole UPDATE checks job ID,
live status, and optional lease owner atomically. There are no ORM flush hooks
or other reads/writes in that scope. The caller's later status transition is
already a separate transaction. The helper returns the same affected-row bool.

## Other candidates

- API-key accounting remains coupled to user/auth-policy checks, maintenance
  state, and legacy hash backfill. Its lost-increment fix is separately tracked
  in #16304 / #16319. Splitting authentication would change its failure boundary.
- Job creation reads authorization context and uses deduplication/advisory locks;
  status updates currently read the row. Those scopes remain transactional.
- Message writes validate executor/ownership and support multiple rows; their
  rollback boundary remains transactional.
- Checkpoint upserts and other job writes need a separate caller audit.
- #16554 implements audited READ autocommit in lfx. This change adds no read
  scope or checkout listeners and does not modify those files. It addresses a
  small, independently reviewable portion of #16404 rather than closing it.

## Persistence and compatibility

A fresh connection is used for each operation. PostgreSQL READ COMMITTED uses
DBAPI AUTOCOMMIT. The durable statement commit remains; explicit BEGIN/COMMIT
framing is removed. Driver failures are propagated without automatic retries:
a network failure or cancellation after execution may have persisted the write.
A later Python failure cannot roll it back. Repeating these payload assignments
is idempotent while the status/owner predicates continue to match.

SQLite and non-default isolation use an explicit transaction. SQLAlchemy's
initialized default, engine-configured isolation override, and per-connection
execution options determine eligibility without an isolation-probe query (with
asyncpg that probe itself starts BEGIN/SHOW/ROLLBACK). The engine override uses
SQLAlchemy 2.x's `_on_connect_isolation_level`; if unavailable, the helper fails
closed to a transaction. This is an audited helper, not a SQL sandbox: structured
UPDATE objects may contain expressions/subqueries and only reviewed callsites
should use it. Applications that change session isolation using raw SQL must
continue using transactional scopes rather than this opt-in path.

Connection release resets isolation. Tests prove a subsequent ordinary transaction
can still roll back, on success and after a failed statement. Tests also cover
before/after execution failures and cancellation, retry, missing jobs, live and
terminal statuses, ownership, a concurrent lease change, independent concurrent
payload columns, and both configured-isolation paths. SQLite, PostgreSQL/asyncpg,
and PostgreSQL/psycopg are exercised. No migration or data rewrite is required.
Rollback is an ordinary code revert restoring explicit transactions.

## Reproduce the measurement

Environment: macOS arm64, Python 3.13.0, PostgreSQL 15.18, SQLAlchemy 2.0.58,
SQLModel 0.0.50, asyncpg 0.32.0. Enable `log_statement=all` and
`log_line_prefix='%m [%p] %a '` on a disposable local PostgreSQL instance.
Then, from the repository root with project dependencies installed:

```sh
PYTHONPATH=src/backend/base:src/lfx/src:src/sdk/src uv run python \
  regressions/independent-update/measure.py \
  --url postgresql+asyncpg://localhost:55449/postgres \
  --server-log /tmp/langflow-retention-postgres.log
```

The script loads the actual baseline method AST from the exact Git revision and
compares it with the patched method. Both pools are warmed before 10 interleaved
samples per method. It only deletes its own seeded job afterward. samples.json
contains all durations and raw server statement lines. The baseline emits 30
statements (10 BEGIN, 10 UPDATE, 10 COMMIT); the patch emits 10 UPDATE statements.
Thus each warm call removes two explicit control commands while retaining its
durable commit. Prepared-statement protocol messages and cold connection setup
are not counted as SQL statements; these are not total network packet counts.

The recorded local median was 1.704 ms before and 1.084 ms after. Shared-host
loopback timings are exploratory, not a production speed claim or an endpoint
benchmark. The correctness tests and SQL command counts are separate evidence.

```sh
LANGFLOW_TEST_DATABASE_URI=postgresql+asyncpg://localhost:55449/langflow_validation \
PYTHONPATH=src/backend/base:src/lfx/src:src/sdk/src uv run pytest \
  src/backend/tests/unit/services/database/test_independent_update.py \
  src/backend/tests/unit/services/jobs/test_jobs_service.py \
  src/backend/tests/unit/services/jobs/test_terminal_write_race.py -q --no-cov
```

Use a UTF-8 PostgreSQL database. Tests create/drop unique schemas; SQLite uses
isolated files. Install psycopg to exercise that driver; it skips if unavailable.

Final focused validation: **103 passed, 2 skipped** (SQLite-only skips for the
PostgreSQL isolation configurations). Raw output: tests.txt. The existing
job-service/terminal-race checks also passed in the broader run (129 passed,
1 skipped before adding the engine-constructor isolation cases). Ruff 0.13.3
format/check and git diff --check passed. Full repository suite not run.
