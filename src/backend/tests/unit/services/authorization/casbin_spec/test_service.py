"""Observable admission behavior of the selected service over real persisted rules."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from langflow.services.authorization.casbin import store
from langflow.services.authorization.casbin.service import CasbinAuthorizationService
from langflow.services.database.models.auth import AuthzShare
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.user.model import User
from lfx.services.authorization.context import authorization_session
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.mark.asyncio
@pytest.mark.parametrize("ambient", [False, True])
async def test_disabled_access_sources_need_no_database_or_projection(ambient):
    """Compatibility mode explains no policy, even with an unbound ambient session."""
    service = CasbinAuthorizationService(SimpleNamespace(auth_settings=SimpleNamespace(AUTHZ_ENABLED=False)))
    request = {"user_id": uuid4(), "resource_type": "flow", "resource_id": uuid4()}
    assert not service.ready
    if ambient:
        async with AsyncSession() as session:
            with authorization_session(session):
                assert await service.get_access_sources(**request) == ()
    else:
        assert await service.get_access_sources(**request) == ()


@pytest.mark.asyncio
async def test_disabled_access_sources_do_not_enter_admission(monkeypatch):
    """Disabled provenance must not touch admission or its projection state."""
    service = CasbinAuthorizationService(SimpleNamespace(auth_settings=SimpleNamespace(AUTHZ_ENABLED=False)))

    def unexpected_admission():
        pytest.fail("Disabled access explanation opened authorization admission")

    monkeypatch.setattr(service, "admission_context", unexpected_admission)
    assert await service.get_access_sources(user_id=uuid4(), resource_type="flow", resource_id=uuid4()) == ()


@pytest.mark.asyncio
async def test_enabled_access_sources_require_initialized_projection():
    """The compatibility guard must not weaken enabled readiness checks."""
    service = CasbinAuthorizationService(SimpleNamespace(auth_settings=SimpleNamespace(AUTHZ_ENABLED=True)))
    with pytest.raises(RuntimeError, match="Authorization projection has not completed initialization"):
        await service.get_access_sources(user_id=uuid4(), resource_type="flow", resource_id=uuid4())


@pytest.mark.asyncio
async def test_staged_grant_and_revocation_use_the_caller_transaction(policy_db):
    """A caller sees its staged policy; the next transaction sees committed revocation."""
    service = CasbinAuthorizationService(
        SimpleNamespace(
            auth_settings=SimpleNamespace(
                AUTHZ_ENABLED=True,
                AUTHZ_SUPERUSER_BYPASS=True,
            )
        )
    )
    owner = User(username=str(uuid4()), password=str(uuid4()), is_active=True)
    recipient = User(username=str(uuid4()), password=str(uuid4()), is_active=True)
    project = Folder(name=str(uuid4()), user_id=owner.id)
    flow = Flow(name=str(uuid4()), user_id=owner.id, folder_id=project.id)
    async with AsyncSession(policy_db, expire_on_commit=False) as session:
        await store.acquire_writer_lock(session)
        session.add_all([owner, recipient, project, flow])
        await session.flush()
        await store.reconcile_policy(session)
        share = AuthzShare(
            resource_type="flow",
            resource_id=flow.id,
            scope="user",
            target_id=recipient.id,
            permission_level="write",
            created_by=owner.id,
        )
        with authorization_session(session):
            assert not await service.enforce(user_id=recipient.id, domain="*", obj=f"flow:{flow.id}", act="write")
            session.add(share)
            await store.reconcile_policy(session)
            assert await service.batch_enforce(
                user_id=recipient.id,
                domain="*",
                requests=[
                    (f"flow:{flow.id}", "read"),
                    (f"flow:{flow.id}", "write"),
                    (f"flow:{flow.id}", "delete"),
                    (f"project:{project.id}", "read"),
                ],
            ) == [True, True, False, False]
        await session.commit()
        await store.acquire_writer_lock(session)
        await session.delete(share)
        await store.reconcile_policy(session)
        await session.commit()
        await store.acquire_writer_lock(session)
        with authorization_session(session):
            assert not await service.enforce(user_id=recipient.id, domain="*", obj=f"flow:{flow.id}", act="read")
            assert await service.enforce(user_id=owner.id, domain="*", obj=f"flow:{flow.id}", act="read")
