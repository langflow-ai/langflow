"""Tests for the last two steps of the migration endpoints: checking the copy, and starting the new instance.

A check that runs here is the real command, started by the endpoint as a real child
process, as in production. The tests that read a destination that holds a copy need a
PostgreSQL server and its driver, and skip without them.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import os
import sys
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import psutil
import pytest
import sqlalchemy as sa
from langflow.api.utils import migration_runs
from langflow.api.v1 import migration as migration_module
from langflow.cli.integrity import check_instance
from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord
from langflow.services.deps import get_db_service, get_settings_service

from .test_migration import (
    DB_PASSWORD,
    FAILING,
    NOWHERE,
    PASSING,
    PAUSE,
    PAUSED_BEFORE_THE_CHECK,
    PREPARED,
    S3_SECRET,
    VERSION,
    _add,
    _add_file_without_bytes,
    _checked,
    _migration,
    _sql,
    bucket,
    config_dir,
    migration_enabled,
    scratch_database,
    server_log,
)
from .test_migration_copy_runs import (
    _TIMEOUT,
    BACKED_UP,
    RUNS,
    UPLOADED,
    _events,
    _ran,
    _ready_to_copy,
    _send_to,
    _start,
    _states,
    _three_copies_made,
    _to_its_end,
    at_the_door,
    no_copy_left_running,
    unanswering,
)

if TYPE_CHECKING:
    from pathlib import Path

# The fixtures of the other migration endpoints' tests, which these tests run under as well.
__all__ = [
    "at_the_door",
    "bucket",
    "config_dir",
    "migration_enabled",
    "no_copy_left_running",
    "scratch_database",
    "server_log",
    "unanswering",
]

# Some tests here start a real command, and a loaded machine takes its time over one.
pytestmark = pytest.mark.timeout(300)

START = "api/v1/migration/steps/start_target/confirm"
ACCEPT = "api/v1/migration/steps/check_target/confirm"
DESTINATIONS = "api/v1/migration/destinations"
CHECK = "check_target"
# After the copy that _ran records, which started at 01:00.
CHECKED_AT = "2026-09-30T02:10:00+00:00"
STARTED_AT = "2026-09-30T02:30:00+00:00"
WAITING = ("locked", "earlier_step")
# The database of an instance that is on PostgreSQL already, which the new instance then runs on as well.
OWN_POSTGRESQL = "postgresql://db.internal:5432/langflow"
SCHEMA_HERE = {"name": "source: schema", "status": "ok", "summary": "database at revision abc", "problems": []}
# What the instance of these tests has to move: it keeps its database on its own disk, and nothing else.
# The record also names a bucket, which this instance has no use for.
DESTINATION = {"database": PREPARED["destinations"]["database"]}
TO_MOVE = {
    "needed": ["database"],
    "skipped": {"copy_knowledge_bases": "no_local_knowledge_bases", "copy_files": "no_local_files"},
}
# An instance on PostgreSQL that keeps nothing on its own disk has nothing to name and nothing to copy.
NOTHING_TO_MOVE = {
    "destination": {},
    "needed": [],
    "skipped": {
        "connect_target": "nothing_to_connect",
        "copy_database": "already_postgresql",
        "copy_knowledge_bases": "no_local_knowledge_bases",
        "copy_files": "no_local_files",
    },
}


def _row(name: str, summary: str, *, there: str | None = None) -> dict:
    """A check of the copy beside this instance's, as the record keeps one."""
    here = {"status": "ok", "summary": summary}
    return {
        "name": name,
        "there": {**here, "summary": there or summary, "problems": []},
        "here": here,
        "same": there is None,
        "accepted": False,
    }


SAME = {"ok": True, "checks": [_row("schema", "database at revision abc"), _row("files", "0 file rows")]}
DIFFERENT = {
    "ok": False,
    "checks": [
        _row("schema", "database at revision abc"),
        _row("credentials", "8 encrypted values", there="7 encrypted values"),
    ],
}
CRASHED = {"status": "failed", "report": None, "error": {"code": "crashed", "message": "no driver"}}
ACCEPTED = {
    "report": DIFFERENT,
    "confirmed_by": "alice",
    "confirmed_at": "2026-09-30T02:20:00+00:00",
    "accepted_differences": ["credentials"],
}


def _copied(config_dir: Path, *checks: dict, **later: Any) -> None:
    """Everything before the check is done: the five steps before the copies, and the one copy this instance needs."""
    _checked(config_dir, [PASSING, *checks], **PREPARED, pause=PAUSED_BEFORE_THE_CHECK, backup=BACKED_UP, **later)
    _ran(config_dir)


def _change(config_dir: Path, step: str, entry: dict) -> None:
    path = config_dir / "migrations" / "migration.json"
    record = json.loads(path.read_text())
    record["steps"][step] = entry
    path.write_text(json.dumps(record))


def _save_another_database(config_dir: Path) -> None:
    """Save another destination database in the record, as "Where your data goes" does."""
    path = config_dir / "migrations" / "migration.json"
    record = json.loads(path.read_text())
    record["destinations"]["database"] = {"location": "db.internal:5432/another"}
    path.write_text(json.dumps(record))


def _checked_copy(config_dir: Path, **changes: Any) -> None:
    """Add to the record a check of the copy that has ended, as the endpoints leave one."""
    entry = {
        "run_id": uuid4().hex,
        "status": "done",
        "started_by": "alice",
        "started_at": CHECKED_AT,
        "finished_at": "2026-09-30T02:11:00+00:00",
        "pause": PAUSED_BEFORE_THE_CHECK["frozen_at"],
        "destination": DESTINATION,
        **TO_MOVE,
        "report": SAME,
        "error": None,
    }
    _change(config_dir, CHECK, {**entry, **changes})


def _a_start(**changes: Any) -> dict:
    """The start of the new instance, as its endpoint records it."""
    entry = {"confirmed_by": "alice", "confirmed_at": STARTED_AT, "pause": PAUSED_BEFORE_THE_CHECK["frozen_at"]}
    return {**entry, **changes}


def _started(config_dir: Path, **changes: Any) -> None:
    """Add to the record the start of the new instance, as its endpoint leaves it."""
    _change(config_dir, "start_target", _a_start(**changes))


def _stand_in(monkeypatch: pytest.MonkeyPatch, printed: dict | None = None) -> dict:
    """Let the endpoint start its command as it does, with one that needs no PostgreSQL driver in its place.

    The command prints this report and ends, or with no report it waits to be stopped. Hands back what
    the endpoint gave the runner: the command line and the environment.
    """
    start_run, given = migration_module.start_run, {}
    script = f"print({json.dumps(printed)!r})" if printed else "import time; time.sleep(60)"

    async def started(step_id: str, argv: list[str], env: dict[str, str], **kwargs: Any) -> str:
        given.update(argv=argv, env=env)
        return await start_run(step_id, [sys.executable, "-c", script], env, **kwargs)

    monkeypatch.setattr(migration_module, "start_run", started)
    return given


async def test_only_a_superuser_can_check_the_copy_accept_what_differs_or_start(client, logged_in_headers):
    for path in (RUNS.format(CHECK), ACCEPT, START):
        assert (await client.post(path, headers=logged_in_headers)).status_code == 403, path


async def test_the_copy_is_checked_before_the_new_instance_is_started(client, logged_in_headers_super_user, config_dir):
    _copied(config_dir)

    migration = await _migration(client, logged_in_headers_super_user)

    assert [step["id"] for step in migration["steps"]][-2:] == [CHECK, "start_target"]
    states = _states(migration)
    assert (states[CHECK], states["start_target"]) == (("current", None), WAITING)


# ---- the check of the copy


@pytest.mark.parametrize(
    ("check", "expected", "counts"),
    [
        (None, ("current", None), False),
        # Its report matches, so the step is done with nothing to press.
        ({}, ("done", None), True),
        ({"report": DIFFERENT}, ("blocked", "differences"), True),
        (ACCEPTED, ("done", None), True),
        # It ended without a report. The error says why, and the check can be started again.
        (CRASHED, ("current", None), True),
        # Changes were turned back on and paused again since: it read what an earlier pause held.
        ({"pause": "2026-09-01T00:00:00+00:00"}, ("current", None), False),
        ({"destination": {"database": {"location": "db.internal:5432/another"}}}, ("current", None), False),
    ],
)
async def test_where_the_check_of_the_copy_stands(
    client, logged_in_headers_super_user, config_dir, check, expected, counts
):
    _copied(config_dir)
    if check is not None:
        _checked_copy(config_dir, **check)

    migration = await _migration(client, logged_in_headers_super_user)

    states = _states(migration)
    assert states[CHECK] == expected
    # The new instance is started on a copy that was checked, and on no other.
    assert states["start_target"] == (("current", None) if expected[0] == "done" else WAITING)
    # A page is given the check only while it counts, so it draws no report of another pause or destination.
    assert (CHECK in migration["record"]["steps"]) is counts


