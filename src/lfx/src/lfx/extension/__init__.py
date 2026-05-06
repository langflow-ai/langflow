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

from lfx.extension.dev_registry import (
    DevExtensionEntry,
    dev_extension_component_paths,
    list_dev_extensions,
    load_dev_extensions,
    register_dev_extension,
    state_file_path,
    unregister_dev_extension,
)
from lfx.extension.errors import (
    ERROR_CODES,
    ExtensionError,
    ExtensionErrorCollection,
    format_extension_error,
)
from lfx.extension.init_template import (
    BASIC_TEMPLATE,
    InitOptions,
    init_extension,
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
from lfx.extension.validate import (
    ValidateReport,
    validate_extension,
)

__all__ = [
    "BASIC_TEMPLATE",
    "BUNDLE_API_VERSION",
    "ERROR_CODES",
    "EXTENSION_SCHEMA_URL",
    "SCHEMA_VERSION",
    "SLOT_EXTRA",
    "SLOT_OFFICIAL",
    "BundleRef",
    "DevExtensionEntry",
    "ExtensionError",
    "ExtensionErrorCollection",
    "ExtensionManifest",
    "InitOptions",
    "LfxCompat",
    "LoadResult",
    "LoadedComponent",
    "ManifestSource",
    "ValidateReport",
    "dev_extension_component_paths",
    "discover_inline_bundles",
    "filter_plugin_entry_points",
    "format_extension_error",
    "init_extension",
    "installed_extension_roots",
    "list_dev_extensions",
    "load_dev_extensions",
    "load_extension",
    "load_manifest",
    "manifest_owning_distributions",
    "register_dev_extension",
    "state_file_path",
    "unregister_dev_extension",
    "validate_extension",
]
