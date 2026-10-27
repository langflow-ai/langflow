from langflow.services.deps import get_settings_service
from langflow.services.evaluations import runner
from langflow.services.evaluations.row_runner import RowExecution
from langflow.services.evaluations.scorers.types import ScoreResult

from .conftest import create_dataset, create_evaluation, create_flow, eval_message_count, start_run, wait_for_run


class TestStress:
    async def test_should_run_300_rows_with_bounded_concurrency(self, client, logged_in_headers, monkeypatch):
        in_flight = 0
        peak = 0
        real_execute = runner.execute_row

        async def counting(**kwargs):
            nonlocal in_flight, peak
            in_flight += 1
            peak = max(peak, in_flight)
            try:
                return await real_execute(**kwargs)
            finally:
                in_flight -= 1

        monkeypatch.setattr(runner, "execute_row", counting)
        monkeypatch.setattr(get_settings_service().settings, "evals_row_concurrency", 3)
        flow = await create_flow(client, logged_in_headers)
        rows = [(f"question {i}", f"question {i}") for i in range(300)]
        dataset = await create_dataset(client, logged_in_headers, "stress", rows)
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])
        run = await wait_for_run(
            client, logged_in_headers, (await start_run(client, logged_in_headers, evaluation["id"]))["id"], timeout=300
        )
        assert run["status"] == "completed", run
        assert (run["completed_items"], run["failed_items"], run["passed_items"]) == (300, 0, 300)
        assert 1 < peak <= 3
        page = (
            await client.get(
                f"api/v1/evaluation-runs/{run['id']}/results",
                params={"page": 2, "size": 200},
                headers=logged_in_headers,
            )
        ).json()
        assert page["total"] == 300
        assert [item["position"] for item in page["items"]] == list(range(200, 300))
        assert await eval_message_count() == 0


def _failing_execute_row(message: str):
    async def fake(**_kwargs):
        return RowExecution(actual=None, error=message, duration_ms=1, tokens=None, cost=None, trace_id="t")

    return fake


class TestEarlyStop:
    async def test_should_stop_a_run_whose_rows_keep_failing_the_same_way(self, client, logged_in_headers, monkeypatch):
        monkeypatch.setattr(runner, "execute_row", _failing_execute_row("The model `o4-mini` has been deprecated"))
        monkeypatch.setattr(get_settings_service().settings, "evals_row_concurrency", 1)
        flow = await create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "doomed", [(f"q{i}", None) for i in range(30)])
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])
        run = await wait_for_run(
            client, logged_in_headers, (await start_run(client, logged_in_headers, evaluation["id"]))["id"]
        )
        assert run["status"] == "failed"
        assert run["completed_items"] == 3
        assert "same error" in run["error"]
        assert "o4-mini" in run["error"]

    async def test_should_stop_when_the_judge_keeps_failing(self, client, logged_in_headers, monkeypatch):
        from langflow.services.evaluations import row_scoring

        async def broken_scorer(spec, **_kwargs):
            if spec["type"] == "llm_judge":
                msg = "Error code: 404 - model retired"
                raise RuntimeError(msg)
            return ScoreResult(value=1.0)

        monkeypatch.setattr(row_scoring, "run_scorer", broken_scorer)
        monkeypatch.setattr(get_settings_service().settings, "evals_row_concurrency", 1)
        flow = await create_flow(client, logged_in_headers)
        dataset = await create_dataset(
            client, logged_in_headers, "judge-doomed", [(f"q{i}", f"q{i}") for i in range(20)]
        )
        judge = [{"name": "j", "provider": "OpenAI", "metadata": {}}]
        evaluation = await create_evaluation(
            client,
            logged_in_headers,
            flow["id"],
            dataset["id"],
            scorers=[{"type": "llm_judge", "name": "judge", "config": {"model": judge}}],
        )
        run = await wait_for_run(
            client, logged_in_headers, (await start_run(client, logged_in_headers, evaluation["id"]))["id"]
        )
        assert run["status"] == "failed"
        assert run["completed_items"] == 3
        assert "model retired" in run["error"]

    async def test_should_keep_going_when_failures_differ(self, client, logged_in_headers, monkeypatch):
        calls = {"n": 0}

        async def varied(**kwargs):
            calls["n"] += 1
            return RowExecution(
                actual=None,
                error=f"input {kwargs['input_text']} rejected",
                duration_ms=1,
                tokens=None,
                cost=None,
                trace_id="t",
            )

        monkeypatch.setattr(runner, "execute_row", varied)
        flow = await create_flow(client, logged_in_headers)
        dataset = await create_dataset(
            client, logged_in_headers, "varied", [("alpha", None), ("beta", None), ("gamma", None), ("delta", None)]
        )
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])
        run = await wait_for_run(
            client, logged_in_headers, (await start_run(client, logged_in_headers, evaluation["id"]))["id"]
        )
        assert run["status"] == "completed"
        assert run["failed_items"] == 4
