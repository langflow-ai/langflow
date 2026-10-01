"""Pytest plugin and reducer for complete, retry-aware backend CI measurements.

Load with ``-p scripts.ci.backend_test_metrics --ci-report-dir PATH``. The
controller journals reports as they arrive, including before a worker crashes.
Only a successful complete collection can produce a reusable timing baseline.
"""

from __future__ import annotations

import argparse
import faulthandler
import json
import math
import os
import platform
import re
import threading
import time
from collections import Counter, defaultdict
from pathlib import Path

import pytest


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_durations(path: Path) -> dict[str, float]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or any(
        not isinstance(key, str)
        or isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
        for key, value in data.items()
    ):
        msg = f"Invalid test durations: {path}"
        raise ValueError(msg)
    return data


def pytest_addoption(parser):
    group = parser.getgroup("backend-ci")
    group.addoption("--ci-report-dir", help="Journal test reports and publish a CI summary")
    group.addoption("--ci-baseline", help="Duration baseline used to calculate missing timing entries")


def pytest_configure(config):
    directory = config.getoption("ci_report_dir")
    if directory:
        config.pluginmanager.register(TimeoutDiagnostics(config, Path(directory)), "backend-ci-timeouts")
        if not hasattr(config, "workerinput"):
            config.pluginmanager.register(Metrics(config, Path(directory)), "backend-ci-metrics")


