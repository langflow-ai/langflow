"""Run `langflow upgrade-check` from a target release and import its report.

One request owns one run: the generator below holds the child process, and closing it
(a disconnect, a cancel, the timeout) stops the child. Nothing is kept between requests.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import shutil
import signal
import sys
import tempfile
from collections import deque
from importlib import metadata
from pathlib import Path
from typing import TYPE_CHECKING, Any

import anyio
import httpx
import sqlalchemy as sa
from lfx.constants import BASE_COMPONENTS_PATH
from packaging.version import InvalidVersion, Version
from sqlmodel import col, func, or_, select

from langflow.api.utils.migration_pause import write_admission
from langflow.initial_setup.constants import STARTER_FOLDER_NAME
from langflow.services.authorization.audit import audit_decision
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.deps import get_db_service, get_settings_service, session_scope
from langflow.services.upgrade_reports.history import MAX_REPORT_BYTES, store_report
from langflow.utils.version import VERSION_INFO

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping
    from uuid import UUID

    from lfx.services.settings.base import Settings
    from sqlmodel.ext.asyncio.session import AsyncSession

CHECKS_PATH = "/api/v1/upgrade-reports/checks"
# The first release that has `upgrade-check`.
MIN_TARGET = Version("1.14.0")
MAX_RELEASES = 20
TIMEOUT_SECONDS = 60 * 60
HEARTBEAT_SECONDS = 15
STOP_GRACE_SECONDS = 10
PYPI_TIMEOUT_SECONDS = 10
MAX_STDERR_CHARS = 2000
_MAX_VERSION_LENGTH = 64
_STDERR_KEPT_BYTES = 8192

# ponytail: per-process lock; two workers can each run one
check_lock = asyncio.Lock()


class InvalidTargetVersionError(ValueError):
    pass


def running_version() -> Version:
    """The release this server is, without a dev or local suffix."""
    return Version(VERSION_INFO["main_version"])


def installed_package() -> str:
    try:
        metadata.version("langflow")
    except metadata.PackageNotFoundError:
        return "langflow-base"
    return "langflow"


def _is_final_release(version: Version) -> bool:
    return not (version.is_prerelease or version.local or version.epoch)


def parse_target_version(raw: str, *, current: Version) -> Version:
    """Return the target as a Version, or raise. Nothing else of `raw` may reach the command."""
    if len(raw) > _MAX_VERSION_LENGTH:
        raise InvalidTargetVersionError
    try:
        version = Version(raw.strip())
    except InvalidVersion:
        raise InvalidTargetVersionError from None
    if not _is_final_release(version) or version < MIN_TARGET or version < current:
        raise InvalidTargetVersionError
    return version


def parse_releases(pypi: Mapping[str, Any], *, current: Version, limit: int = MAX_RELEASES) -> list[str]:
    """Final releases newer than `current` that still have a file to install, newest first."""
    releases = pypi.get("releases") if isinstance(pypi, dict) else None
    if not isinstance(releases, dict):
        msg = "the index answer has no releases"
        raise ValueError(msg)  # noqa: TRY004
    found: list[Version] = []
    for name, files in releases.items():
        try:
            version = Version(name)
        except InvalidVersion:
            continue
        installable = isinstance(files, list) and any(isinstance(f, dict) and not f.get("yanked") for f in files)
        if installable and _is_final_release(version) and version > current:
            found.append(version)
    return [str(version) for version in sorted(found, reverse=True)[:limit]]


async def fetch_pypi(package: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=PYPI_TIMEOUT_SECONDS, follow_redirects=True) as client:
        response = await client.get(f"https://pypi.org/pypi/{package}/json")
        response.raise_for_status()
        return response.json()


def source_database_url(database_url: str) -> str:
    """The server's async driver names a synchronous reader's URL: the check reads with its own driver."""
    url = sa.make_url(database_url)
    if url.get_backend_name() == "sqlite":
        url = url.set(drivername="sqlite")
    return url.render_as_string(hide_password=False)


# The running release's own packages. Their components folders belong to this release; the target ships its own.
_RELEASE_FOLDERS = (Path(__file__).resolve().parents[2], Path(BASE_COMPONENTS_PATH).resolve().parent)


def _admin_components_folders(paths: list[str]) -> list[str]:
    """The components folders the admin added.

    `langflow run` also names a default folder that may not exist. The server skips a missing folder, so
    the check skips it too.
    """
    kept = []
    for path in paths:
        folder = Path(path).resolve()
        if folder.is_dir() and not any(folder.is_relative_to(root) for root in _RELEASE_FOLDERS):
            kept.append(path)
    return kept


def check_command(
    *,
    target: Version,
    current: Version,
    package: str,
    database_url: str,
    output: Path,
    settings: Settings,
    python: str = sys.executable,
    uvx: str = "uvx",
) -> list[str]:
    """The command that checks `database_url` against `target`. The running release needs no download."""
    if target == current:
        command = [python, "-m", "langflow"]
    else:
        command = [uvx, "--python", python, "--from", f"{package}[postgresql]=={target}", "langflow"]
    command += ["upgrade-check", "--database-url", database_url, "--json", "--output", str(output)]
    for path in _admin_components_folders(settings.components_path):
        command += ["--components-path", path]
    for name in (
        "allow_custom_components",
        "substitute_outdated_component_code",
        "block_code_interpreter_components",
        "custom_component_admin_only",
        "allow_components_paths_override",
    ):
        flag = name.replace("_", "-")
        command.append(f"--{flag}" if getattr(settings, name) else f"--no-{flag}")
    return command


def _redact(text: str, database_url: str) -> str:
    text = text.replace(database_url, "<database url>")
    password = sa.make_url(database_url).password
    return text.replace(password, "***") if password else text


async def _stop(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    # ponytail: on Windows terminate() reaches only this process, so a grandchild can outlive the run.
    # The check's own signal handling stops its child on POSIX.
    posix = os.name == "posix"
    with contextlib.suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGTERM) if posix else process.terminate()
    try:
        await asyncio.wait_for(process.wait(), STOP_GRACE_SECONDS)
    except asyncio.TimeoutError:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL) if posix else process.kill()
        await process.wait()


async def _keep_stderr_tail(stream: asyncio.StreamReader, tail: deque[bytes]) -> None:
    size = 0
    while chunk := await stream.read(4096):
        tail.append(chunk)
        size += len(chunk)
        while size > _STDERR_KEPT_BYTES and len(tail) > 1:
            size -= len(tail.popleft())


async def count_checked_flows(session: AsyncSession) -> int:
    """How many flows and saved components the check reads: every one outside the starter projects.

    The check also reads the saved versions that triggers or deployments still run, so it can pass this number.
    """
    starter = select(Folder.id).where(Folder.name == STARTER_FOLDER_NAME, col(Folder.user_id).is_(None))
    outside = or_(col(Flow.folder_id).is_(None), col(Flow.folder_id).not_in(starter))
    return (await session.exec(select(func.count()).select_from(Flow).where(outside))).one()


def _error(code: str, message: str) -> dict[str, str]:
    return {"event": "error", "code": code, "message": message}


async def run_check(
    target: Version, *, current: Version, package: str, admin_id: UUID
) -> AsyncIterator[dict[str, Any]]:
    """Run the check and import its report. The last event is `imported` or `error`."""
    if check_lock.locked():
        yield _error("check_running", "An upgrade check is already running on this server.")
        return
    await check_lock.acquire()
    try:
        download = target != current
        async with session_scope() as session:
            total = await count_checked_flows(session)
        yield {"event": "started", "target_version": str(target), "download": download, "total": total}
        settings = get_settings_service().settings
        database_url = source_database_url(get_db_service().database_url)
        with tempfile.TemporaryDirectory(prefix="langflow-upgrade-check-run-") as folder:
            output = Path(folder) / "report.json"
            command = check_command(
                target=target,
                current=current,
                package=package,
                database_url=database_url,
                output=output,
                settings=settings,
                uvx=shutil.which("uvx") or "uvx",
            )
            env = {**os.environ, "UV_CACHE_DIR": str(Path(folder) / "uv-cache")}
            try:
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                    start_new_session=os.name == "posix",
                    # One event carries the whole report.
                    limit=MAX_REPORT_BYTES + 1024 * 1024,
                )
            except OSError:
                yield _error("install_failed", "The check could not be started.")
                return
            stderr_tail: deque[bytes] = deque()
            stderr_task = asyncio.ensure_future(_keep_stderr_tail(process.stderr, stderr_tail))
            line_task: asyncio.Future[bytes] | None = None
            child_error: dict[str, Any] | None = None
            loop = asyncio.get_running_loop()
            deadline = loop.time() + TIMEOUT_SECONDS
            timed_out = False
            try:
                line_task = asyncio.ensure_future(process.stdout.readline())
                while True:
                    remaining = deadline - loop.time()
                    if remaining <= 0:
                        timed_out = True
                        break
                    done, _ = await asyncio.wait({line_task}, timeout=min(HEARTBEAT_SECONDS, remaining))
                    if not done:
                        yield {"event": "heartbeat"}
                        continue
                    try:
                        line = line_task.result()
                    except ValueError:
                        # A line over the limit is no event this run can use.
                        break
                    if not line:
                        break
                    line_task = asyncio.ensure_future(process.stdout.readline())
                    if line.startswith(b'{"event": "report"'):
                        continue
                    try:
                        event = json.loads(line)
                    except ValueError:
                        continue
                    kind = event.get("event") if isinstance(event, dict) else None
                    flow = event.get("flow") if kind == "flow" else None
                    if isinstance(flow, dict) and flow.get("status") in {"ok", "warn", "fail"}:
                        yield {"event": "flow", "status": flow["status"]}
                    elif kind == "error":
                        child_error = _error(
                            str(event.get("code", "check_failed")),
                            _redact(str(event.get("message", "The check could not finish.")), database_url),
                        )
                if not timed_out:
                    await asyncio.wait_for(process.wait(), max(deadline - loop.time(), 0))
            except asyncio.TimeoutError:
                timed_out = True
            finally:
                # A cancelled request must still stop the child before the folder goes.
                with anyio.CancelScope(shield=True):
                    if line_task is not None:
                        line_task.cancel()
                    await _stop(process)
                    await asyncio.gather(stderr_task, return_exceptions=True)
            if timed_out:
                yield _error("timeout", f"The check did not finish within {TIMEOUT_SECONDS // 60} minutes.")
                return
            if child_error is not None:
                yield child_error
                return
            if process.returncode not in {0, 1} or not output.is_file():
                tail = b"".join(stderr_tail).decode(errors="replace").strip()
                message = _redact(tail, database_url)[-MAX_STDERR_CHARS:] or "The check ended without a report."
                yield _error("install_failed", message)
                return
            content = output.read_bytes()
        async with write_admission("request", method="POST", path=CHECKS_PATH, caller_id=admin_id) as refusal:
            if refusal is not None:
                final = _error("import_refused", refusal)
            else:
                try:
                    if len(content) > MAX_REPORT_BYTES:
                        raise ValueError
                    async with session_scope() as session:
                        row = await store_report(session, content, admin_id)
                except (ValueError, UnicodeError, RecursionError):
                    final = _error("invalid_upgrade_report", "The check produced a report that Langflow cannot import.")
                else:
                    await audit_decision(
                        user_id=admin_id, action="upgrade-report:import", obj=f"upgrade-report:{row.id}", result="allow"
                    )
                    # The counts let the page say what the report found without loading it.
                    flows = {
                        "ok": row.flow_count - row.warning_count - row.failing_count,
                        "warn": row.warning_count,
                        "fail": row.failing_count,
                    }
                    final = {"event": "imported", "report_id": str(row.id), "flows": flows}
        yield final
    finally:
        check_lock.release()


def ndjson(event: Mapping[str, Any]) -> str:
    """One event as the frontend's stream reader splits them: JSON, then a blank line."""
    return json.dumps(event) + "\n\n"
