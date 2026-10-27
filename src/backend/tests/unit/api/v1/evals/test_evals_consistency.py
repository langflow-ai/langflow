import asyncio
from uuid import UUID, uuid4

import pytest
from langflow.services.data_subjects.context import EraseContext
from langflow.services.data_subjects.evaluation_steps import reassign_started_runs
from langflow.services.database.models.evaluation import EvaluationResult, EvaluationRun
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.evaluations import runner
from langflow.services.evaluations.row_runner import RowExecution
from sqlalchemy.exc import IntegrityError
from sqlmodel import func, select

from .conftest import (
    create_dataset,
    create_evaluation,
    create_flow,
    load_flow_data,
    login_headers,
    start_run,
    wait_for_run,
)


def _slow_rows(delay: float, starts: list[str] | None = None):
    async def fake(**kwargs):
        if starts is not None:
            starts.append(str(kwargs["run_id"]))
        await asyncio.sleep(delay)
        return RowExecution(
            actual=kwargs["input_text"], error=None, duration_ms=1, tokens=None, cost=None, trace_id="t"
        )

    return fake


async def _flow_in_project(client, headers, project_id: str) -> dict:
    response = await client.post(
        "api/v1/flows/",
        json={"name": f"f-{uuid4().hex[:6]}", "data": load_flow_data("chat_echo_no_llm.json"), "folder_id": project_id},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _project(client, headers, name: str) -> dict:
    return (await client.post("api/v1/projects/", json={"name": name}, headers=headers)).json()


class TestProjects:
    async def test_should_keep_an_evaluation_whose_flow_moved_out_of_the_deleted_project(
        self, client, logged_in_headers
    ):
        old, new = (
            await _project(client, logged_in_headers, "p-old"),
            await _project(client, logged_in_headers, "p-new"),
        )
        flow = await _flow_in_project(client, logged_in_headers, old["id"])
        dataset = await create_dataset(client, logged_in_headers, "moved", [("a", "a")])
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])
        moved = await client.patch(
            f"api/v1/flows/{flow['id']}", json={"folder_id": new["id"]}, headers=logged_in_headers
        )
        assert moved.status_code == 200, moved.text
        listed = await client.get("api/v1/evaluations", params={"project_id": new["id"]}, headers=logged_in_headers)
        assert [e["id"] for e in listed.json()["items"]] == [evaluation["id"]]
        assert listed.json()["items"][0]["project_id"] == new["id"]
        assert (await client.delete(f"api/v1/projects/{old['id']}", headers=logged_in_headers)).status_code in {
            200,
            204,
        }
        kept = await client.get(f"api/v1/evaluations/{evaluation['id']}", headers=logged_in_headers)
        assert kept.status_code == 200

    async def test_should_stop_a_run_whose_project_was_deleted(self, client, logged_in_headers, monkeypatch):
        monkeypatch.setattr(runner, "execute_row", _slow_rows(0.3))
        monkeypatch.setattr(runner, "CANCEL_POLL_SECONDS", 0.2)
        monkeypatch.setattr(get_settings_service().settings, "evals_row_concurrency", 1)
        project = await _project(client, logged_in_headers, "p-running")
        flow = await _flow_in_project(client, logged_in_headers, project["id"])
        dataset = await create_dataset(client, logged_in_headers, "running", [(f"q{i}", None) for i in range(20)])
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])
        run = await start_run(client, logged_in_headers, evaluation["id"])
        await asyncio.sleep(0.5)
        runner._ACTIVE_RUNS.pop(UUID(run["id"]), None)  # simulate a run owned by another worker
        assert (await client.delete(f"api/v1/projects/{project['id']}", headers=logged_in_headers)).status_code in {
            200,
            204,
        }
        await asyncio.sleep(1.0)
        async with session_scope() as session:
            orphans = (
                await session.exec(
                    select(func.count()).select_from(EvaluationResult).where(EvaluationResult.run_id == UUID(run["id"]))
                )
            ).one()
        assert orphans == 0


class TestDeletingDuringARun:
    async def test_should_delete_a_flow_while_its_run_writes_rows(self, client, logged_in_headers):
        flow = await create_flow(client, logged_in_headers)
        dataset = await create_dataset(
            client, logged_in_headers, "busy-delete", [(f"q{i}", f"q{i}") for i in range(80)]
        )
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])
        run = await start_run(client, logged_in_headers, evaluation["id"])
        await asyncio.sleep(0.5)
        deleted = await client.delete(f"api/v1/flows/{flow['id']}", headers=logged_in_headers)
        assert deleted.status_code == 200, deleted.text
        finished = await wait_for_run(client, logged_in_headers, run["id"])
        assert finished["status"] in {"completed", "failed", "cancelled"}


