"""A decision flow's life through the API: save, export, import, then run from the API and the editor.

Uses the shipped Support Ticket Routing starter. Only the provider's HTTP endpoint is faked, so the server's
credential resolution, request-scoped keys and graph engine run as they do for a user.
"""

import json
from pathlib import Path

import httpx
import pytest
from httpx import AsyncClient, codes
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from lfx.base.models.decisions import providers

from tests.unit.build_utils import build_flow, get_build_events

STARTER = Path(__file__).parents[5] / "backend/base/langflow/initial_setup/starter_projects/Support Ticket Routing.json"
ROUTER = "SmartRouter-4d826"
ROUTE_OUTPUTS = {"Billing": "ChatOutput-27006", "Technical Support": "ChatOutput-450f9", "Sales": "ChatOutput-f0150"}
ELSE_OUTPUT = "ChatOutput-3cacd"
DECISION_FIELDS = ("routing_mode", "decision_model", "decision_kind", "decision_question", "minimum_probability")
DECISION_ONLY_FIELDS = (
    *DECISION_FIELDS,
    "evaluation_error_action",
    "score_levels",
    "last_level_number",
    "yes_description",
    "no_description",
    "yes_message",
    "no_message",
    "yes_minimum_probability",
    "no_minimum_probability",
)


class FakeTypeSafe:
    """TypeSafe's documented Choice answer, putting ``probability`` on the first route."""

    def __init__(self):
        self.calls: list[dict] = []
        self.probability = 0.9

    def post(self, url, *, json, headers, **_kwargs):
        self.calls.append({"url": url, "authorization": headers["Authorization"], "payload": json})
        route_ids = list(json["questions"]["decision"]["criteria"])
        rest = (1 - self.probability) / (len(route_ids) - 1)
        probabilities = {route_id: self.probability if i == 0 else rest for i, route_id in enumerate(route_ids)}
        body = {"model": "jev-1.13.0", "answers": {"decision": {"type": "choice", "probabilities": probabilities}}}
        return httpx.Response(200, json=body, request=httpx.Request("POST", url))


@pytest.fixture
def typesafe(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "typesafe-server-key")
    fake = FakeTypeSafe()
    monkeypatch.setattr(providers, "provider_safe_httpx_post", fake.post)
    return fake


@pytest.fixture
def starter():
    return json.loads(STARTER.read_text(encoding="utf-8"))


def _router(flow_data):
    return next(node for node in flow_data["nodes"] if node["id"] == ROUTER)


async def _save(client, flow, headers, name="Support Ticket Routing"):
    response = await client.post("api/v1/flows/", json={"name": name, "data": flow["data"]}, headers=headers)
    assert response.status_code == codes.CREATED, response.text
    return response.json()


async def _export_and_import(client, flow_id, headers):
    downloaded = await client.post(
        "api/v1/flows/download/", content=json.dumps([flow_id]), headers={**headers, "Content-Type": "application/json"}
    )
    assert downloaded.status_code == codes.OK, downloaded.text
    # Import into a workspace without the original, so the exported file alone has to carry the flow.
    deleted = await client.delete(f"api/v1/flows/{flow_id}", headers=headers)
    assert deleted.status_code == codes.OK, deleted.text
    uploaded = await client.post(
        "api/v1/flows/upload/",
        files={"file": ("Support Ticket Routing.json", downloaded.content, "application/json")},
        headers=headers,
    )
    assert uploaded.status_code == codes.CREATED, uploaded.text
    (imported,) = uploaded.json()
    return imported


async def _run(client, flow_id, api_key, *, headers=None, message="I was charged twice for my plan."):
    return await client.post(
        f"/api/v1/run/{flow_id}",
        json={"input_value": message, "input_type": "chat", "output_type": "chat"},
        headers={"x-api-key": api_key, **(headers or {})},
    )


def _ran_outputs(run_response):
    return {output["component_id"] for output in run_response.json()["outputs"][0]["outputs"]}