class TimeoutDiagnostics:
    """Persist stacks before pytest-timeout can terminate an xdist worker.

    The ordinary timeout output can disappear with worker-local capture buffers.
    This diagnostic timer does not change the timeout or terminate the process.
    """

    def __init__(self, config, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        worker = getattr(config, "workerinput", {}).get("workerid", "master")
        self.output = (directory / f"stacks-{worker}.txt").open("w", encoding="utf-8", buffering=1)
        self.timer: threading.Timer | None = None

    def dump(self, nodeid):
        self.output.write(f"Approaching test timeout: {nodeid}\n")
        faulthandler.dump_traceback(file=self.output, all_threads=True)

    @pytest.hookimpl(wrapper=True, optionalhook=True)
    def pytest_timeout_set_timer(self, item, settings):
        result = yield
        if settings.timeout > 0:
            self.timer = threading.Timer(settings.timeout * 0.8, self.dump, args=(item.nodeid,))
            self.timer.daemon = True
            self.timer.start()
        return result

    def cancel(self):
        if self.timer is not None:
            self.timer.cancel()
            self.timer.join()
            self.timer = None

    @pytest.hookimpl(wrapper=True, optionalhook=True)
    def pytest_timeout_cancel_timer(self, item):  # noqa: ARG002
        self.cancel()
        return (yield)

    def pytest_unconfigure(self, config):  # noqa: ARG002
        self.cancel()
        self.output.close()


def pytest_collection_modifyitems(config, items):
    if not config.getoption("ci_report_dir"):
        return
    for item in items:
        marker = item.get_closest_marker("flaky")
        reason = marker.kwargs.get("reason", "") if marker else ""
        if marker and (
            type(marker.kwargs.get("reruns")) is not int
            or marker.kwargs["reruns"] != 1
            or not isinstance(reason, str)
            or not re.fullmatch(r"https://github\.com/[^/?#\s]+/[^/?#\s]+/issues/[1-9][0-9]*(?:#[^\s]*)?", reason)
        ):
            msg = "CI flaky markers require reruns=1 and a GitHub issue URL in reason"
            raise pytest.UsageError(msg)


class Metrics:
    def __init__(self, config, directory: Path):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self.events = (directory / "events.jsonl").open("w", encoding="utf-8", buffering=1)
        self.started = time.monotonic()
        self.selected: list[str] = []
        self.reports: list[dict] = []
        self.crashes = 0
        baseline = config.getoption("ci_baseline")
        self.baseline = read_durations(Path(baseline)) if baseline else {}
        # A reused output directory must never publish a prior successful run.
        for name in ("summary.json", "durations.json"):
            (directory / name).unlink(missing_ok=True)

    def collect(self, ids):
        self.selected = list(ids)
        write_json(self.directory / "collection.json", self.selected)

    def pytest_collection_finish(self, session):
        if session.items:
            self.collect(item.nodeid for item in session.items)

    @pytest.hookimpl(optionalhook=True)
    def pytest_xdist_node_collection_finished(self, node, ids):  # noqa: ARG002
        self.collect(ids)

    @pytest.hookimpl(optionalhook=True)
    def pytest_testnodedown(self, node, error):  # noqa: ARG002
        if error:
            self.crashes += 1
            self.events.write(json.dumps({"event": "worker_crash", "error": str(error)}) + "\n")

    def pytest_runtest_logreport(self, report):
        entry = {
            "nodeid": report.nodeid,
            "when": report.when,
            "outcome": report.outcome,
            "duration": report.duration,
            "worker": getattr(report, "worker_id", "master"),
        }
        if report.failed or report.outcome == "rerun":
            entry["failure"] = str(report.longrepr)
        self.reports.append(entry)
        self.events.write(json.dumps(entry) + "\n")

    def pytest_sessionfinish(self, session, exitstatus):  # noqa: ARG002
        self.events.close()
        completed = {r["nodeid"] for r in self.reports if r["when"] == "teardown"}
        retried = {r["nodeid"] for r in self.reports if r["outcome"] == "rerun"}
        complete = bool(self.selected) and set(self.selected) <= completed and exitstatus == 0 and not self.crashes
        phases = {
            phase: sum(r["duration"] for r in self.reports if r["when"] == phase)
            for phase in ("setup", "call", "teardown")
        }
        outcomes = {}
        for report in self.reports:
            if report["when"] == "call" or (report["when"] == "setup" and report["outcome"] != "passed"):
                outcomes[report["nodeid"]] = report["outcome"]
        summary = {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "commit": os.getenv("CI_TEST_COMMIT", os.getenv("GITHUB_SHA")),
            "run_id": os.getenv("GITHUB_RUN_ID"),
            "complete": complete,
            "exitstatus": int(exitstatus),
            "selected": len(self.selected),
            "completed": len(completed),
            "missing_timings": len(set(self.selected) - self.baseline.keys()),
            "reruns": sum(r["outcome"] == "rerun" for r in self.reports),
            "worker_crashes": self.crashes,
            "wall_seconds": time.monotonic() - self.started,
            "phase_seconds": phases,
            "outcomes": dict(Counter(outcomes.values())),
            "slowest": sorted(self.reports, key=lambda r: r["duration"], reverse=True)[:20],
        }
        write_json(self.directory / "summary.json", summary)
        if complete:
            durations: dict[str, float] = defaultdict(float)
            for report in self.reports:
                if report["nodeid"] not in retried:
                    durations[report["nodeid"]] += report["duration"]
            write_json(self.directory / "durations.json", durations)


def merge_reports(directories: list[Path], expected_shards: int) -> dict[str, float]:
    if len(directories) != expected_shards:
        msg = f"Expected {expected_shards} shards, found {len(directories)}"
        raise ValueError(msg)
    selected: set[str] = set()
    merged: dict[str, float] = {}
    for directory in directories:
        summary = json.loads((directory / "summary.json").read_text())
        if not summary["complete"]:
            msg = f"Incomplete shard: {directory}"
            raise ValueError(msg)
        ids = set(json.loads((directory / "collection.json").read_text()))
        if selected & ids:
            msg = f"Shard selections overlap: {directory}"
            raise ValueError(msg)
        selected.update(ids)
        durations = read_durations(directory / "durations.json")
        if durations.keys() - ids:
            msg = f"Uncollected test durations: {directory}"
            raise ValueError(msg)
        merged.update(durations)
    if not merged:
        msg = "No stable test timings to publish"
        raise ValueError(msg)
    return merged


def report_markdown(directories: list[Path]) -> str:
    lines = [
        "## Backend test performance",
        "",
        "| Shard | Wall (s) | Tests | Missing timings | Retries | Crashes | Complete |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    walls = []
    phases = Counter()
    for directory in directories:
        label = directory.parent.name if directory.name == "test-results" else directory.name
        path = directory / "summary.json"
        if not path.exists():
            lines.append(f"| {label} | interrupted | | | | | no |")
            continue
        summary = json.loads(path.read_text())
        walls.append(summary["wall_seconds"])
        phases.update(summary["phase_seconds"])
        lines.append(
            f"| {label} | {summary['wall_seconds']:.1f} | {summary['selected']} | "
            f"{summary['missing_timings']} | {summary['reruns']} | {summary['worker_crashes']} | "
            f"{summary['complete']} |"
        )
    if walls:
        lines += [
            "",
            f"Slowest / mean shard: {max(walls) / (sum(walls) / len(walls)):.2f}x.",
            "",
            "Summed worker time (not wall time): " + ", ".join(f"{k} {v:.1f}s" for k, v in phases.items()) + ".",
        ]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--expected-shards", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    directories = sorted({p.parent for p in args.directory.rglob("collection.json")})
    summary = report_markdown(directories)
    print(summary)
    if path := os.getenv("GITHUB_STEP_SUMMARY"):
        with Path(path).open("a") as file:
            file.write(summary)
    try:
        merged = merge_reports(directories, args.expected_shards)
    except (ValueError, KeyError, FileNotFoundError) as error:
        parser.exit(1, f"Not publishing incomplete timings: {error}\n")
    write_json(args.output, merged)


if __name__ == "__main__":
    main()
