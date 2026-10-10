"""Resume a managed single-host upgrade without re-embedding local stores.

Run outside the selected foreground supervisor's dedicated POSIX session. The
operator must disable external restarters first. This controller never selects
processes by name, runs shell commands, or automatically rolls storage back.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import shutil
import socket
import sqlite3
import stat
import sys
import tempfile
import time
from contextlib import closing, suppress
from pathlib import Path
from uuid import uuid4

import httpx
import psutil
from filelock import FileLock, Timeout

from langflow.services.knowledge_base_storage import helper, maintenance

# Internal modules deliberately share the verified helper and durable filesystem primitives.
# ruff: noqa: SLF001

_PROCESS_TIME_TOLERANCE = 0.01
_HTTP_OK = 200
_MAX_PORT = 65535
_MAX_STOP_TIMEOUT = 300
_MAX_READINESS_TIMEOUT = 86400
_MAX_JOURNAL_BYTES = 1024 * 1024
_MAX_WORKERS = 1024
_HELPER_ENV = (
    "LANGFLOW_KB_MIGRATION_HELPER_IMAGE",
    "LANGFLOW_KB_MIGRATION_HELPER_BUNDLE",
    "LANGFLOW_KB_MIGRATION_HELPER_MANIFEST",
    "LANGFLOW_KB_MIGRATION_HELPER_TRUSTED_ROOT",
)


class UpgradeControllerError(RuntimeError):
    """The managed upgrade needs operator attention, with data retained."""


def _error(message: str) -> UpgradeControllerError:
    """Construct an upgrade error with actionable operator guidance."""
    return UpgradeControllerError(message)


def _identity(process: psutil.Process) -> dict:
    """Capture a process's PID and creation time to detect PID reuse."""
    return maintenance.process_identity(process)


def _process(identity: dict) -> psutil.Process | None:
    """Resolve a live process only when its creation time matches the saved identity."""
    if (
        type(identity) is not dict
        or type(identity.get("pid")) is not int
        or identity["pid"] <= 1
        or type(identity.get("created")) not in (int, float)
        or not math.isfinite(identity["created"])
    ):
        msg = "Invalid exact process identity"
        raise _error(msg)
    try:
        process = psutil.Process(identity["pid"])
        if not maintenance.identity_matches(process, identity):
            return None
        if process.status() in (psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD):
            return None
    except psutil.NoSuchProcess:
        return None
    else:
        return process


def _private_directory(path: Path) -> Path:
    """Create or validate a private directory for controller state."""
    if not path.is_absolute() or path.is_symlink():
        msg = "The controller state directory must be an absolute private directory"
        raise _error(msg)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.stat()
    if info.st_uid != os.getuid() or info.st_mode & 0o077 or not stat.S_ISDIR(info.st_mode):
        msg = "The controller state directory must be private and owned by this account"
        raise _error(msg)
    return path.resolve(strict=True)


def _read(path: Path) -> dict:
    """Load the controller's journal from a bounded, validated file."""
    if path.is_symlink():
        msg = "Invalid controller state file"
        raise _error(msg)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            msg = "Controller state must be a private regular file owned by this account"
            raise _error(msg)
        encoded = stream.read(_MAX_JOURNAL_BYTES + 1)
    if len(encoded) > _MAX_JOURNAL_BYTES:
        msg = "Controller state exceeds its size bound"
        raise _error(msg)
    result = json.loads(encoded)
    if not isinstance(result, dict):
        msg = "Invalid controller state"
        raise _error(msg)
    return result


def _write(path: Path, payload: dict, *, exclusive: bool = False) -> None:
    """Persist controller state atomically with an optional exclusive creation guard."""
    encoded = json.dumps(payload, separators=(",", ":")).encode()
    if len(encoded) > _MAX_JOURNAL_BYTES:
        msg = "Controller state exceeds its size bound"
        raise _error(msg)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    if exclusive:
        try:
            os.link(temporary, path)
        finally:
            temporary.unlink()
    else:
        temporary.replace(path)
    maintenance._fsync_directory(path.parent)


def _family(session_id: int) -> list[psutil.Process]:
    """Find processes belonging to the controller-managed process session."""
    family = []
    for process in psutil.process_iter():
        try:
            if os.getsid(process.pid) != session_id:
                continue
            if process.uids().real != os.getuid():
                msg = "Selected supervisor has workers owned by a different account"
                raise _error(msg)
            if process.status() not in (psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD):
                family.append(process)
        except (psutil.NoSuchProcess, ProcessLookupError):
            continue
    if len(family) > _MAX_WORKERS:
        msg = "Supervisor worker count exceeds the controller bound"
        raise _error(msg)
    return family