@pytest.mark.usefixtures("active_user")
async def test_a_decision_flow_survives_export_and_import_and_runs(
    client: AsyncClient, logged_in_headers, created_api_key, typesafe, starter
):
    saved = await _save(client, starter, logged_in_headers)

    imported = await _export_and_import(client, saved["id"], logged_in_headers)

    saved_router, imported_router = _router(saved["data"]), _router(imported["data"])
    for name in (*DECISION_FIELDS, "routes", "evaluation_error_action", "enable_else_output"):
        assert (
            imported_router["data"]["node"]["template"][name]["value"]
            == (saved_router["data"]["node"]["template"][name]["value"])
        ), name
    # Route identity is what decisions activate, so it must survive the round trip with the edges.
    assert [output["name"] for output in imported_router["data"]["node"]["outputs"]] == [
        output["name"] for output in saved_router["data"]["node"]["outputs"]
    ]

    response = await _run(client, imported["id"], created_api_key.api_key)

    assert response.status_code == codes.OK, response.text
    assert _ran_outputs(response) == {ROUTE_OUTPUTS["Billing"]}
    (call,) = typesafe.calls
    assert call["authorization"] == "Bearer typesafe-server-key"
    assert list(call["payload"]["questions"]["decision"]["criteria"]) == [
        "category_1_result",
        "category_2_result",
        "category_3_result",
    ]


@pytest.mark.usefixtures("active_user")
async def test_an_unsure_answer_reaches_else_through_the_api(
    client: AsyncClient, logged_in_headers, created_api_key, typesafe, starter
):
    typesafe.probability = 0.5
    saved = await _save(client, starter, logged_in_headers)

    response = await _run(client, saved["id"], created_api_key.api_key)

    assert response.status_code == codes.OK, response.text
    assert _ran_outputs(response) == {ELSE_OUTPUT}


@pytest.mark.usefixtures("active_user")
async def test_a_callers_request_key_is_used_and_a_missing_key_stops_before_inference(
    client: AsyncClient, logged_in_headers, created_api_key, typesafe, starter, monkeypatch
):
    monkeypatch.delenv("TYPESAFE_API_KEY")
    saved = await _save(client, starter, logged_in_headers)

    refused = await _run(client, saved["id"], created_api_key.api_key)
    assert typesafe.calls == []
    assert "API key" in refused.text

    response = await _run(
        client,
        saved["id"],
        created_api_key.api_key,
        headers={"X-LANGFLOW-GLOBAL-VAR-TYPESAFE_API_KEY": "typesafe-caller-key"},
    )

    assert response.status_code == codes.OK, response.text
    assert _ran_outputs(response) == {ROUTE_OUTPUTS["Billing"]}
    assert [call["authorization"] for call in typesafe.calls] == ["Bearer typesafe-caller-key"]


async def _built_vertices(client, flow_id, headers):
    job = await build_flow(client, flow_id, headers, json={"inputs": {"input_value": "I was charged twice."}})
    events = await get_build_events(client, job["job_id"], headers)
    built, errors = set(), []
    for line in events.text.splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("event") == "end_vertex":
            build_data = event["data"]["build_data"]
            if build_data.get("valid"):
                built.add(build_data["id"])
            else:
                errors.append(build_data)
        elif event.get("event") == "error":
            errors.append(event["data"])
    return built, errors


@pytest.mark.usefixtures("active_user")
async def test_the_editor_build_runs_only_the_chosen_branch(client: AsyncClient, logged_in_headers, typesafe, starter):
    saved = await _save(client, starter, logged_in_headers)

    built, errors = await _built_vertices(client, saved["id"], logged_in_headers)

    assert errors == []
    assert ROUTER in built
    assert ROUTE_OUTPUTS["Billing"] in built
    assert built.isdisjoint({ROUTE_OUTPUTS["Technical Support"], ROUTE_OUTPUTS["Sales"], ELSE_OUTPUT})
    assert len(typesafe.calls) == 1


@pytest.mark.usefixtures("active_user")
async def test_a_router_saved_before_decision_mode_still_routes_with_its_language_model(
    client: AsyncClient, logged_in_headers, created_api_key, typesafe, starter, monkeypatch
):
    """A Smart Router saved by 1.13 has none of the decision fields; it keeps routing with its LLM."""
    template = _router(starter["data"])["data"]["node"]["template"]
    for name in DECISION_ONLY_FIELDS:
        template.pop(name, None)
    template["model"]["value"] = [{"provider": "OpenAI", "name": "gpt-4o", "metadata": {}}]
    llm = FakeListChatModel(responses=["Technical Support"])
    monkeypatch.setattr("lfx.base.models.unified_models.get_llm", lambda **_: llm)
    monkeypatch.setattr("lfx.components.llm_operations.llm_conditional_router.get_llm", lambda **_: llm)
    saved = await _save(client, starter, logged_in_headers, name="Smart Router from 1.13")

    response = await _run(client, saved["id"], created_api_key.api_key)

    assert response.status_code == codes.OK, response.text
    assert _ran_outputs(response) == {ROUTE_OUTPUTS["Technical Support"]}
    assert typesafe.calls == []
