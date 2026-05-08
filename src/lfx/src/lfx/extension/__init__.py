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

from lfx.extension.discovery import (
    DEFAULT_SEED_DIR,
    SEED_DIR_ENV_VAR,
    DiscoveredExtension,
    discover_all_extensions,
    discover_installed_extensions,
    discover_seed_extensions,
)
from lfx.extension.errors import (
    ERROR_CODES,
    ExtensionError,
    ExtensionErrorCollection,
    format_extension_error,
)
from lfx.extension.loader import (
    DEFAULT_MODULE_NAMESPACE,
    SLOT_EXTRA,
    SLOT_OFFICIAL,
    LoadedComponent,
    LoadResult,
    discover_inline_bundles,
    filter_component_entry_points,
    filter_plugin_entry_points,
    installed_extension_roots,
    load_extension,
    load_installed_extensions,
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
from lfx.extension.registry import (
    DuplicateExtensionError,
    Extension,
    ExtensionImmutableError,
    ExtensionRegistry,
    LoadStatus,
    build_registry_from_discovery,
)
from lfx.extension.validate import (
    ValidateReport,
    validate_extension,
)

__all__ = [
    "BUNDLE_API_VERSION",
    "DEFAULT_MODULE_NAMESPACE",
    "DEFAULT_SEED_DIR",
    "ERROR_CODES",
    "EXTENSION_SCHEMA_URL",
    "SCHEMA_VERSION",
    "SEED_DIR_ENV_VAR",
    "SLOT_EXTRA",
    "SLOT_OFFICIAL",
    "BundleRef",
    "DiscoveredExtension",
    "DuplicateExtensionError",
    "Extension",
    "ExtensionError",
    "ExtensionErrorCollection",
    "ExtensionImmutableError",
    "ExtensionManifest",
    "ExtensionRegistry",
    "LfxCompat",
    "LoadResult",
    "LoadStatus",
    "LoadedComponent",
    "ManifestSource",
    "ValidateReport",
    "build_registry_from_discovery",
    "discover_all_extensions",
    "discover_inline_bundles",
    "discover_installed_extensions",
    "discover_seed_extensions",
    "filter_component_entry_points",
    "filter_plugin_entry_points",
    "format_extension_error",
    "installed_extension_roots",
    "load_extension",
    "load_installed_extensions",
    "load_manifest",
    "manifest_owning_distributions",
    "validate_extension",
]
