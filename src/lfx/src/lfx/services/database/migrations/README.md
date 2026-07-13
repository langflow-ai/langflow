# lfx migration stream

This is lfx's **own** alembic lineage, independent of langflow's.

- **Version table:** `lfx_alembic_version` (distinct from langflow's `alembic_version`).
- **Scope:** only the execution-history tables lfx owns — `message`, `transaction`,
  `vertex_build` — enforced by the `include_name` / `include_object` filters in
  [`env.py`](env.py) (`LFX_MIGRATION_TABLES`).

## Why a separate stream

A bare `lfx serve` production deployment must be able to provision its schema
without langflow's 82 migrations present. The model classes are the single
source of truth (they live in `lfx.services.database.models`), so both streams
materialise the *same* target — they can only differ in staleness, which
`alembic check` catches per-stream in CI. See the "two-stream migration model"
section of `src/lfx/PLUGGABLE_SERVICES.md`.

A given physical database is owned by exactly **one** stream: the langflow
editor DB by langflow's lineage, the scaled `lfx serve` DB by this one.

## Commands

lfx does not migrate implicitly on `serve` (explicit-only policy). Provision with:

```bash
lfx db upgrade          # apply migrations to head
lfx db current          # show the current revision
lfx db check            # fail if models drift from the migrations (CI)
lfx db downgrade -1     # roll back one revision
```

## Authoring a new revision

After changing an lfx-core model:

```bash
lfx db revision -m "add message.foo" --autogenerate
```

Then **also** land the equivalent change in langflow's stream
(`src/backend/base/langflow/alembic`) — the shared model is visible to both.
