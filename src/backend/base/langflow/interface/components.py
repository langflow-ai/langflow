from __future__ import annotations

import json
import importlib
import os
import sys
from typing import TYPE_CHECKING, List, Optional

from loguru import logger

from langflow.custom.utils import abuild_custom_components, build_custom_components

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService

# Cache variables
all_types_dict_cache = None
_fully_loaded_components = {}

async def get_and_cache_all_types_dict(
    settings_service: 'SettingsService',
):
    """Get and cache the types dictionary, with partial loading support."""
    global all_types_dict_cache
    
    if all_types_dict_cache is None:
        logger.debug("Building langchain types dict")
        
        if settings_service.settings.lazy_load_components:
            # Partial loading mode - just load component metadata
            logger.debug("Using partial component loading")
            all_types_dict_cache = await aget_component_metadata(settings_service.settings.components_path)
        else:
            # Traditional full loading
            all_types_dict_cache = await aget_all_types_dict(settings_service.settings.components_path)
            
        # Log loading stats
        component_count = sum(
            len(comps) 
            for comps in all_types_dict_cache.get("components", {}).values()
        )
        logger.debug(f"Loaded {component_count} components")
    
    return all_types_dict_cache

async def aget_all_types_dict(components_paths: List[str]):
    """Get all types dictionary with full component loading."""
    return await abuild_custom_components(components_paths=components_paths)

async def aget_component_metadata(components_paths: List[str]):
    """Get just the metadata for all components without loading full templates."""
    # This builds a skeleton of the all_types_dict with just basic component info
    
    components_dict = {"components": {}}
    
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

async def discover_component_types(components_paths: List[str]) -> List[str]:
    """Discover available component types by scanning directories."""
    component_types = set()
    
    for path in components_paths:
        if not os.path.exists(path):
            continue
            
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            # Only include directories that don't start with _ or .
            if os.path.isdir(item_path) and not item.startswith(("_", ".")):
                component_types.add(item)
    
    # Add known types that might not be in directories
    standard_types = {
        "agents", "chains", "embeddings", "llms", "memories", 
        "prompts", "tools", "retrievers", "textsplitters", 
        "toolkits", "utilities", "vectorstores", "custom_components",
        "documentloaders", "outputparsers", "wrappers"
    }
    
    component_types.update(standard_types)
    
    return sorted(list(component_types))

async def discover_component_names(component_type: str, components_paths: List[str]) -> List[str]:
    """Discover component names for a specific type by scanning directories."""
    component_names = set()
    
    for path in components_paths:
        type_dir = os.path.join(path, component_type)
        
        if os.path.exists(type_dir):
            for filename in os.listdir(type_dir):
                # Get Python files that don't start with __
                if filename.endswith('.py') and not filename.startswith('__'):
                    component_name = filename[:-3]  # Remove .py extension
                    component_names.add(component_name)
    
    return sorted(list(component_names))

async def get_component_minimal_metadata(component_type: str, component_name: str, components_paths: List[str]):
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
        }
    }
    
    # Try to find the file to verify it exists
    component_path = None
    for path in components_paths:
        candidate_path = os.path.join(path, component_type, f"{component_name}.py")
        if os.path.exists(candidate_path):
            component_path = candidate_path
            break
    
    if not component_path:
        return None
        
    return metadata

async def ensure_component_loaded(component_type: str, component_name: str, settings_service: 'SettingsService'):
    """Ensure a component is fully loaded if it was only partially loaded."""
    global all_types_dict_cache, _fully_loaded_components
    
    # If already fully loaded, return immediately
    component_key = f"{component_type}:{component_name}"
    if component_key in _fully_loaded_components:
        return
        
    # If we don't have a cache or the component doesn't exist in the cache, nothing to do
    if not all_types_dict_cache or not all_types_dict_cache.get("components", {}).get(component_type, {}).get(component_name):
        return
        
    # Check if component is marked for lazy loading
    if all_types_dict_cache["components"][component_type][component_name].get("lazy_loaded", False):
        logger.debug(f"Fully loading component {component_type}:{component_name}")
        
        # Load just this specific component
        full_component = await load_single_component(component_type, component_name, settings_service.settings.components_path)
        
        if full_component:
            # Replace the stub with the fully loaded component
            all_types_dict_cache["components"][component_type][component_name] = full_component
            # Remove lazy_loaded flag if it exists
            if "lazy_loaded" in all_types_dict_cache["components"][component_type][component_name]:
                del all_types_dict_cache["components"][component_type][component_name]["lazy_loaded"]
            
            # Mark as fully loaded
            _fully_loaded_components[component_key] = True
            logger.debug(f"Component {component_type}:{component_name} fully loaded")
        else:
            logger.warning(f"Failed to fully load component {component_type}:{component_name}")

async def load_single_component(component_type: str, component_name: str, components_paths: List[str]):
    """Load a single component fully."""
    from langflow.custom.utils import get_single_component_dict
    try:
        # Delegate to a more specific function that knows how to load
        # a single component of a specific type
        return await get_single_component_dict(component_type, component_name, components_paths)
    except Exception as e:
        logger.error(f"Error loading component {component_type}:{component_name}: {str(e)}")
        return None

# Also add a utility function to load specific component types
async def get_type_dict(component_type: str, settings_service: 'SettingsService' = None):
    """Get a specific component type dictionary, loading if needed."""
    global all_types_dict_cache
    
    if settings_service is None:
        # Import here to avoid circular imports
        from langflow.services.deps import get_settings_service
        settings_service = get_settings_service()
    
    # Make sure all_types_dict is loaded (at least partially)
    if all_types_dict_cache is None:
        await get_and_cache_all_types_dict(settings_service)
    
    # If the component type exists in the cache, return it
    if component_type in all_types_dict_cache.get("components", {}):
        # If in lazy mode, ensure all components of this type are fully loaded
        if settings_service.settings.lazy_load_components:
            for component_name in list(all_types_dict_cache["components"][component_type].keys()):
                await ensure_component_loaded(component_type, component_name, settings_service)
                
        return all_types_dict_cache["components"][component_type]
    
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
    all_types_dict = get_all_types_dict(components_paths)
    components = [] if not as_dict else {}
    for category in all_types_dict.values():
        for component in category.values():
            component["name"] = component["display_name"]
            if as_dict:
                components[component["name"]] = component
            else:
                components.append(component)
    return components