async def test_a_check_that_starts_is_on_record_and_is_pointed_at_the_destination(
    client, logged_in_headers_super_user, active_super_user, config_dir, monkeypatch, server_log
):
    headers = logged_in_headers_super_user
    _copied(config_dir, SCHEMA_HERE)
    _send_to(monkeypatch, NOWHERE)
    printed = {"name": "schema", "status": "ok", "summary": "database at revision abc", "problems": []}
    given = _stand_in(monkeypatch, {"event": "report", "ok": True, "checks": [printed]})

    run_id = await _start(client, headers, CHECK)
    await _events(client, headers, run_id, CHECK)

    # The command, and where it was pointed: the destination, with an empty folder in place of this instance's own.
    assert given["argv"][1:] == ["-m", "langflow", "check-integrity", "--json"]
    folder = config_dir / "migrations" / "new-instance"
    env = given["env"]
    assert env["LANGFLOW_DATABASE_URL"] == f"postgresql+psycopg://migrator:{DB_PASSWORD}@{NOWHERE}/langflow"
    assert (env["LANGFLOW_CONFIG_DIR"], env["LANGFLOW_KNOWLEDGE_BASES_DIR"]) == (
        str(folder),
        str(folder / "knowledge_bases"),
    )
    migration = await _migration(client, headers)
    kept = migration["record"]["steps"][CHECK]
    assert (kept["run_id"], kept["status"], kept["started_by"]) == (run_id, "done", active_super_user.username)
    assert (kept["pause"], kept["destination"]) == (PAUSED_BEFORE_THE_CHECK["frozen_at"], DESTINATION)
    assert {name: kept[name] for name in ("needed", "skipped")} == TO_MOVE
    assert [(row["name"], row["same"]) for row in kept["report"]["checks"]] == [("schema", True)]
    assert _states(migration)[CHECK] == ("done", None)
    started = f"Migration: user_id={active_super_user.id} started the check of the copy (run {run_id})"
    assert started in server_log.getvalue()


async def test_a_check_whose_run_cannot_be_saved_is_stopped(
    client, logged_in_headers_super_user, active_super_user, config_dir, monkeypatch, server_log
):
    headers = logged_in_headers_super_user
    _copied(config_dir)
    _send_to(monkeypatch, NOWHERE)
    _stand_in(monkeypatch)
    read_run, saves = migration_module.read_run, []

    def read_run_while_another_worker_saves(run_id: str) -> dict:
        # At each look another worker saves something that changes neither the pause nor the destination.
        theirs = migration_module._read_record()
        theirs["backup"]["location"] = f"place {len(saves)}"
        migration_module._write_record(theirs)
        saves.append(run_id)
        return read_run(run_id)

    monkeypatch.setattr(migration_module, "read_run", read_run_while_another_worker_saves)
    refused = await asyncio.wait_for(client.post(RUNS.format(CHECK), headers=headers), _TIMEOUT)
    monkeypatch.setattr(migration_module, "read_run", read_run)

    assert len(saves) == migration_module._SAVE_TRIES
    assert (refused.status_code, refused.json()["detail"]) == (409, {"code": "record_changed"})
    # The record says nothing of the command, so nothing could follow it or stop it later. It was stopped here.
    await asyncio.wait_for(_to_its_end(saves[0]), _TIMEOUT)
    [run] = migration_runs.list_runs()
    assert run["status"] == "cancelled"
    assert CHECK not in (await _migration(client, headers))["record"]["steps"]
    started = f"Migration: user_id={active_super_user.id} started the check of the copy"
    assert f"{started} and its run could not be saved, so it was stopped (run {saves[0]})" in server_log.getvalue()


async def test_a_check_that_still_runs_is_shown_and_can_be_stopped_when_it_no_longer_counts(
    client, logged_in_headers_super_user, config_dir
):
    headers = logged_in_headers_super_user
    _copied(config_dir)
    # Its command is still going, and the pause it was let in for has ended and begun again since.
    waiting = [sys.executable, "-c", "import time; time.sleep(60)"]
    run_id = await migration_runs.start_run(CHECK, waiting, dict(os.environ), started_by="alice")
    earlier = "2026-09-01T00:00:00+00:00"
    _checked_copy(config_dir, run_id=run_id, status="running", finished_at=None, report=None, pause=earlier)

    migration = await _migration(client, headers)

    # It decides nothing, and a page still gets it, so that it can be followed and stopped.
    assert migration["record"]["steps"][CHECK]["run_id"] == run_id
    assert _states(migration)[CHECK] == ("current", None)
    stopped = await client.delete(f"{RUNS.format(CHECK)}/{run_id}", headers=headers)
    assert stopped.status_code == 202
    await asyncio.wait_for(_to_its_end(run_id), _TIMEOUT)
    # Once it is over it is one more check of another pause.
    assert CHECK not in (await _migration(client, headers))["record"]["steps"]


async def test_the_check_of_an_instance_whose_files_are_in_its_own_bucket_reads_them_there(
    client, logged_in_headers_super_user, config_dir, monkeypatch
):
    headers = logged_in_headers_super_user
    # On PostgreSQL with its files in a bucket of its own: nothing to name, nothing to copy.
    own_database = f"postgresql://{NOWHERE}/langflow"
    monkeypatch.setattr(get_db_service(), "database_url", own_database)
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "storage_type", "s3")
    monkeypatch.setattr(settings, "object_storage_bucket_name", "own-bucket")
    monkeypatch.setattr(settings, "object_storage_prefix", "own/files")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIAOWNEXAMPLE")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", S3_SECRET)
    monkeypatch.delenv("PGVECTOR_CONNECTION_STRING", raising=False)
    _checked(config_dir, [PASSING], secret_key=PREPARED["secret_key"], pause=PAUSED_BEFORE_THE_CHECK, backup=BACKED_UP)
    given = _stand_in(monkeypatch, {"event": "report", "ok": True, "checks": []})

    # No worker was given a secret, and none is needed: the new instance runs on what this server runs on.
    run_id = await _start(client, headers, CHECK)
    await _events(client, headers, run_id, CHECK)

    env = given["env"]
    assert env["LANGFLOW_DATABASE_URL"] == own_database
    assert [env[name] for name in ("LANGFLOW_STORAGE_TYPE", "LANGFLOW_OBJECT_STORAGE_BUCKET_NAME")] == [
        "s3",
        "own-bucket",
    ]
    assert (env["LANGFLOW_OBJECT_STORAGE_PREFIX"], env["AWS_SECRET_ACCESS_KEY"]) == ("own/files", S3_SECRET)
    kept = (await _migration(client, headers))["record"]["steps"][CHECK]
    assert (kept["destination"], kept["needed"]) == ({}, [])
    assert kept["skipped"] == {**NOTHING_TO_MOVE["skipped"], "copy_files": "files_in_s3"}


async def test_the_check_needs_the_keys_of_the_bucket_that_is_saved(
    client, logged_in_headers_super_user, active_super_user, config_dir, monkeypatch
):
    # An instance with a file on its own disk, so its files went to the bucket the record names.
    await _three_copies_made(config_dir, active_super_user.id)
    # The worker holds the keys of a bucket that is no longer the saved one.
    _send_to(monkeypatch, NOWHERE, files={"bucket": "earlier", "prefix": "files", "endpoint_url": None})

    refused = await client.post(RUNS.format(CHECK), headers=logged_in_headers_super_user)

    assert (refused.status_code, refused.json()["detail"]) == (409, {"code": "secrets_missing"})
    assert migration_runs.list_runs() == []


async def test_a_copy_that_starts_takes_the_check_of_the_copy_off_the_record(
    client, logged_in_headers_super_user, config_dir, monkeypatch
):
    headers = logged_in_headers_super_user
    _copied(config_dir)
    _checked_copy(config_dir)
    _send_to(monkeypatch, NOWHERE)
    assert _states(await _migration(client, headers))[CHECK] == ("done", None)

    # The database is copied again, which every copy allows before the start. This one reaches nothing.
    await _events(client, headers, await _start(client, headers))

    # It was let in to write to the destination, so what the check read there no longer says what it holds.
    migration = await _migration(client, headers)
    assert CHECK not in migration["record"]["steps"]
    states = _states(migration)
    assert (states["copy_database"][0], states[CHECK], states["start_target"]) == ("blocked", WAITING, WAITING)


