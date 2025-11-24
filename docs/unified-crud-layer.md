# Unified Database CRUD Operations Layer

## Overview

This document describes the unified CRUD (Create, Read, Update, Delete) operations layer implemented to decouple database models from API and component code. This abstraction enables:

1. **Consistent database access patterns** across the codebase
2. **Easier testing** through mockable interfaces
3. **Future pluggable services layer** support

## Architecture

The unified CRUD layer is located in `src/backend/base/langflow/services/database/crud.py` and provides:

- `BaseCRUD`: Generic base class for common CRUD operations
- Specialized CRUD classes for each model type (MessageCRUD, TransactionCRUD, etc.)
- Singleton instances ready to use

## Usage

### Importing CRUD Operations

```python
from langflow.services.database.crud import (
    message_crud,
    transaction_crud,
    vertex_build_crud,
    flow_crud,
    user_crud,
    api_key_crud,
    variable_crud,
    file_crud,
    folder_crud,
)
```

### Basic CRUD Operations

All CRUD instances support these common operations:

#### Get by ID

```python
async def get_record(session: AsyncSession, record_id: UUID):
    record = await message_crud.get(session, record_id)
    return record
```

#### Create

```python
async def create_record(session: AsyncSession):
    message_data = MessageBase(
        text="Hello",
        sender="User",
        sender_name="Test User",
        session_id="session_123",
    )
    new_message = await message_crud.create(session, obj_in=message_data)
    return new_message
```

#### Update

```python
async def update_record(session: AsyncSession, record_id: UUID):
    message = await message_crud.get(session, record_id)
    if message:
        updated = await message_crud.update(
            session,
            db_obj=message,
            obj_in={"text": "Updated text"}
        )
        return updated
```

#### Delete

```python
async def delete_record(session: AsyncSession, record_id: UUID):
    await message_crud.delete(session, id=record_id)
```

#### Get Multiple with Filters

```python
async def get_filtered_records(session: AsyncSession):
    messages = await message_crud.get_multi(
        session,
        skip=0,
        limit=100,
        order_by="timestamp",
        sender="User"
    )
    return messages
```

### Specialized Operations

Each CRUD class may have specialized methods for common operations:

#### MessageCRUD

```python
# Get messages by session ID
messages = await message_crud.get_by_session_id(
    session,
    "session_123",
    skip=0,
    limit=50
)

# Get messages by flow ID
messages = await message_crud.get_by_flow_id(
    session,
    flow_id,
    order_by="timestamp"
)

# Get distinct session IDs
sessions = await message_crud.get_sessions(session, flow_id=flow_id)

# Delete messages by session ID
await message_crud.delete_by_session_id(session, "session_123")

# Delete messages by flow ID
await message_crud.delete_by_flow_id(session, flow_id)
```

#### TransactionCRUD

```python
# Get transactions by flow ID
transactions = await transaction_crud.get_by_flow_id(
    session,
    flow_id,
    limit=1000
)

# Delete transactions by flow ID
await transaction_crud.delete_by_flow_id(session, flow_id)
```

#### VertexBuildCRUD

```python
# Get vertex builds by flow ID (with deduplication)
builds = await vertex_build_crud.get_by_flow_id(
    session,
    flow_id,
    limit=1000
)

# Delete vertex builds by flow ID
await vertex_build_crud.delete_by_flow_id(session, flow_id)
```

#### FlowCRUD

```python
# Get flow by endpoint name
flow = await flow_crud.get_by_endpoint_name(session, "my-endpoint")

# Get flows by user ID
flows = await flow_crud.get_by_user_id(
    session,
    user_id,
    skip=0,
    limit=100
)
```

#### UserCRUD

```python
# Get user by username
user = await user_crud.get_by_username(session, "john_doe")

# Get all superusers
superusers = await user_crud.get_superusers(session)

# Update last login timestamp
await user_crud.update_last_login(session, user_id)
```

#### ApiKeyCRUD

```python
# Get API keys by user ID
api_keys = await api_key_crud.get_by_user_id(session, user_id)

# Get API key by key value
api_key = await api_key_crud.get_by_key(session, "sk-...")
```

#### VariableCRUD

```python
# Get variables by user ID
variables = await variable_crud.get_by_user_id(session, user_id)

# Get variable by name
variable = await variable_crud.get_by_name(
    session,
    user_id,
    "MY_VARIABLE"
)
```

## Migration Guide

### Before (Direct Model Usage)

```python
from langflow.services.database.models.message.model import MessageTable
from sqlmodel import select

async def get_messages(session: AsyncSession, session_id: str):
    stmt = select(MessageTable).where(MessageTable.session_id == session_id)
    result = await session.exec(stmt)
    return list(result.all())
```

### After (CRUD Layer)

```python
from langflow.services.database.crud import message_crud

async def get_messages(session: AsyncSession, session_id: str):
    return await message_crud.get_by_session_id(session, session_id)
```

## Benefits

### 1. Decoupling

API and component code no longer needs to import database models directly:

```python
# ❌ Old way - tightly coupled to model
from langflow.services.database.models.message.model import MessageTable
db_message = await session.get(MessageTable, message_id)

# ✅ New way - uses abstraction
from langflow.services.database.crud import message_crud
db_message = await message_crud.get(session, message_id)
```

### 2. Consistency

All database operations follow the same patterns:

```python
# All CRUD instances have the same interface
message = await message_crud.get(session, id)
flow = await flow_crud.get(session, id)
user = await user_crud.get(session, id)
```

### 3. Testability

CRUD operations can be easily mocked in tests:

```python
from unittest.mock import AsyncMock

async def test_endpoint(monkeypatch):
    mock_crud = AsyncMock()
    mock_crud.get.return_value = test_message
    monkeypatch.setattr("module.message_crud", mock_crud)
    # Test code...
```

### 4. Future Extensibility

The CRUD layer provides a clear interface for future enhancements:
- Pluggable database backends
- Caching strategies
- Audit logging
- Permission checks
- Rate limiting

## Design Principles

1. **Single Responsibility**: Each CRUD class handles operations for one model type
2. **Consistency**: Common operations have the same interface across all CRUD classes
3. **Extensibility**: Specialized operations can be added to specific CRUD classes
4. **Type Safety**: Generic types ensure compile-time type checking
5. **Lazy Loading**: Models are imported lazily to avoid circular dependencies

## Best Practices

### DO

✅ Use CRUD instances for all database operations in API endpoints and services
✅ Use specialized methods when available (e.g., `get_by_session_id`)
✅ Pass the database session explicitly to CRUD methods
✅ Handle None returns appropriately (e.g., when record not found)

### DON'T

❌ Import database model tables in API endpoints or components
❌ Bypass the CRUD layer for database operations
❌ Create new database sessions inside CRUD methods (pass them as parameters)
❌ Add business logic to CRUD classes (keep them focused on database operations)

## Legacy Code

Some legacy modules still import database models directly:

- Model definition files (`model.py`)
- Specialized CRUD functions in model directories (now wrapper functions)
- Test files that need to construct model instances

These imports are acceptable in these contexts, but new code should use the unified CRUD layer.

## Future Enhancements

The unified CRUD layer enables these future improvements:

1. **Pluggable Database Backends**: Support multiple database types
2. **Caching Layer**: Transparent caching of frequently accessed data
3. **Event System**: Emit events on CRUD operations for audit logs
4. **Multi-tenancy**: Add tenant-aware filtering to all operations
5. **Soft Deletes**: Implement soft delete functionality across all models
6. **Bulk Operations**: Optimize batch create/update/delete operations