def _validate_supervisor(identity: dict) -> psutil.Process:
    """Reject an unsafe supervisor identity before stopping any processes."""
    process = _process(identity)
    if process is None:
        msg = "The selected supervisor identity is stale. No processes were stopped"
        raise _error(msg)
    protected = {os.getpid(), *(item.pid for item in psutil.Process().parents())}
    if process.pid in protected or os.getsid(process.pid) != process.pid or os.getpgid(process.pid) != process.pid:
        msg = "Select an independent foreground supervisor that leads its own dedicated session"
        raise _error(msg)
    if process.uids().real != os.getuid():
        msg = "The supervisor must run as the controller account"
        raise _error(msg)
    return process


def _stopped(process: psutil.Process) -> bool:
    """Treat workers that exit during freezing as already drained."""
    try:
        return process.status() in (psutil.STATUS_STOPPED, psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD)
    except psutil.NoSuchProcess:
        return True


def _resume_before_stop(journal_path: Path, journal: dict) -> None:
    """Unfreeze only the saved family if helper staging fails during interrupted preparation."""
    if journal["phase"] not in ("prepared", "stopping"):
        return
    supervisor = _process(journal.get("supervisor_identity", journal["config"]["supervisor"]))
    identities = journal.get("workers", [])
    if not identities and supervisor is not None:
        identities = []
        for process in _family(supervisor.pid):
            with suppress(psutil.NoSuchProcess):
                identities.append(_identity(process))
    for identity in identities:
        if (process := _process(identity)) is not None:
            with suppress(psutil.NoSuchProcess):
                process.resume()
    if supervisor is not None:
        journal["phase"] = "prepared"
        journal.pop("workers", None)
        _write(journal_path, journal)


def _stop(journal_path: Path, journal: dict, timeout: float) -> None:
    """Freeze, durably inventory, then stop only creation-time-bound identities."""
    config = journal["config"]
    identity = journal.get("supervisor_identity", config["supervisor"])
    frozen: list[psutil.Process] = []
    committed = journal["phase"] == "stopping"
    try:
        if not committed:
            supervisor = _validate_supervisor(identity)
            try:
                supervisor.suspend()
            except psutil.NoSuchProcess as exc:
                msg = "The selected supervisor exited during preparation. Inspect its deployment before retrying"
                raise _error(msg) from exc
            frozen.append(supervisor)
            known = {supervisor.pid}
            deadline = time.monotonic() + min(timeout, 10)
            while True:
                family = _family(supervisor.pid)
                for process in family:
                    # A worker escaping the dedicated session defeats its barrier.
                    try:
                        for child in process.children(recursive=True):
                            try:
                                child_session = os.getsid(child.pid)
                            except ProcessLookupError:
                                continue
                            if child_session != supervisor.pid:
                                msg = "A worker escaped the dedicated session. Use the deployment-specific controller"
                                raise _error(msg)
                        if process.pid not in known:
                            process.suspend()
                            frozen.append(process)
                            known.add(process.pid)
                    except psutil.NoSuchProcess:
                        continue
                if all(_stopped(item) for item in _family(supervisor.pid)):
                    break
                if time.monotonic() >= deadline:
                    msg = "Could not freeze the complete selected supervisor family"
                    raise _error(msg)
                time.sleep(0.02)
            journal["workers"] = []
            for item in frozen:
                with suppress(psutil.NoSuchProcess):
                    journal["workers"].append(_identity(item))
            journal["phase"] = "stopping"
            _write(journal_path, journal)
            committed = True
        workers = journal["workers"]
        registered = {item["pid"]: item for item in workers}
        for process in _family(identity["pid"]):
            if process.pid not in registered or _process(registered[process.pid]) is None:
                msg = "An unregistered worker appeared. Keep the external restarter disabled and inspect the instance"
                raise _error(msg)
        # psutil verifies PID reuse again before sending each signal.
        for item in workers:
            if (process := _process(item)) is not None:
                with suppress(psutil.NoSuchProcess):
                    process.terminate()
                    process.resume()
        deadline = time.monotonic() + timeout
        while any(_process(item) is not None for item in workers) and time.monotonic() < deadline:
            time.sleep(0.05)
        for item in workers:
            if (process := _process(item)) is not None:
                with suppress(psutil.NoSuchProcess):
                    process.kill()
        deadline = time.monotonic() + min(timeout, 5)
        while any(_process(item) is not None for item in workers) and time.monotonic() < deadline:
            time.sleep(0.05)
        if any(_process(item) is not None for item in workers) or _family(identity["pid"]):
            msg = "The previous worker barrier could not be established"
            raise _error(msg)
        journal["phase"] = "stopped"
        _write(journal_path, journal)
    finally:
        if not committed:
            for process in frozen:
                with suppress(psutil.NoSuchProcess):
                    process.resume()


