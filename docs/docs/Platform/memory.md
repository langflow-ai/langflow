---
title: Memory
slug: /platform-memory
---

The default storage option in Langflow is a [SQLite](https://www.sqlite.org/) database that can be found at `langflow/src/backend/base/langflow/langflow.db`.

## Configure external memory

To replace the default Langflow SQLite database with another database, modify the following environment variables and start Langflow with them.

```
LANGFLOW_DATABASE_URL=postgresql://user:password@localhost:5432/langflow
```

## Configure the external database connection

The `LANGFLOW_SAVE_DB_IN_CONFIG_DIR` option, when set to `true`, will save the database in the Langflow configuration directory defined by `LANGFLOW_CONFIG_DIR`. This means the database will persist across installations and allow you to share the database across reinstalls and between virtual environments.

```
LANGFLOW_DATABASE_CONNECTION_RETRY=false
LANGFLOW_SAVE_DB_IN_CONFIG_DIR=false
```

The following settings allow you to fine-tune your database connection pool and timeout settings:

```
LANGFLOW_DB_CONNECTION_SETTINGS='{"pool_size": 20, "max_overflow": 30, "pool_timeout": 30, "pool_pre_ping": true, "pool_recycle": 1800, "echo": false}'
LANGFLOW_DB_CONNECT_TIMEOUT=20
```

- `pool_size`: Maximum number of database connections to keep in the pool (default: 20)
- `max_overflow`: Maximum number of connections that can be created beyond the pool_size (default: 30)
- `pool_timeout`: Number of seconds to wait before timing out on getting a connection from the pool (default: 30)
- `pool_pre_ping`: If true, the pool will test connections for liveness upon each checkout (default: true)
- `pool_recycle`: Number of seconds after which a connection is automatically recycled (default: 1800, or 30 minutes)
- `echo`: If true, SQL queries will be logged for debugging purposes (default: false)
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

