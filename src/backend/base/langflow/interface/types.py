import asyncio
import json
from typing import TYPE_CHECKING

from loguru import logger
from langflow.custom.utils import abuild_custom_components, build_custom_components
from langflow.services.cache.base import AsyncBaseCacheService

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


async def get_and_cache_all_types_dict(
    settings_service: "SettingsService",
    cache_service: "CacheService",
    force_refresh: bool = False,
    lock: asyncio.Lock | None = None,
):
    async def get_from_cache(key):
        """
        Retrieves a value from the cache based on the given key.

        Args:
            key: The key to retrieve the value from the cache.

        Returns:
            The value associated with the given key in the cache.

        Raises:
            None.
        """
        return await cache_service.get(key=key, lock=lock)

    async def set_in_cache(key, value):
        """
        Sets the given key-value pair in the cache.

        Parameters:
        - key: The key to set in the cache.
        - value: The value to associate with the key in the cache.

        Returns:
        None
        """
        if isinstance(cache_service, AsyncBaseCacheService):
            await cache_service.set(key=key, value=value, lock=lock)
        else:
            cache_service.set(key=key, value=value, lock=lock)

    all_types_dict = await get_from_cache("all_types_dict")
    if not all_types_dict or force_refresh:
        logger.debug("Building langchain types dict")
        all_types_dict = await aget_all_types_dict(settings_service.settings.components_path)
        await set_in_cache("all_types_dict", all_types_dict)

    return all_types_dict