async def stage_helper() -> None:
    """Verify the actual pinned release and local image before any downtime."""
    image = os.environ.get("LANGFLOW_KB_MIGRATION_HELPER_IMAGE", "")
    docker, cosign = shutil.which("docker"), shutil.which("cosign")
    if not helper._IMAGE.fullmatch(image) or not docker or not cosign:
        msg = "Configure the signed release helper digest, Docker and qualified cosign before upgrading"
        raise _error(msg)
    selected = await helper._stage_verified_helper(docker, cosign, image)
    # Offline verification alone does not prove the operator loaded the image.
    await helper._command(docker, "image", "inspect", selected)
    # Exercise the exact isolation profile before stopping the previous app.
    # Creation does not execute the reader or expose application data.
    with tempfile.TemporaryDirectory(prefix="langflow-helper-preflight-") as directory:
        name = f"langflow-helper-preflight-{uuid4().hex}"
        args = helper.isolated_command(docker, selected, Path(directory), name)
        args[1] = "create"
        args.remove("--rm")
        try:
            await helper._command(*args)
        finally:
            await helper._drain_task(asyncio.create_task(helper._command(docker, "rm", "--force", name)))


def _launch_environment(config: dict, receipt: str) -> dict[str, str]:
    """Bind the verified upgrade receipt to the new worker environment."""
    environment = dict(os.environ)
    for key in _HELPER_ENV:
        environment.pop(key, None)
    environment.update(config["helper"])
    environment.update(
        LANGFLOW_KB_UPGRADE_RECEIPT=receipt,
        LANGFLOW_KNOWLEDGE_BASES_DIR=config["root"],
        LANGFLOW_DATABASE_URL=f"sqlite:///{config['database']}",
    )
    return environment


def _launch(journal_path: Path) -> None:
    """Record the new identity before exec, closing the parent-crash launch gap."""
    journal = _read(journal_path)
    if journal["phase"] != "launching":
        msg = "The launch journal is not ready"
        raise _error(msg)
    identity = _identity(psutil.Process())
    # Competing/resumed launchers race on O_EXCL. Only one can ever exec.
    _write(Path(journal["launch"]), identity, exclusive=True)
    config = journal["config"]
    os.chdir(config["cwd"])
    # Explicit operator argv, no shell or PATH lookup.
    os.execve(config["command"][0], config["command"], _launch_environment(config, journal["receipt"]))  # noqa: S606


async def _start(journal_path: Path, journal: dict) -> dict:
    """Launch or resume observation of the new instance using the durable journal."""
    launch = Path(journal["launch"])
    if not launch.exists():
        log = journal_path.parent / "application.log"
        descriptor = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            info = os.fstat(descriptor)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or info.st_mode & 0o077
                or info.st_nlink != 1
            ):
                msg = "Application log must be a private regular file owned by this account"
                raise _error(msg)
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "langflow.services.knowledge_base_storage.controller",
                "--launch",
                str(journal_path),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=descriptor,
                stderr=descriptor,
                start_new_session=True,
            )
        finally:
            os.close(descriptor)
        deadline = time.monotonic() + 15
        while not launch.exists() and time.monotonic() < deadline:
            if process.returncode is not None:
                msg = "The new application launcher failed. Inspect the private application log"
                raise _error(msg)
            await asyncio.sleep(0.05)
    if not launch.exists():
        msg = "The new application identity is not yet recorded. Resume using the same state directory"
        raise _error(msg)
    identity = _read(launch)
    if _process(identity) is None:
        msg = "The new application exited. Inspect its private log, then resume with --restart-new"
        raise _error(msg)
    return identity


