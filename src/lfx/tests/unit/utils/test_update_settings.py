from unittest.mock import Mock

import pytest
from lfx.services.settings.base import Settings
from lfx.utils.util import update_settings

RUNTIME_SETTINGS = (
    "auto_saving_interval",
    "health_check_max_retries",
    "max_file_size_upload",
    "webhook_polling_interval",
)


@pytest.mark.asyncio
async def test_cache_only_call_keeps_runtime_settings(monkeypatch):
    """A cache-only call, as made by aload_flow_from_json, must not reset unrelated settings.

    Covers both sources of a value: one configured through the environment and one left at its
    ``Settings`` default.
    """
    monkeypatch.setenv("LANGFLOW_MAX_FILE_SIZE_UPLOAD", "250")
    monkeypatch.setenv("LANGFLOW_HEALTH_CHECK_MAX_RETRIES", "7")
    settings = Settings()
    before = {name: getattr(settings, name) for name in RUNTIME_SETTINGS}
    monkeypatch.setattr("lfx.utils.util.get_settings_service", lambda: Mock(settings=settings))

    await update_settings(cache=None)

    assert {name: getattr(settings, name) for name in RUNTIME_SETTINGS} == before
    assert settings.max_file_size_upload == 250


@pytest.mark.asyncio
async def test_explicit_runtime_setting_is_still_applied(monkeypatch):
    settings = Settings()
    monkeypatch.setattr("lfx.utils.util.get_settings_service", lambda: Mock(settings=settings))

    await update_settings(max_file_size_upload=42)

    assert settings.max_file_size_upload == 42
