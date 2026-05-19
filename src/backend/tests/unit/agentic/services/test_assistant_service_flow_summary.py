"""Tests for _get_current_flow_summary ownership + error isolation.

Covers reviewer findings:
- I2: the canvas-context loader must never load a flow the caller does not
  own (IDOR — another user's flow structure leaking into the prompt).
- I5: a malformed flow_id must be distinguished from an operational DB
  failure — it is "no context", not an error, and must not hit the DB.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from uuid import uuid4

from langflow.agentic.services import assistant_service


class _FakeFlow:
    def __init__(self, *, user_id, data, name="Canvas"):
        self.user_id = user_id
        self.data = data
        self.name = name


class _FakeSession:
    def __init__(self, flow):
        self._flow = flow

    async def get(self, _model, _pk):
        return self._flow


def _patch_session(monkeypatch, flow, *, entered_flag=None):
    @asynccontextmanager
    async def _scope():
        if entered_flag is not None:
            entered_flag.append(True)
        yield _FakeSession(flow)

    monkeypatch.setattr("lfx.services.deps.session_scope", _scope)


class TestFlowSummaryOwnership:
    async def test_should_return_none_when_flow_belongs_to_another_user(self, monkeypatch):
        # Arrange — flow owned by user B, requested by user A.
        owner_b = uuid4()
        caller_a = str(uuid4())
        flow = _FakeFlow(user_id=owner_b, data={"nodes": [], "edges": []})
        _patch_session(monkeypatch, flow)

        init_calls: list = []
        monkeypatch.setattr(
            assistant_service,
            "init_working_flow",
            lambda *a, **k: init_calls.append((a, k)),
        )

        # Act
        result = await assistant_service._get_current_flow_summary(str(uuid4()), user_id=caller_a)

        # Assert — no cross-user canvas leaked, and the working flow was NOT seeded.
        assert result is None
        assert init_calls == []

    async def test_should_return_summary_when_caller_owns_the_flow(self, monkeypatch):
        owner = uuid4()
        flow = _FakeFlow(user_id=owner, data={"nodes": [], "edges": []})
        _patch_session(monkeypatch, flow)
        monkeypatch.setattr(assistant_service, "init_working_flow", lambda *_a, **_k: None)
        monkeypatch.setattr(assistant_service, "flow_to_spec_summary", lambda _d: "SUMMARY")

        result = await assistant_service._get_current_flow_summary(str(uuid4()), user_id=str(owner))

        assert result == "SUMMARY"


class TestFlowSummaryBadUuid:
    async def test_should_skip_context_without_db_call_when_flow_id_is_not_a_uuid(self, monkeypatch):
        entered: list = []
        _patch_session(monkeypatch, _FakeFlow(user_id=uuid4(), data={}), entered_flag=entered)

        result = await assistant_service._get_current_flow_summary("not-a-uuid", user_id=str(uuid4()))

        # Malformed id → no context, and the DB session must never be opened.
        assert result is None
        assert entered == []
