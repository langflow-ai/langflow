"""Tests for hot-reloading flows from ``LANGFLOW_LOAD_FLOWS_PATH`` (issue #11918)."""

import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import orjson
import pytest
from langflow.initial_setup import setup
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.trigger.model import TriggerLease
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_settings_service

LEASE_NAME = setup._WATCH_FLOWS_LEASE_NAME
OWNER = "flows-watch:test"


@pytest.fixture
def watch_settings(async_session, monkeypatch, tmp_path):
    settings = get_settings_service()
    monkeypatch.setattr(settings.settings, "load_flows_path", str(tmp_path))
    monkeypatch.setattr(settings.settings, "watch_flows_path", True)

    @asynccontextmanager
    async def session_scope():
        yield async_session
        await async_session.commit()

    monkeypatch.setattr(setup, "session_scope", session_scope)
    return settings


@pytest.fixture
async def superuser(async_session, watch_settings, monkeypatch):
    user = User(id=UUID(int=7), username="admin", password=uuid4().hex, is_superuser=True, is_active=True)
    async_session.add(user)
    await async_session.commit()
    monkeypatch.setattr(watch_settings.auth_settings, "SUPERUSER", "admin")
    return user


def _write_flow(tmp_path, name, payload, *, mtime=None):
    path = tmp_path / name
    path.write_bytes(orjson.dumps(payload))
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


async def _run_pass(tmp_path, applied):
    await setup._watch_flows_pass(str(tmp_path), applied, owner=OWNER, ttl_s=30.0)


async def test_scan_lists_top_level_json_files_only(tmp_path):
    _write_flow(tmp_path, "a.json", {"name": "A"})
    (tmp_path / "notes.txt").write_text("not a flow")
    (tmp_path / "nested").mkdir()
    _write_flow(tmp_path / "nested", "b.json", {"name": "B"})

    assert set(setup._scan_flow_files(str(tmp_path))) == {"a.json"}


async def test_new_file_creates_flow(async_session, superuser, tmp_path):
    flow_id = uuid4()
    _write_flow(tmp_path, "new.json", {"id": str(flow_id), "name": "New flow", "data": {}})
    applied: dict = {}

    await _run_pass(tmp_path, applied)

    created = await async_session.get(Flow, flow_id)
    assert created is not None
    assert created.user_id == superuser.id
    assert "new.json" in applied


@pytest.mark.usefixtures("superuser")
async def test_changed_file_updates_flow(async_session, tmp_path):
    flow_id = uuid4()
    path = _write_flow(tmp_path, "flow.json", {"id": str(flow_id), "name": "Flow", "description": "v1", "data": {}})
    applied: dict = {}
    await _run_pass(tmp_path, applied)

    later = path.stat().st_mtime + 5
    _write_flow(
        tmp_path, "flow.json", {"id": str(flow_id), "name": "Flow", "description": "v2", "data": {}}, mtime=later
    )
    await _run_pass(tmp_path, applied)

    flow = await async_session.get(Flow, flow_id)
    await async_session.refresh(flow)
    assert flow.description == "v2"


@pytest.mark.usefixtures("superuser")
async def test_unchanged_file_is_not_reapplied(tmp_path, monkeypatch):
    flow_id = uuid4()
    _write_flow(tmp_path, "flow.json", {"id": str(flow_id), "name": "Flow", "data": {}})
    applied: dict = {}
    await _run_pass(tmp_path, applied)

    calls = []

    async def record_upsert(*args, **_kwargs):
        calls.append(args)

    monkeypatch.setattr(setup, "upsert_flow_from_file", record_upsert)
    await _run_pass(tmp_path, applied)

    assert calls == []


@pytest.mark.usefixtures("superuser")
async def test_invalid_json_is_skipped_and_other_files_still_apply(async_session, tmp_path):
    (tmp_path / "broken.json").write_text('{"name": "half-writ')
    good_id = uuid4()
    _write_flow(tmp_path, "good.json", {"id": str(good_id), "name": "Good", "data": {}})
    applied: dict = {}

    await _run_pass(tmp_path, applied)

    assert await async_session.get(Flow, good_id) is not None


@pytest.mark.usefixtures("superuser")
async def test_invalid_json_is_retried_once_the_file_changes(async_session, tmp_path):
    path = tmp_path / "flow.json"
    path.write_text('{"name": "half-writ')
    applied: dict = {}
    await _run_pass(tmp_path, applied)

    flow_id = uuid4()
    later = path.stat().st_mtime + 5
    _write_flow(tmp_path, "flow.json", {"id": str(flow_id), "name": "Finished", "data": {}}, mtime=later)
    await _run_pass(tmp_path, applied)

    assert await async_session.get(Flow, flow_id) is not None


@pytest.mark.usefixtures("superuser")
async def test_removed_file_keeps_flow_and_warns_once(async_session, tmp_path, monkeypatch):
    flow_id = uuid4()
    path = _write_flow(tmp_path, "flow.json", {"id": str(flow_id), "name": "Flow", "data": {}})
    applied: dict = {}
    await _run_pass(tmp_path, applied)
    warnings = _capture_warnings(monkeypatch)
    path.unlink()
    await _run_pass(tmp_path, applied)
    await _run_pass(tmp_path, applied)

    assert await async_session.get(Flow, flow_id) is not None
    assert len([w for w in warnings if "flow.json" in w]) == 1


