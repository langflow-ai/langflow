"""Run a migration command as a child process that outlives the request that started it.

A copy can take hours, so a run belongs to no request. The worker that starts one
reads the child's stdout in a background task and keeps two files per run under
CONFIG_DIR/migrations/runs:

    <run_id>.ndjson  every JSON object the child printed, one per line, each given a seq,
                     then one last "end" event that says how the run ended
    <run_id>.json    the status: the step, who started it and when, how it ended

Following, cancelling and listing read those files and nothing in memory, so any
worker can serve a run that another worker started. Only the worker that started a
run writes them. A cancel leaves a <run_id>.cancel file beside them, which tells that
worker why the child exited.

A run is live while its status says running and its child, or the worker reading the
child, still exists. A run that says running with both gone was interrupted: the
server restarted, or that worker died. Nothing is recovered, because every command
run here is safe to run again.

One run is live at a time, whatever its step. Starting a step again deletes the files
of its earlier run, so the folder holds the latest run of each step and no more.

This module does not know which commands exist. It is given an argv and an
environment, which hold passwords and keys, and it never writes or logs either.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import psutil
from filelock import FileLock, Timeout

from langflow.services.deps import get_settings_service
from langflow.services.knowledge_base_storage.maintenance import identity_matches, process_identity

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

# A report line holds every failed item, which can pass asyncio's 64 KiB default.
# ponytail: a line longer than this is skipped, and a run whose report is skipped ends as failed.
# Raise it if a report outgrows it.
_LINE_LIMIT = 16 * 1024 * 1024
# How much of the child's stderr the status file keeps.
_STDERR_LINES = 40
_STDERR_BYTES = 64 * 1024
_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
# How often a follower looks for new events.
_POLL_S = 0.1
# How much of the log a follower reads at a time.
_READ_BYTES = 1024 * 1024
# How long a cancelled child has to stop after SIGTERM, before SIGKILL.
_GRACE_S = 5.0

# The loop keeps only a weak reference to a task, so the ones reading a child are held here.
_readers: set[asyncio.Task] = set()


class RunActiveError(Exception):
    """A run is live, for this step or another. Only one runs at a time."""


class RunNotFoundError(Exception):
    """No run has this id. A step's earlier run is deleted when the step is run again."""


async def start_run(step_id: str, argv: list[str], env: dict[str, str], *, started_by: str) -> str:
    """Spawn the command and return the id of its run at once. Its events are read in the background.

    Raises RunActiveError while another run is live, and whatever the spawn raises.
    """
    runs = _runs_dir()
    runs.mkdir(parents=True, exist_ok=True)
    try:
        # Held from the check until the run is on disk, so two workers cannot both find nothing live.
        with FileLock(runs / "start.lock", timeout=0):
            earlier = list_runs()
            if any(run["status"] == "running" for run in earlier):
                raise RunActiveError
            process = await asyncio.create_subprocess_exec(
                *argv,
                env=env,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=_LINE_LIMIT,
            )
            try:
                status = {
                    "run_id": uuid4().hex,
                    "step_id": step_id,
                    "status": "running",
                    "started_by": started_by,
                    "started_at": _now(),
                    "finished_at": None,
                    "exit_code": None,
                    "stderr": "",
                    "child": _identity(process.pid),
                    "worker": _identity(os.getpid()),
                }
                for run in earlier:
                    if run["step_id"] == step_id:
                        _delete(run["run_id"])
                _path(status["run_id"], ".ndjson").touch()
                _write_status(status)
            except BaseException:
                # With no record of it, nothing could follow the child or stop it.
                process.kill()
                raise
    except Timeout:
        # Another worker is starting a run at this moment.
        raise RunActiveError from None
    reader = asyncio.create_task(_read_child(status, process), name=status["run_id"])
    _readers.add(reader)
    reader.add_done_callback(_readers.discard)
    return status["run_id"]


