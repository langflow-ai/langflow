"""The real command exports usage for healthy flows without writing either source."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from uuid import uuid4

import pytest

from tests.unit.upgrade_check.test_command import _events, _upgrade_check
from tests.unit.upgrade_check.test_reader import RELEASES, _load, _url
from tests.unit.upgrade_check.test_usage import _database, _insert


def test_cli_exports_all_checked_flows_and_separate_editor_serving_evidence(tmp_path):
    source = _load("1.13.0", tmp_path)
    with sqlite3.connect(source) as connection:
        [(flow_id,)] = connection.execute("SELECT id FROM flow WHERE is_component = 0")
        connection.execute(
            "INSERT INTO job(job_id, flow_id, type, status, created_timestamp) VALUES (?, ?, ?, ?, ?)",
            (uuid4().hex, flow_id, "workflow", "completed", "2026-10-01 12:00:00"),
        )
        connection.execute(
            "INSERT INTO job(job_id, flow_id, type, status, created_timestamp) VALUES (?, ?, ?, ?, ?)",
            (uuid4().hex, flow_id, "workflow", "queued", "2026-10-05 12:00:00"),
        )
    serving_dir = tmp_path / "serving"
    serving_dir.mkdir()
    serving = _database(serving_dir)
    _insert(serving, flow_id, "failed", when="2026-10-02T18:00:00+02:00")
    output = tmp_path / "report.json"
    before = [hashlib.sha256(path.read_bytes()).hexdigest() for path in (source, serving)]

    result = _upgrade_check(
        "--database-url", _url(source), "--serving-database-url", _url(serving), "--json", "--output", output
    )

    assert result.returncode == 0, result.stderr
    events = _events(result)
    report = events[-1]["report"]
    assert json.loads(output.read_text()) == report
    assert report["flows"] == [event["flow"] for event in events[:-1]]
    assert len(report["flows"]) == sum(report["summary"]["flows"].values()) == 3
    flow = next(item for item in report["flows"] if item["kind"] == "flow")
    usage = flow["usage"]
    assert (usage["editor"]["runs"], usage["editor"]["errors"]) == (1, 0)
    assert (usage["serving"]["runs"], usage["serving"]["errors"]) == (1, 1)
    assert usage["editor"]["last_run_at"] == "2026-10-01T12:00:00Z"
    assert usage["serving"]["last_run_at"] == "2026-10-02T16:00:00Z"
    assert usage["serving"]["source_identity"]["locator"]["path"] == str(serving.resolve())
    version = next(item for item in report["flows"] if item["kind"] == "flow_version")
    assert version["usage"]["editor"]["runs"] == 1
    assert "usage_is_flow_level_not_version_specific" in version["usage"]["editor"]["limitations"]
    component = next(item for item in report["flows"] if item["kind"] == "component")
    assert component["usage"]["editor"]["runs"] is None
    assert component["usage"]["editor"]["limitations"] == ["saved_component_not_executable"]
    assert [hashlib.sha256(path.read_bytes()).hexdigest() for path in (source, serving)] == before


@pytest.mark.parametrize("alias", ["direct", "hardlink"])
def test_report_cannot_overwrite_the_serving_database(alias, tmp_path):
    source = _load("1.13.0", tmp_path)
    serving_dir = tmp_path / "serving"
    serving_dir.mkdir()
    serving = _database(serving_dir)
    output = serving if alias == "direct" else tmp_path / "report.json"
    if alias == "hardlink":
        output.hardlink_to(serving)
    before = serving.read_bytes()

    result = _upgrade_check(
        "--database-url", _url(source), "--serving-database-url", _url(serving), "--json", "--output", output
    )

    assert result.returncode == 2, result.stderr
    [event] = _events(result)
    assert event["code"] == "output_aliases_source"
    assert serving.read_bytes() == before


@pytest.mark.parametrize("release", RELEASES)
def test_historical_job_schemas_report_explicit_coverage(release, tmp_path):
    from langflow.upgrade_check.reader import read_only_connection
    from langflow.upgrade_check.usage_reader import read_job_usage

    source = _load(release, tmp_path)
    before = source.read_bytes()
    with read_only_connection(_url(source)) as connection:
        usage = read_job_usage(connection).for_flow(str(uuid4()))
    assert usage.coverage.complete is False
    assert usage.coverage.retention_days is None
    assert usage.history in {"no_retained_records", "unavailable"}
    if usage.history == "unavailable":
        assert usage.limitations
    assert source.read_bytes() == before