async def test_the_check_waits_for_the_copies(client, logged_in_headers_super_user, config_dir, monkeypatch):
    headers = logged_in_headers_super_user
    _ready_to_copy(config_dir)
    _send_to(monkeypatch, NOWHERE, files=PREPARED["destinations"]["files"])

    refused = await client.post(RUNS.format(CHECK), headers=headers)

    assert (refused.status_code, refused.json()["detail"]) == (409, {"code": "locked", "reason": "earlier_step"})
    assert migration_runs.list_runs() == []


@pytest.mark.parametrize("held", ["nothing", "another database", "the word and no password"])
async def test_the_check_needs_the_secrets_of_the_destination_that_is_saved(
    client, logged_in_headers_super_user, config_dir, monkeypatch, held
):
    _copied(config_dir)
    if held == "another database":
        # A worker that holds the password of a database that is no longer the saved one.
        _send_to(monkeypatch, NOWHERE)
        monkeypatch.setitem(migration_module._secrets, "for", {"database": {"location": "db.internal:5432/earlier"}})
    elif held == "the word and no password":
        # A worker that says it holds the saved destination, and holds no password for it.
        monkeypatch.setitem(migration_module._secrets, "for", DESTINATION)

    refused = await client.post(RUNS.format(CHECK), headers=logged_in_headers_super_user)

    assert (refused.status_code, refused.json()["detail"]) == (409, {"code": "secrets_missing"})
    assert migration_runs.list_runs() == []


async def test_while_the_check_runs_a_second_one_is_refused_and_it_can_be_stopped(
    client, logged_in_headers_super_user, active_super_user, config_dir, monkeypatch, unanswering, server_log
):
    headers = logged_in_headers_super_user
    _copied(config_dir)
    # The worker holds the database's password and no keys: the bucket the record names has no use here.
    _send_to(monkeypatch, unanswering)
    run_id = await _start(client, headers, CHECK)

    refused = await client.post(RUNS.format(CHECK), headers=headers)

    assert (refused.status_code, refused.json()["detail"]) == (409, {"code": "run_active"})
    migration = await _migration(client, headers)
    kept = migration["record"]["steps"][CHECK]
    assert (kept["run_id"], kept["status"], kept["report"]) == (run_id, "running", None)
    # What it reads: the parts of the saved destination this instance needs, in the pause that is on.
    assert (kept["pause"], kept["destination"]) == (PAUSED_BEFORE_THE_CHECK["frozen_at"], DESTINATION)
    # And what this instance had to move, as it stood when the check was let in.
    assert {name: kept[name] for name in ("needed", "skipped")} == TO_MOVE
    assert _states(migration)[CHECK] == ("current", None)
    # Any user of the machine can read a command line. The address, with its password, is not on this one.
    child = psutil.Process(migration_runs.read_run(run_id)["child"]["pid"])
    assert child.cmdline()[1:] == ["-m", "langflow", "check-integrity", "--json"]
    # It was pointed at the destination, and at an empty folder in place of this instance's own.
    given = child.environ()
    folder = config_dir / "migrations" / "new-instance"
    assert given["LANGFLOW_DATABASE_URL"] == f"postgresql+psycopg://migrator:{DB_PASSWORD}@{unanswering}/langflow"
    assert (given["LANGFLOW_CONFIG_DIR"], given["LANGFLOW_KNOWLEDGE_BASES_DIR"]) == (
        str(folder),
        str(folder / "knowledge_bases"),
    )
    # No file was moved, so it reads no bucket: the new instance starts with an empty folder of its own.
    assert "LANGFLOW_STORAGE_TYPE" not in given

    stopped = await client.delete(f"{RUNS.format(CHECK)}/{run_id}", headers=headers)

    assert (stopped.status_code, stopped.json()) == (202, {"run_id": run_id})
    await asyncio.wait_for(_to_its_end(run_id), _TIMEOUT)
    migration = await _migration(client, headers)
    kept = migration["record"]["steps"][CHECK]
    assert (kept["status"], kept["report"], kept["error"]) == ("cancelled", None, {"code": "cancelled"})
    # Nothing was read, so the step is where it was, and the check can be started again.
    assert _states(migration)[CHECK] == ("current", None)
    stopped_by = f"Migration: user_id={active_super_user.id} stopped the check of the copy (run {run_id})"
    assert stopped_by in server_log.getvalue()


async def test_the_check_reads_every_part_of_the_destination_that_this_instance_moved_to(
    client, logged_in_headers_super_user, active_super_user, config_dir, monkeypatch, unanswering
):
    headers = logged_in_headers_super_user
    # An instance that keeps a knowledge base and a file on its own disk, with its three copies made.
    await _three_copies_made(config_dir, active_super_user.id)
    bucket = {"bucket": "acme", "prefix": "files", "endpoint_url": None}
    _send_to(monkeypatch, unanswering, files=bucket)

    run_id = await _start(client, headers, CHECK)

    kept = (await _migration(client, headers))["record"]["steps"][CHECK]
    assert (sorted(kept["destination"]), kept["needed"], kept["skipped"]) == (
        ["database", "files", "vectors"],
        ["database", "vectors", "files"],
        {},
    )
    given = psutil.Process(migration_runs.read_run(run_id)["child"]["pid"]).environ()
    address = f"postgresql+psycopg://migrator:{DB_PASSWORD}@{unanswering}/langflow"
    # The knowledge bases went into the destination database, and the files into the bucket.
    assert (given["LANGFLOW_DATABASE_URL"], given["PGVECTOR_CONNECTION_STRING"]) == (address, address)
    assert [given[name] for name in ("LANGFLOW_STORAGE_TYPE", "LANGFLOW_OBJECT_STORAGE_BUCKET_NAME")] == ["s3", "acme"]
    assert given["AWS_SECRET_ACCESS_KEY"] == S3_SECRET
    await client.delete(f"{RUNS.format(CHECK)}/{run_id}", headers=headers)
    await asyncio.wait_for(_to_its_end(run_id), _TIMEOUT)


@pytest.mark.parametrize("change", ["changes turned back on", "another destination saved"])
async def test_a_check_is_stopped_as_it_starts_when_what_let_it_in_has_changed(
    client,
    logged_in_headers_super_user,
    active_super_user,
    config_dir,
    monkeypatch,
    at_the_door,
    server_log,
    change,
):
    headers = logged_in_headers_super_user
    arrived, let_go = at_the_door
    _copied(config_dir)
    _send_to(monkeypatch, NOWHERE, files=PREPARED["destinations"]["files"])
    starting = asyncio.create_task(client.post(RUNS.format(CHECK), headers=headers))
    await asyncio.wait_for(arrived.wait(), _TIMEOUT)

    # The check was let in, and its command has not started yet.
    if change == "another destination saved":
        _save_another_database(config_dir)
    else:
        assert (await client.delete(PAUSE, headers=headers)).status_code == 200
    let_go.set()
    refused = await asyncio.wait_for(starting, _TIMEOUT)

    assert (refused.status_code, refused.json()["detail"]) == (409, {"code": "state_changed"})
    # The command had started by then, and was stopped. The record keeps nothing of it.
    [run] = migration_runs.list_runs()
    assert run["status"] == "cancelled"
    stopped = "after what let it in had changed, so it was stopped"
    started = f"Migration: user_id={active_super_user.id} started the check of the copy"
    assert f"{started} {stopped} (run {run['run_id']})" in server_log.getvalue()
    assert CHECK not in (await _migration(client, headers))["record"]["steps"]


async def test_a_check_of_a_destination_that_cannot_be_reached_ends_with_what_differs(
    client, logged_in_headers_super_user, active_super_user, config_dir, monkeypatch, server_log
):
    pytest.importorskip("psycopg", reason="needs the postgresql extra")
    headers = logged_in_headers_super_user
    _copied(config_dir, SCHEMA_HERE)
    _send_to(monkeypatch, NOWHERE, files=PREPARED["destinations"]["files"])

    run_id = await _start(client, headers, CHECK)
    events = await _events(client, headers, run_id, CHECK)

    # The command found a failure and said so in its report, which is a result and no crash.
    assert [event["event"] for event in events] == ["check", "report", "end"]
    migration = await _migration(client, headers)
    kept = migration["record"]["steps"][CHECK]
    assert (kept["run_id"], kept["status"], kept["error"]) == (run_id, "done", None)
    assert kept["started_by"] == active_super_user.username
    schema = kept["report"]["checks"][0]
    assert (schema["name"], schema["there"]["status"], schema["same"]) == ("schema", "fail", False)
    assert schema["here"] == {"status": "ok", "summary": "database at revision abc"}
    states = _states(migration)
    assert (kept["report"]["ok"], states[CHECK], states["start_target"]) == (False, ("blocked", "differences"), WAITING)
    started = f"Migration: user_id={active_super_user.id} started the check of the copy (run {run_id})"
    assert started in server_log.getvalue()
    # The command was given a folder of its own, and it left nothing there: this instance's key least of all.
    folder = config_dir / "migrations" / "new-instance"
    assert folder.is_dir()
    assert [path.name for path in folder.rglob("*") if path.is_file()] == []
    # Neither the password nor the bucket's key is in what the page is given, in a file of the run, or in the log.
    written = "".join(path.read_text(errors="replace") for path in config_dir.rglob("*") if path.is_file())
    everywhere = written + server_log.getvalue() + json.dumps(migration) + json.dumps(events)
    assert not [secret for secret in (DB_PASSWORD, S3_SECRET) if secret in everywhere]


