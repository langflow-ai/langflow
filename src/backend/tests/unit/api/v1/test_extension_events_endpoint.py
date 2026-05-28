"""Tests for the GET /extensions/events controller.

The keyspace is server-derived from the authenticated user; a client-supplied
``keyspace`` query parameter is rejected with 422 so the contract is explicit.
Previously the parameter was silently dropped, which masked client bugs that
assumed it had effect.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, status
from langflow.api.v1.extensions import get_extension_events


def _user(user_id: str = "alice-id") -> SimpleNamespace:
    return SimpleNamespace(id=user_id)


async def test_keyspace_query_param_is_rejected_with_typed_422(monkeypatch: pytest.MonkeyPatch) -> None:
    """Passing ``?keyspace=...`` must surface a typed 422 envelope.

    The body shape must match every other typed-error response in the
    extensions router so clients render the same fix-hint envelope.
    """
    # The service must not be touched on the rejection path.
    sentinel_svc = MagicMock()
    monkeypatch.setattr(
        "langflow.api.v1.extensions.get_extension_events_service",
        lambda: sentinel_svc,
    )

    with pytest.raises(HTTPException) as exc:
        await get_extension_events(
            current_user=_user(),
            since=0.0,
            keyspace="user:bob-id",
        )

    assert exc.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    detail = exc.value.detail
    assert isinstance(detail, dict)
    assert detail["code"] == "extension-events-keyspace-forbidden"
    assert detail["location"] == "query.keyspace"
    assert detail["content"] == "user:bob-id"
    assert detail["hint"]
    assert detail["ref_url"].endswith("#extension-events-keyspace-forbidden")
    sentinel_svc.since.assert_not_called()


async def test_empty_string_keyspace_is_also_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """``?keyspace=`` (empty string) still indicates client intent and is rejected.

    Only the unset/absent case (None) is permitted -- otherwise a buggy
    client could pass an empty value and silently get the user-scoped
    response, defeating the explicit-contract goal of this 422.
    """
    monkeypatch.setattr(
        "langflow.api.v1.extensions.get_extension_events_service",
        lambda: MagicMock(),
    )

    with pytest.raises(HTTPException) as exc:
        await get_extension_events(current_user=_user(), since=0.0, keyspace="")

    assert exc.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert exc.value.detail["code"] == "extension-events-keyspace-forbidden"


async def test_request_without_keyspace_returns_events(monkeypatch: pytest.MonkeyPatch) -> None:
    """The normal path (no keyspace param) is unaffected.

    Regression guard against accidentally tightening the contract for
    callers that already follow it (the frontend hook and any future CLI
    pollers send only ``since``).
    """
    svc = MagicMock()
    svc.since.return_value = ([], True)
    monkeypatch.setattr(
        "langflow.api.v1.extensions.get_extension_events_service",
        lambda: svc,
    )

    response = await get_extension_events(current_user=_user("alice-id"), since=1.5)

    assert response.events == []
    assert response.settled is True
    # The server-derived keyspace must still be ``user:{id}``; the
    # endpoint must not have started accepting client-supplied values.
    svc.since.assert_called_once_with(1.5, "user:alice-id")


async def test_service_unavailable_short_circuits_without_touching_keyspace_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the service is None the endpoint returns an empty settled response.

    The keyspace rejection must run BEFORE this short-circuit so a client
    that passes ``?keyspace=...`` still sees a typed 422 rather than an
    empty 200 (which would be a silent success for an explicitly invalid
    request).
    """
    monkeypatch.setattr(
        "langflow.api.v1.extensions.get_extension_events_service",
        lambda: None,
    )

    # Without keyspace: empty settled response.
    response = await get_extension_events(current_user=_user(), since=0.0)
    assert response.events == []
    assert response.settled is True

    # With keyspace: still 422, even though the service is unavailable.
    with pytest.raises(HTTPException) as exc:
        await get_extension_events(current_user=_user(), since=0.0, keyspace="global")
    assert exc.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert exc.value.detail["code"] == "extension-events-keyspace-forbidden"
