"""Tests for running a migration command as a child process that outlives its request.

Every child here is a real process: a short Python script that prints JSON lines,
waits, writes to stderr, exits non-zero or ignores SIGTERM. A run started by "another
worker" is started by a second real Python process, because the files on disk are
all that two workers share.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
import textwrap
import uuid
from typing import TYPE_CHECKING, Any

import psutil
import pytest
from langflow.api.utils import migration_runs
from langflow.services.deps import get_settings_service

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

# Every wait below ends as soon as its condition holds. This only bounds a test that is failing.
_TIMEOUT = 60

# What every child script starts with. A child that waits holds until the test creates the
# file named by its last argument, and gives up after two minutes so it can never be left running.
_PRELUDE = """
import json, os, sys, time

def emit(**event):
    print(json.dumps(event), flush=True)

def wait_for_gate():
    for _ in range(12000):
        if os.path.exists(sys.argv[-1]):
            return
        time.sleep(0.01)
    sys.exit(9)
"""

# A second server process: it starts one run, then keeps reading it as a worker would.
_WORKER = """
import asyncio, contextlib, os, sys
from langflow.api.utils import migration_runs

async def main():
    await migration_runs.start_run("copy_files", sys.argv[1:], dict(os.environ), started_by="bob")
    await asyncio.Event().wait()

with contextlib.suppress(KeyboardInterrupt):
    asyncio.run(main())
"""


def _child(body: str, *args: object) -> list[str]:
    """The argv of a child that runs body, which may call emit() and wait_for_gate()."""
    return [sys.executable, "-c", _PRELUDE + textwrap.dedent(body), *map(str, args)]


async def _start(body: str, *args: object, step: str = "copy_database") -> str:
    return await migration_runs.start_run(step, _child(body, *args), dict(os.environ), started_by="alice")


async def _until(condition: Callable[[], Any]) -> Any:
    """Wait on a condition, never on a guessed amount of time."""
    deadline = asyncio.get_running_loop().time() + _TIMEOUT
    while not (result := condition()):
        if asyncio.get_running_loop().time() > deadline:
            pytest.fail("The condition did not hold in time")
        await asyncio.sleep(0.01)
    return result


async def _follow(run_id: str, after: int = 0) -> list[dict[str, Any]]:
    """Every event a follower gets, up to the end of the run."""

    async def collect() -> list[dict[str, Any]]:
        return [event async for event in migration_runs.follow_run(run_id, after)]

    return await asyncio.wait_for(collect(), _TIMEOUT)


def _follow_in_background(run_id: str, after: int = 0) -> tuple[list[dict[str, Any]], asyncio.Task]:
    """A follower whose events can be looked at while the run is still going."""
    seen: list[dict[str, Any]] = []

    async def follow() -> None:
        async for event in migration_runs.follow_run(run_id, after):
            # One at a time, so the test sees each event when the follower gets it.
            seen.append(event)  # noqa: PERF401

    return seen, asyncio.create_task(follow())


@pytest.fixture(autouse=True)
async def config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Run files are written under CONFIG_DIR, so keep them out of the real one."""
    monkeypatch.setattr(get_settings_service().settings, "config_dir", str(tmp_path))
    yield tmp_path
    # A test that failed halfway must not leave a child running.
    for run in migration_runs.list_runs():
        await migration_runs.cancel_run(run["run_id"])
    await _until(lambda: all(run["status"] != "running" for run in migration_runs.list_runs()))


@pytest.fixture
def gate(tmp_path: Path) -> Path:
    """The file a waiting child holds for. Create it to let the child go on."""
    return tmp_path / "gate"


@pytest.fixture
async def other_worker(config_dir: Path):
    """Start a run from a second server process, and hand back that process and the run's id."""
    workers = []

    async def start(body: str, *args: object) -> tuple[asyncio.subprocess.Process, str]:
        worker = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            _WORKER,
            *_child(body, *args),
            env={**os.environ, "LANGFLOW_CONFIG_DIR": str(config_dir)},
            stdout=asyncio.subprocess.DEVNULL,
        )
        workers.append(worker)
        # This process learns of the run the way any worker does: from the files.
        (run,) = await _until(migration_runs.list_runs)
        return worker, run["run_id"]

    yield start
    for worker in workers:
        if worker.returncode is None:
            worker.kill()
            await worker.wait()


