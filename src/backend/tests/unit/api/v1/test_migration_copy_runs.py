"""Tests for the migration endpoints that run the copies.

Every copy here is the real command, started by the endpoint as a real child process,
as in production. A test that copies writes to a PostgreSQL database and an S3 bucket
of its own, and skips where there is no server or no driver for one.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import psutil
import pytest
import sqlalchemy as sa
from fastapi import HTTPException
from langflow.api.utils import knowledge_base_service, migration_runs
from langflow.api.v1 import migration as migration_module
from langflow.services.database.models.file.model import File
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord
from langflow.services.database.models.message.model import MessageTable
from langflow.services.database.models.traces.model import SpanTable, TraceTable
from langflow.services.deps import get_db_service, session_scope
from langflow.services.knowledge_base_storage.runtime import backend_for_record
from lfx.base.knowledge_bases.backends import IngestedDocument

from .test_migration import (
    DB_PASSWORD,
    FAILING,
    NOWHERE,
    PASSING,
    PAUSE,
    PAUSED_BEFORE_THE_CHECK,
    PREPARED,
    S3_SECRET,
    _add,
    _add_file_without_bytes,
    _checked,
    _files,
    _migration,
    _sql,
    _steps,
    bucket,
    config_dir,
    migration_enabled,
    scratch_database,
    server_log,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

# The fixtures of the other migration endpoints' tests, which these tests run under as well.
__all__ = ["bucket", "config_dir", "migration_enabled", "scratch_database", "server_log"]

# Most tests here start a real command, and a loaded machine takes its time over one.
pytestmark = pytest.mark.timeout(300)

# Every wait below ends as soon as what it waits for happens. This only bounds a test that is failing.
_TIMEOUT = 120
RUNS = "api/v1/migration/steps/{}/runs"
DECISIONS = "api/v1/migration/decisions"
BACKED_UP = {"location": "s3://backups/langflow", "confirmed_by": "alice", "confirmed_at": "2026-09-30T00:30:00+00:00"}
COPIED = {"ok": True, "revision": "head", "tables_copied": 59, "rows_copied": 48, "orphans": [], "problems": []}
MOVED = {"ok": True, "dry_run": False, "counts": {"relocated": 1}, "attention": []}
UPLOADED = {"ok": True, "dry_run": False, "scope": "all users", "counts": {"copied": 1}, "bytes": 4, "attention": []}
ORPHANS = {"table": "span", "column": "trace_id", "parent": "trace", "ondelete": "CASCADE", "rows": 2}
# What a worker holds of a bucket once its test passed.
S3_KEYS = {"access_key_id": "AKIAEXAMPLE", "secret_access_key": S3_SECRET, "endpoint_url": None, "ca_bundle": None}


@pytest.fixture(autouse=True)
async def no_copy_left_running(config_dir):  # noqa: ARG001
    """A test that failed halfway must not leave a child running, or a run still writing its files."""
    yield
    for run in migration_runs.list_runs():
        await migration_runs.cancel_run(run["run_id"])
        await asyncio.wait_for(_to_its_end(run["run_id"]), _TIMEOUT)


async def _to_its_end(run_id: str) -> None:
    async for _ in migration_runs.follow_run(run_id):
        pass


@pytest.fixture
async def unanswering() -> AsyncIterator[str]:
    """An address that takes a connection and never answers it, so a copy sent there waits until it is stopped."""
    pytest.importorskip("psycopg", reason="needs the postgresql extra")
    held = []
    server = await asyncio.start_server(lambda *connection: held.append(connection), "127.0.0.1", 0)
    host, port = server.sockets[0].getsockname()[:2]
    yield f"{host}:{port}"
    for _, writer in held:
        writer.close()
    server.close()


@pytest.fixture
def at_the_door(monkeypatch: pytest.MonkeyPatch) -> tuple[asyncio.Event, asyncio.Event]:
    """Hold a copy between the check that lets it in and the start of its command, until the test lets it go."""
    arrived, let_go = asyncio.Event(), asyncio.Event()
    start_run = migration_module.start_run

    async def held(*args: Any, **kwargs: Any) -> str:
        arrived.set()
        await let_go.wait()
        return await start_run(*args, **kwargs)

    monkeypatch.setattr(migration_module, "start_run", held)
    return arrived, let_go


def _ready_to_copy(config_dir: Path, **changes: Any) -> None:
    """What the five steps before the copies leave in the record once each of them is done."""
    _checked(config_dir, [PASSING], **{**PREPARED, "pause": PAUSED_BEFORE_THE_CHECK, "backup": BACKED_UP, **changes})


def _ran(config_dir: Path, step: str = "copy_database", **run: Any) -> None:
    """Add to the record a run that has ended, as the endpoints leave one."""
    path = config_dir / "migrations" / "migration.json"
    record = json.loads(path.read_text())
    record["steps"][step] = {
        "run_id": uuid4().hex,
        "status": "done",
        "dry_run": False,
        "started_by": "alice",
        "started_at": "2026-09-30T01:00:00+00:00",
        "finished_at": "2026-09-30T01:05:00+00:00",
        "pause": PAUSED_BEFORE_THE_CHECK["frozen_at"],
        "report": COPIED,
        "error": None,
        "decision_needed": None,
        **run,
    }
    path.write_text(json.dumps(record))


def _failed(code: str, subject: str, kind: str | None = None) -> dict:
    """An item that was not copied, as the record keeps one, with the decision that answers it when one does."""
    return {"code": code, "subject": subject, "decision": kind and {"kind": kind, "subject": subject}}


def _send_to(monkeypatch: pytest.MonkeyPatch, address: str, files: dict | None = None) -> None:
    """Give this worker a destination database, and the keys of a bucket if one is named, as testing them does."""
    url = f"postgresql://migrator:{DB_PASSWORD}@{address}/langflow"
    monkeypatch.setitem(migration_module._secrets, "database_url", url)
    # The worker also keeps which saved destination it holds the secrets of.
    held = {"database": PREPARED["destinations"]["database"]}
    if files:
        monkeypatch.setitem(migration_module._secrets, "files", S3_KEYS)
        held["files"] = files
    monkeypatch.setitem(migration_module._secrets, "for", held)


async def _start(client, headers, step: str = "copy_database", **body: Any) -> str:
    response = await client.post(RUNS.format(step), json=body, headers=headers)
    assert response.status_code == 202, response.text
    return response.json()["run_id"]


async def _events(client, headers, run_id: str, step: str = "copy_database", after: int = 0) -> list[dict]:
    """Every event of a run after the one numbered `after`. The response ends when the run does."""
    response = await client.get(f"{RUNS.format(step)}/{run_id}/events", params={"after": after}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/x-ndjson"
    return [json.loads(event) for event in response.text.split("\n\n") if event]


async def _copy(client, headers, step: str, **body: Any) -> list[dict]:
    """Run a copy to its end, and hand back its events."""
    return await _events(client, headers, await _start(client, headers, step, **body), step)


async def _decide(client, headers, step: str, kind: str, subject: str | None = None, method: str = "POST") -> dict:
    """Record a decision, or withdraw it with DELETE, and hand back what the page is then shown.

    Accepting an item says which report it was read from, as a page that has just loaded the step does.
    """
    decision = {"step": step, "kind": kind, "subject": subject}
    if subject and method == "POST":
        decision["run_id"] = (await _migration(client, headers))["record"]["steps"].get(step, {}).get("run_id")
    response = await client.request(method, DECISIONS, json=decision, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _states(migration: dict) -> dict[str, tuple[str, str | None]]:
    return {step["id"]: (step["state"], step["reason"]) for step in migration["steps"]}


async def _connected(client, headers, config_dir: Path, **destination: Any):
    """Everything before the copies is in the record, and the destination was tested through its own endpoint."""
    _checked(config_dir, [PASSING], secret_key=PREPARED["secret_key"], pause=PAUSED_BEFORE_THE_CHECK, backup=BACKED_UP)
    connected = await client.put("api/v1/migration/destinations", json=destination, headers=headers)
    assert {result["ok"] for result in connected.json()["results"].values()} == {True}, connected.text
    # The endpoint does not say yet which saved destination the worker's secrets are for, so this does.
    saved = connected.json()["record"]["destinations"]
    migration_module._secrets.setdefault("for", {part: saved[part] for part in ("database", "files") if part in saved})
    return connected


async def _knowledge_base(user_id, name: str, chunks: int, *, unit_length: bool = True) -> KnowledgeBaseRecord:
    """A knowledge base on this instance's disk, made the way the app makes one, holding chunks with their vectors."""
    record = await knowledge_base_service.create_record(
        user_id=user_id, name=name, model_selection={"name": "m", "provider": "p"}, chunks=chunks
    )
    backend = await backend_for_record(record)
    try:
        await backend.add_embedded_documents(
            [
                IngestedDocument(
                    id=f"chunk-{number}",
                    content=f"chunk {number}",
                    metadata={"number": number},
                    embedding=[1.0, 0.0, 0.0] if unit_length else [3.0, float(number), 0.0],
                )
                for number in range(chunks)
            ]
        )
    finally:
        await backend.teardown()
    return record


def _stored_file(config_dir: Path, owner, name: str, data: bytes) -> None:
    """A file in this instance's local storage, under the user or the flow it belongs to."""
    (config_dir / str(owner)).mkdir(exist_ok=True)
    (config_dir / str(owner) / name).write_bytes(data)


async def _hang_up_after_the_first_event(client, headers, path: str) -> dict:
    """Follow a run as a raw ASGI client that goes away once the first event has arrived."""
    seen: list[dict] = []
    arrived = asyncio.Event()
    request = [{"type": "http.request", "body": b""}]

    async def receive():
        if request:
            return request.pop()
        await arrived.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        if message["type"] == "http.response.body" and message.get("body"):
            seen.append(json.loads(message["body"]))
            arrived.set()

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [(name.lower().encode(), value.encode()) for name, value in headers.items()],
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
    }
    await asyncio.wait_for(client._transport.app(scope, receive, send), _TIMEOUT)
    return seen[0]


async def test_only_a_superuser_can_run_follow_or_stop_a_copy_or_decide_about_one(client, logged_in_headers):
    run = f"{RUNS.format('copy_database')}/{uuid4().hex}"

    decision = {"step": "copy_database", "kind": "drop_orphans"}

    refused = [
        await client.post(RUNS.format("copy_database"), json={}, headers=logged_in_headers),
        await client.get(f"{run}/events", headers=logged_in_headers),
        await client.delete(run, headers=logged_in_headers),
        await client.post(DECISIONS, json=decision, headers=logged_in_headers),
        await client.request("DELETE", DECISIONS, json=decision, headers=logged_in_headers),
    ]

    assert [response.status_code for response in refused] == [403] * len(refused)


