import asyncio
import contextlib
import hashlib
import importlib
import inspect
import json
import os
import pkgutil
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import orjson

from lfx.constants import BASE_COMPONENTS_PATH
from lfx.custom.utils import abuild_custom_components, create_component_template
from lfx.extension import (
    ExtensionError,
    LoadResult,
    discover_inline_bundles,
    format_extension_error,
    load_dev_extensions,
    load_installed_extensions,
    load_seed_extensions,
)
from lfx.extension.bundle_registry import BundleRecord, get_default_registry
from lfx.extension.reload import register_post_swap_hook
from lfx.log.logger import logger
from lfx.utils.flow_validation import collect_component_hash_lookups
from lfx.utils.validate_cloud import (
    filter_disabled_components_from_dict,
    is_component_disabled_in_astra_cloud,
)

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService

MIN_MODULE_PARTS = 2
MIN_MODULE_PARTS_WITH_FILENAME = 4  # Minimum parts needed to have a module filename (lfx.components.type.filename)
EXPECTED_RESULT_LENGTH = 2  # Expected length of the tuple returned by _process_single_module

# Third-party modules whose package __init__ and a submodule import each other.
# These must be imported single-threaded before any concurrent import fan-out --
# see ``_warm_circular_imports`` for the full deadlock explanation.
MODULES_WITH_INTERNAL_CIRCULAR_IMPORTS = ("toolguard.runtime", "toolguard.runtime.runtime")


# Create a class to manage component cache instead of using globals
class ComponentCache:
    def __init__(self):
        """Initializes the component cache.

        Creates empty storage for all component types and tracking of fully loaded components.
        """
        self.all_types_dict: dict[str, Any] | None = None
        self.fully_loaded_components: dict[str, bool] = {}
        # Precomputed code hashes for fast flow validation.
        # Populated by get_and_cache_all_types_dict() via _build_code_hash_lookups().
        # None means "not yet loaded" (fail-closed); {} means "loaded, no components found".
        self.type_to_current_hash: dict[str, set[str]] | None = None
        self.all_known_hashes: set[str] | None = None


# Singleton instance
component_cache = ComponentCache()


def _post_reload_refresh_cache(record: BundleRecord) -> None:
    """Post-swap hook installed in :data:`_POST_SWAP_HOOKS`.

    Defined here so the hook closes over :data:`component_cache` without
    needing to thread it through ``lfx.extension.reload``.  Concrete logic
    lives in :func:`refresh_bundle_cache_from_record` further down (the
    forward reference is fine; the hook is fired only after first cache
    build).
    """
    refresh_bundle_cache_from_record(record)


register_post_swap_hook(_post_reload_refresh_cache)


def _parse_dev_mode() -> tuple[bool, list[str] | None]:
    """Parse LFX_DEV to determine dev mode and which modules to load.

    Development mode must be explicitly enabled via the LFX_DEV environment variable.
    When enabled, components are always rebuilt dynamically to reflect code changes.
    When disabled or not set, the prebuilt index is used for fast startup.

    Supports two modes:
    - Boolean mode: LFX_DEV=1/true/yes loads all modules dynamically
    - List mode: LFX_DEV=mistral,openai,anthropic loads only specified modules

    Returns:
        Tuple of (dev_mode_enabled, module_list)
        - If module_list is None, load all modules
        - If module_list is a list, only load those specific modules
    """
    lfx_dev = os.getenv("LFX_DEV", "").strip()
    if not lfx_dev:
        return (False, None)

    # Boolean mode: "1", "true", "yes" enables dev mode
    if lfx_dev.lower() in {"1", "true", "yes"}:
        return (True, None)  # Load all modules

    # Boolean mode: "0", "false", "no" explicitly disables dev mode
    if lfx_dev.lower() in {"0", "false", "no"}:
        return (False, None)

    # List mode: comma-separated values
    modules = [m.strip().lower() for m in lfx_dev.split(",") if m.strip()]
    if modules:
        return (True, modules)

    return (False, None)


def _read_component_index(custom_path: str | None = None) -> dict | None:
    """Read and validate the prebuilt component index.

    Args:
        custom_path: Optional custom path or URL to index file. If None, uses built-in index.

    Returns:
        The index dictionary if valid, None otherwise
    """
    try:
        import lfx

        # Determine index location
        if custom_path:
            # Check if it's a URL
            if custom_path.startswith(("http://", "https://")):
                # Fetch from URL
                import httpx

                try:
                    response = httpx.get(custom_path, timeout=10.0)
                    response.raise_for_status()
                    blob = orjson.loads(response.content)
                except httpx.HTTPError as e:
                    logger.warning(f"Failed to fetch component index from {custom_path}: {e}")
                    return None
                except orjson.JSONDecodeError as e:
                    logger.warning(f"Component index from {custom_path} is corrupted or invalid JSON: {e}")
                    return None
            else:
                # Load from file path
                index_path = Path(custom_path)
                if not index_path.exists():
                    logger.warning(f"Custom component index not found at {custom_path}")
                    return None
                try:
                    blob = orjson.loads(index_path.read_bytes())
                except orjson.JSONDecodeError as e:
                    logger.warning(f"Component index at {custom_path} is corrupted or invalid JSON: {e}")
                    return None
        else:
            # Use built-in index
            pkg_dir = Path(inspect.getfile(lfx)).parent
            index_path = pkg_dir / "_assets" / "component_index.json"

            if not index_path.exists():
                return None

            try:
                blob = orjson.loads(index_path.read_bytes())
            except orjson.JSONDecodeError as e:
                logger.warning(f"Built-in component index is corrupted or invalid JSON: {e}")
                return None

        # Integrity check: verify SHA256
        tmp = dict(blob)
        sha = tmp.pop("sha256", None)
        if not sha:
            logger.warning("Component index missing SHA256 hash - index may be tampered")
            return None

        # Use orjson for hash calculation to match build script
        calc = hashlib.sha256(orjson.dumps(tmp, option=orjson.OPT_SORT_KEYS)).hexdigest()
        if sha != calc:
            logger.warning(
                "Component index integrity check failed - SHA256 mismatch (file may be corrupted or tampered)"
            )
            return None

        # Version check: ensure index matches installed lfx version
        from importlib.metadata import PackageNotFoundError, version

        try:
            installed_version = version("lfx")
        except PackageNotFoundError:
            # In some deployment environments (e.g. Docker with workspace installs),
            # lfx may be importable but lack dist-info metadata. Skip version check.
            logger.debug("Could not determine installed lfx version (no package metadata); skipping version check")
            installed_version = None

        if installed_version is not None and blob.get("version") != installed_version:
            logger.debug(
                f"Component index version mismatch: index={blob.get('version')}, installed={installed_version}"
            )
            return None
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Unexpected error reading component index: {type(e).__name__}: {e}")
        return None
    return blob


