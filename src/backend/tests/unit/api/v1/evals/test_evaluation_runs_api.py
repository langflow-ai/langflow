import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from langflow.memory import aadd_messages
from langflow.schema.message import Message
from langflow.services.database.models.evaluation import EvaluationRun
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.jobs.model import JobStatus
from langflow.services.deps import get_job_service, get_settings_service, session_scope
from langflow.services.evaluations import runner
from langflow.services.evaluations.row_runner import RowExecution
from sqlmodel import select

from .conftest import (
    create_dataset,
    create_evaluation,
    create_flow,
    eval_message_count,
    load_flow_data,
    results,
    start_run,
    wait_for_run,
)

PLAYGROUND_NOTE = "PRIVATE-PLAYGROUND-NOTE"


class TestRunLifecycle:
    async def test_should_run_every_row_score_it_and_persist_no_chat_messages(self, client, logged_in_headers):
        flow = await create_flow(client, logged_in_headers)
        rows = [("alpha", "alpha"), ("beta", "beta"), ("gamma", "GAMMA"), ("delta", "nope"), ("epsilon", None)]
        dataset = await create_dataset(client, logged_in_headers, "lifecycle", rows)
        evaluation = await create_evaluation(
            client,
            logged_in_headers,
            flow["id"],
            dataset["id"],
            scorers=[{"type": "exact_match", "name": "exact"}, {"type": "contains", "name": "contains", "weight": 2}],
        )
        run = await wait_for_run(
            client, logged_in_headers, (await start_run(client, logged_in_headers, evaluation["id"]))["id"]
        )

        assert run["status"] == "completed", run
        assert (run["total_items"], run["completed_items"], run["failed_items"]) == (5, 5, 0)
        assert run["flow_version_source"] == "latest"
        assert run["flow_version_number"] >= 1
        items = await results(client, logged_in_headers, run["id"])
        assert [item["actual_output"] for item in items] == [q for q, _ in rows]
        assert [item["passed"] for item in items] == [True, True, True, False, None]
        assert items[4]["scores"]["exact"]["value"] is None
        assert all(item["trace_id"] for item in items)
        assert run["passed_items"] == 3
        assert run["summary"]["pass_rate"] == pytest.approx(0.75)
        assert await eval_message_count() == 0

        failed_only = await results(client, logged_in_headers, run["id"], passed="false")
        assert [item["position"] for item in failed_only] == [3]

        exported = await client.get(f"api/v1/evaluation-runs/{run['id']}/export", headers=logged_in_headers)
        assert exported.status_code == 200
        assert exported.text.splitlines()[0].lstrip("﻿").startswith("position,input,expected_output")

    async def test_should_reuse_the_snapshot_when_the_flow_did_not_change(self, client, logged_in_headers):
        flow = await create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "reuse", [("x", "x")])
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])
        first = await wait_for_run(
            client, logged_in_headers, (await start_run(client, logged_in_headers, evaluation["id"]))["id"]
        )
        second = await wait_for_run(
            client, logged_in_headers, (await start_run(client, logged_in_headers, evaluation["id"]))["id"]
        )
        assert first["flow_version_id"] == second["flow_version_id"]

        runs = (await client.get(f"api/v1/evaluations/{evaluation['id']}/runs", headers=logged_in_headers)).json()
        assert runs["total"] == 2
        listed = (
            await client.get("api/v1/evaluations", params={"flow_id": flow["id"]}, headers=logged_in_headers)
        ).json()
        assert listed["items"][0]["last_run"]["id"] == second["id"]
        assert listed["items"][0]["flow_name"] == "Echo"


