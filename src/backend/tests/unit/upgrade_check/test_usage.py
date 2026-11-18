"""Retained jobs report execution evidence without inventing complete history."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from langflow.upgrade_check.reader import SourceDatabaseError, read_only_connection
from langflow.upgrade_check.usage_reader import read_job_usage, read_serving_usage


def _database(tmp_path, columns="flow_id TEXT, type TEXT, status TEXT, created_timestamp TEXT"):
    path = tmp_path / "jobs.db"
    with sqlite3.connect(path) as connection:
        connection.execute(f"CREATE TABLE job ({columns})")
    return path


def _insert(path, flow_id, status, *, job_type="workflow", when="2026-10-01 12:00:00"):
    with sqlite3.connect(path) as connection:
        connection.execute("INSERT INTO job VALUES (?, ?, ?, ?)", (flow_id, job_type, status, when))


def _read(path):
    with read_only_connection(f"sqlite:///{path}") as connection:
        return read_job_usage(connection)


def test_counts_execution_statuses_and_excludes_unrelated_jobs(tmp_path):
    path = _database(tmp_path)
    flow_id = uuid4()
    for status in ("queued", "in_progress", "completed", "failed", "timed_out", "suspended", "cancelled"):
        _insert(path, flow_id.hex, status)
    _insert(path, flow_id.hex, "failed", job_type="ingestion")
    _insert(path, flow_id.hex, "failed", job_type="evaluation")
    _insert(path, flow_id.hex, "completed", job_type=None)
    before = path.read_bytes()

    usage = _read(path).for_flow(str(flow_id))

    assert (usage.runs, usage.errors) == (5, 2)
    assert usage.history == "retained_records"
    assert usage.last_run_at == "2026-10-01T12:00:00Z"
    assert "cancelled_start_unknown" in usage.limitations
    assert "unclassified_job_type_excluded" in usage.limitations
    assert path.read_bytes() == before


def test_queued_and_canceled_jobs_are_not_execution_evidence(tmp_path):
    path = _database(tmp_path)
    flow_id = str(uuid4())
    _insert(path, flow_id, "queued")
    _insert(path, flow_id, "cancelled")

    usage = _read(path).for_flow(flow_id)

    assert (usage.runs, usage.errors, usage.last_run_at) == (0, 0, None)
    assert usage.history == "retained_records"
    assert usage.coverage.complete is False


def test_zero_retained_jobs_does_not_mean_never_ran(tmp_path):
    path = _database(tmp_path)
    _insert(path, str(uuid4()), "completed")

    usage = _read(path).for_flow(str(uuid4()))

    assert (usage.runs, usage.errors) == (0, 0)
    assert usage.history == "no_retained_records"
    assert usage.coverage.complete is False
    assert usage.coverage.retention_days is None
    assert usage.coverage.oldest_retained_at is None
    assert "retained_jobs_only" in usage.limitations


@pytest.mark.parametrize("missing", ["flow_id", "type", "status", "created_timestamp"])
def test_missing_columns_are_explicitly_unavailable(tmp_path, missing):
    columns = [f"{name} TEXT" for name in ("flow_id", "type", "status", "created_timestamp") if name != missing]
    path = _database(tmp_path, ", ".join(columns))

    usage = _read(path).for_flow(str(uuid4()))

    assert (usage.runs, usage.errors, usage.last_run_at) == (None, None, None)
    assert usage.history == "unavailable"
    assert f"job_column_missing:{missing}" in usage.limitations


def test_missing_job_table_and_unconfigured_serving_are_unknown(tmp_path):
    path = tmp_path / "empty.db"
    with sqlite3.connect(path):
        pass
    flow_id = str(uuid4())

    assert _read(path).for_flow(flow_id).limitations == ["job_table_missing"]
    serving = read_serving_usage(None).for_flow(flow_id)
    assert serving.history == "unavailable"
    assert serving.runs is None
    assert serving.limitations == ["serving_not_configured"]


@pytest.mark.parametrize("failure", [ImportError("driver unavailable"), SourceDatabaseError("folder unavailable")])
def test_optional_serving_failure_preserves_editor_assessment(monkeypatch, tmp_path, failure):
    from dataclasses import asdict

    from langflow.upgrade_check import command, usage_reader
    from langflow.upgrade_check.engine import TargetSettings

    from tests.unit.upgrade_check.test_reader import _load, _url

    def refuse(_url):
        raise failure

    source = _load("1.13.0", tmp_path)
    before = source.read_bytes()
    monkeypatch.setattr(usage_reader, "read_only_connection", refuse)
    monkeypatch.setattr(command, "load_upgrade_registry", lambda **_kwargs: {})

    options = {
        "database_url": _url(source),
        "serving_database_url": "postgresql://unavailable.invalid/langflow",
        "settings": asdict(TargetSettings()),
        "output": None,
        "json": True,
    }
    baseline, _ = command.run({**options, "serving_database_url": None})
    report, _listed = command.run(options)

    assert report["summary"] == baseline["summary"]
    assert len(report["flows"]) == 3
    for row in report["flows"]:
        if row["kind"] != "component":
            assert row["usage"]["editor"]["history"] != "unavailable"
            assert row["usage"]["serving"]["history"] == "unavailable"
            assert "serving_source_unreadable" in row["usage"]["serving"]["limitations"]
    assert source.read_bytes() == before


def test_serving_adapter_joins_preserved_editor_id_without_names_or_versions(tmp_path):
    path = _database(tmp_path)
    editor_id, other_id = uuid4(), uuid4()
    _insert(path, editor_id.hex, "completed", when="2026-10-02T18:30:00+02:00")
    _insert(path, editor_id.hex, "failed", when="2026-10-02T17:00:00Z")
    _insert(path, other_id.hex, "failed", when="2026-10-03 19:00:00")
    before = path.read_bytes()

    snapshot = read_serving_usage(f"sqlite:///{path}")
    usage = snapshot.for_flow(str(editor_id))

    assert (usage.runs, usage.errors) == (2, 1)
    assert usage.last_run_at == "2026-10-02T17:00:00Z"
    assert usage.coverage.oldest_retained_at == "2026-10-02T16:30:00Z"
    assert usage.coverage.newest_retained_at == "2026-10-02T17:00:00Z"
    absent = snapshot.for_flow(str(uuid4()))
    assert absent.history == "no_retained_records"
    assert "preserved_editor_flow_id_not_observed" in absent.limitations
    assert path.read_bytes() == before


def test_invalid_timestamps_and_unknown_statuses_do_not_invent_last_run(tmp_path):
    path = _database(tmp_path)
    flow_id = str(uuid4())
    _insert(path, flow_id, "completed", when="not a timestamp")
    _insert(path, flow_id, "new_status", when="2026-10-04 19:00:00")
    _insert(path, "not-a-flow-id", "completed")

    usage = _read(path).for_flow(flow_id)

    assert (usage.runs, usage.errors, usage.last_run_at) == (1, 0, None)
    assert "job_timestamps_invalid" in usage.limitations
    assert "unknown_job_status_excluded" in usage.limitations
    assert "job_flow_id_invalid" in usage.limitations


def test_unreadable_serving_does_not_leak_connection_credentials():
    snapshot = read_serving_usage("postgresql://private-user:private-password@127.0.0.1:1/app?connect_timeout=1")
    usage = snapshot.for_flow(str(uuid4()))

    assert usage.history == "unavailable"
    assert usage.limitations == ["serving_source_unreadable"]
    assert "private" not in usage.model_dump_json()
    assert datetime.fromisoformat(usage.coverage.observed_at.replace("Z", "+00:00")).tzinfo == timezone.utc


@pytest.mark.parametrize(
    "stamp",
    [
        "2026-02-30T12:00:00Z",
        "2026-02-29T12:00:00Z",
        "2026-13-01T12:00:00Z",
        "2026-10-01T24:00:00Z",
        "2026-10-01T12:60:00Z",
        "2026-10-01T12:00:60Z",
        "2026-10-01T12:00:00+24:00",
        "2026-10-01T12:00:00+00:99",
        "2026-10-01T12:00:00-00:99",
        "2026-10-01",
        "0001-01-01T00:00:00+23:59",
        "9999-12-31T23:59:59-23:59",
        "NaN",
        123,
        float("nan"),
        b"not a timestamp",
        None,
    ],
)
def test_invalid_original_timestamps_stay_unknown_before_sqlite_normalization(tmp_path, stamp):
    path = _database(tmp_path)
    flow_id = str(uuid4())
    _insert(path, flow_id, "completed", when=stamp)
    before = path.read_bytes()

    usage = _read(path).for_flow(flow_id)

    assert (usage.runs, usage.errors, usage.last_run_at) == (1, 0, None)
    assert usage.coverage.oldest_retained_at is None
    assert usage.coverage.newest_retained_at is None
    assert "job_timestamps_invalid" in usage.limitations
    assert path.read_bytes() == before


def test_valid_offsets_and_subseconds_are_ordered_before_sqlite_aggregation(tmp_path):
    path = _database(tmp_path)
    flow_id = str(uuid4())
    _insert(path, flow_id, "completed", when="2024-02-29T23:30:00.123456+02:00")
    _insert(path, flow_id, "completed", when="2024-02-29T21:30:00Z")
    _insert(path, flow_id, "failed", when="2024-02-29T21:30:00.2Z")
    before = path.read_bytes()

    usage = _read(path).for_flow(flow_id)

    assert (usage.runs, usage.errors) == (3, 1)
    assert usage.last_run_at == "2024-02-29T21:30:00.200000Z"
    assert usage.coverage.oldest_retained_at == "2024-02-29T21:30:00Z"
    assert usage.coverage.newest_retained_at == "2024-02-29T21:30:00.200000Z"
    assert "job_timestamps_invalid" not in usage.limitations
    assert path.read_bytes() == before


def test_invalid_execution_time_does_not_claim_a_later_known_run(tmp_path):
    path = _database(tmp_path)
    flow_id = str(uuid4())
    _insert(path, flow_id, "completed", when="2026-02-28 12:00:00.123456")
    _insert(path, flow_id, "failed", when="2026-02-30T12:00:00Z")

    usage = _read(path).for_flow(flow_id)

    assert (usage.runs, usage.errors, usage.last_run_at) == (2, 1, None)
    assert usage.coverage.oldest_retained_at == "2026-02-28T12:00:00.123456Z"
    assert usage.coverage.newest_retained_at == "2026-02-28T12:00:00.123456Z"
    assert "job_timestamps_invalid" in usage.limitations