def _get_cache_path() -> Path:
    """Get the path for the cached component index in the user's cache directory."""
    from platformdirs import user_cache_dir

    cache_dir = Path(user_cache_dir("lfx", "langflow"))
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "component_index.json"


def _save_generated_index(modules_dict: dict) -> None:
    """Save a dynamically generated component index to cache for future use.

    Args:
        modules_dict: Dictionary of components by category
    """
    try:
        cache_path = _get_cache_path()

        # Convert modules_dict to entries format
        entries = [[top_level, components] for top_level, components in modules_dict.items()]

        # Calculate metadata
        num_modules = len(modules_dict)
        num_components = sum(len(components) for components in modules_dict.values())

        # Get version
        from importlib.metadata import version

        langflow_version = version("langflow")

        # Build index structure
        index = {
            "version": langflow_version,
            "metadata": {
                "num_modules": num_modules,
                "num_components": num_components,
            },
            "entries": entries,
        }

        # Calculate hash
        payload = orjson.dumps(index, option=orjson.OPT_SORT_KEYS)
        index["sha256"] = hashlib.sha256(payload).hexdigest()

        # Write to cache
        json_bytes = orjson.dumps(index, option=orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2)
        cache_path.write_bytes(json_bytes)

        logger.debug(f"Saved generated component index to cache: {cache_path}")
    except Exception as e:  # noqa: BLE001
        logger.debug(f"Failed to save generated index to cache: {e}")


async def _send_telemetry(
    telemetry_service: Any,
    index_source: str,
    modules_dict: dict,
    dev_mode: bool,  # noqa: FBT001
    target_modules: list[str] | None,
    start_time_ms: int,
) -> None:
    """Send telemetry about component index loading.

    Args:
        telemetry_service: Telemetry service instance (optional)
        index_source: Source of the index ("builtin", "cache", or "dynamic")
        modules_dict: Dictionary of loaded components
        dev_mode: Whether dev mode is enabled
        target_modules: List of filtered modules if any
        start_time_ms: Start time in milliseconds
    """
    if not telemetry_service:
        return

    try:
        # Calculate metrics
        num_modules = len(modules_dict)
        num_components = sum(len(components) for components in modules_dict.values())
        load_time_ms = int(time.time() * 1000) - start_time_ms
        filtered_modules = ",".join(target_modules) if target_modules else None

        # Import the payload class dynamically to avoid circular imports
        from langflow.services.telemetry.schema import ComponentIndexPayload

        payload = ComponentIndexPayload(
            index_source=index_source,
            num_modules=num_modules,
            num_components=num_components,
            dev_mode=dev_mode,
            filtered_modules=filtered_modules,
            load_time_ms=load_time_ms,
        )

        await telemetry_service.log_component_index(payload)
    except Exception as e:  # noqa: BLE001
        # Don't fail component loading if telemetry fails
        await logger.adebug(f"Failed to send component index telemetry: {e}")


async def _load_from_index_or_cache(
    settings_service: Optional["SettingsService"] = None,
) -> tuple[dict[str, Any], str | None]:
    """Load components from prebuilt index or cache.

    Args:
        settings_service: Optional settings service to get custom index path

    Returns:
        Tuple of (modules_dict, index_source) where index_source is "builtin", "cache", or None if failed
    """
    modules_dict: dict[str, Any] = {}

    # Try to load from prebuilt index first
    custom_index_path = None
    if settings_service and settings_service.settings.components_index_path:
        custom_index_path = settings_service.settings.components_index_path
        await logger.adebug(f"Using custom component index: {custom_index_path}")

    index = _read_component_index(custom_index_path)
    if index and "entries" in index:
        source = custom_index_path or "built-in index"
        await logger.adebug(f"Loading components from {source}")
        # Reconstruct modules_dict from index entries
        for top_level, components in index["entries"]:
            if top_level not in modules_dict:
                modules_dict[top_level] = {}
            modules_dict[top_level].update(components)
        # Filter disabled components for Astra cloud
        modules_dict = filter_disabled_components_from_dict(modules_dict)
        await logger.adebug(f"Loaded {len(modules_dict)} component categories from index")
        return modules_dict, "builtin"

    # Index failed to load - try cache
    await logger.adebug("Prebuilt index not available, checking cache")
    try:
        cache_path = _get_cache_path()
    except Exception as e:  # noqa: BLE001
        await logger.adebug(f"Cache load failed: {e}")
    else:
        if cache_path.exists():
            await logger.adebug(f"Attempting to load from cache: {cache_path}")
            index = _read_component_index(str(cache_path))
            if index and "entries" in index:
                await logger.adebug("Loading components from cached index")
                for top_level, components in index["entries"]:
                    if top_level not in modules_dict:
                        modules_dict[top_level] = {}
                    modules_dict[top_level].update(components)
                # Filter disabled components for Astra cloud
                modules_dict = filter_disabled_components_from_dict(modules_dict)
                await logger.adebug(f"Loaded {len(modules_dict)} component categories from cache")
                return modules_dict, "cache"

    return modules_dict, None


def _warm_circular_imports() -> None:
    """Pre-import third-party modules that contain an *internal* circular import.

    ``toolguard.runtime`` (package __init__) and its ``toolguard.runtime.runtime``
    submodule import each other: the __init__ does ``from .runtime import ...`` while
    runtime.py does ``from toolguard.runtime import IToolInvoker``. That cycle resolves
    cleanly when first imported from a single thread, but the lfx policy modules reach
    it from two different entry points -- ``policies.tool_invoker`` enters at the
    ``toolguard.runtime`` package while ``policies.guard_sync_utils`` enters at the
    ``toolguard.runtime.runtime`` submodule. When those two land on separate worker
    threads at the same time (the ``asyncio.to_thread`` fan-out in
    ``_load_components_dynamically``), one thread holds the package lock and waits for
    the submodule lock while the other holds the submodule lock and waits for the
    package lock, so CPython's import machinery raises ``_DeadlockError``.

    Warming these single-threaded populates ``sys.modules`` so the threaded fan-out
    only ever hits the import cache and can never enter the cycle concurrently. Full
    coverage is preserved -- every component module is still imported below; this only
    front-loads the shared cycle instead of skipping any module.
    """
    for modname in MODULES_WITH_INTERNAL_CIRCULAR_IMPORTS:
        # Optional dependency: when toolguard isn't installed, the dependent component
        # modules are skipped/reported by the fan-out as usual.
        with contextlib.suppress(ImportError):
            importlib.import_module(modname)


