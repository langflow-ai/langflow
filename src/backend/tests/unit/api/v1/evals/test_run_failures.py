from langflow.services.deps import get_settings_service
from langflow.services.evaluations import runner
from langflow.services.evaluations.row_runner import RowExecution
from langflow.services.evaluations.scorers.types import ScoreResult

from .conftest import (
    create_dataset,
    create_evaluation,
    create_flow,
    eval_message_count,
    results,
    start_run,
    wait_for_run,
)


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


def _judge_out_of_tokens():
    from langflow.services.evaluations.scorers.llm_judge import JudgeOutputLimitError

    async def scorer(spec, **_kwargs):
        if spec["type"] == "llm_judge":
            msg = "The judge used its whole output budget for this row (600 tokens) before giving a score."
            raise JudgeOutputLimitError(msg, tokens=846, cost=0.0006, output_tokens=600)
        return ScoreResult(value=1.0)

    return scorer


def _judge_scorers(*, stop: bool | None) -> list[dict]:
    config = {"model": [{"name": "j", "provider": "OpenAI", "metadata": {}}]}
    if stop is not None:
        config["stop_on_output_limit"] = stop
    return [{"type": "exact_match", "name": "exact"}, {"type": "llm_judge", "name": "judge", "config": config}]


class TestJudgeOutputLimit:
    async def test_should_stop_the_run_at_the_first_row_by_default(self, client, logged_in_headers, monkeypatch):
        from langflow.services.evaluations import row_scoring

        monkeypatch.setattr(row_scoring, "run_scorer", _judge_out_of_tokens())
        monkeypatch.setattr(get_settings_service().settings, "evals_row_concurrency", 1)
        flow = await create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "limit-stop", [(f"q{i}", f"q{i}") for i in range(10)])
        evaluation = await create_evaluation(
            client, logged_in_headers, flow["id"], dataset["id"], scorers=_judge_scorers(stop=None)
        )
        run = await wait_for_run(
            client, logged_in_headers, (await start_run(client, logged_in_headers, evaluation["id"]))["id"]
        )
        assert run["status"] == "failed"
        assert run["completed_items"] == 1
        assert run["error"].startswith("Stopped at row 1")
        assert "whole output budget" in run["error"]

    async def test_should_skip_the_judge_score_and_keep_going_when_asked(self, client, logged_in_headers, monkeypatch):
        from langflow.services.evaluations import row_scoring

        monkeypatch.setattr(row_scoring, "run_scorer", _judge_out_of_tokens())
        flow = await create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "limit-go", [(f"q{i}", f"q{i}") for i in range(6)])
        evaluation = await create_evaluation(
            client, logged_in_headers, flow["id"], dataset["id"], scorers=_judge_scorers(stop=False)
        )
        run = await wait_for_run(
            client, logged_in_headers, (await start_run(client, logged_in_headers, evaluation["id"]))["id"]
        )
        assert run["status"] == "completed", run
        assert (run["completed_items"], run["passed_items"]) == (6, 6)
        rows = await results(client, logged_in_headers, run["id"])
        judge = rows[0]["scores"]["judge"]
        assert judge["value"] is None
        assert "whole output budget" in judge["comment"]
        assert rows[0]["tokens_judge"] == 846

    async def test_should_stop_once_the_judge_spends_its_run_budget(self, client, logged_in_headers, monkeypatch):
        monkeypatch.setattr(row_scoring_module(), "run_scorer", _judge_writing(100))
        monkeypatch.setattr(get_settings_service().settings, "evals_row_concurrency", 1)
        run = await _run_with_judge_budget(client, logged_in_headers, "run-budget-stop", run_budget=250, stop=True)
        assert run["status"] == "failed"
        assert run["completed_items"] == 4
        assert "output budget for this run (250 tokens)" in run["error"]

    async def test_should_leave_rows_unjudged_after_the_run_budget_when_asked(
        self, client, logged_in_headers, monkeypatch
    ):
        monkeypatch.setattr(row_scoring_module(), "run_scorer", _judge_writing(100))
        monkeypatch.setattr(get_settings_service().settings, "evals_row_concurrency", 1)
        run = await _run_with_judge_budget(client, logged_in_headers, "run-budget-go", run_budget=250, stop=False)
        assert run["status"] == "completed"
        assert run["completed_items"] == 8
        rows = await results(client, logged_in_headers, run["id"])
        judged = [row["scores"]["judge"]["value"] for row in rows]
        assert judged[:3] == [1.0, 1.0, 1.0]
        assert all(value is None for value in judged[3:])
        assert "output budget for this run" in rows[-1]["scores"]["judge"]["comment"]


def row_scoring_module():
    from langflow.services.evaluations import row_scoring

    return row_scoring


def _judge_writing(output_tokens: int):
    async def scorer(spec, **_kwargs):
        if spec["type"] == "llm_judge":
            return ScoreResult(value=1.0, tokens=output_tokens + 50, output_tokens=output_tokens)
        return ScoreResult(value=1.0)

    return scorer


async def _run_with_judge_budget(client, headers, name: str, *, run_budget: int, stop: bool) -> dict:
    flow = await create_flow(client, headers)
    dataset = await create_dataset(client, headers, name, [(f"q{i}", f"q{i}") for i in range(8)])
    scorers = _judge_scorers(stop=stop)
    scorers[1]["config"].update(max_output_tokens=100, max_run_output_tokens=run_budget)
    evaluation = await create_evaluation(client, headers, flow["id"], dataset["id"], scorers=scorers)
    return await wait_for_run(client, headers, (await start_run(client, headers, evaluation["id"]))["id"])