async def test_a_finding_accepted_in_the_first_step_is_marked_on_the_check_of_the_copy(
    client, logged_in_headers_super_user, config_dir
):
    headers = logged_in_headers_super_user
    # A file without bytes, which the first step found and the admin accepted.
    found = {"status": "fail", "summary": "1 of 1 files have no bytes", "problems": ["alice/gone.txt"]}
    accepted = {"name": "source: files", **found, "accepted_by": "alice", "accepted_at": "2026-09-30T00:05:00+00:00"}
    _copied(config_dir, {"name": "source: files", **found}, accepted_findings=[accepted])
    # A run that printed what the integrity check prints of a destination where the same file has no bytes.
    report = {"event": "report", "ok": False, "checks": [{"name": "files", **found}]}
    printed = [sys.executable, "-c", f"print({json.dumps(report)!r})"]
    run_id = await migration_runs.start_run(CHECK, printed, dict(os.environ), started_by="alice")
    await asyncio.wait_for(_to_its_end(run_id), _TIMEOUT)
    _checked_copy(config_dir, run_id=run_id, status="running", finished_at=None, report=None)

    migration = await _migration(client, headers)

    kept = migration["record"]["steps"][CHECK]
    [row] = kept["report"]["checks"]
    assert (row["name"], row["same"], row["accepted"]) == ("files", True, True)
    # What reads the same on both sides is no difference, so the step is done on it.
    assert (kept["status"], kept["report"]["ok"], _states(migration)[CHECK]) == ("done", True, ("done", None))


# ---- what differs


async def test_a_difference_keeps_the_start_waiting_until_the_admin_accepts_it(
    client, logged_in_headers_super_user, active_super_user, config_dir, server_log
):
    headers = logged_in_headers_super_user
    _copied(config_dir)
    _checked_copy(config_dir, report=DIFFERENT)
    before = await _migration(client, headers)
    assert (_states(before)[CHECK], _states(before)["start_target"]) == (("blocked", "differences"), WAITING)
    refused = await client.post(START, headers=headers)
    assert (refused.status_code, refused.json()["detail"]) == (409, {"code": "locked", "reason": "earlier_step"})

    for body in ({"accept_differences": False}, None):
        refused = await client.post(ACCEPT, json=body, headers=headers)
        assert (refused.status_code, refused.json()["detail"]) == (409, {"code": "differences"})
    # The word has to name the report it is about: a page sends back the run it showed.
    for unread in ({"accept_differences": True}, {"accept_differences": True, "run_id": "another run"}):
        refused = await client.post(ACCEPT, json=unread, headers=headers)
        assert (refused.status_code, refused.json()["detail"]) == (409, {"code": "report_changed"})
    assert (await _migration(client, headers))["record"] == before["record"]

    read = before["record"]["steps"][CHECK]["run_id"]
    accepted = await client.post(ACCEPT, json={"accept_differences": True, "run_id": read}, headers=headers)

    assert accepted.status_code == 200, accepted.text
    states = _states(accepted.json())
    assert (states[CHECK], states["start_target"]) == (("done", None), ("current", None))
    # The record says who read which checks as different.
    kept = accepted.json()["record"]["steps"][CHECK]
    assert (kept["confirmed_by"], kept["accepted_differences"]) == (active_super_user.username, ["credentials"])
    assert datetime.fromisoformat(kept["confirmed_at"]) > datetime.fromisoformat(CHECKED_AT)
    said = f"Migration: user_id={active_super_user.id} accepted what the check of the copy found different: credentials"
    assert said in server_log.getvalue()
    # The word is in the record: the next page load reads it, and so does the start.
    after = await _migration(client, headers)
    assert _states(after)[CHECK] == ("done", None)
    assert after["record"]["steps"][CHECK]["accepted_differences"] == ["credentials"]
    assert (await client.post(START, headers=headers)).status_code == 200


@pytest.mark.parametrize("check", [{}, ACCEPTED])
async def test_nothing_is_recorded_for_a_report_that_matches_or_was_accepted_already(
    client, logged_in_headers_super_user, config_dir, server_log, check
):
    headers = logged_in_headers_super_user
    _copied(config_dir)
    _checked_copy(config_dir, **check)
    before = await _migration(client, headers)
    read = before["record"]["steps"][CHECK]["run_id"]

    again = await client.post(ACCEPT, json={"accept_differences": True, "run_id": read}, headers=headers)

    assert again.status_code == 200, again.text
    assert again.json()["record"] == before["record"]
    assert "accepted what the check of the copy found different" not in server_log.getvalue()


@pytest.mark.parametrize("check", [None, CRASHED, {"pause": "2026-09-01T00:00:00+00:00"}])
async def test_nothing_is_accepted_without_a_check_that_reported(
    client, logged_in_headers_super_user, config_dir, check
):
    headers = logged_in_headers_super_user
    _copied(config_dir)
    if check is not None:
        _checked_copy(config_dir, **check)

    # Saying that the differences were read does not stand in for a report.
    refused = await client.post(ACCEPT, json={"accept_differences": True}, headers=headers)

    assert (refused.status_code, refused.json()["detail"]) == (409, {"code": "not_checked"})


@pytest.mark.parametrize("path", [RUNS.format(CHECK), ACCEPT])
async def test_a_check_that_reported_is_neither_run_again_nor_accepted_while_an_earlier_step_is_open(
    client, logged_in_headers_super_user, config_dir, monkeypatch, path
):
    headers = logged_in_headers_super_user
    # The first step holds a finding that nobody accepted, as after a check of this instance that was run again.
    _copied(config_dir, FAILING)
    # The check found a difference, so its step says so whatever the steps before it say.
    _checked_copy(config_dir, report=DIFFERENT)
    _send_to(monkeypatch, NOWHERE, files=PREPARED["destinations"]["files"])
    before = await _migration(client, headers)
    assert (_states(before)["check_source"][0], _states(before)[CHECK]) == ("blocked", ("blocked", "differences"))
    read = before["record"]["steps"][CHECK]["run_id"]

    refused = await client.post(path, json={"accept_differences": True, "run_id": read}, headers=headers)

    assert (refused.status_code, refused.json()["detail"]) == (409, {"code": "locked", "reason": "earlier_step"})
    assert (await _migration(client, headers))["record"] == before["record"]
    assert migration_runs.list_runs() == []


async def test_differences_are_not_accepted_when_a_step_before_opened_while_the_request_waited(
    client, logged_in_headers_super_user, config_dir, monkeypatch
):
    headers = logged_in_headers_super_user
    _copied(config_dir)
    _checked_copy(config_dir, report=DIFFERENT)
    read = (await _migration(client, headers))["record"]["steps"][CHECK]["run_id"]
    read_record, reads = migration_module._read_record, []

    def read_while_another_worker_checks_this_instance_again() -> dict:
        reads.append(True)
        if len(reads) == 2:
            # Another worker saves a new check of this instance, with a finding that nobody accepted.
            theirs = read_record()
            theirs["steps"]["check_source"]["report"]["checks"].append(FAILING)
            migration_module._write_record(theirs)
        return read_record()

    monkeypatch.setattr(migration_module, "_read_record", read_while_another_worker_checks_this_instance_again)
    refused = await client.post(ACCEPT, json={"accept_differences": True, "run_id": read}, headers=headers)
    monkeypatch.setattr(migration_module, "_read_record", read_record)

    assert (refused.status_code, refused.json()["detail"]) == (409, {"code": "locked", "reason": "earlier_step"})
    assert "confirmed_at" not in (await _migration(client, headers))["record"]["steps"][CHECK]


# ---- the start of the new instance