async def test_a_step_that_is_not_a_copy_and_a_run_that_is_not_there_are_not_found(
    client, logged_in_headers_super_user, config_dir
):
    headers = logged_in_headers_super_user
    _ready_to_copy(config_dir)
    never_started = f"{RUNS.format('copy_database')}/{uuid4().hex}"

    missing = [
        await client.post(RUNS.format("backup"), json={}, headers=headers),
        await client.get(f"{never_started}/events", headers=headers),
        await client.delete(never_started, headers=headers),
        # A run's id names its files, so one the runner did not make names nothing.
        await client.get(f"{RUNS.format('copy_database')}/migration.json/events", headers=headers),
    ]

    assert [response.status_code for response in missing] == [404, 404, 404, 404]
    assert [response.json()["detail"]["code"] for response in missing] == ["unknown_step", *["run_not_found"] * 3]


async def test_the_database_copy_has_no_test_run(client, logged_in_headers_super_user, config_dir, monkeypatch):
    headers = logged_in_headers_super_user
    _ready_to_copy(config_dir)
    _send_to(monkeypatch, NOWHERE)

    refused = await client.post(RUNS.format("copy_database"), json={"dry_run": True}, headers=headers)

    assert refused.status_code == 422
    assert refused.json()["detail"] == {"code": "no_dry_run"}
    assert "copy_database" not in (await _migration(client, headers))["record"]["steps"]


async def test_a_copy_waits_for_the_steps_before_it(client, logged_in_headers_super_user, config_dir, monkeypatch):
    headers = logged_in_headers_super_user
    # Checked, connected and the key confirmed, and changes are not paused yet.
    _checked(config_dir, [PASSING], **PREPARED)
    _send_to(monkeypatch, NOWHERE)

    refused = await client.post(RUNS.format("copy_database"), json={}, headers=headers)

    assert refused.status_code == 409
    assert refused.json()["detail"] == {"code": "locked", "reason": "earlier_step"}
    assert "copy_database" not in (await _migration(client, headers))["record"]["steps"]


async def test_a_copy_that_was_made_waits_again_when_a_step_before_it_opens_again(
    client, logged_in_headers_super_user, config_dir, monkeypatch
):
    headers = logged_in_headers_super_user
    # The copy was made. Then the check found something that blocks, so it and the pause are to be gone through again.
    _checked(config_dir, [FAILING], **PREPARED, pause=PAUSED_BEFORE_THE_CHECK, backup=BACKED_UP)
    _ran(config_dir)
    _send_to(monkeypatch, NOWHERE)
    steps = await _steps(client, headers)
    assert (steps["check_source"], steps["pause"]) == (("blocked", "blocking_findings"), ("blocked", "recheck_failed"))
    # The copy keeps saying where it stands, which is what a page draws it from.
    assert steps["copy_database"] == ("done", None)

    refused = await client.post(RUNS.format("copy_database"), json={}, headers=headers)

    assert refused.status_code == 409
    assert refused.json()["detail"] == {"code": "locked", "reason": "earlier_step"}
    assert migration_runs.list_runs() == []


async def test_a_copy_this_instance_does_not_need_is_refused(
    client, logged_in_headers_super_user, config_dir, monkeypatch
):
    _ready_to_copy(config_dir)
    monkeypatch.setattr(get_db_service(), "database_url", "postgresql://db.internal:5432/langflow")

    refused = await client.post(RUNS.format("copy_database"), json={}, headers=logged_in_headers_super_user)

    assert refused.status_code == 409
    assert refused.json()["detail"] == {"code": "skipped", "reason": "already_postgresql"}


@pytest.mark.parametrize(
    "held",
    [
        # After a restart the record still says where the data goes, and the password went with the old process.
        {},
        # Another worker saved another destination since this one tested its own. Its password is for the earlier one.
        {"database_url": f"postgresql://{NOWHERE}/langflow", "for": {"database": {"location": "db.internal/earlier"}}},
    ],
)
async def test_a_copy_needs_the_secrets_of_the_destination_that_is_saved(
    client, logged_in_headers_super_user, config_dir, monkeypatch, held
):
    headers = logged_in_headers_super_user
    _ready_to_copy(config_dir)
    monkeypatch.setattr(migration_module, "_secrets", held)

    refused = await client.post(RUNS.format("copy_database"), json={}, headers=headers)

    assert refused.status_code == 409
    assert refused.json()["detail"] == {"code": "secrets_missing"}
    assert "copy_database" not in (await _migration(client, headers))["record"]["steps"]


async def test_a_copy_the_destination_refuses_blocks_the_step_with_the_commands_own_code(
    client, logged_in_headers_super_user, active_super_user, config_dir, monkeypatch, server_log
):
    headers = logged_in_headers_super_user
    _ready_to_copy(config_dir)
    _send_to(monkeypatch, NOWHERE)

    run_id = await _start(client, headers)
    events = await _events(client, headers, run_id)

    assert [event["seq"] for event in events] == list(range(1, len(events) + 1))
    assert events[0] == {"event": "progress", "phase": "checking", "done": 0, "total": None, "unit": "rows", "seq": 1}
    report, end = events[-2:]
    assert (report["event"], report["ok"]) == ("report", False)
    assert [problem["code"] for problem in report["problems"]] == ["target_unreachable"]
    assert end == {"event": "end", "status": "done", "exit_code": 1, "seq": len(events)}
    # A page that comes back asks for what it has not seen yet.
    assert await _events(client, headers, run_id, after=report["seq"] - 1) == [report, end]
    assert await _events(client, headers, run_id, after=end["seq"]) == []
    # The run is this step's, and is found under no other.
    assert (await client.get(f"{RUNS.format('backup')}/{run_id}/events", headers=headers)).status_code == 404

    # What a page that was reloaded draws the step from, with no event read again.
    migration = await _migration(client, headers)
    run = migration["record"]["steps"]["copy_database"]
    assert run == {
        "run_id": run_id,
        "status": "done",
        "dry_run": False,
        "started_by": "activeuser",
        "started_at": run["started_at"],
        "finished_at": run["finished_at"],
        # The pause that let it in.
        "pause": PAUSED_BEFORE_THE_CHECK["frozen_at"],
        "report": {key: value for key, value in report.items() if key not in ("event", "seq")},
        "error": None,
        "decision_needed": None,
    }
    assert datetime.fromisoformat(run["started_at"]) <= datetime.fromisoformat(run["finished_at"])
    steps = {step["id"]: (step["state"], step["reason"]) for step in migration["steps"]}
    assert steps["copy_database"] == ("blocked", "target_unreachable")
    assert steps["start_target"] == ("locked", "earlier_step")
    started = f"Migration: user_id={active_super_user.id} started the copy of the database (run {run_id})"
    assert started in server_log.getvalue()


@pytest.mark.parametrize(
    ("run", "expected"),
    [
        ({}, ("done", None)),
        # Let in by an earlier pause. It started during this one, which checked and backed up nothing of its own yet.
        ({"pause": "2026-09-28T00:00:00+00:00"}, ("current", None)),
        (
            {"status": "failed", "report": None, "error": {"code": "crashed", "message": "Killed"}},
            ("blocked", "crashed"),
        ),
        ({"status": "cancelled", "report": None, "error": {"code": "cancelled"}}, ("blocked", "cancelled")),
        (
            {"report": {**COPIED, "ok": False, "problems": [{"code": "orphans_droppable", "message": "3 rows"}]}},
            ("blocked", "orphans_droppable"),
        ),
    ],
)
async def test_a_copy_completes_its_step_only_when_this_pause_let_it_in_and_it_reported_ok(
    client, logged_in_headers_super_user, config_dir, run, expected
):
    _ready_to_copy(config_dir)
    _ran(config_dir, **run)

    steps = await _steps(client, logged_in_headers_super_user)

    assert steps["copy_database"] == expected
    # What comes after the copies is not built. It says so once nothing before it is left to do.
    closed = ("locked", "not_available" if expected[0] == "done" else "earlier_step")
    assert (steps["start_target"], steps["check_target"]) == (closed, closed)


async def test_a_copy_from_before_the_pause_was_lifted_has_to_be_made_again(
    client, logged_in_headers_super_user, config_dir
):
    headers = logged_in_headers_super_user
    _ready_to_copy(config_dir)
    _ran(config_dir)
    assert (await _steps(client, headers))["copy_database"] == ("done", None)

    await client.delete("api/v1/migration/pause", headers=headers)

    # Changes are allowed again, so what was copied is no longer all of it. The pause comes first once more.
    steps = await _steps(client, headers)
    assert steps["pause"] == ("current", None)
    assert steps["copy_database"] == ("locked", "earlier_step")


@pytest.mark.parametrize(
    ("change", "pause", "copy"),
    [
        ("changes turned back on", ("current", None), ("locked", "earlier_step")),
        # The new pause has checked and backed up nothing yet, so no copy can stand for it.
        ("paused again", ("blocked", "recheck_pending"), ("locked", "earlier_step")),
        ("another database saved", ("done", None), ("current", None)),
    ],
)
async def test_a_copy_is_stopped_as_it_starts_when_what_let_it_in_has_changed(
    client,
    logged_in_headers_super_user,
    active_super_user,
    config_dir,
    monkeypatch,
    at_the_door,
    server_log,
    change,
    pause,
    copy,
):
    headers = logged_in_headers_super_user
    arrived, let_go = at_the_door
    _ready_to_copy(config_dir)
    _send_to(monkeypatch, NOWHERE)
    starting = asyncio.create_task(client.post(RUNS.format("copy_database"), json={}, headers=headers))
    await asyncio.wait_for(arrived.wait(), _TIMEOUT)

    # The copy was let in, and its command has not started yet.
    if change == "another database saved":
        path = config_dir / "migrations" / "migration.json"
        record = json.loads(path.read_text())
        record["destinations"]["database"] = {"location": "db.internal:5432/another"}
        path.write_text(json.dumps(record))
    else:
        await client.delete(PAUSE, headers=headers)
    if change == "paused again":
        assert (await client.post(PAUSE, headers=headers)).status_code == 200
    let_go.set()
    refused = await asyncio.wait_for(starting, _TIMEOUT)

    assert refused.status_code == 409
    assert refused.json()["detail"] == {"code": "state_changed"}
    # The command had started by then, and was stopped. The record keeps nothing of it.
    [run] = migration_runs.list_runs()
    assert run["status"] == "cancelled"
    stopped = "after what let it in had changed, so it was stopped"
    started = f"Migration: user_id={active_super_user.id} started the copy of the database"
    assert f"{started} {stopped} (run {run['run_id']})" in server_log.getvalue()
    migration = await _migration(client, headers)
    assert "copy_database" not in migration["record"]["steps"]
    steps = {step["id"]: (step["state"], step["reason"]) for step in migration["steps"]}
    assert (steps["pause"], steps["copy_database"]) == (pause, copy)