async def _load_components_dynamically(
    target_modules: list[str] | None = None,
) -> dict[str, Any]:
    """Load components dynamically by scanning and importing modules.

    Args:
        target_modules: Optional list of specific module names to load (e.g., ["mistral", "openai"])

    Returns:
        Dictionary mapping top-level module names to their components
    """
    modules_dict: dict[str, Any] = {}

    try:
        import lfx.components as components_pkg
    except ImportError as e:
        await logger.aerror(f"Failed to import langflow.components package: {e}", exc_info=True)
        return modules_dict

    # Collect all module names to process
    module_names = []
    for _, modname, _ in pkgutil.walk_packages(components_pkg.__path__, prefix=components_pkg.__name__ + "."):
        # Skip if the module is in the deactivated folder
        if "deactivated" in modname:
            continue

        # Parse module name once for all checks
        parts = modname.split(".")
        if len(parts) > MIN_MODULE_PARTS:
            component_type = parts[2]

            # Skip disabled components when ASTRA_CLOUD_DISABLE_COMPONENT is true
            if len(parts) >= MIN_MODULE_PARTS_WITH_FILENAME:
                module_filename = parts[3]
                if is_component_disabled_in_astra_cloud(component_type.lower(), module_filename):
                    continue

            # If specific modules requested, filter by top-level module name
            if target_modules and component_type.lower() not in target_modules:
                continue

        module_names.append(modname)

    if target_modules:
        await logger.adebug(f"Found {len(module_names)} modules matching filter")

    if not module_names:
        return modules_dict

    # Warm third-party modules with internal circular imports single-threaded before
    # the concurrent fan-out below, otherwise two worker threads can each grab one half
    # of the cycle and CPython raises an import ``_DeadlockError``.
    _warm_circular_imports()

    # Create tasks for parallel module processing
    tasks = [asyncio.to_thread(_process_single_module, modname) for modname in module_names]

    # Wait for all modules to be processed
    try:
        module_results = await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as e:  # noqa: BLE001
        await logger.aerror(f"Error during parallel module processing: {e}", exc_info=True)
        return modules_dict

    # Merge results from all modules
    for result in module_results:
        if isinstance(result, Exception):
            await logger.awarning(f"Module processing failed: {result}")
            continue

        if result and isinstance(result, tuple) and len(result) == EXPECTED_RESULT_LENGTH:
            top_level, components = result
            if top_level and components:
                if top_level not in modules_dict:
                    modules_dict[top_level] = {}
                modules_dict[top_level].update(components)

    return modules_dict


async def _load_full_dev_mode() -> tuple[dict[str, Any], str]:
    """Load all components dynamically in full dev mode.

    Returns:
        Tuple of (modules_dict, index_source)
    """
    await logger.adebug("LFX_DEV full mode: loading all modules dynamically")
    modules_dict = await _load_components_dynamically(target_modules=None)
    return modules_dict, "dynamic"


async def _load_selective_dev_mode(
    settings_service: Optional["SettingsService"],
    target_modules: list[str],
) -> tuple[dict[str, Any], str]:
    """Load index and selectively reload specific modules.

    Args:
        settings_service: Settings service for custom index path
        target_modules: List of module names to reload

    Returns:
        Tuple of (modules_dict, index_source)
    """
    await logger.adebug(f"LFX_DEV selective mode: reloading {target_modules}")
    modules_dict, _ = await _load_from_index_or_cache(settings_service)

    # Reload specific modules dynamically
    dynamic_modules = await _load_components_dynamically(target_modules=target_modules)

    # Merge/replace the targeted modules
    for top_level, components in dynamic_modules.items():
        if top_level not in modules_dict:
            modules_dict[top_level] = {}
        modules_dict[top_level].update(components)

    await logger.adebug(f"Reloaded {len(target_modules)} module(s), kept others from index")
    return modules_dict, "dynamic"


async def _load_production_mode(
    settings_service: Optional["SettingsService"],
) -> tuple[dict[str, Any], str]:
    """Load components in production mode with fallback chain.

    Tries: index -> cache -> dynamic build (with caching)

    Args:
        settings_service: Settings service for custom index path

    Returns:
        Tuple of (modules_dict, index_source)
    """
    modules_dict, index_source = await _load_from_index_or_cache(settings_service)

    if not index_source:
        # No index or cache available - build dynamically and save
        await logger.adebug("Falling back to dynamic loading")
        modules_dict = await _load_components_dynamically(target_modules=None)
        index_source = "dynamic"

        # Save to cache for future use
        if modules_dict:
            await logger.adebug("Saving generated component index to cache")
            _save_generated_index(modules_dict)

    return modules_dict, index_source


async def import_langflow_components(
    settings_service: Optional["SettingsService"] = None,
    telemetry_service: Any | None = None,
) -> dict[str, dict[str, Any]]:
    """Asynchronously discovers and loads all built-in Langflow components.

    Loading Strategy:
    - Production mode: Load from prebuilt index -> cache -> build dynamically (with caching)
    - Dev mode (full): Build all components dynamically
    - Dev mode (selective): Load index + replace specific modules dynamically

    Args:
        settings_service: Optional settings service to get custom index path
        telemetry_service: Optional telemetry service to log component loading metrics

    Returns:
        A dictionary with a "components" key mapping top-level package names to their component templates.
    """
    start_time_ms: int = int(time.time() * 1000)
    dev_mode_enabled, target_modules = _parse_dev_mode()

    # Strategy pattern: map dev mode state to loading function
    if dev_mode_enabled and not target_modules:
        modules_dict, index_source = await _load_full_dev_mode()
    elif dev_mode_enabled and target_modules:
        modules_dict, index_source = await _load_selective_dev_mode(settings_service, target_modules)
    else:
        modules_dict, index_source = await _load_production_mode(settings_service)

    # Send telemetry
    await _send_telemetry(
        telemetry_service, index_source, modules_dict, dev_mode_enabled, target_modules, start_time_ms
    )

    return {"components": modules_dict}


