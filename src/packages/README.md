# Langflow Modules

This directory contains the modular Python packages that make up Langflow:

## Structure

### `/packages/core` (lfx)
- **Package**: `lfx` (Langflow Executor)
- **Purpose**: Lightweight CLI tool for executing and serving Langflow AI flows
- **Key Features**:
  - Core graph processing and execution
  - Component system
  - CLI interface
  - Template management
  - Serialization and I/O operations

### `/packages/base` (langflow-base)
- **Package**: `langflow-base`
- **Purpose**: Base Langflow package with web application
- **Key Features**:
  - FastAPI web application
  - API endpoints
  - Database models and migrations (Alembic)
  - Services layer
  - Authentication and security
  - Integration with langchain ecosystem

### `/packages/langflow`
- **Package**: `langflow`
- **Purpose**: Main orchestration package
- **Key Features**:
  - Version management
  - Package coordination
  - Entry point for full Langflow application

## Dependencies

```
langflow (main package)
    ├── langflow-base (web application and services)
    │   └── lfx (core execution engine)
    └── lfx (can also be used standalone)
```

## Development

Each module has its own `pyproject.toml` for dependency management and can be developed independently while maintaining clear interfaces between packages.

### Building Packages

```bash
# Build individual packages
cd src/packages/core && hatch build
cd src/packages/base && hatch build
cd src/packages/langflow && hatch build
```

### Testing

```bash
# Run tests for individual packages
cd src/packages/core && pytest tests/
cd src/packages/base && pytest  # Tests location TBD
```

## Migration Notes

This structure was migrated from:
- `src/core/` → `src/packages/core/`
- `src/backend/base/` → `src/packages/base/`
- `src/backend/langflow/version/` → `src/packages/langflow/version/`

The namespace package compatibility layer in `langflow/__init__.py` ensures backward compatibility with existing imports.