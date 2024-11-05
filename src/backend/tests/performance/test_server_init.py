import asyncio

import pytest
from langflow.services.deps import get_settings_service


@pytest.mark.benchmark
async def test_initialize_services():
    """Benchmark the initialization of services."""
    from langflow.services.utils import initialize_services

    await asyncio.to_thread(initialize_services, fix_migration=False)


@pytest.mark.benchmark
async def test_setup_llm_caching():
    """Benchmark LLM caching setup."""
    from langflow.interface.utils import setup_llm_caching

    await asyncio.to_thread(setup_llm_caching)


@pytest.mark.benchmark
async def test_initialize_super_user():
    """Benchmark super user initialization."""
    from langflow.initial_setup.setup import initialize_super_user_if_needed
    from langflow.services.utils import initialize_services

    await asyncio.to_thread(initialize_services, fix_migration=False)
    await asyncio.to_thread(initialize_super_user_if_needed)


@pytest.mark.benchmark
async def test_get_and_cache_all_types_dict():
    """Benchmark get_and_cache_all_types_dict function."""
    from langflow.interface.types import get_and_cache_all_types_dict

    settings_service = await asyncio.to_thread(get_settings_service)
    result = await asyncio.to_thread(get_and_cache_all_types_dict, settings_service)
    assert result is not None


@pytest.mark.benchmark
async def test_create_starter_projects():
    """Benchmark creation of starter projects."""
    from langflow.initial_setup.setup import create_or_update_starter_projects
    from langflow.interface.types import get_and_cache_all_types_dict
    from langflow.services.utils import initialize_services

    await asyncio.to_thread(initialize_services, fix_migration=False)
    settings_service = await asyncio.to_thread(get_settings_service)
    types_dict = await get_and_cache_all_types_dict(settings_service)
    await asyncio.to_thread(create_or_update_starter_projects, types_dict)


@pytest.mark.benchmark
async def test_load_flows():
    """Benchmark loading flows from directory."""
    from langflow.initial_setup.setup import load_flows_from_directory

    await asyncio.to_thread(load_flows_from_directory)