def _process_single_module(modname: str) -> tuple[str, dict] | None:
    """Process a single module and return its components.

    Args:
        modname: The full module name to process

    Returns:
        A tuple of (top_level_package, components_dict) or None if processing failed
    """
    try:
        module = importlib.import_module(modname)
    except Exception as e:  # noqa: BLE001
        # Catch all exceptions during import to prevent component failures from crashing startup
        # TODO: Surface these errors to the UI in a friendly manner
        logger.error(f"Failed to import module {modname}: {e}", exc_info=True)
        return None
    # Extract the top-level subpackage name after "lfx.components."
    # e.g., "lfx.components.Notion.add_content_to_page" -> "Notion"
    mod_parts = modname.split(".")
    if len(mod_parts) <= MIN_MODULE_PARTS:
        return None

    top_level = mod_parts[2]
    module_components = {}

    # Bind frequently used functions for small speed gain
    _getattr = getattr

    # Fast path: only check class objects defined in this module
    failed_count = []
    for name, obj in vars(module).items():
        if not isinstance(obj, type):
            continue

        # Only consider classes defined in this module
        if obj.__module__ != modname:
            continue

        # Check for required attributes
        if not (
            _getattr(obj, "code_class_base_inheritance", None) is not None
            or _getattr(obj, "_code_class_base_inheritance", None) is not None
        ):
            continue

        try:
            comp_instance = obj()
            # modname is the full module name without the name of the obj
            full_module_name = f"{modname}.{name}"
            comp_template, _ = create_component_template(
                component_extractor=comp_instance, module_name=full_module_name
            )
            component_name = obj.name if hasattr(obj, "name") and obj.name else name
            module_components[component_name] = comp_template
        except Exception as e:  # noqa: BLE001
            failed_count.append(f"{name}: {e}")
            continue

    if failed_count:
        logger.warning(
            f"Skipped {len(failed_count)} component class{'es' if len(failed_count) != 1 else ''} "
            f"in module '{modname}' due to instantiation failure: {', '.join(failed_count)}"
        )
    logger.debug(f"Processed module {modname}")
    return (top_level, module_components)


async def _determine_loading_strategy(settings_service: "SettingsService") -> dict[str, Any]:
    """Determines and executes the appropriate component loading strategy.

    Args:
        settings_service: Service containing loading configuration

    Returns:
        Dictionary containing loaded component types and templates
    """
    component_cache.all_types_dict = {}
    if settings_service.settings.lazy_load_components:
        # Partial loading mode - just load component metadata
        await logger.adebug("Using partial component loading")
        component_cache.all_types_dict = await aget_component_metadata(settings_service.settings.components_path)
    elif settings_service.settings.components_path:
        # Traditional full loading - filter out base components path to only load custom components
        custom_paths = [p for p in settings_service.settings.components_path if p != BASE_COMPONENTS_PATH]
        if custom_paths:
            component_cache.all_types_dict = await aget_all_types_dict(custom_paths)

    # Log custom component loading stats
    components_dict = component_cache.all_types_dict or {}
    component_count = sum(len(comps) for comps in components_dict.get("components", {}).values())
    if component_count > 0 and settings_service.settings.components_path:
        await logger.adebug(
            f"Built {component_count} custom components from {settings_service.settings.components_path}"
        )

    return component_cache.all_types_dict or {}


def _build_code_hash_lookups(cache: ComponentCache) -> None:
    """Populate type_to_current_hash and all_known_hashes from all_types_dict.

    Called once after all_types_dict is fully populated. Builds:
    - type_to_current_hash: {component_type: 12-char SHA256 prefix}
    - all_known_hashes: set of all known code hashes
    """
    if not cache.all_types_dict:
        return

    type_to_hash, all_hashes = collect_component_hash_lookups(cache.all_types_dict)

    cache.type_to_current_hash = type_to_hash
    cache.all_known_hashes = all_hashes
    logger.debug(f"Built code hash lookups: {len(type_to_hash)} types, {len(all_hashes)} unique hashes")


def _components_path_extension_paths(settings_service: "SettingsService") -> list[Path]:
    """Inline-bundle parent paths derived from settings.components_path.

    Each entry in components_path is treated as a parent directory whose
    immediate subfolders are inline bundles at the @extra slot. The base
    Langflow components path is excluded (it is not an inline-bundle root).

    Comparison against ``BASE_COMPONENTS_PATH`` resolves both sides so a
    trailing slash, ``./`` prefix, or symlink does not slip the base
    components dir through as an inline-bundle root (which would produce
    duplicate / garbage palette entries from walking it as a bundle parent).
    """
    try:
        base_resolved = Path(BASE_COMPONENTS_PATH).resolve(strict=False)
    except OSError:
        base_resolved = Path(BASE_COMPONENTS_PATH)
    paths: list[Path] = []
    for raw in settings_service.settings.components_path or []:
        candidate = Path(raw)
        try:
            candidate_resolved = candidate.resolve(strict=False)
        except OSError:
            candidate_resolved = candidate
        if candidate_resolved == base_resolved:
            continue
        if candidate.is_dir():
            paths.append(candidate)
    return paths


def _decorate_template_with_extension(
    template: dict[str, Any],
    *,
    extension_id: str,
    bundle: str,
    extension_version: str,
    namespaced_id: str,
) -> dict[str, Any]:
    """Stamp the AC-required identity fields onto a frontend-node template.

    The ``namespaced_id`` is also written to the template so a consumer that
    only looks at the value (not the dict key) still sees the canonical
    ``ext:<bundle>:<Class>@<slot>`` identifier.
    """
    template["extension"] = extension_id
    template["bundle"] = bundle
    template["extension_version"] = extension_version
    template["namespaced_id"] = namespaced_id
    return template


