"""Langflow Extension System (foundation).

Public surface for this milestone:
    - ``ExtensionManifest``, ``BundleRef``, ``LfxCompat`` -- Pydantic models for
      the v0 manifest schema.
    - ``BUNDLE_API_VERSION`` -- the integer BUNDLE_API.md contract version this
      lfx package implements; manifests must list ``str(BUNDLE_API_VERSION)``
      in ``lfx.compat``.
    - ``ExtensionError`` -- the typed error envelope every other extension-system
      module emits.
    - ``format_extension_error`` -- the single renderer that turns an
      ``ExtensionError`` into a human-readable message (plain text + JSON-able
      dict).  No other code in the extension system formats error strings.
    - ``validate_extension`` -- the offline, non-executing manifest + AST checker
      that backs ``lfx extension validate``.

All three components evolve together: the schema defines what ``validate``
checks, and the formatter renders ``validate``'s output.
"""

from lfx.extension.errors import (
    ERROR_CODES,
    ExtensionError,
    ExtensionErrorCollection,
    format_extension_error,
)
from lfx.extension.loader import (
    SLOT_EXTRA,
    SLOT_OFFICIAL,
    LoadedComponent,
    LoadResult,
    discover_inline_bundles,
    filter_plugin_entry_points,
    installed_extension_roots,
    load_extension,
    manifest_owning_distributions,
)
from lfx.extension.manifest import (
    BUNDLE_API_VERSION,
    EXTENSION_SCHEMA_URL,
    SCHEMA_VERSION,
    BundleRef,
    ExtensionManifest,
    LfxCompat,
    ManifestSource,
    load_manifest,
)
from lfx.extension.migration import (
    MIGRATION_SCHEMA_VERSION,
    MIGRATION_TABLE_PATH,
    MigrationEntry,
    MigrationReport,
    MigrationTable,
    NodeRewriteRecord,
    load_migration_table,
    migrate_flow_payload,
)
from lfx.extension.validate import (
    ValidateReport,
    validate_extension,
)

__all__ = [
    "BUNDLE_API_VERSION",
    "ERROR_CODES",
    "EXTENSION_SCHEMA_URL",
    "MIGRATION_SCHEMA_VERSION",
    "MIGRATION_TABLE_PATH",
    "SCHEMA_VERSION",
    "SLOT_EXTRA",
    "SLOT_OFFICIAL",
    "BundleRef",
    "ExtensionError",
    "ExtensionErrorCollection",
    "ExtensionManifest",
    "LfxCompat",
    "LoadResult",
    "LoadedComponent",
    "ManifestSource",
    "MigrationEntry",
    "MigrationReport",
    "MigrationTable",
    "NodeRewriteRecord",
    "ValidateReport",
    "discover_inline_bundles",
    "filter_plugin_entry_points",
    "format_extension_error",
    "installed_extension_roots",
    "load_extension",
    "load_manifest",
    "load_migration_table",
    "manifest_owning_distributions",
    "migrate_flow_payload",
    "validate_extension",
]
