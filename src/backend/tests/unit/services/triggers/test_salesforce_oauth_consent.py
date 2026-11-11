"""Repeated Salesforce authorization keeps login and approval explicit."""

from dataclasses import replace
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from langflow.services.auth import utils as auth_utils
from langflow.services.connection.oauth import broker, providers
from langflow.services.connection.oauth.config import OAuthRegistration
from langflow.services.database.models.connection import Connection
from langflow.services.database.models.connection.oauth import ConnectionOAuth
from langflow.services.deps import session_scope
from langflow.services.triggers.providers import registry
from langflow.services.triggers.providers.salesforce import PROVIDER, oauth

from tests.unit.services.triggers.salesforce_testkit import ORG

pytestmark = pytest.mark.no_blockbuster


@pytest.mark.parametrize("context", ["hosted", "self_managed"])
async def test_repeated_add_and_reauthorize_request_fresh_login_and_consent(monkeypatch, trigger_owner, context):
    monkeypatch.setenv("LANGFLOW_SALESFORCE_ORIGIN", ORG)
    configured = replace(PROVIDER, oauth=replace(oauth.OAUTH, allowed_origins=(ORG,)))
    monkeypatch.setattr(registry, "all_providers", lambda: (configured,))
    registration = OAuthRegistration(
        provider="salesforce",
        context=context,
        client_id="operator-app",
        client_secret="synthetic-client-secret",  # noqa: S106  # pragma: allowlist secret
        redirect_uri="https://langflow.example/api/v1/connections/oauth/salesforce/callback",
        tenant=ORG,
        scopes=["api", "id", "refresh_token"],
    )
    monkeypatch.setattr(broker, "get_oauth_settings", lambda: SimpleNamespace(registration=lambda _id: registration))
    states, browsers, challenges = set(), set(), set()
    async with session_scope() as session:
        first = Connection(
            provider_key="salesforce",
            name="first",
            display_name="First",
            owner_id=trigger_owner,
            executing_identity={"identity": "user_delegated"},
        )
        second = Connection(
            provider_key="salesforce",
            name="second",
            display_name="Second",
            owner_id=trigger_owner,
            executing_identity={"identity": "user_delegated"},
        )
        session.add_all([first, second])
        await session.flush()
        for row in (first, second, first):
            url, state, browser = await broker.start(
                session,
                row=row,
                user_id=trigger_owner,
                registration_id="salesforce-work",
                scopes=registration.scopes,
            )
            assert url.startswith(ORG + "/services/oauth2/authorize?")
            params = parse_qs(urlsplit(url).query)
            assert params["prompt"] == ["login consent"]
            assert params["scope"] == ["api id refresh_token"]
            assert params["state"] == [state]
            assert params["code_challenge_method"] == ["S256"]
            binding = await session.get(ConnectionOAuth, row.id)
            verifier = auth_utils.decrypt_api_key(binding.encrypted_verifier)
            assert params["code_challenge"] == [providers.challenge(verifier)]
            states.add(state)
            browsers.add(browser)
            challenges.add(params["code_challenge"][0])
            row.status = "ready"
            session.add(row)
        assert len(states) == len(browsers) == len(challenges) == 3