def _emit_extension_diagnostics(results: list[LoadResult]) -> None:
    """Surface typed errors/warnings from a batch of LoadResults to the logger.

    The future events pipeline will replace this with structured
    emission; until then we want operators to see what the loader
    rejected without silently dropping the typed payload.
    """
    for result in results:
        for err in result.errors:
            logger.error("Extension load error: %s", format_extension_error(err))
        for warn in result.warnings:
            logger.warning("Extension load warning: %s", format_extension_error(warn))


# Discovery-source precedence for cross-source bundle-name collisions.
# Higher in the list wins.  Ordered from most-authoritative (pip-installed
# distribution = explicit, packaged install) to least (LANGFLOW_COMPONENTS_PATH
# = loose, legacy custom-components path).  Operators who stage a bundle in
# multiple places almost always *want* the more-authoritative copy to win;
# the typed warning is what catches the unintentional case.
_DISCOVERY_PRECEDENCE: tuple[str, ...] = ("installed", "seed", "dev", "inline")


def _resolve_bundle_shadowing(
    *,
    extension_results: list[LoadResult],
    seed_results: list[LoadResult],
    dev_results: list[LoadResult],
    inline_results: list[LoadResult],
) -> tuple[list[LoadResult], list[LoadResult], list[LoadResult], list[LoadResult]]:
    """Drop loser components and emit typed shadow warnings on lower-precedence dups.

    Precedence is :data:`_DISCOVERY_PRECEDENCE` (installed > seed > dev > inline).
    For each bundle name claimed by more than one source, the highest-precedence
    source keeps its components; every other source has its ``components`` cleared
    AND gains a typed warning naming the winning source's path so the operator can
    diagnose without grepping.

    Two distinct codes get emitted depending on which pair collided:

      - ``seed-bundle-shadowed`` (the original code): emitted when an installed
        Extension shadows a seed-directory bundle.  Preserved verbatim so the
        existing CLI warn-only set, snapshot tests, and operator runbooks keep
        working.
      - ``bundle-shadowed`` (new generic code): emitted for every other shadow
        pair (seed-shadows-dev, seed-shadows-inline, dev-shadows-inline,
        installed-shadows-dev/inline).  Carries the loser's source_path as
        ``location`` and the winner's source_path in the message body.

    The returned tuple has the same shape and order as the inputs so the caller
    can splice it back into ``all_results`` without re-ordering.

    Within a single source list, duplicates are not handled here -- the
    per-source loaders surface their own typed errors (``duplicate-distribution``,
    ``duplicate-inline-bundle``) and that diagnostic stays on the result it
    came from.
    """
    sources: dict[str, list[LoadResult]] = {
        "installed": extension_results,
        "seed": seed_results,
        "dev": dev_results,
        "inline": inline_results,
    }

    # First pass: pick the winning source per bundle name.
    # Records the source-kind label so the second pass knows whether to mint a
    # `seed-bundle-shadowed` (existing code) or the new generic `bundle-shadowed`.
    winner_for_bundle: dict[str, tuple[str, LoadResult]] = {}
    for kind in _DISCOVERY_PRECEDENCE:
        for result in sources[kind]:
            if not result.bundle or not result.components:
                # Either the loader never identified a bundle (path-error sentinels)
                # or the source already produced no components -- nothing to shadow.
                continue
            winner_for_bundle.setdefault(result.bundle, (kind, result))

    # Second pass: for each result that is NOT the winner, drop its components
    # and append the typed warning to the result's errors list (mirroring the
    # original ``seed-bundle-shadowed`` flow so CLI exit-code logic keeps
    # treating it as a non-fatal diagnostic that stays attached to the loser).
    for kind in _DISCOVERY_PRECEDENCE:
        for result in sources[kind]:
            if not result.bundle or not result.components:
                continue
            winner_kind, winner_result = winner_for_bundle[result.bundle]
            if winner_result is result:
                continue
            loser_path = str(result.source_path) if result.source_path else result.bundle
            winner_path = str(winner_result.source_path) if winner_result.source_path else winner_result.bundle
            if winner_kind == "installed" and kind == "seed":
                # Preserve the documented code for the documented pair so the
                # existing CLI warn-only set and snapshot tests keep working.
                result.errors.append(
                    ExtensionError(
                        code="seed-bundle-shadowed",
                        message=(
                            f"Seed bundle {result.bundle!r} at {loser_path} is shadowed by an "
                            f"installed Extension of the same name at {winner_path}; "
                            "the seed copy is being skipped."
                        ),
                        location=loser_path,
                        content=result.bundle,
                        hint=(
                            "Remove the seed-directory subdirectory or uninstall the conflicting "
                            "pip distribution so each @official-slot bundle name has exactly one source."
                        ),
                    )
                )
            else:
                result.errors.append(
                    ExtensionError(
                        code="bundle-shadowed",
                        message=(
                            f"Bundle {result.bundle!r} at {loser_path} (source: {kind}) is shadowed "
                            f"by a higher-precedence source at {winner_path} (source: {winner_kind}); "
                            "the lower-precedence copy is being skipped."
                        ),
                        location=loser_path,
                        content=result.bundle,
                        hint=(
                            "Discovery precedence is installed > seed > dev > inline. "
                            f"Either remove the {kind} copy of this bundle or rename it so each "
                            "bundle name comes from exactly one source."
                        ),
                    )
                )
            # Drop components so the registry-population and palette-construction
            # loops naturally skip this result; the typed warning still emits.
            result.components = []

    return extension_results, seed_results, dev_results, inline_results


