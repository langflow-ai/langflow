---
title: Memory
slug: /memory
---

The default storage option in Langflow is a [SQLite](https://www.sqlite.org/) database located at `langflow/src/backend/base/langflow/langflow.db`.

## Configure external memory

To replace the default Langflow SQLite database with another database, modify the `LANGFLOW_DATABASE_URL` and start Langflow with this value.

```
LANGFLOW_DATABASE_URL=postgresql://user:password@localhost:5432/langflow
```

For an example, see [Configure an external PostgreSQL database](/configuration-custom-database).

## Configure the external database connection

The following settings allow you to fine-tune your database connection pool and timeout settings:

```
LANGFLOW_DB_CONNECTION_SETTINGS='{"pool_size": 20, "max_overflow": 30, "pool_timeout": 30, "pool_pre_ping": true, "pool_recycle": 1800, "echo": false}'
LANGFLOW_DB_CONNECT_TIMEOUT=20
```

- `pool_size`: Maximum number of database connections to keep in the pool (default: 20)
- `max_overflow`: Maximum number of connections that can be created beyond the pool_size (default: 30)
- `pool_timeout`: Number of seconds to wait before timing out on getting a connection from the pool (default: 30)
- `pool_pre_ping`: If true, the pool tests connections for liveness upon each checkout (default: true)
- `pool_recycle`: Number of seconds after which a connection is automatically recycled (default: 1800, or 30 minutes)
- `echo`: If true, SQL queries are logged for debugging purposes (default: false)
- `LANGFLOW_DB_CONNECT_TIMEOUT`: Maximum number of seconds to wait when establishing a new database connection (default: 20)

## Cache memory

Langflow provides multiple caching options that can be configured using the `LANGFLOW_CACHE_TYPE` environment variable.

| Type | Description | Storage Location | Persistence |
|------|-------------|------------------|-------------|
| `async` (default) | Asynchronous in-memory cache | Application memory | Cleared on restart |
| `memory` | Thread-safe in-memory cache | Application memory | Cleared on restart |
| `disk` | File system-based cache | System cache directory* | Persists after restart |
| `redis` | Distributed cache | Redis server | Persists in Redis |

*System cache directory locations:
- Linux/WSL: `~/.cache/langflow/`
- macOS: `/Users/<username>/Library/Caches/langflow/`
- Windows: `%LOCALAPPDATA%\langflow\langflow\Cache`

