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
- `src/lfx/services/` - Minimal built-in service implementations
- `src/backend/base/langflow/services/` - Full-featured Langflow services

## Architecture Benefits

The pluggable service system provides:
- ✅ **Automatic discovery** - Services found from config files, decorators, or entry points
- ✅ **Lazy instantiation** - Services created only when first accessed
- ✅ **Dependency injection** - Service dependencies resolved automatically
- ✅ **Lifecycle management** - Proper teardown when service manager shuts down
- ✅ **Flexibility** - Swap implementations without code changes (via config)
