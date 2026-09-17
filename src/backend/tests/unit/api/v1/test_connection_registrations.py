"""API coverage for the OAuth registration listing a connection picker reads."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import TYPE_CHECKING

import pytest
from lfx.services.deps import get_integration_policy_service, get_policy_bundle_service

if TYPE_CHECKING:
    from httpx import AsyncClient

pytestmark = pytest.mark.no_blockbuster

_GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar.events.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


def _google(**overrides) -> dict:
    return {
        "provider": "google",
        "owner": "customer",
        "context": "self_managed",
        "client_type": "confidential",
        "client_id": "google-client-id.apps.googleusercontent.com",
        "client_secret": "google-client-secret",  # pragma: allowlist secret - test fixture
        "redirect_uri": "https://langflow.example/api/v1/connections/oauth/google/callback",
        "scopes": _GOOGLE_SCOPES,
        **overrides,
    }


def _slack(**overrides) -> dict:
    return {
        "provider": "slack",
        "owner": "customer",
        "context": "self_managed",
        "client_type": "confidential",
        "client_id": "slack-client-id",
        "client_secret": "slack-client-secret",  # pragma: allowlist secret - test fixture
        "redirect_uri": "https://langflow.example/api/v1/connections/oauth/slack/callback",
        "scopes": ["chat:write"],
        **overrides,
    }


@pytest.fixture
def registrations(monkeypatch):
    def configure(configs: dict) -> None:
        monkeypatch.setenv("LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS", json.dumps(configs))

    configure({"google-work": _google(), "slack-bot": _slack()})
    return configure


@pytest.fixture
def integration_policy():
    """Publish an approved-provider ceiling for one test and restore it afterwards."""
    bundle = get_policy_bundle_service()
    original = bundle.snapshot

    def _approve(*providers: str) -> None:
        bundle.publish(
            replace(
                original,
                revision=original.revision + 1,
                initialized=True,
                approved_integration_provider_ids=frozenset(providers),
            )
        )
        get_integration_policy_service().invalidate()

    yield _approve

    bundle.publish(replace(original, revision=bundle.snapshot.revision + 1))
    get_integration_policy_service().invalidate()


async def test_omits_providers_outside_the_integration_policy(
    client: AsyncClient, logged_in_headers, registrations, integration_policy
):
    _ = registrations
    integration_policy("google")

    response = await client.get("api/v1/connections/oauth/registrations", headers=logged_in_headers)

    assert response.status_code == 200, response.text
    # Slack is configured but outside the ceiling, so consent could not start.
    assert [entry["id"] for entry in response.json()["registrations"]] == ["google-work"]


async def test_lists_configured_registrations(client: AsyncClient, logged_in_headers, registrations):
    _ = registrations
    response = await client.get("api/v1/connections/oauth/registrations", headers=logged_in_headers)

    assert response.status_code == 200, response.text
    listed = response.json()["registrations"]
    assert [entry["id"] for entry in listed] == ["google-work", "slack-bot"]
    assert listed[0] == {
        "id": "google-work",
        "provider": "google",
        "profile": "user",
        "context": "self_managed",
        "client_type": "confidential",
        "scopes": _GOOGLE_SCOPES,
        "allowed_tenants": [],
    }


async def test_never_returns_client_credentials(client: AsyncClient, logged_in_headers, registrations):
    _ = registrations
    response = await client.get("api/v1/connections/oauth/registrations", headers=logged_in_headers)

    body = response.text
    assert "client_secret" not in body
    assert "google-client-secret" not in body
    assert "google-client-id" not in body
    assert "redirect_uri" not in body


async def test_is_never_cached_by_a_shared_proxy(client: AsyncClient, logged_in_headers, registrations):
    _ = registrations
    response = await client.get("api/v1/connections/oauth/registrations", headers=logged_in_headers)

    # The payload depends on the caller's policy, so it must not be shared.
    assert response.headers.get("cache-control") == "no-store"


async def test_filters_by_provider(client: AsyncClient, logged_in_headers, registrations):
    _ = registrations
    response = await client.get("api/v1/connections/oauth/registrations?provider=slack", headers=logged_in_headers)

    assert response.status_code == 200, response.text
    assert [entry["id"] for entry in response.json()["registrations"]] == ["slack-bot"]


async def test_omits_registrations_this_deployment_would_refuse(client: AsyncClient, logged_in_headers, registrations):
    # A desktop registration is unavailable while the instance context is
    # self_managed: oauth/start raises, so the listing must not advertise it.
    registrations(
        {
            "google-work": _google(),
            "google-desktop": _google(
                context="desktop",
                client_type="public",
                client_secret=None,
                redirect_uri="http://localhost:7860/api/v1/connections/oauth/google/callback",
            ),
        }
    )
    response = await client.get("api/v1/connections/oauth/registrations", headers=logged_in_headers)

    assert [entry["id"] for entry in response.json()["registrations"]] == ["google-work"]


async def test_omits_invalid_registrations(client: AsyncClient, logged_in_headers, registrations):
    registrations({"google-work": _google(), "broken": {"provider": "google"}})
    response = await client.get("api/v1/connections/oauth/registrations", headers=logged_in_headers)

    assert response.status_code == 200, response.text
    assert [entry["id"] for entry in response.json()["registrations"]] == ["google-work"]


async def test_reports_no_registrations_when_none_are_configured(client: AsyncClient, logged_in_headers, registrations):
    registrations({})
    response = await client.get("api/v1/connections/oauth/registrations", headers=logged_in_headers)

    assert response.status_code == 200, response.text
    assert response.json() == {"registrations": []}


async def test_requires_authentication(client: AsyncClient, registrations):
    _ = registrations
    response = await client.get("api/v1/connections/oauth/registrations")

    assert response.status_code in {401, 403}


async def test_rejects_an_invalid_provider_filter(client: AsyncClient, logged_in_headers, registrations):
    _ = registrations
    response = await client.get("api/v1/connections/oauth/registrations?provider=Google", headers=logged_in_headers)

    assert response.status_code == 422
