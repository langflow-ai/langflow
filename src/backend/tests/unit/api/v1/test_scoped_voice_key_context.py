"""Each flow invocation on a voice socket revalidates its database credential."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks, HTTPException
from langflow.api.v1 import chat
from langflow.services.auth.context import AuthCredentialContext, get_current_auth_context, set_current_auth_context
from langflow.services.database.models.api_key.model import ApiKey
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_settings_service, session_scope

from tests.unit.services.authorization._policy_double import install_policy_authz


@pytest.fixture
async def voice_key(flow, active_user, monkeypatch):
    policy = {"restrictions": [{"resource_type": "flow", "actions": ["execute"]}]}
    key = ApiKey(user_id=active_user.id, api_key=uuid4().hex, permissions=policy)
    async with session_scope() as session:
        session.add(key)
    previous = get_current_auth_context()
    set_current_auth_context(
        AuthCredentialContext(
            method="api_key",
            api_key_id=key.id,
            api_key_source="db",  # pragma: allowlist secret
            api_key_restricted=True,
            api_key_permissions=policy,
        )
    )
    started = AsyncMock(return_value=str(uuid4()))
    monkeypatch.setattr(chat, "start_flow_build", started)
    monkeypatch.setattr(chat, "_register_job_owner_or_cancel", AsyncMock())
    monkeypatch.setattr(chat, "get_flow_events_response", AsyncMock(return_value="stream"))
    with install_policy_authz(get_settings_service()) as plugin:

        async def enforce(*, act, context, **_kwargs):
            return any(act in grant["actions"] for grant in context["api_key_permissions"]["restrictions"])

        monkeypatch.setattr(plugin, "enforce", enforce)
        try:
            yield key, flow, active_user, started
        finally:
            set_current_auth_context(previous)


@pytest.mark.parametrize("change", ["narrowed", "deleted", "expired", "inactive", "owner_inactive"])
async def test_voice_rechecks_key_before_next_build(voice_key, change):
    key, flow, user, started = voice_key
    async with session_scope() as session:
        stored = await session.get(ApiKey, key.id)
        if change == "narrowed":
            stored.permissions = {"restrictions": [{"resource_type": "flow", "actions": ["read"]}]}
        elif change == "deleted":
            await session.delete(stored)
        elif change == "expired":
            stored.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        elif change == "inactive":
            stored.is_active = False
        else:
            owner = await session.get(User, user.id)
            owner.is_active = False
            session.add(owner)
    with pytest.raises(HTTPException):
        await chat.build_flow_and_stream(flow.id, None, BackgroundTasks(), user)
    started.assert_not_awaited()


async def test_voice_invocations_use_new_credential_contexts(voice_key):
    _key, flow, user, started = voice_key
    before = get_current_auth_context()
    assert await chat.build_flow_and_stream(flow.id, None, BackgroundTasks(), user) == "stream"
    first = get_current_auth_context()
    assert await chat.build_flow_and_stream(flow.id, None, BackgroundTasks(), user) == "stream"
    second = get_current_auth_context()
    assert before is not first
    assert first is not second
    assert before.api_key_id == first.api_key_id == second.api_key_id
    assert started.await_count == 2


async def test_voice_keeps_key_identity_after_policy_removal(voice_key):
    key, flow, user, started = voice_key
    async with session_scope() as session:
        stored = await session.get(ApiKey, key.id)
        stored.permissions = None
    assert await chat.build_flow_and_stream(flow.id, None, BackgroundTasks(), user) == "stream"
    assert get_current_auth_context().api_key_id == key.id
    assert not get_current_auth_context().api_key_restricted
    async with session_scope() as session:
        stored = await session.get(ApiKey, key.id)
        stored.is_active = False
    with pytest.raises(HTTPException):
        await chat.build_flow_and_stream(flow.id, None, BackgroundTasks(), user)
    assert started.await_count == 1


async def test_voice_deleted_key_denial_retains_audit_actor(voice_key, monkeypatch):
    from langflow.services.database.models.auth import AuthzAuditLog
    from sqlmodel import select

    key, flow, user, _started = voice_key
    settings = get_settings_service().auth_settings
    monkeypatch.setattr(settings, "AUTHZ_AUDIT_ENABLED", True)
    monkeypatch.setattr(settings, "AUTHZ_AUDIT_DURABLE", True)
    async with session_scope() as session:
        await session.delete(await session.get(ApiKey, key.id))
    with pytest.raises(HTTPException):
        await chat.build_flow_and_stream(flow.id, None, BackgroundTasks(), user)
    async with session_scope() as session:
        audit = (await session.exec(select(AuthzAuditLog).where(AuthzAuditLog.actor_id == key.id))).one()
    assert audit.actor_type == "api_key"
    assert audit.user_id == user.id
    assert audit.result == "deny"


async def test_voice_refresh_preserves_external_user_key_restriction(voice_key, monkeypatch):
    from langflow.services.database.models.auth import SSOUserProfile

    _key, flow, user, started = voice_key
    settings = get_settings_service().auth_settings
    monkeypatch.setattr(settings, "EXTERNAL_AUTH_ACCESS_CEILING_ENABLED", True)
    monkeypatch.setattr(settings, "EXTERNAL_AUTH_DISABLE_API_KEYS_FOR_EXTERNAL_USERS", True)
    async with session_scope() as session:
        session.add(SSOUserProfile(user_id=user.id, sso_provider="external", sso_user_id=uuid4().hex))
    with pytest.raises(HTTPException):
        await chat.build_flow_and_stream(flow.id, None, BackgroundTasks(), user)
    started.assert_not_awaited()


@pytest.mark.parametrize(
    "credential",
    [
        AuthCredentialContext(method="jwt"),
        AuthCredentialContext(method="api_key", api_key_source="env"),  # pragma: allowlist secret
    ],
)
async def test_non_database_credentials_keep_voice_behavior(voice_key, credential, monkeypatch):
    from unittest.mock import Mock

    from langflow.services.auth import api_key_context

    _key, flow, user, started = voice_key
    set_current_auth_context(credential)
    monkeypatch.setattr(api_key_context, "session_scope", Mock(side_effect=AssertionError("database refresh reached")))
    assert await chat.build_flow_and_stream(flow.id, None, BackgroundTasks(), user) == "stream"
    assert get_current_auth_context() is credential
    started.assert_awaited_once()
