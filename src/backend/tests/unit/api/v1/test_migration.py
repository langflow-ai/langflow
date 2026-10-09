"""Tests for the migration admin endpoints.

The source checks run the real migration-preflight command as a child process
against the test database, as the endpoint does in production.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from typing import TYPE_CHECKING
from uuid import uuid4

import langflow.api.router as api_router_module
import pytest
from anyio import Path as AsyncPath
from fastapi import APIRouter
from langflow.api.v1.migration import _source_env
from langflow.services.database.models.file.model import File
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord
from langflow.services.deps import get_db_service, get_settings_service, get_storage_service, session_scope
from langflow.utils.version import get_version_info

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path

VERSION = get_version_info()["version"]


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
def config_dir(client, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:  # noqa: ARG001
    """The migration record is written under CONFIG_DIR, so keep it out of the real one."""
    monkeypatch.setattr(get_settings_service().settings, "config_dir", str(tmp_path))
    return tmp_path


async def _run_checks(client, headers, target_version: str = VERSION) -> list[dict]:
    response = await client.post("api/v1/migration/checks", json={"target_version": target_version}, headers=headers)
    assert response.status_code == 200, response.text
    return [json.loads(event) for event in response.text.split("\n\n") if event]


async def _migration(client, headers) -> dict:
    response = await client.get("api/v1/migration", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _write_record(config_dir: Path, record: dict) -> None:
    (config_dir / "migrations").mkdir(exist_ok=True)
    (config_dir / "migrations" / "migration.json").write_text(json.dumps(record))


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
    ]

    assert [response.status_code for response in refused] == [403, 403, 403, 403]


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


def _checked(config_dir: Path, checks: list[dict]) -> None:
    """A finished source check with these results."""
    step = {"status": "done", "started_by": "alice", "started_at": "2026-09-30T00:00:00+00:00"}
    report = {"event": "report", "checks": checks}
    _write_record(
        config_dir,
        {
            "target": {"version": VERSION, "set_by": "alice", "set_at": step["started_at"]},
            "steps": {"check_source": {**step, "target_version": VERSION, "report": report}},
            "accepted_findings": [],
        },
    )


async def test_after_the_check_the_next_needed_step_is_current_and_the_rest_wait(
    client, logged_in_headers_super_user, config_dir
):
    _checked(config_dir, [{"name": "version", "status": "ok", "summary": "same version"}])

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
    _checked(config_dir, [{"name": "source: credentials", "status": "fail", "summary": "2 values do not open"}])

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
