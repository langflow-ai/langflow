# langflow-services ownership

This distribution ships the standalone Python package `services`.

## Dependency direction
`langflow-base` -> `langflow-services` (`services`) -> `lfx`

Runtime modules under `src/langflow-services/src/services` MUST NOT import
`langflow.*`. Public `langflow.services.*` paths are thin one-way re-exports
owned by `langflow-base`.

## Package layout (invariant)

Every Langflow-owned concrete `ServiceType` lives in its own subpackage:

```
services/<service_name>/
  __init__.py
  service.py      # primary Service implementation(s)
  factory.py      # ServiceFactory for this type
  ...             # helpers / backend modules owned by this service
```

`<service_name>` is derived from `ServiceType.value` by stripping the trailing
`_service` suffix (for example `JOB_SERVICE = "jobs_service"` → `jobs/`,
`SHARED_COMPONENT_CACHE_SERVICE` → `shared_component_cache/`).

### Packaging and discovery
The single `langflow-services` wheel follows the consolidated `lfx-bundles`
pattern:

- `[project.optional-dependencies]` exposes a **service-shell** extra per
  service subpackage when useful as an ownership marker (`job-queue` →
  `services/job_queue`, etc.). Empty shells mean the default path needs no
  extra third-party deps.
- Use **`<service>-<backend>`** extras only when a service has distinct
  selectable backends with different deps (do not invent them across the board):
  - `database-sqlite` / `database-postgresql` (no empty `database` shell)
  - `tracing-*` / `tracing-all`
  - `storage-s3`, `cache-redis`, `job-queue-redis`, `task-celery`,
    `variable-kubernetes`
- Deployment adapters are **not** generic “adapters-*” extras. Nested source
  `services/adapters/deployment/watsonx_orchestrate` maps to the flat extra
  `deployment-watsonx-orchestrate` (PEP 508 cannot express
  `[adapters][deployment][…]` nesting).
- `langflow-services[production]` covers every Langflow-owned service: production
  backends where they exist (Postgres, Redis cache/job-queue, S3, Celery),
  otherwise the default/only implementation (including DB-backed `variable`;
  Kubernetes variables stay opt-in via `variable-kubernetes`). Tracing
  providers and deployment adapters stay opt-in (`tracing-all`,
  `deployment-watsonx-orchestrate`).
- `langflow-services[all]` aggregates every service shell plus every selectable
  backend/provider (including `tracing-all`). `production` is a separate
  convenience aggregate and is not nested under `all`.
- The `lfx.service-packages` entry-point group advertises
  `services.bootstrap:register_all_service_factories`.
- `langflow-base` depends on `langflow-services[database-sqlite,memory-base]` by
  default and re-exports backend extras (`[postgresql]`, `[redis]`,
  `[aioboto3]`, `[production]`, tracing, `[ibm-watsonx-clients]` →
  `deployment-watsonx-orchestrate`, etc.).

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

### Allowed at `services/` root (shared infrastructure only)
- `__init__.py`
- `bootstrap.py` — factory / adapter registration
- `deps.py` — internal getters used by concrete services
- `factory.py` — concrete `ServiceFactory` + dependency inference
- `providers.py` — host-injected CRUD / hooks

### Explicit exceptions
- **LFX-owned service types** (not extracted here): `settings`, `executor`,
  `mcp_composer`, `extension_events`
- **Non-service adapters**: `adapters/` (deployment plugin registry; not a
  `ServiceType`)

Do **not** add new top-level `services/*.py` modules for implementations, and
do **not** split one `ServiceType` across multiple top-level packages.

## Owned by LFX
- `Service`, `ServiceType`, factory ABC, manager, protocols, registries
- settings / executor / extension_events / mcp_composer
- canonical ORM models in `lfx.services.database.models`

## Owned by this package (`services.*`)
Concrete `Service` implementations, concrete factories, provider backends,
implementation-owned helpers, and registration bootstrap (`services.bootstrap`).

Host seams are injected via:
- `services.providers.register_crud` / `register_hook`
- `services.auth.service.set_jit_user_defaults_hook` / `set_get_user_by_flow_id_hook`
- `services.database.factory.set_alembic_path_provider`
- `services.memory_base.kb_hooks.set_kb_helpers`

These hooks are registered by `langflow.services.utils.register_all_service_factories()`
before factories are created. Callers that construct services without that bootstrap
must either register the same hooks or pass explicit constructor kwargs (for
`DatabaseService` alembic paths). Partial init without hooks is unsupported for
auth CRUD, Celery, audit cleanup, and KB helpers.

## Owned by langflow-base
- `langflow.services.*` compatibility re-exports
- database CRUD / model shims / utils / session helpers
- Alembic
- authorization guards/fetch/listing/audit/...
- deps.py host DI, host lifecycle (superuser, mappers)
- FastAPI routes and API helpers
