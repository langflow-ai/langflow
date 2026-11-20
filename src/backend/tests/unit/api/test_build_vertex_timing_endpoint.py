"""Endpoint regression tests for per-call vertex build timing.

Server-built vertices must record exactly one build_times entry each (the single
recording site is Graph.build_vertex; the endpoints no longer record separately),
and successful responses keep their own duration/timedelta, which must contain
the recorded library entry.
"""

import collections
import json

import pytest
from httpx import codes
from lfx.graph.vertex.base import Vertex

from tests.unit.build_utils import build_flow, create_flow, get_build_events


@pytest.fixture(autouse=True)
def _allow(monkeypatch):
    monkeypatch.setenv("LANGFLOW_ALLOW_CUSTOM_COMPONENTS", "true")


@pytest.fixture
def spy(monkeypatch):
    calls = collections.defaultdict(list)
    orig = Vertex.add_build_time

    def wrapped(self, t):
        calls[self.id].append(t)
        return orig(self, t)

    monkeypatch.setattr(Vertex, "add_build_time", wrapped)
    return calls


async def _events(client, job_id, headers):
    resp = await get_build_events(client, job_id, headers)
    assert resp.status_code == codes.OK
    return [json.loads(line) async for line in resp.aiter_lines() if line.strip()]


async def test_build_flow_endpoint_one_entry_per_vertex_and_durations(
    client, json_memory_chatbot_no_llm, logged_in_headers, spy
):
    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    job = (await build_flow(client, flow_id, logged_in_headers))["job_id"]
    evs = await _events(client, job, logged_in_headers)
    ends = [e for e in evs if e["event"] == "end_vertex"]
    assert ends
    built_ids = {e["data"]["build_data"]["id"] for e in ends}
    assert built_ids
    # bidirectional: every ended vertex recorded, every recorded vertex ended
    assert set(spy) == built_ids
    for vid in built_ids:
        assert len(spy[vid]) == 1, (vid, spy[vid])
    for e in ends:
        rd = e["data"]["build_data"]["data"]
        assert rd["duration"]
        td = rd["timedelta"]
        assert td is not None
        assert td >= 0
        # server response duration must contain the recorded library entry
        assert td >= spy[e["data"]["build_data"]["id"]][0]


async def test_build_flow_endpoint_failure(client, json_memory_chatbot_no_llm, logged_in_headers, spy, monkeypatch):
    orig = Vertex.build
    fired = []

    async def boom(self, *a, **k):
        if "ChatOutput" in self.id:
            fired.append(self.id)
            msg = "intentional endpoint build failure"
            raise ValueError(msg)
        return await orig(self, *a, **k)

    monkeypatch.setattr(Vertex, "build", boom)
    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    job = (await build_flow(client, flow_id, logged_in_headers))["job_id"]
    evs = await _events(client, job, logged_in_headers)
    assert fired, "the injected ChatOutput failure never fired - the test would be vacuous"
    assert spy, "expected at least one recorded entry"
    for vid, entries in spy.items():
        assert len(entries) == 1, (vid, entries)
    errs = [e for e in evs if e["event"] == "end_vertex" and e["data"]["build_data"].get("valid") is False]
    assert errs, "expected an error end_vertex event for the failed vertex"
    failed_ids = {e["data"]["build_data"]["id"] for e in errs}
    assert fired[0] in failed_ids
    for e in errs:
        rd = e["data"]["build_data"]["data"]
        td = rd["timedelta"]
        assert td is not None
        assert td >= 0
        # the failed call's call-until-failure entry is still contained in the response region
        assert td >= spy[e["data"]["build_data"]["id"]][0]


async def test_deprecated_vertex_route(client, json_memory_chatbot_no_llm, logged_in_headers, spy):
    flow_id = await create_flow(client, json_memory_chatbot_no_llm, logged_in_headers)
    r = await client.post(f"api/v1/build/{flow_id}/vertices", headers=logged_in_headers)
    assert r.status_code == 200
    body = r.json()
    ids = body["ids"]
    assert ids, "expected at least one vertex id from the deprecated route"
    for vid in ids:
        r = await client.post(f"api/v1/build/{flow_id}/vertices/{vid}", headers=logged_in_headers, json={})
        assert r.status_code == 200
        assert len(spy[vid]) == 1, (vid, spy[vid])
        assert r.json()["data"]["timedelta"] >= spy[vid][0]
    assert set(spy) == set(ids)  # exactly the listed vertices were built, once each


async def test_build_flow_endpoint_frozen_second_run_records_no_new_entries(
    client, json_memory_chatbot_no_llm, logged_in_headers, monkeypatch
):
    """Frozen vertices served from the result cache on a rerun record nothing.

    The endpoint no longer records region-time entries for cache-hit builds; the
    graph layer only records vertex.build calls, and a cache hit makes no call.
    """
    payload = json.loads(json_memory_chatbot_no_llm)
    for node in payload["data"]["nodes"]:
        node["data"]["node"]["frozen"] = True
    flow_id = await create_flow(client, json.dumps(payload), logged_in_headers)
    job = (await build_flow(client, flow_id, logged_in_headers))["job_id"]
    evs = await _events(client, job, logged_in_headers)
    assert [e for e in evs if e["event"] == "end_vertex"], "first run must build vertices"

    calls = collections.defaultdict(list)
    orig = Vertex.add_build_time

    def wrapped(self, t):
        calls[self.id].append(t)
        return orig(self, t)

    monkeypatch.setattr(Vertex, "add_build_time", wrapped)
    job2 = (await build_flow(client, flow_id, logged_in_headers))["job_id"]
    evs2 = await _events(client, job2, logged_in_headers)
    assert [e for e in evs2 if e["event"] == "end_vertex"], "second run must still emit end_vertex events"
    assert not calls, f"frozen cache-hit rerun recorded entries: {dict(calls)}"
