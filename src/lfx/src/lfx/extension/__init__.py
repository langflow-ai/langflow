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

Module loading
--------------
This package re-exports symbols from a dozen submodules.  Eagerly importing
every submodule on ``import lfx.extension`` cost the validate CLI ~25ms of
unnecessary work (loader + dev_registry + migration + registry + discovery)
before any author-typed command had a chance to run.

To keep ``lfx extension validate`` snappy we use PEP 562 ``__getattr__``:
submodules are imported on first access of one of their re-exported names.
Static analyzers and ``dir()`` still see the full public API via ``__all__``,
and ``from lfx.extension import X`` keeps working unchanged -- only the wall
time of the first attribute access for a given submodule reflects its cost.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    # Static analyzers and IDEs see the eager-import shape so autocomplete /
    # go-to-definition keep working; PEP 562 only changes runtime behavior.
    from lfx.extension.dev_registry import (
        DevExtensionEntry,
        dev_extension_component_paths,
        list_dev_extensions,
        load_dev_extensions,
        register_dev_extension,
        state_file_path,
        unregister_dev_extension,
    )
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
    from lfx.extension.init_template import (
        BASIC_TEMPLATE,
        InitOptions,
        init_extension,
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
        load_seed_extensions,
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


# Map each public name to the submodule that owns it.  PEP 562 ``__getattr__``
# uses this to import the submodule lazily on first attribute access.
_EXPORTS: dict[str, str] = {
    # errors
    "ERROR_CODES": "errors",
    "ExtensionError": "errors",
    "ExtensionErrorCollection": "errors",
    "format_extension_error": "errors",
    # validate
    "ValidateReport": "validate",
    "validate_extension": "validate",
    # manifest
    "BUNDLE_API_VERSION": "manifest",
    "EXTENSION_SCHEMA_URL": "manifest",
    "SCHEMA_VERSION": "manifest",
    "BundleRef": "manifest",
    "ExtensionManifest": "manifest",
    "LfxCompat": "manifest",
    "ManifestSource": "manifest",
    "load_manifest": "manifest",
    # init_template
    "BASIC_TEMPLATE": "init_template",
    "InitOptions": "init_template",
    "init_extension": "init_template",
    # discovery
    "DEFAULT_SEED_DIR": "discovery",
    "SEED_DIR_ENV_VAR": "discovery",
    "DiscoveredExtension": "discovery",
    "discover_all_extensions": "discovery",
    "discover_installed_extensions": "discovery",
    "discover_seed_extensions": "discovery",
    # loader
    "DEFAULT_MODULE_NAMESPACE": "loader",
    "SLOT_EXTRA": "loader",
    "SLOT_OFFICIAL": "loader",
    "LoadResult": "loader",
    "LoadedComponent": "loader",
    "discover_inline_bundles": "loader",
    "filter_component_entry_points": "loader",
    "filter_plugin_entry_points": "loader",
    "installed_extension_roots": "loader",
    "load_extension": "loader",
    "load_installed_extensions": "loader",
    "load_seed_extensions": "loader",
    "manifest_owning_distributions": "loader",
    # dev_registry
    "DevExtensionEntry": "dev_registry",
    "dev_extension_component_paths": "dev_registry",
    "list_dev_extensions": "dev_registry",
    "load_dev_extensions": "dev_registry",
    "register_dev_extension": "dev_registry",
    "state_file_path": "dev_registry",
    "unregister_dev_extension": "dev_registry",
    # migration
    "MIGRATION_SCHEMA_VERSION": "migration",
    "MIGRATION_TABLE_PATH": "migration",
    "MigrationEntry": "migration",
    "MigrationReport": "migration",
    "MigrationTable": "migration",
    "NodeRewriteRecord": "migration",
    "load_migration_table": "migration",
    "migrate_flow_payload": "migration",
    # registry
    "DuplicateExtensionError": "registry",
    "Extension": "registry",
    "ExtensionImmutableError": "registry",
    "ExtensionRegistry": "registry",
    "LoadStatus": "registry",
    "build_registry_from_discovery": "registry",
}


def __getattr__(name: str) -> Any:
    """Lazy loader for re-exported public symbols (PEP 562).

    Importing ``lfx.extension`` no longer eagerly pulls every submodule.
    The first access of e.g. ``lfx.extension.validate_extension`` imports
    ``lfx.extension.validate`` and caches the resolved attribute in the
    module's ``__dict__`` so subsequent lookups are free.
    """
    submodule = _EXPORTS.get(name)
    if submodule is None:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    module = importlib.import_module(f"{__name__}.{submodule}")
    value = getattr(module, name)
    # Cache on the package module so repeated lookups skip the dispatcher.
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Make every lazy export show up in ``dir(lfx.extension)`` for tab completion."""
    return sorted(set(globals()) | set(_EXPORTS))


__all__ = [
    "BASIC_TEMPLATE",
    "BUNDLE_API_VERSION",
    "DEFAULT_MODULE_NAMESPACE",
    "DEFAULT_SEED_DIR",
    "ERROR_CODES",
    "EXTENSION_SCHEMA_URL",
    "MIGRATION_SCHEMA_VERSION",
    "MIGRATION_TABLE_PATH",
    "SCHEMA_VERSION",
    "SEED_DIR_ENV_VAR",
    "SLOT_EXTRA",
    "SLOT_OFFICIAL",
    "BundleRef",
    "DevExtensionEntry",
    "DiscoveredExtension",
    "DuplicateExtensionError",
    "Extension",
    "ExtensionError",
    "ExtensionErrorCollection",
    "ExtensionImmutableError",
    "ExtensionManifest",
    "ExtensionRegistry",
    "InitOptions",
    "LfxCompat",
    "LoadResult",
    "LoadStatus",
    "LoadedComponent",
    "ManifestSource",
    "MigrationEntry",
    "MigrationReport",
    "MigrationTable",
    "NodeRewriteRecord",
    "ValidateReport",
    "build_registry_from_discovery",
    "dev_extension_component_paths",
    "discover_all_extensions",
    "discover_inline_bundles",
    "discover_installed_extensions",
    "discover_seed_extensions",
    "filter_component_entry_points",
    "filter_plugin_entry_points",
    "format_extension_error",
    "init_extension",
    "installed_extension_roots",
    "list_dev_extensions",
    "load_dev_extensions",
    "load_extension",
    "load_installed_extensions",
    "load_manifest",
    "load_migration_table",
    "load_seed_extensions",
    "manifest_owning_distributions",
    "migrate_flow_payload",
    "register_dev_extension",
    "state_file_path",
    "unregister_dev_extension",
    "validate_extension",
]
