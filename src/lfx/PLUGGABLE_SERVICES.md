# Pluggable Services System

LFX now supports a pluggable service architecture that allows you to customize and extend service implementations without modifying core code.

## Overview

The pluggable services system supports **three** discovery mechanisms:

1. **Decorator Registration** - Services self-register when imported (best for library use)
2. **Configuration Files** - Explicit service mapping in config files (best for CLI use)
3. **Entry Points** - Python package entry points (best for distributable plugins)

**Discovery order** (services are discovered in this order, with later sources able to override earlier ones):
1. Entry points (lowest priority)
2. Decorator registration
3. Configuration files (highest priority)

## Adapter Registries (Service-Scoped Plugin Registries)

LFX also supports **adapter registries** -- collections of swappable implementations that share the same protocol.
Use them when you need to choose between several adapters at runtime (for example, deployment adapters keyed as `local` and `remote` in your own config/plugin setup).

### Service vs Adapter Registry

| Concern | Service | Adapter registry |
|---|---|---|
| **Lookup key** | `ServiceType` enum | String key within a registry |
| **Cardinality** | One implementation per type | Many adapters per registry |
| **Type safety** | Protocol per `ServiceType` | Protocol-typed registry per `AdapterType` |
| **Example** | `storage_service` | `deployment` adapters by key, e.g. `"local"`, `"remote"` |

### Core API

Each adapter type exposes a typed accessor in `lfx.services.deps`:

```python
from lfx.services.deps import get_deployment_adapter

adapter = get_deployment_adapter("local")   # returns None if key is unknown
```

Adapters are created lazily on first access and cached as singletons — subsequent calls with the same key return the same instance.
Discovery config is resolved internally (settings `config_dir` when available, otherwise current working directory).
The key (`"local"` above) is an example; adapter keys are fully user-defined.

### Registering Adapters

#### Option A: Decorator Registration

```python
from lfx.services import register_adapter
from lfx.services.adapters.schema import AdapterType

@register_adapter(AdapterType.DEPLOYMENT, "local")
class LocalAdapter:
    ...
```

The decorator registers the class immediately at import time (same pattern as `@register_service` for top-level services).
Defaults to `override=True`; set `override=False` to keep an existing key untouched.
`"local"` is only an example adapter key.

#### Option B: Configuration Files

`lfx.toml` (preferred when both files exist):

```toml
[deployment.adapters]
local = "my_package.deployment:LocalAdapter"
remote = "my_package.deployment:RemoteAdapter"
```

`pyproject.toml`:

```toml
[tool.lfx.deployment.adapters]
local = "my_package.deployment:LocalAdapter"
remote = "my_package.deployment:RemoteAdapter"
```

`local`/`remote` are illustrative keys; choose names that match your adapter set.

#### Option C: Entry Points

Entry-point groups follow the naming convention `lfx.<adapter_type>.adapters` (e.g. `lfx.deployment.adapters`).

```toml
[project.entry-points."lfx.deployment.adapters"]
local = "my_package.deployment:LocalAdapter"
remote = "my_package.deployment:RemoteAdapter"
```

Entry-point names are adapter keys and are fully user-defined.

### Adapter Discovery and Precedence

Adapter registration mirrors the top-level `@register_service` model:

1. **Decorator registration** — immediate at import time (`override=True` by default)
2. **Entry points** (`override=False`) — discovered during `discover()`
3. **Config files** (`override=True`) — discovered during `discover()`

Effective precedence (what wins when multiple sources register the same key):

Config files > Decorators > Entry points

Config files are intended as deploy-time overrides and take highest priority.

Discovery is **one-time per registry instance**. Subsequent calls to `discover()` are no-ops.

Entry-point groups and config section paths are derived from the `AdapterType` value automatically (e.g. `lfx.deployment.adapters` and `[deployment.adapters]`).

### Adapter Instance Lifecycle

- Adapter **classes** are discovered and registered first; **instances** are created separately
- Instances are created lazily on first `get_<type>_adapter()` call
- One instance is cached per adapter key (singleton per key)
- All cached adapter instances are torn down automatically during service manager shutdown

### Recommended File Structure

When adapters are part of core LFX, prefer namespacing them under `services/adapters`:

```text
lfx/services/
  adapters/
    deployment/
      __init__.py
      base.py
      service.py
      exceptions.py
      schema.py
```

This keeps top-level services (DI-managed singletons) separate from adapter implementations (keyed registries with multiple implementations per type).

### Payload Contract Ownership (Adapters vs API Layer)

Payload contracts intentionally split ownership across layers:

- **LFX owns shared slot primitives and slot taxonomy**:
  - `lfx.services.adapters.payload` defines shared primitives (`PayloadSlot`, `ProviderPayloadSchemas`)
  - each adapter domain in lfx defines canonical slot names once (for example deployment slots in
    `lfx.services.adapters.deployment.payloads`)