class TestFlowVersions:
    async def test_should_run_a_chosen_history_version_and_retain_it(self, client, logged_in_headers):
        flow = await create_flow(client, logged_in_headers)
        snapshot = await client.post(
            f"api/v1/flows/{flow['id']}/versions/", json={"description": "v1"}, headers=logged_in_headers
        )
        assert snapshot.status_code == 201, snapshot.text
        version_id = snapshot.json()["id"]
        dataset = await create_dataset(client, logged_in_headers, "versions", [("x", "x")])
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])

        run = await wait_for_run(
            client, logged_in_headers, (await start_run(client, logged_in_headers, evaluation["id"], version_id))["id"]
        )
        assert run["status"] == "completed"
        assert (run["flow_version_id"], run["flow_version_source"]) == (version_id, "history")
        async with session_scope() as session:
            version = (await session.exec(select(FlowVersion).where(FlowVersion.id == UUID(version_id)))).one()
            assert version.retained
            assert version.retained_reason == "evaluation"

        blocked = await client.delete(f"api/v1/flows/{flow['id']}/versions/{version_id}", headers=logged_in_headers)
        assert blocked.status_code >= 400

        deleted = await client.delete(f"api/v1/evaluations/{evaluation['id']}", headers=logged_in_headers)
        assert deleted.status_code == 204
        async with session_scope() as session:
            version = (await session.exec(select(FlowVersion).where(FlowVersion.id == UUID(version_id)))).one()
            assert not version.retained

    async def test_should_refuse_a_version_of_another_flow(self, client, logged_in_headers):
        flow = await create_flow(client, logged_in_headers)
        other = await create_flow(client, logged_in_headers, name="Other")
        foreign = await client.post(f"api/v1/flows/{other['id']}/versions/", json={}, headers=logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "foreign-version", [("x", "x")])
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])
        response = await client.post(
            f"api/v1/evaluations/{evaluation['id']}/runs",
            json={"flow_version_id": foreign.json()["id"]},
            headers=logged_in_headers,
        )
        assert response.status_code == 404

    async def test_should_create_and_run_a_chosen_version_atomically(self, client, logged_in_headers):
        flow = await create_flow(client, logged_in_headers)
        other = await create_flow(client, logged_in_headers, name="Other")
        own = (await client.post(f"api/v1/flows/{flow['id']}/versions/", json={}, headers=logged_in_headers)).json()
        foreign = (
            await client.post(f"api/v1/flows/{other['id']}/versions/", json={}, headers=logged_in_headers)
        ).json()
        dataset = await create_dataset(client, logged_in_headers, "create-run", [("x", "x")])
        body = {
            "flow_id": flow["id"],
            "dataset_id": dataset["id"],
            "scorers": [{"type": "exact_match", "name": "exact"}],
        }
        refused = await client.post(
            "api/v1/evaluations",
            params={"run": True},
            json={**body, "flow_version_id": foreign["id"]},
            headers=logged_in_headers,
        )
        assert refused.status_code == 404
        listed = await client.get("api/v1/evaluations", params={"flow_id": flow["id"]}, headers=logged_in_headers)
        assert listed.json()["total"] == 0
        started = await client.post(
            "api/v1/evaluations",
            params={"run": True},
            json={**body, "flow_version_id": own["id"]},
            headers=logged_in_headers,
        )
        assert started.status_code == 201, started.text
        run = await wait_for_run(client, logged_in_headers, started.json()["id"])
        assert (run["flow_version_id"], run["flow_version_source"]) == (own["id"], "history")

    async def test_should_check_the_chosen_version_not_the_draft(self, client, logged_in_headers):
        flow = await create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "old-version", [("x", "x")])
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])
        async with session_scope() as session:
            broken = FlowVersion(
                flow_id=UUID(flow["id"]), user_id=None, data=load_flow_data("human_input_flow.json"), version_number=99
            )
            session.add(broken)
            await session.flush()
            broken_id = str(broken.id)
        response = await client.post(
            f"api/v1/evaluations/{evaluation['id']}/runs",
            json={"flow_version_id": broken_id},
            headers=logged_in_headers,
        )
        assert response.status_code == 422
        codes = {issue["code"] for issue in response.json()["detail"]["issues"]}
        assert {"human_in_the_loop", "no_input"} <= codes


