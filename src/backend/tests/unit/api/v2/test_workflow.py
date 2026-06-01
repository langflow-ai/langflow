"""Unit tests for the V2 Workflow status, stop, and IDOR-protection endpoints.

The AG-UI request contract for ``POST /workflows`` is covered, no-mocks, in
``test_workflow_agui.py``. This module covers the ``GET /workflows`` status
endpoint, ``POST /workflows/stop``, and cross-user ownership enforcement.

Test Organization:
    - TestWorkflowDeveloperAPIProtection: endpoint reachability (status, stop)
    - TestWorkflowStatus: workflow status retrieval
    - TestWorkflowStop: stopping a running workflow
    - TestWorkflowIDORProtection: cross-user ownership enforcement
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.jobs.model import Job, JobType
from lfx.schema.workflow import JobStatus
from lfx.services.deps import session_scope


class TestWorkflowDeveloperAPIProtection:
    """Test developer API protection for workflow endpoints."""

    async def test_get_workflow_allowed_when_dev_api_enabled_job_not_found(
        self,
        client: AsyncClient,
        created_api_key,
    ):
        """Test GET workflow endpoint is allowed when developer API is enabled - job not found."""
        headers = {"x-api-key": created_api_key.api_key}
        response = await client.get(
            "api/v2/workflows?job_id=550e8400-e29b-41d4-a716-446655440001",  # Non-existent job ID
            headers=headers,
        )

        assert response.status_code == 404
        result = response.json()
        assert result["detail"]["code"] == "JOB_NOT_FOUND"
        assert "550e8400-e29b-41d4-a716-446655440001" in result["detail"]["job_id"]
        assert "This endpoint is not available" not in response.text

    async def test_stop_workflow_allowed_when_dev_api_enabled_job_not_found(
        self,
        client: AsyncClient,
        created_api_key,
    ):
        """Test POST workflow/stop endpoint is allowed when developer API is enabled - job not found."""
        request_data = {
            "job_id": "550e8400-e29b-41d4-a716-446655440001"  # Non-existent job ID
        }

        headers = {"x-api-key": created_api_key.api_key}
        response = await client.post(
            "api/v2/workflows/stop",
            json=request_data,
            headers=headers,
        )

        # Should return 404 because job doesn't exist, NOT because endpoint is disabled
        assert response.status_code == 404
        result = response.json()
        assert result["detail"]["code"] == "JOB_NOT_FOUND"
        assert "550e8400-e29b-41d4-a716-446655440001" in result["detail"]["job_id"]
        assert "This endpoint is not available" not in response.text

    async def test_get_workflow_allowed_when_dev_api_enabled_job_exists(
        self,
        client: AsyncClient,
        created_api_key,
    ):
        """Test GET /workflow allowed when dev API enabled - job exists (501 not implemented)."""
        # Since job management isn't implemented, we'll test with any job_id
        # The endpoint should return 501 regardless of whether the job exists
        headers = {"x-api-key": created_api_key.api_key}
        response = await client.get(
            "api/v2/workflows?job_id=550e8400-e29b-41d4-a716-446655440002",
            headers=headers,
        )

        assert response.status_code == 404
        result = response.json()
        assert result["detail"]["code"] == "JOB_NOT_FOUND"
        assert "This endpoint is not available" not in response.text

    async def test_stop_workflow_allowed_when_dev_api_enabled_job_exists(
        self,
        client: AsyncClient,
        created_api_key,
    ):
        """Test POST /workflow/stop allowed when dev API enabled - job exists (501 not implemented)."""
        # Since job management isn't implemented, we'll test with any job_id
        # The endpoint should return 501 regardless of whether the job exists
        request_data = {"job_id": "550e8400-e29b-41d4-a716-446655440002"}

        headers = {"x-api-key": created_api_key.api_key}
        response = await client.post(
            "api/v2/workflows/stop",
            json=request_data,
            headers=headers,
        )

        assert response.status_code == 404
        result = response.json()
        assert result["detail"]["code"] == "JOB_NOT_FOUND"
        assert "This endpoint is not available" not in response.text


class TestWorkflowStatus:
    """Test workflow status retrieval endpoints."""

    async def test_get_status_queued(
        self,
        client: AsyncClient,
        created_api_key,
    ):
        """Test GET /workflow returns 200 for a queued job."""
        job_id = uuid4()
        flow_id = uuid4()

        mock_job = MagicMock()
        mock_job.job_id = job_id
        mock_job.flow_id = flow_id
        mock_job.status = JobStatus.QUEUED
        mock_job.type = JobType.WORKFLOW
        mock_job.user_id = None
        mock_job.created_timestamp = datetime.now(timezone.utc)

        with patch("langflow.api.v2.workflow.get_job_service") as mock_get_job_service:
            mock_service = MagicMock()
            mock_service.get_job_by_job_id = AsyncMock(return_value=mock_job)
            mock_get_job_service.return_value = mock_service

            headers = {"x-api-key": created_api_key.api_key}
            response = await client.get(f"api/v2/workflows?job_id={job_id}", headers=headers)

            assert response.status_code == 200
            result = response.json()
            assert result["job_id"] == str(job_id)
            assert result["status"] == "queued"
            assert result["flow_id"] == str(flow_id)

    async def test_get_status_not_found(
        self,
        client: AsyncClient,
        created_api_key,
    ):
        """Test GET /workflow returns 404 for a non-existent job."""
        job_id = uuid4()

        with patch("langflow.api.v2.workflow.get_job_service") as mock_get_job_service:
            mock_service = MagicMock()
            mock_service.get_job_by_job_id = AsyncMock(return_value=None)
            mock_get_job_service.return_value = mock_service

            headers = {"x-api-key": created_api_key.api_key}
            response = await client.get(f"api/v2/workflows?job_id={job_id}", headers=headers)

            assert response.status_code == 404
            result = response.json()
            assert result["detail"]["code"] == "JOB_NOT_FOUND"

    async def test_get_status_failed(
        self,
        client: AsyncClient,
        created_api_key,
    ):
        """Test GET /workflow returns 500 for a failed job."""
        job_id = uuid4()

        mock_job = MagicMock()
        mock_job.job_id = job_id
        mock_job.status = JobStatus.FAILED
        mock_job.type = JobType.WORKFLOW
        mock_job.user_id = None

        with patch("langflow.api.v2.workflow.get_job_service") as mock_get_job_service:
            mock_service = MagicMock()
            mock_service.get_job_by_job_id = AsyncMock(return_value=mock_job)
            mock_get_job_service.return_value = mock_service

            headers = {"x-api-key": created_api_key.api_key}
            response = await client.get(f"api/v2/workflows?job_id={job_id}", headers=headers)

            assert response.status_code == 500
            result = response.json()
            assert result["detail"]["code"] == "JOB_FAILED"
            assert result["detail"]["job_id"] == str(job_id)

    async def test_get_status_completed_reconstruction(
        self,
        client: AsyncClient,
        created_api_key,
    ):
        """Test GET /workflow returns reconstructed response for a completed job."""
        job_id = uuid4()

        flow_id = uuid4()
        mock_job = MagicMock()
        mock_job.job_id = job_id
        mock_job.flow_id = flow_id
        mock_job.status = JobStatus.COMPLETED
        mock_job.type = JobType.WORKFLOW
        mock_job.user_id = None

        with (
            patch("langflow.api.v2.workflow.get_job_service") as mock_get_job_service,
            patch("langflow.api.v2.workflow.get_flow_by_id_or_endpoint_name") as mock_get_flow,
            patch("langflow.api.v2.workflow.reconstruct_workflow_response_from_job_id") as mock_reconstruct,
        ):
            mock_service = MagicMock()
            mock_service.get_job_by_job_id = AsyncMock(return_value=mock_job)
            mock_get_job_service.return_value = mock_service

            mock_flow = MagicMock()
            mock_flow.id = flow_id
            mock_get_flow.return_value = mock_flow

            mock_reconstruct.return_value = {"flow_id": str(flow_id), "status": "completed", "outputs": {}}

            headers = {"x-api-key": created_api_key.api_key}
            response = await client.get(f"api/v2/workflows?job_id={job_id}", headers=headers)

            assert response.status_code == 200
            result = response.json()
            assert result["status"] == "completed"
            mock_reconstruct.assert_called_once()

    async def test_get_status_timed_out(
        self,
        client: AsyncClient,
        created_api_key,
    ):
        """Test GET /workflow returns 408 for a timed out job."""
        job_id = uuid4()
        flow_id = uuid4()

        mock_job = MagicMock()
        mock_job.job_id = job_id
        mock_job.flow_id = flow_id
        mock_job.status = JobStatus.TIMED_OUT
        mock_job.type = JobType.WORKFLOW
        mock_job.user_id = None

        with patch("langflow.api.v2.workflow.get_job_service") as mock_get_job_service:
            mock_service = MagicMock()
            mock_service.get_job_by_job_id = AsyncMock(return_value=mock_job)
            mock_get_job_service.return_value = mock_service

            headers = {"x-api-key": created_api_key.api_key}
            # Add timeout to client.get to avoid hanging if something goes wrong
            response = await client.get(f"api/v2/workflows?job_id={job_id}", headers=headers)

            assert response.status_code == 408
            result = response.json()
            assert result["detail"]["code"] == "EXECUTION_TIMEOUT"
            assert result["detail"]["job_id"] == str(job_id)
            assert result["detail"]["flow_id"] == str(flow_id)


class TestWorkflowStop:
    """Test workflow stop endpoints."""

    async def test_stop_workflow_success(
        self,
        client: AsyncClient,
        created_api_key,
    ):
        """Test POST /workflow/stop cancels a running job."""
        job_id = str(uuid4())

        mock_job = MagicMock()
        mock_job.job_id = job_id
        mock_job.status = JobStatus.IN_PROGRESS
        mock_job.type = JobType.WORKFLOW
        mock_job.user_id = None

        with (
            patch("langflow.api.v2.workflow.get_job_service") as mock_get_job_service,
            patch("langflow.api.v2.workflow.get_task_service") as mock_get_task_service,
        ):
            mock_job_service = MagicMock()
            mock_job_service.get_job_by_job_id = AsyncMock(return_value=mock_job)
            mock_job_service.update_job_status = AsyncMock()
            mock_get_job_service.return_value = mock_job_service

            mock_task_service = MagicMock()
            mock_task_service.revoke_task = AsyncMock(return_value=True)
            mock_get_task_service.return_value = mock_task_service

            headers = {"x-api-key": created_api_key.api_key}
            response = await client.post("api/v2/workflows/stop", json={"job_id": job_id}, headers=headers)

            assert response.status_code == 200
            result = response.json()
            assert result["job_id"] == job_id
            assert "cancelled successfully" in result["message"]
            mock_task_service.revoke_task.assert_called_once()
            mock_job_service.update_job_status.assert_called_once_with(UUID(job_id), JobStatus.CANCELLED)

    async def test_stop_workflow_not_found(
        self,
        client: AsyncClient,
        created_api_key,
    ):
        """Test POST /workflow/stop returns 404 for non-existent job."""
        job_id = str(uuid4())

        with patch("langflow.api.v2.workflow.get_job_service") as mock_get_job_service:
            mock_service = MagicMock()
            mock_service.get_job_by_job_id = AsyncMock(return_value=None)
            mock_get_job_service.return_value = mock_service

            headers = {"x-api-key": created_api_key.api_key}
            response = await client.post("api/v2/workflows/stop", json={"job_id": job_id}, headers=headers)

            assert response.status_code == 404
            result = response.json()
            assert result["detail"]["code"] == "JOB_NOT_FOUND"

    async def test_stop_workflow_already_cancelled(
        self,
        client: AsyncClient,
        created_api_key,
    ):
        """Test POST /workflow/stop handles already cancelled jobs."""
        job_id = str(uuid4())

        mock_job = MagicMock()
        mock_job.job_id = job_id
        mock_job.status = JobStatus.CANCELLED
        mock_job.type = JobType.WORKFLOW
        mock_job.user_id = None

        with patch("langflow.api.v2.workflow.get_job_service") as mock_get_job_service:
            mock_service = MagicMock()
            mock_service.get_job_by_job_id = AsyncMock(return_value=mock_job)
            mock_get_job_service.return_value = mock_service

            headers = {"x-api-key": created_api_key.api_key}
            response = await client.post("api/v2/workflows/stop", json={"job_id": job_id}, headers=headers)

            assert response.status_code == 200
            result = response.json()
            assert result["job_id"] == job_id
            assert "already cancelled" in result["message"]


@pytest.mark.security
class TestWorkflowIDORProtection:
    """Security regression tests for IDOR on workflow job endpoints.

    Covers GHSA-qfw4-cjhf-3g3q: background workflow jobs are queryable and
    cancellable cross-user unless an ownership check is enforced.
    """

    @pytest.mark.security
    async def test_get_workflow_status_forbidden_for_other_user_job(
        self,
        client: AsyncClient,
        created_api_key,
        created_user_two_api_key,
    ):
        """GET /api/v2/workflows returns 404 when the job belongs to a different user.

        GHSA-qfw4-cjhf-3g3q: job status must not be visible cross-user.
        Ownership is enforced at the SQL level — unauthorized access returns 404.
        """
        job_id = uuid4()
        other_user_id = created_user_two_api_key.user_id

        async with session_scope() as session:
            job = Job(
                job_id=job_id,
                flow_id=uuid4(),
                status=JobStatus.QUEUED,
                type=JobType.WORKFLOW,
                user_id=other_user_id,
            )
            session.add(job)
            await session.flush()

        try:
            headers = {"x-api-key": created_api_key.api_key}
            response = await client.get(f"api/v2/workflows?job_id={job_id}", headers=headers)

            assert response.status_code == 404
            result = response.json()
            assert result["detail"]["code"] == "JOB_NOT_FOUND"
            assert result["detail"]["job_id"] == str(job_id)
        finally:
            async with session_scope() as session:
                db_job = await session.get(Job, job_id)
                if db_job:
                    await session.delete(db_job)

    @pytest.mark.security
    async def test_get_workflow_status_allowed_for_own_job(
        self,
        client: AsyncClient,
        created_api_key,
    ):
        """GET /api/v2/workflows returns 200 when the job belongs to the requesting user."""
        job_id = uuid4()
        owner_user_id = created_api_key.user_id

        async with session_scope() as session:
            job = Job(
                job_id=job_id,
                flow_id=uuid4(),
                status=JobStatus.QUEUED,
                type=JobType.WORKFLOW,
                user_id=owner_user_id,
            )
            session.add(job)
            await session.flush()

        try:
            headers = {"x-api-key": created_api_key.api_key}
            response = await client.get(f"api/v2/workflows?job_id={job_id}", headers=headers)

            assert response.status_code == 200
            result = response.json()
            assert result["job_id"] == str(job_id)
        finally:
            async with session_scope() as session:
                db_job = await session.get(Job, job_id)
                if db_job:
                    await session.delete(db_job)

    @pytest.mark.security
    async def test_stop_workflow_forbidden_for_other_user_job(
        self,
        client: AsyncClient,
        created_api_key,
        created_user_two_api_key,
    ):
        """POST /api/v2/workflows/stop returns 404 when the job belongs to a different user.

        GHSA-qfw4-cjhf-3g3q: job cancellation must not be allowed cross-user.
        Ownership is enforced at the SQL level — unauthorized access returns 404.
        """
        job_id = uuid4()
        other_user_id = created_user_two_api_key.user_id

        async with session_scope() as session:
            job = Job(
                job_id=job_id,
                flow_id=uuid4(),
                status=JobStatus.IN_PROGRESS,
                type=JobType.WORKFLOW,
                user_id=other_user_id,
            )
            session.add(job)
            await session.flush()

        try:
            headers = {"x-api-key": created_api_key.api_key}
            response = await client.post(
                "api/v2/workflows/stop",
                json={"job_id": str(job_id)},
                headers=headers,
            )

            assert response.status_code == 404
            result = response.json()
            assert result["detail"]["code"] == "JOB_NOT_FOUND"
            assert result["detail"]["job_id"] == str(job_id)
        finally:
            async with session_scope() as session:
                db_job = await session.get(Job, job_id)
                if db_job:
                    await session.delete(db_job)

    @pytest.mark.security
    async def test_stop_workflow_allowed_for_own_job(
        self,
        client: AsyncClient,
        created_api_key,
    ):
        """POST /api/v2/workflows/stop succeeds when the job belongs to the requesting user."""
        job_id = uuid4()
        owner_user_id = created_api_key.user_id

        async with session_scope() as session:
            job = Job(
                job_id=job_id,
                flow_id=uuid4(),
                status=JobStatus.CANCELLED,
                type=JobType.WORKFLOW,
                user_id=owner_user_id,
            )
            session.add(job)
            await session.flush()

        try:
            headers = {"x-api-key": created_api_key.api_key}
            response = await client.post(
                "api/v2/workflows/stop",
                json={"job_id": str(job_id)},
                headers=headers,
            )

            assert response.status_code == 200
        finally:
            async with session_scope() as session:
                db_job = await session.get(Job, job_id)
                if db_job:
                    await session.delete(db_job)

    @pytest.mark.security
    async def test_get_workflow_status_allowed_for_legacy_job_with_no_user_id(
        self,
        client: AsyncClient,
        created_api_key,
    ):
        """GET /api/v2/workflows does NOT block legacy jobs where user_id is NULL.

        Jobs created before the fix have user_id=None and must not be broken.
        """
        job_id = uuid4()

        async with session_scope() as session:
            job = Job(
                job_id=job_id,
                flow_id=uuid4(),
                status=JobStatus.QUEUED,
                type=JobType.WORKFLOW,
                user_id=None,
            )
            session.add(job)
            await session.flush()

        try:
            headers = {"x-api-key": created_api_key.api_key}
            response = await client.get(f"api/v2/workflows?job_id={job_id}", headers=headers)

            assert response.status_code == 200
            result = response.json()
            assert result["job_id"] == str(job_id)
        finally:
            async with session_scope() as session:
                db_job = await session.get(Job, job_id)
                if db_job:
                    await session.delete(db_job)

    @pytest.mark.security
    async def test_stop_workflow_allowed_for_legacy_job_with_no_user_id(
        self,
        client: AsyncClient,
        created_api_key,
    ):
        """POST /api/v2/workflows/stop does NOT block legacy jobs where user_id is NULL.

        Jobs created before the ownership fix have user_id=None and must not be
        broken by the ownership check (parity with the equivalent GET test).
        """
        job_id = uuid4()

        async with session_scope() as session:
            job = Job(
                job_id=job_id,
                flow_id=uuid4(),
                status=JobStatus.IN_PROGRESS,
                type=JobType.WORKFLOW,
                user_id=None,
            )
            session.add(job)
            await session.flush()

        try:
            headers = {"x-api-key": created_api_key.api_key}
            response = await client.post(
                "api/v2/workflows/stop",
                json={"job_id": str(job_id)},
                headers=headers,
            )

            assert response.status_code == 200, (
                "Legacy jobs with user_id=None must not be blocked by the ownership check"
            )
        finally:
            async with session_scope() as session:
                db_job = await session.get(Job, job_id)
                if db_job:
                    await session.delete(db_job)

    @pytest.mark.security
    async def test_stop_workflow_returns_404_for_non_workflow_job_type(
        self,
        client: AsyncClient,
        created_api_key,
    ):
        """POST /api/v2/workflows/stop returns 404 for non-WORKFLOW job types.

        Prevents stop endpoint from cancelling ingestion or evaluation jobs.
        """
        job_id = uuid4()

        async with session_scope() as session:
            job = Job(
                job_id=job_id,
                flow_id=uuid4(),
                status=JobStatus.IN_PROGRESS,
                type=JobType.INGESTION,
                user_id=None,
            )
            session.add(job)
            await session.flush()

        try:
            headers = {"x-api-key": created_api_key.api_key}
            response = await client.post(
                "api/v2/workflows/stop",
                json={"job_id": str(job_id)},
                headers=headers,
            )

            assert response.status_code == 404
            result = response.json()
            assert result["detail"]["code"] == "JOB_NOT_FOUND"
        finally:
            async with session_scope() as session:
                db_job = await session.get(Job, job_id)
                if db_job:
                    await session.delete(db_job)

    @pytest.mark.security
    async def test_get_workflow_status_returns_404_for_non_workflow_job_type(
        self,
        client: AsyncClient,
        created_api_key,
    ):
        """GET /api/v2/workflows returns 404 for non-WORKFLOW job types.

        Prevents status endpoint from exposing ingestion or evaluation jobs.
        """
        job_id = uuid4()

        async with session_scope() as session:
            job = Job(
                job_id=job_id,
                flow_id=uuid4(),
                status=JobStatus.IN_PROGRESS,
                type=JobType.INGESTION,
                user_id=None,
            )
            session.add(job)
            await session.flush()

        try:
            headers = {"x-api-key": created_api_key.api_key}
            response = await client.get(f"api/v2/workflows?job_id={job_id}", headers=headers)

            assert response.status_code == 404
            result = response.json()
            assert result["detail"]["code"] == "JOB_NOT_FOUND"
        finally:
            async with session_scope() as session:
                db_job = await session.get(Job, job_id)
                if db_job:
                    await session.delete(db_job)

    @pytest.mark.security
    async def test_background_job_stores_user_id_and_blocks_cross_user_access(
        self,
        client: AsyncClient,
        created_api_key,
        created_user_two_api_key,
    ):
        """End-to-end: POST /workflows (background=true) stores user_id and blocks cross-user GET.

        This test exercises the real create_job code path to catch regressions
        where user_id is not passed to create_job (causing user_id=NULL and
        bypassing the ownership check — the exact bug found in Postman).

        Steps:
          1. Alice creates a background job via the real endpoint (no mock on create_job)
          2. Bob queries the job_id returned — must get 404 (ownership enforced at SQL level)
        """
        flow_id = uuid4()
        job_id_str = None

        async with session_scope() as session:
            flow = Flow(
                id=flow_id,
                name="Alice End-to-End Flow",
                data={"nodes": [], "edges": []},
                user_id=created_api_key.user_id,
            )
            session.add(flow)
            await session.flush()

        try:
            # Mock only the task service to prevent real background execution
            with patch("langflow.api.v2.workflow.get_task_service") as mock_task_svc:
                mock_task_service = MagicMock()
                mock_task_service.fire_and_forget_task = AsyncMock()
                mock_task_svc.return_value = mock_task_service

                alice_headers = {"x-api-key": created_api_key.api_key}
                response = await client.post(
                    "api/v2/workflows",
                    json={
                        "flow_id": str(flow_id),
                        "mode": "background",
                        "session_id": "idor-thread",
                    },
                    headers=alice_headers,
                )

            assert response.status_code in (200, 202), (
                f"Expected 200/202 from Alice's background job creation, got {response.status_code}: {response.text}"
            )
            job_id_str = response.json()["job_id"]

            # Bob queries Alice's job — must be 404 (ownership enforced at SQL level)
            bob_headers = {"x-api-key": created_user_two_api_key.api_key}
            response = await client.get(
                f"api/v2/workflows?job_id={job_id_str}",
                headers=bob_headers,
            )

            assert response.status_code == 404, (
                f"Expected 404 Not Found but got {response.status_code}. "
                "user_id is not being persisted in create_job — Bob can access Alice's job."
            )
            assert response.json()["detail"]["code"] == "JOB_NOT_FOUND"

        finally:
            async with session_scope() as session:
                if job_id_str:
                    db_job = await session.get(Job, UUID(job_id_str))
                    if db_job:
                        await session.delete(db_job)
                db_flow = await session.get(Flow, flow_id)
                if db_flow:
                    await session.delete(db_flow)
