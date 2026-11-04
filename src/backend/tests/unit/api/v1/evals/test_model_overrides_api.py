from uuid import uuid4

from langflow.services.evaluations import runner
from langflow.services.evaluations.row_runner import RowExecution

from .conftest import create_dataset, load_flow_data, wait_for_run

GPT = [{"name": "gpt-4o", "provider": "OpenAI", "metadata": {}}]
MINI = [{"name": "gpt-4o-mini", "provider": "OpenAI", "metadata": {}}]


def _flow_with_model_picker() -> tuple[dict, str]:
    """The echo flow with a model picker on its input node; the runner is stubbed, so no model is called."""
    data = load_flow_data("chat_echo_no_llm.json")
    node = next(node for node in data["nodes"] if node["data"]["type"] == "ChatInput")
    node["data"]["node"]["template"]["model"] = {"type": "model", "display_name": "Language Model", "value": GPT}
    return data, node["data"]["id"]


async def _create_flow(client, headers) -> tuple[dict, str]:
    data, node_id = _flow_with_model_picker()
    response = await client.post("api/v1/flows/", json={"name": "Picker", "data": data}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json(), node_id


def _capture_graphs(captured: list[dict]):
    async def fake(**kwargs):
        captured.append(kwargs["graph_data"])
        return RowExecution(
            actual=kwargs["input_text"], error=None, duration_ms=1, tokens=None, cost=None, trace_id="t"
        )

    return fake


def _picker_value(graph_data: dict, node_id: str) -> list[dict]:
    node = next(node for node in graph_data["nodes"] if node["data"]["id"] == node_id)
    return node["data"]["node"]["template"]["model"]["value"]


class TestModelOverrides:
    async def test_should_list_the_flow_model_pickers_in_the_check(self, client, logged_in_headers):
        flow, node_id = await _create_flow(client, logged_in_headers)

        response = await client.get(
            "api/v1/evaluations/check", params={"flow_id": flow["id"]}, headers=logged_in_headers
        )

        assert response.status_code == 200
        pickers = response.json()["model_pickers"]
        assert [(p["node_id"], p["field"], p["model_type"]) for p in pickers] == [(node_id, "model", "language")]
        assert pickers[0]["value"] == GPT

    async def test_should_run_with_the_swapped_model_and_keep_the_flow_unchanged(
        self, client, logged_in_headers, monkeypatch
    ):
        captured: list[dict] = []
        monkeypatch.setattr(runner, "execute_row", _capture_graphs(captured))
        flow, node_id = await _create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "swap", [("a", "a"), ("b", "b")])
        override = {"node_id": node_id, "field": "model", "value": MINI}

        started = await client.post(
            "api/v1/evaluations",
            params={"run": True},
            json={
                "flow_id": flow["id"],
                "dataset_id": dataset["id"],
                "scorers": [{"type": "exact_match", "name": "exact"}],
                "model_overrides": [override],
            },
            headers=logged_in_headers,
        )

        assert started.status_code == 201, started.text
        run = await wait_for_run(client, logged_in_headers, started.json()["id"])
        assert run["status"] == "completed"
        assert run["config"]["model_overrides"] == [override]
        assert len(captured) == 2
        assert all(_picker_value(graph, node_id) == MINI for graph in captured)
        saved = (await client.get(f"api/v1/flows/{flow['id']}", headers=logged_in_headers)).json()
        assert _picker_value(saved["data"], node_id) == GPT

    async def test_should_refuse_an_override_for_a_component_not_in_the_flow(self, client, logged_in_headers):
        flow, _ = await _create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "missing", [("a", "a")])
        created = await client.post(
            "api/v1/evaluations",
            json={
                "flow_id": flow["id"],
                "dataset_id": dataset["id"],
                "scorers": [{"type": "exact_match", "name": "x"}],
            },
            headers=logged_in_headers,
        )
        assert created.status_code == 201, created.text

        response = await client.post(
            f"api/v1/evaluations/{created.json()['id']}/runs",
            json={"model_overrides": [{"node_id": "Agent-404", "field": "model", "value": MINI}]},
            headers=logged_in_headers,
        )

        assert response.status_code == 422
        runs = await client.get(f"api/v1/evaluations/{created.json()['id']}/runs", headers=logged_in_headers)
        assert runs.json()["total"] == 0

    async def test_should_reject_the_same_field_overridden_twice(self, client, logged_in_headers):
        flow, node_id = await _create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "twice", [("a", "a")])
        override = {"node_id": node_id, "field": "model", "value": MINI}

        response = await client.post(
            "api/v1/evaluations/estimate",
            json={"flow_id": flow["id"], "dataset_id": dataset["id"], "model_overrides": [override, override]},
            headers=logged_in_headers,
        )

        assert response.status_code == 422

    async def test_should_estimate_with_the_swapped_model(self, client, logged_in_headers):
        flow, node_id = await _create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "estimate", [("a", "a")])
        body = {"flow_id": flow["id"], "dataset_id": dataset["id"]}

        plain = await client.post("api/v1/evaluations/estimate", json=body, headers=logged_in_headers)
        swapped = await client.post(
            "api/v1/evaluations/estimate",
            json={**body, "model_overrides": [{"node_id": node_id, "field": "model", "value": MINI}]},
            headers=logged_in_headers,
        )

        assert plain.status_code == swapped.status_code == 200
        assert swapped.json()["llm_calls"] == plain.json()["llm_calls"] == 1