class TestMemoryIsolation:
    async def test_should_never_read_playground_history(self, client, logged_in_headers, active_user, user_one_api_key):
        data = load_flow_data("MemoryChatbotNoLLM.json")
        for node in data["nodes"]:
            if node["data"]["type"] == "Memory":
                node["data"]["node"]["template"]["session_id"]["value"] = "support"
        response = await client.post(
            "api/v1/flows/", json={"name": "Memory bot", "data": data}, headers=logged_in_headers
        )
        flow = response.json()
        await aadd_messages(
            Message(text=PLAYGROUND_NOTE, sender="User", sender_name="User", session_id="support", flow_id=flow["id"]),
            flow_id=flow["id"],
            user_id=active_user.id,
        )

        playground = await client.post(
            f"api/v1/run/{flow['id']}",
            json={"input_value": "hello", "session_id": "support"},
            headers={"x-api-key": user_one_api_key},
        )
        assert playground.status_code == 200, playground.text
        assert PLAYGROUND_NOTE in playground.text, (
            "the flow must read history outside an evaluation, or this test proves nothing"
        )

        dataset = await create_dataset(client, logged_in_headers, "memory", [("row one", None), ("row two", None)])
        evaluation = await create_evaluation(
            client, logged_in_headers, flow["id"], dataset["id"], scorers=[{"type": "contains", "name": "c"}]
        )
        run = await wait_for_run(
            client, logged_in_headers, (await start_run(client, logged_in_headers, evaluation["id"]))["id"]
        )
        assert run["status"] == "completed", run
        outputs = [item["actual_output"] for item in await results(client, logged_in_headers, run["id"])]
        assert len(outputs) == 2
        assert all(PLAYGROUND_NOTE not in output for output in outputs), outputs
        assert all("row one" not in output for output in outputs[1:]), "row two must not see row one"
        assert await eval_message_count() == 0

    async def test_should_hide_stored_history_from_explicit_reads_during_a_row(self, client, active_user):  # noqa: ARG002
        from langflow.memory import aget_messages
        from lfx.memory.flow_context import reset_evals_memory_isolated, set_evals_memory_isolated

        flow_id = uuid4()
        async with session_scope() as session:
            from langflow.services.database.models.flow.model import Flow

            session.add(Flow(id=flow_id, name="direct", user_id=active_user.id, data={}))
        await aadd_messages(
            Message(text=PLAYGROUND_NOTE, sender="User", sender_name="User", session_id="support", flow_id=flow_id),
            flow_id=flow_id,
            user_id=active_user.id,
        )
        visible = await aget_messages(session_id="support", flow_id=flow_id, user_id=active_user.id)
        assert [message.text for message in visible] == [PLAYGROUND_NOTE]
        token = set_evals_memory_isolated(True)
        try:
            assert await aget_messages(session_id="support", flow_id=flow_id, user_id=active_user.id) == []
        finally:
            reset_evals_memory_isolated(token)