def read_run(run_id: str) -> dict[str, Any]:
    """The status of a run: running, done, failed, cancelled or interrupted. Raises RunNotFoundError."""
    try:
        run = json.loads(_path(run_id, ".json").read_text())
    except (FileNotFoundError, ValueError):
        # A status is replaced whole, so one that is not JSON is what a machine that lost power left.
        raise RunNotFoundError(run_id) from None
    if run["status"] == "running" and not (_read_here(run_id) or _process(run["worker"]) or _process(run["child"])):
        # Nothing is left to write how it ended.
        run["status"] = "interrupted"
    return run


def list_runs() -> list[dict[str, Any]]:
    """The status of every run on disk, which is the latest run of each step."""
    runs = []
    for path in _runs_dir().glob("*.json"):
        # A worker that starts a step again deletes its earlier run, maybe right now.
        with contextlib.suppress(RunNotFoundError):
            runs.append(read_run(path.stem))
    return runs


async def follow_run(run_id: str, after: int = 0) -> AsyncIterator[dict[str, Any]]:
    """Yield the events of a run with a seq above after, as they are appended, and stop after its end.

    Raises RunNotFoundError.
    """
    # ponytail: finding its place means reading the log from the start. Keep the offsets if logs outgrow that.
    position = seq = 0
    while True:
        # The status is read before the log: once a run is over, everything it wrote is already there.
        run = read_run(run_id)
        events, position = _read_events(_path(run_id, ".ndjson"), position)
        for event in events:
            seq = event["seq"]
            if seq > after:
                yield event
            if event.get("event") == "end":
                return
        if not events and run["status"] != "running":
            # Nothing wrote the end, so the status says how the run ended.
            if seq >= after:
                yield {"event": "end", "status": run["status"], "exit_code": run["exit_code"], "seq": seq + 1}
            return
        # More may be waiting to be read. If not, wait for the child to print.
        await asyncio.sleep(0 if events else _POLL_S)


async def cancel_run(run_id: str) -> None:
    """Stop a run from any worker: SIGTERM to its child, then SIGKILL if it is still there after the grace period.

    The run ends as cancelled, unless the child had already printed its report. A run
    that is over, or whose child has already exited, is left alone. Raises RunNotFoundError.
    """
    run = read_run(run_id)
    child = _process(run["child"])
    if run["status"] != "running" or child is None:
        return
    # Tells the worker reading the child why it exited.
    _path(run_id, ".cancel").touch()
    with contextlib.suppress(psutil.NoSuchProcess):
        child.terminate()
        for _ in range(round(_GRACE_S / _POLL_S)):
            if _process(run["child"]) is None:
                return
            await asyncio.sleep(_POLL_S)
        child.kill()


async def _read_child(status: dict[str, Any], process: asyncio.subprocess.Process) -> None:
    """Append the child's events to the log until it exits, then record how the run ended."""
    log = _path(status["run_id"], ".ndjson")
    stderr = bytearray()
    drain = asyncio.create_task(_keep_tail(process.stderr, stderr))
    seq = 0
    reported = False
    outcome = "failed"
    try:
        async for line in _read_lines(process.stdout):
            try:
                event = json.loads(line)
            except ValueError:
                # Not JSON.
                continue
            if not isinstance(event, dict):
                continue
            seq += 1
            reported = reported or event.get("event") == "report"
            _append(log, {**event, "seq": seq})
        await process.wait()
        await drain
        if reported:
            outcome = "done"
        elif _path(status["run_id"], ".cancel").exists():
            outcome = "cancelled"
    except asyncio.CancelledError:
        # The server is stopping, and the child stops with it.
        outcome = "interrupted"
        raise
    finally:
        drain.cancel()
        if process.returncode is None:
            process.kill()
        lines = _ANSI.sub("", stderr.decode(errors="replace")).splitlines()[-_STDERR_LINES:]
        # The status first: a follower that finds no end in the log reads how the run ended from it.
        # ponytail: if this write fails, as on a full disk, the run reads as running until this worker
        # stops. A lock the reader holds for as long as it reads would tell the other workers at once.
        _write_status(
            {
                **status,
                "status": outcome,
                "finished_at": _now(),
                "exit_code": process.returncode,
                "stderr": "\n".join(lines),
            }
        )
        _append(log, {"event": "end", "status": outcome, "exit_code": process.returncode, "seq": seq + 1})


