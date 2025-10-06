import os

import pytest
from langflow.services.deps import get_settings_service


@pytest.fixture(autouse=True)
def setup_database_url(tmp_path, monkeypatch):
    """Setup a temporary database URL for testing."""
    settings_service = get_settings_service()
    db_path = tmp_path / "test_performance.db"
    original_value = os.getenv("LANGFLOW_DATABASE_URL")
    monkeypatch.delenv("LANGFLOW_DATABASE_URL", raising=False)
    test_db_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("LANGFLOW_DATABASE_URL", test_db_url)
    settings_service.set("database_url", test_db_url)
    yield
    # Restore original value if it existed
    if original_value is not None:
        monkeypatch.setenv("LANGFLOW_DATABASE_URL", original_value)
        settings_service.set("database_url", original_value)
    else:
        monkeypatch.delenv("LANGFLOW_DATABASE_URL", raising=False)


async def test_initialize_services():
    """Benchmark the initialization of services."""
    from langflow.services.utils import initialize_services

    await initialize_services(fix_migration=False)
    settings_service = get_settings_service()
    assert "test_performance.db" in settings_service.settings.database_url


def test_setup_llm_caching():
    """Benchmark LLM caching setup."""
    from langflow.interface.utils import setup_llm_caching

    setup_llm_caching()
    settings_service = get_settings_service()
    assert "test_performance.db" in settings_service.settings.database_url


async def test_initialize_super_user():
    """Benchmark super user initialization."""
    from langflow.initial_setup.setup import initialize_auto_login_default_superuser
    from langflow.services.utils import initialize_services

    await initialize_services(fix_migration=False)
    await initialize_auto_login_default_superuser()
    settings_service = get_settings_service()
    assert "test_performance.db" in settings_service.settings.database_url


async def test_get_and_cache_all_types_dict():
    """Benchmark get_and_cache_all_types_dict function."""
    from langflow.interface.components import get_and_cache_all_types_dict

    settings_service = get_settings_service()
    result = await get_and_cache_all_types_dict(settings_service)
    assert "vectorstores" in result
    assert "test_performance.db" in settings_service.settings.database_url


async def test_create_starter_projects():
    """Benchmark creation of starter projects."""
    from langflow.initial_setup.setup import create_or_update_starter_projects
    from langflow.interface.components import get_and_cache_all_types_dict
    from langflow.services.utils import initialize_services

    await initialize_services(fix_migration=False)
    settings_service = get_settings_service()
    types_dict = await get_and_cache_all_types_dict(settings_service)
    await create_or_update_starter_projects(types_dict)
    assert "test_performance.db" in settings_service.settings.database_url


async def test_load_flows():
    """Benchmark loading flows from directory."""
    from langflow.initial_setup.setup import load_flows_from_directory

    await load_flows_from_directory()
    settings_service = get_settings_service()
    assert "test_performance.db" in settings_service.settings.database_url


def test_env_var_loading(tmp_path, monkeypatch):
    """Test that environment variables from .env are loaded before settings initialization."""
    # Create a temporary .env file
    env_file = tmp_path / ".env"
    env_var_name = "LANGFLOW_TEST_ENV_VAR"
    env_var_value = "test_value_123"
    env_file.write_text(f"{env_var_name}={env_var_value}\n")

    # Ensure the variable is not set before
    monkeypatch.delenv(env_var_name, raising=False)

    # Patch find_dotenv to return our temp .env file
    monkeypatch.setattr("langflow.services.settings.factory.find_dotenv", lambda: str(env_file))

    # Patch load_dotenv to actually load our temp .env file
    from dotenv import load_dotenv

    monkeypatch.setattr("langflow.services.settings.factory.load_dotenv", load_dotenv)

    # Trigger settings initialization (should load env file)
    from langflow.services.settings.factory import SettingsServiceFactory

    factory = SettingsServiceFactory()
    factory._check_env_loaded()

    # Assert env var is now in os.environ
    assert os.getenv(env_var_name) == env_var_value

    # Optionally, check if settings service can access it (if relevant)
    settings_service = get_settings_service()
    # If your settings service exposes env vars, check here
    # assert settings_service.settings.test_env_var == env_var_value  # Uncomment if applicable
