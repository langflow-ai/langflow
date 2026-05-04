"""Langflow Extension System (foundation, LE-1014).

Public surface for this milestone:
    - ``ExtensionManifest``, ``BundleRef``, ``LangflowCompat`` -- Pydantic models for
      the v0 manifest schema.
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
    EXTENSION_SCHEMA_URL,
    SCHEMA_VERSION,
    BundleRef,
    ExtensionManifest,
    LangflowCompat,
    ManifestSource,
    load_manifest,
)
from lfx.extension.validate import (
    ValidateReport,
    validate_extension,
)

__all__ = [
    "ERROR_CODES",
    "EXTENSION_SCHEMA_URL",
    "SCHEMA_VERSION",
    "SLOT_EXTRA",
    "SLOT_OFFICIAL",
    "BundleRef",
    "ExtensionError",
    "ExtensionErrorCollection",
    "ExtensionManifest",
    "LangflowCompat",
    "LoadResult",
    "LoadedComponent",
    "ManifestSource",
    "ValidateReport",
    "discover_inline_bundles",
    "filter_plugin_entry_points",
    "format_extension_error",
    "installed_extension_roots",
    "load_extension",
    "load_manifest",
    "manifest_owning_distributions",
    "validate_extension",
]