async def test_events_arrive_in_order_and_the_run_ends_done_with_its_report(config_dir: Path):
    run_id = await _start(
        """
        emit(event="progress", phase="copying", done=1, total=2, unit="rows")
        emit(event="item", table="flow", source_rows=2, target_rows=2)
        emit(event="report", ok=False, problems=[{"code": "count_mismatch", "message": "flow"}])
        """
    )

    events = await _follow(run_id)

    assert [(event["seq"], event["event"]) for event in events] == [
        (1, "progress"),
        (2, "item"),
        (3, "report"),
        (4, "end"),
    ]
    # Whether the report says ok is the caller's business: it arrives as the command wrote it.
    assert events[2] == {
        "event": "report",
        "ok": False,
        "problems": [{"code": "count_mismatch", "message": "flow"}],
        "seq": 3,
    }
    assert events[3] == {"event": "end", "status": "done", "exit_code": 0, "seq": 4}
    run = migration_runs.read_run(run_id)
    assert (run["step_id"], run["status"], run["started_by"], run["exit_code"]) == ("copy_database", "done", "alice", 0)
    assert run["started_at"] <= run["finished_at"]
    # What the endpoints will build on: two files per run, and these fields in the status.
    assert {path.name for path in (config_dir / "migrations" / "runs").iterdir()} == {
        f"{run_id}.ndjson",
        f"{run_id}.json",
        "start.lock",
    }
    assert set(run) == {
        "run_id",
        "step_id",
        "status",
        "started_by",
        "started_at",
        "finished_at",
        "exit_code",
        "stderr",
        "child",
        "worker",
    }


async def test_a_follower_that_starts_late_gets_only_the_later_events(gate: Path):
    run_id = await _start(
        """
        emit(event="progress", done=1)
        emit(event="progress", done=2)
        wait_for_gate()
        emit(event="progress", done=3)
        emit(event="report", ok=True)
        """,
        gate,
    )

    seen, follower = _follow_in_background(run_id, after=1)
    await _until(lambda: seen)
    # The run is still going, so the follower holds for what comes next.
    assert not follower.done()
    gate.touch()
    await asyncio.wait_for(follower, _TIMEOUT)

    assert [event["seq"] for event in seen] == [2, 3, 4, 5]
    # A follower that starts after the run has finished gets the tail and the end.
    assert [(event["seq"], event["event"]) for event in await _follow(run_id, after=3)] == [(4, "report"), (5, "end")]
    assert await _follow(run_id, after=5) == []


async def test_two_followers_of_one_run_both_get_every_event(gate: Path):
    run_id = await _start(
        """
        emit(event="progress", done=1)
        wait_for_gate()
        emit(event="progress", done=2)
        emit(event="report", ok=True)
        """,
        gate,
    )

    first, first_follower = _follow_in_background(run_id)
    second, second_follower = _follow_in_background(run_id)
    await _until(lambda: first and second)
    gate.touch()
    await asyncio.wait_for(asyncio.gather(first_follower, second_follower), _TIMEOUT)

    assert [event["seq"] for event in first] == [1, 2, 3, 4]
    assert second == first


async def test_a_child_that_exits_without_a_report_ends_failed_with_its_stderr():
    run_id = await _start(
        """
        emit(event="error", code="bucket_error", message="the bucket refused the request")
        for number in range(50):
            print(f"\\x1b[31mline {number}\\x1b[0m", file=sys.stderr)
        sys.exit(2)
        """
    )

    events = await _follow(run_id)

    assert events == [
        {"event": "error", "code": "bucket_error", "message": "the bucket refused the request", "seq": 1},
        {"event": "end", "status": "failed", "exit_code": 2, "seq": 2},
    ]
    run = migration_runs.read_run(run_id)
    assert (run["status"], run["exit_code"]) == ("failed", 2)
    # The last 40 lines, without the colour codes.
    assert run["stderr"].splitlines() == [f"line {number}" for number in range(10, 50)]


