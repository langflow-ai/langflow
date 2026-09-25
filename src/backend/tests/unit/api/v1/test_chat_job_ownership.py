"""Ownership checks shared by the v1 build events and cancel endpoints."""

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from langflow.api.v1 import chat
from langflow.services.job_queue.service import JobQueueBackendUnavailableError


class OwnerlessQueue:
    async def get_job_owner(self, _job_id):
        return None

    async def is_public_job_async(self, _job_id):
        return False


@pytest.mark.asyncio
async def test_owned_job_allows_owner_and_denies_other_user():
    owner_id = uuid4()

    class OwnedQueue(OwnerlessQueue):
        async def get_job_owner(self, _job_id):
            return owner_id

    job_id = str(uuid4())
    queue = OwnedQueue()
    await chat._verify_job_ownership(job_id, SimpleNamespace(id=owner_id), queue)

    with pytest.raises(HTTPException) as denied:
        await chat._verify_job_ownership(job_id, SimpleNamespace(id=uuid4()), queue)
    assert denied.value.status_code == 404


@pytest.mark.asyncio
async def test_ownerless_nonpublic_job_is_denied():
    """An unowned queue cannot be reached through authenticated v1 controls."""
    with pytest.raises(HTTPException) as denied:
        await chat._verify_job_ownership(str(uuid4()), SimpleNamespace(id=uuid4()), OwnerlessQueue())
    assert denied.value.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_at", ["owner", "marker"])
async def test_job_ownership_backend_failure_does_not_disclose_connection_target(fail_at: str):
    backend_detail = "redis://internal.example:6379/0"

    class UnavailableQueue(OwnerlessQueue):
        async def get_job_owner(self, _job_id):
            if fail_at == "owner":
                raise JobQueueBackendUnavailableError(backend_detail)

        async def is_public_job_async(self, _job_id):
            raise JobQueueBackendUnavailableError(backend_detail)

    with pytest.raises(HTTPException) as unavailable:
        await chat._verify_job_ownership(str(uuid4()), SimpleNamespace(id=uuid4()), UnavailableQueue())
    assert unavailable.value.status_code == 503
    assert unavailable.value.detail == "Job queue is temporarily unavailable."


@pytest.mark.asyncio
async def test_owner_registration_backend_failure_cancels_job_without_disclosing_connection_target():
    backend_detail = "redis://internal.example:6379/0"

    class UnavailableQueue:
        cancelled = False

        async def register_job_owner(self, _job_id, _user_id):
            raise JobQueueBackendUnavailableError(backend_detail)

        async def cancel_job(self, _job_id):
            self.cancelled = True

    queue = UnavailableQueue()
    with pytest.raises(HTTPException) as unavailable:
        await chat._register_job_owner_or_cancel(queue, str(uuid4()), uuid4())
    assert queue.cancelled
    assert unavailable.value.status_code == 503
    assert unavailable.value.detail == "Job queue is temporarily unavailable."


@pytest.mark.asyncio
async def test_public_temporary_job_does_not_require_queue_owner():
    class PublicQueue(OwnerlessQueue):
        async def is_public_job_async(self, _job_id):
            return True

    await chat._verify_job_ownership(str(uuid4()), SimpleNamespace(id=uuid4()), PublicQueue())


@pytest.mark.asyncio
async def test_v1_routes_reject_ownerless_jobs_without_touching_queue():
    """Ownerless nonpublic v1 jobs are rejected before queue access."""
    job_id = str(uuid4())

    class NoQueue(OwnerlessQueue):
        def get_queue_data(self, _job_id):
            pytest.fail("v1 routes must reject ownerless jobs before queue access")

    user = SimpleNamespace(id=uuid4())
    queue = NoQueue()

    with pytest.raises(HTTPException) as events_denied:
        await chat.get_build_events(job_id=job_id, queue_service=queue, current_user=user)
    assert events_denied.value.status_code == 404

    with pytest.raises(HTTPException) as cancel_denied:
        await chat.cancel_build(job_id=job_id, queue_service=queue, current_user=user)
    assert cancel_denied.value.status_code == 404


@pytest.mark.asyncio
async def test_public_marker_lookup_preserves_cancellation():
    class CancelledQueue:
        async def is_public_job_async(self, _job_id):
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await chat._assert_public_job(str(uuid4()), CancelledQueue(), "Public flow events are unavailable.")
