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


def test_superuser_always_authorized(monkeypatch):
    _enable(monkeypatch)
    # Even for another end user's job, the admin/editor bypass holds.
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
