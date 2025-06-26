"""Component interface and management system for Langflow.

This module provides the core interface for managing and loading components
in Langflow, including:
- Dynamic component discovery and loading
- Component template creation and management
- Component cache management and optimization
- Custom component integration and processing

The ComponentCache class manages component state and ensures efficient
loading and retrieval of component definitions throughout the application.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import pkgutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from langflow.custom.utils import abuild_custom_components, create_component_template
from langflow.services.settings.base import BASE_COMPONENTS_PATH

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


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


async def import_langflow_components():
    """Asynchronously discovers and loads all built-in Langflow components with module-level parallelization.

    Scans the `langflow.components` package and its submodules in parallel, instantiates classes that are subclasses
    of `Component` or `CustomComponent`, and generates their templates. Components are grouped by their
    top-level subpackage name.

    Returns:
        A dictionary with a "components" key mapping top-level package names to their component templates.
    """
    modules_dict = {}
    try:
        import langflow.components as components_pkg
    except ImportError as e:
        logger.error(f"Failed to import langflow.components package: {e}", exc_info=True)
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
        logger.error(f"Error during parallel module processing: {e}", exc_info=True)
        return {"components": modules_dict}

    # Merge results from all modules
    for result in module_results:
        if isinstance(result, Exception):
            logger.warning(f"Module processing failed: {result}")
            continue

        if result and isinstance(result, tuple) and len(result) == EXPECTED_RESULT_LENGTH:
            top_level, components = result
            if top_level and components:
                if top_level not in modules_dict:
                    modules_dict[top_level] = {}
                modules_dict[top_level].update(components)

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
    except (ImportError, AttributeError) as e:
        logger.error(f"Error importing module {modname}: {e}", exc_info=True)
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
            comp_template, _ = create_component_template(component_extractor=comp_instance)
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


async def get_and_cache_all_types_dict(
    settings_service: SettingsService,
):
    """Retrieves and caches the complete dictionary of component types and templates.

    Supports both full and partial (lazy) loading. If the cache is empty, loads built-in Langflow
    components and either fully loads all components or loads only their metadata, depending on the
    lazy loading setting. Merges built-in and custom components into the cache and returns the
    resulting dictionary.
    """
    if component_cache.all_types_dict is None:
        logger.debug("Building components cache")

        langflow_components = await import_langflow_components()
        component_cache.all_types_dict = {}
        if settings_service.settings.lazy_load_components:
            # Partial loading mode - just load component metadata
            logger.debug("Using partial component loading")
            component_cache.all_types_dict = await aget_component_metadata(settings_service.settings.components_path)
        elif (
            settings_service.settings.components_path
            and BASE_COMPONENTS_PATH not in settings_service.settings.components_path
        ):
            # Traditional full loading
            component_cache.all_types_dict = await aget_all_types_dict(settings_service.settings.components_path)

        # Log custom component loading stats
        components_dict = component_cache.all_types_dict or {}
        component_count = sum(len(comps) for comps in components_dict.get("components", {}).values())
        if component_count > 0 and settings_service.settings.components_path:
            logger.debug(f"Built {component_count} custom components from {settings_service.settings.components_path}")

        # merge the dicts
        component_cache.all_types_dict = {
            **langflow_components["components"],
            **components_dict,
        }
        component_count = sum(len(comps) for comps in component_cache.all_types_dict.values())
        logger.debug(f"Loaded {component_count} components")
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
    logger.debug(f"Discovered {len(component_types)} component types: {', '.join(component_types)}")

    # For each component type directory
    for component_type in component_types:
        components_dict["components"][component_type] = {}

        # Get list of components in this type
        component_names = await discover_component_names(component_type, components_paths)
        logger.debug(f"Found {len(component_names)} components for type {component_type}")

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


async def ensure_component_loaded(component_type: str, component_name: str, settings_service: SettingsService):
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
        logger.debug(f"Fully loading component {component_type}:{component_name}")

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
            logger.debug(f"Component {component_type}:{component_name} fully loaded")
        else:
            logger.warning(f"Failed to fully load component {component_type}:{component_name}")


async def load_single_component(component_type: str, component_name: str, components_paths: list[str]):
    """Load a single component fully."""
    from langflow.custom.utils import get_single_component_dict

    try:
        # Delegate to a more specific function that knows how to load
        # a single component of a specific type
        return await get_single_component_dict(component_type, component_name, components_paths)
    except (ImportError, ModuleNotFoundError) as e:
        # Handle issues with importing the component or its dependencies
        logger.error(f"Import error loading component {component_type}:{component_name}: {e!s}")
        return None
    except (AttributeError, TypeError) as e:
        # Handle issues with component structure or type errors
        logger.error(f"Component structure error for {component_type}:{component_name}: {e!s}")
        return None
    except FileNotFoundError as e:
        # Handle missing files
        logger.error(f"File not found for component {component_type}:{component_name}: {e!s}")
        return None
    except ValueError as e:
        # Handle invalid values or configurations
        logger.error(f"Invalid configuration for component {component_type}:{component_name}: {e!s}")
        return None
    except (KeyError, IndexError) as e:
        # Handle data structure access errors
        logger.error(f"Data structure error for component {component_type}:{component_name}: {e!s}")
        return None
    except RuntimeError as e:
        # Handle runtime errors
        logger.error(f"Runtime error loading component {component_type}:{component_name}: {e!s}")
        logger.debug("Full traceback for runtime error", exc_info=True)
        return None
    except OSError as e:
        # Handle OS-related errors (file system, permissions, etc.)
        logger.error(f"OS error loading component {component_type}:{component_name}: {e!s}")
        return None


# Also add a utility function to load specific component types
async def get_type_dict(component_type: str, settings_service: SettingsService | None = None):
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
    from langflow.custom.utils import build_custom_components

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