async def test_the_new_instance_is_started_on_a_copy_that_was_checked_and_that_ends_the_move(
    client, logged_in_headers_super_user, active_super_user, config_dir, server_log
):
    headers = logged_in_headers_super_user
    _copied(config_dir)
    _checked_copy(config_dir)
    assert _states(await _migration(client, headers))["start_target"] == ("current", None)

    started = await client.post(START, headers=headers)

    assert started.status_code == 200, started.text
    states = _states(started.json())
    assert (states[CHECK], states["start_target"]) == (("done", None), ("done", None))
    kept = started.json()["record"]["steps"]["start_target"]
    assert kept["confirmed_by"] == active_super_user.username
    assert datetime.fromisoformat(kept["confirmed_at"]) > datetime.fromisoformat(PAUSED_BEFORE_THE_CHECK["frozen_at"])
    # The pause it was confirmed in: a start counts for no other.
    assert sorted(kept) == ["confirmed_at", "confirmed_by", "pause"]
    assert kept["pause"] == PAUSED_BEFORE_THE_CHECK["frozen_at"]
    # The check it was started on stays on record with its report.
    assert started.json()["record"]["steps"][CHECK]["report"] == SAME
    confirmed = f"Migration: user_id={active_super_user.id} confirmed that the new instance was started"
    assert confirmed in server_log.getvalue()


@pytest.mark.parametrize("check", [None, {"report": DIFFERENT}, CRASHED, {"pause": "2026-09-01T00:00:00+00:00"}])
async def test_the_start_waits_for_a_check_of_the_copy_that_is_done(
    client, logged_in_headers_super_user, config_dir, check
):
    headers = logged_in_headers_super_user
    _copied(config_dir)
    if check is not None:
        _checked_copy(config_dir, **check)

    refused = await client.post(START, headers=headers)

    assert (refused.status_code, refused.json()["detail"]) == (409, {"code": "locked", "reason": "earlier_step"})
    assert "start_target" not in (await _migration(client, headers))["record"]["steps"]


async def test_saying_again_that_the_new_instance_was_started_changes_nothing(
    client, logged_in_headers_super_user, config_dir, server_log
):
    headers = logged_in_headers_super_user
    _copied(config_dir)
    _checked_copy(config_dir)
    _started(config_dir)
    before = await _migration(client, headers)

    again = await client.post(START, headers=headers)

    assert again.status_code == 200, again.text
    assert again.json()["record"] == before["record"]
    assert "confirmed that the new instance was started" not in server_log.getvalue()


async def test_a_start_counts_for_the_pause_it_was_confirmed_in(client, logged_in_headers_super_user, config_dir):
    _copied(config_dir)
    _checked_copy(config_dir)
    # Changes were turned back on and paused again since: that start belongs to a move that was given up.
    _started(config_dir, pause="2026-09-01T00:00:00+00:00")

    states = _states(await _migration(client, logged_in_headers_super_user))

    assert (states[CHECK], states["start_target"]) == (("done", None), ("current", None))


async def test_a_start_of_a_move_that_was_given_up_stands_in_the_way_of_nothing(
    client, logged_in_headers_super_user, config_dir
):
    headers = logged_in_headers_super_user
    _copied(config_dir)
    _checked_copy(config_dir)
    # Changes were turned back on and paused again since that start.
    _started(config_dir, pause="2026-09-01T00:00:00+00:00")

    # The check, a copy and the destination are open again. Each is answered for what it lacks, and none
    # with the word that a new instance was started.
    for run in (CHECK, "copy_database"):
        refused = await client.post(RUNS.format(run), json={}, headers=headers)
        assert (refused.status_code, refused.json()["detail"]) == (409, {"code": "secrets_missing"})
    unneeded = await client.put(DESTINATIONS, json={"vectors": {"kind": "pgvector"}}, headers=headers)
    assert (unneeded.status_code, unneeded.json()["detail"]["code"]) == (422, "not_needed")
    started = await client.post(START, headers=headers)

    # And the new instance of this move is started in its place.
    assert started.status_code == 200, started.text
    kept = started.json()["record"]["steps"]["start_target"]
    assert kept["pause"] == PAUSED_BEFORE_THE_CHECK["frozen_at"]
    assert kept["confirmed_at"] != STARTED_AT


async def test_a_start_is_not_recorded_when_changes_came_back_on_while_it_waited(
    client, logged_in_headers_super_user, config_dir, monkeypatch
):
    headers = logged_in_headers_super_user
    _copied(config_dir)
    _checked_copy(config_dir)
    read_record, reads = migration_module._read_record, []

    def read_while_another_worker_resumes() -> dict:
        reads.append(True)
        if len(reads) == 2:
            # Another worker turns changes back on between this request's look at the steps and its save.
            theirs = read_record()
            del theirs["pause"]
            migration_module._write_record(theirs)
        return read_record()

    monkeypatch.setattr(migration_module, "_read_record", read_while_another_worker_resumes)
    refused = await client.post(START, headers=headers)
    monkeypatch.setattr(migration_module, "_read_record", read_record)

    assert (refused.status_code, refused.json()["detail"]) == (409, {"code": "locked", "reason": "earlier_step"})
    assert "start_target" not in (await _migration(client, headers))["record"]["steps"]


async def test_a_start_is_not_recorded_when_a_copy_was_let_in_while_it_waited(
    client, logged_in_headers_super_user, config_dir, monkeypatch
):
    headers = logged_in_headers_super_user
    _copied(config_dir)
    _checked_copy(config_dir)
    # The copy of another request, running as a process of its own. Every copy can be made again before the start.
    waiting = [sys.executable, "-c", "import time; time.sleep(60)"]
    run_id = await migration_runs.start_run("copy_database", waiting, dict(os.environ), started_by="alice")
    read_record, reads = migration_module._read_record, []

    def read_while_the_copy_is_saved() -> dict:
        reads.append(True)
        if len(reads) == 2:
            # The other request saves its run between this request's look at the steps and its save.
            theirs = read_record()
            theirs["steps"]["copy_database"].update(run_id=run_id, status="running", finished_at=None, report=None)
            migration_module._write_record(theirs)
        return read_record()

    monkeypatch.setattr(migration_module, "_read_record", read_while_the_copy_is_saved)
    refused = await client.post(START, headers=headers)
    monkeypatch.setattr(migration_module, "_read_record", read_record)

    # A copy that writes to the destination and a start on record do not go together, in either order.
    assert (refused.status_code, refused.json()["detail"]) == (409, {"code": "locked", "reason": "earlier_step"})
    assert "start_target" not in (await _migration(client, headers))["record"]["steps"]


# ---- once the new instance was started


@pytest.mark.parametrize(
    ("step", "body"),
    [("copy_database", {}), ("copy_knowledge_bases", {}), ("copy_files", {}), ("copy_files", {"dry_run": True})],
)
async def test_no_copy_starts_once_the_new_instance_was_started(
    client, logged_in_headers_super_user, active_super_user, config_dir, monkeypatch, step, body
):
    headers = logged_in_headers_super_user
    await _three_copies_made(config_dir, active_super_user.id)
    # The worker holds what a copy needs, so nothing but the start stands in its way.
    _send_to(monkeypatch, NOWHERE, files={"bucket": "acme", "prefix": "files", "endpoint_url": None})
    _started(config_dir)

    refused = await client.post(RUNS.format(step), json=body, headers=headers)

    assert (refused.status_code, refused.json()["detail"]) == (409, {"code": "new_instance_started"})
    assert migration_runs.list_runs() == []


async def test_a_copy_at_the_door_is_stopped_when_the_start_is_confirmed_before_its_command_starts(
    client, logged_in_headers_super_user, config_dir, monkeypatch, at_the_door
):
    headers = logged_in_headers_super_user
    arrived, let_go = at_the_door
    _copied(config_dir)
    _checked_copy(config_dir)
    _send_to(monkeypatch, NOWHERE)
    # The database is copied again, which every copy allows before the start.
    starting = asyncio.create_task(client.post(RUNS.format("copy_database"), json={}, headers=headers))
    await asyncio.wait_for(arrived.wait(), _TIMEOUT)

    # The copy was let in, and its command has not started yet. The record still shows the earlier copy as done.
    assert (await client.post(START, headers=headers)).status_code == 200
    let_go.set()
    refused = await asyncio.wait_for(starting, _TIMEOUT)

    assert (refused.status_code, refused.json()["detail"]) == (409, {"code": "state_changed"})
    [run] = migration_runs.list_runs()
    assert run["status"] == "cancelled"


