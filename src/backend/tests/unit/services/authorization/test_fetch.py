"""Tests for share-aware fetch helpers (strict pass-through contract)."""

from __future__ import annotations

from typing import Any, ClassVar
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from langflow.services.authorization.fetch import authorized_or_owner_scoped, deny_to_404
from langflow.services.database.models.flow.model import Flow
from lfx.services.authorization.base import BaseAuthorizationService

# Reuse the live Flow model so the test exercises a real SQLAlchemy
# InstrumentedAttribute path. The session is fake — only the compiled SQL
# matters, not actual rows.
_DummyRow = Flow


class _StubService(BaseAuthorizationService):
    """Minimal subclass so tests can flip SUPPORTS_CROSS_USER_FETCH.

    Cross-user fetch in the helper requires *both* the plugin capability
    *and* ``is_enabled()`` to be true, so tests opt into both together via
    ``supports_cross_user`` to mirror an authorization plugin with
    ``AUTHZ_ENABLED=true``.
    """

    SUPPORTS_CROSS_USER_FETCH: ClassVar[bool] = False

    def __init__(self, *, supports_cross_user: bool = False) -> None:
        super().__init__()
        self._supports = supports_cross_user
        self.set_ready()

    async def supports_cross_user_fetch(self) -> bool:
        return self._supports

    async def is_enabled(self) -> bool:
        return self._supports

    async def enforce(self, **_: Any) -> bool:
        return True

    async def batch_enforce(self, *, requests, **_: Any) -> list[bool]:
        return [True] * len(requests)


class _FakeResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def first(self) -> Any:
        return self._value


class _FakeSession:
    """Captures the compiled SQL each call passes to ``exec``."""

    def __init__(self, *, returns: Any = "row") -> None:
        self.calls: list[str] = []
        self.returns = returns

    async def exec(self, stmt: Any) -> _FakeResult:
        # str(stmt) gives the compiled SQL — enough to assert which branch ran.
        self.calls.append(str(stmt))
        return _FakeResult(self.returns)


@pytest.mark.anyio
async def test_owner_scoped_when_service_does_not_support_cross_user_fetch():
    """OSS pass-through default keeps the owner predicate so visibility cannot widen."""
    session = _FakeSession(returns=object())
    service = _StubService(supports_cross_user=False)
    with patch(
        "langflow.services.authorization.fetch.get_authorization_service",
        return_value=service,
    ):
        await authorized_or_owner_scoped(
            session,
            _DummyRow,
            id_column=_DummyRow.id,
            resource_id=uuid4(),
            owner_column=_DummyRow.user_id,
            owner_id=uuid4(),
        )
    # The owner-scoped branch adds a ``user_id =`` predicate in WHERE.
    assert "user_id = :user_id" in session.calls[0]


@pytest.mark.anyio
async def test_id_only_when_service_supports_cross_user_fetch():
    """Authorization plugin loads by id alone; route guard then decides access."""
    session = _FakeSession(returns=object())
    service = _StubService(supports_cross_user=True)
    with patch(
        "langflow.services.authorization.fetch.get_authorization_service",
        return_value=service,
    ):
        await authorized_or_owner_scoped(
            session,
            _DummyRow,
            id_column=_DummyRow.id,
            resource_id=uuid4(),
            owner_column=_DummyRow.user_id,
            owner_id=uuid4(),
        )
    # No user_id = :user_id predicate in the share-aware path.
    assert "user_id = :user_id" not in session.calls[0]
    assert "WHERE flow.id" in session.calls[0]


def test_deny_to_404_only_rewrites_403():
    """The helper preserves UUID privacy by converting 403 → 404 only."""
    rewritten = deny_to_404(HTTPException(status_code=403, detail="nope"))
    assert rewritten.status_code == 404

    # A non-403 is surfaced unchanged — its detail is not relabeled as "not found".
    untouched = deny_to_404(HTTPException(status_code=500, detail="boom"), detail="Variable not found")
    assert untouched.status_code == 500
    assert untouched.detail == "boom"
