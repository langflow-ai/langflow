"""Offline guard for the opt-in live suite's credential wiring.

CI deselects the live suite, so nothing else notices when the payload it builds stops
satisfying the connection resolver. This drives the suite's own token exchange against
a canned Google response and resolves every action through ``EnvConnectionResolver``,
the resolver the live suite uses, without contacting Google.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import test_workspace_actions_live as live
from lfx.services.authorization.base import ExecutionPrincipal
from lfx.services.connection.env_resolver import EnvConnectionResolver
from lfx_google.components.google import (
    GmailSendComponent,
    GoogleCalendarCreateComponent,
    GoogleCalendarListComponent,
    GoogleDriveFetchComponent,
    GoogleDriveListComponent,
)

ACTIONS = [
    GmailSendComponent,
    GoogleDriveListComponent,
    GoogleDriveFetchComponent,
    GoogleCalendarListComponent,
    GoogleCalendarCreateComponent,
]
FAKE_EXCHANGE_TOKEN = "fake-live-suite-access-token"  # noqa: S105  # pragma: allowlist secret


@pytest.fixture
def minted_payload(monkeypatch: pytest.MonkeyPatch) -> dict:
    monkeypatch.setenv("GOOGLE_LIVE_CLIENT_ID", "client-id")
    monkeypatch.setenv("GOOGLE_LIVE_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("GOOGLE_LIVE_REFRESH_TOKEN", "refresh-token")
    # Google's token endpoint reports the grant as one space-delimited ``scope`` string.
    exchange = {
        "access_token": FAKE_EXCHANGE_TOKEN,
        "expires_in": 3599,
        "scope": " ".join(sorted(live._manifest_scopes())),
        "token_type": "Bearer",
    }
    response = SimpleNamespace(status_code=live.HTTP_OK, json=lambda: exchange)
    with patch("httpx.post", return_value=response):
        payload = live._mint_access_token()
    assert payload is not None
    return payload


def test_the_manifest_grant_is_the_four_wave_one_scopes() -> None:
    assert live._manifest_scopes() == {
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/calendar.events.readonly",
        "https://www.googleapis.com/auth/calendar.events",
    }


@pytest.mark.parametrize("component_class", ACTIONS, ids=lambda cls: cls.__name__)
async def test_the_minted_credential_clears_the_scope_floor_for_every_action(
    minted_payload: dict, monkeypatch: pytest.MonkeyPatch, component_class
) -> None:
    monkeypatch.setenv(live.LIVE_ENV_KEY, json.dumps(minted_payload))
    resolver = EnvConnectionResolver()
    monkeypatch.setattr("lfx.services.deps.get_connection_resolver", lambda: resolver)
    component = component_class()
    component.connection = live.CONNECTION_HANDLE
    component.set_vertex(
        SimpleNamespace(
            graph=SimpleNamespace(
                execution_principal=ExecutionPrincipal(kind="headless_operator"), flow_id=None, run_id=None
            )
        )
    )

    credential = await component.resolve_connection("connection").get_credential()

    assert credential.scopes_verified is True


def test_the_least_privilege_check_rejects_a_broader_grant(minted_payload: dict, monkeypatch) -> None:
    monkeypatch.setenv(live.LIVE_ENV_KEY, json.dumps(minted_payload))
    live.test_live_grant_is_least_privilege()

    broader = dict(minted_payload, scopes=[*minted_payload["scopes"], "https://www.googleapis.com/auth/drive"])
    monkeypatch.setenv(live.LIVE_ENV_KEY, json.dumps(broader))
    with pytest.raises(AssertionError):
        live.test_live_grant_is_least_privilege()
