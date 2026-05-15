# lfx-datastax

DataStax / AstraDB components as a standalone Langflow Extension Bundle.

Third extracted bundle (after `lfx-duckduckgo` and `lfx-arxiv`); ports
the 11 datastax components and their shared `AstraDBBaseComponent`
mixin out of `lfx.components.datastax` and `lfx.base.datastax` into a
single `lfx-datastax` distribution.

## Components

| Class | Module |
| --- | --- |
| `AstraDBVectorStoreComponent` | `astradb_vectorstore` |
| `AstraDBDataAPIComponent` | `astradb_data_api` |
| `AstraDBGraphVectorStoreComponent` | `astradb_graph` |
| `AstraDBCQLToolComponent` | `astradb_cql` |
| `AstraDBToolComponent` | `astradb_tool` |
| `AstraDBChatMemory` | `astradb_chatmemory` |
| `AstraVectorizeComponent` | `astradb_vectorize` |
| `GraphRAGComponent` | `graph_rag` |
| `HCDVectorStoreComponent` | `hcd` |
| `Dotenv` | `dotenv` |
| `GetEnvVar` | `getenvvar` |

## Install

```bash
pip install lfx-datastax
```

The bundle is registered automatically via the `langflow.extensions`
entry-point. After install, restart your Langflow server; the
components will appear in the palette under the `datastax` bundle
group with the namespaced IDs `ext:datastax:<Class>@official`.

## Develop

```bash
cd src/bundles/datastax
pip install -e .
lfx extension validate src/lfx_datastax
```

## Manifest

The extension manifest ships at `src/lfx_datastax/extension.json` and
points at `components/datastax`. The shared `AstraDBBaseComponent` lives
at `lfx_datastax.base.astradb_base` (was `lfx.base.datastax.astradb_base`
pre-extraction); third-party code that imported the base should switch
to the new path.

## Migration

Saved flows that referenced the legacy `lfx.components.datastax.*`
import paths or bare class names are rewritten to
`ext:datastax:<Class>@official` by the migration table in
`src/lfx/src/lfx/extension/migration/migration_table.json`.