async def test_stderr_that_never_ends_a_line_does_not_stall_the_run():
    # More than the stream limit with no newline, as a progress bar that redraws one line writes.
    run_id = await _start(
        """
        for _ in range(170):
            sys.stderr.write("\\r" + "#" * 100_000)
        emit(event="report", ok=True)
        """
    )

    events = await _follow(run_id)

    assert events[-1] == {"event": "end", "status": "done", "exit_code": 0, "seq": 2}
    assert migration_runs.read_run(run_id)["stderr"] == "#" * 64 * 1024


async def test_stdout_lines_that_are_not_json_objects_are_skipped():
    run_id = await _start(
        """
        print("Copying 3 tables", flush=True)
        emit(event="progress", done=1)
        print("[1, 2]", flush=True)
        print(flush=True)
        emit(note="an object of any shape is an event")
        emit(event="report", ok=True)
        """
    )

    events = await _follow(run_id)

    assert events == [
        {"event": "progress", "done": 1, "seq": 1},
        {"note": "an object of any shape is an event", "seq": 2},
        {"event": "report", "ok": True, "seq": 3},
        {"event": "end", "status": "done", "exit_code": 0, "seq": 4},
    ]


async def test_a_line_far_larger_than_the_default_stream_limit_survives():
    # About 2 MB on one line, where asyncio stops at 64 KiB unless told otherwise.
    run_id = await _start('emit(event="report", ok=False, attention=["x" * 1000] * 2000)')

    events = await _follow(run_id)

    assert events[0]["attention"] == ["x" * 1000] * 2000
    assert events[1] == {"event": "end", "status": "done", "exit_code": 0, "seq": 2}


async def test_a_log_longer_than_one_read_arrives_whole_and_in_order():
    run_id = await _start(
        """
        for number in range(3000):
            emit(event="item", number=number, reason="r" * 500)
        emit(event="report", ok=True)
        """
    )

    events = await _follow(run_id)

    assert [event["seq"] for event in events] == list(range(1, 3003))
    assert [event["number"] for event in events[:3000]] == list(range(3000))


async def test_cancel_ends_the_run_cancelled(gate: Path):
    run_id = await _start(
        """
        emit(event="progress", done=1)
        wait_for_gate()
        """,
        gate,
    )
    seen, follower = _follow_in_background(run_id)
    await _until(lambda: seen)

    await migration_runs.cancel_run(run_id)
    await asyncio.wait_for(follower, _TIMEOUT)

    assert seen[-1] == {"event": "end", "status": "cancelled", "exit_code": -signal.SIGTERM, "seq": 2}
    assert migration_runs.read_run(run_id)["status"] == "cancelled"


