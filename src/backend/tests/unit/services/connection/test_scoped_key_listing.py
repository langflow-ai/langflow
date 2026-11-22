"""Connection lists must apply a key ceiling even for platform superusers."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from langflow.services.auth.context import AuthCredentialContext, clear_current_auth_context, set_current_auth_context
from langflow.services.authorization import guards, listing
from langflow.services.connection import service as connection_service
from langflow.services.database.models.connection import Connection, ConnectionOwnershipMode
from langflow.services.database.models.user.model import User
from lfx.services.authorization import ResourceVisibilityScope
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession


async def test_superuser_key_list_is_restricted_before_rows_are_returned(monkeypatch):
    user = User(id=uuid4(), username="key-owner", password=uuid4().hex, is_superuser=True, is_active=True)
    allowed = Connection(name="allowed", display_name="Allowed", provider_key="google_workspace", owner_id=user.id)
    denied = Connection(name="denied", display_name="Denied", provider_key="google_workspace", owner_id=user.id)

    class Authorization:
        async def is_enabled(self):
            return True

        async def supports_cross_user_fetch(self):
            return True

        async def supports_api_key_scopes(self):
            return True

        async def get_resource_visibility(self, **_kwargs):
            return ResourceVisibilityScope(
                all_resources=True, intersections=(ResourceVisibilityScope(resource_ids=(allowed.id,)),)
            )

        async def batch_enforce(self, *, requests, **_kwargs):
            return [obj == f"connection:{allowed.id}" for obj, _ in requests]

    authorization = Authorization()
    for module in (connection_service, guards, listing):
        monkeypatch.setattr(module, "get_authorization_service", lambda: authorization)
    for module in (guards, listing):
        monkeypatch.setattr(
            module, "get_settings_service", lambda: SimpleNamespace(auth_settings=SimpleNamespace(AUTHZ_ENABLED=True))
        )
    engine = create_async_engine("sqlite+aiosqlite://")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(SQLModel.metadata.create_all)
        async with AsyncSession(engine, expire_on_commit=False) as session:
            session.add_all([user, allowed, denied])
            await session.commit()
            set_current_auth_context(
                AuthCredentialContext(
                    method="api_key", api_key_id=uuid4(), api_key_source="db", api_key_restricted=True
                )
            )
            rows = await connection_service.DatabaseConnectionResolverService()._list_visible_rows(
                session, user=user, provider_ids=None
            )
            assert [row.id for row in rows] == [allowed.id]
    finally:
        clear_current_auth_context()
        await engine.dispose()


@pytest.mark.parametrize("is_superuser", [False, True])
@pytest.mark.parametrize(("authz_enabled", "scope_support"), [(False, True), (True, False), (True, True)])
async def test_restricted_key_list_without_cross_user_fetch_applies_ceiling(
    monkeypatch, is_superuser, authz_enabled, scope_support
):
    user = User(id=uuid4(), username="key-owner", password=uuid4().hex, is_superuser=is_superuser, is_active=True)
    allowed = Connection(name="allowed", display_name="Allowed", provider_key="google_workspace", owner_id=user.id)
    denied = Connection(name="denied", display_name="Denied", provider_key="google_workspace", owner_id=user.id)
    instance = Connection(
        name="instance",
        display_name="Instance",
        provider_key="google_workspace",
        ownership_mode=ConnectionOwnershipMode.INSTANCE.value,
    )

    class Authorization:
        async def is_enabled(self):
            return authz_enabled

        async def supports_cross_user_fetch(self):
            return False

        async def supports_api_key_scopes(self):
            return scope_support

        async def batch_enforce(self, *, requests, **_kwargs):
            return [obj == f"connection:{allowed.id}" for obj, _ in requests]

    authorization = Authorization()
    for module in (connection_service, guards, listing):
        monkeypatch.setattr(module, "get_authorization_service", lambda: authorization)
    for module in (guards, listing):
        monkeypatch.setattr(
            module,
            "get_settings_service",
            lambda: SimpleNamespace(auth_settings=SimpleNamespace(AUTHZ_ENABLED=authz_enabled)),
        )
    engine = create_async_engine("sqlite+aiosqlite://")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(SQLModel.metadata.create_all)
        async with AsyncSession(engine, expire_on_commit=False) as session:
            session.add_all([user, allowed, denied, instance])
            await session.commit()
            set_current_auth_context(
                AuthCredentialContext(
                    method="api_key", api_key_id=uuid4(), api_key_source="db", api_key_restricted=True
                )
            )
            resolver = connection_service.DatabaseConnectionResolverService()
            if not authz_enabled or not scope_support:
                with pytest.raises(HTTPException) as exc:
                    await resolver._list_visible_rows(session, user=user, provider_ids=None)
                assert exc.value.status_code == 403
            else:
                rows = await resolver._list_visible_rows(session, user=user, provider_ids=None)
                assert [row.id for row in rows] == [allowed.id]
    finally:
        clear_current_auth_context()
        await engine.dispose()