async def import_extension_components(
    settings_service: "SettingsService",
) -> dict[str, dict[str, Any]]:
    """Build templates for every Component loaded via the Extension System.

    Two sources feed this:
        - Installed Extensions (any pip-installed distribution shipping
          ``extension.json``) -> ``@official`` slot.
        - Subfolders of every ``LANGFLOW_COMPONENTS_PATH`` entry (parsed
          via the settings layer's pathsep split) -> ``@extra`` slot.

    For each :class:`LoadedComponent`, instantiates the class, builds a
    frontend-node template via :func:`create_component_template`, and
    stamps ``extension``, ``bundle``, and ``extension_version`` onto the
    template so consumers of ``/api/v1/all`` can identify the source.

    Returns a mapping shaped like ``{bundle_name: {namespaced_id: template}}``
    where ``namespaced_id`` is the canonical ``ext:<bundle>:<Class>@<slot>``
    address from :class:`LoadedComponent`. The bundle name remains the
    top-level category so ``/all`` continues to group components by source,
    matching the existing built-in / custom layout.

    Components whose class fails to instantiate or template are skipped
    with a logged warning -- one bad bundle must not abort the cache build.
    """
    extension_results = load_installed_extensions()
    # Seed-directory bundles are the second @official-slot production-install
    # source documented in deployment-extensions-production.mdx: a Docker
    # image (or any operator-controlled host) can stage bundles under
    # ``$LANGFLOW_SEED_DIR`` (or the default ``/opt/langflow/bundles``)
    # without going through pip.  Load them through the same pathway as
    # pip-installed Extensions so they enter the BundleRegistry, get
    # registered at @official, and are reloadable when reload is enabled.
    # When neither $LANGFLOW_SEED_DIR is set nor /opt/langflow/bundles
    # exists this is a no-op, so it costs nothing in Mode A.
    seed_results = load_seed_extensions()
    # Dev extensions registered via ``lfx extension dev`` ship the same v0
    # manifest contract as installed extensions; load them through the
    # @official-slot pathway so they enter the BundleRegistry, expose the
    # extension_id/version/namespaced_id metadata the palette needs, and
    # become reloadable via the same endpoint.  This replaces an earlier
    # approach that appended their bundle directories to LANGFLOW_COMPONENTS_PATH,
    # which silently fell back to legacy custom-component loading without
    # extension metadata.
    dev_results = load_dev_extensions()
    inline_results = discover_inline_bundles(_components_path_extension_paths(settings_service))

    # Resolve cross-source bundle-name shadowing in a single pass.  Discovery
    # surfaces four sources -- installed (pip) > seed (filesystem-staged) >
    # dev (`lfx extension dev`) > inline (LANGFLOW_COMPONENTS_PATH) -- and the
    # registry is keyed by bundle name.  Without an explicit precedence the
    # registry-population loop would silently overwrite earlier records with
    # later ones (last-wins by iteration order), and the reload endpoint would
    # then walk the *winner's* source path while the operator edits a different
    # copy on disk: the empty-deltas reload bug.  Drop loser components AND
    # surface the typed warning before either the registry or the palette
    # mapping is built so the operator sees the shadow once with the actual
    # paths involved.
    deduped_extension_results, deduped_seed_results, deduped_dev_results, deduped_inline_results = (
        _resolve_bundle_shadowing(
            extension_results=extension_results,
            seed_results=seed_results,
            dev_results=dev_results,
            inline_results=inline_results,
        )
    )

    _emit_extension_diagnostics(
        [*deduped_extension_results, *deduped_seed_results, *deduped_dev_results, *deduped_inline_results]
    )

    # Populate the process-default BundleRegistry so the reload endpoint
    # (POST /api/v1/extensions/{id}/bundles/{name}/reload) can find a
    # bundle by name.  Without this, every reload returns
    # ``reload-bundle-not-installed`` even for bundles visible in the
    # palette, because the registry is never primed at startup.  Reload
    # later updates the registry directly; the cache hook in
    # :func:`refresh_extension_components_cache` keeps ``component_cache``
    # in sync after a swap.  ``all_results`` is the deduped list so both
    # the registry record and the palette template come from the same
    # winning source path.
    registry = get_default_registry()
    all_results = [
        *deduped_extension_results,
        *deduped_seed_results,
        *deduped_dev_results,
        *deduped_inline_results,
    ]
    for result in all_results:
        if not result.bundle or not result.components or result.slot is None:
            continue
        record = BundleRecord(
            bundle=result.bundle,
            extension_id=result.extension_id or result.bundle,
            extension_version=result.extension_version or "0.0.0",
            slot=result.slot,
            components=tuple(result.components),
            distribution=result.distribution,
            source_path=result.source_path,
        )
        registry.install_bundle(record)

    components_dict: dict[str, dict[str, Any]] = {}
    for result in all_results:
        if not result.bundle:
            continue
        bundle_dict = components_dict.setdefault(result.bundle, {})
        for loaded in result.components:
            try:
                instance = loaded.klass()
                template, _ = create_component_template(
                    component_extractor=instance,
                    module_name=loaded.module_name,
                )
            except Exception as exc:  # noqa: BLE001
                # Defensive: a class whose name ends in "Component" but that
                # doesn't actually inherit from the lfx Component base will
                # blow up here. Skip and log; the rest of the bundle loads.
                await logger.awarning(
                    "Could not build template for %s in bundle %r (skipped): %s",
                    loaded.class_name,
                    loaded.bundle,
                    exc,
                )
                continue
            # Register under the namespaced ID: ``ext:<bundle>:<Class>@<slot>``.
            # This is the canonical address saved flows reference after
            # the migration table rewrites legacy class-name lookups.
            bundle_dict[loaded.namespaced_id] = _decorate_template_with_extension(
                template,
                extension_id=loaded.extension_id,
                bundle=loaded.bundle,
                extension_version=loaded.extension_version,
                namespaced_id=loaded.namespaced_id,
            )
    return components_dict


