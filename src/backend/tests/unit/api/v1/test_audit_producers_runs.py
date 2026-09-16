"""Every flow run records who ran it, from where, and whether it worked; never what it received or returned."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import status
from langflow.services.deps import get_settings_service, session_scope

from .audit_helpers import enabled_audit, events_by_user, events_for, login, make_user

pytestmark = pytest.mark.usefixtures("audit_on")

PRIVATE_INPUT = "customer-ssn-123-45-6789"
STARTER_PROJECTS = Path(__file__).parents[4] / "base" / "langflow" / "initial_setup" / "starter_projects"


@pytest.fixture
def audit_on(client):  # noqa: ARG001
    yield from enabled_audit()


async def _run_events(flow_id, *, count: int = 1, timeout: float = 30.0) -> list:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        runs = [event for event in await events_for(flow_id) if event.operation == "run"]
        if len(runs) >= count or asyncio.get_running_loop().time() > deadline:
            return runs
        await asyncio.sleep(0.2)


async def _drain_build(client, flow_id, headers, body=None) -> None:
    started = await client.post(f"api/v1/build/{flow_id}/flow", json=body or {}, headers=headers)
    assert started.status_code == status.HTTP_200_OK, started.text
    events = await client.get(
        f"api/v1/build/{started.json()['job_id']}/events", headers={**headers, "Accept": "application/x-ndjson"}
    )
    assert events.status_code == status.HTTP_200_OK


async def test_an_api_run_records_its_key_and_outcome_but_not_its_input(client, simple_api_test, created_api_key):
    response = await client.post(
        f"api/v1/run/{simple_api_test['id']}",
        headers={"x-api-key": created_api_key.api_key},
        json={"input_value": PRIVATE_INPUT},
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    [run] = await _run_events(simple_api_test["id"])
    assert (run.action, run.operation, run.event_type, run.result, run.error_code) == (
        "flow:execute",
        "run",
        "action",
        "succeeded",
        None,
    )
    assert (run.actor_type, run.actor_id, run.user_id) == ("api_key", created_api_key.id, created_api_key.user_id)
    assert run.resource_name == simple_api_test["name"]
    assert set(run.details) == {"schema_version", "run"}
    assert run.details["run"]["trigger"] == "v1_run"
    assert run.details["run"]["duration_ms"] >= 0
    assert PRIVATE_INPUT not in json.dumps(run.details)


async def test_a_streamed_run_records_exactly_one_event(client, simple_api_test, created_api_key):
    response = await client.post(
        f"api/v1/run/{simple_api_test['id']}?stream=true",
        headers={"x-api-key": created_api_key.api_key},
        json={"input_value": "hello"},
    )

    assert response.status_code == status.HTTP_200_OK
    runs = await _run_events(simple_api_test["id"])
    await asyncio.sleep(0.5)
    assert len(await _run_events(simple_api_test["id"])) == len(runs) == 1
    assert runs[0].result == "succeeded"


async def test_a_run_refused_for_its_input_is_a_failure_blamed_on_the_request(client, simple_api_test, created_api_key):
    response = await client.post(
        f"api/v1/run/{simple_api_test['id']}",
        headers={"x-api-key": created_api_key.api_key},
        json={"input_type": "chat", "input_value": "a", "tweaks": {"Chat Input": {"input_value": "b"}}},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    [run] = await _run_events(simple_api_test["id"])
    assert (run.result, run.error_code, set(run.details)) == ("failed", "INVALID_CONTENT", {"schema_version", "run"})


async def test_a_playground_build_that_succeeds_records_the_user_and_trigger(
    client, json_memory_chatbot_no_llm, logged_in_headers, active_user
):
    created = await client.post("api/v1/flows/", json=json.loads(json_memory_chatbot_no_llm), headers=logged_in_headers)
    flow_id = created.json()["id"]

    await _drain_build(client, flow_id, logged_in_headers)

    [run] = await _run_events(flow_id)
    assert (run.result, run.actor_type, run.user_id) == ("succeeded", "user", active_user.id)
    assert run.details["run"]["trigger"] == "interactive_chat"
    assert run.resource_name == created.json()["name"]


async def test_a_build_whose_component_fails_records_a_failed_run(client, logged_in_headers):
    agent = json.loads((STARTER_PROJECTS / "Simple Agent.json").read_text(encoding="utf-8"))
    created = await client.post(
        "api/v1/flows/", json={"name": f"agent-{uuid4().hex}", "data": agent["data"]}, headers=logged_in_headers
    )
    flow_id = created.json()["id"]

    await _drain_build(client, flow_id, logged_in_headers)

    [run] = await _run_events(flow_id)
    assert (run.event_type, run.result, run.error_code) == ("action", "failed", "FLOW_EXECUTION_FAILED")
    assert set(run.details) == {"schema_version", "run"}
    assert run.resource_name == created.json()["name"]


async def test_a_webhook_run_is_attributed_to_the_webhook_trigger(client, added_flow_webhook_test, created_api_key):
    response = await client.post(
        f"api/v1/webhook/{added_flow_webhook_test['id']}",
        headers={"x-api-key": created_api_key.api_key},
        json={"payload": PRIVATE_INPUT},
    )

    assert response.status_code == status.HTTP_202_ACCEPTED, response.text
    [run] = await _run_events(added_flow_webhook_test["id"])
    assert run.details["run"]["trigger"] == "webhook"
    assert PRIVATE_INPUT not in json.dumps(run.details)


async def test_a_refused_run_records_one_denial_and_no_outcome(client):
    from tests.unit.services.authorization._policy_double import create_user_share, install_policy_authz

    alice_id, alice_name = await make_user("alice")
    bob_id, bob_name = await make_user("bob")
    alice, bob = await login(client, alice_name), await login(client, bob_name)
    flow = await client.post("api/v1/flows/", json={"name": f"f-{uuid4().hex}", "data": {}}, headers=alice)
    flow_id = flow.json()["id"]
    async with session_scope() as session:
        await create_user_share(
            session,
            resource_type="flow",
            resource_id=UUID(flow_id),
            target_user_id=bob_id,
            permission_level="read",
            created_by=alice_id,
        )

    with install_policy_authz(get_settings_service()):
        response = await client.post(f"api/v1/build/{flow_id}/flow", json={}, headers=bob)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    runs = [event for event in await events_by_user(bob_id) if event.operation == "run"]
    assert [(event.event_type, event.result, event.error_code) for event in runs] == [
        ("authz", "deny", "PERMISSION_DENIED")
    ]


async def test_nothing_is_recorded_for_a_run_when_auditing_is_off(client, simple_api_test, created_api_key):
    get_settings_service().settings.audit_enabled = False

    response = await client.post(
        f"api/v1/run/{simple_api_test['id']}", headers={"x-api-key": created_api_key.api_key}, json={}
    )

    assert response.status_code == status.HTTP_200_OK
    await asyncio.sleep(0.5)
    assert await _run_events(simple_api_test["id"], timeout=0) == []
