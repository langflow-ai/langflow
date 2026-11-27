# Vertex build flow-scoped read index

## What changed

The `vertex_build` table carries a composite index on `(flow_id, id, timestamp)`,
named `ix_vertex_build_flow_id_id_timestamp`.

With `flow_id` first, the index narrows both queries to one flow's rows without
scanning the table. `id` second lets the flow-scoped read group by vertex id in
index order and look up each vertex's newest row by `(flow_id, id, timestamp)`,
and lets the per-vertex trim read one vertex's builds directly. The flow-scoped
read still sorts its small result by `timestamp` across vertex ids. The
per-vertex trim reads rows in `timestamp` order, and an incremental sort handles
the `build_id` tie-break.

Before this change the table carried only its primary key on `build_id` and
`ix_vertex_build_job_id` on `job_id`. Neither `flow_id` nor `id` was indexed.

`VertexBuildTable.__table_args__` declares the index and the migration
`b3e7d1f5a9c2` creates it, so the ORM metadata and the migrated schema agree.
`alembic check` reports no difference between them.

## Queries the index serves

`get_vertex_builds_by_flow_id` in
`services/database/models/vertex_builds/crud.py` reads one flow's build history.
It groups the flow's rows by vertex `id` to find each vertex's newest timestamp,
joins that back to the table, and orders the result by `timestamp`. Without the
index each call scans the whole table twice.

The per-vertex trim in `log_vertex_build`, in the same module, runs on every
logged build. It deletes a vertex's builds beyond `max_vertex_builds_per_vertex`,
selecting the newest rows for one `(flow_id, id)` pair ordered by
`timestamp DESC, build_id DESC`. Without the index each logged build scans the
whole table twice.

## Queries the index does not serve

The global trim in `log_vertex_build` deletes builds beyond
`max_vertex_builds_to_keep` across all flows. `clean_vertex_builds` in
`services/utils.py` does the same on a schedule. Neither filters on `flow_id`, so
both sort the whole table by `timestamp` and the index does not apply to them.
Both are unaffected by this index. Their timings are the same with and without
it.

Retention correctness is tracked in #16409.

## Migration behavior

The migration `b3e7d1f5a9c2_index_vertex_build_flow_reads.py` follows
`a1b2c9d3e4f5_index_message_history_reads.py`. It is an `EXPAND` phase migration
and its `down_revision` is `7a4c2e9b6d15`.

`upgrade()` returns early when the `vertex_build` table is absent. It reads the
table's current index names through `sa.inspect` and creates the index only when
it is missing, so running the upgrade again over an existing index does nothing.

On PostgreSQL the migration builds the index with `postgresql_concurrently=True`
inside `op.get_context().autocommit_block()`. A plain `CREATE INDEX` holds a write
lock for the whole build, and a rolling deploy leaves an old pod logging builds
while the new one migrates. `CREATE INDEX CONCURRENTLY` cannot run inside the
migration transaction, which is why the autocommit block is required.

A cancelled concurrent build leaves an index that the inspector still reports but
the planner never uses. Before creating the index, the migration queries
`pg_index` for a matching entry with `indisvalid` false and drops it
concurrently. Without that step a retry treats the dead index as present and
skips it.

On other dialects the migration calls `op.create_index` directly.

`downgrade()` mirrors `upgrade()`. It returns early when the table is absent or
the index is not present, drops the index concurrently on PostgreSQL, and drops
it directly elsewhere. It removes only the index; `vertex_build` rows survive a
downgrade and a later upgrade.

## Measurements

The measurements below come from the code in this change, the model index and
migration `b3e7d1f5a9c2`, on November 18, 2026. The schema is the one
`alembic upgrade head` builds, in a throwaway PostgreSQL 17.12 container on
Ubuntu 26.04 under WSL2, with `shared_buffers=256MB`, `work_mem=16MB` and
`track_io_timing=on`. The seed is 8 flows, 25 vertex ids per flow, and
timestamps spread over 30 days.

Each query ran under `EXPLAIN (ANALYZE, BUFFERS)` 15 times per state, alternating
between the migrated schema and the same table with the index dropped. Deletes
ran inside a transaction that rolls back, so the row count stays fixed. The
figure is PostgreSQL's reported execution time, in milliseconds.

| Query | Rows | Index dropped | Index present | Ratio |
| --- | ---: | ---: | ---: | ---: |
| `get_vertex_builds_by_flow_id` | 3,000 | 1.111 | 0.477 | 2.33x |
| Per-vertex trim | 3,000 | 0.920 | 0.085 | 10.82x |
| `get_vertex_builds_by_flow_id` | 60,000 | 20.171 | 2.662 | 7.58x |
| Per-vertex trim | 60,000 | 21.612 | 0.523 | 41.32x |

The write path calls `log_vertex_build` once per build at the default 3,000-row
retention cap, which runs the insert, the per-vertex trim, the global trim and
the commit. It ran 150 times per state, in blocks of 10, alternating.

| Measurement | Index dropped | Index present |
| --- | ---: | ---: |
| Median | 11.784 | 10.770 |
| Mean | 12.621 | 11.342 |
| 10th percentile | 10.893 | 9.906 |
| 90th percentile | 16.012 | 13.899 |

The index adds no measurable write cost at the default cap, and the read gain
does not carry over to the whole write path: the global trim dominates each
logged build, and the index does not serve it.

These are single-client measurements on one machine with both datasets resident
in cache. They are not a production guarantee.

## Verification

```bash
uv run --no-sync pytest \
  src/backend/tests/unit/alembic/ \
  src/backend/tests/unit/services/database/test_vertex_builds.py \
  src/backend/tests/unit/services/database/test_vertex_builds_flow_reads.py
```

On SQLite this reports 368 passed and 201 skipped. Setting
`LANGFLOW_TEST_DATABASE_URI` to a PostgreSQL 17 instance activates the
parametrized `db_url` fixture's postgres cases and reports 553 passed and
16 skipped.

`src/backend/tests/unit/alembic/test_vertex_build_flow_index_migration.py`
covers the index on both backends: the ORM metadata declares it with the right
columns, the upgrade creates it, a second upgrade over the existing index does
nothing, a downgrade removes it, and `vertex_build` rows survive both
directions. A PostgreSQL-only test interrupts a concurrent build, leaves an
invalid index, and asserts that the next upgrade replaces it with a valid one.

`src/backend/tests/unit/services/database/test_vertex_builds_flow_reads.py`
covers the read contract: `get_vertex_builds_by_flow_id` returns the newest
build per vertex in timestamp order, keeps two flows that share vertex ids
apart, and excludes flows owned by another user.
