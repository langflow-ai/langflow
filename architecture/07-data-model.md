# 7. Data Model (core tables)

Persistence uses **SQLModel** (Pydantic + SQLAlchemy) with **Alembic** migrations in `src/backend/base/langflow/alembic/versions/`. SQLite is the default; Postgres is supported in production.

```mermaid
erDiagram
    USER ||--o{ FLOW : owns
    USER ||--o{ APIKEY : has
    USER ||--o{ VARIABLE : has
    FLOW ||--o{ FLOWVERSION : versions
    FLOW ||--o{ MESSAGE : produces
    FLOW ||--o{ VERTEXBUILD : logs

    FLOW {
        uuid id PK
        string name
        string description
        string icon
        json data "graph nodes+edges"
        bool is_component
        string endpoint_name
        bool webhook
        bool mcp_enabled
        enum access_type "PRIVATE|PUBLIC"
        uuid user_id FK
    }
    USER { uuid id PK
           string username
           string hashed_password }
    APIKEY { uuid id PK
             string name
             string hashed_key }
    MESSAGE { uuid id PK
              string sender
              text content
              uuid flow_id FK }
    VERTEXBUILD { uuid id PK
                  string vertex_id
                  json artifacts
                  uuid flow_id FK }
```

## The `Flow` table is the keystone

The most important column is **`data` (JSON)** — it stores the entire graph (nodes, positions, edges, parameter values) as a single document. This means:

- Saving a flow is one row write.
- Versioning is a snapshot copy.
- The execution engine doesn't need a schema migration when you add a new component type.

The trade-off: rich queries over flow content require JSON operators, not relational joins. That's deliberate — the relational layer tracks *flows as artifacts*, while the engine treats the JSON as the source of truth.

## Other key columns on `Flow`

| Column | Meaning |
|---|---|
| `endpoint_name` | Custom URL slug used for public execution endpoints. |
| `webhook` | If true, the flow accepts webhook triggers. |
| `mcp_enabled` | If true, the flow is exposed as an MCP tool. |
| `access_type` | `PRIVATE` or `PUBLIC`. Controls auth requirements at run time. |
| `is_component` | Distinguishes reusable sub-components from standalone flows. |

## Auxiliary tables

- **`User` / `APIKey`** — authentication.
- **`Variable`** — global key/value store available to components at run time.
- **`Message`** — chat history per flow / session.
- **`VertexBuild`** — per-vertex execution log (artifacts, errors). Drives the Playground inspector and observability exports.
- **`FlowVersion`** — versioned snapshots of `Flow.data`.

## Migrations

Alembic migrations live alongside the models:

```
src/backend/base/langflow/alembic/
  env.py
  versions/
    20XX_..._add_xyz.py
```

Use `make alembic-revision message="..."` to scaffold and `make alembic-upgrade` to apply.