class TestGuards:
    async def test_should_block_a_human_in_the_loop_flow(self, client, logged_in_headers):
        flow = await create_flow(client, logged_in_headers, filename="human_input_flow.json", name="HITL")
        dataset = await create_dataset(client, logged_in_headers, "hitl", [("x", None)])
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])
        response = await client.post(f"api/v1/evaluations/{evaluation['id']}/runs", headers=logged_in_headers)
        assert response.status_code == 422
        assert "human_in_the_loop" in {issue["code"] for issue in response.json()["detail"]["issues"]}

    async def test_should_refuse_an_empty_dataset(self, client, logged_in_headers):
        flow = await create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "empty", [])
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])
        response = await client.post(f"api/v1/evaluations/{evaluation['id']}/runs", headers=logged_in_headers)
        assert response.status_code == 422

    async def test_should_refuse_a_dataset_over_the_item_limit(self, client, logged_in_headers, monkeypatch):
        monkeypatch.setattr(get_settings_service().settings, "evals_max_items", 2)
        flow = await create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "big", [("a", None), ("b", None), ("c", None)])
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])
        response = await client.post(f"api/v1/evaluations/{evaluation['id']}/runs", headers=logged_in_headers)
        assert response.status_code == 422
        assert "limit" in response.json()["detail"]

    async def test_should_validate_scorer_config(self, client, logged_in_headers):
        flow = await create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "scorers", [("a", None)])
        for scorers in (
            [{"type": "llm_judge", "name": "judge"}],
            [{"type": "exact_match", "name": "x"}, {"type": "contains", "name": "x"}],
            [{"type": "unknown", "name": "x"}],
            [],
        ):
            response = await client.post(
                "api/v1/evaluations",
                json={"flow_id": flow["id"], "dataset_id": dataset["id"], "scorers": scorers},
                headers=logged_in_headers,
            )
            assert response.status_code == 422, scorers

    async def test_should_hide_another_users_evaluation_and_runs(self, client, logged_in_headers, user_two):
        flow = await create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "private", [("x", "x")])
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])
        run = await wait_for_run(
            client, logged_in_headers, (await start_run(client, logged_in_headers, evaluation["id"]))["id"]
        )
        # The user_two fixture's fixed test password, not a credential.
        credentials = {"username": user_two.username, "password": "hashed_password"}  # pragma: allowlist secret
        login = await client.post("api/v1/login", data=credentials)
        other = {"Authorization": f"Bearer {login.json()['access_token']}"}
        for path in (
            f"api/v1/evaluations/{evaluation['id']}",
            f"api/v1/evaluations/{evaluation['id']}/runs",
            f"api/v1/evaluation-runs/{run['id']}",
            f"api/v1/evaluation-runs/{run['id']}/results",
        ):
            assert (await client.get(path, headers=other)).status_code == 404, path
        start = await client.post(f"api/v1/evaluations/{evaluation['id']}/runs", headers=other)
        assert start.status_code == 404
        forged = await client.post(
            "api/v1/evaluations",
            json={
                "flow_id": flow["id"],
                "dataset_id": dataset["id"],
                "scorers": [{"type": "exact_match", "name": "e"}],
            },
            headers=other,
        )
        assert forged.status_code == 404


def _slow_execute_row(delay: float):
    async def fake(**kwargs):
        await asyncio.sleep(delay)
        return RowExecution(
            actual=kwargs["input_text"], error=None, duration_ms=int(delay * 1000), tokens=None, cost=None, trace_id="t"
        )

    return fake


class TestStoppingRuns:
    async def test_should_cancel_a_running_evaluation_and_keep_finished_rows(
        self, client, logged_in_headers, monkeypatch
    ):
        monkeypatch.setattr(runner, "execute_row", _slow_execute_row(0.5))
        monkeypatch.setattr(get_settings_service().settings, "evals_row_concurrency", 1)
        flow = await create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "cancel", [(f"q{i}", f"q{i}") for i in range(20)])
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])
        started = await start_run(client, logged_in_headers, evaluation["id"])
        busy = await client.post(f"api/v1/evaluations/{evaluation['id']}/runs", headers=logged_in_headers)
        assert busy.status_code == 409
        await asyncio.sleep(1.2)
        cancelled = await client.post(f"api/v1/evaluation-runs/{started['id']}/cancel", headers=logged_in_headers)
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"
        await asyncio.sleep(1.0)
        run = await wait_for_run(client, logged_in_headers, started["id"])
        assert run["status"] == "cancelled"
        assert 0 < run["completed_items"] < 20
        assert run["summary"] is not None
        again = await client.post(f"api/v1/evaluation-runs/{started['id']}/cancel", headers=logged_in_headers)
        assert again.status_code == 409
        async with session_scope() as session:
            job_id = (await session.exec(select(EvaluationRun.job_id).where(EvaluationRun.id == UUID(run["id"])))).one()
        job = await get_job_service().get_job_by_job_id(job_id)
        assert job.status == JobStatus.CANCELLED

    async def test_should_record_a_timeout_per_row_without_failing_the_run(
        self, client, logged_in_headers, monkeypatch
    ):
        monkeypatch.setattr(runner, "execute_row", _slow_execute_row(5))
        monkeypatch.setattr(get_settings_service().settings, "evals_row_timeout_s", 0.3)
        flow = await create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "timeout", [("a", "a"), ("b", "b")])
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])
        run = await wait_for_run(
            client, logged_in_headers, (await start_run(client, logged_in_headers, evaluation["id"]))["id"]
        )
        assert run["status"] == "completed"
        assert run["failed_items"] == 2
        items = await results(client, logged_in_headers, run["id"])
        assert all(item["error"].startswith("Timed out") and item["passed"] is False for item in items)

    async def test_should_fail_a_run_whose_worker_disappeared(self, client, logged_in_headers):
        flow = await create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "lost", [("a", "a")])
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])
        async with session_scope() as session:
            orphan = EvaluationRun(
                evaluation_id=UUID(evaluation["id"]),
                user_id=UUID(flow["user_id"]),
                job_id=uuid4(),
                flow_id=UUID(flow["id"]),
                flow_name="Echo",
                dataset_name="lost",
                dataset_revision=1,
                status="running",
                total_items=1,
                created_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            )
            session.add(orphan)
            await session.flush()
            orphan_id = str(orphan.id)
        run = (await client.get(f"api/v1/evaluation-runs/{orphan_id}", headers=logged_in_headers)).json()
        assert run["status"] == "failed"
        assert "server stopped" in run["error"]
        allowed = await client.post(f"api/v1/evaluations/{evaluation['id']}/runs", headers=logged_in_headers)
        assert allowed.status_code == 202