class TestActiveRuns:
    async def test_should_refuse_item_changes_while_a_run_uses_the_dataset(
        self, client, logged_in_headers, monkeypatch
    ):
        monkeypatch.setattr(runner, "execute_row", _slow_rows(0.3))
        monkeypatch.setattr(get_settings_service().settings, "evals_row_concurrency", 1)
        flow = await create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "busy", [(f"q{i}", None) for i in range(6)])
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])
        run = await start_run(client, logged_in_headers, evaluation["id"])
        base = f"api/v1/datasets/{dataset['id']}"
        add = await client.post(f"{base}/items", json={"items": [{"input": "new"}]}, headers=logged_in_headers)
        assert add.status_code == 409
        assert (await client.delete(base, headers=logged_in_headers)).status_code == 409
        busy_delete = await client.delete(f"api/v1/evaluations/{evaluation['id']}", headers=logged_in_headers)
        assert busy_delete.status_code == 409
        await wait_for_run(client, logged_in_headers, run["id"])
        add = await client.post(f"{base}/items", json={"items": [{"input": "new"}]}, headers=logged_in_headers)
        assert add.status_code == 201

    async def test_should_allow_only_one_active_run_per_evaluation_in_the_database(self, client, logged_in_headers):
        flow = await create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "one-active", [("a", "a")])
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])

        def active() -> EvaluationRun:
            return EvaluationRun(
                evaluation_id=UUID(evaluation["id"]),
                user_id=UUID(flow["user_id"]),
                flow_name="f",
                dataset_name="d",
                dataset_revision=1,
                status="running",
            )

        async with session_scope() as session:
            session.add(active())
        async with session_scope() as session:
            session.add(active())
            with pytest.raises(IntegrityError):
                await session.flush()
            await session.rollback()

    async def test_should_answer_409_when_a_concurrent_start_wins(self, client, logged_in_headers, monkeypatch):
        from langflow.services.evaluations import run_service

        monkeypatch.setattr(runner, "execute_row", _slow_rows(0.5))
        flow = await create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "race", [("a", "a"), ("b", "b")])
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])
        first = await start_run(client, logged_in_headers, evaluation["id"])

        async def never_busy(*_args, **_kwargs) -> bool:
            return False

        monkeypatch.setattr(run_service, "has_active_run", never_busy)
        second = await client.post(f"api/v1/evaluations/{evaluation['id']}/runs", headers=logged_in_headers)
        assert second.status_code == 409
        await wait_for_run(client, logged_in_headers, first["id"])

    async def test_should_start_exactly_one_of_many_simultaneous_runs(self, client, logged_in_headers, monkeypatch):
        monkeypatch.setattr(runner, "execute_row", _slow_rows(0.2))
        flow = await create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "burst", [("a", "a"), ("b", "b")])
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])
        sibling = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])
        responses = await asyncio.gather(
            *[client.post(f"api/v1/evaluations/{evaluation['id']}/runs", headers=logged_in_headers) for _ in range(5)],
            client.post(f"api/v1/evaluations/{sibling['id']}/runs", headers=logged_in_headers),
        )
        burst, other = [r.status_code for r in responses[:5]], responses[5].status_code
        assert sorted(burst) == [202, 409, 409, 409, 409], burst
        assert other == 202
        for response in responses:
            if response.status_code == 202:
                await wait_for_run(client, logged_in_headers, response.json()["id"])

    async def test_should_fail_a_run_whose_pod_died_while_its_job_looks_in_progress(self, client, logged_in_headers):
        from langflow.services.database.models.jobs.model import JobStatus, JobType
        from langflow.services.deps import get_job_service

        flow = await create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "dead-pod", [("a", "a")])
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])
        job_id = uuid4()
        await get_job_service().create_job(
            job_id=job_id,
            flow_id=UUID(flow["id"]),
            job_type=JobType.EVALUATION,
            user_id=UUID(flow["user_id"]),
            status=JobStatus.IN_PROGRESS,
            initial_metadata={"heartbeat_at": "2020-01-01T00:00:00+00:00"},
        )
        async with session_scope() as session:
            orphan = EvaluationRun(
                evaluation_id=UUID(evaluation["id"]),
                user_id=UUID(flow["user_id"]),
                job_id=job_id,
                flow_name="f",
                dataset_name="d",
                dataset_revision=1,
                status="running",
            )
            session.add(orphan)
            await session.flush()
            run_id = str(orphan.id)
        run = (await client.get(f"api/v1/evaluation-runs/{run_id}", headers=logged_in_headers)).json()
        assert run["status"] == "failed"
        restart = await client.post(f"api/v1/evaluations/{evaluation['id']}/runs", headers=logged_in_headers)
        assert restart.status_code == 202, restart.text
        await wait_for_run(client, logged_in_headers, restart.json()["id"])

    async def test_should_not_fail_a_run_that_is_still_launching(self, client, logged_in_headers):
        flow = await create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "launching", [("a", "a")])
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])
        async with session_scope() as session:
            launching = EvaluationRun(
                evaluation_id=UUID(evaluation["id"]),
                user_id=UUID(flow["user_id"]),
                job_id=uuid4(),
                flow_name="f",
                dataset_name="d",
                dataset_revision=1,
                status="queued",
            )
            session.add(launching)
            await session.flush()
            run_id = str(launching.id)
        run = (await client.get(f"api/v1/evaluation-runs/{run_id}", headers=logged_in_headers)).json()
        assert run["status"] == "queued"


