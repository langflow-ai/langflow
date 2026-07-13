# Deploying lfx as a configurable service

This directory shows how to hydrate lfx's **Tier 1** (infrastructure) and
**Tier 2** (composed) services for a production `lfx serve` deployment. It is
scoped to the two services extracted into lfx so far — the database and the
DB-backed chat memory — and the same pattern extends to the rest as they land.

## The two hydration inputs

lfx separates *which implementation* from *how it connects*:

| Input | Mechanism | What it carries | Example |
|-------|-----------|-----------------|---------|
| **Wiring** | `lfx.toml` `[services]` | which class backs each `ServiceType` | `database_service = "…:DatabaseService"` |
| **Connection / tunables** | environment (`LANGFLOW_*`) | URLs, credentials, pool sizes | `LANGFLOW_DATABASE_URL=postgresql://…` |

At boot the service manager discovers `lfx.toml` in `$LANGFLOW_CONFIG_DIR` and
selects those implementations; each service then reads its own connection
settings from the environment. Precedence is **`lfx.toml` > entry-point plugins
> built-in defaults**.

With **no `lfx.toml`**, bare lfx stays ephemeral — `NoopDatabaseService` +
`InMemoryMemoryService` — which is exactly what `lfx run` wants. Adding the
`lfx.toml` here flips the same process to persistent Postgres + DB-backed memory
without any code change. That is the editor↔production parity goal: the same
engine code, wired differently.

## Files

- [`lfx.toml`](lfx.toml) — the production wiring (database + memory).
- [`k8s/configmap.yaml`](k8s/configmap.yaml) — mounts `lfx.toml` at `/config` and
  carries non-secret tunables.
- [`k8s/secret.example.yaml`](k8s/secret.example.yaml) — shape of the Secret
  holding `LANGFLOW_DATABASE_URL` (credentials).
- [`k8s/knative-service.yaml`](k8s/knative-service.yaml) — a scale-to-zero
  gateway that mounts both and runs `lfx db upgrade` as an initContainer.

## Migrations are explicit

lfx does **not** migrate implicitly on `serve`. Provision the schema first:

```bash
export LANGFLOW_DATABASE_URL='postgresql://user:pass@host:5432/lfx'
lfx db upgrade      # apply lfx's migration stream to head
lfx db current      # confirm the head revision
```

In Kubernetes this is the initContainer (or a one-shot Job). lfx's migration
stream is **its own** alembic lineage (version table `lfx_alembic_version`),
independent of langflow's — see the two-stream model in
[`../PLUGGABLE_SERVICES.md`](../PLUGGABLE_SERVICES.md). A given physical database
is owned by exactly one stream: the langflow editor DB by langflow's lineage, the
scaled `lfx serve` DB by lfx's.

## Quick local smoke test (SQLite)

```bash
export LANGFLOW_CONFIG_DIR="$PWD/deploy"          # find lfx.toml
export LANGFLOW_DATABASE_URL="sqlite:///$PWD/lfx.db"
lfx db upgrade                                    # creates message/transaction/vertex_build
lfx serve path/to/flow.json                       # persistent chat memory over SQLite
```

Point `LANGFLOW_DATABASE_URL` at Postgres and the same commands provision and
serve against Postgres instead.