async def test_a_check_at_the_door_is_stopped_when_the_start_is_confirmed_before_its_command_starts(
    client, logged_in_headers_super_user, config_dir, monkeypatch, at_the_door
):
    headers = logged_in_headers_super_user
    arrived, let_go = at_the_door
    _copied(config_dir)
    _checked_copy(config_dir)
    _send_to(monkeypatch, NOWHERE)
    # The copy is checked again, which is allowed before the start.
    starting = asyncio.create_task(client.post(RUNS.format(CHECK), headers=headers))
    await asyncio.wait_for(arrived.wait(), _TIMEOUT)

    # The check was let in, and its command has not started yet. The start is confirmed on the check on record.
    assert (await client.post(START, headers=headers)).status_code == 200
    before = (await _migration(client, headers))["record"]
    let_go.set()
    refused = await asyncio.wait_for(starting, _TIMEOUT)

    assert (refused.status_code, refused.json()["detail"]) == (409, {"code": "state_changed"})
    [run] = migration_runs.list_runs()
    assert run["status"] == "cancelled"
    # The check that the new instance was started on is still the one on record.
    assert (await _migration(client, headers))["record"] == before


async def test_the_copy_is_not_checked_again_once_the_new_instance_runs_on_it(
    client, logged_in_headers_super_user, config_dir, monkeypatch
):
    headers = logged_in_headers_super_user
    _copied(config_dir)
    _checked_copy(config_dir)
    _started(config_dir)
    _send_to(monkeypatch, NOWHERE, files=PREPARED["destinations"]["files"])
    before = await _migration(client, headers)

    refused = await client.post(RUNS.format(CHECK), headers=headers)

    # The new instance writes rows of its own from its first start, so its database no longer reads as the copy.
    assert (refused.status_code, refused.json()["detail"]) == (409, {"code": "new_instance_started"})
    assert migration_runs.list_runs() == []
    assert (await _migration(client, headers))["record"] == before["record"]


async def test_the_destination_stays_as_it_is_once_the_new_instance_was_started(
    client, logged_in_headers_super_user, config_dir
):
    headers = logged_in_headers_super_user
    _copied(config_dir)
    _checked_copy(config_dir)
    _started(config_dir)
    before = await _migration(client, headers)

    address = f"postgresql://migrator:{DB_PASSWORD}@{NOWHERE}/another"
    refused = await client.put(DESTINATIONS, json={"database_url": address}, headers=headers)

    # Nothing is tested and nothing is saved: the new instance runs on the destination that was checked.
    assert (refused.status_code, refused.json()["detail"]) == (409, {"code": "new_instance_started"})
    # A part this instance has no use for meets the same answer: nothing of the request is looked at.
    unneeded = await client.put(DESTINATIONS, json={"vectors": {"kind": "pgvector"}}, headers=headers)
    assert (unneeded.status_code, unneeded.json()["detail"]) == (409, {"code": "new_instance_started"})
    assert (await _migration(client, headers))["record"] == before["record"]
    assert migration_module._secrets == {"for": {}}


async def test_a_destination_is_not_saved_when_the_start_was_confirmed_while_it_was_tested(
    client, logged_in_headers_super_user, config_dir, monkeypatch
):
    headers = logged_in_headers_super_user
    _copied(config_dir)
    _checked_copy(config_dir)
    read_record, reads = migration_module._read_record, []

    def read_while_another_worker_confirms_the_start() -> dict:
        reads.append(True)
        if len(reads) == 2:
            # Another worker records the start while this request's test of the address was under way.
            theirs = read_record()
            theirs["steps"]["start_target"] = _a_start()
            migration_module._write_record(theirs)
        return read_record()

    monkeypatch.setattr(migration_module, "_read_record", read_while_another_worker_confirms_the_start)
    address = f"postgresql://migrator:{DB_PASSWORD}@{NOWHERE}/another"
    refused = await client.put(DESTINATIONS, json={"database_url": address}, headers=headers)
    monkeypatch.setattr(migration_module, "_read_record", read_record)

    assert (refused.status_code, refused.json()["detail"]) == (409, {"code": "new_instance_started"})
    saved = (await _migration(client, headers))["record"]["destinations"]
    assert saved["database"] == PREPARED["destinations"]["database"]
    assert "database_url" not in migration_module._secrets


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("POST", "api/v1/migration/checks", {"target_version": VERSION}),
        ("POST", "api/v1/migration/accepted-findings", {"name": "source: files"}),
        ("DELETE", "api/v1/migration/accepted-findings?name=source%3A%20files", None),
        ("POST", "api/v1/migration/secret-key/verify", {"fingerprint": "000000000000"}),
        ("POST", "api/v1/migration/steps/backup/confirm", {"location": "s3://backups/again"}),
        ("POST", "api/v1/migration/decisions", {"step": "copy_files", "kind": "keep_bucket_file"}),
        ("DELETE", "api/v1/migration/decisions", {"step": "copy_files", "kind": "keep_bucket_file"}),
    ],
)
async def test_the_record_of_a_move_is_closed_once_the_new_instance_was_started(
    client, logged_in_headers_super_user, config_dir, method, path, body
):
    headers = logged_in_headers_super_user
    _copied(config_dir)
    _checked_copy(config_dir)
    _started(config_dir)
    before = await _migration(client, headers)

    refused = await client.request(method, path, json=body, headers=headers)

    # The steps before the start say what the new instance was started on. The one way on is back.
    assert (refused.status_code, refused.json()["detail"]) == (409, {"code": "new_instance_started"})
    after = await _migration(client, headers)
    assert (after["record"], after["steps"]) == (before["record"], before["steps"])


@pytest.mark.parametrize(
    ("own_database", "said", "status"),
    [
        (None, None, 409),
        (None, {"target_stopped": False, "database_restored": True}, 409),
        (None, {"target_stopped": True}, 200),
        # An instance on PostgreSQL shares its database with the new one, which has written to it since.
        (OWN_POSTGRESQL, {"target_stopped": True}, 409),
        (OWN_POSTGRESQL, {"target_stopped": True, "database_restored": True}, 200),
    ],
)
async def test_after_the_start_changes_come_back_on_only_on_the_admins_word(
    client,
    logged_in_headers_super_user,
    active_super_user,
    config_dir,
    monkeypatch,
    server_log,
    own_database,
    said,
    status,
):
    headers = logged_in_headers_super_user
    if own_database:
        monkeypatch.setattr(get_db_service(), "database_url", own_database)
    _copied(config_dir)
    _checked_copy(config_dir)
    _started(config_dir)

    resumed = await client.request("DELETE", PAUSE, json=said, headers=headers)

    assert resumed.status_code == status, resumed.text
    migration = await _migration(client, headers)
    states = _states(migration)
    resumed_by = f"Migration: user_id={active_super_user.id} resumed changes to this instance"
    if status == 409:
        assert resumed.json()["detail"] == {"code": "new_instance_running"}
        # The pause is still on, and so is the start.
        assert (states["pause"], states["start_target"]) == (("done", None), ("done", None))
        assert resumed_by not in server_log.getvalue()
    else:
        assert "pause" not in migration["record"]
        # The move was given up: neither its check nor its start counts, and a page is given no report of it.
        assert (states["pause"], states[CHECK], states["start_target"]) == (("current", None), WAITING, WAITING)
        assert CHECK not in migration["record"]["steps"]
        restored = " and the database restored" if own_database else ""
        assert f"{resumed_by}, saying that the new instance is stopped{restored}" in server_log.getvalue()


async def test_a_start_that_another_pause_saw_asks_nothing_of_a_resume(
    client, logged_in_headers_super_user, config_dir
):
    _copied(config_dir)
    # Changes were turned back on and paused again since, so no new instance was started in this pause.
    _started(config_dir, pause="2026-09-01T00:00:00+00:00")

    resumed = await client.delete(PAUSE, headers=logged_in_headers_super_user)

    assert resumed.status_code == 200, resumed.text
    assert "pause" not in resumed.json()["record"]


async def test_a_resume_that_meets_a_start_confirmed_meanwhile_is_refused(
    client, logged_in_headers_super_user, config_dir, monkeypatch, server_log
):
    headers = logged_in_headers_super_user
    _copied(config_dir)
    _checked_copy(config_dir)
    read_record, confirmed = migration_module._read_record, []

    def read_while_another_worker_confirms_the_start() -> dict:
        record = read_record()
        if not confirmed:
            # Another worker records the start just after this request read the record.
            confirmed.append(True)
            theirs = read_record()
            theirs["steps"]["start_target"] = _a_start()
            migration_module._write_record(theirs)
        return record

    monkeypatch.setattr(migration_module, "_read_record", read_while_another_worker_confirms_the_start)
    refused = await client.delete(PAUSE, headers=headers)
    monkeypatch.setattr(migration_module, "_read_record", read_record)

    # The first try ended the pause on a record with no start, and its save was refused. The second try
    # met the start, and the admin had said nothing of the new instance.
    assert (refused.status_code, refused.json()["detail"]) == (409, {"code": "new_instance_running"})
    assert "pause" in (await _migration(client, headers))["record"]
    assert "resumed changes" not in server_log.getvalue()


