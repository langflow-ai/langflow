import asyncio
import os

import pytest
from langflow.services.deps import get_settings_service


@pytest.fixture(autouse=True)
def setup_database_url(tmp_path, monkeypatch):
    """Setup a temporary database URL for testing."""
    db_path = tmp_path / "test_performance.db"
    test_db_url = f"sqlite:///{db_path}"

    # Store original value
    original_value = os.environ.get("LANGFLOW_DATABASE_URL")

    # Set environment variable
    monkeypatch.setenv("LANGFLOW_DATABASE_URL", test_db_url)

    # Reset settings service to ensure it picks up new database URL

    yield test_db_url

    # Restore original value if it existed
    if original_value is not None:
        monkeypatch.setenv("LANGFLOW_DATABASE_URL", original_value)
    else:
        monkeypatch.delenv("LANGFLOW_DATABASE_URL", raising=False)


@pytest.mark.benchmark
async def test_initialize_services(setup_database_url):
    """Benchmark the initialization of services."""
    from langflow.services.utils import initialize_services

    test_db_url = setup_database_url
    await asyncio.to_thread(initialize_services, fix_migration=False)
    settings_service = await asyncio.to_thread(get_settings_service)
    assert settings_service.settings.database_url == test_db_url


@pytest.mark.benchmark
async def test_setup_llm_caching(setup_database_url):
    """Benchmark LLM caching setup."""
    from langflow.interface.utils import setup_llm_caching

    test_db_url = setup_database_url
    await asyncio.to_thread(setup_llm_caching)
    settings_service = await asyncio.to_thread(get_settings_service)
    assert settings_service.settings.database_url == test_db_url


@pytest.mark.benchmark
async def test_initialize_super_user(setup_database_url):
    """Benchmark super user initialization."""
    from langflow.initial_setup.setup import initialize_super_user_if_needed
    from langflow.services.utils import initialize_services

    test_db_url = setup_database_url
    await asyncio.to_thread(initialize_services, fix_migration=False)
    await asyncio.to_thread(initialize_super_user_if_needed)
    settings_service = await asyncio.to_thread(get_settings_service)
    assert settings_service.settings.database_url == test_db_url


@pytest.mark.benchmark
async def test_get_and_cache_all_types_dict(setup_database_url):
    """Benchmark get_and_cache_all_types_dict function."""
    from langflow.interface.types import get_and_cache_all_types_dict
    from langflow.services.utils import initialize_services

    test_db_url = setup_database_url
    await asyncio.to_thread(initialize_services, fix_migration=False)
    settings_service = await asyncio.to_thread(get_settings_service)
    result = await get_and_cache_all_types_dict(settings_service)
    assert result is not None
    assert settings_service.settings.database_url == test_db_url


@pytest.mark.benchmark
async def test_create_starter_projects(setup_database_url):
    """Benchmark creation of starter projects."""
    from langflow.initial_setup.setup import create_or_update_starter_projects
    from langflow.interface.types import get_and_cache_all_types_dict
    from langflow.services.utils import initialize_services

    test_db_url = setup_database_url
    await asyncio.to_thread(initialize_services, fix_migration=False)
    settings_service = await asyncio.to_thread(get_settings_service)
    types_dict = await get_and_cache_all_types_dict(settings_service)
    await asyncio.to_thread(create_or_update_starter_projects, types_dict)
    assert settings_service.settings.database_url == test_db_url


@pytest.mark.benchmark
async def test_load_flows(setup_database_url):
    """Benchmark loading flows from directory."""
    from langflow.initial_setup.setup import load_flows_from_directory

    test_db_url = setup_database_url
    await asyncio.to_thread(load_flows_from_directory)
    settings_service = await asyncio.to_thread(get_settings_service)
    assert settings_service.settings.database_url == test_db_url
