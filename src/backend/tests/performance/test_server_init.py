import asyncio
import os

import pytest
from langflow.services.deps import get_settings_service


@pytest.fixture(scope="module")
def shared_tmp_path(tmp_path_factory):
    """Create a shared temporary directory for all tests in the module."""
    return tmp_path_factory.mktemp("test_db")


@pytest.fixture
async def setup_database_url(shared_tmp_path, monkeypatch):
    """Setup a temporary database URL for testing."""
    from langflow.services.utils import initialize_services

    db_path = shared_tmp_path / "test_performance.db"
    test_db_url = f"sqlite:///{db_path}"

    # Store original value
    original_value = os.environ.get("LANGFLOW_DATABASE_URL")

    # Set environment variable
    monkeypatch.setenv("LANGFLOW_DATABASE_URL", test_db_url)

    # Initialize services with our test database URL
    await asyncio.to_thread(initialize_services, fix_migration=False)

    # Verify settings are using our test database
    settings_service = await asyncio.to_thread(get_settings_service)
    assert settings_service.settings.database_url == test_db_url

    yield test_db_url

    # Restore original value if it existed
    if original_value is not None:
        monkeypatch.setenv("LANGFLOW_DATABASE_URL", original_value)
    else:
        monkeypatch.delenv("LANGFLOW_DATABASE_URL", raising=False)


@pytest.mark.benchmark
async def test_initialize_services(setup_database_url):
    """Benchmark the initialization of services."""
    settings_service = await asyncio.to_thread(get_settings_service)
    assert settings_service.settings.database_url == setup_database_url


@pytest.mark.benchmark
async def test_setup_llm_caching(setup_database_url):
    """Benchmark LLM caching setup."""
    from langflow.interface.utils import setup_llm_caching

    assert os.getenv("LANGFLOW_DATABASE_URL") == setup_database_url
    await asyncio.to_thread(setup_llm_caching)


@pytest.mark.benchmark
async def test_initialize_super_user():
    """Benchmark super user initialization."""
    from langflow.initial_setup.setup import initialize_super_user_if_needed

    await asyncio.to_thread(initialize_super_user_if_needed)


@pytest.mark.benchmark
async def test_get_and_cache_all_types_dict():
    """Benchmark get_and_cache_all_types_dict function."""
    from langflow.interface.types import get_and_cache_all_types_dict

    settings_service = await asyncio.to_thread(get_settings_service)
    result = await get_and_cache_all_types_dict(settings_service)
    assert result is not None


@pytest.mark.benchmark
async def test_create_starter_projects():
    """Benchmark creation of starter projects."""
    from langflow.initial_setup.setup import create_or_update_starter_projects
    from langflow.interface.types import get_and_cache_all_types_dict

    settings_service = await asyncio.to_thread(get_settings_service)
    types_dict = await get_and_cache_all_types_dict(settings_service)
    await asyncio.to_thread(create_or_update_starter_projects, types_dict)


@pytest.mark.benchmark
async def test_load_flows():
    """Benchmark loading flows from directory."""
    from langflow.initial_setup.setup import load_flows_from_directory

    await asyncio.to_thread(load_flows_from_directory)
