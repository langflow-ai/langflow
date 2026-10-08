"""Tests for the migration admin endpoints.

The source checks run the real migration-preflight command as a child process
against the test database, as the endpoint does in production.
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import socket
import subprocess
import sys
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from urllib.parse import urlparse
from uuid import uuid4

import langflow.api.router as api_router_module
import pytest
import structlog
import uvicorn
from anyio import Path as AsyncPath
from fastapi import APIRouter, FastAPI, Request
from httpx import ASGITransport, AsyncClient
from langflow.api.utils import migration_pause
from langflow.api.v1 import migration as migration_module
from langflow.api.v1.migration import _source_env
from langflow.services.database.models.file.model import File
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.jobs.model import Job, JobStatus, JobType
from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord
from langflow.services.database.models.user.model import User
from langflow.services.deps import (
    get_background_execution_service,
    get_db_service,
    get_job_service,
    get_queue_service,
    get_settings_service,
    get_storage_service,
    session_scope,
)
from langflow.services.triggers.listeners import replicas
from langflow.utils.version import get_version_info
from lfx.log.logger import configure

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable
    from pathlib import Path

VERSION = get_version_info()["version"]
PASSING = {"name": "version", "status": "ok", "summary": "same version"}
FAILING = {"name": "source: credentials", "status": "fail", "summary": "2 values do not open"}
# What the two steps before the pause leave in the record once they are done. The bucket is for the
# tests that upload a file: an instance that keeps files on its own disk has to name one.
PREPARED = {
    "destinations": {
        "database": {"location": "db.internal:5432/langflow"},
        "files": {"bucket": "langflow-files", "prefix": "files", "endpoint_url": None},
        "results": {"database": {"ok": True}, "files": {"ok": True}},
        "saved_by": "alice",
        "saved_at": "2026-09-30T00:10:00+00:00",
    },
    "secret_key": {"verified_by": "alice", "verified_at": "2026-09-30T00:20:00+00:00"},
}
# A pause that began before, and after, the check that _checked records.
PAUSED_BEFORE_THE_CHECK = {"frozen_at": "2026-09-29T00:00:00+00:00", "frozen_by": "alice"}
PAUSED_AFTER_THE_CHECK = {"frozen_at": "2026-10-01T00:00:00+00:00", "frozen_by": "alice"}
PAUSE = "api/v1/migration/pause"
NEW_FLOW = {"name": "saved around a pause", "data": {}}


@pytest.fixture(autouse=True)
def migration_enabled(monkeypatch: pytest.MonkeyPatch):
    """Turn the feature on. The flag is read when the routes are mounted, so mount them for this test."""
    monkeypatch.setattr(api_router_module.FEATURE_FLAGS, "instance_migration", True)
    routes = api_router_module.router_v1.routes
    mounted = len(routes)
    api_router_module.include_migration_router(api_router_module.router_v1)
    yield
    del routes[mounted:]


@pytest.fixture(autouse=True)
def config_dir(migration_enabled, client, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:  # noqa: ARG001
    """The migration record is written under CONFIG_DIR, so keep it out of the real one.

    The feature is turned on first: the app registers the pause middleware when it is built.
    """
    monkeypatch.setattr(get_settings_service().settings, "config_dir", str(tmp_path))
    return tmp_path


@pytest.fixture
def server_log(client, monkeypatch: pytest.MonkeyPatch):  # noqa: ARG001
    """What the migration routes log, at the level an instance runs at to keep the audit lines.

    A logger binds to the settings of the moment it is first used, so the routes get a fresh one.
    """
    lines = io.StringIO()
    configure(log_level="DEBUG", output_file=lines, cache=False)
    monkeypatch.setattr(migration_module, "logger", structlog.get_logger())
    yield lines
    configure()


async def _run_checks(client, headers, target_version: str = VERSION) -> list[dict]:
    response = await client.post("api/v1/migration/checks", json={"target_version": target_version}, headers=headers)
    assert response.status_code == 200, response.text
    return [json.loads(event) for event in response.text.split("\n\n") if event]


async def _migration(client, headers) -> dict:
    response = await client.get("api/v1/migration", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def _steps(client, headers) -> dict[str, tuple[str, str | None]]:
    migration = await _migration(client, headers)
    return {step["id"]: (step["state"], step["reason"]) for step in migration["steps"]}


def _write_record(config_dir: Path, record: dict) -> None:
    (config_dir / "migrations").mkdir(exist_ok=True)
    (config_dir / "migrations" / "migration.json").write_text(json.dumps(record))


async def _add(*rows) -> None:
    async with session_scope() as session:
        session.add_all(rows)
        await session.commit()


async def _run_and_hang_up(client, headers, on_first_event: Callable[[], Awaitable[None]] | None = None) -> None:
    """Drive the app as a raw ASGI client that hangs up after the first event.

    on_first_event runs while the stream waits to send that event, so the run is still live.
    """
    first_event = asyncio.Event()
    request = [{"type": "http.request", "body": json.dumps({"target_version": VERSION}).encode()}]

    async def receive():
        if request:
            return request.pop()
        await first_event.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        if message["type"] == "http.response.body" and message.get("body") and not first_event.is_set():
            if on_first_event:
                await on_first_event()
            first_event.set()

    raw_headers = [(b"content-type", b"application/json")]
    raw_headers += [(name.lower().encode(), value.encode()) for name, value in headers.items()]
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/v1/migration/checks",
        "raw_path": b"/api/v1/migration/checks",
        "query_string": b"",
        "root_path": "",
        "headers": raw_headers,
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
    }
    await client._transport.app(scope, receive, send)
    assert first_event.is_set()


def test_the_routes_are_absent_when_the_feature_is_off(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(api_router_module.FEATURE_FLAGS, "instance_migration", False)
    router_v1 = APIRouter(prefix="/v1")

    api_router_module.include_migration_router(router_v1)

    assert router_v1.routes == []


async def test_only_a_superuser_can_open_the_migration(client, logged_in_headers):
    finding = {"name": "source: files"}
    refused = [
        await client.get("api/v1/migration", headers=logged_in_headers),
        await client.post("api/v1/migration/checks", json={"target_version": VERSION}, headers=logged_in_headers),
        await client.post("api/v1/migration/accepted-findings", json=finding, headers=logged_in_headers),
        await client.delete("api/v1/migration/accepted-findings", params=finding, headers=logged_in_headers),
        await client.post(PAUSE, headers=logged_in_headers),
        await client.delete(PAUSE, headers=logged_in_headers),
    ]

    assert [response.status_code for response in refused] == [403] * len(refused)


async def test_the_page_describes_this_instance_and_its_steps(client, logged_in_headers_super_user, config_dir):
    migration = await _migration(client, logged_in_headers_super_user)

    instance = migration["instance"]
    assert instance["version"] == VERSION
    assert instance["database"] == {"type": "sqlite", "path": str(get_db_service().database_url).split("///")[1]}
    assert instance["knowledge_bases"]["local"] is False
    assert instance["files"] == {"storage": "local", "folder": str(config_dir), "local": False}
    assert "secret_key" not in instance
    assert migration["steps"] == [
        {"id": "check_source", "state": "current", "reason": None},
        {"id": "connect_target", "state": "locked", "reason": "earlier_step"},
        {"id": "secret_key", "state": "locked", "reason": "earlier_step"},
        {"id": "pause", "state": "locked", "reason": "earlier_step"},
        {"id": "backup", "state": "locked", "reason": "earlier_step"},
        {"id": "copy_database", "state": "locked", "reason": "earlier_step"},
        {"id": "copy_knowledge_bases", "state": "skipped", "reason": "no_local_knowledge_bases"},
        {"id": "copy_files", "state": "skipped", "reason": "no_local_files"},
        {"id": "start_target", "state": "locked", "reason": "earlier_step"},
        {"id": "check_target", "state": "locked", "reason": "earlier_step"},
    ]


def _checked(config_dir: Path, checks: list[dict], status: str = "done", **later: dict) -> None:
    """A source check that ended with these results, and what the steps after it recorded."""
    step = {"status": status, "started_by": "alice", "started_at": "2026-09-30T00:00:00+00:00"}
    report = {"event": "report", "checks": checks}
    _write_record(
        config_dir,
        {
            "target": {"version": VERSION, "set_by": "alice", "set_at": step["started_at"]},
            "steps": {"check_source": {**step, "target_version": VERSION, "report": report}},
            "accepted_findings": [],
            **later,
        },
    )


async def test_after_the_check_the_next_needed_step_is_current_and_the_rest_wait(
    client, logged_in_headers_super_user, config_dir
):
    _checked(config_dir, [PASSING])

    steps = (await _migration(client, logged_in_headers_super_user))["steps"]

    assert [(step["id"], step["state"], step["reason"]) for step in steps] == [
        ("check_source", "done", None),
        ("connect_target", "current", "not_available"),
        ("secret_key", "locked", "earlier_step"),
        ("pause", "locked", "earlier_step"),
        ("backup", "locked", "earlier_step"),
        ("copy_database", "locked", "earlier_step"),
        ("copy_knowledge_bases", "skipped", "no_local_knowledge_bases"),
        ("copy_files", "skipped", "no_local_files"),
        ("start_target", "locked", "earlier_step"),
        ("check_target", "locked", "earlier_step"),
    ]


async def test_a_skipped_step_is_passed_over_for_the_current_one(
    client, logged_in_headers_super_user, config_dir, monkeypatch
):
    monkeypatch.setattr(get_db_service(), "database_url", "postgresql://db.internal:5432/langflow")
    monkeypatch.setattr(get_settings_service().settings, "storage_type", "s3")
    _checked(config_dir, [])

    steps = {
        step["id"]: (step["state"], step["reason"])
        for step in (await _migration(client, logged_in_headers_super_user))["steps"]
    }

    assert steps["connect_target"] == ("skipped", "nothing_to_connect")
    assert steps["secret_key"] == ("current", "not_available")
    assert steps["pause"] == ("locked", "earlier_step")


async def test_blocking_findings_keep_every_later_step_locked(client, logged_in_headers_super_user, config_dir):
    _checked(config_dir, [FAILING])

    migration = await _migration(client, logged_in_headers_super_user)

    assert migration["steps"][0] == {"id": "check_source", "state": "blocked", "reason": "blocking_findings"}
    assert {step["state"] for step in migration["steps"][1:]} == {"locked", "skipped"}


@pytest.mark.parametrize(
    ("backend_type", "backend_config", "local"),
    [
        ("sqlite", {}, True),
        # Not upgraded yet: this Langflow turns it into SQLite, and that is what gets copied.
        ("chroma", {}, True),
        ("chroma", {"mode": "cloud"}, False),
        ("postgres", {}, False),
    ],
)
async def test_only_knowledge_bases_stored_here_keep_the_copy_step(
    client, logged_in_headers_super_user, active_super_user, backend_type, backend_config, local
):
    async with session_scope() as session:
        session.add(
            KnowledgeBaseRecord(
                user_id=active_super_user.id, name="kb", backend_type=backend_type, backend_config=backend_config
            )
        )
        await session.commit()

    migration = await _migration(client, logged_in_headers_super_user)

    assert migration["instance"]["knowledge_bases"]["local"] is local
    steps = {step["id"]: (step["state"], step["reason"]) for step in migration["steps"]}
    assert steps["copy_knowledge_bases"] == (
        ("locked", "earlier_step") if local else ("skipped", "no_local_knowledge_bases")
    )


async def test_files_stored_here_keep_the_copy_step(client, logged_in_headers_super_user, active_super_user):
    await _add_file_without_bytes(active_super_user.id)

    migration = await _migration(client, logged_in_headers_super_user)

    assert migration["instance"]["files"]["local"] is True
    steps = {step["id"]: step for step in migration["steps"]}
    assert steps["copy_files"] == {"id": "copy_files", "state": "locked", "reason": "earlier_step"}


async def test_uploads_with_no_file_row_keep_the_copy_step(
    client, logged_in_headers_super_user, active_super_user, config_dir, monkeypatch
):
    # The v1 upload route saves under CONFIG_DIR/<flow id> and adds no File row.
    monkeypatch.setattr(get_storage_service(), "data_dir", AsyncPath(config_dir))
    async with session_scope() as session:
        flow = Flow(name="uploads", data={}, user_id=active_super_user.id)
        session.add(flow)
        await session.commit()
        await session.refresh(flow)
    uploaded = await client.post(
        f"api/v1/files/upload/{flow.id}",
        files={"file": ("cat.txt", b"meow")},
        headers=logged_in_headers_super_user,
    )
    assert uploaded.status_code == 201, uploaded.text

    migration = await _migration(client, logged_in_headers_super_user)

    assert migration["instance"]["files"]["local"] is True
    steps = {step["id"]: step for step in migration["steps"]}
    assert steps["copy_files"] == {"id": "copy_files", "state": "locked", "reason": "earlier_step"}


async def test_folders_relocate_files_would_not_copy_do_not_keep_the_copy_step(
    client, logged_in_headers_super_user, active_super_user, config_dir
):
    # relocate-files copies the files directly inside each user's and each flow's folder, and nothing else.
    stray = config_dir / str(uuid4())
    stray.mkdir()
    (stray / "orphan.txt").write_text("left by a flow that was deleted")
    async with session_scope() as session:
        flow = Flow(name="nested-only", data={}, user_id=active_super_user.id)
        session.add(flow)
        await session.commit()
        await session.refresh(flow)
    nested = config_dir / str(flow.id) / "sub"
    nested.mkdir(parents=True)
    (nested / "deep.txt").write_text("in a subfolder")

    migration = await _migration(client, logged_in_headers_super_user)

    assert migration["instance"]["files"]["local"] is False
    steps = {step["id"]: step for step in migration["steps"]}
    assert steps["copy_files"]["state"] == "skipped"


async def test_an_instance_on_postgresql_and_s3_skips_what_it_does_not_need(
    client, logged_in_headers_super_user, monkeypatch
):
    url = "postgresql://alice:hunter2@db.internal:5432/langflow"  # pragma: allowlist secret
    monkeypatch.setattr(get_db_service(), "database_url", url)
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "storage_type", "s3")
    monkeypatch.setattr(settings, "object_storage_bucket_name", "acme")
    monkeypatch.setattr(settings, "object_storage_prefix", "files")

    response = await client.get("api/v1/migration", headers=logged_in_headers_super_user)

    assert "hunter2" not in response.text
    assert "alice" not in response.text
    instance = response.json()["instance"]
    assert instance["database"] == {"type": "postgresql", "location": "db.internal:5432/langflow"}
    assert instance["files"] == {"storage": "s3", "bucket": "acme", "prefix": "files", "local": False}
    steps = {step["id"]: (step["state"], step["reason"]) for step in response.json()["steps"]}
    assert steps["connect_target"] == ("skipped", "nothing_to_connect")
    assert steps["copy_database"] == ("skipped", "already_postgresql")
    assert steps["copy_files"] == ("skipped", "files_in_s3")


async def test_the_source_checks_stream_each_check_then_the_report(
    client, logged_in_headers_super_user, tmp_path, monkeypatch
):
    # The server's own environment names a target key file, which the command reads when it is given one.
    (tmp_path / "target_key").write_text("not this instance's key")
    monkeypatch.setenv("LANGFLOW_TARGET_SECRET_KEY_FILE", str(tmp_path / "target_key"))

    *checks, report = await _run_checks(client, logged_in_headers_super_user, target_version=f"langflow v{VERSION}")

    assert {line["event"] for line in checks} == {"check"}
    assert report["event"] == "report"
    assert report["checks"] == [line["check"] for line in checks]
    by_name = {check["name"]: check for check in report["checks"]}
    assert by_name["version"]["status"] == "ok"
    assert "source: authorization" in by_name
    # The page never sends a key, so the check that needs one is left out, and the run takes none from the environment.
    assert "target key" not in by_name
    assert report["ok"] is True

    migration = await _migration(client, logged_in_headers_super_user)
    step = migration["record"]["steps"]["check_source"]
    assert step["status"] == "done"
    assert step["report"] == report
    assert step["started_by"] == "activeuser"
    assert step["target_version"] == VERSION
    target = migration["record"]["target"]
    assert (target["version"], target["set_by"]) == (VERSION, "activeuser")
    assert target["set_at"] == step["started_at"]
    assert migration["steps"][0] == {"id": "check_source", "state": "done", "reason": None}


async def test_the_source_checks_read_auto_login_as_this_server_runs_with_it(monkeypatch: pytest.MonkeyPatch):
    # The default superuser check reads AUTO_LOGIN, so the run is given this server's value, whatever the
    # environment it inherits says.
    monkeypatch.setenv("LANGFLOW_AUTO_LOGIN", "false")
    monkeypatch.setattr(get_settings_service().auth_settings, "AUTO_LOGIN", True)

    assert _source_env()["LANGFLOW_AUTO_LOGIN"] == "true"


@pytest.mark.parametrize(
    ("target_version", "detail"),
    [
        ("not a version", {"code": "version_invalid"}),
        ("0.0.1", {"code": "version_older", "source_version": VERSION}),
    ],
)
async def test_a_version_the_move_cannot_use_is_refused_before_anything_runs(
    client, logged_in_headers_super_user, target_version, detail
):
    response = await client.post(
        "api/v1/migration/checks", json={"target_version": target_version}, headers=logged_in_headers_super_user
    )

    assert response.status_code == 422
    assert response.json()["detail"] == detail
    assert (await _migration(client, logged_in_headers_super_user))["record"] == {
        "target": {},
        "steps": {},
        "accepted_findings": [],
    }


async def test_a_second_run_waits_for_the_live_one(client, logged_in_headers_super_user):
    headers = logged_in_headers_super_user
    seen = {}

    async def while_running():
        seen["refused"] = await client.post(
            "api/v1/migration/checks", json={"target_version": VERSION}, headers=headers
        )
        seen["migration"] = await _migration(client, headers)

    await _run_and_hang_up(client, headers, while_running)

    assert seen["refused"].status_code == 409
    detail = seen["refused"].json()["detail"]
    assert detail["code"] == "already_running"
    assert detail["by"] == "activeuser"
    step = seen["migration"]["record"]["steps"]["check_source"]
    assert step["status"] == "running"
    assert detail["started_at"] == step["started_at"]
    # The run ends with its request, so the next one starts.
    await _run_checks(client, headers)


async def test_a_client_that_disconnects_cancels_the_run(client, logged_in_headers_super_user):
    await _run_and_hang_up(client, logged_in_headers_super_user)

    step = (await _migration(client, logged_in_headers_super_user))["record"]["steps"]["check_source"]
    assert step["status"] == "cancelled"
    assert step["finished_at"] is not None


async def test_a_run_reads_as_live_only_while_its_child_exists(client, logged_in_headers_super_user, config_dir):
    """What another worker's run looks like from here, and what a server restart mid-run leaves behind."""
    headers = logged_in_headers_super_user
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])  # noqa: ASYNC220, S603
    step = {"status": "running", "started_by": "alice", "started_at": "2026-09-30T00:00:00+00:00", "pid": child.pid}
    _write_record(
        config_dir,
        {
            "target": {"version": VERSION, "set_by": "alice", "set_at": step["started_at"]},
            "steps": {"check_source": {**step, "target_version": VERSION}},
            "accepted_findings": [],
        },
    )
    try:
        assert (await _migration(client, headers))["record"]["steps"]["check_source"]["status"] == "running"
        refused = await client.post("api/v1/migration/checks", json={"target_version": VERSION}, headers=headers)
        assert refused.status_code == 409
        assert refused.json()["detail"] == {"code": "already_running", "by": "alice", "started_at": step["started_at"]}
    finally:
        child.kill()
        child.wait()

    migration = await _migration(client, headers)

    assert migration["record"]["steps"]["check_source"]["status"] == "cancelled"
    assert migration["steps"][0] == {"id": "check_source", "state": "current", "reason": None}
    await _run_checks(client, headers)


