import asyncio

import pytest
from langflow.services.deps import get_settings_service
from langflow.services.evaluations import runner
from langflow.services.evaluations.row_runner import RowExecution

from .conftest import TERMINAL, create_dataset, create_evaluation, load_flow_data

GPT = [{"name": "gpt-4o", "provider": "OpenAI", "metadata": {}}]
MINI = [{"name": "gpt-4o-mini", "provider": "OpenAI", "metadata": {}}]
NANO = [{"name": "gpt-4.1-nano", "provider": "OpenAI", "metadata": {}}]
EDITED = [{"name": "edited-after-start", "provider": "OpenAI", "metadata": {}}]


async def _create_flow(client, headers) -> tuple[dict, str]:
    data = load_flow_data("chat_echo_no_llm.json")
    node = next(node for node in data["nodes"] if node["data"]["type"] == "ChatInput")
    node["data"]["node"]["template"]["model"] = {"type": "model", "display_name": "Language Model", "value": GPT}
    response = await client.post("api/v1/flows/", json={"name": "Compare", "data": data}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json(), node["data"]["id"]


def _picker(graph_data: dict, node_id: str) -> str:
    node = next(node for node in graph_data["nodes"] if node["data"]["id"] == node_id)
    return node["data"]["node"]["template"]["model"]["value"][0]["name"]


def _variants(node_id: str, *models: list[dict] | None) -> list[dict]:
    return [
        {"model_overrides": [] if model is None else [{"node_id": node_id, "field": "model", "value": model}]}
        for model in models
    ]


async def _runs(client, headers, evaluation_id: str) -> list[dict]:
    response = await client.get(f"api/v1/evaluations/{evaluation_id}/runs", headers=headers)
    assert response.status_code == 200, response.text
    return sorted(response.json()["items"], key=lambda run: run["created_at"])


async def _wait_for_comparison(client, headers, evaluation_id: str, expected: int, timeout: float = 60.0) -> list[dict]:
    """Every run of the evaluation once ``expected`` exist and none is active, or once nothing moved for a while."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    settled_since: float | None = None
    while True:
        runs = await _runs(client, headers, evaluation_id)
        idle = all(run["status"] in TERMINAL for run in runs)
        if idle and len(runs) >= expected:
            return runs
        settled_since = (settled_since or loop.time()) if idle else None
        # A chain that stopped early never reaches ``expected``: give the next start a moment, then return.
        if settled_since is not None and loop.time() - settled_since > 1.5:
            return runs
        if loop.time() > deadline:
            pytest.fail(f"comparison did not finish: {runs}")
        await asyncio.sleep(0.2)


def _recording_execute_row(
    seen: list[tuple[str, str]], node_id: str, *, delay: float = 0.0, on_first=None, overlap: list | None = None
):
    active: set[str] = set()
    overlap = overlap if overlap is not None else []

    async def fake(**kwargs):
        run_id = str(kwargs["run_id"])
        active.add(run_id)
        if len(active) > 1:
            overlap.append(set(active))
        if on_first is not None and not seen:
            await on_first()
        seen.append((run_id, _picker(kwargs["graph_data"], node_id)))
        await asyncio.sleep(delay)
        active.discard(run_id)
        return RowExecution(
            actual=kwargs["input_text"], error=None, duration_ms=5, tokens=None, cost=None, trace_id="t"
        )

    return fake


async def _start_comparison(client, headers, flow_id: str, dataset_id: str, variants: list[dict]):
    return await client.post(
        "api/v1/evaluations",
        params={"run": True},
        json={
            "flow_id": flow_id,
            "dataset_id": dataset_id,
            "scorers": [{"type": "exact_match", "name": "exact"}],
            "variants": variants,
        },
        headers=headers,
    )


class TestModelComparison:
    async def test_should_run_each_variant_in_turn_on_one_flow_version(self, client, logged_in_headers, monkeypatch):
        seen: list[tuple[str, str]] = []
        overlap: list[set[str]] = []
        flow, node_id = await _create_flow(client, logged_in_headers)
        monkeypatch.setattr(runner, "execute_row", _recording_execute_row(seen, node_id, delay=0.01, overlap=overlap))
        dataset = await create_dataset(client, logged_in_headers, "cmp", [(f"q{i}", f"q{i}") for i in range(4)])

        started = await _start_comparison(
            client, logged_in_headers, flow["id"], dataset["id"], _variants(node_id, None, MINI, NANO)
        )

        assert started.status_code == 201, started.text
        runs = await _wait_for_comparison(client, logged_in_headers, started.json()["evaluation_id"], 3)
        assert [run["status"] for run in runs] == ["completed"] * 3
        assert runs[0]["id"] == started.json()["id"]
        comparisons = [run["config"]["comparison"] for run in runs]
        assert len({c["id"] for c in comparisons}) == 1
        assert [c["index"] for c in comparisons] == [0, 1, 2]
        assert len({run["flow_version_id"] for run in runs}) == 1
        models_by_run = {run["id"]: {model for run_id, model in seen if run_id == run["id"]} for run in runs}
        assert [models_by_run[run["id"]] for run in runs] == [{"gpt-4o"}, {"gpt-4o-mini"}, {"gpt-4.1-nano"}]
        assert overlap == []
        assert all(run["completed_items"] == 4 for run in runs)

    async def test_should_keep_the_pinned_version_when_the_flow_changes_mid_comparison(
        self, client, logged_in_headers, monkeypatch
    ):
        flow, node_id = await _create_flow(client, logged_in_headers)

        async def edit_flow():
            data = load_flow_data("chat_echo_no_llm.json")
            node = next(node for node in data["nodes"] if node["data"]["type"] == "ChatInput")
            node["data"]["node"]["template"]["model"] = {"type": "model", "display_name": "LM", "value": EDITED}
            response = await client.patch(f"api/v1/flows/{flow['id']}", json={"data": data}, headers=logged_in_headers)
            assert response.status_code == 200, response.text

        seen: list[tuple[str, str]] = []
        monkeypatch.setattr(runner, "execute_row", _recording_execute_row(seen, node_id, on_first=edit_flow))
        dataset = await create_dataset(client, logged_in_headers, "pinned", [("a", "a"), ("b", "b")])

        started = await _start_comparison(
            client, logged_in_headers, flow["id"], dataset["id"], _variants(node_id, None, MINI, None)
        )

        assert started.status_code == 201, started.text
        runs = await _wait_for_comparison(client, logged_in_headers, started.json()["evaluation_id"], 3)
        assert len(runs) == 3
        assert {model for _, model in seen} == {"gpt-4o", "gpt-4o-mini"}
        assert len({run["flow_version_id"] for run in runs}) == 1

    async def test_should_stop_the_remaining_variants_when_one_is_cancelled(
        self, client, logged_in_headers, monkeypatch
    ):
        flow, node_id = await _create_flow(client, logged_in_headers)
        monkeypatch.setattr(runner, "execute_row", _recording_execute_row([], node_id, delay=0.3))
        monkeypatch.setattr(get_settings_service().settings, "evals_row_concurrency", 1)
        dataset = await create_dataset(client, logged_in_headers, "stop", [(f"q{i}", None) for i in range(20)])

        started = await _start_comparison(
            client, logged_in_headers, flow["id"], dataset["id"], _variants(node_id, None, MINI, NANO)
        )
        await asyncio.sleep(0.8)
        cancelled = await client.post(
            f"api/v1/evaluation-runs/{started.json()['id']}/cancel", headers=logged_in_headers
        )

        assert cancelled.status_code == 200
        runs = await _wait_for_comparison(client, logged_in_headers, started.json()["evaluation_id"], 3)
        assert [run["status"] for run in runs] == ["cancelled"]

    async def test_should_go_on_after_a_variant_that_stopped_early(self, client, logged_in_headers, monkeypatch):
        flow, node_id = await _create_flow(client, logged_in_headers)

        async def broken_mini(**kwargs):
            if _picker(kwargs["graph_data"], node_id) == "gpt-4o-mini":
                return RowExecution(
                    actual=None, error="model retired", duration_ms=1, tokens=None, cost=None, trace_id="t"
                )
            return RowExecution(
                actual=kwargs["input_text"], error=None, duration_ms=1, tokens=None, cost=None, trace_id="t"
            )

        monkeypatch.setattr(runner, "execute_row", broken_mini)
        monkeypatch.setattr(get_settings_service().settings, "evals_row_concurrency", 1)
        dataset = await create_dataset(client, logged_in_headers, "retired", [(f"q{i}", f"q{i}") for i in range(10)])

        started = await _start_comparison(
            client, logged_in_headers, flow["id"], dataset["id"], _variants(node_id, MINI, None)
        )

        runs = await _wait_for_comparison(client, logged_in_headers, started.json()["evaluation_id"], 2)
        assert [run["status"] for run in runs] == ["failed", "completed"]
        assert "model retired" in runs[0]["error"]
        assert runs[1]["passed_items"] == 10

    async def test_should_stop_quietly_when_the_flow_is_deleted_mid_comparison(
        self, client, logged_in_headers, monkeypatch
    ):
        flow, node_id = await _create_flow(client, logged_in_headers)

        async def delete_flow():
            response = await client.delete(f"api/v1/flows/{flow['id']}", headers=logged_in_headers)
            assert response.status_code == 200, response.text

        monkeypatch.setattr(runner, "execute_row", _recording_execute_row([], node_id, on_first=delete_flow))
        dataset = await create_dataset(client, logged_in_headers, "gone", [("a", "a")])

        started = await _start_comparison(
            client, logged_in_headers, flow["id"], dataset["id"], _variants(node_id, None, MINI)
        )

        assert started.status_code == 201, started.text
        runs = await _wait_for_comparison(client, logged_in_headers, started.json()["evaluation_id"], 2)
        assert len(runs) == 1

    async def test_should_stop_when_the_scoring_changes_mid_comparison(self, client, logged_in_headers, monkeypatch):
        flow, node_id = await _create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "rescored", [("a", "a"), ("b", "b")])
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])

        async def rescore():
            response = await client.patch(
                f"api/v1/evaluations/{evaluation['id']}",
                json={"scorers": [{"type": "contains", "name": "contains"}]},
                headers=logged_in_headers,
            )
            assert response.status_code == 200, response.text

        monkeypatch.setattr(runner, "execute_row", _recording_execute_row([], node_id, on_first=rescore))

        response = await client.post(
            f"api/v1/evaluations/{evaluation['id']}/runs",
            json={"variants": _variants(node_id, None, MINI)},
            headers=logged_in_headers,
        )

        assert response.status_code == 202, response.text
        runs = await _wait_for_comparison(client, logged_in_headers, evaluation["id"], 2)
        assert [run["config"]["scorers"][0]["name"] for run in runs] == ["exact"]

    async def test_should_refuse_a_later_variant_the_flow_cannot_run_before_spending(
        self, client, logged_in_headers, monkeypatch
    ):
        calls: list[dict] = []

        async def fake(**kwargs):
            calls.append(kwargs)
            return RowExecution(actual="x", error=None, duration_ms=1, tokens=None, cost=None, trace_id="t")

        monkeypatch.setattr(runner, "execute_row", fake)
        flow, node_id = await _create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "bad", [("a", "a")])
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])
        variants = [
            *_variants(node_id, None),
            {"model_overrides": [{"node_id": "Agent-404", "field": "model", "value": MINI}]},
        ]

        response = await client.post(
            f"api/v1/evaluations/{evaluation['id']}/runs", json={"variants": variants}, headers=logged_in_headers
        )

        assert response.status_code == 422
        assert "Agent-404" in response.text
        assert (await _runs(client, logged_in_headers, evaluation["id"])) == []
        assert calls == []

    @pytest.mark.parametrize(
        "body",
        [
            pytest.param(
                lambda n: {
                    "variants": _variants(n, None, MINI),
                    "model_overrides": _variants(n, MINI)[0]["model_overrides"],
                },
                id="both",
            ),
            pytest.param(lambda n: {"variants": _variants(n, *([MINI] * 9))}, id="too-many"),
            pytest.param(
                lambda n: {
                    "variants": [{"model_overrides": _variants(n, MINI)[0]["model_overrides"] * 2}, *_variants(n, None)]
                },
                id="field-twice",
            ),
        ],
    )
    async def test_should_reject_malformed_variants(self, client, logged_in_headers, body):
        flow, node_id = await _create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "malformed", [("a", "a")])
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])

        response = await client.post(
            f"api/v1/evaluations/{evaluation['id']}/runs", json=body(node_id), headers=logged_in_headers
        )

        assert response.status_code == 422

    async def test_should_run_once_without_a_comparison_for_a_single_variant(
        self, client, logged_in_headers, monkeypatch
    ):
        seen: list[tuple[str, str]] = []
        flow, node_id = await _create_flow(client, logged_in_headers)
        monkeypatch.setattr(runner, "execute_row", _recording_execute_row(seen, node_id))
        dataset = await create_dataset(client, logged_in_headers, "single", [("a", "a")])

        started = await _start_comparison(
            client, logged_in_headers, flow["id"], dataset["id"], _variants(node_id, MINI)
        )

        assert started.status_code == 201, started.text
        runs = await _wait_for_comparison(client, logged_in_headers, started.json()["evaluation_id"], 1)
        assert len(runs) == 1
        assert "comparison" not in runs[0]["config"]
        assert seen[0][1] == "gpt-4o-mini"

    async def test_should_estimate_every_variant_together(self, client, logged_in_headers):
        flow, node_id = await _create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "est", [("a", "a"), ("b", "b")])
        body = {"flow_id": flow["id"], "dataset_id": dataset["id"]}

        single = await client.post("api/v1/evaluations/estimate", json=body, headers=logged_in_headers)
        triple = await client.post(
            "api/v1/evaluations/estimate",
            json={**body, "variants": _variants(node_id, None, MINI, NANO)},
            headers=logged_in_headers,
        )

        assert single.status_code == triple.status_code == 200
        assert single.json()["variants"] == 1
        assert triple.json()["variants"] == 3
        assert triple.json()["items"] == single.json()["items"] == 2
        assert triple.json()["llm_calls"] == 3 * single.json()["llm_calls"]
        assert triple.json()["tokens_high"] >= 3 * single.json()["tokens_low"]