def _owns_listener(identity: dict, port: int) -> bool:
    """Check that the saved instance family owns the expected readiness listener."""
    if _process(identity) is None:
        return False
    for process in _family(identity["pid"]):
        try:
            if any(
                connection.status == psutil.CONN_LISTEN
                and connection.family == socket.AF_INET
                and connection.laddr.ip in ("127.0.0.1", "0.0.0.0")  # noqa: S104 -- wildcard covers the exact probe address
                and connection.laddr.port == port
                for connection in process.net_connections(kind="tcp")
            ):
                return True
        except psutil.NoSuchProcess:
            continue
    return False


async def _wait_ready(identity: dict, port: int, timeout: float) -> None:
    """Wait for strict storage readiness from the instance that owns the listener."""
    deadline = time.monotonic() + timeout
    async with httpx.AsyncClient(trust_env=False, timeout=2, follow_redirects=False) as client:
        while time.monotonic() < deadline:
            if _process(identity) is None:
                msg = "The new application exited before readiness. Data and journal are retained"
                raise _error(msg)
            if await helper._disk_call(_owns_listener, identity, port):
                try:
                    response = await client.get(f"http://127.0.0.1:{port}/healthz?require_storage_ready=true")
                    if response.status_code == _HTTP_OK and response.json().get("status") == "ok":
                        return
                except (httpx.HTTPError, ValueError, AttributeError):
                    pass
            await asyncio.sleep(0.25)
    msg = "Readiness timed out. Leave the old supervisor disabled, repair through the new admin API and resume"
    raise _error(msg)


async def upgrade(
    *,
    root: Path,
    database: Path,
    state: Path,
    supervisor: dict,
    command: list[str],
    cwd: Path,
    port: int,
    stop_timeout: float = 30,
    readiness_timeout: float = 3600,
    restart_new: bool = False,
    external_restarts_disabled: bool = False,
) -> dict:
    """Perform or resume one upgrade. Cancellation retains a resumable journal."""
    if os.name != "posix" or not hasattr(os, "getsid"):
        msg = "This controller requires POSIX sessions. Use the platform service manager on Windows"
        raise _error(msg)
    if not external_restarts_disabled:
        msg = "Explicitly attest external service restarters are disabled for this dedicated supervisor"
        raise _error(msg)
    if os.getuid() == 0:
        msg = "Run this controller as the non-root application account so private snapshots remain readable"
        raise _error(msg)
    if (
        not command
        or not Path(command[0]).is_absolute()
        or not Path(command[0]).is_file()
        or not os.access(command[0], os.X_OK)
    ):
        msg = "Supply the new foreground application's absolute executable and argument vector"
        raise _error(msg)
    if (
        not 1 <= port <= _MAX_PORT
        or not 0 < stop_timeout <= _MAX_STOP_TIMEOUT
        or not 0 < readiness_timeout <= _MAX_READINESS_TIMEOUT
    ):
        msg = "Invalid controller port or bounded timeout"
        raise _error(msg)
    state = _private_directory(state)
    root, database, cwd = root.resolve(strict=True), database.resolve(strict=True), cwd.resolve(strict=True)
    if not root.is_dir() or not database.is_file() or not cwd.is_dir():
        msg = "Storage root, SQLite metadata database and application directory must already exist"
        raise _error(msg)
    config = {
        "host": socket.gethostname(),
        "root": str(root),
        "database": str(database),
        "supervisor": supervisor,
        "command": command,
        "cwd": str(cwd),
        "port": port,
        "helper": {key: os.environ[key] for key in _HELPER_ENV if key in os.environ},
    }
    journal_path = state / "upgrade.json"
    lock_path = root / ".upgrade-controller.lock"
    if lock_path.is_symlink():
        msg = "Invalid controller lock path"
        raise _error(msg)
    lock = FileLock(lock_path, timeout=0)
    try:
        lock.acquire()
    except Timeout as exc:
        msg = "Another upgrade controller owns this storage root"
        raise _error(msg) from exc
    try:
        if journal_path.exists():
            journal = _read(journal_path)
            if journal.get("version") != 1 or journal.get("config") != config:
                msg = "Resume with the original instance, command, helper settings and state directory"
                raise _error(msg)
        else:
            selected_supervisor = _validate_supervisor(supervisor)
            if os.getsid(0) == supervisor["pid"]:
                msg = "Run the upgrade controller outside the selected supervisor's session"
                raise _error(msg)
            remaining = maintenance.remaining_legacy_workers(
                excluded_pids={process.pid for process in _family(supervisor["pid"])}
            )
            if remaining:
                msg = f"Unselected Langflow workers remain (PIDs {remaining}). Stop their deployments before upgrading"
                raise _error(msg)
            # Fail before downtime for a busy target port or unreadable metadata.
            with socket.socket() as listener:
                try:
                    listener.bind(("127.0.0.1", port))
                except OSError:
                    if not _owns_listener(supervisor, port):
                        raise
            with closing(sqlite3.connect(f"{database.as_uri()}?mode=ro", uri=True)) as connection:
                if connection.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                    msg = "Application metadata failed its pre-upgrade integrity check"
                    raise _error(msg)
            if not os.access(root, os.W_OK) or not os.access(database, os.W_OK):
                msg = "The application account cannot write the selected data paths"
                raise _error(msg)
            journal = {
                "version": 1,
                "config": config,
                "phase": "prepared",
                "supervisor_identity": _identity(selected_supervisor),
            }
            _write(journal_path, journal, exclusive=True)
        if journal["phase"] in ("prepared", "stopping", "stopped"):
            try:
                await stage_helper()
            except BaseException:
                await helper._disk_call(_resume_before_stop, journal_path, journal)
                raise
        if journal["phase"] in ("prepared", "stopping"):
            await helper._disk_call(_stop, journal_path, journal, stop_timeout)
        if journal["phase"] == "stopped":
            receipt = state / f"receipt-{uuid4().hex}.json"
            await helper._disk_call(
                lambda: maintenance.create_receipt(
                    root=root, database=database, receipt=receipt, previous_workers=journal["workers"]
                )
            )
            journal.update(phase="backed_up", receipt=str(receipt))
            _write(journal_path, journal)
        if journal["phase"] == "backed_up":
            await helper._disk_call(
                lambda: maintenance.validate_receipt(root=root, database=database, receipt=Path(journal["receipt"]))
            )
            journal.update(phase="launching", launch=str(state / f"launch-{uuid4().hex}.json"))
            _write(journal_path, journal)
        if restart_new and journal["phase"] in ("launching", "started", "ready"):
            launch = Path(journal["launch"])
            if launch.exists() and _process(_read(launch)) is None:
                if _family(_read(launch)["pid"]):
                    msg = "New-version workers outlived their supervisor. Stop that deployment before restarting it"
                    raise _error(msg)
                await helper._disk_call(
                    lambda: maintenance.validate_receipt(root=root, database=database, receipt=Path(journal["receipt"]))
                )
                await stage_helper()
                journal.update(phase="launching", launch=str(state / f"launch-{uuid4().hex}.json"))
                _write(journal_path, journal)
        if journal["phase"] == "launching":
            identity = await helper._drain_task(asyncio.create_task(_start(journal_path, journal)))
            journal.update(phase="started", application=identity)
            _write(journal_path, journal)
        await _wait_ready(journal["application"], port, readiness_timeout)
        journal["phase"] = "ready"
        _write(journal_path, journal)
        return journal
    finally:
        lock.release()


