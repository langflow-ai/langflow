"""update_settings must change only the settings a caller passes.

aload_flow_from_json calls update_settings(cache=...) on every flow load; hardcoded
defaults for four parameters used to overwrite the configured values each time
(max_file_size_upload -> 100, webhook_polling_interval -> 5000).
"""

import pytest
from lfx.load import aload_flow_from_json
from lfx.services.deps import get_settings_service
from lfx.utils.util import update_settings

CONFIGURED = {
    "max_file_size_upload": 500,
    "webhook_polling_interval": 0,
    "health_check_max_retries": 9,
    "auto_saving_interval": 3000,
}


@pytest.fixture
def configured_settings():
    settings = get_settings_service().settings
    original = {name: getattr(settings, name) for name in CONFIGURED}
    settings.update_settings(**CONFIGURED)
    yield settings
    settings.update_settings(**original)


def _current(settings) -> dict[str, int]:
    return {name: getattr(settings, name) for name in CONFIGURED}


@pytest.mark.asyncio
async def test_should_keep_configured_settings_when_no_value_is_passed(configured_settings):
    await update_settings()

    assert _current(configured_settings) == CONFIGURED


@pytest.mark.asyncio
async def test_should_keep_configured_settings_when_a_flow_is_loaded(configured_settings):
    await aload_flow_from_json({"data": {"nodes": [], "edges": []}}, disable_logs=True)

    assert _current(configured_settings) == CONFIGURED


@pytest.mark.asyncio
async def test_should_apply_an_explicitly_passed_value(configured_settings):
    await update_settings(max_file_size_upload=200, webhook_polling_interval=2500)

    assert configured_settings.max_file_size_upload == 200
    assert configured_settings.webhook_polling_interval == 2500
    assert configured_settings.health_check_max_retries == CONFIGURED["health_check_max_retries"]