async def test_a_copy_start_does_not_put_back_a_pause_that_another_worker_ended_under_it(
    client, logged_in_headers_super_user, config_dir, monkeypatch
):
    headers = logged_in_headers_super_user
    _ready_to_copy(config_dir)
    _send_to(monkeypatch, NOWHERE)
    read_run, resumed = migration_module.read_run, []

    def read_run_after_a_resume(run_id: str) -> dict:
        # Another worker turns changes back on at this point: after this request read the record for
        # the last time, and before it saves its run into it.
        if not resumed:
            theirs = migration_module._read_record()
            resumed.append(theirs.pop("pause"))
            migration_module._write_record(theirs)
        return read_run(run_id)

    monkeypatch.setattr(migration_module, "read_run", read_run_after_a_resume)

    refused = await asyncio.wait_for(client.post(RUNS.format("copy_database"), json={}, headers=headers), _TIMEOUT)

    assert resumed
    assert refused.status_code == 409, refused.text
    assert refused.json()["detail"] == {"code": "state_changed"}
    # The command had started, and was stopped.
    [run] = migration_runs.list_runs()
    assert run["status"] == "cancelled"
    migration = await _migration(client, headers)
    # The other worker's word stands: this request's save did not put the pause back.
    assert "pause" not in migration["record"]
    assert "copy_database" not in migration["record"]["steps"]


async def test_a_copy_start_whose_save_is_refused_every_time_stops_the_command_it_started(
    client, logged_in_headers_super_user, config_dir, monkeypatch
):
    headers = logged_in_headers_super_user
    _ready_to_copy(config_dir)
    _send_to(monkeypatch, NOWHERE)
    read_run, saves = migration_module.read_run, []

    def read_run_while_another_worker_saves(run_id: str) -> dict:
        # At each look another worker saves something that changes neither the pause nor the destination.
        theirs = migration_module._read_record()
        theirs["backup"]["location"] = f"place {len(saves)}"
        migration_module._write_record(theirs)
        saves.append(run_id)
        return read_run(run_id)

    monkeypatch.setattr(migration_module, "read_run", read_run_while_another_worker_saves)
    refused = await asyncio.wait_for(client.post(RUNS.format("copy_database"), json={}, headers=headers), _TIMEOUT)
    monkeypatch.setattr(migration_module, "read_run", read_run)

    assert len(saves) == migration_module._SAVE_TRIES
    assert refused.status_code == 409, refused.text
    assert refused.json()["detail"] == {"code": "record_changed"}
    # The record says nothing of the command, so nothing could follow it or stop it later. It was stopped here.
    await asyncio.wait_for(_to_its_end(saves[0]), _TIMEOUT)
    [run] = migration_runs.list_runs()
    assert run["status"] == "cancelled"
    assert "copy_database" not in (await _migration(client, headers))["record"]["steps"]


