import asyncio
import json
from typing import TYPE_CHECKING

from loguru import logger
from langflow.custom.utils import abuild_custom_components, build_custom_components

if TYPE_CHECKING:
    from langflow.services.cache.base import CacheService
    from langflow.services.settings.service import SettingsService


async def aget_all_types_dict(components_paths):
    """Get all types dictionary combining native and custom components."""
    custom_components_from_file = await abuild_custom_components(components_paths=components_paths)
    return custom_components_from_file


def get_all_types_dict(components_paths):
    """Get all types dictionary combining native and custom components."""
    custom_components_from_file = build_custom_components(components_paths=components_paths)
    return custom_components_from_file


# TypeError: unhashable type: 'list'
def key_func(*args, **kwargs):
    # components_paths is a list of paths
    return json.dumps(args) + json.dumps(kwargs)


async def aget_all_components(components_paths, as_dict=False):
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


def get_all_components(components_paths, as_dict=False):
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


all_types_dict_cache = None


async def get_and_cache_all_types_dict(
    settings_service: "SettingsService",
    cache_service: "CacheService",
    force_refresh: bool = False,
    lock: asyncio.Lock | None = None,
):
    global all_types_dict_cache
    if all_types_dict_cache is None:
        logger.debug("Building langchain types dict")
        all_types_dict_cache = await aget_all_types_dict(settings_service.settings.components_path)

    return all_types_dict_cache
