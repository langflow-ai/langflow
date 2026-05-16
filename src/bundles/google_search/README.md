# lfx-google-search

Google Search APIs: official Google Search and Serper.

Part of the Google split (4-way separation of the legacy `lfx.components.google` directory).

## Components

| Class | Module |
| --- | --- |
| `GoogleSearchAPICore` | `google_search_api_core` |
| `GoogleSerperAPICore` | `google_serper_api_core` |

## Install

```bash
pip install lfx-google-search
```

## Develop

```bash
cd src/bundles/google_search
pip install -e .
lfx extension validate src/lfx_google_search
```

## Migration

Saved flows that referenced `lfx.components.google.*` for one of this bundle's components rewrite to `ext:google_search:<Class>@official` via the migration table at `src/lfx/src/lfx/extension/migration/migration_table.json`.