def test_a_save_waits_for_another_worker_that_is_in_the_middle_of_its_save(client, config_dir):  # noqa: ARG001
    fcntl = pytest.importorskip("fcntl")
    _ready_to_copy(config_dir)
    record = migration_module._read_record()
    saved_before = record.get("generation", 0)
    # Another worker is between its look at the record and its write: it holds the lock that every save takes.
    theirs = os.open(config_dir / "migrations" / "migration.lock", os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(theirs, fcntl.LOCK_EX)
    saving = threading.Thread(target=migration_module._write_record, args=(record,), daemon=True)
    try:
        saving.start()
        saving.join(0.5)

        assert saving.is_alive()
        assert migration_module._read_record().get("generation", 0) == saved_before
    finally:
        os.close(theirs)
    saving.join(10)
    assert not saving.is_alive()
    assert migration_module._read_record()["generation"] == saved_before + 1


def test_a_save_of_a_record_that_another_worker_saved_since_is_refused(client, config_dir):  # noqa: ARG001
    _ready_to_copy(config_dir)
    mine, theirs = migration_module._read_record(), migration_module._read_record()
    del theirs["pause"]
    migration_module._write_record(theirs)
    mine["backup"]["location"] = "another place"

    with pytest.raises(HTTPException) as refused:
        migration_module._write_record(mine)

    assert refused.value.status_code == 409
    assert refused.value.detail == {"code": "record_changed"}
    saved = migration_module._read_record()
    assert "pause" not in saved
    assert saved["backup"]["location"] != "another place"


async def test_turning_changes_back_on_is_done_again_on_what_another_worker_saved_meanwhile(
    client, logged_in_headers_super_user, config_dir, monkeypatch
):
    headers = logged_in_headers_super_user
    _ready_to_copy(config_dir)
    read_record, saved_meanwhile = migration_module._read_record, []

    def read_and_let_another_worker_save() -> dict:
        record = read_record()
        if not saved_meanwhile:
            # Another worker saves where the backup is, just after this request has read the record.
            saved_meanwhile.append(True)
            theirs = read_record()
            theirs["backup"]["location"] = "another place"
            migration_module._write_record(theirs)
        return record

    monkeypatch.setattr(migration_module, "_read_record", read_and_let_another_worker_save)

    resumed = await client.delete(PAUSE, headers=headers)

    assert resumed.status_code == 200, resumed.text
    record = resumed.json()["record"]
    # Both stand: the pause is over, and what the other worker saved is kept.
    assert "pause" not in record
    assert record["backup"]["location"] == "another place"


async def test_a_run_whose_files_are_gone_reads_as_interrupted(client, logged_in_headers_super_user, config_dir):
    headers = logged_in_headers_super_user
    _ready_to_copy(config_dir)
    # What a server that lost its disk mid-run finds in the record when it comes back.
    _ran(config_dir, status="running", finished_at=None, report=None)

    migration = await _migration(client, headers)

    run = migration["record"]["steps"]["copy_database"]
    assert (run["status"], run["error"]) == ("interrupted", {"code": "interrupted"})
    assert {step["id"]: step["reason"] for step in migration["steps"]}["copy_database"] == "interrupted"
    # Written down, so the next reader does not have to work it out again.
    saved = json.loads((config_dir / "migrations" / "migration.json").read_text())
    assert saved["steps"]["copy_database"]["status"] == "interrupted"


async def test_how_a_copy_ended_is_not_saved_over_a_newer_run_that_another_worker_started(
    client, logged_in_headers_super_user, config_dir, monkeypatch
):
    headers = logged_in_headers_super_user
    _ready_to_copy(config_dir)
    older, newer = "a" * 32, "b" * 32
    _ran(config_dir, run_id=older, status="running", finished_at=None, report=None)
    started = []

    def read_run_after_another_worker_started_a_copy(run_id: str) -> dict:
        # After this request read the record, another worker found the older run over and started a newer one.
        if not started:
            theirs = migration_module._read_record()
            theirs["steps"]["copy_database"] = {**theirs["steps"]["copy_database"], "run_id": newer}
            migration_module._write_record(theirs)
            started.append(newer)
        raise migration_runs.RunNotFoundError(run_id)

    monkeypatch.setattr(migration_module, "read_run", read_run_after_another_worker_started_a_copy)
    await _migration(client, headers)

    assert started
    saved = migration_module._read_record()["steps"]["copy_database"]
    # The newer run is still the one the record names, so a page can still follow it and stop it.
    assert (saved["run_id"], saved["status"]) == (newer, "running")


async def test_while_a_copy_runs_a_second_one_is_refused(
    client, logged_in_headers_super_user, config_dir, monkeypatch, unanswering
):
    headers = logged_in_headers_super_user
    _ready_to_copy(config_dir)
    _send_to(monkeypatch, unanswering)
    run_id = await _start(client, headers)

    refused = await client.post(RUNS.format("copy_database"), json={}, headers=headers)

    assert refused.status_code == 409
    assert refused.json()["detail"] == {"code": "run_active"}
    migration = await _migration(client, headers)
    run = migration["record"]["steps"]["copy_database"]
    assert (run["run_id"], run["status"], run["finished_at"]) == (run_id, "running", None)
    assert {step["id"]: step["state"] for step in migration["steps"]}["copy_database"] == "current"
    # Any user of the machine can read a command line. The address, with its password, is not on this one.
    command = psutil.Process(migration_runs.read_run(run_id)["child"]["pid"]).cmdline()
    assert command[1:] == ["-m", "langflow", "convert-sqlite-to-postgres", "--json"]


async def test_a_running_copy_can_still_be_followed_and_stopped_when_a_step_before_it_opens_again(
    client, logged_in_headers_super_user, config_dir, monkeypatch, unanswering
):
    headers = logged_in_headers_super_user
    _ready_to_copy(config_dir)
    _send_to(monkeypatch, unanswering)
    run_id = await _start(client, headers)

    resumed = await client.delete(PAUSE, headers=headers)

    assert resumed.status_code == 200, resumed.text
    steps = await _steps(client, headers)
    assert steps["pause"] == ("current", None)
    # Its command still writes to the destination, so the page still draws the copy, with its stop.
    assert steps["copy_database"] == ("current", None)
    refused = await client.post(RUNS.format("copy_database"), json={}, headers=headers)
    assert refused.status_code == 409
    assert refused.json()["detail"] == {"code": "locked", "reason": "earlier_step"}

    stopped = await client.delete(f"{RUNS.format('copy_database')}/{run_id}", headers=headers)

    assert stopped.status_code == 202
    await asyncio.wait_for(_to_its_end(run_id), _TIMEOUT)
    assert (await _steps(client, headers))["copy_database"] == ("locked", "earlier_step")


async def test_a_page_that_goes_away_leaves_the_copy_running_until_it_is_stopped(
    client, logged_in_headers_super_user, active_super_user, config_dir, monkeypatch, unanswering, server_log
):
    headers = logged_in_headers_super_user
    _ready_to_copy(config_dir)
    _send_to(monkeypatch, unanswering)
    run_id = await _start(client, headers)
    run = f"{RUNS.format('copy_database')}/{run_id}"

    first = await _hang_up_after_the_first_event(client, headers, f"/{run}/events")

    assert first == {"event": "progress", "phase": "checking", "done": 0, "total": None, "unit": "rows", "seq": 1}
    assert migration_runs.read_run(run_id)["status"] == "running"

    # The page comes back, asks for what it has not seen, and stops the copy.
    following = asyncio.create_task(_events(client, headers, run_id, after=first["seq"]))
    stopped = await client.delete(run, headers=headers)

    assert stopped.status_code == 202
    assert stopped.json() == {"run_id": run_id}
    rest = await asyncio.wait_for(following, _TIMEOUT)
    assert [(event["event"], event["seq"], event["status"]) for event in rest] == [("end", 2, "cancelled")]
    migration = await _migration(client, headers)
    kept = migration["record"]["steps"]["copy_database"]
    assert (kept["status"], kept["report"], kept["error"]) == ("cancelled", None, {"code": "cancelled"})
    assert {step["id"]: (step["state"], step["reason"]) for step in migration["steps"]}["copy_database"] == (
        "blocked",
        "cancelled",
    )
    stopped_by = f"Migration: user_id={active_super_user.id} stopped the copy of the database (run {run_id})"
    assert stopped_by in server_log.getvalue()
    # Stopping a run that is over is not an error, and there is nothing to log.
    assert (await client.delete(run, headers=headers)).status_code == 202
    assert server_log.getvalue().count("stopped the copy") == 1


async def test_the_database_is_copied_and_the_step_is_done(
    client, logged_in_headers_super_user, config_dir, scratch_database
):
    headers = logged_in_headers_super_user
    await _connected(client, headers, config_dir, database_url=scratch_database.render_as_string(hide_password=False))
    assert (await _steps(client, headers))["copy_database"] == ("current", None)

    run_id = await _start(client, headers)
    events = await _events(client, headers, run_id)

    report, end = events[-2:]
    assert (report["event"], report["ok"]) == ("report", True), report
    assert (end["status"], end["exit_code"]) == ("done", 0)
    copied = [event["item"] for event in events if event["event"] == "item"]
    engine = sa.create_engine(scratch_database)
    with engine.connect() as destination:
        assert destination.scalars(sa.text('SELECT username FROM "user"')).all().count("activeuser") == 1
    engine.dispose()
    migration = await _migration(client, headers)
    run = migration["record"]["steps"]["copy_database"]
    assert (run["status"], run["error"]) == ("done", None)
    assert run["report"]["tables_copied"] == len(copied) > 0
    assert run["report"]["rows_copied"] == sum(table["target_rows"] for table in copied) > 0
    steps = {step["id"]: (step["state"], step["reason"]) for step in migration["steps"]}
    assert steps["copy_database"] == ("done", None)
    # This instance keeps nothing else on its own disk, and what follows the copies is not built.
    assert steps["copy_knowledge_bases"] == ("skipped", "no_local_knowledge_bases")
    assert steps["copy_files"] == ("skipped", "no_local_files")
    assert steps["start_target"] == ("locked", "not_available")


def _command_line(run_id: str) -> str:
    """The command line of a run's child, which any user of the machine can read while it runs."""
    command = " ".join(psutil.Process(migration_runs.read_run(run_id)["child"]["pid"]).cmdline())
    # Read while the command was still starting, or there would be nothing here to search.
    assert "-m langflow" in command
    return command


def _nowhere(secrets: list[str], command: str, responses: list, config_dir: Path, server_log, caplog, capfd) -> None:
    """Assert that no secret is on the command line, in a response, in a file under CONFIG_DIR or in a log.

    CONFIG_DIR holds the record, and the status and the events of every run. It is also where Langflow
    keeps this instance's key, in a file that any command given the key writes again.
    """
    printed = capfd.readouterr()
    kept = [path for path in config_dir.rglob("*") if path.is_file() and path != config_dir / "secret_key"]
    shown = {
        "the command line": command,
        **{f"response {number}": response.text for number, response in enumerate(responses)},
        **{str(path): path.read_text(errors="replace") for path in kept},
        "the migration log": server_log.getvalue(),
        "the other logs": caplog.text,
        "stdout": printed.out,
        "stderr": printed.err,
    }
    assert [where for where, text in shown.items() if any(secret in text for secret in secrets)] == []


async def test_a_copy_that_fails_gives_no_password_or_key_away(
    client, logged_in_headers_super_user, config_dir, monkeypatch, server_log, caplog, capfd
):
    headers = logged_in_headers_super_user
    caplog.set_level("DEBUG")
    key = migration_module.get_settings_service().auth_settings.SECRET_KEY.get_secret_value()
    _ready_to_copy(config_dir)
    _send_to(monkeypatch, NOWHERE)

    started = await client.post(RUNS.format("copy_database"), json={}, headers=headers)
    run_id = started.json()["run_id"]
    command = _command_line(run_id)
    responses = [
        started,
        await client.get(f"{RUNS.format('copy_database')}/{run_id}/events", headers=headers),
        await client.get("api/v1/migration", headers=headers),
    ]

    assert '"target_unreachable"' in responses[1].text
    _nowhere([DB_PASSWORD, key], command, responses, config_dir, server_log, caplog, capfd)


async def test_a_copy_that_succeeds_gives_no_password_or_key_away(
    client, logged_in_headers_super_user, config_dir, scratch_database, server_log, caplog, capfd
):
    headers = logged_in_headers_super_user
    caplog.set_level("DEBUG")
    key = migration_module.get_settings_service().auth_settings.SECRET_KEY.get_secret_value()
    url = scratch_database.set(password=scratch_database.password or DB_PASSWORD)
    connected = await _connected(client, headers, config_dir, database_url=url.render_as_string(hide_password=False))

    started = await client.post(RUNS.format("copy_database"), json={}, headers=headers)
    run_id = started.json()["run_id"]
    command = _command_line(run_id)
    responses = [
        connected,
        started,
        await client.get(f"{RUNS.format('copy_database')}/{run_id}/events", headers=headers),
        await client.get("api/v1/migration", headers=headers),
    ]

    assert responses[3].json()["record"]["steps"]["copy_database"]["report"]["ok"] is True
    _nowhere([url.password, key], command, responses, config_dir, server_log, caplog, capfd)


async def _three_copies_to_make(config_dir: Path, user_id) -> None:
    """An instance that keeps a knowledge base and a file on its own disk, with every step before the copies done."""
    await _add(KnowledgeBaseRecord(user_id=user_id, name="handbook", backend_type="sqlite"))
    await _add_file_without_bytes(user_id)
    parts = {"vectors": {"kind": "pgvector"}, "files": {"bucket": "acme", "prefix": "files", "endpoint_url": None}}
    results = {part: {"ok": True} for part in ("database", "vectors", "files")}
    _ready_to_copy(config_dir, destinations={**PREPARED["destinations"], **parts, "results": results})


async def test_a_file_copy_needs_the_keys_of_the_bucket_that_is_saved(
    client, logged_in_headers_super_user, active_super_user, config_dir, monkeypatch
):
    await _three_copies_to_make(config_dir, active_super_user.id)
    _ran(config_dir)
    _ran(config_dir, "copy_knowledge_bases", report=MOVED)
    # This worker tested another bucket than the one that is saved now, and its keys are for that one.
    _send_to(monkeypatch, NOWHERE, files={"bucket": "earlier", "prefix": "files", "endpoint_url": None})

    refused = await client.post(RUNS.format("copy_files"), json={}, headers=logged_in_headers_super_user)

    assert refused.status_code == 409
    assert refused.json()["detail"] == {"code": "secrets_missing"}
    assert migration_runs.list_runs() == []


async def test_a_copy_that_was_made_waits_again_when_the_copy_before_it_is_no_longer_done(
    client, logged_in_headers_super_user, active_super_user, config_dir, monkeypatch
):
    headers = logged_in_headers_super_user
    await _three_copies_to_make(config_dir, active_super_user.id)
    _ran(config_dir)
    _ran(config_dir, "copy_knowledge_bases", report=MOVED)
    # The database was copied again, and that copy died.
    _ran(config_dir, status="failed", report=None, error={"code": "crashed", "message": "Killed"})
    _send_to(monkeypatch, NOWHERE)
    steps = await _steps(client, headers)
    assert (steps["copy_database"], steps["copy_knowledge_bases"]) == (("blocked", "crashed"), ("done", None))

    refused = await client.post(RUNS.format("copy_knowledge_bases"), json={}, headers=headers)

    assert refused.status_code == 409
    assert refused.json()["detail"] == {"code": "locked", "reason": "earlier_step"}
    assert migration_runs.list_runs() == []


async def test_on_postgresql_a_copy_of_the_knowledge_bases_is_refused_without_the_store_whatever_its_step_reads(
    client, logged_in_headers_super_user, active_super_user, config_dir, monkeypatch
):
    headers = logged_in_headers_super_user
    await _add(KnowledgeBaseRecord(user_id=active_super_user.id, name="handbook", backend_type="sqlite"))
    _ready_to_copy(config_dir, destinations={"vectors": {"kind": "pgvector"}, "results": {"vectors": {"ok": True}}})
    monkeypatch.setattr(get_db_service(), "database_url", f"postgresql://{NOWHERE}/langflow")
    # The copy was made while the server named its store. Then the server was started again without it.
    _ran(config_dir, "copy_knowledge_bases", report=MOVED)
    monkeypatch.delenv("PGVECTOR_CONNECTION_STRING", raising=False)
    assert (await _steps(client, headers))["copy_knowledge_bases"] == ("done", None)

    refused = await client.post(RUNS.format("copy_knowledge_bases"), json={}, headers=headers)

    assert (refused.status_code, refused.json()) == (409, {"detail": {"code": "pgvector_env_missing"}})
    assert migration_runs.list_runs() == []


@pytest.mark.parametrize(
    ("named", "step", "answer"),
    [
        # After the copy every knowledge base is in pgvector, and this server would have no way to open one.
        (False, ("blocked", "pgvector_env_missing"), (409, {"detail": {"code": "pgvector_env_missing"}})),
        (True, ("current", None), (202, None)),
    ],
)
async def test_on_postgresql_the_knowledge_bases_are_copied_only_when_this_server_can_read_them_there(
    client, logged_in_headers_super_user, active_super_user, config_dir, monkeypatch, named, step, answer
):
    headers = logged_in_headers_super_user
    await _add(KnowledgeBaseRecord(user_id=active_super_user.id, name="handbook", backend_type="sqlite"))
    _ready_to_copy(config_dir, destinations={"vectors": {"kind": "pgvector"}, "results": {"vectors": {"ok": True}}})
    # An instance already on PostgreSQL keeps its database. Its knowledge bases go into it, and it serves on from it.
    own = f"postgresql://{NOWHERE}/langflow"
    monkeypatch.setattr(get_db_service(), "database_url", own)
    # The server reads pgvector knowledge bases from the store its own environment names, and from no other.
    # That store need not be its database.
    store = f"postgresql://{NOWHERE}/vectors"
    if named:
        monkeypatch.setenv("PGVECTOR_CONNECTION_STRING", store)
    else:
        monkeypatch.delenv("PGVECTOR_CONNECTION_STRING", raising=False)

    steps = await _steps(client, headers)
    started = await client.post(RUNS.format("copy_knowledge_bases"), json={}, headers=headers)
    if named:
        # The copy writes where this server reads: it is given the server's own store, and the database to work on.
        given = psutil.Process(migration_runs.read_run(started.json()["run_id"])["child"]["pid"]).environ()
        assert (given["LANGFLOW_DATABASE_URL"], given["PGVECTOR_CONNECTION_STRING"]) == (own, store)
        # It reads that store as the server does, so it is told not to count what it skips.
        assert "--no-verify-skipped" in _command_line(started.json()["run_id"])

    assert (steps["copy_database"], steps["copy_knowledge_bases"]) == (("skipped", "already_postgresql"), step)
    status, refusal = answer
    assert started.status_code == status
    assert refusal is None or started.json() == refusal
    assert len(migration_runs.list_runs()) == (1 if named else 0)


async def test_each_copy_waits_for_the_one_before_it_and_a_test_run_completes_nothing(
    client, logged_in_headers_super_user, active_super_user, config_dir
):
    headers = logged_in_headers_super_user
    await _three_copies_to_make(config_dir, active_super_user.id)

    async def copies() -> list[tuple[str, str | None]]:
        steps = await _steps(client, headers)
        return [steps[step] for step in ("copy_database", "copy_knowledge_bases", "copy_files", "start_target")]

    waiting, closed = ("locked", "earlier_step"), ("locked", "not_available")
    assert await copies() == [("current", None), waiting, waiting, waiting]
    _ran(config_dir)
    assert await copies() == [("done", None), ("current", None), waiting, waiting]
    _ran(config_dir, "copy_knowledge_bases", report=MOVED)
    assert await copies() == [("done", None), ("done", None), ("current", None), waiting]
    # A test run says what a copy would do. The step is still to do.
    _ran(config_dir, "copy_files", dry_run=True, report={**UPLOADED, "dry_run": True, "counts": {"would_copy": 1}})
    assert await copies() == [("done", None), ("done", None), ("current", None), waiting]
    missing = _failed("no_source_bytes", f"{active_super_user.id}/gone.txt", "accept_missing_attachment")
    _ran(config_dir, "copy_files", report={**UPLOADED, "ok": False, "counts": {"failed": 1}, "attention": [missing]})
    assert await copies() == [("done", None), ("done", None), ("blocked", "no_source_bytes"), waiting]
    _ran(config_dir, "copy_files", report=UPLOADED)
    assert await copies() == [("done", None), ("done", None), ("done", None), closed]


async def test_the_copies_after_the_database_are_to_be_made_again_once_it_is_copied_again(
    client, logged_in_headers_super_user, active_super_user, config_dir
):
    headers = logged_in_headers_super_user
    await _three_copies_to_make(config_dir, active_super_user.id)
    _ran(config_dir)
    _ran(config_dir, "copy_knowledge_bases", report=MOVED, started_at="2026-09-30T01:10:00+00:00")
    _ran(config_dir, "copy_files", report=UPLOADED, started_at="2026-09-30T01:20:00+00:00")

    async def copies() -> list[tuple[str, str | None]]:
        steps = await _steps(client, headers)
        return [steps[step] for step in ("copy_database", "copy_knowledge_bases", "copy_files")]

    assert await copies() == [("done", None), ("done", None), ("done", None)]

    # The database copy writes every row again, and with them what the other two had changed in the destination:
    # where each knowledge base is kept, and how chat history names its attachments.
    _ran(config_dir, started_at="2026-09-30T02:00:00+00:00")

    assert await copies() == [("done", None), ("current", None), ("locked", "earlier_step")]
    _ran(config_dir, "copy_knowledge_bases", report=MOVED, started_at="2026-09-30T02:10:00+00:00")
    assert await copies() == [("done", None), ("done", None), ("current", None)]
    _ran(config_dir, "copy_files", report=UPLOADED, started_at="2026-09-30T02:20:00+00:00")
    assert await copies() == [("done", None), ("done", None), ("done", None)]


async def test_a_copy_that_dies_without_reporting_blocks_the_step_as_crashed(
    client, logged_in_headers_super_user, active_super_user, config_dir, monkeypatch, server_log, caplog, capfd
):
    headers = logged_in_headers_super_user
    caplog.set_level("DEBUG")
    await _add_file_without_bytes(active_super_user.id)
    files = {"bucket": "acme", "prefix": "files", "endpoint_url": None}
    results = {"database": {"ok": True}, "files": {"ok": True}}
    _ready_to_copy(config_dir, destinations={**PREPARED["destinations"], "files": files, "results": results})
    _ran(config_dir)
    # The database the files are filed in went away after it was copied to.
    _send_to(monkeypatch, NOWHERE, files)

    started = await client.post(RUNS.format("copy_files"), json={}, headers=headers)
    run_id = started.json()["run_id"]
    command = _command_line(run_id)
    events = await _events(client, headers, run_id, "copy_files")

    assert events[-1] == {"event": "end", "status": "failed", "exit_code": 1, "seq": len(events)}
    assert "report" not in [event["event"] for event in events]
    shown = await client.get("api/v1/migration", headers=headers)
    run = shown.json()["record"]["steps"]["copy_files"]
    assert (run["status"], run["report"], run["error"]["code"]) == ("failed", None, "crashed")
    # All there is to go on is what the command last wrote to stderr.
    assert run["error"]["message"].strip()
    assert {step["id"]: step["reason"] for step in shown.json()["steps"]}["copy_files"] == "crashed"
    assert command.endswith("relocate-files --json --bucket acme --prefix files")
    # A traceback is where an address would show, with its password.
    _nowhere(
        [DB_PASSWORD, S3_SECRET, S3_KEYS["access_key_id"]],
        command,
        [started, shown],
        config_dir,
        server_log,
        caplog,
        capfd,
    )


async def test_a_knowledge_base_kept_in_this_servers_own_pgvector_store_blocks_the_step(
    client, logged_in_headers_super_user, active_super_user, config_dir, scratch_database, monkeypatch
):
    pytest.importorskip("pgvector", reason="needs the pgvector extra")
    headers, user = logged_in_headers_super_user, active_super_user.id
    # This server keeps "remote" in a pgvector store of its own, which no copy is given.
    monkeypatch.setenv("PGVECTOR_CONNECTION_STRING", f"postgresql://{NOWHERE}/vectors")
    remote = uuid4()
    await _add(KnowledgeBaseRecord(id=remote, user_id=user, name="remote", backend_type="postgres", chunks=36))
    await _knowledge_base(user, "local", 5)
    _sql(scratch_database, "CREATE EXTENSION vector")
    address = scratch_database.render_as_string(hide_password=False)
    await _connected(client, headers, config_dir, database_url=address, vectors={"kind": "pgvector"})
    await _copy(client, headers, "copy_database")

    # A test run says so before anything is copied.
    *_, tested, _ = await _copy(client, headers, "copy_knowledge_bases", dry_run=True)
    assert (tested["ok"], tested["counts"]) == (False, {"would_relocate": 1, "failed": 1})

    *_, report, end = await _copy(client, headers, "copy_knowledge_bases")

    assert (report["ok"], report["counts"]) == (False, {"relocated": 1, "failed": 1})
    # The command ended as it should, with one item failed. The step waits on that item.
    assert (end["status"], end["exit_code"]) == ("done", 1)
    migration = await _migration(client, headers)
    [left] = migration["record"]["steps"]["copy_knowledge_bases"]["report"]["attention"]
    assert (left["kb_id"], left["kb_name"], left["code"]) == (str(remote), "remote", "kb_target_short")
    assert "0 of its 36" in left["reason"]
    steps = {step["id"]: (step["state"], step["reason"]) for step in migration["steps"]}
    assert steps["copy_knowledge_bases"] == ("blocked", "kb_target_short")

    # "local" is in the destination by now, so a second copy skips it. "remote" is still not there.
    *_, again, _ = await _copy(client, headers, "copy_knowledge_bases")
    assert (again["ok"], again["counts"]) == (False, {"skipped": 1, "failed": 1})
    assert (await _steps(client, headers))["copy_knowledge_bases"] == ("blocked", "kb_target_short")


async def test_knowledge_bases_are_copied_into_the_destination_and_this_instance_keeps_its_own(
    client, logged_in_headers_super_user, active_super_user, config_dir, scratch_database
):
    pytest.importorskip("pgvector", reason="needs the pgvector extra")
    headers = logged_in_headers_super_user
    handbook = await _knowledge_base(active_super_user.id, "handbook", 12)
    _sql(scratch_database, "CREATE EXTENSION vector")
    # Spelled for another driver, as an address copied from somewhere else can be. The test of the
    # destination reads it all the same, and so do the copies.
    address = scratch_database.set(drivername="postgresql+asyncpg").render_as_string(hide_password=False)
    await _connected(client, headers, config_dir, database_url=address, vectors={"kind": "pgvector"})
    assert (await _steps(client, headers))["copy_knowledge_bases"] == ("locked", "earlier_step")
    await _copy(client, headers, "copy_database")

    # A test run first. It says what a copy would do, and the step is still to do.
    *_, tested, _ = await _copy(client, headers, "copy_knowledge_bases", dry_run=True)

    assert (tested["ok"], tested["dry_run"], tested["counts"]) == (True, True, {"would_relocate": 1})
    migration = await _migration(client, headers)
    assert migration["record"]["steps"]["copy_knowledge_bases"]["dry_run"] is True
    assert {step["id"]: step["state"] for step in migration["steps"]}["copy_knowledge_bases"] == "current"

    events = await _copy(client, headers, "copy_knowledge_bases")

    report, end = events[-2:]
    assert (report["ok"], report["dry_run"], report["counts"], report["attention"]) == (
        True,
        False,
        {"relocated": 1},
        [],
    )
    assert (end["status"], end["exit_code"]) == ("done", 0)
    progress = [event for event in events if event["event"] == "progress"][-1]
    assert (progress["done"], progress["total"], progress["subject"]) == (12, 12, str(handbook.id))
    engine = sa.create_engine(scratch_database)
    with engine.connect() as destination:
        assert destination.scalars(sa.text("SELECT backend_type FROM knowledge_base")).all() == ["postgres"]
        [table] = [name for name in sa.inspect(destination).get_table_names() if name.startswith("lf_")]
        assert destination.scalar(sa.text(f'SELECT count(*) FROM "{table}"')) == 12  # noqa: S608
    engine.dispose()
    # This instance was only read. It still serves the knowledge base from its own disk.
    async with session_scope() as session:
        assert (await session.get(KnowledgeBaseRecord, handbook.id)).backend_type == "sqlite"
    migration = await _migration(client, headers)
    run = migration["record"]["steps"]["copy_knowledge_bases"]
    assert (run["status"], run["dry_run"], run["report"]["counts"]) == ("done", False, {"relocated": 1})
    steps = {step["id"]: (step["state"], step["reason"]) for step in migration["steps"]}
    assert steps["copy_knowledge_bases"] == ("done", None)
    assert steps["copy_files"] == ("skipped", "no_local_files")
    assert steps["start_target"] == ("locked", "not_available")

    # Copying the database again writes this instance's rows over the destination's, so the knowledge base
    # there is said to be on local disk once more. Its copy is to be made again, which puts that right.
    await _copy(client, headers, "copy_database")

    def kept_in() -> list[str]:
        engine = sa.create_engine(scratch_database)
        with engine.connect() as destination:
            return destination.scalars(sa.text("SELECT backend_type FROM knowledge_base")).all()

    assert kept_in() == ["sqlite"]
    assert (await _steps(client, headers))["copy_knowledge_bases"] == ("current", None)
    *_, again, _ = await _copy(client, headers, "copy_knowledge_bases")
    assert (again["ok"], again["counts"]) == (True, {"relocated": 1})
    assert kept_in() == ["postgres"]
    assert (await _steps(client, headers))["copy_knowledge_bases"] == ("done", None)


async def test_a_knowledge_base_that_cannot_be_copied_blocks_the_step_until_the_admin_decides(
    client, logged_in_headers_super_user, active_super_user, config_dir, scratch_database
):
    pytest.importorskip("pgvector", reason="needs the pgvector extra")
    headers, user = logged_in_headers_super_user, active_super_user.id
    await _knowledge_base(user, "handbook", 5)
    # Vectors that are not unit length rank differently under the destination's metric, so the copy asks first.
    notes = await _knowledge_base(user, "notes", 5, unit_length=False)
    # A knowledge base in a store this Langflow has no backend for cannot be read, so it cannot be copied.
    elsewhere = uuid4()
    await _add(KnowledgeBaseRecord(id=elsewhere, user_id=user, name="elsewhere", backend_type="astra"))
    # Nor is one whose store holds fewer chunks than its row says. The command leaves that for someone to look at.
    thin = await _knowledge_base(user, "thin", 3)
    async with session_scope() as session:
        (await session.get(KnowledgeBaseRecord, thin.id)).chunks = 9
        await session.commit()
    _sql(scratch_database, "CREATE EXTENSION vector")
    address = scratch_database.render_as_string(hide_password=False)
    await _connected(client, headers, config_dir, database_url=address, vectors={"kind": "pgvector"})
    await _copy(client, headers, "copy_database")

    *_, report, end = await _copy(client, headers, "copy_knowledge_bases")

    assert (report["ok"], report["counts"]) == (False, {"relocated": 1, "failed": 3})
    assert (end["status"], end["exit_code"]) == ("done", 1)
    migration = await _migration(client, headers)
    # The record keeps each knowledge base that needs attention, with what the command said about it.
    failed = {
        item["kb_name"]: item for item in migration["record"]["steps"]["copy_knowledge_bases"]["report"]["attention"]
    }
    assert {name: (item["subject"], item["code"]) for name, item in failed.items()} == {
        "notes": (str(notes.id), "kb_metric_change"),
        "elsewhere": (str(elsewhere), "kb_backend_missing"),
        "thin": (str(thin.id), "kb_short"),
    }
    assert failed["notes"]["flag"] == "--allow-metric-change"
    # And with what the admin may decide about it: an option for the whole step, or leaving that one behind.
    # Leaving one behind is said of this run's report. Nothing has been decided yet.
    first = migration["record"]["steps"]["copy_knowledge_bases"]["run_id"]
    assert {name: item["decision"] for name, item in failed.items()} == {
        "notes": {"kind": "accept_ranking_change", "subject": None, "run_id": None, "made": None},
        "elsewhere": {"kind": "leave_behind", "subject": str(elsewhere), "run_id": first, "made": None},
        "thin": {"kind": "leave_behind", "subject": str(thin.id), "run_id": first, "made": None},
    }
    assert _states(migration)["copy_knowledge_bases"] == ("blocked", "kb_metric_change")

    # Leaving the two behind accepts them as they are.
    await _decide(client, headers, "copy_knowledge_bases", "leave_behind", str(elsewhere))
    left = await _decide(client, headers, "copy_knowledge_bases", "leave_behind", str(thin.id))
    assert _states(left)["copy_knowledge_bases"] == ("blocked", "kb_metric_change")
    # The third can be copied, so it is not one to leave behind. Saying so is kept, and changes nothing.
    said = await _decide(client, headers, "copy_knowledge_bases", "leave_behind", str(notes.id))
    assert [made["subject"] for made in said["record"]["decisions"]] == [str(elsewhere), str(thin.id), str(notes.id)]
    assert _states(said)["copy_knowledge_bases"] == ("blocked", "kb_metric_change")
    # Accepting the change of ranking is an option of the command, so nothing changes until the copy is run again.
    accepted = await _decide(client, headers, "copy_knowledge_bases", "accept_ranking_change")
    assert _states(accepted)["copy_knowledge_bases"] == ("blocked", "kb_metric_change")

    run_id = await _start(client, headers, "copy_knowledge_bases")
    command = _command_line(run_id)
    *_, report, end = await _events(client, headers, run_id, "copy_knowledge_bases")

    assert command.endswith("relocate-kb --to postgres --json --verify-skipped --allow-metric-change")
    assert (report["ok"], report["counts"]) == (False, {"relocated": 1, "skipped": 1, "failed": 2})
    migration = await _migration(client, headers)
    still_failed = migration["record"]["steps"]["copy_knowledge_bases"]["report"]["attention"]
    assert {item["kb_name"] for item in still_failed} == {"elsewhere", "thin"}
    # What the admin accepted was the report of the run before. This one is theirs to read, and to accept, again.
    assert _states(migration)["copy_knowledge_bases"] == ("blocked", still_failed[0]["code"])
    await _decide(client, headers, "copy_knowledge_bases", "leave_behind", str(elsewhere))
    again = await _decide(client, headers, "copy_knowledge_bases", "leave_behind", str(thin.id))
    assert _states(again)["copy_knowledge_bases"] == ("done", None)
    left_behind = [made for made in again["record"]["decisions"] if made["subject"] in (str(elsewhere), str(thin.id))]
    assert [made["run_id"] for made in left_behind] == [run_id, run_id]

    withdrawn = await _decide(client, headers, "copy_knowledge_bases", "leave_behind", str(elsewhere), method="DELETE")
    assert _states(withdrawn)["copy_knowledge_bases"] == ("blocked", "kb_backend_missing")


async def test_a_knowledge_base_that_is_still_ingesting_is_not_the_admins_to_leave_behind(
    client, logged_in_headers_super_user, active_super_user, config_dir, scratch_database
):
    pytest.importorskip("pgvector", reason="needs the pgvector extra")
    headers, user = logged_in_headers_super_user, active_super_user.id
    growing = uuid4()
    await _add(KnowledgeBaseRecord(id=growing, user_id=user, name="growing", status="ingesting"))
    _sql(scratch_database, "CREATE EXTENSION vector")
    address = scratch_database.render_as_string(hide_password=False)
    await _connected(client, headers, config_dir, database_url=address, vectors={"kind": "pgvector"})
    await _copy(client, headers, "copy_database")

    *_, report, _ = await _copy(client, headers, "copy_knowledge_bases")

    assert (report["ok"], report["counts"]) == (False, {"failed": 1})
    migration = await _migration(client, headers)
    [waiting] = migration["record"]["steps"]["copy_knowledge_bases"]["report"]["attention"]
    # It can be copied once it has finished, so the record offers no decision about it.
    assert (waiting["subject"], waiting["code"], waiting["decision"]) == (str(growing), "kb_ingesting", None)

    left = await _decide(client, headers, "copy_knowledge_bases", "leave_behind", str(growing))

    assert [(made["kind"], made["subject"]) for made in left["record"]["decisions"]] == [("leave_behind", str(growing))]
    assert _states(left)["copy_knowledge_bases"] == ("blocked", "kb_ingesting")


@pytest.mark.api_key_required
async def test_files_are_copied_into_the_bucket_and_this_instance_keeps_its_own(
    client, logged_in_headers_super_user, active_super_user, config_dir, scratch_database, bucket, monkeypatch, tmp_path
):
    from aiobotocore.session import get_session

    headers, user = logged_in_headers_super_user, active_super_user.id
    _stored_file(config_dir, user, "cat.txt", b"meow")
    flow_id, message_id = uuid4(), uuid4()
    _stored_file(config_dir, flow_id, "pic.png", b"a picture")
    # Chat history names an attachment by where it is on this instance's disk.
    on_disk = str(config_dir / str(flow_id) / "pic.png")
    said = {"sender": "User", "sender_name": "User", "session_id": "chat", "text": "see attached", "files": [on_disk]}
    await _add(
        File(user_id=user, name="cat", path=f"{user}/cat.txt", size=4),
        Flow(id=flow_id, name="chat", data={}, user_id=user),
        MessageTable(id=message_id, flow_id=flow_id, **said),
    )
    address = scratch_database.render_as_string(hide_password=False)
    await _connected(client, headers, config_dir, database_url=address, files=_files(bucket))
    await _copy(client, headers, "copy_database")

    *_, tested, _ = await _copy(client, headers, "copy_files", dry_run=True)

    assert (tested["ok"], tested["dry_run"], tested["counts"]) == (True, True, {"would_copy": 2, "would_repoint": 1})
    assert (await _steps(client, headers))["copy_files"] == ("current", None)
    async with get_session().create_client("s3") as s3:
        assert "Contents" not in await s3.list_objects_v2(Bucket=bucket)

    # The server has AWS settings of its own, for its own work. The copy goes where the admin said all the same.
    (tmp_path / "aws").write_text(f"[profile its-own]\nendpoint_url = http://{NOWHERE}\n")
    with monkeypatch.context() as server:
        server.setenv("AWS_CONFIG_FILE", str(tmp_path / "aws"))
        server.setenv("AWS_PROFILE", "its-own")
        server.setenv("AWS_SESSION_TOKEN", "its-own")
        server.setenv("AWS_ENDPOINT_URL", f"http://{NOWHERE}")
        # Nor does it take the server's word for where this instance's files are.
        server.setenv("LANGFLOW_STORAGE_TYPE", "s3")
        run_id = await _start(client, headers, "copy_files")
    *_, report, end = await _events(client, headers, run_id, "copy_files")

    assert (report["ok"], report["counts"], report["bytes"]) == (True, {"copied": 2, "repointed": 1}, 13)
    assert (end["status"], end["exit_code"]) == ("done", 0)
    async with get_session().create_client("s3") as s3:
        stored = await s3.get_object(Bucket=bucket, Key=f"files/{user}/cat.txt")
        assert await stored["Body"].read() == b"meow"
    # The attachment is renamed in the database the new instance will run on. This instance's own was only read.
    engine = sa.create_engine(scratch_database)
    with engine.connect() as destination:
        assert destination.scalars(sa.text("SELECT files FROM message")).all() == [[f"{flow_id}/pic.png"]]
    engine.dispose()
    async with session_scope() as session:
        assert (await session.get(MessageTable, message_id)).files == [on_disk]
    migration = await _migration(client, headers)
    run = migration["record"]["steps"]["copy_files"]
    assert (run["status"], run["dry_run"], run["report"]["counts"]) == ("done", False, {"copied": 2, "repointed": 1})
    steps = {step["id"]: (step["state"], step["reason"]) for step in migration["steps"]}
    assert steps["copy_files"] == ("done", None)
    assert steps["start_target"] == ("locked", "not_available")


@pytest.mark.api_key_required
async def test_a_file_that_cannot_be_copied_blocks_the_step_until_the_admin_accepts_it(
    client, logged_in_headers_super_user, active_super_user, config_dir, scratch_database, bucket
):
    from aiobotocore.session import get_session

    headers, user = logged_in_headers_super_user, active_super_user.id
    _stored_file(config_dir, user, "cat.txt", b"meow")
    await _add(File(user_id=user, name="cat", path=f"{user}/cat.txt", size=4))
    # A row whose bytes are gone from the disk, and a name the bucket already holds something else under.
    await _add_file_without_bytes(user)
    async with get_session().create_client("s3") as s3:
        await s3.put_object(Bucket=bucket, Key=f"files/{user}/cat.txt", Body=b"not the same cat")
    address = scratch_database.render_as_string(hide_password=False)
    await _connected(client, headers, config_dir, database_url=address, files=_files(bucket))
    await _copy(client, headers, "copy_database")

    *_, report, end = await _copy(client, headers, "copy_files")

    assert (report["ok"], report["counts"]) == (False, {"failed": 2})
    assert (end["status"], end["exit_code"]) == ("done", 1)
    migration = await _migration(client, headers)
    failed = migration["record"]["steps"]["copy_files"]["report"]["attention"]
    assert [(item["subject"], item["code"], item["decision"]["kind"]) for item in failed] == [
        (f"{user}/cat.txt", "file_conflict", "keep_bucket_file"),
        (f"{user}/gone.txt", "no_source_bytes", "accept_missing_attachment"),
    ]
    # Each decision names the item and the run whose report lists it, which is what a page sends back.
    run_id = migration["record"]["steps"]["copy_files"]["run_id"]
    assert [(item["decision"]["subject"], item["decision"]["run_id"]) for item in failed] == [
        (f"{user}/cat.txt", run_id),
        (f"{user}/gone.txt", run_id),
    ]
    assert _states(migration)["copy_files"] == ("blocked", "file_conflict")
    async with get_session().create_client("s3") as s3:
        kept = await s3.get_object(Bucket=bucket, Key=f"files/{user}/cat.txt")
        assert await kept["Body"].read() == b"not the same cat"

    # Each one is the admin's to accept, with the decision made for it: a file the bucket holds another version of
    # is not a missing one.
    wrong = await _decide(client, headers, "copy_files", "accept_missing_attachment", f"{user}/cat.txt")
    assert _states(wrong)["copy_files"] == ("blocked", "file_conflict")
    # What the bucket holds stays, and the file with no bytes is let go.
    one = await _decide(client, headers, "copy_files", "keep_bucket_file", f"{user}/cat.txt")
    assert _states(one)["copy_files"] == ("blocked", "no_source_bytes")
    both = await _decide(client, headers, "copy_files", "accept_missing_attachment", f"{user}/gone.txt")
    assert _states(both)["copy_files"] == ("done", None)


@pytest.mark.api_key_required
async def test_the_copies_that_follow_the_database_give_no_password_or_key_away(
    client,
    logged_in_headers_super_user,
    active_super_user,
    config_dir,
    scratch_database,
    bucket,
    server_log,
    caplog,
    capfd,
):
    pytest.importorskip("pgvector", reason="needs the pgvector extra")
    headers, user = logged_in_headers_super_user, active_super_user.id
    caplog.set_level("DEBUG")
    key = migration_module.get_settings_service().auth_settings.SECRET_KEY.get_secret_value()
    await _knowledge_base(user, "handbook", 3)
    _stored_file(config_dir, user, "cat.txt", b"meow")
    await _add(File(user_id=user, name="cat", path=f"{user}/cat.txt", size=4))
    _sql(scratch_database, "CREATE EXTENSION vector")
    url = scratch_database.set(password=scratch_database.password or DB_PASSWORD)
    # This S3 server takes any keys, so the secret one can be one that is found if it turns up anywhere.
    files = _files(bucket, secret_access_key=S3_SECRET)
    address, vectors = url.render_as_string(hide_password=False), {"kind": "pgvector"}
    responses = [await _connected(client, headers, config_dir, database_url=address, vectors=vectors, files=files)]
    commands = []

    for step in ("copy_database", "copy_knowledge_bases", "copy_files"):
        started = await client.post(RUNS.format(step), json={}, headers=headers)
        run_id = started.json()["run_id"]
        commands.append(_command_line(run_id))
        responses += [started, await client.get(f"{RUNS.format(step)}/{run_id}/events", headers=headers)]
    responses.append(await client.get("api/v1/migration", headers=headers))

    assert {step["id"]: step["state"] for step in responses[-1].json()["steps"]}["copy_files"] == "done"
    _nowhere([url.password, key, S3_SECRET], " ".join(commands), responses, config_dir, server_log, caplog, capfd)


@pytest.mark.parametrize(
    ("decision", "code"),
    [
        ({"step": "copy_database", "kind": "leave_behind", "subject": "kb-1"}, "unknown_decision"),
        ({"step": "copy_files", "kind": "drop_orphans"}, "unknown_decision"),
        ({"step": "backup", "kind": "drop_orphans"}, "unknown_decision"),
        # Accepting an item says which one.
        ({"step": "copy_files", "kind": "keep_bucket_file"}, "subject_missing"),
    ],
)
async def test_a_decision_its_step_does_not_have_is_refused(client, logged_in_headers_super_user, decision, code):
    headers = logged_in_headers_super_user

    refused = [await client.request(method, DECISIONS, json=decision, headers=headers) for method in ("POST", "DELETE")]

    assert [response.status_code for response in refused] == [400, 400]
    assert [response.json()["detail"] for response in refused] == [{"code": code}] * 2
    assert "decisions" not in (await _migration(client, headers))["record"]


async def test_accepting_a_failed_item_completes_its_step_until_the_acceptance_is_withdrawn(
    client, logged_in_headers_super_user, active_super_user, config_dir, server_log
):
    headers, user = logged_in_headers_super_user, active_super_user.id
    await _add_file_without_bytes(user)
    files = {"bucket": "acme", "prefix": "files", "endpoint_url": None}
    results = {"database": {"ok": True}, "files": {"ok": True}}
    _ready_to_copy(config_dir, destinations={**PREPARED["destinations"], "files": files, "results": results})
    _ran(config_dir)
    conflict = _failed("file_conflict", f"{user}/cat.txt", "keep_bucket_file")
    missing = _failed("no_source_bytes", f"{user}/gone.txt", "accept_missing_attachment")
    report = {**UPLOADED, "ok": False, "counts": {"failed": 2}, "attention": [conflict, missing]}
    _ran(config_dir, "copy_files", report=report)
    assert (await _steps(client, headers))["copy_files"] == ("blocked", "file_conflict")

    one = await _decide(client, headers, "copy_files", "keep_bucket_file", conflict["subject"])
    both = await _decide(client, headers, "copy_files", "accept_missing_attachment", missing["subject"])
    # Deciding the same thing twice is deciding it once.
    again = await _decide(client, headers, "copy_files", "keep_bucket_file", conflict["subject"])

    assert _states(one)["copy_files"] == ("blocked", "no_source_bytes")
    assert _states(both)["copy_files"] == ("done", None)
    assert _states(again)["copy_files"] == ("done", None)
    # The record says who decided what, and when.
    decisions = again["record"]["decisions"]
    assert {(made["step"], made["kind"], made["subject"], made["by"]) for made in decisions} == {
        ("copy_files", "keep_bucket_file", conflict["subject"], "activeuser"),
        ("copy_files", "accept_missing_attachment", missing["subject"], "activeuser"),
    }
    assert len(decisions) == 2
    assert all(
        datetime.fromisoformat(made["at"]) > datetime.fromisoformat(BACKED_UP["confirmed_at"]) for made in decisions
    )
    # And which report was accepted: the one of the run that stands.
    assert {made["run_id"] for made in decisions} == {again["record"]["steps"]["copy_files"]["run_id"]}
    # A page draws each item from the record alone: the decision that answers it comes with who made it, and when.
    kept, let_go = (item["decision"] for item in again["record"]["steps"]["copy_files"]["report"]["attention"])
    assert [item["decision"]["made"] for item in one["record"]["steps"]["copy_files"]["report"]["attention"]] == [
        {"by": "activeuser", "at": one["record"]["decisions"][0]["at"]},
        None,
    ]
    assert (kept["made"]["by"], let_go["made"]) == ("activeuser", {"by": "activeuser", "at": decisions[0]["at"]})

    withdrawn = await _decide(client, headers, "copy_files", "keep_bucket_file", conflict["subject"], method="DELETE")

    assert [item["decision"]["made"] for item in withdrawn["record"]["steps"]["copy_files"]["report"]["attention"]] == [
        None,
        let_go["made"],
    ]
    assert _states(withdrawn)["copy_files"] == ("blocked", "file_conflict")
    assert [made["kind"] for made in withdrawn["record"]["decisions"]] == ["accept_missing_attachment"]
    named = f"'keep_bucket_file' for the copy of the files: '{conflict['subject']}'"
    assert f"Migration: user_id={user} decided {named}" in server_log.getvalue()
    assert f"Migration: user_id={user} withdrew the decision {named}" in server_log.getvalue()


async def test_what_was_accepted_of_one_run_is_asked_again_by_the_next(
    client, logged_in_headers_super_user, active_super_user, config_dir
):
    headers, user = logged_in_headers_super_user, active_super_user.id
    await _three_copies_to_make(config_dir, user)
    _ran(config_dir)
    _ran(config_dir, "copy_knowledge_bases", report=MOVED)
    conflict = _failed("file_conflict", f"{user}/cat.txt", "keep_bucket_file")
    report = {**UPLOADED, "ok": False, "counts": {"failed": 1}, "attention": [conflict]}
    _ran(config_dir, "copy_files", report=report)
    kept = await _decide(client, headers, "copy_files", "keep_bucket_file", conflict["subject"])
    assert _states(kept)["copy_files"] == ("done", None)

    # The files are copied again, and what they are copied to holds something under that name as well.
    _ran(config_dir, "copy_files", report=report)

    # Nobody has read this report, so nobody has accepted what it says.
    migration = await _migration(client, headers)
    assert _states(migration)["copy_files"] == ("blocked", "file_conflict")
    [asked] = migration["record"]["steps"]["copy_files"]["report"]["attention"]
    assert (asked["decision"]["run_id"], asked["decision"]["made"]) == (
        migration["record"]["steps"]["copy_files"]["run_id"],
        None,
    )
    again = await _decide(client, headers, "copy_files", "keep_bucket_file", conflict["subject"])
    assert _states(again)["copy_files"] == ("done", None)
    # The record holds one acceptance of that file: the one for the run that stands.
    [made] = again["record"]["decisions"]
    assert made["run_id"] == again["record"]["steps"]["copy_files"]["run_id"]
    assert made["run_id"] != kept["record"]["steps"]["copy_files"]["run_id"]


async def test_an_acceptance_read_from_the_report_before_is_refused(
    client, logged_in_headers_super_user, active_super_user, config_dir
):
    headers, user = logged_in_headers_super_user, active_super_user.id
    await _three_copies_to_make(config_dir, user)
    _ran(config_dir)
    _ran(config_dir, "copy_knowledge_bases", report=MOVED)
    conflict = _failed("file_conflict", f"{user}/cat.txt", "keep_bucket_file")
    report = {**UPLOADED, "ok": False, "counts": {"failed": 1}, "attention": [conflict]}
    _ran(config_dir, "copy_files", report=report)
    # One page has the report of this copy before it.
    [read] = (await _migration(client, headers))["record"]["steps"]["copy_files"]["report"]["attention"]
    # From another one the files are copied again, to another bucket say, and that one holds the name as well.
    _ran(config_dir, "copy_files", report=report)

    # The first page sends back the decision it was given, which names the report it read.
    sent = {"step": "copy_files", **{key: read["decision"][key] for key in ("kind", "subject", "run_id")}}
    refused = await client.post(DECISIONS, json=sent, headers=headers)

    assert (refused.status_code, refused.json()) == (409, {"detail": {"code": "report_changed"}})
    migration = await _migration(client, headers)
    assert migration["record"].get("decisions", []) == []
    assert _states(migration)["copy_files"] == ("blocked", "file_conflict")
    # So is an acceptance that names no report at all.
    unnamed = await client.post(DECISIONS, json={**sent, "run_id": None}, headers=headers)
    assert (unnamed.status_code, unnamed.json()) == (409, {"detail": {"code": "report_changed"}})


async def test_an_item_is_accepted_only_from_a_report_that_lists_it(
    client, logged_in_headers_super_user, active_super_user, config_dir
):
    headers, user = logged_in_headers_super_user, active_super_user.id
    await _three_copies_to_make(config_dir, user)
    _ran(config_dir)
    _ran(config_dir, "copy_knowledge_bases", report=MOVED)
    conflict = _failed("file_conflict", f"{user}/cat.txt", "keep_bucket_file")
    # The files are being copied again. A page that has not caught up still shows what the copy before reported.
    again = uuid4().hex
    _ran(config_dir, "copy_files", run_id=again, status="running", finished_at=None, report=None)

    kept = await _decide(client, headers, "copy_files", "keep_bucket_file", conflict["subject"])

    # This run has reported nothing yet, so there is nothing of it to accept. The decision is kept, and is for no run.
    assert [(made["kind"], made["run_id"]) for made in kept["record"]["decisions"]] == [("keep_bucket_file", None)]
    # When it ends with that file refused, the admin has still to read its report.
    report = {**UPLOADED, "ok": False, "counts": {"failed": 1}, "attention": [conflict]}
    _ran(config_dir, "copy_files", run_id=again, report=report)
    assert (await _steps(client, headers))["copy_files"] == ("blocked", "file_conflict")


async def test_a_decision_that_does_not_answer_what_failed_is_kept_and_completes_nothing(
    client, logged_in_headers_super_user, active_super_user, config_dir
):
    headers, user = logged_in_headers_super_user, active_super_user.id
    await _three_copies_to_make(config_dir, user)
    _ran(config_dir)
    _ran(config_dir, "copy_knowledge_bases", report=MOVED)
    conflict = _failed("file_conflict", f"{user}/cat.txt", "keep_bucket_file")
    # A file that did not arrive whole is copied again. Nothing the admin decides stands in for that.
    unverified = _failed("verify_failed", f"{user}/big.bin")
    report = {**UPLOADED, "ok": False, "counts": {"failed": 2}, "attention": [conflict, unverified]}
    _ran(config_dir, "copy_files", report=report)

    await _decide(client, headers, "copy_files", "accept_missing_attachment", conflict["subject"])
    decided = await _decide(client, headers, "copy_files", "accept_missing_attachment", unverified["subject"])

    assert [(made["kind"], made["subject"]) for made in decided["record"]["decisions"]] == [
        ("accept_missing_attachment", conflict["subject"]),
        ("accept_missing_attachment", unverified["subject"]),
    ]
    assert _states(decided)["copy_files"] == ("blocked", "file_conflict")
    # The decision made for the first file accepts it, and the second still blocks.
    kept = await _decide(client, headers, "copy_files", "keep_bucket_file", conflict["subject"])
    assert _states(kept)["copy_files"] == ("blocked", "verify_failed")


async def test_an_option_the_admin_decided_on_is_on_the_command_line_of_the_next_run(
    client, logged_in_headers_super_user, active_super_user, config_dir, monkeypatch, server_log
):
    headers = logged_in_headers_super_user
    _ready_to_copy(config_dir)
    # A copy that was refused over rows it could leave out, which is the admin's to decide.
    refused = {**COPIED, "ok": False, "tables_copied": 0, "rows_copied": 0, "problems": [{"code": "orphans_droppable"}]}
    asked = {"code": "orphans_droppable", "flag": "--drop-orphans", "details": {"orphans": [ORPHANS]}}
    _ran(config_dir, report=refused, decision_needed={**asked, "decision": {"kind": "drop_orphans", "subject": None}})
    _send_to(monkeypatch, NOWHERE)
    undecided = (await _migration(client, headers))["record"]["steps"]["copy_database"]["decision_needed"]
    assert undecided["decision"] == {"kind": "drop_orphans", "subject": None, "run_id": None, "made": None}

    # An option holds for the whole step, so whatever it is said to be about is not kept.
    decided = await _decide(client, headers, "copy_database", "drop_orphans", "the spans")

    # The run that asked copied nothing, so the step waits for the next one.
    assert _states(decided)["copy_database"] == ("blocked", "orphans_droppable")
    [made] = decided["record"]["decisions"]
    # What the command asked now says that it was answered, by whom and when.
    answered = decided["record"]["steps"]["copy_database"]["decision_needed"]["decision"]
    assert answered["made"] == {"by": "activeuser", "at": made["at"]}
    # Nor is the run that asked: an option is for every run of the step.
    assert (made["step"], made["kind"], made["subject"], made["run_id"], made["by"]) == (
        "copy_database",
        "drop_orphans",
        None,
        None,
        "activeuser",
    )
    run_id = await _start(client, headers)
    assert _command_line(run_id).endswith("convert-sqlite-to-postgres --json --drop-orphans")
    await _events(client, headers, run_id)

    await _decide(client, headers, "copy_database", "drop_orphans", method="DELETE")

    run_id = await _start(client, headers)
    assert _command_line(run_id).endswith("convert-sqlite-to-postgres --json")
    named = "'drop_orphans' for the copy of the database"
    assert f"Migration: user_id={active_super_user.id} decided {named}" in server_log.getvalue()
    assert f"Migration: user_id={active_super_user.id} withdrew the decision {named}" in server_log.getvalue()


async def test_rows_that_point_at_nothing_are_left_out_once_the_admin_says_so(
    client, logged_in_headers_super_user, active_super_user, config_dir, scratch_database
):
    headers = logged_in_headers_super_user
    flow_id, trace_id = uuid4(), uuid4()
    await _add(
        Flow(id=flow_id, name="traced", data={}, user_id=active_super_user.id),
        TraceTable(id=trace_id, name="run", flow_id=flow_id),
        SpanTable(name="root", trace_id=trace_id),
        SpanTable(name="child", trace_id=trace_id),
    )
    async with session_scope() as session:
        # Clearing a flow's traces left their spans behind: SQLite was never told to enforce the foreign key.
        await session.exec(sa.text("DELETE FROM trace"))
        await session.commit()
    await _connected(client, headers, config_dir, database_url=scratch_database.render_as_string(hide_password=False))

    events = await _copy(client, headers, "copy_database")

    asked = next(event for event in events if event["event"] == "decision_needed")
    assert asked["details"]["orphans"] == [ORPHANS]
    migration = await _migration(client, headers)
    # What a page that was reloaded draws the question from, with the decision that answers it.
    run = migration["record"]["steps"]["copy_database"]
    assert run["decision_needed"] == {
        **{key: value for key, value in asked.items() if key not in ("event", "seq")},
        "decision": {"kind": "drop_orphans", "subject": None, "run_id": None, "made": None},
    }
    assert (run["report"]["ok"], run["report"]["rows_copied"]) == (False, 0)
    assert _states(migration)["copy_database"] == ("blocked", "orphans_droppable")

    await _decide(client, headers, "copy_database", "drop_orphans")
    *_, report, end = await _copy(client, headers, "copy_database")

    assert (report["ok"], report["orphans"]) == (True, [ORPHANS])
    assert (end["status"], end["exit_code"]) == ("done", 0)
    engine = sa.create_engine(scratch_database)
    with engine.connect() as destination:
        assert destination.scalar(sa.text("SELECT count(*) FROM span")) == 0
    engine.dispose()
    migration = await _migration(client, headers)
    assert migration["record"]["steps"]["copy_database"]["decision_needed"] is None
    assert _states(migration)["copy_database"] == ("done", None)
