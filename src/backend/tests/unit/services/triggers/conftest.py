"""Shared fixtures for the trigger service tests.

Every test here runs against the real database the ``client`` fixture stands up,
because the guarantees under test (the unique dedupe index, guarded conditional
UPDATEs, lease expiry) are database behaviour. Mocking them would test nothing.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.trigger.model import Trigger
from langflow.services.database.models.trigger.schemas import TriggerState
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope


@pytest.fixture
async def trigger_owner(client):  # noqa: ARG001
    """A user who owns flows and triggers, independent of the login fixtures."""
    async with session_scope() as session:
        user = User(
            username=f"trigger-owner-{uuid4().hex[:8]}",
            password="not-a-login",  # noqa: S106  # pragma: allowlist secret
            is_active=True,
            is_superuser=False,
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        return user.id


@pytest.fixture
async def owned_flow(trigger_owner):
    async with session_scope() as session:
        flow = Flow(name=f"trigger-flow-{uuid4().hex[:6]}", user_id=trigger_owner, data={"nodes": [], "edges": []})
        session.add(flow)
        await session.flush()
        await session.refresh(flow)
        return flow.id


@pytest.fixture
def make_trigger(trigger_owner, owned_flow):
    """Create an ACTIVE trigger row and return its id."""

    async def _make(**overrides) -> "uuid4.__class__":  # noqa: UP037 - runtime-only annotation
        fields = {
            "flow_id": owned_flow,
            "user_id": trigger_owner,
            "name": "digest",
            "kind": "schedule",
            "config": {},
            "provider_state": {},
            "state": TriggerState.ACTIVE.value,
            "concurrency_limit": 1,
            "max_attempts": 3,
        }
        fields.update(overrides)
        async with session_scope() as session:
            row = Trigger(**fields)
            session.add(row)
            await session.flush()
            await session.refresh(row)
            return row.id

    return _make


class FakeBackgroundExecutionService:
    """Records submits instead of running flows — but parses them for real.

    The dispatcher's contract with the background execution service is narrow —
    ``submit(flow_id=..., request=..., user=...) -> job_id`` — so a recorder is
    enough to assert everything TRG-2 owns (one submit per event, the request
    shape, the identity) without standing up a build pipeline.

    A pure recorder is NOT enough for the request *shape*, though. The real
    service hands the dict to ``_parse_persisted_workflow_request``, which
    rebuilds a ``WorkflowRunRequest`` — a model that forbids extra keys. A
    recorder that only appends to a list happily accepts a request the real
    worker would reject after committing the job row, which is exactly how an
    unrunnable request shape survived a fully green suite. So every submit here
    goes through the same parser first, and a bad shape fails the test that
    produced it rather than production.
    """

    def __init__(self, *, fail_times: int = 0) -> None:
        self.submits: list[dict] = []
        self.fail_times = fail_times
        self._frame_source_factory = object()  # already installed; do not touch v2 routes

    async def submit(self, *, flow_id, request, user):
        from langflow.api.v2.workflow import _parse_persisted_workflow_request

        # Raises for any key WorkflowRunRequest does not declare, exactly as the
        # real service's _enqueue -> frame-source factory does.
        _parse_persisted_workflow_request(request)
        if self.fail_times > 0:
            self.fail_times -= 1
            msg = "submit exploded"
            raise RuntimeError(msg)
        self.submits.append({"flow_id": flow_id, "request": request, "user_id": user.id})
        return uuid4()


@pytest.fixture
def fake_background_service(monkeypatch):
    """Install the recorder everywhere the dispatcher looks the service up."""
    service = FakeBackgroundExecutionService()

    def _get():
        return service

    monkeypatch.setattr("langflow.services.deps.get_background_execution_service", _get)
    return service
