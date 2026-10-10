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
import subprocess
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
# It logs down to DEBUG, so nothing it sends to the application log stays hidden.
_WORKER = """
import asyncio, contextlib, os, signal, sys
from langflow.api.utils import migration_runs
from lfx.log.logger import configure, logger

async def main():
    await migration_runs.start_run("copy_files", sys.argv[1:], dict(os.environ), started_by="bob")
    await asyncio.Event().wait()

# A process started in the background of a shell script is born ignoring Ctrl-C. A server is not.
signal.signal(signal.SIGINT, signal.default_int_handler)
configure(log_level="DEBUG")
logger.debug("The worker logs at DEBUG")
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
def unreaped():
    """A process nothing reaps: once killed it keeps its pid, as the child of a dead worker can in a container."""
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])  # noqa: S603
    yield process
    process.kill()
    process.wait()


@pytest.fixture
async def other_worker(config_dir: Path):
    """Start a run from a second server process, and hand back that process and the run's id."""
    workers = []

    async def start(body: str, *args: object, **env: str) -> tuple[asyncio.subprocess.Process, str]:
        # Its output goes where this process's output goes, so a test can read what it logged.
        worker = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            _WORKER,
            *_child(body, *args),
            env={**os.environ, **env, "LANGFLOW_CONFIG_DIR": str(config_dir)},
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
        emit(event="report", ok=False, problems=[{"code": "count_mismatch"}])
        """
    )

    events = await _follow(run_id)

    assert [event["seq"] for event in events] == [1, 2, 3, 4]
    assert [event["event"] for event in events] == ["progress", "item", "report", "end"]
    # Whether the report says ok is the caller's business: it arrives as the command wrote it.
    assert events[2] == {"event": "report", "ok": False, "problems": [{"code": "count_mismatch"}], "seq": 3}
    assert events[3] == {"event": "end", "status": "done", "exit_code": 0, "seq": 4}
    run = migration_runs.read_run(run_id)
    assert (run["step_id"], run["status"], run["started_by"], run["exit_code"]) == ("copy_database", "done", "alice", 0)
    assert run["started_at"] <= run["finished_at"]
    # What the endpoints will build on: two files per run, a log that holds what was followed, these fields.
    runs = config_dir / "migrations" / "runs"
    assert {path.name for path in runs.iterdir()} == {f"{run_id}.ndjson", f"{run_id}.json", "start.lock"}
    assert [json.loads(line) for line in (runs / f"{run_id}.ndjson").read_text().splitlines()] == events
    recorded = {"run_id", "step_id", "status", "started_by", "started_at", "finished_at", "exit_code", "stderr"}
    assert set(run) == recorded | {"child", "worker"}


async def test_the_child_runs_with_the_environment_it_was_given_and_no_other(monkeypatch: pytest.MonkeyPatch):
    # The commands read where to copy to from their environment, and the server's own must not leak in.
    given = {**os.environ, "TARGET_URL": "postgresql://target"}
    monkeypatch.setenv("ONLY_THE_SERVER_HAS_THIS", "1")
    child = _child('emit(target=os.environ["TARGET_URL"], server=os.environ.get("ONLY_THE_SERVER_HAS_THIS"))')

    run_id = await migration_runs.start_run("copy_database", child, given, started_by="alice")

    assert (await _follow(run_id))[0] == {"target": "postgresql://target", "server": None, "seq": 1}


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


async def test_a_line_longer_than_the_raised_limit_is_skipped_and_the_run_goes_on(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(migration_runs, "_LINE_LIMIT", 64 * 1024)
    run_id = await _start(
        """
        emit(event="progress", done=1)
        emit(event="item", reason="r" * 200_000)
        emit(event="report", ok=True)
        """
    )

    events = await _follow(run_id)

    assert [(event["seq"], event["event"]) for event in events] == [(1, "progress"), (2, "report"), (3, "end")]
    assert events[-1] == {"event": "end", "status": "done", "exit_code": 0, "seq": 3}


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
    # Followed again now that the run is over, when a full read is not yet the whole log.
    assert await _follow(run_id) == events


@pytest.mark.parametrize("split", [False, True])
@pytest.mark.parametrize("terminated", [False, True])
async def test_an_oversized_lines_json_suffix_is_skipped(*, split: bool, terminated: bool):
    # Feed the stream directly to control whether the overrun happens before its newline arrives.
    stream = asyncio.StreamReader(limit=64)
    stream.feed_data(b"x" * 65)

    async def collect() -> list[bytes]:
        return [line async for line in migration_runs._read_lines(stream)]

    reader = asyncio.create_task(collect())
    if split:
        # Let the reader consume the oversized prefix and wait for the rest of this same line.
        await asyncio.sleep(0)
    suffix = b'{"event":"report","ok":true}'
    following = b'{"event":"progress","done":1}\n'
    stream.feed_data(suffix + (b"\n" + following if terminated else b""))
    stream.feed_eof()

    assert await asyncio.wait_for(reader, _TIMEOUT) == ([following] if terminated else [])


async def test_a_stdout_line_without_a_final_newline_is_preserved():
    stream = asyncio.StreamReader(limit=64)
    report = b'{"event":"report","ok":true}'
    stream.feed_data(report)
    stream.feed_eof()

    assert [line async for line in migration_runs._read_lines(stream)] == [report]


async def test_a_line_still_being_written_is_read_once_it_is_whole(config_dir: Path, unreaped: subprocess.Popen):
    # One process stands in for a worker and its child, and this test does their writing, so the
    # log can stop halfway through a line.
    identity = migration_runs._identity(unreaped.pid)
    run_id = uuid.uuid4().hex
    runs = config_dir / "migrations" / "runs"
    runs.mkdir(parents=True)
    log = runs / f"{run_id}.ndjson"
    log.write_text('{"event": "progress", "done": 1, "seq": 1}\n{"event": "progress", "do')
    status = {"run_id": run_id, "step_id": "copy_files", "status": "running", "exit_code": None}
    (runs / f"{run_id}.json").write_text(json.dumps({**status, "child": identity, "worker": identity}))
    seen, follower = _follow_in_background(run_id)
    await _until(lambda: seen)

    with log.open("a") as lines:
        lines.write('ne": 2, "seq": 2}\n')
    await _until(lambda: len(seen) == 2)
    # A worker that dies halfway through a line leaves that half behind for good. Nothing reaps
    # the process here, so it keeps its pid too, and that must not make the run look live.
    with log.open("a") as lines:
        lines.write('{"event": "progr')
    unreaped.kill()
    await asyncio.wait_for(follower, _TIMEOUT)

    assert [event.get("done") for event in seen] == [1, 2, None]
    assert seen[-1] == {"event": "end", "status": "interrupted", "exit_code": None, "seq": 3}


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
    # A grace period as long as any wait here: however slow the machine, the child is not killed
    # before this test has seen what it did with SIGTERM.
    monkeypatch.setattr(migration_runs, "_GRACE_S", _TIMEOUT)
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

    cancel = asyncio.create_task(migration_runs.cancel_run(run_id))
    await _until(lambda: len(seen) > 1)
    # It was asked first, it went on, and the grace period is still running.
    assert (seen[1].get("note"), cancel.done()) == ("asked to stop", False)
    # The rest of the grace period goes by a thousand times faster. Then the child is killed.
    monkeypatch.setattr(migration_runs, "_POLL_S", migration_runs._POLL_S / 1000)
    await asyncio.wait_for(asyncio.gather(cancel, follower), _TIMEOUT)

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


async def test_a_run_whose_log_can_no_longer_be_written_ends_failed_and_stops_its_child(config_dir: Path, gate: Path):
    if os.getuid() == 0:
        pytest.skip("Root can write to a file whatever its permissions say")
    run_id = await _start(
        """
        emit(event="progress", done=1)
        wait_for_gate()
        emit(event="progress", done=2)
        time.sleep(120)
        """,
        gate,
    )
    seen, follower = _follow_in_background(run_id)
    await _until(lambda: seen)
    child = migration_runs.read_run(run_id)["child"]

    (config_dir / "migrations" / "runs" / f"{run_id}.ndjson").chmod(0o400)
    gate.touch()
    await asyncio.wait_for(follower, _TIMEOUT)

    # The worker could not write the end to the log either, so the follower read it from the status.
    assert seen[-1] == {"event": "end", "status": "failed", "exit_code": None, "seq": 2}
    await _until(lambda: migration_runs._process(child) is None)


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


@pytest.mark.parametrize("run_id", ["0" * 32, "../migration", "", "f" * 32])
async def test_a_run_that_does_not_exist_is_not_found(run_id: str, config_dir: Path):
    # A file that an id with a path in it would reach.
    (config_dir / "migrations" / "runs").mkdir(parents=True)
    (config_dir / "migrations" / "migration.json").write_text('{"status": "done"}')
    # A status with nothing in it, as a machine that lost power can leave one. It is no run.
    (config_dir / "migrations" / "runs" / f"{'f' * 32}.json").touch()

    with pytest.raises(migration_runs.RunNotFoundError):
        migration_runs.read_run(run_id)
    with pytest.raises(migration_runs.RunNotFoundError):
        await migration_runs.cancel_run(run_id)
    with pytest.raises(migration_runs.RunNotFoundError):
        await _follow(run_id)
    # Nor does it stand in the way of the next start, which lists the runs first.
    assert migration_runs.list_runs() == []


async def _start_and_outlive_the_child(last_words: str, gate: Path) -> str:
    """Start a run whose child hands its stdout to a process of its own and exits.

    The process the status file names is then gone while output is still to come: the
    other process holds for the gate, runs last_words and exits.
    """
    run_id = await _start(
        """
        import subprocess
        subprocess.Popen([sys.executable, "-c", sys.argv[1], sys.argv[-1]])
        emit(event="progress", done=1)
        """,
        _PRELUDE + f"wait_for_gate()\n{last_words}\n",
        gate,
    )
    child = migration_runs.read_run(run_id)["child"]
    await _until(lambda: child is None or not psutil.pid_exists(child["pid"]))
    return run_id


async def test_a_run_is_not_interrupted_while_its_worker_still_reads_it(gate: Path):
    run_id = await _start_and_outlive_the_child('emit(event="report", ok=True)', gate)

    assert migration_runs.read_run(run_id)["status"] == "running"
    gate.touch()
    assert [event["event"] for event in await _follow(run_id)] == ["progress", "report", "end"]
    assert migration_runs.read_run(run_id)["status"] == "done"


async def test_a_cancel_that_arrives_after_the_child_exited_changes_nothing(gate: Path):
    run_id = await _start_and_outlive_the_child("sys.exit(3)", gate)

    await migration_runs.cancel_run(run_id)
    gate.touch()

    # The run ends as it would have without the cancel: failed, since no report came.
    assert (await _follow(run_id))[-1] == {"event": "end", "status": "failed", "exit_code": 0, "seq": 2}
    # And a cancel after the end does nothing at all.
    await migration_runs.cancel_run(run_id)
    assert migration_runs.read_run(run_id)["status"] == "failed"


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
    # A follower that already has that end is not given it again.
    assert await _follow(run_id, after=2) == []
    # Every command is safe to rerun, so the next start goes through.
    again = await _start('emit(event="report", ok=True)')
    assert (await _follow(again))[-1]["status"] == "done"


async def test_a_pid_that_went_to_another_process_does_not_keep_a_run_live(gate: Path, other_worker, config_dir: Path):
    # A process is told apart by when it started, to within a clock tick. This one is given a tenth
    # of a second on the run's worker and child, so it can never share a tick with either of them.
    stranger = await asyncio.create_subprocess_exec(sys.executable, "-c", "import time; time.sleep(120)")
    try:
        # Linux's reported creation time can look old already because its boot time is rounded.
        loop = asyncio.get_running_loop()
        started = loop.time()
        await _until(lambda: loop.time() - started > 0.1)
        worker, run_id = await other_worker("wait_for_gate()", gate)
        worker.kill()
        await worker.wait()
        os.kill(migration_runs.read_run(run_id)["child"]["pid"], signal.SIGKILL)
        await _until(lambda: migration_runs.read_run(run_id)["status"] == "interrupted")

        # After a restart the same pids are handed out again. Here both go to a process the run never had.
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
    await asyncio.wait_for(worker.wait(), _TIMEOUT)
    await asyncio.wait_for(follower, _TIMEOUT)

    run = migration_runs.read_run(run_id)
    # The worker wrote how the run ended on its way out: no reader had to work it out.
    assert (run["status"], run["finished_at"] is not None) == ("interrupted", True)
    assert seen[-1] == {"event": "end", "status": "interrupted", "exit_code": None, "seq": 2}
    await _until(lambda: migration_runs._process(run["child"]) is None)


async def test_the_environment_and_the_arguments_are_never_written(
    config_dir: Path, other_worker, capfd: pytest.CaptureFixture
):
    password, argument = f"password-{uuid.uuid4().hex}", f"argument-{uuid.uuid4().hex}"
    # Started by a worker of its own, whose log is all on, and which passes its own environment on.
    worker, run_id = await other_worker(
        """
        emit(event="progress", done=1)
        print("could not connect", file=sys.stderr)
        sys.exit(1)
        """,
        argument,
        LANGFLOW_MIGRATION_TARGET_URL=f"postgresql://langflow:{password}@db/langflow",
    )
    await _follow(run_id)
    # Stopped, so everything it had to log is written.
    worker.send_signal(signal.SIGINT)
    await asyncio.wait_for(worker.wait(), _TIMEOUT)

    written = b"".join(path.read_bytes() for path in config_dir.rglob("*") if path.is_file())
    logged = "".join(capfd.readouterr())
    # The run's files and the worker's log are the ones being read here.
    assert b"could not connect" in written
    assert b'"progress"' in written
    assert "The worker logs at DEBUG" in logged
    for value in (password, argument):
        assert value.encode() not in written
        assert value not in logged
