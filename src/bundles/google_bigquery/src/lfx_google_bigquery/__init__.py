"""lfx-google-bigquery: Google BigQuery bundle.

Distribution unit ``lfx-google-bigquery``.  At runtime Langflow's loader
discovers ``extension.json`` shipped alongside this ``__init__.py`` and
registers the bundle's components under the namespaced IDs
``ext:google_bigquery:<Class>@official``.

Part of the Google split: 9 components from the in-tree ``google/``
directory were partitioned across 4 lfx-google-* bundles by audience
(GenAI / Workspace / BigQuery / Search).
"""

from lfx_google_bigquery.components.google_bigquery.google_bq_sql_executor import BigQueryExecutorComponent

__all__ = [
    "BigQueryExecutorComponent",
]