async def test_cancel_kills_a_child_that_ignores_sigterm(gate: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(migration_runs, "_GRACE_S", 1.0)
    run_id = await _start(
        """
        import signal
        signal.signal(signal.SIGTERM, lambda *_: emit(event="progress", note="asked to stop"))
        emit(event="progress", note="ready")
        wait_for_gate()
        """,
        gate,
    )
    seen, follower = _follow_in_background(run_id)
    # Its first event says the handler is in place.
    await _until(lambda: seen)

    await migration_runs.cancel_run(run_id)
    await asyncio.wait_for(follower, _TIMEOUT)

    # It was asked first, and killed only because it went on.
    assert [event.get("note") for event in seen] == ["ready", "asked to stop", None]
    assert seen[-1] == {"event": "end", "status": "cancelled", "exit_code": -signal.SIGKILL, "seq": 3}


async def test_a_second_run_is_refused_while_one_is_live_and_allowed_after_it_ends(gate: Path):
    first = await _start(
        """
        wait_for_gate()
        emit(event="report", ok=True)
        """,
        gate,
    )

    # One run at a time, whichever step it belongs to.
    with pytest.raises(migration_runs.RunActiveError):
        await _start('emit(event="report", ok=True)', step="copy_files")

    gate.touch()
    await _follow(first)
    second = await _start('emit(event="report", ok=True)', step="copy_files")
    assert (await _follow(second))[-1]["status"] == "done"


async def test_two_starts_at_the_same_moment_start_one_run(gate: Path):
    results = await asyncio.gather(
        _start("wait_for_gate()", gate, step="copy_database"),
        _start("wait_for_gate()", gate, step="copy_files"),
        return_exceptions=True,
    )

    assert sorted(type(result).__name__ for result in results) == ["RunActiveError", "str"]
    assert len(migration_runs.list_runs()) == 1


async def test_a_command_that_cannot_be_spawned_leaves_no_run_behind():
    with pytest.raises(FileNotFoundError):
        await migration_runs.start_run("copy_database", ["/no/such/command"], {}, started_by="alice")

    assert migration_runs.list_runs() == []
    run_id = await _start('emit(event="report", ok=True)')
    assert (await _follow(run_id))[-1]["status"] == "done"


async def test_a_run_that_cannot_be_recorded_does_not_leave_its_child_running(config_dir: Path, gate: Path):
    if os.getuid() == 0:
        pytest.skip("Root can write to a folder whatever its permissions say")
    runs = config_dir / "migrations" / "runs"
    runs.mkdir(parents=True)
    (runs / "start.lock").touch()
    children = set(psutil.Process().children())
    # The lock file can still be opened, but none of the run's files can be created.
    runs.chmod(0o500)
    try:
        with pytest.raises(PermissionError):
            await _start("wait_for_gate()", gate)
    finally:
        runs.chmod(0o700)

    await _until(lambda: set(psutil.Process().children()) <= children)


async def test_a_new_run_replaces_the_earlier_run_of_its_step(config_dir: Path):
    async def run(step: str) -> str:
        run_id = await _start('emit(event="report", ok=True)', step=step)
        await _follow(run_id)
        return run_id

    first = await run("copy_database")
    other = await run("copy_files")
    second = await run("copy_database")

    assert {run["run_id"] for run in migration_runs.list_runs()} == {other, second}
    assert not list((config_dir / "migrations" / "runs").glob(f"{first}*"))
    with pytest.raises(migration_runs.RunNotFoundError):
        migration_runs.read_run(first)


@pytest.mark.parametrize("run_id", ["0" * 32, "../migration", ""])
async def test_a_run_that_does_not_exist_is_not_found(run_id: str, config_dir: Path):
    # A file that an id with a path in it would reach.
    (config_dir / "migrations" / "runs").mkdir(parents=True)
    (config_dir / "migrations" / "migration.json").write_text('{"status": "done"}')

    with pytest.raises(migration_runs.RunNotFoundError):
        migration_runs.read_run(run_id)
    with pytest.raises(migration_runs.RunNotFoundError):
        await migration_runs.cancel_run(run_id)
    with pytest.raises(migration_runs.RunNotFoundError):
        await _follow(run_id)


async def test_a_run_is_not_interrupted_while_its_worker_still_reads_it(gate: Path):
    # The child hands its stdout to a process of its own and exits, so the process the
    # status file names is gone while output is still to come.
    run_id = await _start(
        """
        import subprocess
        subprocess.Popen([sys.executable, "-c", sys.argv[1], sys.argv[-1]])
        emit(event="progress", done=1)
        """,
        _PRELUDE + 'wait_for_gate()\nemit(event="report", ok=True)\n',
        gate,
    )
    child = migration_runs.read_run(run_id)["child"]
    await _until(lambda: child is None or not psutil.pid_exists(child["pid"]))

    assert migration_runs.read_run(run_id)["status"] == "running"
    gate.touch()
    assert [(event["seq"], event["event"]) for event in await _follow(run_id)] == [
        (1, "progress"),
        (2, "report"),
        (3, "end"),
    ]
    assert migration_runs.read_run(run_id)["status"] == "done"


async def test_another_worker_can_follow_and_cancel_a_run(gate: Path, other_worker):
    _, run_id = await other_worker(
        """
        emit(event="progress", done=1)
        wait_for_gate()
        """,
        gate,
    )
    seen, follower = _follow_in_background(run_id)
    await _until(lambda: seen)

    await migration_runs.cancel_run(run_id)
    await asyncio.wait_for(follower, _TIMEOUT)

    assert seen == [
        {"event": "progress", "done": 1, "seq": 1},
        {"event": "end", "status": "cancelled", "exit_code": -signal.SIGTERM, "seq": 2},
    ]
    # Only the worker that started the run records how it ended.
    run = migration_runs.read_run(run_id)
    assert (run["status"], run["started_by"], run["worker"]["pid"] != os.getpid()) == ("cancelled", "bob", True)


async def test_a_run_whose_worker_dies_reads_as_interrupted_and_its_follower_ends(gate: Path, other_worker):
    worker, run_id = await other_worker(
        """
        emit(event="progress", done=1)
        wait_for_gate()
        """,
        gate,
    )
    seen, follower = _follow_in_background(run_id)
    await _until(lambda: seen)

    # Killed outright: the worker records nothing on its way out.
    worker.kill()
    await worker.wait()
    # Its child is still going, so the run is still live and nothing else may start.
    run = migration_runs.read_run(run_id)
    assert run["status"] == "running"
    with pytest.raises(migration_runs.RunActiveError):
        await _start('emit(event="report", ok=True)')

    os.kill(run["child"]["pid"], signal.SIGKILL)
    await asyncio.wait_for(follower, _TIMEOUT)

    assert seen[-1] == {"event": "end", "status": "interrupted", "exit_code": None, "seq": 2}
    assert migration_runs.read_run(run_id)["status"] == "interrupted"
    # Every command is safe to rerun, so the next start goes through.
    again = await _start('emit(event="report", ok=True)')
    assert (await _follow(again))[-1]["status"] == "done"


async def test_a_pid_that_went_to_another_process_does_not_keep_a_run_live(gate: Path, other_worker, config_dir: Path):
    worker, run_id = await other_worker("wait_for_gate()", gate)
    worker.kill()
    await worker.wait()
    os.kill(migration_runs.read_run(run_id)["child"]["pid"], signal.SIGKILL)
    await _until(lambda: migration_runs.read_run(run_id)["status"] == "interrupted")

    # After a restart the same pids are handed out again. Here both go to a process the run never had.
    stranger = await asyncio.create_subprocess_exec(sys.executable, "-c", "import time; time.sleep(120)")
    try:
        status = config_dir / "migrations" / "runs" / f"{run_id}.json"
        recorded = json.loads(status.read_text())
        recorded["child"]["pid"] = recorded["worker"]["pid"] = stranger.pid
        status.write_text(json.dumps(recorded))

        assert migration_runs.read_run(run_id)["status"] == "interrupted"
        # Cancelling must not reach a process that only shares the pid.
        await migration_runs.cancel_run(run_id)
        assert psutil.Process(stranger.pid).status() != psutil.STATUS_ZOMBIE
    finally:
        stranger.kill()
        await stranger.wait()


async def test_a_worker_that_stops_records_the_run_as_interrupted_and_stops_its_child(gate: Path, other_worker):
    worker, run_id = await other_worker(
        """
        emit(event="progress", done=1)
        wait_for_gate()
        """,
        gate,
    )
    seen, follower = _follow_in_background(run_id)
    await _until(lambda: seen)

    # Ctrl-C makes asyncio cancel whatever is still running, as a server that stops does.
    worker.send_signal(signal.SIGINT)
    await worker.wait()
    await asyncio.wait_for(follower, _TIMEOUT)

    run = migration_runs.read_run(run_id)
    # The worker wrote how the run ended on its way out: no reader had to work it out.
    assert (run["status"], run["finished_at"] is not None) == ("interrupted", True)
    assert seen[-1] == {"event": "end", "status": "interrupted", "exit_code": None, "seq": 2}
    await _until(lambda: migration_runs._process(run["child"]) is None)


async def test_the_environment_and_the_arguments_are_never_written(config_dir: Path, capfd: pytest.CaptureFixture):
    password, argument = f"password-{uuid.uuid4().hex}", f"argument-{uuid.uuid4().hex}"
    child = _child(
        """
        emit(event="progress", done=1)
        print("could not connect", file=sys.stderr)
        sys.exit(1)
        """,
        argument,
    )
    env = {**os.environ, "LANGFLOW_MIGRATION_TARGET_URL": f"postgresql://langflow:{password}@db/langflow"}

    run_id = await migration_runs.start_run("copy_database", child, env, started_by="alice")
    await _follow(run_id)

    written = b"".join(path.read_bytes() for path in config_dir.rglob("*") if path.is_file())
    # The run's files are the ones being read here.
    assert b"could not connect" in written
    assert b'"progress"' in written
    output = capfd.readouterr()
    for value in (password, argument):
        assert value.encode() not in written
        assert value not in output.out + output.err