def main() -> None:
    """Parse operator arguments and run or resume the managed upgrade controller."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launch", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--supervisor-pid", type=int)
    parser.add_argument("--supervisor-created", type=float)
    parser.add_argument("--cwd", type=Path)
    parser.add_argument("--port", type=int)
    parser.add_argument("--stop-timeout", type=float, default=30)
    parser.add_argument("--readiness-timeout", type=float, default=3600)
    parser.add_argument("--restart-new", action="store_true")
    parser.add_argument("--external-restarts-disabled", action="store_true")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        if args.launch:
            _launch(args.launch)
            return
        if any(
            value is None
            for value in (
                args.root,
                args.database,
                args.state,
                args.supervisor_pid,
                args.supervisor_created,
                args.cwd,
                args.port,
            )
        ):
            parser.error("root, database, state, exact supervisor identity, cwd and port are required")
        command = args.command[1:] if args.command[:1] == ["--"] else args.command
        result = asyncio.run(
            upgrade(
                root=args.root,
                database=args.database,
                state=args.state,
                supervisor={"pid": args.supervisor_pid, "created": args.supervisor_created},
                command=command,
                cwd=args.cwd,
                port=args.port,
                stop_timeout=args.stop_timeout,
                readiness_timeout=args.readiness_timeout,
                restart_new=args.restart_new,
                external_restarts_disabled=args.external_restarts_disabled,
            )
        )
        sys.stdout.write(f"Upgrade {result['phase']}. New supervisor PID: {result['application']['pid']}\n")
    except (UpgradeControllerError, maintenance.MaintenanceRequiredError, helper.MigrationHelperError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