class TestUnsetModelPicker:
    async def test_should_refuse_a_run_until_a_model_is_chosen_for_an_empty_picker(
        self, client, logged_in_headers, monkeypatch
    ):
        captured: list[dict] = []
        monkeypatch.setattr(runner, "execute_row", _capture_graphs(captured))
        data, node_id = _flow_with_model_picker()
        picker = next(n for n in data["nodes"] if n["data"]["id"] == node_id)["data"]["node"]["template"]["model"]
        picker.update(value=[], required=True)
        flow = await client.post("api/v1/flows/", json={"name": "Unset", "data": data}, headers=logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "unset", [("a", "a")])
        body = {
            "flow_id": flow.json()["id"],
            "dataset_id": dataset["id"],
            "scorers": [{"type": "exact_match", "name": "exact"}],
        }

        check = await client.get(
            "api/v1/evaluations/check", params={"flow_id": flow.json()["id"]}, headers=logged_in_headers
        )
        refused = await client.post("api/v1/evaluations", params={"run": True}, json=body, headers=logged_in_headers)
        started = await client.post(
            "api/v1/evaluations",
            params={"run": True},
            json={**body, "model_overrides": [{"node_id": node_id, "field": "model", "value": MINI}]},
            headers=logged_in_headers,
        )

        assert [p["value"] for p in check.json()["model_pickers"]] == [[]]
        assert refused.status_code == 422
        assert "Choose a model" in refused.text
        assert started.status_code == 201, started.text
        run = await wait_for_run(client, logged_in_headers, started.json()["id"])
        assert run["status"] == "completed"
        assert _picker_value(captured[0], node_id) == MINI


class TestHistoricalVersion:
    async def test_should_estimate_and_check_the_chosen_version_not_the_draft(self, client, logged_in_headers):
        flow, _ = await _create_flow(client, logged_in_headers)
        saved = await client.post(
            f"api/v1/flows/{flow['id']}/versions/", json={"description": "calls a model"}, headers=logged_in_headers
        )
        assert saved.status_code == 201, saved.text
        version_id = saved.json()["id"]
        # The draft no longer calls a model; the saved version still does.
        patched = await client.patch(
            f"api/v1/flows/{flow['id']}",
            json={"data": load_flow_data("chat_echo_no_llm.json")},
            headers=logged_in_headers,
        )
        assert patched.status_code == 200, patched.text
        dataset = await create_dataset(client, logged_in_headers, "history-estimate", [("a", "a")])
        body = {"flow_id": flow["id"], "dataset_id": dataset["id"]}

        draft = await client.post("api/v1/evaluations/estimate", json=body, headers=logged_in_headers)
        pinned = await client.post(
            "api/v1/evaluations/estimate", json={**body, "flow_version_id": version_id}, headers=logged_in_headers
        )
        draft_check = await client.get(
            "api/v1/evaluations/check", params={"flow_id": flow["id"]}, headers=logged_in_headers
        )
        pinned_check = await client.get(
            "api/v1/evaluations/check",
            params={"flow_id": flow["id"], "flow_version_id": version_id},
            headers=logged_in_headers,
        )

        assert draft.json()["llm_calls"] == 0
        assert pinned.json()["llm_calls"] == 1
        assert draft_check.json()["model_pickers"] == []
        assert len(pinned_check.json()["model_pickers"]) == 1

    async def test_should_refuse_an_estimate_for_a_version_of_another_flow(self, client, logged_in_headers):
        flow, _ = await _create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "history-404", [("a", "a")])

        response = await client.post(
            "api/v1/evaluations/estimate",
            json={"flow_id": flow["id"], "dataset_id": dataset["id"], "flow_version_id": str(uuid4())},
            headers=logged_in_headers,
        )

        assert response.status_code == 404


class TestHistoryBasis:
    async def test_should_not_lend_an_overridden_runs_usage_to_the_flows_own_model(
        self, client, logged_in_headers, monkeypatch
    ):
        async def spending_row(**kwargs):
            return RowExecution(
                actual=kwargs["input_text"], error=None, duration_ms=1, tokens=100, cost=0.001, trace_id="t"
            )

        monkeypatch.setattr(runner, "execute_row", spending_row)
        flow, node_id = await _create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "history-override", [("a", "a"), ("b", "b")])
        mini = [{"node_id": node_id, "field": "model", "value": MINI}]
        started = await client.post(
            "api/v1/evaluations",
            params={"run": True},
            json={
                "flow_id": flow["id"],
                "dataset_id": dataset["id"],
                "scorers": [{"type": "exact_match", "name": "exact"}],
                "model_overrides": mini,
            },
            headers=logged_in_headers,
        )
        assert started.status_code == 201, started.text
        assert (await wait_for_run(client, logged_in_headers, started.json()["id"]))["status"] == "completed"
        body = {"flow_id": flow["id"], "dataset_id": dataset["id"]}

        own_model = await client.post("api/v1/evaluations/estimate", json=body, headers=logged_in_headers)
        same_override = await client.post(
            "api/v1/evaluations/estimate", json={**body, "model_overrides": mini}, headers=logged_in_headers
        )

        assert own_model.json()["basis"] == "model"
        assert same_override.json()["basis"] == "history"
