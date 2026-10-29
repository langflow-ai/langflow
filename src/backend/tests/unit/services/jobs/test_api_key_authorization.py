"""Queued jobs retain credential provenance and recheck current key limits."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langflow.services.auth.context import AuthCredentialContext, clear_current_auth_context, set_current_auth_context
from langflow.services.database.models.api_key.model import ApiKey
from langflow.services.database.models.auth import SSOUserProfile
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.jobs.model import Job, JobStatus, JobType
from langflow.services.database.models.knowledge_base.model import KnowledgeBaseRecord
from langflow.services.database.models.memory_base.model import MemoryBase
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_job_service, get_settings_service, session_scope

pytestmark = pytest.mark.usefixtures("client")
_PROVENANCE = "api_key_authorization"


def _policy(actions=None):
    return {"restrictions": [{"resource_type": "flow", "actions": actions or ["read", "execute"]}]}


@pytest.fixture(autouse=True)
def _credential_context():
    clear_current_auth_context()
    yield
    clear_current_auth_context()


async def _seed(active_user, monkeypatch):
    async def enforce(*, context, act, obj, **_kwargs):
        policy = context.get("api_key_permissions")
        resource_type, _, resource_id = obj.partition(":")
        return policy is None or any(
            act in item["actions"]
            and item["resource_type"] == resource_type
            and ("resource_ids" not in item or resource_id in item["resource_ids"])
            for item in policy.get("restrictions", [])
        )

    authorization = SimpleNamespace(supports_api_key_scopes=AsyncMock(return_value=True), enforce=enforce)
    monkeypatch.setattr(get_settings_service().auth_settings, "AUTHZ_ENABLED", True)
    monkeypatch.setattr(
        "langflow.services.database.models.api_key.crud.get_authorization_service", lambda: authorization
    )
    monkeypatch.setattr("langflow.services.authorization.guards.get_authorization_service", lambda: authorization)
    async with session_scope() as session:
        flow = Flow(name="Queued key test", user_id=active_user.id, data={"nodes": [], "edges": []})
        key = ApiKey(name="Queued key", api_key="not-a-real-credential", user_id=active_user.id, permissions=_policy())
        session.add(flow)
        session.add(key)
        await session.flush()
        return flow.id, key.id


def _authenticate(key_id):
    set_current_auth_context(
        AuthCredentialContext(
            method="api_key",
            api_key_id=key_id,
            api_key_source="db",  # pragma: allowlist secret
            api_key_restricted=True,
            api_key_permissions=_policy(),
        )
    )


async def test_job_creation_stamps_provenance_atomically(active_user, monkeypatch):
    flow_id, key_id = await _seed(active_user, monkeypatch)
    _authenticate(key_id)
    job = await get_job_service().create_job(
        uuid4(), flow_id, user_id=active_user.id, initial_metadata={"request": {"input_value": "hello"}}
    )
    origin = job.job_metadata[_PROVENANCE]
    assert origin["api_key_id"] == str(key_id)
    assert origin["actor_user_id"] == str(active_user.id)
    assert origin["targets"] == [{"resource_type": "flow", "resource_id": str(flow_id), "action": "execute"}]
    assert "permissions" not in origin
    assert "api_key" not in origin


async def test_untrusted_metadata_cannot_inject_provenance(active_user):
    job = await get_job_service().create_job(
        uuid4(),
        uuid4(),
        user_id=active_user.id,
        initial_metadata={_PROVENANCE: {"api_key_id": "forged"}, "request": {}},
    )
    assert _PROVENANCE not in job.job_metadata


@pytest.mark.parametrize(
    "change",
    [
        "deleted",
        "inactive",
        "expired",
        "narrowed",
        "owner_inactive",
        "malformed",
        "provenance",
        "target",
        "external_profile",
    ],
)
async def test_changed_key_blocks_queued_callback(active_user, monkeypatch, change):
    flow_id, key_id = await _seed(active_user, monkeypatch)
    _authenticate(key_id)
    service = get_job_service()
    job_id = uuid4()
    await service.create_job(job_id, flow_id, user_id=active_user.id)
    clear_current_auth_context()
    async with session_scope() as session:
        key = await session.get(ApiKey, key_id)
        if change == "deleted":
            await session.delete(key)
        elif change == "inactive":
            key.is_active = False
        elif change == "expired":
            key.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        elif change == "narrowed":
            key.permissions = _policy(["read"])
        elif change == "malformed":
            key.permissions = {}
        elif change == "provenance":
            job = await session.get(Job, job_id)
            job.job_metadata = {**job.job_metadata, _PROVENANCE: None}
        elif change == "target":
            job = await session.get(Job, job_id)
            job.flow_id = uuid4()
        elif change == "external_profile":
            auth_settings = get_settings_service().auth_settings
            monkeypatch.setattr(auth_settings, "EXTERNAL_AUTH_ACCESS_CEILING_ENABLED", True)
            monkeypatch.setattr(auth_settings, "EXTERNAL_AUTH_DISABLE_API_KEYS_FOR_EXTERNAL_USERS", True)
            session.add(
                SSOUserProfile(
                    user_id=active_user.id,
                    sso_provider=auth_settings.EXTERNAL_AUTH_PROVIDER,
                    sso_user_id=str(active_user.id),
                )
            )
        else:
            owner = await session.get(User, active_user.id)
            owner.is_active = False
        await session.flush()
    callback = AsyncMock(return_value="must not execute")
    with pytest.raises(PermissionError):
        await service.execute_with_status(job_id, callback)
    callback.assert_not_awaited()
    failed = await service.get_job_by_job_id(job_id)
    assert failed.status == JobStatus.FAILED
    assert failed.error == {"type": "authorization_denied", "detail": "Job authorization is no longer valid."}


async def test_metadata_replacement_preserves_origin(active_user, monkeypatch):
    flow_id, key_id = await _seed(active_user, monkeypatch)
    _authenticate(key_id)
    service = get_job_service()
    job_id = uuid4()
    original = await service.create_job(job_id, flow_id, user_id=active_user.id)
    clear_current_auth_context()
    updated = await service.update_job_metadata(job_id, {"progress": 10}, replace=True)
    assert updated.job_metadata[_PROVENANCE] == original.job_metadata[_PROVENANCE]


async def test_suspend_and_metadata_update_cannot_replace_origin(active_user, monkeypatch):
    flow_id, key_id = await _seed(active_user, monkeypatch)
    _authenticate(key_id)
    service = get_job_service()
    job_id = uuid4()
    original = await service.create_job(job_id, flow_id, user_id=active_user.id)
    clear_current_auth_context()
    suspended = await service.suspend_job(job_id, {"pending_request_id": "pause"})
    assert suspended.job_metadata[_PROVENANCE] == original.job_metadata[_PROVENANCE]
    assert suspended.status == JobStatus.SUSPENDED
    for update in (service.suspend_job, service.update_job_metadata):
        with pytest.raises(PermissionError):
            await update(job_id, {_PROVENANCE: None})
    preserved = await service.get_job_by_job_id(job_id)
    assert preserved.job_metadata[_PROVENANCE] == original.job_metadata[_PROVENANCE]


@pytest.mark.parametrize("asset_type", ["knowledge_base", "memory_base"])
async def test_ingestion_rechecks_real_knowledge_base_target(active_user, monkeypatch, asset_type):
    flow_id, key_id = await _seed(active_user, monkeypatch)
    async with session_scope() as session:
        knowledge_base = KnowledgeBaseRecord(name=f"queued-{asset_type}", user_id=active_user.id)
        session.add(knowledge_base)
        await session.flush()
        asset_id = knowledge_base.id
        if asset_type == "memory_base":
            memory_base = MemoryBase(
                name="Queued memory", flow_id=flow_id, user_id=active_user.id, kb_name=knowledge_base.name
            )
            session.add(memory_base)
            await session.flush()
            asset_id = memory_base.id
        key = await session.get(ApiKey, key_id)
        key.permissions = {
            "restrictions": [
                *_policy()["restrictions"],
                {"resource_type": "knowledge_base", "actions": ["ingest"], "resource_ids": [str(knowledge_base.id)]},
            ]
        }
        knowledge_base_id = knowledge_base.id
    _authenticate(key_id)
    service = get_job_service()
    job_id = uuid4()
    job = await service.create_job(
        job_id,
        flow_id if asset_type == "memory_base" else uuid4(),
        job_type=JobType.INGESTION,
        asset_id=asset_id,
        asset_type=asset_type,
        user_id=active_user.id,
    )
    targets = job.job_metadata[_PROVENANCE]["targets"]
    assert targets[-1] == {"resource_type": "knowledge_base", "resource_id": str(knowledge_base_id), "action": "ingest"}
    assert len(targets) == (2 if asset_type == "memory_base" else 1)
    clear_current_auth_context()
    callback = AsyncMock(return_value="ingested")
    assert await service.execute_with_status(job_id, callback) == "ingested"
    async with session_scope() as session:
        key = await session.get(ApiKey, key_id)
        key.permissions = _policy()
    callback.reset_mock()
    with pytest.raises(PermissionError):
        await service.execute_with_status(job_id, callback)
    callback.assert_not_awaited()


async def test_current_key_allows_work_without_changing_callback_identity(active_user, monkeypatch):
    flow_id, key_id = await _seed(active_user, monkeypatch)
    _authenticate(key_id)
    service = get_job_service()
    job_id = uuid4()
    await service.create_job(job_id, flow_id, user_id=active_user.id)
    clear_current_auth_context()
    execution_identity = object()
    callback = AsyncMock(return_value="completed")
    assert await service.execute_with_status(job_id, callback, user=execution_identity) == "completed"
    callback.assert_awaited_once_with(user=execution_identity)


async def test_legacy_job_has_no_key_revalidation(active_user):
    service = get_job_service()
    job_id = uuid4()
    await service.create_job(job_id, uuid4(), user_id=active_user.id)
    callback = AsyncMock(return_value="legacy")
    assert await service.execute_with_status(job_id, callback) == "legacy"


async def test_worker_callback_preserves_key_attribution_for_child_work(active_user, monkeypatch):
    from langflow.services.auth.context import get_current_auth_context

    flow_id, key_id = await _seed(active_user, monkeypatch)
    _authenticate(key_id)
    service = get_job_service()
    job_id = uuid4()
    await service.create_job(job_id, flow_id, user_id=active_user.id)
    clear_current_auth_context()

    async def callback():
        context = get_current_auth_context()
        assert context is not None
        assert context.api_key_id == key_id
        child = await service.create_job(uuid4(), flow_id, user_id=active_user.id)
        assert child.job_metadata[_PROVENANCE]["api_key_id"] == str(key_id)

    await service.execute_with_status(job_id, callback)
    assert get_current_auth_context() is None


@pytest.mark.parametrize("owner_present", [True, False])
async def test_queue_authorization_failure_keeps_owner_in_audit(active_user, monkeypatch, owner_present):
    from langflow.services.database.models.auth import AuthzAuditLog
    from sqlmodel import select

    flow_id, key_id = await _seed(active_user, monkeypatch)
    settings = get_settings_service().auth_settings
    monkeypatch.setattr(settings, "AUTHZ_AUDIT_ENABLED", True)
    monkeypatch.setattr(settings, "AUTHZ_AUDIT_DURABLE", True)
    _authenticate(key_id)
    service = get_job_service()
    job_id = uuid4()
    await service.create_job(job_id, flow_id, user_id=active_user.id)
    clear_current_auth_context()
    async with session_scope() as session:
        key = await session.get(ApiKey, key_id)
        if owner_present:
            key.is_active = False
        else:
            owner = await session.get(User, active_user.id)
            await session.delete(owner)
    with pytest.raises(PermissionError):
        await service.execute_with_status(job_id, AsyncMock())
    async with session_scope() as session:
        event = (await session.exec(select(AuthzAuditLog).where(AuthzAuditLog.actor_id == key_id))).one()
    assert event.actor_type == "api_key"
    assert event.user_id == (active_user.id if owner_present else None)
    if not owner_present:
        assert event.details["originating_user_id"] == str(active_user.id)