class TestRunner:
    async def test_should_share_the_process_limit_between_runs(self, client, logged_in_headers, monkeypatch):
        starts: list[str] = []
        monkeypatch.setattr(runner, "execute_row", _slow_rows(0.2, starts))
        monkeypatch.setattr(runner, "_GLOBAL_LIMITS", {})
        settings = get_settings_service().settings
        monkeypatch.setattr(settings, "evals_row_concurrency", 1)
        monkeypatch.setattr(settings, "evals_max_concurrency", 2)
        flow = await create_flow(client, logged_in_headers)
        first_ds = await create_dataset(client, logged_in_headers, "share-a", [(f"a{i}", None) for i in range(6)])
        second_ds = await create_dataset(client, logged_in_headers, "share-b", [(f"b{i}", None) for i in range(6)])
        first = await create_evaluation(client, logged_in_headers, flow["id"], first_ds["id"])
        second = await create_evaluation(client, logged_in_headers, flow["id"], second_ds["id"])
        run_a = await start_run(client, logged_in_headers, first["id"])
        run_b = await start_run(client, logged_in_headers, second["id"])
        await wait_for_run(client, logged_in_headers, run_a["id"])
        await wait_for_run(client, logged_in_headers, run_b["id"])
        first_b = starts.index(run_b["id"])
        assert first_b < starts.count(run_a["id"]), starts

    async def test_should_resolve_the_judge_inside_the_flows_provider_policy_scope(
        self, client, logged_in_headers, monkeypatch
    ):
        from langflow.services.evaluations.scorers import llm_judge
        from lfx.services.model_provider_policy.context import current_model_provider_policy_context

        seen = []

        def capture_get_llm(*_args, **_kwargs):
            seen.append(current_model_provider_policy_context())
            msg = "judge model unavailable"
            raise RuntimeError(msg)

        monkeypatch.setattr(runner, "execute_row", _slow_rows(0))
        monkeypatch.setattr(llm_judge, "get_llm", capture_get_llm)
        project = await _project(client, logged_in_headers, "p-policy")
        flow = await _flow_in_project(client, logged_in_headers, project["id"])
        dataset = await create_dataset(client, logged_in_headers, "policy", [("a", "a")])
        judge = [{"name": "j", "provider": "OpenAI", "metadata": {}}]
        evaluation = await create_evaluation(
            client,
            logged_in_headers,
            flow["id"],
            dataset["id"],
            scorers=[{"type": "llm_judge", "name": "judge", "config": {"model": judge}}],
        )
        await wait_for_run(
            client, logged_in_headers, (await start_run(client, logged_in_headers, evaluation["id"]))["id"]
        )
        assert len(seen) == 1
        context = seen[0]
        assert context is not None, "the judge ran outside the flow's provider policy scope"
        assert str(context.user_id) == flow["user_id"]
        assert str(context.attributes["project_id"]) == project["id"]
        assert context.attributes["provider_scope_required"] is True
        assert current_model_provider_policy_context() is None

    async def test_should_finish_a_run_when_a_cancel_poll_fails(self, client, logged_in_headers, monkeypatch):
        monkeypatch.setattr(runner, "execute_row", _slow_rows(0.2))
        monkeypatch.setattr(runner, "CANCEL_POLL_SECONDS", 0.05)
        monkeypatch.setattr(get_settings_service().settings, "evals_row_concurrency", 1)

        async def flaky_status(_run_id):
            msg = "database went away"
            raise ConnectionError(msg)

        monkeypatch.setattr(runner, "_run_status", flaky_status)
        flow = await create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "flaky", [(f"q{i}", f"q{i}") for i in range(4)])
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])
        run = await wait_for_run(
            client, logged_in_headers, (await start_run(client, logged_in_headers, evaluation["id"]))["id"]
        )
        assert run["status"] == "completed", run
        assert run["summary"] is not None

    async def test_should_store_a_row_once_when_a_timeout_races_the_save(self, client, logged_in_headers):
        flow = await create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "once", [("a", "a")])
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])
        async with session_scope() as session:
            run = EvaluationRun(
                evaluation_id=UUID(evaluation["id"]),
                user_id=UUID(flow["user_id"]),
                flow_name="f",
                dataset_name="d",
                dataset_revision=1,
                status="completed",
            )
            session.add(run)
            await session.flush()
            run_id = run.id

        def row(position: int = 0) -> EvaluationResult:
            return EvaluationResult(run_id=run_id, position=position, input={"text": "a"})

        assert await runner._store_result(run_id, row()) is True
        assert await runner._store_result(run_id, row()) is False
        orphan = EvaluationResult(run_id=uuid4(), position=0, input={})
        assert await runner._store_result(orphan.run_id, orphan) is False
        async with session_scope() as session:
            count_stmt = select(func.count()).select_from(EvaluationResult).where(EvaluationResult.run_id == run_id)
            stored = (await session.exec(count_stmt)).one()
            done_stmt = select(EvaluationRun.completed_items).where(EvaluationRun.id == run_id)
            completed = (await session.exec(done_stmt)).one()
        assert (stored, completed) == (1, 1)


