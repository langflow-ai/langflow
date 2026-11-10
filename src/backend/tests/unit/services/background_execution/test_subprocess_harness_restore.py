"""Worker-subprocess teardown restores the validated database setting and environment."""

from __future__ import annotations

import os

import pytest
from langflow.services.deps import get_settings_service
from lfx.services.manager import get_service_manager
from lfx.services.schema import ServiceType

from ._subprocess_harness import WorkerHarness

pytestmark = pytest.mark.usefixtures("client")


@pytest.mark.parametrize("prior_env_set", [False, True])
async def test_teardown_restores_database_settings_after_the_environment(monkeypatch, prior_env_set):
    settings = get_settings_service().settings
    original_url = settings.database_url
    manager = get_service_manager()
    database_service = manager.services.get(ServiceType.DATABASE_SERVICE)
    try:
        with monkeypatch.context() as patch:
            if prior_env_set:
                patch.setenv("LANGFLOW_DATABASE_URL", original_url)
            else:
                patch.delenv("LANGFLOW_DATABASE_URL", raising=False)
            settings.database_url = original_url
            prior_url = settings.database_url
            prior_env = os.environ.get("LANGFLOW_DATABASE_URL")
            patch.setenv("LANGFLOW_DATABASE_URL", "postgresql+psycopg://localhost/harness_restore")
            settings.database_url = os.environ["LANGFLOW_DATABASE_URL"]
            harness = WorkerHarness(
                db_url=settings.database_url,
                job_service=None,
                _prior_db_service=database_service,
                _prior_settings_url=prior_url,
                _prior_db_env_set=prior_env_set,
                _prior_db_env=prior_env,
            )

            await harness.teardown()

            assert os.environ.get("LANGFLOW_DATABASE_URL") == prior_env
            assert settings.database_url == prior_url
            assert manager.services.get(ServiceType.DATABASE_SERVICE) is database_service
    finally:
        settings.database_url = original_url
