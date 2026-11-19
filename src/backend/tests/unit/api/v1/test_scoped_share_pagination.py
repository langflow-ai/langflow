"""Restricted share pagination bounds permission checks after filling the page."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from langflow.api.v1 import authz_shares
from langflow.services.auth.context import AuthCredentialContext, clear_current_auth_context, set_current_auth_context
from langflow.services.database.models.auth import AuthzShare, ShareScope


@pytest.mark.anyio
@pytest.mark.parametrize("is_superuser", [False, True])
async def test_restricted_share_page_stops_checks_after_enough_permitted_rows(monkeypatch, is_superuser):
    owner_id = uuid4()
    resource_id = uuid4()
    rows = [
        AuthzShare(resource_type="flow", resource_id=resource_id, scope=ShareScope.USER.value, target_id=owner_id)
        for _ in range(8)
    ]
    session = AsyncMock()
    session.exec.side_effect = [iter(rows), iter([])]
    monkeypatch.setattr(authz_shares, "_resolve_resource_owner", AsyncMock(return_value=owner_id))
    monkeypatch.setattr(authz_shares, "_serialize_shares", AsyncMock(side_effect=lambda _session, items: items))

    async def authorize(_user, _action, **target):
        if target["share_id"] == rows[1].id:
            raise HTTPException(status_code=403)

    permission = AsyncMock(side_effect=authorize)
    monkeypatch.setattr(authz_shares, "ensure_share_permission", permission)
    set_current_auth_context(AuthCredentialContext(method="api_key", api_key_id=uuid4(), api_key_restricted=True))
    try:
        result = await authz_shares.list_shares(
            current_user=SimpleNamespace(id=owner_id, is_superuser=is_superuser), session=session, offset=1, limit=2
        )
    finally:
        clear_current_auth_context()

    assert [row.id for row in result] == [rows[2].id, rows[3].id]
    assert permission.await_count == 4