async def test_a_record_that_fails_to_save_does_not_leave_the_child_running(
    client, logged_in_headers_super_user, config_dir
):
    record = config_dir / "migrations" / "migration.json"
    pids = []

    async def break_the_record():
        pids.append(json.loads(record.read_text())["steps"]["check_source"]["pid"])
        record.write_text("{not json")

    with pytest.raises(RuntimeError, match="response already started"):
        await _run_and_hang_up(client, logged_in_headers_super_user, break_the_record)

    # Killed before the record was read, so the child is gone at once instead of finishing its checks.
    status = subprocess.run(  # noqa: ASYNC221, S603
        ["ps", "-o", "stat=", "-p", str(pids[0])],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    assert status.stdout.strip() in {"", "Z"}


async def test_an_unreadable_record_says_where_it_is(client, logged_in_headers_super_user, config_dir):
    (config_dir / "migrations").mkdir()
    path = config_dir / "migrations" / "migration.json"
    path.write_text("{not json")

    response = await client.get("api/v1/migration", headers=logged_in_headers_super_user)

    assert response.status_code == 500
    assert response.json()["detail"] == {"code": "record_unreadable", "path": str(path)}


async def test_a_failing_check_that_is_safe_to_move_can_be_accepted(
    client, logged_in_headers_super_user, active_super_user
):
    await _add_file_without_bytes(active_super_user.id)
    await _run_checks(client, logged_in_headers_super_user)
    headers = logged_in_headers_super_user

    migration = await _migration(client, headers)
    assert "source: files" in migration["blocking_findings"]
    assert "source: files" in migration["acceptable_checks"]

    accepted = await client.post("api/v1/migration/accepted-findings", json={"name": "source: files"}, headers=headers)
    assert accepted.status_code == 200
    migration = await _migration(client, headers)
    assert "source: files" not in migration["blocking_findings"]
    assert migration["record"]["accepted_findings"][0]["accepted_by"] == "activeuser"

    withdrawn = await client.delete(
        "api/v1/migration/accepted-findings", params={"name": "source: files"}, headers=headers
    )
    assert withdrawn.status_code == 200
    assert "source: files" in (await _migration(client, headers))["blocking_findings"]


async def test_an_acceptance_lapses_when_the_finding_changes(client, logged_in_headers_super_user, active_super_user):
    headers = logged_in_headers_super_user
    await _add_file_without_bytes(active_super_user.id)
    await _run_checks(client, headers)
    await client.post("api/v1/migration/accepted-findings", json={"name": "source: files"}, headers=headers)
    assert "source: files" not in (await _migration(client, headers))["blocking_findings"]

    # A second file went missing after the admin accepted the first.
    await _add_file_without_bytes(active_super_user.id, name="also-gone")
    await _run_checks(client, headers)

    assert "source: files" in (await _migration(client, headers))["blocking_findings"]


async def test_an_acceptance_lapses_when_a_different_file_is_missing_with_the_same_count(
    client, logged_in_headers_super_user, active_super_user, config_dir
):
    headers = logged_in_headers_super_user
    await _add_file_without_bytes(active_super_user.id, name="first")
    await _add_file_without_bytes(active_super_user.id, name="second")
    folder = config_dir / str(active_super_user.id)
    folder.mkdir()
    (folder / "second.txt").write_text("present at the first check")
    *_, original_report = await _run_checks(client, headers)
    accepted = await client.post("api/v1/migration/accepted-findings", json={"name": "source: files"}, headers=headers)
    assert accepted.status_code == 200
    assert "source: files" not in accepted.json()["blocking_findings"]
    original = next(check for check in original_report["checks"] if check["name"] == "source: files")

    (folder / "first.txt").write_text("recovered")
    (folder / "second.txt").unlink()
    *_, report = await _run_checks(client, headers)
    changed = next(check for check in report["checks"] if check["name"] == "source: files")

    assert changed["summary"] == original["summary"]
    assert changed["problems"] != original["problems"]
    assert "source: files" in (await _migration(client, headers))["blocking_findings"]


async def test_an_acceptance_without_recorded_problems_requires_accepting_again(
    client, logged_in_headers_super_user, config_dir
):
    check = {"name": "source: files", "status": "fail", "summary": "one missing file", "problems": ["file A missing"]}
    _checked(config_dir, [check])
    path = config_dir / "migrations" / "migration.json"
    record = json.loads(path.read_text())
    record["accepted_findings"] = [{"name": check["name"], "summary": check["summary"], "accepted_by": "alice"}]
    _write_record(config_dir, record)

    assert "source: files" in (await _migration(client, logged_in_headers_super_user))["blocking_findings"]
    accepted = await client.post(
        "api/v1/migration/accepted-findings", json={"name": "source: files"}, headers=logged_in_headers_super_user
    )
    assert accepted.status_code == 200
    assert "source: files" not in accepted.json()["blocking_findings"]


async def test_a_check_that_makes_the_move_unsafe_cannot_be_accepted(
    client, logged_in_headers_super_user, active_super_user
):
    # Still on Chroma: this Langflow has to upgrade its storage before the knowledge base can be copied.
    async with session_scope() as session:
        session.add(KnowledgeBaseRecord(user_id=active_super_user.id, name="legacy", backend_type="chroma"))
        await session.commit()
    await _run_checks(client, logged_in_headers_super_user)
    headers = logged_in_headers_super_user

    assert "source: knowledge base storage" in (await _migration(client, headers))["blocking_findings"]
    unsafe = await client.post(
        "api/v1/migration/accepted-findings", json={"name": "source: knowledge base storage"}, headers=headers
    )
    assert unsafe.status_code == 400
    assert unsafe.json()["detail"] == {"code": "not_acceptable"}

    # Acceptable, but it did not fail in this run: no file rows point at missing bytes.
    passing = await client.post("api/v1/migration/accepted-findings", json={"name": "source: files"}, headers=headers)
    assert passing.status_code == 400
    assert passing.json()["detail"] == {"code": "not_failing"}


async def test_a_command_that_crashes_is_recorded_as_failed(client, logged_in_headers_super_user, monkeypatch):
    # A scheme SQLAlchemy has no dialect for: the command dies before it can report.
    url = "notadb://alice:hunter2@127.0.0.1/langflow"  # pragma: allowlist secret
    monkeypatch.setattr(get_db_service(), "database_url", url)

    *_, last = await _run_checks(client, logged_in_headers_super_user)

    assert last["event"] == "error"
    record = (await _migration(client, logged_in_headers_super_user))["record"]
    step = record["steps"]["check_source"]
    assert step["status"] == "failed"
    assert step["exit_code"] == 1
    assert step["error"] == last["message"]
    assert "notadb" in step["error"]
    assert "\x1b" not in step["error"]
    # The record is kept on disk and the page offers it as a download.
    assert "hunter2" not in step["error"]


async def test_a_report_longer_than_64_kib_still_arrives(client, logged_in_headers_super_user, active_super_user):
    # A check names five of its problems at most, so it takes long names to pass asyncio's 64 KiB line limit.
    async with session_scope() as session:
        for number in range(5):
            session.add(KnowledgeBaseRecord(user_id=active_super_user.id, name=f"{number}-" + "k" * 20_000))
        await session.commit()

    *_, report = await _run_checks(client, logged_in_headers_super_user)

    assert report["event"] == "report"
    assert len(json.dumps(report)) > 64 * 1024
    step = (await _migration(client, logged_in_headers_super_user))["record"]["steps"]["check_source"]
    assert step["status"] == "done"


async def _add_file_without_bytes(user_id, name: str = "gone") -> None:
    async with session_scope() as session:
        session.add(File(user_id=user_id, name=name, path=f"{user_id}/{name}.txt", size=1))
        await session.commit()


async def test_the_pause_waits_for_the_steps_before_it(client, logged_in_headers_super_user, config_dir):
    _checked(config_dir, [PASSING])

    refused = await client.post(PAUSE, headers=logged_in_headers_super_user)

    assert refused.status_code == 409
    assert refused.json()["detail"] == {"code": "locked", "reason": "earlier_step"}
    assert "pause" not in (await _migration(client, logged_in_headers_super_user))["record"]


async def test_a_pause_refuses_changes_until_the_admin_resumes(client, logged_in_headers_super_user, config_dir):
    headers = logged_in_headers_super_user
    _checked(config_dir, [PASSING], **PREPARED)
    before = datetime.now(timezone.utc)

    paused = await client.post(PAUSE, headers=headers)

    assert paused.status_code == 200, paused.text
    pause = paused.json()["record"]["pause"]
    assert pause["frozen_by"] == "activeuser"
    assert datetime.fromisoformat(pause["frozen_at"]) >= before
    assert (await client.post("api/v1/flows/", json=NEW_FLOW, headers=headers)).status_code == 503
    # Pausing again keeps the moment that the re-check and the copies are measured against.
    assert (await client.post(PAUSE, headers=headers)).json()["record"]["pause"] == pause

    resumed = await client.delete(PAUSE, headers=headers)

    assert resumed.status_code == 200, resumed.text
    assert "pause" not in resumed.json()["record"]
    assert (await client.post("api/v1/flows/", json=NEW_FLOW, headers=headers)).status_code == 201
    # Nothing to resume is not an error.
    assert (await client.delete(PAUSE, headers=headers)).status_code == 200


async def test_each_pause_and_resume_is_logged(
    client, logged_in_headers_super_user, active_super_user, config_dir, server_log
):
    _checked(config_dir, [PASSING], **PREPARED)

    await client.post(PAUSE, headers=logged_in_headers_super_user)
    await client.delete(PAUSE, headers=logged_in_headers_super_user)

    assert f"Migration: user_id={active_super_user.id} paused changes to this instance" in server_log.getvalue()
    assert f"Migration: user_id={active_super_user.id} resumed changes to this instance" in server_log.getvalue()


# A second worker process that lets a change in and keeps it going until it is told to end it.
WORKER_WITH_A_CHANGE = """
import sys
from langflow.api.utils.migration_pause import writing
with writing() as let_in:
    print(f"let_in={let_in}", flush=True)
    sys.stdin.readline()
"""


async def _upload_held_open(client, headers, arrived: asyncio.Event, release: asyncio.Event) -> int:
    """Upload a file as a raw ASGI client that keeps back the end of its body until release is set.

    arrived is set when the server asks for the body, which it does after the pause middleware let
    the upload in. Returns the status the upload ends with.
    """
    body = (
        b'--held\r\nContent-Disposition: form-data; name="file"; filename="notes.txt"\r\n'
        b"Content-Type: text/plain\r\n\r\nwritten around a pause\r\n--held--\r\n"
    )
    pieces = [body[:-10], body[-10:]]
    statuses: list[int] = []

    async def receive():
        if len(pieces) == 2:
            arrived.set()
            return {"type": "http.request", "body": pieces.pop(0), "more_body": True}
        if pieces:
            await release.wait()
            return {"type": "http.request", "body": pieces.pop(0), "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message):
        if message["type"] == "http.response.start":
            statuses.append(message["status"])

    raw_headers = [(b"content-type", b"multipart/form-data; boundary=held")]
    raw_headers += [(b"content-length", str(len(body)).encode())]
    raw_headers += [(name.lower().encode(), value.encode()) for name, value in headers.items()]
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/v2/files/",
        "raw_path": b"/api/v2/files/",
        "query_string": b"",
        "root_path": "",
        "headers": raw_headers,
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
    }
    await client._transport.app(scope, receive, send)
    return statuses[0]


def _tell_when_the_pause_is_written(monkeypatch: pytest.MonkeyPatch) -> tuple[asyncio.Event, list[str]]:
    """An event set when the pause route writes the pause, and each frozen_at it writes."""
    written, moments = asyncio.Event(), []
    write = migration_module._write_record

    def write_and_tell(record: dict) -> None:
        write(record)
        if pause := record.get("pausing") or record.get("pause"):
            moments.append(pause["frozen_at"])
            written.set()

    monkeypatch.setattr(migration_module, "_write_record", write_and_tell)
    return written, moments


@pytest.mark.parametrize("counted_by", ["the lock that workers share", "this worker's count alone"])
async def test_the_pause_is_refused_while_a_change_let_in_before_it_is_still_going(
    client, logged_in_headers_super_user, config_dir, monkeypatch, counted_by
):
    headers = logged_in_headers_super_user
    _checked(config_dir, [PASSING], **PREPARED)
    monkeypatch.setattr(migration_module, "_DRAIN_SECONDS", 0.2)
    if counted_by == "this worker's count alone":
        # As on Windows, which has no flock.
        monkeypatch.setattr(migration_pause, "fcntl", None)
    arrived, release = asyncio.Event(), asyncio.Event()
    uploading = asyncio.create_task(_upload_held_open(client, headers, arrived, release))
    await arrived.wait()

    # The upload was let in and has not sent the end of its file. Paused now, it would write while paused.
    refused = await client.post(PAUSE, headers=headers)

    assert refused.status_code == 409, refused.text
    detail = refused.json()["detail"]
    # The admin is told what the pause waited for, and since when.
    [change] = detail.pop("changes")
    assert detail == {"code": "requests_active", "jobs": [], "listeners": [], "elsewhere": False}
    assert {**change, "since": None} == {
        "kind": "request",
        "method": "POST",
        "path": "/api/v2/files/",
        "name": None,
        "since": None,
    }
    assert datetime.fromisoformat(change["since"]) <= datetime.now(timezone.utc)
    assert not {"pause", "pausing"} & (await _migration(client, headers))["record"].keys()

    release.set()

    # It ends as a change made before any pause, because the pause was taken out again.
    assert await uploading == 201
    assert (await _migration(client, headers))["instance"]["files"]["local"] is True
    assert (await client.post(PAUSE, headers=headers)).status_code == 200


async def test_a_pause_that_was_ended_while_its_request_still_waited_is_not_answered_as_a_pause(
    client, logged_in_headers_super_user, config_dir, monkeypatch
):
    headers = logged_in_headers_super_user
    _checked(config_dir, [PASSING], **PREPARED)
    written, _ = _tell_when_the_pause_is_written(monkeypatch)
    arrived, release = asyncio.Event(), asyncio.Event()
    uploading = asyncio.create_task(_upload_held_open(client, headers, arrived, release))
    await arrived.wait()
    pausing = asyncio.create_task(client.post(PAUSE, headers=headers))
    await written.wait()

    # Changes are turned back on while the request still waits for the upload. Then the upload ends.
    assert (await client.delete(PAUSE, headers=headers)).status_code == 200
    release.set()
    assert await uploading == 201

    ended = await pausing
    assert ended.status_code == 409, ended.text
    assert ended.json()["detail"] == {"code": "pause_ended"}
    assert not {"pause", "pausing"} & (await _migration(client, headers))["record"].keys()


async def test_the_pause_begins_once_the_last_change_let_in_before_it_has_ended(
    client, logged_in_headers_super_user, config_dir, monkeypatch
):
    headers = logged_in_headers_super_user
    _checked(config_dir, [PASSING], **PREPARED)
    written, moments = _tell_when_the_pause_is_written(monkeypatch)
    arrived, release, ended = asyncio.Event(), asyncio.Event(), []
    uploading = asyncio.create_task(_upload_held_open(client, headers, arrived, release))
    uploading.add_done_callback(lambda _: ended.append("the upload"))
    await arrived.wait()
    pausing = asyncio.create_task(client.post(PAUSE, headers=headers))
    pausing.add_done_callback(lambda _: ended.append("the pause"))
    await written.wait()

    # From the moment the pause is written no new change is let in, while the one let in before goes on.
    assert (await client.post("api/v1/flows/", json=NEW_FLOW, headers=headers)).status_code == 503
    release.set()

    assert await uploading == 201
    paused = await pausing
    assert paused.status_code == 200, paused.text
    assert ended == ["the upload", "the pause"]
    # The moment the re-check and the copies are measured against is the one the instance became still at.
    frozen_at = paused.json()["record"]["pause"]["frozen_at"]
    assert datetime.fromisoformat(frozen_at) > datetime.fromisoformat(moments[0])


async def test_a_second_pause_request_is_not_told_that_changes_are_paused_while_the_first_still_waits(
    client, logged_in_headers_super_user, config_dir, monkeypatch
):
    headers = logged_in_headers_super_user
    _checked(config_dir, [PASSING], **PREPARED)
    monkeypatch.setattr(migration_module, "_DRAIN_SECONDS", 1)
    written, _ = _tell_when_the_pause_is_written(monkeypatch)
    arrived, release = asyncio.Event(), asyncio.Event()
    uploading = asyncio.create_task(_upload_held_open(client, headers, arrived, release))
    await arrived.wait()
    first = asyncio.create_task(client.post(PAUSE, headers=headers))
    await written.wait()

    # The first request still waits for the upload, so the instance is not still. The second waits for it too.
    second = await client.post(PAUSE, headers=headers)

    assert second.status_code == 409, second.text
    assert second.json()["detail"]["code"] == "requests_active"
    assert (await first).status_code == 409
    record = (await _migration(client, headers))["record"]
    assert "pause" not in record
    assert "pausing" not in record
    release.set()
    assert await uploading == 201


async def test_a_check_that_runs_while_a_pause_still_waits_does_not_count_for_it(
    client, logged_in_headers_super_user, config_dir, monkeypatch
):
    headers = logged_in_headers_super_user
    _checked(config_dir, [PASSING], **PREPARED)
    # Long enough for the check's own command to run while the pause waits for the upload.
    monkeypatch.setattr(migration_module, "_DRAIN_SECONDS", 120)
    written, _ = _tell_when_the_pause_is_written(monkeypatch)
    arrived, release = asyncio.Event(), asyncio.Event()
    uploading = asyncio.create_task(_upload_held_open(client, headers, arrived, release))
    await arrived.wait()
    pausing = asyncio.create_task(client.post(PAUSE, headers=headers))
    await written.wait()

    # The upload has not ended. A check that passes now says nothing about what the instance holds once it is still.
    await _run_checks(client, headers)
    assert (await _steps(client, headers))["pause"] == ("current", None)

    release.set()
    assert await uploading == 201
    assert (await pausing).status_code == 200
    # The pause begins after that check, so the check has to run again.
    assert (await _steps(client, headers))["pause"] == ("blocked", "recheck_pending")


async def test_a_pause_that_nobody_finished_checking_is_checked_by_the_next_request(
    client, logged_in_headers_super_user, active_super_user, config_dir
):
    headers = logged_in_headers_super_user
    # The worker that wrote it was stopped while it waited for writes to end.
    left_behind = {"frozen_at": "2026-10-06T12:00:00+00:00", "frozen_by": "bob"}
    _checked(config_dir, [PASSING], **PREPARED, pausing=left_behind)

    # No new change is let in, and no step takes it for a pause.
    assert (await client.post("api/v1/flows/", json=NEW_FLOW, headers=headers)).status_code == 503
    assert (await _steps(client, headers))["pause"] == ("current", None)

    paused = await client.post(PAUSE, headers=headers)

    assert paused.status_code == 200, paused.text
    record = paused.json()["record"]
    assert "pausing" not in record
    assert record["pause"]["frozen_by"] == active_super_user.username
    assert datetime.fromisoformat(record["pause"]["frozen_at"]) > datetime.fromisoformat(left_behind["frozen_at"])


async def test_turning_changes_back_on_ends_a_pause_that_nobody_finished_checking(
    client, logged_in_headers_super_user, config_dir
):
    headers = logged_in_headers_super_user
    _checked(config_dir, [PASSING], **PREPARED, pausing={"frozen_at": "2026-10-06T12:00:00+00:00", "frozen_by": "bob"})

    assert (await client.delete(PAUSE, headers=headers)).status_code == 200

    assert "pausing" not in (await _migration(client, headers))["record"]
    assert (await client.post("api/v1/flows/", json=NEW_FLOW, headers=headers)).status_code == 201


async def test_a_job_started_by_a_change_that_was_still_going_stops_the_pause(
    client, logged_in_headers_super_user, active_super_user, config_dir, monkeypatch
):
    headers, flow_id, job_id = logged_in_headers_super_user, uuid4(), uuid4()
    _checked(config_dir, [PASSING], **PREPARED)
    written, _ = _tell_when_the_pause_is_written(monkeypatch)
    arrived, release = asyncio.Event(), asyncio.Event()
    uploading = asyncio.create_task(_upload_held_open(client, headers, arrived, release))
    await arrived.wait()
    pausing = asyncio.create_task(client.post(PAUSE, headers=headers))
    await written.wait()

    # What a change that was let in before the pause can still do: queue a job, after the pause is written.
    await _add(
        Flow(id=flow_id, name="nightly report", data={}, user_id=active_super_user.id),
        Job(job_id=job_id, flow_id=flow_id, user_id=active_super_user.id, status=JobStatus.QUEUED),
    )
    release.set()

    assert await uploading == 201
    refused = await pausing
    assert refused.status_code == 409, refused.text
    assert refused.json()["detail"]["code"] == "jobs_active"
    assert [job["id"] for job in refused.json()["detail"]["jobs"]] == [str(job_id)]
    assert "pause" not in (await _migration(client, headers))["record"]
    assert (await client.post("api/v1/flows/", json=NEW_FLOW, headers=headers)).status_code == 201


async def test_a_run_that_ends_with_its_request_does_not_stop_the_pause(
    client, logged_in_headers_super_user, active_super_user, config_dir, monkeypatch
):
    headers, flow_id, job_id = logged_in_headers_super_user, uuid4(), uuid4()
    _checked(config_dir, [PASSING], **PREPARED)
    # What a request that runs a flow has in the table for as long as it runs.
    await _add(
        Flow(id=flow_id, name="asked for over the API", data={}, user_id=active_super_user.id),
        Job(job_id=job_id, flow_id=flow_id, user_id=active_super_user.id, status=JobStatus.IN_PROGRESS),
    )
    written, _ = _tell_when_the_pause_is_written(monkeypatch)
    arrived, release = asyncio.Event(), asyncio.Event()
    running = asyncio.create_task(_upload_held_open(client, headers, arrived, release))
    await arrived.wait()
    pausing = asyncio.create_task(client.post(PAUSE, headers=headers))
    await written.wait()

    # The request ends within the wait, and its run with it.
    await get_job_service().update_job_status(job_id, JobStatus.COMPLETED)
    release.set()

    assert await running == 201
    # A busy instance always has such a run going. The pause waits for it and then begins.
    assert (await pausing).status_code == 200


async def test_a_job_is_named_together_with_a_change_that_outlasts_the_wait(
    client, logged_in_headers_super_user, active_super_user, config_dir, monkeypatch
):
    headers, flow_id, job_id = logged_in_headers_super_user, uuid4(), uuid4()
    _checked(config_dir, [PASSING], **PREPARED)
    monkeypatch.setattr(migration_module, "_DRAIN_SECONDS", 0.2)
    await _add(
        Flow(id=flow_id, name="nightly report", data={}, user_id=active_super_user.id),
        Job(job_id=job_id, flow_id=flow_id, user_id=active_super_user.id, status=JobStatus.QUEUED),
    )
    arrived, release = asyncio.Event(), asyncio.Event()
    uploading = asyncio.create_task(_upload_held_open(client, headers, arrived, release))
    await arrived.wait()
    try:
        refused = await client.post(PAUSE, headers=headers)
    finally:
        release.set()

    assert refused.status_code == 409, refused.text
    detail = refused.json()["detail"]
    # Both are still in the way, so both are named in one answer.
    assert detail["code"] == "jobs_active"
    assert [job["id"] for job in detail["jobs"]] == [str(job_id)]
    assert [(change["kind"], change["method"], change["path"]) for change in detail["changes"]] == [
        ("request", "POST", "/api/v2/files/")
    ]
    assert await uploading == 201


async def _held_before_it_is_a_job(
    monkeypatch: pytest.MonkeyPatch, module: object, step: str
) -> tuple[asyncio.Event, asyncio.Event]:
    """Make a run wait at a step it takes before it writes its job, as one whose request has just answered."""
    arrived, release = asyncio.Event(), asyncio.Event()
    real = getattr(module, step)

    async def waits(*args, **kwargs):
        arrived.set()
        await release.wait()
        return await real(*args, **kwargs)

    monkeypatch.setattr(module, step, waits)
    return arrived, release


async def _refused_over_work_left_running(client, headers, arrived: asyncio.Event, release: asyncio.Event) -> dict:
    """Pause while a run is held before it is a job, and return what the refusal says. Then let the run end."""
    await asyncio.wait_for(arrived.wait(), timeout=10)
    try:
        refused = await client.post(PAUSE, headers=headers)
        # The run goes on to write its job, its messages and its results, so the instance is not still.
        assert refused.status_code == 409, refused.text
        assert not {"pause", "pausing"} & (await _migration(client, headers))["record"].keys()
    finally:
        release.set()
    # Once the run has ended, nothing is under way for the next pause to wait for.
    assert await migration_pause.drained(10)
    return refused.json()["detail"]


async def test_a_run_that_a_webhook_left_running_stops_the_pause(
    client, logged_in_headers_super_user, active_super_user, config_dir, monkeypatch
):
    from langflow.api.v1 import endpoints

    headers, flow_id = logged_in_headers_super_user, uuid4()
    _checked(config_dir, [PASSING], **PREPARED)
    monkeypatch.setattr(migration_module, "_DRAIN_SECONDS", 0.2)
    await _add(Flow(id=flow_id, name="on a webhook", data={"nodes": [], "edges": []}, user_id=active_super_user.id))
    # A webhook that asks for no key runs as the owner of its flow.
    monkeypatch.setattr(get_settings_service().auth_settings, "WEBHOOK_AUTH_ENABLE", False)
    arrived, release = await _held_before_it_is_a_job(monkeypatch, endpoints, "apply_global_variable_defaults")

    # The webhook answers at once and leaves its run going in a task of its own.
    answered = await client.post(f"api/v1/webhook/{flow_id}", json={"any": "payload"})
    assert answered.status_code == 202, answered.text

    detail = await _refused_over_work_left_running(client, headers, arrived, release)

    assert detail["code"] == "requests_active"
    assert [(change["kind"], change["name"]) for change in detail["changes"]] == [("task", "webhook_run")]


async def test_a_playground_run_that_is_not_a_job_yet_stops_the_pause(
    client, logged_in_headers_super_user, active_super_user, config_dir, monkeypatch
):
    from langflow.api import build

    headers, flow_id = logged_in_headers_super_user, uuid4()
    _checked(config_dir, [PASSING], **PREPARED)
    monkeypatch.setattr(migration_module, "_DRAIN_SECONDS", 0.2)
    await _add(Flow(id=flow_id, name="a playground run", data={"nodes": [], "edges": []}, user_id=active_super_user.id))
    arrived, release = await _held_before_it_is_a_job(monkeypatch, build, "build_graph_from_db")

    # The build answers with its id at once and runs in a task of the job queue.
    started = await client.post(f"api/v1/build/{flow_id}/flow", json={}, headers=headers)
    assert started.status_code == 200, started.text

    detail = await _refused_over_work_left_running(client, headers, arrived, release)

    assert detail["code"] == "requests_active"
    assert [(change["kind"], change["name"]) for change in detail["changes"]] == [("task", "background_task")]


async def test_any_work_the_job_queue_starts_stops_the_pause_until_it_ends(
    client, logged_in_headers_super_user, config_dir, monkeypatch
):
    headers, queue, job_id = logged_in_headers_super_user, get_queue_service(), str(uuid4())
    _checked(config_dir, [PASSING], **PREPARED)
    monkeypatch.setattr(migration_module, "_DRAIN_SECONDS", 0.2)
    arrived, release = asyncio.Event(), asyncio.Event()

    async def work() -> None:
        # What the memory capture after a run is: started by a request, never a job, and still writing.
        arrived.set()
        await release.wait()

    queue.create_queue(job_id)
    queue.start_job(job_id, work())
    try:
        detail = await _refused_over_work_left_running(client, headers, arrived, release)
    finally:
        await queue.cleanup_job(job_id)

    assert detail["code"] == "requests_active"
    assert [(change["kind"], change["name"]) for change in detail["changes"]] == [("task", "background_task")]
    assert (await client.post(PAUSE, headers=headers)).status_code == 200


async def test_a_background_run_that_was_cancelled_stops_the_pause_until_it_ends(
    client, logged_in_headers_super_user, active_super_user, config_dir, monkeypatch
):
    headers, owner, flow_id, job_id = logged_in_headers_super_user, active_super_user.id, uuid4(), uuid4()
    _checked(config_dir, [PASSING], **PREPARED)
    monkeypatch.setattr(migration_module, "_DRAIN_SECONDS", 0.2)
    running = {"status": JobStatus.IN_PROGRESS, "job_metadata": {"request": {"mode": "background"}}}
    await _add(
        Flow(id=flow_id, name="a long background run", data={}, user_id=owner),
        Job(job_id=job_id, flow_id=flow_id, user_id=owner, **running),
    )
    arrived, release = asyncio.Event(), asyncio.Event()

    async def run() -> None:
        arrived.set()
        try:
            await release.wait()
        except asyncio.CancelledError:
            # What a run still does once it is told to stop: it ends its step, then writes how it ended.
            await release.wait()
            raise

    executor = get_background_execution_service()._executor
    await executor.start()
    await executor.submit(str(job_id), run)
    await asyncio.wait_for(arrived.wait(), timeout=10)
    try:
        [job] = (await client.post(PAUSE, headers=headers)).json()["detail"]["jobs"]
        cancel = job["cancel"]
        cancelled = await client.request(cancel["method"], cancel["url"], json=cancel["body"], headers=headers)
        assert cancelled.status_code == 200, cancelled.text

        # From here on the table says that the run is cancelled, and the run has not ended.
        refused = await client.post(PAUSE, headers=headers)
    finally:
        release.set()

    assert refused.status_code == 409, refused.text
    detail = refused.json()["detail"]
    assert detail["code"] == "requests_active"
    assert [(change["kind"], change["name"]) for change in detail["changes"]] == [("task", "background_run")]
    assert await migration_pause.drained(10)
    assert (await client.post(PAUSE, headers=headers)).status_code == 200


async def test_a_tool_call_that_an_mcp_stream_runs_stops_the_pause(
    client, logged_in_headers_super_user, active_super_user, config_dir, monkeypatch
):
    from langflow.api.v1 import endpoints, mcp, mcp_utils

    headers, flow_id = logged_in_headers_super_user, uuid4()
    _checked(config_dir, [PASSING], **PREPARED)
    monkeypatch.setattr(migration_module, "_DRAIN_SECONDS", 0.2)
    monkeypatch.setattr(mcp_utils.get_mcp_config(), "enable_progress_notifications", False)
    await _add(Flow(id=flow_id, name="lookup", data={"nodes": [], "edges": []}, user_id=active_super_user.id))
    arrived, release = await _held_before_it_is_a_job(monkeypatch, endpoints, "apply_global_variable_defaults")

    # Over the SSE transport the POST that carries a call answers 202 at once. The call then runs in
    # the task of the stream that the client keeps open, and that stream is a GET.
    caller = mcp_utils.current_user_ctx.set(active_super_user)
    calling = asyncio.create_task(mcp_utils.handle_call_tool("lookup", {}, mcp.server))
    mcp_utils.current_user_ctx.reset(caller)

    detail = await _refused_over_work_left_running(client, headers, arrived, release)
    await asyncio.gather(calling, return_exceptions=True)

    assert detail["code"] == "requests_active"
    assert [(change["kind"], change["name"]) for change in detail["changes"]] == [("task", "mcp_tool_call")]


async def test_a_tool_call_that_reaches_an_mcp_stream_during_the_pause_is_refused(
    client,  # noqa: ARG001
    active_super_user,
    config_dir,
    monkeypatch,
):
    from langflow.api.v1 import endpoints, mcp, mcp_utils

    _checked(config_dir, [PASSING], pause=PAUSED_AFTER_THE_CHECK, **PREPARED)
    monkeypatch.setattr(mcp_utils.get_mcp_config(), "enable_progress_notifications", False)
    await _add(Flow(id=uuid4(), name="lookup", data={"nodes": [], "edges": []}, user_id=active_super_user.id))
    arrived, _ = await _held_before_it_is_a_job(monkeypatch, endpoints, "apply_global_variable_defaults")

    # The POST that carried this call was let in just before the pause, and has answered.
    caller = mcp_utils.current_user_ctx.set(active_super_user)
    try:
        with pytest.raises(RuntimeError, match="This instance is being migrated"):
            await asyncio.wait_for(mcp_utils.handle_call_tool("lookup", {}, mcp.server), timeout=10)
    finally:
        mcp_utils.current_user_ctx.reset(caller)

    # The run was never begun.
    assert not arrived.is_set()
    assert await migration_pause.drained(10)


async def test_a_run_that_an_a2a_request_left_going_stops_the_pause(
    client, logged_in_headers_super_user, config_dir, monkeypatch
):
    from a2a.server.agent_execution import RequestContext
    from a2a.server.context import ServerCallContext
    from a2a.server.events import EventQueue
    from langflow.api.v1 import a2a_executor
    from langflow.api.v1.a2a_executor import FlowAgentExecutor

    headers = logged_in_headers_super_user
    _checked(config_dir, [PASSING], **PREPARED)
    monkeypatch.setattr(migration_module, "_DRAIN_SECONDS", 0.2)
    monkeypatch.setattr(a2a_executor, "_SAVE_GRACE", 0)
    arrived, release = asyncio.Event(), asyncio.Event()

    async def run(*_args) -> None:
        # Where the flow runs. A run writes its job only once its graph is built.
        arrived.set()
        await release.wait()
        msg = "the run ends here"
        raise RuntimeError(msg)

    async def resume(*_args) -> None:
        pytest.fail("a first message does not resume a run")

    context = RequestContext(
        call_context=ServerCallContext(state={"flow_id": str(uuid4())}), task_id=uuid4().hex, context_id="c"
    )
    # What the SDK does with a message that asks not to wait: the request answers with the task, and
    # the run goes on in a task of the SDK's own.
    running = asyncio.create_task(FlowAgentExecutor(run, resume).execute(context, EventQueue()))

    detail = await _refused_over_work_left_running(client, headers, arrived, release)
    await running

    assert detail["code"] == "requests_active"
    assert [(change["kind"], change["name"]) for change in detail["changes"]] == [("task", "a2a_run")]
    # No reader saves this run's last state here, and a test must not leave a place behind.
    assert await migration_pause.drained(5)


@pytest.fixture(autouse=True)
def no_a2a_place_left_behind():
    """A test that fails midway must not leave a run's place for the tests after it in this process."""
    yield
    from langflow.api.v1 import a2a_executor

    for task_id, place in list(a2a_executor._places.items()):
        a2a_executor._settle(task_id, place, given_up=True)


def _an_a2a_run_that_fails() -> tuple:
    """An executor whose run ends at once, the context of one message, and the task store's own call context."""
    from a2a.server.agent_execution import RequestContext
    from a2a.server.context import ServerCallContext
    from langflow.api.v1.a2a_executor import FlowAgentExecutor

    async def run(*_args) -> None:
        msg = "the run ends here"
        raise RuntimeError(msg)

    async def resume(*_args) -> None:
        pytest.fail("a first message does not resume a run")

    caller = ServerCallContext(state={"flow_id": str(uuid4()), "admitted_user_id": str(uuid4())})
    context = RequestContext(call_context=caller, task_id=uuid4().hex, context_id="c")
    return FlowAgentExecutor(run, resume), context, caller


async def test_an_a2a_run_stops_the_pause_until_the_state_it_ended_with_is_saved(
    client, logged_in_headers_super_user, config_dir, monkeypatch
):
    from a2a.server.events import EventQueue
    from a2a.types import a2a_pb2 as pb
    from langflow.api.v1 import a2a

    headers = logged_in_headers_super_user
    _checked(config_dir, [PASSING], **PREPARED)
    monkeypatch.setattr(migration_module, "_DRAIN_SECONDS", 0.2)
    executor, context, caller = _an_a2a_run_that_fails()

    # The run is over: execute() has returned. The SDK reads the last event of a run after that, and saves it.
    await executor.execute(context, EventQueue())
    refused = await client.post(PAUSE, headers=headers)

    assert refused.status_code == 409, refused.text
    changes = refused.json()["detail"]["changes"]
    assert [(change["kind"], change["name"]) for change in changes] == [("task", "a2a_run")]

    ended = pb.TaskStatus(state=pb.TaskState.TASK_STATE_FAILED)
    await a2a._TASK_STORE.save(pb.Task(id=context.task_id, context_id="c", status=ended), caller)

    # What the run ended with is in the database now, so it has nothing left to write.
    assert (await client.post(PAUSE, headers=headers)).status_code == 200


def _hold_the_save_an_a2a_run_ends_with(monkeypatch: pytest.MonkeyPatch) -> tuple[asyncio.Event, asyncio.Event]:
    """Hold the task store's save of a state that ends a task, as a slow database holds it.

    Returns an event that is set when that save is reached, and the event that lets it go on.
    """
    from langflow.api.v1 import a2a

    reached, release = asyncio.Event(), asyncio.Event()
    save = a2a.DurableTaskStore.save

    async def save_held(store, task, context) -> None:
        if a2a.pb.TaskState.Name(task.status.state) in a2a._TERMINAL_STATE_NAMES:
            reached.set()
            await release.wait()
        await save(store, task, context)

    monkeypatch.setattr(a2a.DurableTaskStore, "save", save_held)
    return reached, release


async def _the_pause_waits_for_the_held_save(client, headers, task_id: str, reached, release) -> None:
    from langflow.services.database.models.a2a.model import A2ATask
    from sqlmodel import select

    try:
        await asyncio.wait_for(reached.wait(), timeout=30)

        # The run itself is over, and what it ended with is not in the database yet.
        refused = await client.post(PAUSE, headers=headers)

        assert refused.status_code == 409, refused.text
        changes = refused.json()["detail"]["changes"]
        assert [(change["kind"], change["name"]) for change in changes] == [("task", "a2a_run")]
    finally:
        # Whatever the test finds, the SDK's reader is let go, or the app could not shut down.
        release.set()
    assert await migration_pause.drained(10)
    assert (await client.post(PAUSE, headers=headers)).status_code == 200
    async with session_scope() as session:
        [task] = (await session.exec(select(A2ATask).where(A2ATask.id == task_id))).all()
    # It was saved before the pause, so the pause holds all of it.
    assert task.task["status"]["state"] == "TASK_STATE_COMPLETED"


async def test_a_message_that_does_not_wait_for_its_a2a_run_stops_the_pause_until_the_run_is_saved(
    client, logged_in_headers_super_user, active_super_user, config_dir, monkeypatch
):
    from lfx.services.deps import get_settings_service as lfx_settings

    from .test_a2a import _ECHO_FLOW, _create_flow, _jsonrpc, _text_message

    headers = logged_in_headers_super_user
    _checked(config_dir, [PASSING], **PREPARED)
    monkeypatch.setattr(migration_module, "_DRAIN_SECONDS", 0.2)
    monkeypatch.setattr(lfx_settings().settings, "a2a_enabled", True)
    flow_id = await _create_flow(active_super_user.id, data=json.loads(_ECHO_FLOW.read_bytes())["data"])
    reached, release = _hold_the_save_an_a2a_run_ends_with(monkeypatch)

    # The request answers with the task at once. The SDK runs the flow and saves the task after that.
    sent = await _jsonrpc(
        client, flow_id, "message/send", {**_text_message("hello"), "configuration": {"blocking": False}}
    )
    assert sent.status_code == 200, sent.text

    await _the_pause_waits_for_the_held_save(client, headers, sent.json()["result"]["id"], reached, release)


async def test_an_answer_to_an_a2a_task_that_waits_for_a_person_stops_the_pause_until_its_run_is_saved(
    client, logged_in_headers_super_user, active_super_user, config_dir, monkeypatch
):
    from lfx.services.deps import get_settings_service as lfx_settings

    from .test_a2a import _HUMAN_INPUT_FLOW, _create_flow, _jsonrpc, _text_message

    headers = logged_in_headers_super_user
    _checked(config_dir, [PASSING], **PREPARED)
    monkeypatch.setattr(migration_module, "_DRAIN_SECONDS", 0.2)
    monkeypatch.setattr(lfx_settings().settings, "a2a_enabled", True)
    flow_id = await _create_flow(active_super_user.id, data=json.loads(_HUMAN_INPUT_FLOW.read_bytes())["data"])
    # The first message runs until the flow asks a person. Its request waits for that, and the task is saved.
    waiting = (await _jsonrpc(client, flow_id, "message/send", _text_message("start"))).json()["result"]
    assert waiting["status"]["state"] == "input-required"
    assert await migration_pause.drained(10)
    reached, release = _hold_the_save_an_a2a_run_ends_with(monkeypatch)

    # The answer goes on with the run. The SDK first saves the task once more as it is, still waiting for
    # a person, with the answer in it. That save ends nothing: the run has only begun.
    answer = _text_message("Approve", message_id="m2", context_id=waiting["contextId"], task_id=waiting["id"])
    sent = await _jsonrpc(client, flow_id, "message/send", {**answer, "configuration": {"blocking": False}})
    assert sent.status_code == 200, sent.text

    await _the_pause_waits_for_the_held_save(client, headers, waiting["id"], reached, release)


@pytest.mark.parametrize("stored_by", ["this version", "a version before the owner of a public task had a name"])
async def test_an_answer_keeps_its_place_through_its_first_save_whichever_row_the_store_finds(
    client,  # noqa: ARG001
    config_dir,
    stored_by,
):
    from a2a.server.agent_execution import RequestContext
    from a2a.server.context import ServerCallContext
    from a2a.server.events import EventQueue
    from a2a.types import a2a_pb2 as pb
    from google.protobuf.json_format import MessageToDict
    from langflow.api.v1 import a2a, a2a_executor
    from langflow.services.authorization.public_access import PUBLIC_ANONYMOUS_ACTOR_ID
    from langflow.services.database.models import A2ATask

    _checked(config_dir, [PASSING], **PREPARED)
    flow_id, task_id = str(uuid4()), uuid4().hex
    caller = ServerCallContext(state={"flow_id": flow_id, "admitted_user_id": str(PUBLIC_ANONYMOUS_ACTOR_ID)})
    # An older version stored a public task under the flow alone. It is still read from there, and saved under
    # the owner of today, where the store then finds no row.
    owner = f"{flow_id}:{PUBLIC_ANONYMOUS_ACTOR_ID}" if stored_by == "this version" else f"{flow_id}:"
    waiting = pb.Task(id=task_id, context_id="c", status=pb.TaskStatus(state=pb.TaskState.TASK_STATE_INPUT_REQUIRED))
    async with session_scope() as session:
        session.add(A2ATask(id=task_id, owner=owner, task=MessageToDict(waiting)))
    read = await a2a._TASK_STORE.get(task_id, caller)
    arrived, release = asyncio.Event(), asyncio.Event()

    async def run(*_args) -> None:
        pytest.fail("an answer to a waiting task does not start a first run")

    async def resume(*_args) -> None:
        arrived.set()
        await release.wait()
        msg = "the run ends here"
        raise RuntimeError(msg)

    context = RequestContext(call_context=caller, task_id=task_id, context_id="c", task=read)
    running = asyncio.create_task(a2a_executor.FlowAgentExecutor(run, resume).execute(context, EventQueue()))
    await asyncio.wait_for(arrived.wait(), timeout=10)

    # The SDK's first save for an answer: the task as it is, still waiting, with the answer in it.
    await a2a._TASK_STORE.save(read, caller)
    release.set()
    await running

    # The run has returned, and what it ended with is still to be saved.
    assert not await migration_pause.drained(0)
    failed = pb.Task(id=task_id, context_id="c", status=pb.TaskStatus(state=pb.TaskState.TASK_STATE_FAILED))
    await a2a._TASK_STORE.save(failed, caller)
    # A loop of the app can be in the middle of a pass, which holds a place of its own for a moment.
    assert await migration_pause.drained(5)


async def test_an_a2a_run_still_going_keeps_its_place_when_its_task_is_saved_as_cancelled(
    client,  # noqa: ARG001
    config_dir,
    monkeypatch,
):
    from a2a.server.agent_execution import RequestContext
    from a2a.server.context import ServerCallContext
    from a2a.server.events import EventQueue
    from a2a.types import a2a_pb2 as pb
    from langflow.api.v1 import a2a, a2a_executor

    _checked(config_dir, [PASSING], **PREPARED)
    monkeypatch.setattr(a2a_executor, "_SAVE_GRACE", 0)
    arrived, release = asyncio.Event(), asyncio.Event()

    async def run(*_args) -> None:
        arrived.set()
        await release.wait()
        msg = "the run ends here"
        raise RuntimeError(msg)

    async def resume(*_args) -> None:
        pytest.fail("a first message does not resume a run")

    caller = ServerCallContext(state={"flow_id": str(uuid4()), "admitted_user_id": str(uuid4())})
    context = RequestContext(call_context=caller, task_id=uuid4().hex, context_id="c")
    running = asyncio.create_task(a2a_executor.FlowAgentExecutor(run, resume).execute(context, EventQueue()))
    await arrived.wait()

    # A tasks/cancel writes the task as cancelled at once. The run it cancels still goes, and still writes.
    cancelled = pb.TaskStatus(state=pb.TaskState.TASK_STATE_CANCELED)
    await a2a._TASK_STORE.save(pb.Task(id=context.task_id, context_id="c", status=cancelled), caller)

    assert not await migration_pause.drained(0.2)
    release.set()
    await running
    assert await migration_pause.drained(5)


async def test_the_wait_for_the_last_save_of_an_a2a_run_starts_again_at_each_save_of_its_task(
    client,  # noqa: ARG001
    config_dir,
):
    from a2a.server.events import EventQueue
    from a2a.types import a2a_pb2 as pb
    from langflow.api.v1 import a2a, a2a_executor

    _checked(config_dir, [PASSING], **PREPARED)
    executor, context, caller = _an_a2a_run_that_fails()
    await executor.execute(context, EventQueue())
    place = a2a_executor._places[context.task_id]
    given_up_at = place.giving_up.when()

    # The SDK saves what the run did one event after the other, and a slow reader can still be at an early one.
    working = pb.TaskStatus(state=pb.TaskState.TASK_STATE_WORKING)
    await a2a._TASK_STORE.save(pb.Task(id=context.task_id, context_id="c", status=working), caller)

    assert a2a_executor._places[context.task_id] is place
    assert place.giving_up.when() > given_up_at
    assert not await migration_pause.drained(0)

    failed = pb.TaskStatus(state=pb.TaskState.TASK_STATE_FAILED)
    await a2a._TASK_STORE.save(pb.Task(id=context.task_id, context_id="c", status=failed), caller)

    assert context.task_id not in a2a_executor._places
    assert place.giving_up.cancelled()
    # A loop of the app can be in the middle of a pass, which holds a place of its own for a moment.
    assert await migration_pause.drained(5)


async def test_an_a2a_run_whose_last_state_is_never_saved_gives_its_place_up(
    client,  # noqa: ARG001
    config_dir,
    monkeypatch,
):
    from a2a.server.events import EventQueue
    from langflow.api.v1 import a2a_executor

    _checked(config_dir, [PASSING], **PREPARED)
    monkeypatch.setattr(a2a_executor, "_SAVE_GRACE", 0.3)
    executor, context, _ = _an_a2a_run_that_fails()

    await executor.execute(context, EventQueue())

    # The SDK's reader may be gone. A place nobody can let go would refuse every pause from then on.
    assert not await migration_pause.drained(0)
    assert await migration_pause.drained(5)


async def test_a_refused_pause_leaves_a_pause_that_another_request_made(
    client, logged_in_headers_super_user, active_super_user, config_dir, monkeypatch
):
    headers, flow_id = logged_in_headers_super_user, uuid4()
    _checked(config_dir, [PASSING], **PREPARED)
    written, _ = _tell_when_the_pause_is_written(monkeypatch)
    arrived, release = asyncio.Event(), asyncio.Event()
    uploading = asyncio.create_task(_upload_held_open(client, headers, arrived, release))
    await arrived.wait()
    pausing = asyncio.create_task(client.post(PAUSE, headers=headers))
    await written.wait()

    # While this request waits, another worker's request pauses for itself, and a job is queued.
    record = (await _migration(client, headers))["record"]
    theirs = {"frozen_at": "2026-10-06T12:00:00+00:00", "frozen_by": "bob"}
    _write_record(config_dir, {**record, "pause": theirs})
    await _add(
        Flow(id=flow_id, name="nightly report", data={}, user_id=active_super_user.id),
        Job(job_id=uuid4(), flow_id=flow_id, user_id=active_super_user.id, status=JobStatus.QUEUED),
    )
    release.set()

    assert await uploading == 201
    assert (await pausing).status_code == 409
    assert (await _migration(client, headers))["record"]["pause"] == theirs


async def test_a_pause_request_that_is_cut_off_while_it_waits_leaves_no_pause_behind(
    client, logged_in_headers_super_user, config_dir, monkeypatch
):
    headers = logged_in_headers_super_user
    _checked(config_dir, [PASSING], **PREPARED)
    written, _ = _tell_when_the_pause_is_written(monkeypatch)
    arrived, release = asyncio.Event(), asyncio.Event()
    uploading = asyncio.create_task(_upload_held_open(client, headers, arrived, release))
    await arrived.wait()
    pausing = asyncio.create_task(client.post(PAUSE, headers=headers))
    await written.wait()

    # The request itself is cancelled while the pause waits for the upload. Nobody checked that pause.
    # A caller that hangs up does not cancel it on a server: that is the next test.
    pausing.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pausing

    assert not {"pause", "pausing"} & (await _migration(client, headers))["record"].keys()
    release.set()
    assert await uploading == 201


@pytest.fixture
async def served(client) -> AsyncIterator[str]:
    """The address of the app behind a real server.

    Only a server shows the app a caller that hangs up: it keeps the request going, and the app has to notice.
    """
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    # A test that fails with a request still open must not keep the server from stopping.
    config = uvicorn.Config(client._transport.app, lifespan="off", log_level="warning", timeout_graceful_shutdown=5)
    server = uvicorn.Server(config)
    serving = asyncio.create_task(server.serve(sockets=[sock]))
    while not server.started:  # noqa: ASYNC110
        await asyncio.sleep(0.05)
    yield f"http://127.0.0.1:{sock.getsockname()[1]}"
    server.should_exit = True
    await serving


async def _record_once(client, headers, settled: Callable[[dict], bool]) -> dict:
    """The record, read until it is as asked. A request that goes on without its caller tells the test nothing else."""

    async def read() -> dict:
        while not settled(record := (await _migration(client, headers))["record"]):  # noqa: ASYNC110
            await asyncio.sleep(0.02)
        return record

    return await asyncio.wait_for(read(), timeout=30)


async def test_a_pause_request_whose_caller_hangs_up_while_it_waits_leaves_no_pause_behind(
    client, served, logged_in_headers_super_user, config_dir
):
    headers = logged_in_headers_super_user
    _checked(config_dir, [PASSING], **PREPARED)
    arrived, release = asyncio.Event(), asyncio.Event()
    uploading = asyncio.create_task(_upload_held_open(client, headers, arrived, release))
    await arrived.wait()
    async with AsyncClient(base_url=served) as browser:
        pausing = asyncio.create_task(browser.post(PAUSE, headers=headers))
        await _record_once(client, headers, lambda record: "pausing" in record)
        # The admin's browser gives up while the pause waits for the upload. The server keeps the request going.
        pausing.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pausing
    # The upload ends after the server has seen the caller leave, as it does when a person gives up on a wait.
    await asyncio.sleep(0.2)
    release.set()
    assert await uploading == 201

    # The pause that waited refuses changes until the wait is over, at most _DRAIN_SECONDS after the caller left.
    record = await _record_once(client, headers, lambda record: "pausing" not in record)
    # Nobody was there to read that changes are paused, so nobody would know to turn them back on.
    assert "pause" not in record
    assert (await client.post("api/v1/flows/", json=NEW_FLOW, headers=headers)).status_code == 201


async def test_a_caller_that_stays_through_the_wait_is_answered_with_the_pause(
    client, served, logged_in_headers_super_user, config_dir
):
    headers = logged_in_headers_super_user
    _checked(config_dir, [PASSING], **PREPARED)
    arrived, release = asyncio.Event(), asyncio.Event()
    uploading = asyncio.create_task(_upload_held_open(client, headers, arrived, release))
    await arrived.wait()
    async with AsyncClient(base_url=served) as browser:
        pausing = asyncio.create_task(browser.post(PAUSE, headers=headers))
        await _record_once(client, headers, lambda record: "pausing" in record)
        release.set()
        assert await uploading == 201
        paused = await pausing

    assert paused.status_code == 200, paused.text
    assert "pause" in paused.json()["record"]
    assert (await client.post("api/v1/flows/", json=NEW_FLOW, headers=headers)).status_code == 503


async def test_a_caller_that_hangs_up_after_the_pause_was_written_leaves_changes_paused(
    client, served, logged_in_headers_super_user, config_dir
):
    headers = logged_in_headers_super_user
    _checked(config_dir, [PASSING], **PREPARED)
    address = urlparse(served)
    _, caller = await asyncio.open_connection(address.hostname, address.port)
    lines = [f"POST /{PAUSE} HTTP/1.1", "Host: testserver", "Content-Length: 0"]
    lines += [f"{name}: {value}" for name, value in headers.items()]
    caller.write("\r\n".join([*lines, "", ""]).encode())
    try:
        await caller.drain()
        await _record_once(client, headers, lambda record: "pause" in record)
    finally:
        # It was decided while the caller was there. The caller leaves without reading the answer.
        caller.close()
        await caller.wait_closed()
    await asyncio.sleep(0.2)

    assert "pause" in (await _migration(client, headers))["record"]
    assert (await client.post("api/v1/flows/", json=NEW_FLOW, headers=headers)).status_code == 503


async def test_the_listener_for_the_caller_ends_at_whatever_moment_the_wait_is_over():
    # Behind as many middlewares as the app has, a task group there can take one cancel() for its own.
    # The listener then goes on, and a route that waits for it to end never answers.
    for turns in range(40):
        app = FastAPI()
        for _ in range(6):

            @app.middleware("http")
            async def pass_on(request, call_next):
                return await call_next(request)

        @app.post("/wait")
        async def wait(request: Request, turns: int) -> None:
            listener = asyncio.create_task(migration_module._hung_up(request))
            for _ in range(turns):
                await asyncio.sleep(0)
            await migration_module._end(listener)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as caller:
            answered = await asyncio.wait_for(caller.post("/wait", params={"turns": turns}), timeout=5)
        assert answered.status_code == 200, f"after {turns} turns: {answered.text}"


async def test_the_pause_is_refused_while_another_worker_has_a_change_going(
    client, logged_in_headers_super_user, config_dir, monkeypatch
):
    pytest.importorskip("fcntl", reason="workers share the lock through flock")
    headers = logged_in_headers_super_user
    _checked(config_dir, [PASSING], **PREPARED)
    monkeypatch.setattr(migration_module, "_DRAIN_SECONDS", 0.2)
    env = {**os.environ, "LANGFLOW_CONFIG_DIR": str(config_dir), "LANGFLOW_FEATURE_INSTANCE_MIGRATION": "true"}
    pipe = asyncio.subprocess.PIPE
    worker = await asyncio.create_subprocess_exec(
        sys.executable, "-c", WORKER_WITH_A_CHANGE, env=env, stdin=pipe, stdout=pipe
    )
    try:
        said = b"the worker exited"
        # Imports may print before the worker says that it let its change in.
        async for line in worker.stdout:
            if line.startswith(b"let_in="):
                said = line
                break
        assert said == b"let_in=True\n"

        refused = await client.post(PAUSE, headers=headers)

        assert refused.status_code == 409, refused.text
        # The lock says that a place is held and never whose, so this worker can name none of it.
        assert refused.json()["detail"] == {
            "code": "requests_active",
            "jobs": [],
            "listeners": [],
            "changes": [],
            "elsewhere": True,
        }
        assert not {"pause", "pausing"} & (await _migration(client, headers))["record"].keys()
    finally:
        if worker.returncode is None:
            worker.stdin.write(b"\n")
            await worker.stdin.drain()
        await worker.wait()

    assert (await client.post(PAUSE, headers=headers)).status_code == 200


@pytest.mark.parametrize(
    ("pause", "check", "status", "expected"),
    [
        (None, PASSING, "done", ("current", None)),
        # A check from before the pause says nothing about what the instance held when it stopped.
        (PAUSED_AFTER_THE_CHECK, PASSING, "done", ("blocked", "recheck_pending")),
        (PAUSED_BEFORE_THE_CHECK, PASSING, "done", ("done", None)),
        (PAUSED_BEFORE_THE_CHECK, FAILING, "done", ("blocked", "recheck_failed")),
        # The re-check is still running, or it stopped before it could report.
        (PAUSED_BEFORE_THE_CHECK, PASSING, "cancelled", ("blocked", "recheck_pending")),
    ],
)
async def test_the_pause_step_is_done_once_a_check_started_after_it_passes(
    client, logged_in_headers_super_user, config_dir, pause, check, status, expected
):
    _checked(config_dir, [check], status, **PREPARED, **({"pause": pause} if pause else {}))

    steps = await _steps(client, logged_in_headers_super_user)

    assert steps["pause"] == expected


async def test_a_re_check_that_fails_reopens_the_check_and_keeps_what_was_done(
    client, logged_in_headers_super_user, config_dir
):
    _checked(config_dir, [FAILING], **PREPARED, pause=PAUSED_BEFORE_THE_CHECK)

    steps = await _steps(client, logged_in_headers_super_user)

    assert steps["check_source"] == ("blocked", "blocking_findings")
    assert steps["connect_target"] == ("done", None)
    assert steps["secret_key"] == ("done", None)
    assert steps["pause"] == ("blocked", "recheck_failed")
    assert steps["backup"] == ("locked", "earlier_step")


async def test_a_check_that_passes_after_the_pause_completes_the_step(client, logged_in_headers_super_user, config_dir):
    headers = logged_in_headers_super_user
    _checked(config_dir, [PASSING], **PREPARED)
    assert (await client.post(PAUSE, headers=headers)).status_code == 200
    assert (await _steps(client, headers))["pause"] == ("blocked", "recheck_pending")

    # The page starts the re-check, and the pause lets the migration routes through.
    await _run_checks(client, headers)

    steps = await _steps(client, headers)
    assert steps["pause"] == ("done", None)
    assert steps["backup"] == ("current", "not_available")


async def test_a_check_from_an_earlier_pause_does_not_count_for_the_next_one(
    client, logged_in_headers_super_user, config_dir
):
    headers = logged_in_headers_super_user
    _checked(config_dir, [PASSING], **PREPARED, pause=PAUSED_BEFORE_THE_CHECK)
    assert (await _steps(client, headers))["pause"] == ("done", None)

    # Changes made between the two pauses are in none of the checks or copies made before the second.
    await client.delete(PAUSE, headers=headers)
    await client.post(PAUSE, headers=headers)

    assert (await _steps(client, headers))["pause"] == ("blocked", "recheck_pending")


@pytest.mark.parametrize("status", [JobStatus.QUEUED, JobStatus.IN_PROGRESS])
async def test_the_pause_is_refused_while_a_job_is_still_writing(
    client, logged_in_headers_super_user, active_super_user, config_dir, status
):
    headers = logged_in_headers_super_user
    _checked(config_dir, [PASSING], **PREPARED)
    flow_id, job_id, started_at = uuid4(), uuid4(), datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
    await _add(
        Flow(id=flow_id, name="nightly report", data={}, user_id=active_super_user.id),
        Job(job_id=job_id, flow_id=flow_id, user_id=active_super_user.id, status=status, created_timestamp=started_at),
    )

    refused = await client.post(PAUSE, headers=headers)

    assert refused.status_code == 409
    assert refused.json()["detail"] == {
        "code": "jobs_active",
        "jobs": [
            {
                "id": str(job_id),
                "flow_name": "nightly report",
                "knowledge_base": None,
                "owner": "activeuser",
                "state": status.value,
                "started_at": started_at.isoformat(),
                "cancel": None,
            }
        ],
        "listeners": [],
        # The job is in the table, so the pause did not wait to learn what else is under way.
        "changes": [],
    }
    assert "pause" not in (await _migration(client, headers))["record"]
    assert (await client.post("api/v1/flows/", json=NEW_FLOW, headers=headers)).status_code == 201

    await get_job_service().update_job_status(job_id, JobStatus.COMPLETED)

    assert (await client.post(PAUSE, headers=headers)).status_code == 200


async def test_a_run_that_waits_for_a_person_does_not_hold_the_pause(
    client, logged_in_headers_super_user, active_super_user, config_dir
):
    headers, owner = logged_in_headers_super_user, active_super_user.id
    _checked(config_dir, [PASSING], **PREPARED)
    flow_id, waiting_id, running_id = uuid4(), uuid4(), uuid4()
    await _add(
        Flow(id=flow_id, name="needs a sign-off", data={}, user_id=owner),
        Job(job_id=waiting_id, flow_id=flow_id, user_id=owner, status=JobStatus.SUSPENDED),
        Job(job_id=running_id, flow_id=flow_id, user_id=owner, status=JobStatus.IN_PROGRESS),
    )

    refused = await client.post(PAUSE, headers=headers)

    # Next to a job that is running, the one that waits is not listed.
    assert refused.status_code == 409
    assert [job["id"] for job in refused.json()["detail"]["jobs"]] == [str(running_id)]

    await get_job_service().update_job_status(running_id, JobStatus.COMPLETED)

    assert (await client.post(PAUSE, headers=headers)).status_code == 200
    # It cannot write while changes are paused: the answer it waits for is a change, and that is refused.
    answer = {"request_id": "sign-off", "decision": {"approved": True}}
    answered = await client.post(f"api/v2/workflows/{waiting_id}/resume", json=answer, headers=headers)
    assert answered.status_code == 503


async def test_the_refusal_says_who_owns_each_job_and_how_to_cancel_it(
    client, logged_in_headers_super_user, active_super_user, config_dir
):
    _checked(config_dir, [PASSING], **PREPARED)
    admin, bob, flow_id, kb_id, ingestion_id = active_super_user.id, uuid4(), uuid4(), uuid4(), uuid4()
    background_id = uuid4()
    background = {"status": JobStatus.QUEUED, "job_metadata": {"request": {"mode": "background"}}}
    started = [datetime(2026, 10, 1, hour, tzinfo=timezone.utc) for hour in (9, 10, 11, 12)]
    await _add(
        User(id=bob, username="bob", password="never signs in"),  # noqa: S106  # pragma: allowlist secret
        Flow(id=flow_id, name="weekly digest", data={}, user_id=admin),
        # Marked by its own ingestion, which the job below already stands for.
        KnowledgeBaseRecord(id=kb_id, user_id=admin, name="q&a_handbook", status="ingesting", backend_type="postgres"),
        Job(job_id=background_id, flow_id=flow_id, user_id=admin, created_timestamp=started[0], **background),
        Job(job_id=uuid4(), flow_id=flow_id, user_id=admin, status=JobStatus.IN_PROGRESS, created_timestamp=started[1]),
        Job(
            job_id=ingestion_id,
            flow_id=ingestion_id,
            user_id=admin,
            status=JobStatus.QUEUED,
            type=JobType.INGESTION,
            asset_id=kb_id,
            asset_type="knowledge_base",
            created_timestamp=started[2],
        ),
        Job(job_id=uuid4(), flow_id=flow_id, user_id=bob, created_timestamp=started[3], **background),
    )

    refused = await client.post(PAUSE, headers=logged_in_headers_super_user)

    assert refused.status_code == 409
    # Each job comes with the whole request that cancels it, so the page sends it as it is.
    stop = {"method": "POST", "url": "/api/v2/workflows/stop", "body": {"job_id": str(background_id)}}
    cancel_ingestion = {"method": "POST", "url": "/api/v1/knowledge_bases/q%26a_handbook/cancel", "body": None}
    shown = ("flow_name", "knowledge_base", "owner", "state", "cancel")
    assert [tuple(job[key] for key in shown) for job in refused.json()["detail"]["jobs"]] == [
        ("weekly digest", None, "activeuser", "queued", stop),
        # It ends with the request that started it, so there is no route to stop it.
        ("weekly digest", None, "activeuser", "in_progress", None),
        (None, "q&a_handbook", "activeuser", "queued", cancel_ingestion),
        # A cancel route answers only the job's owner, so the admin is told whose job it is.
        ("weekly digest", None, "bob", "queued", None),
    ]


@pytest.mark.parametrize("kind", ["a background run", "an ingestion"])
async def test_a_job_cancelled_with_the_request_it_came_with_no_longer_holds_the_pause(
    client, logged_in_headers_super_user, active_super_user, config_dir, kind
):
    headers, owner = logged_in_headers_super_user, active_super_user.id
    _checked(config_dir, [PASSING], **PREPARED)
    flow_id, kb_id, job_id = uuid4(), uuid4(), uuid4()
    queued = {"status": JobStatus.QUEUED, "job_metadata": {"request": {"mode": "background"}}}
    ingesting = {"status": JobStatus.IN_PROGRESS, "type": JobType.INGESTION, "asset_type": "knowledge_base"}
    rows = {
        "a background run": [
            Flow(id=flow_id, name="queued in the background", data={}, user_id=owner),
            Job(job_id=job_id, flow_id=flow_id, user_id=owner, **queued),
        ],
        "an ingestion": [
            KnowledgeBaseRecord(id=kb_id, user_id=owner, name="handbook", backend_type="postgres"),
            Job(job_id=job_id, flow_id=job_id, user_id=owner, asset_id=kb_id, **ingesting),
        ],
    }
    await _add(*rows[kind])
    [job] = (await client.post(PAUSE, headers=headers)).json()["detail"]["jobs"]

    # Sent exactly as it came: the page knows nothing about either route.
    cancel = job["cancel"]
    cancelled = await client.request(cancel["method"], cancel["url"], json=cancel["body"], headers=headers)

    assert cancelled.status_code == 200, cancelled.text
    assert (await client.post(PAUSE, headers=headers)).status_code == 200


async def test_the_pause_is_refused_while_a_knowledge_base_is_marked_as_ingesting(
    client, logged_in_headers_super_user, active_super_user, config_dir
):
    _checked(config_dir, [PASSING], **PREPARED)
    kb_id, marked_at = uuid4(), datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
    # What an ingestion leaves when the server stops under it: the mark, and no job to cancel.
    await _add(
        KnowledgeBaseRecord(
            id=kb_id,
            user_id=active_super_user.id,
            name="handbook",
            status="ingesting",
            backend_type="postgres",
            updated_at=marked_at,
        )
    )

    refused = await client.post(PAUSE, headers=logged_in_headers_super_user)

    assert refused.status_code == 409
    assert refused.json()["detail"]["jobs"] == [
        {
            "id": str(kb_id),
            "flow_name": None,
            "knowledge_base": "handbook",
            "owner": "activeuser",
            "state": "ingesting",
            "started_at": marked_at.isoformat(),
            "cancel": None,
        }
    ]


async def test_the_pause_is_refused_while_a_trigger_listener_is_alive(client, logged_in_headers_super_user, config_dir):
    headers = logged_in_headers_super_user
    _checked(config_dir, [PASSING], **PREPARED)
    async with session_scope() as session:
        # A listener that was killed leaves a lease that has run out. One that is running keeps renewing its own.
        await replicas.announce(session, holder="listener:111:deadbeef", ttl_s=-1)
        await replicas.announce(session, holder="listener:222:cafef00d", ttl_s=30)

    refused = await client.post(PAUSE, headers=headers)

    assert refused.status_code == 409
    detail = refused.json()["detail"]
    assert (detail["code"], detail["jobs"]) == ("jobs_active", [])
    [listener] = detail["listeners"]
    assert listener["holder"] == "listener:222:cafef00d"
    assert datetime.fromisoformat(listener["heartbeat_at"]) <= datetime.now(timezone.utc)
    assert not {"pause", "pausing"} & (await _migration(client, headers))["record"].keys()

    async with session_scope() as session:
        # What a listener does when it is stopped.
        await replicas.withdraw(session, holder="listener:222:cafef00d")

    assert (await client.post(PAUSE, headers=headers)).status_code == 200