async def test_what_the_new_instance_adds_to_a_database_it_shares_with_this_one_reopens_no_step(
    client, logged_in_headers_super_user, active_super_user, config_dir, monkeypatch
):
    headers = logged_in_headers_super_user
    # An instance on PostgreSQL that keeps nothing on its own disk: no destination to name, no copy to make.
    monkeypatch.setattr(get_db_service(), "database_url", OWN_POSTGRESQL)
    _checked(config_dir, [PASSING], secret_key=PREPARED["secret_key"], pause=PAUSED_BEFORE_THE_CHECK, backup=BACKED_UP)
    _checked_copy(config_dir, **NOTHING_TO_MOVE)
    before = _states(await _migration(client, headers))
    assert (before["connect_target"], before["copy_files"], before["start_target"]) == (
        ("skipped", "nothing_to_connect"),
        ("skipped", "no_local_files"),
        ("current", None),
    )

    # The admin starts the new instance on that database, and somebody uploads a first file there before
    # the admin is back on this page.
    await _add_file_without_bytes(active_super_user.id)

    assert _states(await _migration(client, headers)) == before
    started = await client.post(START, headers=headers)
    assert started.status_code == 200, started.text
    # And nothing opens again once the start is on record.
    after = _states(started.json())
    assert after == {**before, "start_target": ("done", None)}


async def test_this_instance_has_nothing_more_to_name_once_its_copy_was_checked_whatever_the_shared_database_says(
    client, logged_in_headers_super_user, active_super_user, config_dir, monkeypatch
):
    headers = logged_in_headers_super_user
    # An instance on PostgreSQL with files on its own disk, which went to a bucket. It has no knowledge base.
    monkeypatch.setattr(get_db_service(), "database_url", OWN_POSTGRESQL)
    await _add_file_without_bytes(active_super_user.id)
    files = {"bucket": "acme", "prefix": "files", "endpoint_url": None}
    saved = {
        "files": files,
        "results": {"files": {"ok": True}},
        "saved_by": "alice",
        "saved_at": BACKED_UP["confirmed_at"],
    }
    _checked(
        config_dir,
        [PASSING],
        destinations=saved,
        secret_key=PREPARED["secret_key"],
        pause=PAUSED_BEFORE_THE_CHECK,
        backup=BACKED_UP,
    )
    _ran(config_dir, "copy_files", report=UPLOADED)
    to_move = {"copy_database": "already_postgresql", "copy_knowledge_bases": "no_local_knowledge_bases"}
    _checked_copy(config_dir, destination={"files": files}, needed=["files"], skipped=to_move)
    before = _states(await _migration(client, headers))
    assert (before["connect_target"], before["copy_knowledge_bases"], before["start_target"]) == (
        ("done", None),
        ("skipped", "no_local_knowledge_bases"),
        ("current", None),
    )

    # The new instance runs on that database, and somebody makes a first knowledge base there, on its disk.
    await _add(KnowledgeBaseRecord(user_id=active_super_user.id, name="made there", backend_type="sqlite"))

    assert _states(await _migration(client, headers)) == before
    assert (await client.post(START, headers=headers)).status_code == 200


# ---- the settings of the new instance


async def test_the_settings_are_given_once_the_copy_was_checked(client, logged_in_headers_super_user, config_dir):
    headers = logged_in_headers_super_user
    _copied(config_dir)
    assert (await _migration(client, headers))["start"]["settings"] == []

    _checked_copy(config_dir)

    assert (await _migration(client, headers))["start"]["settings"] != []


async def test_the_start_step_hands_out_the_settings_of_the_new_instance_and_no_secret(
    client, logged_in_headers_super_user, config_dir, monkeypatch
):
    monkeypatch.delenv("PGVECTOR_CONNECTION_STRING", raising=False)
    _copied(config_dir)
    _checked_copy(config_dir)
    # The worker holds the destination's password and keys, as after "Where your data goes".
    _send_to(monkeypatch, "db.internal:5432", files=PREPARED["destinations"]["files"])

    response = await client.get("api/v1/migration", headers=logged_in_headers_super_user)

    settings = response.json()["start"]["settings"]
    assert [f"{setting['name']}={setting['value']}" for setting in settings][:7] == [
        "LANGFLOW_DATABASE_URL=postgresql://<user>:<password>@db.internal:5432/langflow",
        "LANGFLOW_SECRET_KEY=<secret key>",
        "LANGFLOW_STORAGE_TYPE=s3",
        "LANGFLOW_OBJECT_STORAGE_BUCKET_NAME=langflow-files",  # pragma: allowlist secret
        "LANGFLOW_OBJECT_STORAGE_PREFIX=files",
        "AWS_ACCESS_KEY_ID=<access key id>",
        "AWS_SECRET_ACCESS_KEY=<secret access key>",
    ]
    # This server's own way of signing in comes last, as it runs with it.
    assert settings[7]["name"] == "LANGFLOW_AUTO_LOGIN"
    assert [setting["fill"] for setting in settings[:8]] == [True, True, False, False, False, True, True, False]
    assert not [secret for secret in (DB_PASSWORD, S3_SECRET) if secret in response.text]


async def test_the_settings_name_where_the_knowledge_bases_and_the_files_went_and_stay_after_the_start(
    client, logged_in_headers_super_user, active_super_user, config_dir, monkeypatch
):
    monkeypatch.delenv("PGVECTOR_CONNECTION_STRING", raising=False)
    headers = logged_in_headers_super_user
    # An instance that keeps a knowledge base and a file on its own disk, with its three copies made and checked.
    path = await _three_copies_made(config_dir, active_super_user.id)
    saved = json.loads(path.read_text())["destinations"]
    moved_to = {part: saved[part] for part in ("database", "vectors", "files")}
    _checked_copy(config_dir, destination=moved_to, needed=["database", "vectors", "files"], skipped={})

    before = (await _migration(client, headers))["start"]["settings"]

    assert [f"{setting['name']}={setting['value']}" for setting in before][:8] == [
        "LANGFLOW_DATABASE_URL=postgresql://<user>:<password>@db.internal:5432/langflow",
        "LANGFLOW_SECRET_KEY=<secret key>",
        "LANGFLOW_STORAGE_TYPE=s3",
        "LANGFLOW_OBJECT_STORAGE_BUCKET_NAME=acme",
        "LANGFLOW_OBJECT_STORAGE_PREFIX=files",
        "AWS_ACCESS_KEY_ID=<access key id>",
        "AWS_SECRET_ACCESS_KEY=<secret access key>",
        # The knowledge bases went into the destination database, so the new instance reads them there.
        "PGVECTOR_CONNECTION_STRING=postgresql+psycopg://<user>:<password>@db.internal:5432/langflow",
    ]
    started = await client.post(START, headers=headers)
    assert started.status_code == 200, started.text
    # The list is still there for the admin who has just started the new instance with it.
    assert started.json()["start"]["settings"] == before


