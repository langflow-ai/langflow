"""The version telemetry event reports which database engine an install runs on."""

from __future__ import annotations

import pytest
from langflow.services.deps import get_settings_service
from langflow.services.telemetry.schema import VersionPayload
from langflow.services.telemetry.service import TelemetryService, database_dialect


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("sqlite:///./langflow.db", "sqlite"),
        ("sqlite+aiosqlite:////tmp/langflow.db", "sqlite"),
        ("postgresql://user:secret@db.internal:5432/langflow", "postgresql"),  # pragma: allowlist secret
        ("postgresql+psycopg://user:secret@db.internal:5432/langflow", "postgresql"),  # pragma: allowlist secret
        ("not a url", "unknown"),
        ("", "unknown"),
        (None, "unknown"),
    ],
)
def test_database_dialect_reports_only_the_engine(url, expected):
    # Only the engine name leaves the process. The URL carries a host and often
    # credentials, so none of it may reach the telemetry payload.
    assert database_dialect(url) == expected


def test_version_payload_serializes_the_dialect():
    payload = VersionPayload(
        package="langflow",
        version="1.13.0",
        platform="Linux",
        python="3.12",
        arch="64bit",
        auto_login=False,
        cache_type="async",
        backend_only=False,
        database_dialect="postgresql",
    )

    assert payload.model_dump(by_alias=True)["databaseDialect"] == "postgresql"


def test_version_payload_dialect_defaults_to_unknown():
    payload = VersionPayload(
        package="langflow",
        version="1.13.0",
        platform="Linux",
        python="3.12",
        arch="64bit",
        auto_login=False,
        cache_type="async",
        backend_only=False,
    )

    assert payload.database_dialect == "unknown"


async def test_version_event_carries_the_configured_dialect():
    settings_service = get_settings_service()
    service = TelemetryService(settings_service)
    service.do_not_track = False

    await service.log_package_version()

    _, payload, _ = service.telemetry_queue.get_nowait()
    assert payload.database_dialect == database_dialect(settings_service.settings.database_url)
    assert payload.database_dialect != "unknown"
