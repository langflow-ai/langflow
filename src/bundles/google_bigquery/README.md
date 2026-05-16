# lfx-google-bigquery

Google BigQuery SQL executor with Service Account credentials.

Part of the Google split (4-way separation of the legacy `lfx.components.google` directory).

## Components

| Class | Module |
| --- | --- |
| `BigQueryExecutorComponent` | `google_bq_sql_executor` |

## Install

```bash
pip install lfx-google-bigquery
```

## Develop

```bash
cd src/bundles/google_bigquery
pip install -e .
lfx extension validate src/lfx_google_bigquery
```

## Migration

Saved flows that referenced `lfx.components.google.*` for one of this bundle's components rewrite to `ext:google_bigquery:<Class>@official` via the migration table at `src/lfx/src/lfx/extension/migration/migration_table.json`.
