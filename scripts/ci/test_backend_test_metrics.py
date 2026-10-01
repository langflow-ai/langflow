"""Exercise CI reporting with actual pytest runs, including interrupted and flaky suites."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def run_suite(tmp_path, source, *args):
    (tmp_path / "test_sample.py").write_text(source)
    reports = tmp_path / "reports"
    env = {**os.environ, "PYTHONPATH": str(ROOT), "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
    result = subprocess.run(  # noqa: S603 - fixed interpreter and test-owned source
        [
            sys.executable,
            "-m",
            "pytest",
            "-c",
            "/dev/null",
            "-p",
            "no:cacheprovider",
            "-p",
            "scripts.ci.backend_test_metrics",
            "--ci-report-dir",
            str(reports),
            *args,
            str(tmp_path / "test_sample.py"),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=45,
    )
    assert (reports / "summary.json").exists(), result.stdout + result.stderr
    return result, reports, json.loads((reports / "summary.json").read_text())


def test_records_all_phases_and_collection(tmp_path):
    result, reports, summary = run_suite(tmp_path, "def test_ok(): assert True\n")
    assert result.returncode == 0
    assert summary["complete"] is True
    assert summary["selected"] == 1
    assert summary["phase_seconds"].keys() == {"setup", "call", "teardown"}
    events = [json.loads(line) for line in (reports / "events.jsonl").read_text().splitlines()]
    assert [e["when"] for e in events] == ["setup", "call", "teardown"]
    assert len(json.loads((reports / "durations.json").read_text())) == 1


def test_failed_or_interrupted_runs_never_publish_a_baseline(tmp_path):
    result, reports, summary = run_suite(tmp_path, "def test_a(): assert False\ndef test_b(): pass\n", "-x")
    assert result.returncode == 1
    assert summary["complete"] is False
    assert summary["selected"] == 2
    assert not (reports / "durations.json").exists()
    assert (reports / "events.jsonl").stat().st_size > 0


def test_xdist_collects_once_and_records_worker_reports(tmp_path):
    result, _, summary = run_suite(
        tmp_path, "def test_a(): pass\ndef test_b(): pass\n", "-p", "xdist.plugin", "-n", "2"
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert summary["selected"] == 2
    assert summary["complete"] is True


def test_retry_preserves_first_failure_and_excludes_flake_from_timings(tmp_path):
    source = """from pathlib import Path
def test_flaky():
    marker = Path('attempt')
    if not marker.exists():
        marker.touch()
        assert False, 'first failure'
"""
    result, reports, summary = run_suite(tmp_path, source, "-p", "rerunfailures", "--reruns", "1")
    assert result.returncode == 0, result.stdout + result.stderr
    assert summary["reruns"] == 1
    assert summary["complete"] is True
    assert json.loads((reports / "durations.json").read_text()) == {}
    assert "first failure" in (reports / "events.jsonl").read_text()


def test_merge_rejects_missing_or_overlapping_shards(tmp_path):
    from scripts.ci.backend_test_metrics import merge_reports

    _, reports, _ = run_suite(tmp_path, "def test_ok(): pass\n")
    with pytest.raises(ValueError, match="Expected 2"):
        merge_reports([reports], 2)
    with pytest.raises(ValueError, match="overlap"):
        merge_reports([reports, reports], 2)


def test_merge_publishes_complete_disjoint_shards(tmp_path):
    from scripts.ci.backend_test_metrics import merge_reports

    directories = []
    expected = {}
    for name in ("a", "b"):
        shard = tmp_path / name
        shard.mkdir()
        result, reports, summary = run_suite(shard, f"def test_{name}(): pass\n")
        assert result.returncode == 0
        assert summary["complete"] is True
        directories.append(reports)
        expected.update(json.loads((reports / "durations.json").read_text()))
    merged = merge_reports(directories, 2)
    assert len(merged) == 2
    assert merged == expected


def test_worker_crash_keeps_reports_but_cannot_publish_timings(tmp_path):
    result, reports, summary = run_suite(
        tmp_path,
        "import os\ndef test_crash(): os._exit(1)\n",
        "-p",
        "xdist.plugin",
        "-n",
        "1",
        "--max-worker-restart=0",
    )
    assert result.returncode != 0
    assert summary["worker_crashes"] == 1
    assert summary["complete"] is False
    assert "worker_crash" in (reports / "events.jsonl").read_text()
    assert not (reports / "durations.json").exists()


def test_worker_timeout_preserves_blocked_stack(tmp_path):
    result, reports, summary = run_suite(
        tmp_path,
        "import time\ndef test_blocked(): time.sleep(30)\n",
        "-p",
        "xdist.plugin",
        "-p",
        "pytest_timeout",
        "-n",
        "1",
        "--timeout=2",
        "--timeout-method=thread",
        "--max-worker-restart=0",
    )
    assert result.returncode != 0
    assert summary["complete"] is False
    assert summary["worker_crashes"] == 1
    stacks = (reports / "stacks-gw0.txt").read_text()
    assert "Approaching test timeout:" in stacks
    assert "test_blocked" in stacks
    assert "test_sample.py" in stacks


def test_success_cancels_timeout_diagnostic(tmp_path):
    result, reports, summary = run_suite(tmp_path, "def test_ok(): pass\n", "-p", "pytest_timeout", "--timeout=1")
    assert result.returncode == 0
    assert summary["complete"] is True
    assert (reports / "stacks-master.txt").read_text() == ""


@pytest.mark.parametrize(
    "marker",
    [
        "reruns=5",
        "reruns=1, reason='https://github.com/langflow-ai/langflow'",
        "reruns=1, reason='https://github.com/langflow-ai/langflow/pull/123'",
        "reruns=True, reason='https://github.com/langflow-ai/langflow/issues/123'",
    ],
)
def test_ci_rejects_untracked_blanket_flake_markers(tmp_path, marker):
    result, _, summary = run_suite(
        tmp_path,
        f"import pytest\n@pytest.mark.flaky({marker})\ndef test_bad_policy(): pass\n",
        "-p",
        "rerunfailures",
    )
    assert result.returncode != 0
    assert "CI flaky markers require" in result.stderr + result.stdout
    assert summary["complete"] is False


def test_ci_accepts_one_retry_with_a_tracked_issue(tmp_path):
    result, _, summary = run_suite(
        tmp_path,
        "import pytest\n"
        "@pytest.mark.flaky(reruns=1, reason='https://github.com/langflow-ai/langflow/issues/123')\n"
        "def test_tracked(): pass\n",
        "-p",
        "rerunfailures",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert summary["complete"] is True


@pytest.mark.parametrize("duration", [-1, float("inf"), float("nan"), "slow", True])
def test_invalid_timings_are_rejected(tmp_path, duration):
    from scripts.ci.backend_test_metrics import read_durations

    path = tmp_path / "durations.json"
    path.write_text(json.dumps({"test_one": duration}))
    with pytest.raises(ValueError, match="Invalid test durations"):
        read_durations(path)
