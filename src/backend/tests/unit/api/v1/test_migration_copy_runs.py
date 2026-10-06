"""Tests for the migration endpoints that run the copies.

Every copy here is the real command, started by the endpoint as a real child process,
as in production. A test that copies writes to a PostgreSQL database of its own, and
skips where there is no server or no driver for one.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import psutil
import pytest
import sqlalchemy as sa
from langflow.api.utils import migration_runs
from langflow.api.v1 import migration as migration_module
from langflow.services.deps import get_db_service

from .test_migration import (
    DB_PASSWORD,
    FAILING,
    NOWHERE,
    PASSING,
    PAUSE,
    PAUSED_BEFORE_THE_CHECK,
    PREPARED,
    _checked,
    _migration,
    _steps,
    config_dir,
    migration_enabled,
    scratch_database,
    server_log,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

# The fixtures of the other migration endpoints' tests, which these tests run under as well.
__all__ = ["config_dir", "migration_enabled", "scratch_database", "server_log"]

# Most tests here start a real command, and a loaded machine takes its time over one.
pytestmark = pytest.mark.timeout(300)

# Every wait below ends as soon as what it waits for happens. This only bounds a test that is failing.
_TIMEOUT = 120
RUNS = "api/v1/migration/steps/{}/runs"
BACKED_UP = {"location": "s3://backups/langflow", "confirmed_by": "alice", "confirmed_at": "2026-09-30T00:30:00+00:00"}
COPIED = {"ok": True, "revision": "head", "tables_copied": 59, "rows_copied": 48, "orphans": [], "problems": []}


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


def _send_to(monkeypatch: pytest.MonkeyPatch, address: str) -> None:
    """Give this worker a destination database, as testing one that answers does."""
    url = f"postgresql://migrator:{DB_PASSWORD}@{address}/langflow"
    monkeypatch.setitem(migration_module._secrets, "database_url", url)
    # The worker also keeps which saved destination it holds the password of.
    monkeypatch.setitem(migration_module._secrets, "for", {"database": PREPARED["destinations"]["database"]})


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


async def _connected(client, headers, config_dir: Path, **destination: Any):
    """Everything before the copies is in the record, and the destination was tested through its own endpoint."""
    _checked(config_dir, [PASSING], secret_key=PREPARED["secret_key"], pause=PAUSED_BEFORE_THE_CHECK, backup=BACKED_UP)
    connected = await client.put("api/v1/migration/destinations", json=destination, headers=headers)
    assert {result["ok"] for result in connected.json()["results"].values()} == {True}, connected.text
    # The endpoint does not say yet which saved destination the worker's secrets are for, so this does.
    saved = connected.json()["record"]["destinations"]
    migration_module._secrets.setdefault("for", {part: saved[part] for part in ("database", "files") if part in saved})
    return connected


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


async def test_only_a_superuser_can_run_follow_or_stop_a_copy(client, logged_in_headers):
    run = f"{RUNS.format('copy_database')}/{uuid4().hex}"

    refused = [
        await client.post(RUNS.format("copy_database"), json={}, headers=logged_in_headers),
        await client.get(f"{run}/events", headers=logged_in_headers),
        await client.delete(run, headers=logged_in_headers),
    ]

    assert [response.status_code for response in refused] == [403, 403, 403]


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

    CONFIG_DIR holds the record, and the status and the events of every run.
    """
    printed = capfd.readouterr()
    shown = {
        "the command line": command,
        **{f"response {number}": response.text for number, response in enumerate(responses)},
        **{str(path): path.read_text(errors="replace") for path in config_dir.rglob("*") if path.is_file()},
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
