# Migration rehearsal fixtures

Tooling for rehearsing a whole-instance migration: moving a Langflow instance's data
onto a different deployment, or converting its database from SQLite to Postgres.

Not related to `scripts/migrate/`, which checks alembic revisions and bundle
changelogs. This directory is about moving an instance's *data*.

## Why a fixture instead of a real instance

A migration that loses data usually loses it silently. The database and the things
outside it disagree, and nothing raises: a `file` row pointing at no object, a
knowledge base row naming a store the vectors already left, a role assignment that
never compiled into a policy rule, a credential that decrypts to an empty string.

A large instance full of ordinary rows will pass a migration that is broken. So this
seeds a small instance where **every row exists to trip a specific failure**, and each
fixture is commented in `seed_instance.py` with what it catches.

## Usage

Run from the repository root so the venv resolves. Seed both engines: SQLite and
Postgres fail differently, and a converter has to survive both.

```bash
KEY=$(python -c "import base64; print(base64.urlsafe_b64encode(b'x'*32).decode())")

LANGFLOW_DATABASE_URL=sqlite:////tmp/fx/src.db \
LANGFLOW_CONFIG_DIR=/tmp/fx/cfg \
LANGFLOW_KNOWLEDGE_BASES_DIR=/tmp/fx/kb \
LANGFLOW_SECRET_KEY=$KEY \
uv run --no-project python scripts/migration_rehearsal/seed_instance.py \
    --chunks 300 --manifest /tmp/fx/manifest.json
```

Point it at an empty database. It refuses to run against one that already holds the
fixture superuser rather than failing on a unique constraint.

`LANGFLOW_SECRET_KEY` must be a valid Fernet key, meaning 32 url-safe base64-encoded
bytes. Any other 32-character string raises at seed time, when the first credential is
encrypted.

The script builds the schema through `initialize_database()`, the same path startup
uses, so alembic stamps a revision and seeds its own rows. It then writes a manifest
naming what it created, so a test can assert what survived a migration.

## What gets seeded, and why

| Fixture | What it catches |
| --- | --- |
| All content owned by one superuser | `teardown_superuser` deleting credentials, files and folders on SQLite while orphaning flows |
| Custom role parented on a system role, and a second parented on the first | Realigning system role ids fails once any row references one, since `parent_role_id` has no `ON UPDATE CASCADE`. The two-level chain means remapping has a hierarchy to carry |
| Role assignments on a system and a custom role | System role ids are generated per install, so a carried assignment points at a role the target does not have |
| Shares targeting a user and a team | `resource_id` and `target_id` are polymorphic with no foreign key, so stale values insert cleanly and grant nothing |
| Six encrypted columns across five tables | `variable.value`, `apikey.api_key`, `user.store_api_key`, `folder.auth_settings` and `mcp_server.config` are Fernet under `LANGFLOW_SECRET_KEY`; `sso_config.client_secret_encrypted` is an AES-256-GCM envelope keyed by HKDF off the same secret. A wrong key returns `""` rather than raising | <!-- pragma: allowlist secret -->
| Knowledge base with empty `model_selection` | Embedding resolution silently falls back to a default, so the row reports a model it may never have used |
| Knowledge base naming a stubbed backend | `BackendType` still carries `astra` and `mongodb`, so the row parses and then fails at backend construction |
| Knowledge base with 300 real vectors in a local Chroma store | Enough to force batched reads, so count reconciliation and partial-read behaviour get exercised. The store's `count()` matches the row's cached `chunks`, so a reconciliation run starts clean |
| Memory base with ingestion records | Cursors advance only after a confirmed vector write, so records marked ingested are never reprocessed |
| Suspended job with a checkpoint | Resume state, not history. Dropping it makes a paused run unresumable |
| Nested folders | The self-referential foreign key, which forces parents before children |
| `file` rows with absolute and logical paths | Both shapes occur in practice, and an absolute local path is meaningless against object storage. The logical row has real bytes on disk; the absolute row is left dangling deliberately |
| Two policy bundle revisions | Append-only history rather than a singleton, with the active pointer referencing it |
| Non-default provider allowlist, `enforce_sso` on | Rows both a source and a target seed. Skipping them silently resets customer configuration |

## Three differences between the engines

All three were found by running this against each, and all three affect any converter.

**Postgres enforces enum membership; SQLite does not.** `flow_type_enum`,
`job_status_enum`, `access_type_enum` and others are real types on Postgres and free
text on SQLite. A value SQLite accepted can fail only at conversion time, and only on
the rows that carry it, so a small sample can pass while a real database stops partway.

**Postgres returns UUID objects where SQLite returns strings.** Anything comparing ids
across the two engines has to coerce, or it silently matches nothing. The manifest
round-trips every id through `UUID` so both engines emit one spelling.

**Ids must be bound with a type, not as strings.** `sa.Uuid` stores 32-char undashed
hex on SQLite. A dashed string bound through `text()` lands verbatim, so the same
column ends up holding two spellings and no typed lookup matches a seeded row.
Postgres normalizes both, which hides it there. Every id here binds as a `UUID`
object through a typed `bindparam`.

## The manifest

Besides naming what was seeded, the manifest carries `expected_failures`: the rows
seeded to fail a check on purpose, with the reason. A rehearsal needs that to tell an
intended negative, like the knowledge base on a stubbed backend, from a real one.
