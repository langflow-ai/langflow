"""Ownership checks shared by the v1 build events and cancel endpoints."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request
from langflow.api.v1 import chat


class OwnerlessQueue:
    async def get_job_owner(self, _job_id):
        return None

    async def is_public_job_async(self, _job_id):
        return False


def request(end_user_id: str | None = None) -> Request:
    headers = [(b"x-end-user-id", end_user_id.encode())] if end_user_id is not None else []
    return Request({"type": "http", "headers": headers})


@pytest.mark.asyncio
async def test_persisted_workflow_owner_controls_v1_job_access(monkeypatch):
    """V2 background jobs have no queue owner but must stay tenant-scoped."""
    owner_id = uuid4()
    other_id = uuid4()
    job_id = str(uuid4())

    class JobService:
        async def get_job_by_job_id(self, _job_id):
            return SimpleNamespace(user_id=owner_id, job_metadata=None)

    monkeypatch.setattr(chat, "get_job_service", JobService)
    queue = OwnerlessQueue()

    await chat._verify_job_ownership(job_id, SimpleNamespace(id=owner_id, is_superuser=False), queue, request())
    with pytest.raises(HTTPException) as denied:
        await chat._verify_job_ownership(job_id, SimpleNamespace(id=other_id, is_superuser=False), queue, request())
    assert denied.value.status_code == 404


@pytest.mark.asyncio
async def test_shared_service_account_cannot_access_another_end_users_job(monkeypatch):
    """Serving end users share one account, so its UUID alone is insufficient."""
    from lfx.services import deps as lfx_deps

    settings = SimpleNamespace(
        serving_end_user_header="X-End-User-Id", serving_trust_proxy_headers=True, serving_end_user_required=False
    )
    monkeypatch.setattr(lfx_deps, "get_settings_service", lambda: SimpleNamespace(settings=settings))
    owner_id = uuid4()

    class JobService:
        async def get_job_by_job_id(self, _job_id):
            return SimpleNamespace(user_id=owner_id, job_metadata={"end_user_id": "alice"})

    monkeypatch.setattr(chat, "get_job_service", JobService)
    user = SimpleNamespace(id=owner_id, is_superuser=True)
    queue = OwnerlessQueue()
    job_id = str(uuid4())

    await chat._verify_job_ownership(job_id, user, queue, request("alice"))
    with pytest.raises(HTTPException) as denied:
        await chat._verify_job_ownership(job_id, user, queue, request("bob"))
    assert denied.value.status_code == 404


@pytest.mark.asyncio
async def test_ownerless_nonpublic_job_without_database_owner_is_denied(monkeypatch):
    class JobService:
        async def get_job_by_job_id(self, _job_id):
            return None

    monkeypatch.setattr(chat, "get_job_service", JobService)

    with pytest.raises(HTTPException) as denied:
        await chat._verify_job_ownership(str(uuid4()), SimpleNamespace(id=uuid4()), OwnerlessQueue(), request())
    assert denied.value.status_code == 404


@pytest.mark.asyncio
async def test_ownerless_job_fails_closed_when_database_is_unavailable(monkeypatch):
    class JobService:
        async def get_job_by_job_id(self, _job_id):
            raise RuntimeError

    monkeypatch.setattr(chat, "get_job_service", JobService)

    with pytest.raises(HTTPException) as denied:
        await chat._verify_job_ownership(str(uuid4()), SimpleNamespace(id=uuid4()), OwnerlessQueue(), request())
    assert denied.value.status_code == 503


@pytest.mark.asyncio
async def test_public_temporary_job_does_not_require_database_owner(monkeypatch):
    class PublicQueue(OwnerlessQueue):
        async def is_public_job_async(self, _job_id):
            return True

    def no_database_lookup():
        pytest.fail("public temporary jobs must not need a persisted workflow job")

    monkeypatch.setattr(chat, "get_job_service", no_database_lookup)

    await chat._verify_job_ownership(str(uuid4()), SimpleNamespace(id=uuid4()), PublicQueue(), request())