def refresh_bundle_cache_from_record(record: "BundleRecord") -> None:
    """Rebuild ``component_cache.all_types_dict`` for a single bundle after reload.

    The reload pipeline updates :class:`~lfx.extension.bundle_registry.BundleRegistry`
    in place, but the palette / new-graph construction path reads from the
    flat ``component_cache.all_types_dict``.  Without this, a successful
    reload swaps the registry but leaves the palette stale until the next
    server restart.  Called by :func:`lfx.extension.reload.reload_bundle`
    in Stage 5.

    Components whose class fails to instantiate or template are skipped
    with a logged warning, mirroring :func:`import_extension_components`.
    """
    if component_cache.all_types_dict is None:
        # Cache hasn't been built yet; nothing to refresh.  The first
        # ``get_and_cache_all_types_dict`` call will see the fresh registry
        # entry and pick up the post-reload class set.
        return
    bundle_dict: dict[str, Any] = {}
    failures: list[tuple[str, str]] = []
    for loaded in record.components:
        try:
            instance = loaded.klass()
            template, _ = create_component_template(
                component_extractor=instance,
                module_name=loaded.module_name,
            )
        except Exception as exc:  # noqa: BLE001
            failures.append((loaded.class_name, repr(exc)))
            logger.warning(
                "Could not build template for %s in bundle %r during reload (skipped): %s",
                loaded.class_name,
                record.bundle,
                exc,
            )
            continue
        bundle_dict[loaded.namespaced_id] = _decorate_template_with_extension(
            template,
            extension_id=loaded.extension_id,
            bundle=loaded.bundle,
            extension_version=loaded.extension_version,
            namespaced_id=loaded.namespaced_id,
        )

    expected = len(record.components)
    succeeded = len(bundle_dict)
    # Total failure: every component raised.  Never overwrite an existing
    # cache entry with {} -- that turns the palette black and masks the
    # real problem.  Raise so the post-swap hook layer can surface this
    # as a typed warning on ReloadResult.
    if expected > 0 and succeeded == 0:
        logger.error(
            "Cache rebuild for bundle %r produced zero templates from %d components; "
            "preserving previous cache entry.  Failures: %s",
            record.bundle,
            expected,
            failures,
        )
        first_failure = failures[0][1] if failures else "<none>"
        msg = (
            f"refresh_bundle_cache_from_record: every component in bundle "
            f"{record.bundle!r} failed to template ({expected} attempted, 0 "
            f"succeeded).  First failure: {first_failure}"
        )
        raise RuntimeError(msg)
    if failures:
        logger.error(
            "Partial cache rebuild for bundle %r: %d of %d components failed (succeeded=%d).  Failures: %s",
            record.bundle,
            len(failures),
            expected,
            succeeded,
            failures,
        )

    component_cache.all_types_dict[record.bundle] = bundle_dict

    # Invalidate the precomputed code-hash lookups so flow validation
    # picks up the freshly-loaded class bodies instead of comparing
    # against the pre-reload hashes.  ``get_component_hash_lookups_for_validation``
    # rebuilds them lazily on the next call when both fields are None.
    component_cache.type_to_current_hash = None
    component_cache.all_known_hashes = None


async def get_and_cache_all_types_dict(
    settings_service: "SettingsService",
    telemetry_service: Any | None = None,
):
    """Retrieves and caches the complete dictionary of component types and templates.

    Supports both full and partial (lazy) loading. If the cache is empty, loads built-in Langflow
    components and either fully loads all components or loads only their metadata, depending on the
    lazy loading setting. Merges built-in, custom, and Extension-System components into the cache
    and returns the resulting dictionary.

    Args:
        settings_service: Settings service instance
        telemetry_service: Optional telemetry service for tracking component loading metrics
    """
    if component_cache.all_types_dict is None:
        await logger.adebug("Building components cache")

        langflow_components = await import_langflow_components(settings_service, telemetry_service)
        custom_components_dict = await _determine_loading_strategy(settings_service)
        try:
            extension_components = await import_extension_components(settings_service)
        except Exception as exc:  # noqa: BLE001
            # Extension loading failures should never block legacy component
            # loading: surface and continue.
            await logger.aerror("Extension System load failed; continuing without it: %s", exc)
            extension_components = {}

        # Flatten custom dict if it has a "components" wrapper
        custom_flat = custom_components_dict.get("components", custom_components_dict) or {}

        # Merge built-in, custom, and extension components (no wrapper at cache level).
        # Extension components win on collision so a manifest-shipping bundle
        # supersedes any same-named legacy entry.
        component_cache.all_types_dict = {
            **langflow_components["components"],
            **custom_flat,
            **extension_components,
        }
        component_count = sum(len(comps) for comps in component_cache.all_types_dict.values())
        await logger.adebug(f"Loaded {component_count} components")

        # Precompute code hash lookups for fast flow validation
        _build_code_hash_lookups(component_cache)

    return component_cache.all_types_dict


async def aget_all_types_dict(components_paths: list[str]):
    """Get all types dictionary with full component loading."""
    return await abuild_custom_components(components_paths=components_paths)


async def aget_component_metadata(components_paths: list[str]):
    """Asynchronously retrieves minimal metadata for all components in the specified paths.

    Builds a dictionary containing basic information (such as display name, type, and description) for
    each discovered component, without loading their full templates. Each component entry is marked as
    `lazy_loaded` to indicate that only metadata has been loaded.

    Args:
        components_paths: List of filesystem paths to search for component types and names.

    Returns:
        A dictionary with component types as keys and their corresponding component metadata as values.
    """
    # This builds a skeleton of the all_types_dict with just basic component info

    components_dict: dict = {"components": {}}

    if not components_paths:
        return components_dict

    # Get all component types
    component_types = await discover_component_types(components_paths)
    await logger.adebug(f"Discovered {len(component_types)} component types: {', '.join(component_types)}")

    # For each component type directory
    for component_type in component_types:
        components_dict["components"][component_type] = {}

        # Get list of components in this type
        component_names = await discover_component_names(component_type, components_paths)
        await logger.adebug(f"Found {len(component_names)} components for type {component_type}")

        # Create stub entries with just basic metadata
        for name in component_names:
            # Get minimal metadata for component
            metadata = await get_component_minimal_metadata(component_type, name, components_paths)

            if metadata:
                components_dict["components"][component_type][name] = metadata
                # Mark as needing full loading
                components_dict["components"][component_type][name]["lazy_loaded"] = True

    return components_dict


async def discover_component_types(components_paths: list[str]) -> list[str]:
    """Discover available component types by scanning directories."""
    component_types: set[str] = set()

    for path in components_paths:
        path_obj = Path(path)
        if not path_obj.exists():
            continue

        for item in path_obj.iterdir():
            # Only include directories that don't start with _ or .
            if item.is_dir() and not item.name.startswith(("_", ".")):
                component_types.add(item.name)

    # Add known types that might not be in directories
    standard_types = {
        "agents",
        "chains",
        "embeddings",
        "llms",
        "memories",
        "prompts",
        "tools",
        "retrievers",
        "textsplitters",
        "toolkits",
        "utilities",
        "vectorstores",
        "custom_components",
        "documentloaders",
        "outputparsers",
        "wrappers",
    }

    component_types.update(standard_types)

    return sorted(component_types)


async def discover_component_names(component_type: str, components_paths: list[str]) -> list[str]:
    """Discover component names for a specific type by scanning directories."""
    component_names: set[str] = set()

    for path in components_paths:
        type_dir = Path(path) / component_type

        if type_dir.exists():
            for filename in type_dir.iterdir():
                # Get Python files that don't start with __
                if filename.name.endswith(".py") and not filename.name.startswith("__"):
                    component_name = filename.name[:-3]  # Remove .py extension
                    component_names.add(component_name)

    return sorted(component_names)


