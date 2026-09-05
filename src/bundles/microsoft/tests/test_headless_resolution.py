"""Headless resolution through the environment wire format.

Only ``lfx run`` stamps a ``headless_operator`` principal today
(``lfx/run/_defaults.py``); ``lfx serve`` and full Langflow stamp nothing until
INT-6 (LE-2464) lands, and the portable deny floor refuses every other kind for
an env-owned credential. These tests pin both halves of that contract.
"""

from __future__ import annotations

import json

import httpx
import pytest
from lfx.integrations.errors import ConnectionNotAuthorizedError, ConnectionUnresolvedError, ScopeMissingError
from lfx.integrations.models import ConnectionRef
from lfx.services.authorization.base import ExecutionPrincipal
from lfx_microsoft import OutlookSearchComponent
from microsoft_testkit import TransportRecorder, build_component, graph_fixture, json_response

ENV_KEY = ConnectionRef(provider="microsoft", name="work").env_key()
HEADLESS = ExecutionPrincipal(kind="headless_operator")


def _wire(scopes: list[str]) -> str:
    return json.dumps({"access_token": "headless-token", "scopes": scopes})


def test_env_key_is_the_documented_headless_variable() -> None:
    assert ENV_KEY == "LF_CONNECTION__MICROSOFT__WORK"


@pytest.mark.usefixtures("unset_resolver")
async def test_headless_operator_resolves_the_env_credential(monkeypatch) -> None:
    monkeypatch.setenv(ENV_KEY, _wire(["Mail.Read"]))
    recorder = TransportRecorder(lambda _request: json_response(graph_fixture("messages_page1")))
    component = build_component(
        OutlookSearchComponent,
        recorder,
        principal=HEADLESS,
        connection="microsoft/work",
        top=2,
    )

    rows = await component.search_messages()

    assert len(rows) == 2
    assert recorder.last.headers["authorization"] == "Bearer headless-token"


@pytest.mark.usefixtures("unset_resolver")
async def test_short_form_scopes_satisfy_the_resolver(monkeypatch) -> None:
    """Entra echoes the short form; the wire value must use it too."""
    monkeypatch.setenv(ENV_KEY, _wire(["Mail.Read"]))
    recorder = TransportRecorder(lambda _request: json_response({"value": []}))
    component = build_component(
        OutlookSearchComponent,
        recorder,
        principal=HEADLESS,
        connection="microsoft/work",
    )

    assert await component.search_messages() == []


@pytest.mark.usefixtures("unset_resolver")
async def test_a_missing_scope_fails_before_any_graph_request(monkeypatch) -> None:
    monkeypatch.setenv(ENV_KEY, _wire(["Calendars.Read"]))
    recorder = TransportRecorder(lambda _request: httpx.Response(200, json={"value": []}))
    component = build_component(
        OutlookSearchComponent,
        recorder,
        principal=HEADLESS,
        connection="microsoft/work",
    )

    with pytest.raises(ScopeMissingError) as excinfo:
        await component.search_messages()
    assert excinfo.value.missing == frozenset({"Mail.Read"})
    assert recorder.requests == []


@pytest.mark.usefixtures("unset_resolver")
async def test_an_unset_variable_reports_the_env_key(monkeypatch) -> None:
    monkeypatch.delenv(ENV_KEY, raising=False)
    recorder = TransportRecorder(lambda _request: httpx.Response(200, json={"value": []}))
    component = build_component(
        OutlookSearchComponent,
        recorder,
        principal=HEADLESS,
        connection="microsoft/work",
    )

    with pytest.raises(ConnectionUnresolvedError) as excinfo:
        await component.search_messages()
    assert excinfo.value.env_key == ENV_KEY
    assert recorder.requests == []


@pytest.mark.usefixtures("unset_resolver")
async def test_an_unstamped_principal_is_denied_by_the_deny_floor(monkeypatch) -> None:
    """This is why canvas execution of these components needs INT-6."""
    monkeypatch.setenv(ENV_KEY, _wire(["Mail.Read"]))
    recorder = TransportRecorder(lambda _request: httpx.Response(200, json={"value": []}))
    component = build_component(
        OutlookSearchComponent,
        recorder,
        principal=ExecutionPrincipal.unknown(),
        connection="microsoft/work",
    )

    with pytest.raises(ConnectionNotAuthorizedError):
        await component.search_messages()
    assert recorder.requests == []


@pytest.mark.usefixtures("unset_resolver")
async def test_the_component_rejects_a_handle_for_another_provider() -> None:
    recorder = TransportRecorder(lambda _request: httpx.Response(200, json={"value": []}))
    component = build_component(
        OutlookSearchComponent,
        recorder,
        principal=HEADLESS,
        connection="google/work",
    )

    with pytest.raises(ValueError, match="does not match declared provider"):
        await component.search_messages()
