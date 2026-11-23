# Startup retention regression

Baseline: release-1.14.0 at 68e8338f3a6063c696fe25a1814cb15fc00c88ac.
Change: PR #16435. Python 3.13.0, SQLAlchemy 2.0.58, SQLModel 0.0.50,
aiosqlite 0.22.1, asyncpg 0.32.0, PostgreSQL 15.18 (Homebrew), macOS arm64.

Run against a disposable PostgreSQL instance (the test creates/drops unique schemas):

```sh
LANGFLOW_TEST_DATABASE_URI=postgresql+asyncpg://localhost:55449/postgres \
uv run pytest src/backend/tests/unit/services/database/test_startup_retention.py \
  src/backend/tests/unit/services/database/test_vertex_builds.py -q --no-cov
```

The new tests use real application models and cleanup functions. For the negative
control, replace only services/utils.py with the baseline version, run the startup
retention tests, then restore the patched file. Raw pytest output is in before.txt
and after.txt. Baseline: 12 failed, 9 passed, 1 skipped. Patched: 30 passed, 1 skipped
(includes 9 existing runtime build-retention checks). Wall times are test-runner
output, not a performance benchmark. Both cleanup functions still execute one
DELETE statement per invocation; transaction framing belongs to the caller.

Transactions retain the configured newest N records **per flow**. Builds preserve
the existing global N-record budget and now delete by build_id, with timestamp/ID
tie-breaking. Runtime's additional per-vertex pruning remains in log_vertex_build;
startup does not introduce a new per-vertex deletion policy. Limits 0, 1, 3, and 6
cover empty retention and below/above-budget histories. These count settings have
no documented disable sentinel; 0 continues to retain zero records. Negative
limits are not assigned a new meaning by this change.

The caller initialize_services still owns the cleanup transaction. The tests
verify rollback, two committed cleanups, exact survivors, mixed/tied timestamps,
reused component IDs, independent flows, and a PostgreSQL insert committed after
the cleanup snapshot. SQLite serializes writers, so that MVCC case is skipped.
This is snapshot cleanup: concurrent writers may temporarily exceed a cap and
later runtime/startup cleanup enforces it. No new locks or retry semantics.

No schema migration or historical row rewrite is required. Deploy normally;
startup applies configured limits. Already-deleted history cannot be recovered.
Rolling back restores the prior cleanup algorithm, including its deletion bug.
