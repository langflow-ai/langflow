"""/agentic/check-config must report the feature gate, not just provider config.

The assistant has two independent failure modes: no provider connected, and the
``agentic_experience`` gate turned off. ``check-config`` is deliberately ungated (so a
non-agentic deployment can still query provider configuration), which means it is the only
probe a client can use to tell those apart -- every /assist route 404s when the gate is off.
Without ``enabled`` in the payload, the UI reads ``configured: true`` and offers an assistant
that answers 404.
"""

import pytest
from httpx import AsyncClient
from langflow.services.deps import get_settings_service


@pytest.fixture
def assistant_settings():
    return get_settings_service().settings


async def test_should_report_enabled_false_when_the_gate_is_off(
    client: AsyncClient, logged_in_headers, monkeypatch, assistant_settings
):
    monkeypatch.setattr(assistant_settings, "agentic_experience", False)

    response = await client.get("api/v1/agentic/check-config", headers=logged_in_headers)

    assert response.status_code == 200
    assert response.json()["enabled"] is False


async def test_should_report_enabled_true_when_the_gate_is_on(
    client: AsyncClient, logged_in_headers, monkeypatch, assistant_settings
):
    monkeypatch.setattr(assistant_settings, "agentic_experience", True)

    response = await client.get("api/v1/agentic/check-config", headers=logged_in_headers)

    assert response.status_code == 200
    assert response.json()["enabled"] is True


async def test_should_stay_reachable_when_the_gate_is_off(
    client: AsyncClient, logged_in_headers, monkeypatch, assistant_settings
):
    """The probe itself must never 404, or the UI loses the only way to explain the gate."""
    monkeypatch.setattr(assistant_settings, "agentic_experience", False)

    response = await client.get("api/v1/agentic/check-config", headers=logged_in_headers)

    assert response.status_code == 200
    assert "configured" in response.json()


async def test_should_keep_gate_and_provider_config_independent(
    client: AsyncClient, logged_in_headers, monkeypatch, assistant_settings
):
    """`enabled` reports the gate only -- it must not be conflated with provider config."""
    monkeypatch.setattr(assistant_settings, "agentic_experience", False)

    body = (await client.get("api/v1/agentic/check-config", headers=logged_in_headers)).json()

    assert body["enabled"] is False
    assert "configured" in body
    assert isinstance(body["configured"], bool)