- **Adapters (LFX side) own adapter-facing payload models**:
  - adapters populate their `*PayloadSchemas` registry with adapter-side models
- **API hosts (for example Langflow) own API-facing payload models**:
  - API mapper layers populate their own API payload registries
  - API slots may differ from adapter slots when API-specific references or reshaping are required

This boundary allows both layers to share one slot taxonomy while keeping API exceptions and
transformation logic outside adapter implementations.

Deployment is the concrete example in this repository:

- LFX defines deployment slot taxonomy and adapter registry (`DeploymentPayloadFields` / `DeploymentPayloadSchemas`)
- Langflow defines deployment API registry (`DeploymentApiPayloads`) and mapper behavior

### Error Handling Behavior

- Invalid import paths (missing `module:ClassName`) are ignored with warning logs
- Entry point load failures do not stop discovery from other sources
- Malformed TOML is ignored with warning logs
- Missing configured sections are treated as empty configuration

### Registry Uniqueness

- Exactly one registry exists per `AdapterType`

## Quick Start

### For CLI Users (Config File Approach)

Create an `lfx.toml` in your project root:

```toml
[services]
database_service = "langflow.services.database.service:DatabaseService"
storage_service = "langflow.services.storage.local:LocalStorageService"
cache_service = "langflow.services.cache.service:ThreadingInMemoryCache"
```

Then run:
```bash
lfx serve my_flow.json
```

Services will be automatically discovered from:
1. The current working directory (looking for `lfx.toml` or `pyproject.toml`)
2. Or the config directory specified in your settings

**Note**: Service discovery happens automatically on first service access.

### For Library Users (Decorator Approach)

In your service module:

```python
from lfx.services import register_service
from lfx.services.base import Service
from lfx.services.schema import ServiceType

@register_service(ServiceType.DATABASE_SERVICE)
class MyDatabaseService(Service):
    name = "database_service"

    def __init__(self, settings_service):
        self.settings = settings_service.settings
        self.set_ready()

    async def teardown(self) -> None:
        # Cleanup logic
        pass
```

Simply importing this module will register the service.

### For Plugin Developers (Entry Points Approach)

In your plugin's `pyproject.toml`:

```toml
[project.entry-points."lfx.services"]
database_service = "my_plugin.services:MyDatabaseService"
storage_service = "my_plugin.services:MyStorageService"
```

When your package is installed, LFX will automatically discover these services.

## Configuration Details

### Config File Locations

LFX searches for configuration in this order:

1. `./lfx.toml` (project-specific config)
2. `./pyproject.toml` under `[tool.lfx.services]` (Python project integration)

### Config File Format

**Standalone `lfx.toml`:**

```toml
[services]
database_service = "package.module:ClassName"
storage_service = "package.module:ClassName"
```

**In `pyproject.toml`:**

```toml
[tool.lfx.services]
database_service = "package.module:ClassName"
storage_service = "package.module:ClassName"
```

### Service Keys

Service keys **must** match `ServiceType` enum values exactly:

- `database_service`
- `auth_service`
- `storage_service`
- `cache_service`
- `chat_service`
- `session_service`
- `task_service`
- `store_service`
- `variable_service`
- `telemetry_service`
- `tracing_service`
- `state_service`
- `job_queue_service`
- `shared_component_cache_service`
- `mcp_composer_service`
- `transaction_service`

**Important:** `settings_service` is **not pluggable** and cannot be overridden. It is always created using the built-in factory and provides the foundational configuration for all other services.

## Creating Custom Services

### Step 1: Implement the Service Class

```python
from lfx.services.base import Service

class MyCustomStorageService(Service):
    name = "storage_service"  # Must match ServiceType value

    def __init__(self, settings_service):
        """Dependencies are auto-injected based on __init__ signature."""
        self.settings = settings_service
        self.set_ready()

    async def save_file(self, flow_id: str, file_name: str, data: bytes) -> None:
        # Your implementation
        pass

    async def get_file(self, flow_id: str, file_name: str) -> bytes:
        # Your implementation
        pass

    async def teardown(self) -> None:
        # Cleanup when service manager shuts down
        pass
```

### Step 2: Register the Service

**Option A: Decorator (recommended for libraries)**

```python
from lfx.services import register_service
from lfx.services.schema import ServiceType

@register_service(ServiceType.STORAGE_SERVICE)
class MyCustomStorageService(Service):
    ...
```

**Option B: Config File (recommended for CLI users)**

Add to `lfx.toml`:
```toml
[services]
storage_service = "my_package.services:MyCustomStorageService"
```

**Option C: Entry Points (recommended for plugins)**

Add to your `pyproject.toml`:
```toml
[project.entry-points."lfx.services"]
storage_service = "my_package.services:MyCustomStorageService"
```

### Step 3: Use the Service

