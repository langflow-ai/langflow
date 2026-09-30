"""Append-only migration table + flow-deserializer rewrite hook.

This subpackage implements the migration layer of the Extension System.
A flow saved before a bundle was extracted contains legacy component
references in three shapes:

    * bare class name (``"OpenAIEmbeddings"``)
    * old import path (``"langflow.components.openai.OpenAIEmbeddings"``)
    * pre-Phase-A namespaced ID (``"ext:openai:OpenAIEmbeddings@official-pre-a"``)

The migration table maps each legacy form to the post-Phase-A canonical
``ext:<bundle>:<Class>@<slot>`` identifier.  The deserializer hook walks the
saved-flow payload on load and rewrites every ``data.type`` field whose value
is a legacy reference.

Public surface:
    - :func:`load_migration_table` -- read and validate the canonical JSON.
    - :func:`migrate_flow_payload` -- rewrite a flow payload in place.
    - :class:`MigrationTable` / :class:`MigrationEntry` -- Pydantic models.
    - :class:`MigrationReport` -- per-node rewrite outcomes; will feed
      the ``flow-migrated`` event once the events pipeline lands.
"""

from lfx.extension.migration.loader import (
    MIGRATION_TABLE_PATH,
    empty_table,
    invalidate_cache,
    load_migration_table,
)
from lfx.extension.migration.rewrite import (
    MigrationReport,
    NodeRewriteRecord,
    RewriteOutcome,
    migrate_flow_payload,
)
from lfx.extension.migration.schema import (
    MIGRATION_SCHEMA_VERSION,
    MigrationEntry,
    MigrationTable,
)

__all__ = [
    "MIGRATION_SCHEMA_VERSION",
    "MIGRATION_TABLE_PATH",
    "MigrationEntry",
    "MigrationReport",
    "MigrationTable",
    "NodeRewriteRecord",
    "RewriteOutcome",
    "empty_table",
    "invalidate_cache",
    "load_migration_table",
    "migrate_flow_payload",
]