async def get_component_minimal_metadata(component_type: str, component_name: str, components_paths: list[str]):
    """Extract minimal metadata for a component without loading its full implementation."""
    # Create a more complete metadata structure that the UI needs
    metadata = {
        "display_name": component_name.replace("_", " ").title(),
        "name": component_name,
        "type": component_type,
        "description": f"A {component_type} component (not fully loaded)",
        "template": {
            "_type": component_type,
            "inputs": {},
            "outputs": {},
            "output_types": [],
            "documentation": f"A {component_type} component",
            "display_name": component_name.replace("_", " ").title(),
            "base_classes": [component_type],
        },
    }

    # Try to find the file to verify it exists
    component_path = None
    for path in components_paths:
        candidate_path = Path(path) / component_type / f"{component_name}.py"
        if candidate_path.exists():
            component_path = candidate_path
            break

    if not component_path:
        return None

    return metadata


async def ensure_component_loaded(component_type: str, component_name: str, settings_service: "SettingsService"):
    """Ensure a component is fully loaded if it was only partially loaded."""
    # If already fully loaded, return immediately
    component_key = f"{component_type}:{component_name}"
    if component_key in component_cache.fully_loaded_components:
        return

    # If we don't have a cache or the component doesn't exist in the cache, nothing to do
    if (
        not component_cache.all_types_dict
        or "components" not in component_cache.all_types_dict
        or component_type not in component_cache.all_types_dict["components"]
        or component_name not in component_cache.all_types_dict["components"][component_type]
    ):
        return

    # Check if component is marked for lazy loading
    if component_cache.all_types_dict["components"][component_type][component_name].get("lazy_loaded", False):
        await logger.adebug(f"Fully loading component {component_type}:{component_name}")

        # Load just this specific component
        full_component = await load_single_component(
            component_type, component_name, settings_service.settings.components_path
        )

        if full_component:
            # Replace the stub with the fully loaded component
            component_cache.all_types_dict["components"][component_type][component_name] = full_component
            # Remove lazy_loaded flag if it exists
            if "lazy_loaded" in component_cache.all_types_dict["components"][component_type][component_name]:
                del component_cache.all_types_dict["components"][component_type][component_name]["lazy_loaded"]

            # Mark as fully loaded
            component_cache.fully_loaded_components[component_key] = True
            await logger.adebug(f"Component {component_type}:{component_name} fully loaded")
        else:
            await logger.awarning(f"Failed to fully load component {component_type}:{component_name}")


async def load_single_component(component_type: str, component_name: str, components_paths: list[str]):
    """Load a single component fully."""
    from lfx.custom.utils import get_single_component_dict

    try:
        # Delegate to a more specific function that knows how to load
        # a single component of a specific type
        return await get_single_component_dict(component_type, component_name, components_paths)
    except (ImportError, ModuleNotFoundError) as e:
        # Handle issues with importing the component or its dependencies
        await logger.aerror(f"Import error loading component {component_type}:{component_name}: {e!s}")
        return None
    except (AttributeError, TypeError) as e:
        # Handle issues with component structure or type errors
        await logger.aerror(f"Component structure error for {component_type}:{component_name}: {e!s}")
        return None
    except FileNotFoundError as e:
        # Handle missing files
        await logger.aerror(f"File not found for component {component_type}:{component_name}: {e!s}")
        return None
    except ValueError as e:
        # Handle invalid values or configurations
        await logger.aerror(f"Invalid configuration for component {component_type}:{component_name}: {e!s}")
        return None
    except (KeyError, IndexError) as e:
        # Handle data structure access errors
        await logger.aerror(f"Data structure error for component {component_type}:{component_name}: {e!s}")
        return None
    except RuntimeError as e:
        # Handle runtime errors
        await logger.aerror(f"Runtime error loading component {component_type}:{component_name}: {e!s}")
        await logger.adebug("Full traceback for runtime error", exc_info=True)
        return None
    except OSError as e:
        # Handle OS-related errors (file system, permissions, etc.)
        await logger.aerror(f"OS error loading component {component_type}:{component_name}: {e!s}")
        return None


# Also add a utility function to load specific component types
async def get_type_dict(component_type: str, settings_service: Optional["SettingsService"] = None):
    """Get a specific component type dictionary, loading if needed."""
    if settings_service is None:
        # Import here to avoid circular imports
        from langflow.services.deps import get_settings_service

        settings_service = get_settings_service()

    # Make sure all_types_dict is loaded (at least partially)
    if component_cache.all_types_dict is None:
        await get_and_cache_all_types_dict(settings_service)

    # Check if component type exists in the cache
    if (
        component_cache.all_types_dict
        and "components" in component_cache.all_types_dict
        and component_type in component_cache.all_types_dict["components"]
    ):
        # If in lazy mode, ensure all components of this type are fully loaded
        if settings_service.settings.lazy_load_components:
            for component_name in list(component_cache.all_types_dict["components"][component_type].keys()):
                await ensure_component_loaded(component_type, component_name, settings_service)

        return component_cache.all_types_dict["components"][component_type]

    return {}


# TypeError: unhashable type: 'list'
def key_func(*args, **kwargs):
    # components_paths is a list of paths
    return json.dumps(args) + json.dumps(kwargs)


async def aget_all_components(components_paths, *, as_dict=False):
    """Get all components names combining native and custom components."""
    all_types_dict = await aget_all_types_dict(components_paths)
    components = {} if as_dict else []
    for category in all_types_dict.values():
        for component in category.values():
            component["name"] = component["display_name"]
            if as_dict:
                components[component["name"]] = component
            else:
                components.append(component)
    return components


def get_all_components(components_paths, *, as_dict=False):
    """Get all components names combining native and custom components."""
    # Import here to avoid circular imports
    from lfx.custom.utils import build_custom_components

    all_types_dict = build_custom_components(components_paths=components_paths)
    components = [] if not as_dict else {}
    for category in all_types_dict.values():
        for component in category.values():
            component["name"] = component["display_name"]
            if as_dict:
                components[component["name"]] = component
            else:
                components.append(component)
    return components
