import asyncio
import hashlib
import importlib
import inspect
import json
import os
import pkgutil
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import orjson

from lfx.constants import BASE_COMPONENTS_PATH
from lfx.custom.utils import abuild_custom_components, create_component_template
from lfx.log.logger import logger

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService

MIN_MODULE_PARTS = 2
EXPECTED_RESULT_LENGTH = 2  # Expected length of the tuple returned by _process_single_module


# Create a class to manage component cache instead of using globals
class ComponentCache:
    def __init__(self):
        """Initializes the component cache.

        Creates empty storage for all component types and tracking of fully loaded components.
        """
        self.all_types_dict: dict[str, Any] | None = None
        self.fully_loaded_components: dict[str, bool] = {}


# Singleton instance
component_cache = ComponentCache()


def _dev_mode() -> bool:
    """Detect if running in development mode.

    Development mode is detected by:
    1. LFX_DEV environment variable: "1"/"true"/"yes" = dev, "0"/"false"/"no" = prod
    2. If LFX_DEV not set: Editable install = dev, otherwise = prod

    Returns:
        True if in development mode, False otherwise
    """
    # 1) Check env override (takes precedence)
    lfx_dev = os.getenv("LFX_DEV", "").lower()
    if lfx_dev:
        # Explicit setting: 1/true/yes = dev, 0/false/no = prod
        if lfx_dev in {"1", "true", "yes"}:
            return True
        if lfx_dev in {"0", "false", "no"}:
            return False

    # 2) If no env var, use editable install heuristic
    try:
        import lfx

        src = Path(inspect.getfile(lfx)).resolve()
        # If the path doesn't contain site-packages, it's likely an editable install
        return "site-packages" not in str(src)
    except Exception:  # noqa: BLE001
        return False


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

                response = httpx.get(custom_path, timeout=10.0)
                response.raise_for_status()
                blob = orjson.loads(response.content)
            else:
                # Load from file path
                index_path = Path(custom_path)
                if not index_path.exists():
                    logger.warning(f"Custom component index not found at {custom_path}")
                    return None
                blob = orjson.loads(index_path.read_bytes())
        else:
            # Use built-in index
            pkg_dir = Path(inspect.getfile(lfx)).parent
            index_path = pkg_dir / "_assets" / "component_index.json"

            if not index_path.exists():
                return None

            blob = orjson.loads(index_path.read_bytes())

        # Integrity check: verify SHA256
        tmp = dict(blob)
        sha = tmp.pop("sha256", None)
        if not sha:
            return None

        # Use orjson for hash calculation to match build script
        calc = hashlib.sha256(orjson.dumps(tmp, option=orjson.OPT_SORT_KEYS)).hexdigest()
        if sha != calc:
            logger.warning("Component index integrity check failed")
            return None

        # Version check: ensure index matches installed lfx version
        try:
            from importlib.metadata import version

            installed_version = version("lfx")
            if blob.get("version") != installed_version:
                logger.debug(
                    f"Component index version mismatch: index={blob.get('version')}, installed={installed_version}"
                )
                return None
        except Exception:  # noqa: BLE001
            # If version check fails, still return blob (likely dev mode)
            return blob
        else:
            return blob
    except Exception as e:  # noqa: BLE001
        logger.debug(f"Failed to read component index: {e}")
        return None


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

        # Get version
        try:
            from importlib.metadata import version

            lfx_version = version("lfx")
        except Exception:  # noqa: BLE001
            lfx_version = "0.0.0+unknown"

        # Build index structure
        index = {
            "version": lfx_version,
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


async def import_langflow_components(settings_service: Optional["SettingsService"] = None):
    """Asynchronously discovers and loads all built-in Langflow components with module-level parallelization.

    In production mode (non-dev), attempts to load components from a prebuilt static index for instant startup.
    Falls back to dynamic module scanning if index is unavailable or invalid. When dynamic loading is used,
    the generated index is cached for future use.

    Scans the `lfx.components` package and its submodules in parallel, instantiates classes that are subclasses
    of `Component` or `CustomComponent`, and generates their templates. Components are grouped by their
    top-level subpackage name.

    Args:
        settings_service: Optional settings service to get custom index path

    Returns:
        A dictionary with a "components" key mapping top-level package names to their component templates.
    """
    # Track if we need to save the index after building
    should_save_index = False

    # Fast path: load from prebuilt index if not in dev mode
    if not _dev_mode():
        # Get custom index path from settings if available
        custom_index_path = None
        if settings_service and settings_service.settings.components_index_path:
            custom_index_path = settings_service.settings.components_index_path
            await logger.adebug(f"Using custom component index: {custom_index_path}")

        index = _read_component_index(custom_index_path)
        if index and "entries" in index:
            source = custom_index_path or "built-in index"
            await logger.adebug(f"Loading components from {source}")
            # Reconstruct modules_dict from index entries
            modules_dict = {}
            for top_level, components in index["entries"]:
                if top_level not in modules_dict:
                    modules_dict[top_level] = {}
                modules_dict[top_level].update(components)
            await logger.adebug(f"Loaded {len(modules_dict)} component categories from index")
            return {"components": modules_dict}

        # Index failed to load in production - try cache before building
        await logger.adebug("Prebuilt index not available, checking cache")
        try:
            cache_path = _get_cache_path()
            if cache_path.exists():
                await logger.adebug(f"Attempting to load from cache: {cache_path}")
                index = _read_component_index(str(cache_path))
                if index and "entries" in index:
                    await logger.adebug("Loading components from cached index")
                    modules_dict = {}
                    for top_level, components in index["entries"]:
                        if top_level not in modules_dict:
                            modules_dict[top_level] = {}
                        modules_dict[top_level].update(components)
                    await logger.adebug(f"Loaded {len(modules_dict)} component categories from cache")
                    return {"components": modules_dict}
        except Exception as e:  # noqa: BLE001
            await logger.adebug(f"Cache load failed: {e}")

        # No cache available, will build and save
        await logger.adebug("Falling back to dynamic loading")
        should_save_index = True

    # Fallback: dynamic loading (dev mode or index unavailable)
    modules_dict = {}
    try:
        import lfx.components as components_pkg
    except ImportError as e:
        await logger.aerror(f"Failed to import langflow.components package: {e}", exc_info=True)
        return {"components": modules_dict}

    # Collect all module names to process
    module_names = []
    for _, modname, _ in pkgutil.walk_packages(components_pkg.__path__, prefix=components_pkg.__name__ + "."):
        # Skip if the module is in the deactivated folder
        if "deactivated" not in modname:
            module_names.append(modname)

    if not module_names:
        return {"components": modules_dict}

    # Create tasks for parallel module processing
    tasks = [asyncio.to_thread(_process_single_module, modname) for modname in module_names]

    # Wait for all modules to be processed
    try:
        module_results = await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as e:  # noqa: BLE001
        await logger.aerror(f"Error during parallel module processing: {e}", exc_info=True)
        return {"components": modules_dict}

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

    # Save the generated index to cache if needed (production mode with missing index)
    if should_save_index and modules_dict:
        await logger.adebug("Saving generated component index to cache")
        _save_generated_index(modules_dict)

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
    # Extract the top-level subpackage name after "langflow.components."
    # e.g., "langflow.components.Notion.add_content_to_page" -> "Notion"
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


async def _determine_loading_strategy(settings_service: "SettingsService") -> dict:
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

    return component_cache.all_types_dict


async def get_and_cache_all_types_dict(
    settings_service: "SettingsService",
):
    """Retrieves and caches the complete dictionary of component types and templates.

    Supports both full and partial (lazy) loading. If the cache is empty, loads built-in Langflow
    components and either fully loads all components or loads only their metadata, depending on the
    lazy loading setting. Merges built-in and custom components into the cache and returns the
    resulting dictionary.
    """
    if component_cache.all_types_dict is None:
        await logger.adebug("Building components cache")

        langflow_components = await import_langflow_components(settings_service)
        custom_components_dict = await _determine_loading_strategy(settings_service)

        # merge the dicts
        component_cache.all_types_dict = {
            **langflow_components["components"],
            **custom_components_dict,
        }
        component_count = sum(len(comps) for comps in component_cache.all_types_dict.values())
        await logger.adebug(f"Loaded {component_count} components")
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