class TestDeletions:
    async def test_should_keep_results_readable_after_the_flow_is_deleted(self, client, logged_in_headers):
        flow = await create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "orphaned", [("a", "a")])
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])
        run = await wait_for_run(
            client, logged_in_headers, (await start_run(client, logged_in_headers, evaluation["id"]))["id"]
        )
        assert (await client.delete(f"api/v1/flows/{flow['id']}", headers=logged_in_headers)).status_code in {200, 204}

        detail = (await client.get(f"api/v1/evaluations/{evaluation['id']}", headers=logged_in_headers)).json()
        assert detail["flow_id"] is None
        assert len(await results(client, logged_in_headers, run["id"])) == 1
        rerun = await client.post(f"api/v1/evaluations/{evaluation['id']}/runs", headers=logged_in_headers)
        assert rerun.status_code == 422

    async def test_should_keep_results_readable_after_the_dataset_is_deleted(self, client, logged_in_headers):
        flow = await create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "gone", [("a", "a")])
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])
        run = await wait_for_run(
            client, logged_in_headers, (await start_run(client, logged_in_headers, evaluation["id"]))["id"]
        )
        assert (await client.delete(f"api/v1/datasets/{dataset['id']}", headers=logged_in_headers)).status_code == 204
        items = await results(client, logged_in_headers, run["id"])
        assert items[0]["input"] == "a"
        detail = (await client.get(f"api/v1/evaluations/{evaluation['id']}", headers=logged_in_headers)).json()
        assert detail["dataset_id"] is None

    async def test_should_delete_evaluations_with_their_project(self, client, logged_in_headers):
        project = (await client.post("api/v1/projects/", json={"name": "evals-proj"}, headers=logged_in_headers)).json()
        response = await client.post(
            "api/v1/flows/",
            json={"name": "In project", "data": load_flow_data("chat_echo_no_llm.json"), "folder_id": project["id"]},
            headers=logged_in_headers,
        )
        flow = response.json()
        dataset = await create_dataset(client, logged_in_headers, "proj-ds", [("a", "a")])
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])
        assert evaluation["project_id"] == project["id"]
        await wait_for_run(
            client, logged_in_headers, (await start_run(client, logged_in_headers, evaluation["id"]))["id"]
        )
        deleted = await client.delete(f"api/v1/projects/{project['id']}", headers=logged_in_headers)
        assert deleted.status_code in {200, 204}, deleted.text
        assert (
            await client.get(f"api/v1/evaluations/{evaluation['id']}", headers=logged_in_headers)
        ).status_code == 404
