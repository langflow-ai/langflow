# langflow-services

Concrete Langflow service implementations for the LFX pluggable service layer.

This distribution ships the standalone Python package `langflow_services`. It sits
between the LFX plugin kernel and the Langflow FastAPI host:

```
langflow-base  ->  langflow-services (`langflow_services`)  ->  lfx
```

`langflow-base` depends on this package and exposes public `langflow.services.*`
compatibility re-exports. Runtime modules under `langflow_services` must never
import `langflow.*`.

## Install

Pulled automatically with Langflow / `langflow-base`. For a standalone install:

```bash
pip install langflow-services
# or with production backends (Postgres, Redis, S3, Celery, …)
pip install "langflow-services[production]"
# or every service shell + selectable backend/provider
pip install "langflow-services[all]"
```

### Extras

`[project.optional-dependencies]` follows the consolidated `lfx-bundles` pattern:

- **Service-shell** extras mark ownership of a service subpackage when useful
  (`job-queue` → `langflow_services/job_queue`, etc.). Empty shells mean the
  default path needs no extra third-party deps.
- **`<service>-<backend>`** extras only when a service has distinct selectable
  backends with different deps (do not invent them across the board):
  - `database-sqlite` / `database-postgresql` (no empty `database` shell)
  - `tracing-*` / `tracing-all`
  - `storage-s3`, `cache-redis`, `job-queue-redis`, `task-celery`,
    `variable-kubernetes`
- Deployment adapters are **not** generic `adapters-*` extras. Nested source
  `langflow_services/adapters/deployment/watsonx_orchestrate` maps to the flat
  extra `deployment-watsonx-orchestrate` (PEP 508 cannot express
  `[adapters][deployment][…]` nesting).
- `langflow-services[production]` covers every Langflow-owned service: production
  backends where they exist (Postgres, Redis cache/job-queue, S3, Celery),
  otherwise the default/only implementation (including DB-backed `variable`;
  Kubernetes variables stay opt-in via `variable-kubernetes`). Tracing providers
  and deployment adapters stay opt-in (`tracing-all`,
  `deployment-watsonx-orchestrate`).
- `langflow-services[all]` aggregates every service shell plus every selectable
  backend/provider (including `tracing-all`). `production` is a separate
  convenience aggregate and is not nested under `all`.

`langflow-base` depends on `langflow-services[database-sqlite,memory-base]` by
default and re-exports backend extras (`[postgresql]`, `[redis]`, `[aioboto3]`,
`[production]`, tracing, `[ibm-watsonx-clients]` →
`deployment-watsonx-orchestrate`, etc.).

## Discovery and bootstrap

The `lfx.service-packages` entry-point group advertises:

```toml
langflow-services = "langflow_services.bootstrap:register_all_service_factories"
```

The host loads this registrar after registering CRUD, Alembic, version, and
lifecycle hooks. Callers that construct services without that bootstrap must
either register the same hooks or pass explicit constructor kwargs (for
`DatabaseService` alembic paths). Partial init without hooks is unsupported for
auth CRUD, Celery, audit cleanup, and KB helpers.

Host seams are injected via:

- `langflow_services.providers.register_crud` / `register_hook`
- `langflow_services.auth.service.set_jit_user_defaults_hook` /
  `set_get_user_by_flow_id_hook`
- `langflow_services.database.factory.set_alembic_path_provider`
- `langflow_services.memory_base.kb_hooks.set_kb_helpers`

These hooks are registered by
`langflow.services.utils.register_all_service_factories()` before factories are
created.

## Versioning

`langflow-services` versions on the same public axis as `langflow` and `lfx`
(`1.x.y`). `langflow-base` remains on the `0.x.y` remap of that line for
**stable** releases (`make patch v=1.11.0` → services/lfx/langflow `1.11.0`,
base `0.11.0`). `langflow-base` depends on `langflow-services~=1.11.0`.

**Nightlies** remap `langflow-base` onto the root `1.x` axis so
`langflow` / `langflow-base` / `langflow-services` share one `.devN` tag
(e.g. `1.11.0.devN`). `lfx` and `langflow-sdk` keep their own nightly
counters (`lfx_nightly_tag.py` / `sdk_nightly_tag.py`).

## Package layout

Every Langflow-owned concrete `ServiceType` lives in its own subpackage:

```
langflow_services/<service_name>/
  __init__.py
  service.py      # primary Service implementation(s)
  factory.py      # ServiceFactory for this type
  ...             # helpers / backend modules owned by this service
```

`<service_name>` is derived from `ServiceType.value` by stripping the trailing
`_service` suffix (for example `JOB_SERVICE = "jobs_service"` → `jobs/`,
`SHARED_COMPONENT_CACHE_SERVICE` → `shared_component_cache/`).

### Backend variants stay nested

Concrete backends remain **inside** the owning service subpackage. Do not
promote them to top-level packages or separate distributions:

- `database` → `database-sqlite` / `database-postgresql`
- `storage/local.py`, `storage/s3.py` → extra `storage-s3`
- `task/backends/anyio.py`, `task/backends/celery.py` → extra `task-celery`
- `variable/kubernetes.py` → extra `variable-kubernetes`
- `tracing/<provider>.py` → `tracing-*` extras
- `cache` Redis / in-memory → extra `cache-redis` when Redis is selected
- `memory_base` Chroma stack → service extra `memory-base`
- `adapters/deployment/watsonx_orchestrate/` → `deployment-watsonx-orchestrate`

### Allowed at `langflow_services/` root (shared infrastructure only)

- `__init__.py`
- `bootstrap.py` — factory / adapter registration
- `deps.py` — internal getters used by concrete services
- `factory.py` — concrete `ServiceFactory` + dependency inference
- `providers.py` — host-injected CRUD / hooks

Do **not** add new top-level `langflow_services/*.py` modules for
implementations, and do **not** split one `ServiceType` across multiple
top-level packages.

## Ownership and boundaries

### Owned by LFX

- `Service`, `ServiceType`, factory ABC, manager, protocols, registries
- settings / executor / extension_events / mcp_composer
- canonical ORM models in `lfx.services.database.models`

### Owned by this package (`langflow_services.*`)

Concrete `Service` implementations, concrete factories, provider backends,
implementation-owned helpers, and registration bootstrap
(`langflow_services.bootstrap`).

### Owned by langflow-base

- `langflow.services.*` compatibility re-exports
- database CRUD / model shims / utils / session helpers
- Alembic
- authorization guards/fetch/listing/audit/...
- deps.py host DI, host lifecycle (superuser, mappers)
- FastAPI routes and API helpers

### Explicit exceptions

- **LFX-owned service types** (not extracted here): `settings`, `executor`,
  `mcp_composer`, `extension_events`
- **Non-service adapters**: `adapters/` (deployment plugin registry; not a
  `ServiceType`)

### Dependency direction (invariant)

Runtime modules under `src/langflow-services/src/langflow_services` MUST NOT
import `langflow.*`. Public `langflow.services.*` paths are thin one-way
re-exports owned by `langflow-base`.
