"""Usage imports validate uncertainty without loading the component execution engine."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest
from langflow.upgrade_check.usage import JobUsage, UsageCoverage
from pydantic import ValidationError


@pytest.mark.parametrize(
    "stamp",
    [
        "2026-10-01",
        "2026-10-01T12:00:00",
        "yesterday",
        "2026-10-01T12:00:00+00:99",
        "2026-10-01T12:00:00+24:00",
        "2026-10-01T12:00:00-00:99",
    ],
)
def test_usage_timestamps_require_known_timezone(stamp):
    with pytest.raises(ValidationError):
        UsageCoverage(observed_at=stamp)


@pytest.mark.parametrize(
    "changes",
    [
        {"runs": -1},
        {"runs": 1, "errors": 2},
        {"runs": None},
        {"last_run_at": "2026-10-01T12:00:00Z", "runs": 0},
        {"history": "no_retained_records", "runs": 1},
        {"history": "unavailable"},
        {"history": "never_ran"},
    ],
)
def test_usage_rejects_counts_that_contradict_evidence(changes):
    fields = {
        "history": "retained_records",
        "runs": 1,
        "errors": 0,
        "coverage": {"observed_at": "2026-10-01T12:00:00Z"},
        **changes,
    }
    with pytest.raises(ValidationError):
        JobUsage.model_validate(fields)


def test_usage_period_compares_offsets_and_fractional_seconds():
    coverage = UsageCoverage(
        observed_at="2026-10-02T12:00:00Z",
        oldest_retained_at="2026-10-01T12:00:00+02:00",
        newest_retained_at="2026-10-01T10:00:00.100000Z",
    )
    assert coverage.complete is False
    with pytest.raises(ValidationError, match="ordered"):
        coverage.model_validate({**coverage.model_dump(), "oldest_retained_at": "2026-10-03T12:00:00Z"})


def test_usage_schema_import_does_not_load_engine_or_settings():
    result = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-c",
            "import json, sys, langflow; before = set(sys.modules); "
            "from langflow.upgrade_check.usage import FlowUsage; "
            "assert 'langflow.upgrade_check.reader' not in sys.modules; "
            "print(json.dumps([key for key in set(sys.modules) - before if key.startswith("
            "('langflow.upgrade_check.engine', 'langflow.services.settings', 'lfx.services.settings'))]))",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout) == []


@pytest.mark.parametrize("fraction", ["1", "123", "123456", "123456789"])
def test_usage_accepts_iso_fractional_seconds_without_rewriting_wire(fraction):
    stamp = f"2026-10-01T12:00:00.{fraction}Z"
    coverage = UsageCoverage(observed_at=stamp)
    assert coverage.observed_at == stamp