class TestOwnership:
    async def test_should_let_the_evaluation_owner_read_a_run_someone_else_started(
        self, client, logged_in_headers, user_two
    ):
        flow = await create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "started-by", [("a", "a")])
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])
        async with session_scope() as session:
            run = EvaluationRun(
                evaluation_id=UUID(evaluation["id"]),
                user_id=user_two.id,
                flow_name="f",
                dataset_name="d",
                dataset_revision=1,
                status="completed",
            )
            session.add(run)
            await session.flush()
            run_id = str(run.id)
        assert (await client.get(f"api/v1/evaluation-runs/{run_id}", headers=logged_in_headers)).status_code == 200
        other = await login_headers(client, user_two)
        assert (await client.get(f"api/v1/evaluation-runs/{run_id}", headers=other)).status_code == 404

    async def test_should_hand_runs_to_the_evaluation_owner_when_the_starter_is_erased(
        self, client, logged_in_headers, user_two
    ):
        flow = await create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "erase-starter", [("a", "a")])
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])
        async with session_scope() as session:
            run = EvaluationRun(
                evaluation_id=UUID(evaluation["id"]),
                user_id=user_two.id,
                flow_name="f",
                dataset_name="d",
                dataset_revision=1,
                status="completed",
            )
            session.add(run)
            await session.flush()
            run_id = run.id
        async with session_scope() as session:
            moved = await reassign_started_runs(session, EraseContext(request_id=uuid4(), subject_user_id=user_two.id))
        assert moved == 1
        async with session_scope() as session:
            owner = (await session.exec(select(EvaluationRun.user_id).where(EvaluationRun.id == run_id))).one()
        assert str(owner) == flow["user_id"]

    async def test_should_copy_a_dataset_into_the_callers_account(self, client, logged_in_headers, user_two):
        from langflow.services.database.models.evaluation import Dataset
        from langflow.services.evaluations.dataset_service import duplicate_dataset

        dataset = await create_dataset(client, logged_in_headers, "shared-src", [("a", "a")])
        async with session_scope() as session:
            source = (await session.exec(select(Dataset).where(Dataset.id == UUID(dataset["id"])))).one()
            copy = await duplicate_dataset(session, source, user_two.id)
            assert copy.user_id == user_two.id

    async def test_should_hide_every_write_path_from_another_user(self, client, logged_in_headers, user_two):
        flow = await create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "mine-only", [("a", "a")])
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])
        run = await wait_for_run(
            client, logged_in_headers, (await start_run(client, logged_in_headers, evaluation["id"]))["id"]
        )
        item_id = (await client.get(f"api/v1/datasets/{dataset['id']}/items", headers=logged_in_headers)).json()[
            "items"
        ][0]["id"]
        other = await login_headers(client, user_two)
        theirs = (await client.post("api/v1/datasets/", json={"name": "theirs"}, headers=other)).json()
        base = f"api/v1/datasets/{dataset['id']}"
        csv = {"file": ("d.csv", b"input\nx\n", "text/csv")}
        attempts = [
            client.patch(base, json={"name": "stolen"}, headers=other),
            client.post(f"{base}/items", json={"items": [{"input": "x"}]}, headers=other),
            client.patch(f"{base}/items/{item_id}", json={"input": "x"}, headers=other),
            client.post(f"{base}/items/delete", json={"ids": [item_id]}, headers=other),
            client.post(f"{base}/import/preview", files=csv, headers=other),
            client.post(f"{base}/import", files=csv, data={"input_column": "input"}, headers=other),
            client.post(f"{base}/duplicate", headers=other),
            client.get(f"{base}/export", headers=other),
            client.patch(f"api/v1/evaluations/{evaluation['id']}", json={"name": "x"}, headers=other),
            client.delete(f"api/v1/evaluations/{evaluation['id']}", headers=other),
            client.post(f"api/v1/evaluation-runs/{run['id']}/cancel", headers=other),
            client.get(f"api/v1/evaluation-runs/{run['id']}/export", headers=other),
            client.patch(
                f"api/v1/evaluations/{evaluation['id']}", json={"dataset_id": theirs["id"]}, headers=logged_in_headers
            ),
        ]
        for attempt in attempts:
            response = await attempt
            assert response.status_code == 404, (response.request.method, response.request.url, response.text)