@pytest.mark.usefixtures("superuser")
async def test_pass_does_nothing_without_the_lease(async_session, tmp_path):
    now = datetime.now(timezone.utc)
    async_session.add(
        TriggerLease(
            name=LEASE_NAME,
            owner="flows-watch:another-worker",
            acquired_at=now,
            heartbeat_at=now,
            expires_at=now + timedelta(minutes=5),
        )
    )
    await async_session.commit()
    flow_id = uuid4()
    _write_flow(tmp_path, "flow.json", {"id": str(flow_id), "name": "Flow", "data": {}})
    applied: dict = {}

    await _run_pass(tmp_path, applied)

    assert await async_session.get(Flow, flow_id) is None
    assert applied == {}


async def _edit_in_ui(async_session, flow_id, description):
    flow = await async_session.get(Flow, flow_id)
    flow.description = description
    async_session.add(flow)
    await async_session.commit()
    return flow


def _capture_warnings(monkeypatch):
    warnings = []

    async def record_warning(message, *_args, **_kwargs):
        warnings.append(message)

    monkeypatch.setattr(setup.logger, "awarning", record_warning)
    return warnings


@pytest.mark.usefixtures("superuser")
async def test_overwriting_a_ui_edited_flow_warns(async_session, tmp_path, monkeypatch):
    flow_id = uuid4()
    path = _write_flow(tmp_path, "flow.json", {"id": str(flow_id), "name": "Flow", "description": "file", "data": {}})
    applied: dict = {}
    await _run_pass(tmp_path, applied)

    flow = await _edit_in_ui(async_session, flow_id, "edited in the UI")
    warnings = _capture_warnings(monkeypatch)
    later = path.stat().st_mtime + 5
    _write_flow(
        tmp_path, "flow.json", {"id": str(flow_id), "name": "Flow", "description": "file v2", "data": {}}, mtime=later
    )
    await _run_pass(tmp_path, applied)

    await async_session.refresh(flow)
    assert flow.description == "file v2"
    assert any("edited since" in w and "'Flow'" in w for w in warnings)


@pytest.mark.usefixtures("superuser")
async def test_overwriting_an_unedited_flow_does_not_warn(tmp_path, monkeypatch):
    flow_id = uuid4()
    path = _write_flow(tmp_path, "flow.json", {"id": str(flow_id), "name": "Flow", "description": "v1", "data": {}})
    applied: dict = {}
    await _run_pass(tmp_path, applied)

    warnings = _capture_warnings(monkeypatch)
    later = path.stat().st_mtime + 5
    _write_flow(
        tmp_path, "flow.json", {"id": str(flow_id), "name": "Flow", "description": "v2", "data": {}}, mtime=later
    )
    await _run_pass(tmp_path, applied)

    assert not any("edited since" in w for w in warnings)


@pytest.mark.usefixtures("superuser")
async def test_ui_edit_to_a_startup_loaded_flow_warns(async_session, tmp_path, monkeypatch):
    flow_id = uuid4()
    path = _write_flow(tmp_path, "flow.json", {"id": str(flow_id), "name": "Flow", "description": "file", "data": {}})
    await setup.load_flows_from_directory()
    applied = await setup._prime_applied_flow_files(str(tmp_path))

    await _edit_in_ui(async_session, flow_id, "edited in the UI")
    warnings = _capture_warnings(monkeypatch)
    later = path.stat().st_mtime + 5
    _write_flow(
        tmp_path, "flow.json", {"id": str(flow_id), "name": "Flow", "description": "file v2", "data": {}}, mtime=later
    )
    await _run_pass(tmp_path, applied)

    assert any("edited since" in w for w in warnings)


@pytest.mark.usefixtures("superuser")
async def test_priming_does_not_reapply_startup_files(tmp_path, monkeypatch):
    _write_flow(tmp_path, "flow.json", {"id": str(uuid4()), "name": "Flow", "data": {}})
    await setup.load_flows_from_directory()
    applied = await setup._prime_applied_flow_files(str(tmp_path))
    calls = []

    async def record_upsert(*args, **_kwargs):
        calls.append(args)

    monkeypatch.setattr(setup, "upsert_flow_from_file", record_upsert)
    await _run_pass(tmp_path, applied)

    assert calls == []


async def test_watch_without_load_flows_path_warns_and_returns(monkeypatch):
    settings = get_settings_service()
    monkeypatch.setattr(settings.settings, "load_flows_path", None)
    monkeypatch.setattr(settings.settings, "watch_flows_path", True)
    warnings = _capture_warnings(monkeypatch)

    await setup.watch_flows_from_directory()

    assert any("LANGFLOW_LOAD_FLOWS_PATH" in w for w in warnings)


async def test_watch_with_missing_directory_warns_and_returns(monkeypatch, tmp_path):
    settings = get_settings_service()
    monkeypatch.setattr(settings.settings, "load_flows_path", str(tmp_path / "missing"))
    monkeypatch.setattr(settings.settings, "watch_flows_path", True)
    warnings = _capture_warnings(monkeypatch)

    await setup.watch_flows_from_directory()

    assert any("not a directory" in w for w in warnings)


def test_watch_flows_path_defaults_to_off():
    from lfx.services.settings.base import Settings

    assert Settings.model_fields["watch_flows_path"].default is False
