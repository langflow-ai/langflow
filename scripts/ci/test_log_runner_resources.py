"""Resource evidence must survive a killed sampler without exposing process arguments."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).with_name("log_runner_resources.py")


@pytest.mark.parametrize("force_kill", [False, True])
def test_samples_are_readable_before_process_exit(tmp_path, force_kill):
    output = tmp_path / "resources.jsonl"
    process = subprocess.Popen(  # noqa: S603 - fixed interpreter and repository script
        [
            sys.executable,
            str(SCRIPT),
            "--output",
            str(output),
            "--parent-pid",
            str(os.getpid()),
            "--interval",
            "0.05",
        ],
    )
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            lines = output.read_text().splitlines() if output.exists() else []
            if len(lines) >= 3:
                break
            assert process.poll() is None
            time.sleep(0.02)
        else:
            pytest.fail("Sampler did not flush two samples while running")
        assert process.poll() is None
        process.kill() if force_kill else process.terminate()
        process.wait(timeout=5)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)

    records = [json.loads(line) for line in output.read_text().splitlines()]
    assert records[0]["event"] == "runner"
    samples = records[1:]
    assert len(samples) >= 2
    assert samples[-1]["monotonic_seconds"] > samples[0]["monotonic_seconds"]
    assert all(s["memory"]["total"] > 0 and s["process_rss_bytes"] > 0 for s in samples)
    assert any(p["pid"] == process.pid for s in samples for p in s["processes"])
    assert all("cmdline" not in p and "environ" not in p for s in samples for p in s["processes"])
    if not force_kill:
        assert process.returncode == 0


@pytest.mark.parametrize("interval", ["0", "-1", "nan", "inf"])
def test_rejects_intervals_that_would_spin_or_never_sample(tmp_path, interval):
    result = subprocess.run(  # noqa: S603 - fixed interpreter and repository script
        [
            sys.executable,
            str(SCRIPT),
            "--output",
            str(tmp_path / "resources.jsonl"),
            "--parent-pid",
            str(os.getpid()),
            f"--interval={interval}",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 2
    assert "finite positive number" in result.stderr