class TestLimits:
    async def test_should_refuse_a_csv_over_the_byte_limit(self, client, logged_in_headers, monkeypatch):
        monkeypatch.setattr(get_settings_service().settings, "evals_csv_max_bytes", 16)
        dataset = await create_dataset(client, logged_in_headers, "too-big", [])
        response = await client.post(
            f"api/v1/datasets/{dataset['id']}/import/preview",
            files={"file": ("d.csv", b"input\n" + b"x" * 64, "text/csv")},
            headers=logged_in_headers,
        )
        assert response.status_code == 413

    async def test_should_ignore_history_from_a_different_flow_version(self, client, logged_in_headers):
        flow = await create_flow(client, logged_in_headers)
        dataset = await create_dataset(client, logged_in_headers, "hist", [("a", "a")])
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])
        run = await wait_for_run(
            client, logged_in_headers, (await start_run(client, logged_in_headers, evaluation["id"]))["id"]
        )
        async with session_scope() as session:
            stored = (await session.exec(select(EvaluationRun).where(EvaluationRun.id == UUID(run["id"])))).one()
            stored.summary = {**(stored.summary or {}), "tokens": {"flow": 100, "judge": 0, "total": 100}}
            session.add(stored)
        body = {"flow_id": flow["id"], "dataset_id": dataset["id"], "scorers": [{"type": "exact_match", "name": "e"}]}
        same = (await client.post("api/v1/evaluations/estimate", json=body, headers=logged_in_headers)).json()
        assert same["basis"] == "history"
        changed = {**flow["data"], "description": "edited"}
        patched = await client.patch(f"api/v1/flows/{flow['id']}", json={"data": changed}, headers=logged_in_headers)
        assert patched.status_code == 200, patched.text
        after = (await client.post("api/v1/evaluations/estimate", json=body, headers=logged_in_headers)).json()
        assert after["basis"] == "model"

    async def test_should_serve_the_flow_check_as_a_read(self, client, logged_in_headers):
        flow = await create_flow(client, logged_in_headers)
        response = await client.get(
            "api/v1/evaluations/check", params={"flow_id": flow["id"]}, headers=logged_in_headers
        )
        assert response.status_code == 200, response.text
        assert response.json()["blocking"] == []

    async def test_should_list_previews_and_read_one_result_in_full(self, client, logged_in_headers, user_two):
        long_text = " ".join(["word"] * 400)
        flow = await create_flow(client, logged_in_headers)
        dataset = await create_dataset(
            client, logged_in_headers, "previews", [(long_text, long_text), ("short", "short")]
        )
        evaluation = await create_evaluation(client, logged_in_headers, flow["id"], dataset["id"])
        run = await wait_for_run(
            client, logged_in_headers, (await start_run(client, logged_in_headers, evaluation["id"]))["id"]
        )
        listed = (await client.get(f"api/v1/evaluation-runs/{run['id']}/results", headers=logged_in_headers)).json()[
            "items"
        ]
        long_row, short_row = listed
        assert long_row["preview"] is True
        assert len(long_row["input"]) == 500
        assert short_row["preview"] is False
        full = await client.get(
            f"api/v1/evaluation-runs/{run['id']}/results/{long_row['id']}", headers=logged_in_headers
        )
        assert full.status_code == 200
        assert full.json()["input"] == long_text
        assert full.json()["preview"] is False
        other = await login_headers(client, user_two)
        hidden = await client.get(f"api/v1/evaluation-runs/{run['id']}/results/{long_row['id']}", headers=other)
        assert hidden.status_code == 404
