"""P3: serving-plane end-user isolation on the jobs lifecycle.

Two layers are proven here:

* the pure decision (``_caller_owns_job_end_user``) across the superuser / feature-off /
  anonymous / identified matrix, stubbing settings so no transport is involved; and
* the full HTTP chain (``POST /workflows`` background submit -> ``GET /workflows`` status /
  ``POST /workflows/stop``) showing one end user cannot read or stop another's run even
  though both share the one service-account api key.

``job.user_id`` stays the SID (so re-enqueue/resume can still fetch the SID-owned flow);
the end user lives in ``job_metadata['end_user_id']`` and is the sole isolation key here (F8).
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langflow.api.v2.workflow import _caller_owns_job_end_user
from langflow.services.database.models.flow.model import Flow
from lfx.services.deps import session_scope

HEADER = "X-End-User-Id"


def _req(**headers: str):
    """Minimal request exposing only the case-insensitive ``headers.get`` the helper uses."""
    lower = {k.lower(): v for k, v in headers.items()}
    return SimpleNamespace(headers=SimpleNamespace(get=lambda name, default=None: lower.get(name.lower(), default)))


def _job(end_user_id=None):
    return SimpleNamespace(job_metadata={"end_user_id": end_user_id} if end_user_id else None)


def _user(*, superuser=False):
    return SimpleNamespace(is_superuser=superuser)


def _stub_settings(monkeypatch, **overrides):
    base = {
        "serving_end_user_header": None,
        "serving_trust_proxy_headers": False,
        "serving_end_user_required": False,
    }
    base.update(overrides)
    from lfx.services import deps as deps_module

    monkeypatch.setattr(
        deps_module,
        "get_settings_service",
        lambda: SimpleNamespace(settings=SimpleNamespace(**base)),
    )


def _enable(monkeypatch):
    _stub_settings(monkeypatch, serving_end_user_header=HEADER, serving_trust_proxy_headers=True)


# --- pure decision matrix ----------------------------------------------------------


def test_superuser_bypass_suppressed_when_serving_on(monkeypatch):
    _enable(monkeypatch)
    # On the serving plane the SID is itself a superuser; the bypass must NOT let it (as "bob")
    # reach another end user's ("alice") job. With serving on, the superuser is scoped like anyone.
    assert _caller_owns_job_end_user(_job("alice"), _req(**{HEADER: "bob"}), _user(superuser=True)) is False
    # ...and it CAN reach a job that is actually its own end user's.
    assert _caller_owns_job_end_user(_job("alice"), _req(**{HEADER: "alice"}), _user(superuser=True)) is True


def test_superuser_bypass_holds_when_feature_off(monkeypatch):
    # Editor plane (feature off): the admin/editor superuser bypass is unchanged.
    _stub_settings(monkeypatch, serving_end_user_header=None)
    assert _caller_owns_job_end_user(_job("alice"), _req(**{HEADER: "bob"}), _user(superuser=True)) is True


def test_identified_matching_end_user_authorized(monkeypatch):
    _enable(monkeypatch)
    assert _caller_owns_job_end_user(_job("alice"), _req(**{HEADER: "alice"}), _user()) is True


def test_identified_mismatched_end_user_denied(monkeypatch):
    _enable(monkeypatch)
    assert _caller_owns_job_end_user(_job("alice"), _req(**{HEADER: "bob"}), _user()) is False


def test_anonymous_caller_cannot_reach_identified_job(monkeypatch):
    _enable(monkeypatch)
    # Feature on but this request carries no header: it must not reach an identified run.
    assert _caller_owns_job_end_user(_job("alice"), _req(), _user()) is False


def test_anonymous_caller_reaches_anonymous_job(monkeypatch):
    _enable(monkeypatch)
    assert _caller_owns_job_end_user(_job(None), _req(), _user()) is True


def test_feature_off_is_unchanged(monkeypatch):
    # No header configured: resolve returns None, and a job created pre-feature has no
    # end_user_id, so the check is a pass-through (BC).
    _stub_settings(monkeypatch, serving_end_user_header=None)
    assert _caller_owns_job_end_user(_job(None), _req(**{HEADER: "alice"}), _user()) is True


def test_non_uuid_end_user_compares_by_derived_owner(monkeypatch):
    _enable(monkeypatch)
    # Same opaque id on both sides derives to the same owner UUID -> authorized.
    assert _caller_owns_job_end_user(_job("team-7"), _req(**{HEADER: "team-7"}), _user()) is True
    assert _caller_owns_job_end_user(_job("team-7"), _req(**{HEADER: "team-9"}), _user()) is False


# --- full HTTP chain ---------------------------------------------------------------

pytestmark = pytest.mark.usefixtures("client")


@pytest.fixture
async def bg_flow(created_api_key, json_memory_chatbot_no_llm):
    raw = json.loads(json_memory_chatbot_no_llm)
    flow_id = uuid4()
    async with session_scope() as session:
        flow = Flow(
            id=flow_id,
            name="isolation-no-llm-flow",
            description="No-LLM flow for end-user isolation tests",
            data=raw.get("data", raw),
            user_id=created_api_key.user_id,
        )
        session.add(flow)
        await session.flush()
    yield str(flow_id)
    async with session_scope() as session:
        flow = await session.get(Flow, flow_id)
        if flow:
            await session.delete(flow)


def _serving_on(monkeypatch):
    """Enable the serving feature on the live settings singleton for one test."""
    from lfx.services.deps import get_settings_service

    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "serving_end_user_header", HEADER)
    monkeypatch.setattr(settings, "serving_trust_proxy_headers", True)
    monkeypatch.setattr(settings, "serving_end_user_required", False)


async def _submit(client, flow_id, api_key, *, end_user=None):
    headers = {"x-api-key": api_key}
    if end_user is not None:
        headers[HEADER] = end_user
    body = {"flow_id": flow_id, "mode": "background", "stream_protocol": "langflow", "input_value": "hi"}
    return await client.post("api/v2/workflows", json=body, headers=headers)


async def _status(client, job_id, api_key, *, end_user=None):
    headers = {"x-api-key": api_key}
    if end_user is not None:
        headers[HEADER] = end_user
    return await client.get(f"api/v2/workflows?job_id={job_id}", headers=headers)


async def _stop(client, job_id, api_key, *, end_user=None):
    headers = {"x-api-key": api_key}
    if end_user is not None:
        headers[HEADER] = end_user
    return await client.post("api/v2/workflows/stop", json={"job_id": job_id}, headers=headers)


async def test_end_user_cannot_read_or_stop_another_end_users_job(client, created_api_key, bg_flow, monkeypatch):
    _serving_on(monkeypatch)
    submit = await _submit(client, bg_flow, created_api_key.api_key, end_user="alice")
    assert submit.status_code == 200, submit.text
    job_id = submit.json()["job_id"]

    # Another end user, same api key (same SID): must not see or stop alice's run.
    assert (await _status(client, job_id, created_api_key.api_key, end_user="bob")).status_code == 404
    assert (await _stop(client, job_id, created_api_key.api_key, end_user="bob")).status_code == 404
    # An anonymous caller (feature on, no header) is likewise denied.
    assert (await _status(client, job_id, created_api_key.api_key)).status_code == 404

    # Alice herself can read her own run.
    assert (await _status(client, job_id, created_api_key.api_key, end_user="alice")).status_code == 200


async def test_feature_off_leaves_job_status_reachable(client, created_api_key, bg_flow):
    # Default settings (feature off): the header is ignored and the SID owner reads the job
    # exactly as before — proves the isolation layer is a strict no-op when off (BC).
    submit = await _submit(client, bg_flow, created_api_key.api_key, end_user="alice")
    assert submit.status_code == 200, submit.text
    job_id = submit.json()["job_id"]
    assert (await _status(client, job_id, created_api_key.api_key, end_user="bob")).status_code == 200


# --- B1: the enumerating /pending endpoint is gated too ------------------------------


async def _make_suspended_hitl_job(flow_id: str, sid, end_user: str | None):
    """Create a SUSPENDED workflow job carrying a pending human-input event.

    Owned by the SID and tagged with ``end_user`` so ``/pending`` surfaces (and scopes) it.
    """
    from langflow.services.database.models.jobs.model import JobStatus, JobType
    from langflow.services.deps import get_job_service
    from langflow.services.jobs.exceptions import HUMAN_INPUT_REQUIRED_EVENT

    svc = get_job_service()
    job_id = uuid4()
    await svc.create_job(job_id=job_id, flow_id=flow_id, job_type=JobType.WORKFLOW, user_id=sid, end_user_id=end_user)
    await svc.update_job_status(job_id, JobStatus.SUSPENDED)
    await svc.append_event(
        job_id,
        HUMAN_INPUT_REQUIRED_EVENT,
        {"request_id": f"r-{end_user}", "prompt": f"q for {end_user}", "allowed_decisions": []},
    )
    return str(job_id)


async def _pending(client, flow_id, api_key, *, end_user=None):
    headers = {"x-api-key": api_key}
    if end_user is not None:
        headers[HEADER] = end_user
    return await client.get(f"api/v2/workflows/pending?flow_id={flow_id}", headers=headers)


async def test_pending_list_is_scoped_to_the_end_user(client, created_api_key, bg_flow, monkeypatch):
    _serving_on(monkeypatch)
    sid = created_api_key.user_id
    alice_job = await _make_suspended_hitl_job(bg_flow, sid, "alice")
    bob_job = await _make_suspended_hitl_job(bg_flow, sid, "bob")

    # Alice enumerates -> only her suspended run (bob's prompt + merged session id must not leak).
    resp = await _pending(client, bg_flow, created_api_key.api_key, end_user="alice")
    assert resp.status_code == 200, resp.text
    ids = {row["job_id"] for row in resp.json()}
    assert ids == {alice_job}

    # Bob enumerates -> only his.
    resp = await _pending(client, bg_flow, created_api_key.api_key, end_user="bob")
    assert {row["job_id"] for row in resp.json()} == {bob_job}

    # Anonymous (feature on, no header) -> neither identified run.
    resp = await _pending(client, bg_flow, created_api_key.api_key)
    assert resp.json() == []


async def test_pending_list_feature_off_returns_all_bc(client, created_api_key, bg_flow):
    # Default settings: no end-user scoping, so the SID owner sees every suspended run (unchanged).
    sid = created_api_key.user_id
    a = await _make_suspended_hitl_job(bg_flow, sid, None)
    b = await _make_suspended_hitl_job(bg_flow, sid, None)
    resp = await _pending(client, bg_flow, created_api_key.api_key)
    assert resp.status_code == 200, resp.text
    assert {a, b} <= {row["job_id"] for row in resp.json()}


async def _events(client, job_id, api_key, *, end_user=None):
    headers = {"x-api-key": api_key}
    if end_user is not None:
        headers[HEADER] = end_user
    return await client.get(f"api/v2/workflows/{job_id}/events", headers=headers)


async def test_reattach_events_is_scoped_to_the_end_user(client, created_api_key, bg_flow, monkeypatch):
    # Reattaching to a live event stream is the same class as status/stop/resume (needs a job id):
    # a different end user sharing the SID must be denied before the SSE stream opens.
    _serving_on(monkeypatch)
    sid = created_api_key.user_id
    alice_job = await _make_suspended_hitl_job(bg_flow, sid, "alice")

    assert (await _events(client, alice_job, created_api_key.api_key, end_user="bob")).status_code == 404
    assert (await _events(client, alice_job, created_api_key.api_key)).status_code == 404