async def _read_lines(stream: asyncio.StreamReader) -> AsyncIterator[bytes]:
    """Yield bounded stdout lines, discarding an oversized line through its newline or EOF."""
    discarding = False
    while True:
        try:
            line = await stream.readuntil(b"\n")
        except asyncio.LimitOverrunError as exc:
            # readline() drops only the buffered prefix when the newline has not arrived yet.
            # Keep discarding so a JSON-looking suffix cannot become a separate event.
            await stream.readexactly(exc.consumed)
            discarding = True
            continue
        except asyncio.IncompleteReadError as exc:
            if not discarding and exc.partial:
                yield exc.partial
            return
        if not discarding:
            yield line
        discarding = False


async def _keep_tail(stream: asyncio.StreamReader, tail: bytearray) -> None:
    # In chunks and not lines: a progress bar can write for hours without ending a line.
    while chunk := await stream.read(_STDERR_BYTES):
        tail += chunk
        del tail[:-_STDERR_BYTES]


def _identity(pid: int) -> dict[str, Any] | None:
    """What tells this process from a later one given the same pid. None when it has already exited."""
    try:
        return process_identity(psutil.Process(pid))
    except (psutil.NoSuchProcess, ProcessLookupError):
        # Linux answers with the second when the process is reaped while its entry in /proc is read.
        return None


def _read_here(run_id: str) -> bool:
    """Whether this worker is the one reading the run's child, which it knows without asking the system.

    A process is told apart by when it started. On macOS that time moves when the system clock is set:
    psutil shifts it once the boot time differs by a second or more from the one it read at import, and
    a status written before then matches no process.
    """
    return any(reader.get_name() == run_id for reader in _readers)


def _process(identity: dict[str, Any] | None) -> psutil.Process | None:
    """The process a status file names. None when it is gone, or when its pid now belongs to another."""
    # ponytail: a pid means something on one host. Replicas that share CONFIG_DIR would need a lease instead.
    if identity:
        with contextlib.suppress(psutil.Error, ProcessLookupError):
            process = psutil.Process(identity["pid"])
            # A child that exited and was never reaped keeps its pid, but can no longer write.
            if process.status() != psutil.STATUS_ZOMBIE and identity_matches(process, identity):
                return process
    return None


def _read_events(log: Path, position: int) -> tuple[list[dict[str, Any]], int]:
    """The complete lines from position on, about a megabyte of them, and where the next read starts."""
    with log.open("rb") as lines:
        lines.seek(position)
        chunk = lines.readlines(_READ_BYTES)
    if chunk and not chunk[-1].endswith(b"\n"):
        # The line is still being written.
        chunk.pop()
    return [json.loads(line) for line in chunk], position + sum(map(len, chunk))


def _append(log: Path, event: dict[str, Any]) -> None:
    with log.open("a") as lines:
        lines.write(json.dumps(event) + "\n")


def _write_status(status: dict[str, Any]) -> None:
    path = _path(status["run_id"], ".json")
    # Replaced in one step, so a reader in another worker never sees half a file.
    partial = path.with_suffix(".partial")
    partial.write_text(json.dumps(status, indent=2))
    partial.replace(path)


def _delete(run_id: str) -> None:
    for path in _runs_dir().glob(f"{run_id}.*"):
        path.unlink(missing_ok=True)


def _runs_dir() -> Path:
    return Path(get_settings_service().settings.config_dir) / "migrations" / "runs"


def _path(run_id: str, suffix: str) -> Path:
    # The id arrives in a URL and names a file, so it has to be one start_run made.
    if not re.fullmatch(r"[0-9a-f]{32}", run_id):
        raise RunNotFoundError(run_id)
    return _runs_dir() / f"{run_id}{suffix}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