```python
from lfx.services.deps import get_storage_service

storage = get_storage_service()
await storage.save_file("flow_123", "data.json", b'{"key": "value"}')
```

## Dependency Injection

Services can depend on other services. Dependencies are resolved automatically based on `__init__` parameter type hints:

```python
from lfx.services.base import Service
from lfx.services.settings.service import SettingsService

class MyDatabaseService(Service):
    name = "database_service"

    def __init__(self, settings_service: SettingsService, cache_service: CacheService):
        """
        Dependencies are auto-injected:
        - settings_service: SettingsService will be created first
        - cache_service: CacheService will be created second
        """
        self.settings = settings_service.settings
        self.cache = cache_service
        self.set_ready()
```

The ServiceManager will:
1. Detect dependencies from type hints
2. Create dependencies first (in topological order)
3. Pass them to your service's `__init__`

## Override Priority

When multiple registration mechanisms provide the same service, **config files have highest priority**:

1. **Entry Points** (lowest priority) - discovered first, use `override=False`
2. **Decorator Registration** (medium priority) - run when modules import, use `override=True` by default
3. **Config Files** (highest priority) - discovered last, use `override=True`

Example:
```python
# Entry point registers: MyPluginStorage (override=False, won't replace existing)
# Decorator registers: CustomStorageService (override=True, replaces entry point)
# Config file registers: LocalStorageService (override=True, replaces decorator)

# Result: LocalStorageService wins (config file is highest priority)
```

You can control decorator override behavior:

```python
@register_service(ServiceType.STORAGE_SERVICE, override=False)
class MyService(Service):
    ...  # Won't override if already registered (e.g., from config file loaded earlier)
```

**Note**: In practice, decorators typically run during module import before `discover_plugins()` is called, but config files are explicitly designed to override decorators for deployment-time flexibility.

## Testing Custom Services

```python
import pytest
from lfx.services.manager import get_service_manager
from lfx.services.schema import ServiceType

def test_custom_service():
    # Register your test service
    manager = get_service_manager()
    manager.register_service_class(
        ServiceType.STORAGE_SERVICE,
        MyTestStorageService,
        override=True
    )

    # Use the service
    from lfx.services.deps import get_storage_service
    storage = get_storage_service()

    assert isinstance(storage, MyTestStorageService)
```

## Troubleshooting

### Settings Service Cannot Be Overridden

**Error:** `ValueError: Settings service cannot be registered via plugins`

**Cause:** You attempted to register `settings_service` in a config file or via decorator.

**Solution:** Remove `settings_service` from your config. The settings service is foundational and always uses the built-in implementation. Its `config_dir` is used to discover other plugins.

### Service Not Found

**Error:** `NoServiceRegisteredError: No factory registered for database_service`

**Solutions:**
1. Check service key matches `ServiceType` enum value exactly
2. Verify import path is correct: `"module.path:ClassName"`
3. Ensure config file is in the correct location:
   - If settings service exists: `{settings.config_dir}/lfx.toml`
   - Otherwise: `./lfx.toml` or `./pyproject.toml` in current directory
4. Enable debug logging: `export LANGFLOW_LOG_LEVEL=DEBUG`

### Import Errors

**Error:** `ModuleNotFoundError: No module named 'langflow'`

**Solutions:**
1. Ensure langflow is installed: `pip install langflow`
2. Check if module path in config is correct
3. Verify the package is importable: `python -c "import langflow.services.database"`

### Circular Dependencies

Services should not depend on each other in a circular way:

❌ **Bad:**
```python
class ServiceA(Service):
    def __init__(self, service_b: ServiceB): ...

class ServiceB(Service):
    def __init__(self, service_a: ServiceA): ...
```

✅ **Good:**
```python
class ServiceA(Service):
    def __init__(self, settings: SettingsService): ...

class ServiceB(Service):
    def __init__(self, settings: SettingsService, service_a: ServiceA): ...
```

## Examples

See:
- `lfx.toml.example` - Example configuration file showing Langflow service registration
- `src/lfx/services/` - Minimal built-in service implementations (auth, telemetry, tracing, variable, storage, etc.)
  - Auth: `lfx.services.auth.base` (BaseAuthService) and `lfx.services.auth.service` (AuthService). Use `get_auth_service()` from `lfx.services.deps`. Override with `auth_service = "langflow.services.auth.service:AuthService"` in config for full JWT/API key auth.
- `src/backend/base/langflow/services/` - Full-featured Langflow services

## Architecture Benefits

The pluggable service system provides:
- ✅ **Automatic discovery** - Services found from config files, decorators, or entry points
- ✅ **Lazy instantiation** - Services created only when first accessed
- ✅ **Dependency injection** - Service dependencies resolved automatically
- ✅ **Lifecycle management** - Proper teardown when service manager shuts down
- ✅ **Flexibility** - Swap implementations without code changes (via config)
