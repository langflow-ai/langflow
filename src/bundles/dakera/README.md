# lfx-dakera

Dakera persistent memory components as a standalone [Langflow](https://github.com/langflow-ai/langflow)
Extension Bundle.

[Dakera](https://dakera.ai) is a self-hosted memory server that gives agents **persistent,
decay-weighted vector recall** across sessions: memories are importance-scored and decay over
time, so stale context stops competing with fresh, relevant facts.

## Component

**Dakera Memory** — one node that speaks the full Dakera memory API. A **Mode** dropdown selects
the operation and the node shows only the fields relevant to it:

| Mode | Description | Endpoint |
|------|-------------|----------|
| **Recall** | Decay-weighted semantic recall (importance + recency aware) | `POST /v1/memory/recall` |
| **Search** | Filterable browse by tags / importance range / sort order | `POST /v1/memory/search` |
| **Store** | Persist a memory with importance, tags, TTL and metadata | `POST /v1/memory/store` |
| **Get** | Fetch a single memory by ID | `GET /v1/memory/get/{id}` |
| **Update** | Patch content / importance / tags / metadata | `PUT /v1/memory/update/{id}` |
| **Forget** | Delete by ID, tags, session, or importance threshold | `POST /v1/memory/forget` |

Recall and Search return a `DataFrame` of ranked memories; Store / Get / Update return a
single-row `DataFrame` for the affected memory; Forget returns the delete count. Every operation
is scoped to `agent_id` (the memory namespace).

## Install

```bash
pip install lfx-dakera
```

The bundle is discovered automatically by Langflow via the `langflow.extensions` entry point;
the **Dakera Memory** node appears in the component sidebar.

## Running a Dakera server

Self-hosting bundles a MinIO object store, so run it via the
[`dakera-deploy`](https://github.com/dakera-ai/dakera-deploy) compose file rather than the bare image:

```bash
git clone https://github.com/dakera-ai/dakera-deploy && cd dakera-deploy
docker compose -f docker/docker-compose.yml up -d   # server on http://localhost:3000
```

Point the node's **Dakera API URL** at `http://localhost:3000`. Set an **API Key** (a `dk-…`
token) if your instance requires authentication; leave it empty for unauthenticated local dev.

## Links

- Docs: https://dakera.ai/docs
- Python SDK: https://dakera.ai/docs/python
- Self-hosting: https://github.com/dakera-ai/dakera-deploy

## License

MIT