@pytest.mark.parametrize("endpoint", ["https://s3.internal:9000", f"https://keyid:{S3_SECRET}@s3.internal:9000"])
async def test_an_instance_on_postgresql_with_its_own_bucket_and_store_is_given_them_and_no_secret(
    client, logged_in_headers_super_user, config_dir, monkeypatch, endpoint
):
    # What this server runs on, each with a secret in it: its database, its bucket and its knowledge base store.
    monkeypatch.setattr(
        get_db_service(), "database_url", f"postgresql://dbuser:{DB_PASSWORD}@db.internal:5432/langflow"
    )
    monkeypatch.setenv("PGVECTOR_CONNECTION_STRING", f"postgresql+psycopg://vectors:{DB_PASSWORD}@pg.internal:5432/kb")
    monkeypatch.setenv("AWS_ENDPOINT_URL", endpoint)
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "storage_type", "s3")
    monkeypatch.setattr(settings, "object_storage_bucket_name", "own-bucket")
    monkeypatch.setattr(settings, "object_storage_prefix", "own/files")
    auth = get_settings_service().auth_settings
    monkeypatch.setattr(auth, "SUPERUSER", "root-admin")
    _checked(config_dir, [PASSING], secret_key=PREPARED["secret_key"], pause=PAUSED_BEFORE_THE_CHECK, backup=BACKED_UP)
    # It has nothing to copy, so the check read its own stores, and no destination is saved.
    _checked_copy(
        config_dir, **{**NOTHING_TO_MOVE, "skipped": {**NOTHING_TO_MOVE["skipped"], "copy_files": "files_in_s3"}}
    )

    response = await client.get("api/v1/migration", headers=logged_in_headers_super_user)

    # An endpoint that holds a user and a password is not handed out.
    plain = [f"AWS_ENDPOINT_URL={endpoint}"] if "@" not in endpoint else []
    signing_in = ["LANGFLOW_AUTO_LOGIN=true"]
    if not auth.AUTO_LOGIN:
        signing_in = [
            "LANGFLOW_AUTO_LOGIN=false",
            "LANGFLOW_SUPERUSER=root-admin",
            "LANGFLOW_SUPERUSER_PASSWORD=<password>",
        ]
    assert [f"{setting['name']}={setting['value']}" for setting in response.json()["start"]["settings"]] == [
        "LANGFLOW_DATABASE_URL=postgresql://<user>:<password>@db.internal:5432/langflow",
        "LANGFLOW_SECRET_KEY=<secret key>",
        "LANGFLOW_STORAGE_TYPE=s3",
        "LANGFLOW_OBJECT_STORAGE_BUCKET_NAME=own-bucket",  # pragma: allowlist secret
        "LANGFLOW_OBJECT_STORAGE_PREFIX=own/files",  # pragma: allowlist secret
        "AWS_ACCESS_KEY_ID=<access key id>",
        "AWS_SECRET_ACCESS_KEY=<secret access key>",
        *plain,
        "PGVECTOR_CONNECTION_STRING=postgresql+psycopg://<user>:<password>@pg.internal:5432/kb",
        *signing_in,
    ]
    assert not [secret for secret in (DB_PASSWORD, S3_SECRET, "dbuser", "vectors:") if secret in response.text]


# ---- with a real destination


def _contents(database: sa.URL) -> dict[str, Any]:
    """How many rows each table of a database holds, and the revision it is at."""
    engine = sa.create_engine(database)
    with engine.connect() as connection:
        tables = sorted(sa.inspect(connection).get_table_names())
        contents = {table: connection.scalar(sa.text(f'SELECT count(*) FROM "{table}"')) for table in tables}  # noqa: S608
        contents["revision"] = connection.scalar(sa.text("SELECT version_num FROM alembic_version"))
    engine.dispose()
    return contents


async def _moved(client, headers, config_dir: Path, scratch_database) -> list[dict]:
    """Copy this instance's database to a destination of its own, through the endpoints.

    Hands back what the integrity check says of this instance, which the first step keeps under these names.
    """
    # A value that only this instance's key opens, so that the check of the copy needs the same key.
    credential = {"name": "moved", "value": "opens with this key", "type": "Credential", "default_fields": []}
    assert (await client.post("api/v1/variables/", json=credential, headers=headers)).status_code == 201
    here = [{**dataclasses.asdict(check), "name": f"source: {check.name}"} for check in (await check_instance()).checks]
    assert {check["status"] for check in here} == {"ok"}, here
    _checked(config_dir, here, secret_key=PREPARED["secret_key"], pause=PAUSED_BEFORE_THE_CHECK, backup=BACKED_UP)
    address = scratch_database.render_as_string(hide_password=False)
    connected = await client.put(DESTINATIONS, json={"database_url": address}, headers=headers)
    assert connected.json()["results"]["database"]["ok"], connected.text
    # The endpoint does not say yet which saved destination the worker's secrets are for, so this does.
    saved = connected.json()["record"]["destinations"]
    migration_module._secrets.setdefault("for", {"database": saved["database"]})
    copied = await _events(client, headers, await _start(client, headers))
    assert copied[-1]["status"] == "done", copied[-3:]
    return here


async def test_a_copy_that_holds_what_this_instance_held_passes_its_check_and_the_new_instance_can_be_started(
    client, logged_in_headers_super_user, config_dir, scratch_database, monkeypatch
):
    monkeypatch.delenv("PGVECTOR_CONNECTION_STRING", raising=False)
    headers = logged_in_headers_super_user
    here = await _moved(client, headers, config_dir, scratch_database)
    before = _contents(scratch_database)

    run_id = await _start(client, headers, CHECK)
    events = await _events(client, headers, run_id, CHECK)

    assert (events[-1]["status"], events[-1]["exit_code"]) == ("done", 0), events[-3:]
    # The check read the destination and changed nothing there: every table holds what it held.
    assert _contents(scratch_database) == before
    assert before["user"] >= 1
    migration = await _migration(client, headers)
    report = migration["record"]["steps"][CHECK]["report"]
    # Every check this instance passed was run on the destination, and each reads the same there.
    assert [row["name"] for row in report["checks"]] == [check["name"].removeprefix("source: ") for check in here]
    assert [row["name"] for row in report["checks"] if not row["same"]] == []
    states = _states(migration)
    assert (report["ok"], states[CHECK], states["start_target"]) == (True, ("done", None), ("current", None))
    # The copied credential opened there, which it does with this instance's key and no other.
    credentials = next(row for row in report["checks"] if row["name"] == "credentials")
    assert credentials["there"]["status"] == "ok"
    assert not credentials["there"]["summary"].startswith("0 ")
    # A check that ran to its end left nothing in its folder either: no key, no file.
    folder = config_dir / "migrations" / "new-instance"
    assert [path.name for path in folder.rglob("*") if path.is_file()] == []

    started = await client.post(START, headers=headers)

    assert _states(started.json())["start_target"] == ("done", None)


async def test_a_value_that_did_not_arrive_is_found_and_copying_again_puts_it_right(
    client, logged_in_headers_super_user, config_dir, scratch_database, monkeypatch
):
    monkeypatch.delenv("PGVECTOR_CONNECTION_STRING", raising=False)
    headers = logged_in_headers_super_user
    await _moved(client, headers, config_dir, scratch_database)
    # The credential is gone from the destination, as after a restore of an older dump there.
    _sql(scratch_database, "DELETE FROM variable WHERE name = 'moved'")

    events = await _events(client, headers, await _start(client, headers, CHECK), CHECK)

    assert events[-1]["event"] == "end", events[-3:]
    migration = await _migration(client, headers)
    report = migration["record"]["steps"][CHECK]["report"]
    assert [row["name"] for row in report["checks"] if not row["same"]] == ["credentials"]
    states = _states(migration)
    assert (report["ok"], states[CHECK], states["start_target"]) == (False, ("blocked", "differences"), WAITING)

    # Nothing runs on the destination yet, so the database is copied again and checked again.
    copied = await _events(client, headers, await _start(client, headers))
    assert copied[-1]["status"] == "done", copied[-3:]
    stale = await _migration(client, headers)
    assert (_states(stale)[CHECK], CHECK in stale["record"]["steps"]) == (("current", None), False)
    await _events(client, headers, await _start(client, headers, CHECK), CHECK)

    migration = await _migration(client, headers)
    assert migration["record"]["steps"][CHECK]["report"]["ok"] is True
    assert _states(migration)[CHECK] == ("done", None)


async def test_a_destination_at_another_revision_is_not_read_and_the_check_says_so(
    client, logged_in_headers_super_user, config_dir, scratch_database, monkeypatch
):
    monkeypatch.delenv("PGVECTOR_CONNECTION_STRING", raising=False)
    headers = logged_in_headers_super_user
    await _moved(client, headers, config_dir, scratch_database)
    # What a newer Langflow does to a database it is started on, when somebody started one there too early.
    _sql(scratch_database, "UPDATE alembic_version SET version_num = 'f00dfeedf00d'")

    run_id = await _start(client, headers, CHECK)
    events = await _events(client, headers, run_id, CHECK)

    assert [event["event"] for event in events] == ["check", "report", "end"]
    migration = await _migration(client, headers)
    kept = migration["record"]["steps"][CHECK]
    # This Langflow reads no table of another version, so the schema is the one check that ran.
    assert [(row["name"], row["there"]["status"], row["same"]) for row in kept["report"]["checks"]] == [
        ("schema", "fail", False)
    ]
    assert kept["report"]["checks"][0]["there"]["summary"].startswith("database is at f00dfeedf00d and this Langflow")
    assert (kept["status"], kept["report"]["ok"], _states(migration)[CHECK]) == (
        "done",
        False,
        ("blocked", "differences"),
    )

    accepted = await client.post(ACCEPT, json={"accept_differences": True, "run_id": run_id}, headers=headers)

    assert _states(accepted.json())[CHECK] == ("done", None)
    assert accepted.json()["record"]["steps"][CHECK]["accepted_differences"] == ["schema"]
