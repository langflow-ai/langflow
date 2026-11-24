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
from functools import partial
from importlib import metadata
from pathlib import Path
from typing import TYPE_CHECKING, Any

import anyio
import httpx
import sqlalchemy as sa
from lfx.constants import BASE_COMPONENTS_PATH
from lfx.log.logger import logger
from packaging.version import InvalidVersion, Version
from sqlmodel import col, func, or_, select

from langflow.api.utils.migration_pause import write_admission
from langflow.api.utils.migration_runs import _keep_tail, _read_lines
from langflow.initial_setup.constants import STARTER_FOLDER_NAME
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.deps import get_db_service, get_settings_service, session_scope
from langflow.services.upgrade_reports.history import (
    MAX_REPORT_BYTES,
    UnsupportedReportFormatError,
    import_report_content,
)
from langflow.utils.version import VERSION_INFO

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Mapping
    from uuid import UUID

    from lfx.services.settings.base import Settings
    from sqlmodel.ext.asyncio.session import AsyncSession

CHECKS_PATH = "/api/v1/upgrade-reports/checks"
# The first release that has `upgrade-check`.
MIN_TARGET = Version("1.14.0")
MAX_RELEASES = 20
TIMEOUT_SECONDS = 60 * 60
HEARTBEAT_SECONDS = 15
# Above the CLI's own 10 s wait for its child.
STOP_GRACE_SECONDS = 15
DRAIN_SECONDS = 5
PYPI_TIMEOUT_SECONDS = 10
MAX_STDERR_CHARS = 2000
_MAX_VERSION_LENGTH = 64
DATABASE_URL_VARIABLE = "LANGFLOW_UPGRADE_CHECK_DATABASE_URL"

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


async def fetch_pypi(package: str, version: Version | None = None) -> dict[str, Any]:
    path = f"{package}/{version}" if version else package
    async with httpx.AsyncClient(timeout=PYPI_TIMEOUT_SECONDS, follow_redirects=True) as client:
        response = await client.get(f"https://pypi.org/pypi/{path}/json")
        response.raise_for_status()
        return response.json()


async def fetch_upload_time(package: str, version: Version) -> str | None:
    """When the last file of a release was uploaded, or None when the index does not say."""
    try:
        answer = await fetch_pypi(package, version)
        times = [file["upload_time_iso_8601"] for file in answer["urls"]]
    except (httpx.HTTPError, ValueError, LookupError, TypeError):
        return None
    return max(times) if times else None


# The running release's own packages. Their components folders belong to this release; the target ships its own.
_RELEASE_FOLDERS = (Path(__file__).resolve().parents[2], Path(BASE_COMPONENTS_PATH).resolve().parent)

# What the check and uv may inherit. The server's secret key, provider keys and cloud credentials stay out:
# uv resolves dependencies afresh and runs code from them.
_ENVIRONMENT = frozenset(
    {
        "PATH",
        "HOME",
        "USERPROFILE",
        "APPDATA",
        "TMP",
        "TEMP",
        "TMPDIR",
        "LANG",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "REQUESTS_CA_BUNDLE",
        "SYSTEMROOT",
        "COMSPEC",
        "PATHEXT",
        "WINDIR",
    }
)
# Locale, uv's index and auth settings for mirrors, and libpq's connection settings.
_ENVIRONMENT_PREFIXES = ("LC_", "UV_", "PG", "KRB5")


def check_environment(inherited: Mapping[str, str], *, database_url: str, cache_dir: Path) -> dict[str, str]:
    env = {
        name: value
        for name, value in inherited.items()
        if name.upper() in _ENVIRONMENT or name.upper().startswith(_ENVIRONMENT_PREFIXES)
    }
    env["UV_CACHE_DIR"] = str(cache_dir)
    env[DATABASE_URL_VARIABLE] = database_url
    return env


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
    output: Path,
    settings: Settings,
    python: str = sys.executable,
    uvx: str = "uvx",
    exclude_newer: str | None = None,
) -> list[str]:
    """The command that checks the database named by `DATABASE_URL_VARIABLE` against `target`.

    The running release needs no download. With `exclude_newer`, uv resolves the target's dependencies as
    they were when that release shipped.
    """
    if target == current:
        command = [python, "-m", "langflow"]
    else:
        command = [uvx, "--python", python]
        if exclude_newer:
            command += ["--exclude-newer", exclude_newer]
        command += ["--from", f"{package}[postgresql]=={target}", "langflow"]
    command += ["upgrade-check", "--json", "--output", str(output)]
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


async def count_checked_flows(session: AsyncSession) -> int:
    """How many flows and saved components the check reads: every one outside the starter projects.

    The check also reads the saved versions that triggers or deployments still run, so it can pass this number.
    """
    starter = select(Folder.id).where(Folder.name == STARTER_FOLDER_NAME, col(Folder.user_id).is_(None))
    outside = or_(col(Flow.folder_id).is_(None), col(Flow.folder_id).not_in(starter))
    return (await session.exec(select(func.count()).select_from(Flow).where(outside))).one()


def _error(code: str, message: str) -> dict[str, str]:
    return {"event": "error", "code": code, "message": message}


def _translate(line: bytes) -> dict[str, Any] | None:
    """The page's event for one line of the check's output, or None for a line the page does not need."""
    try:
        event = json.loads(line)
    except (ValueError, RecursionError):
        return None
    kind = event.get("event") if isinstance(event, dict) else None
    flow = event.get("flow") if kind == "flow" else None
    if isinstance(flow, dict) and flow.get("status") in {"ok", "warn", "fail"}:
        return {"event": "flow", "status": flow["status"]}
    if kind == "error":
        return _error(str(event.get("code", "check_failed")), str(event.get("message", "The check could not finish.")))
    return None


async def _child_events(
    argv: list[str],
    env: Mapping[str, str],
    *,
    timeout: float,  # noqa: ASYNC109
    heartbeat: float,
    redact: Callable[[str], str],
) -> AsyncIterator[dict[str, Any]]:
    """Run the check and yield its flow events and a heartbeat while it is quiet.

    The child is stopped before this ends, however it ends. A run that does not finish ends with exactly
    one error event, and a run that does ends without one.
    """
    try:
        process = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            start_new_session=os.name == "posix",
        )
    except NotImplementedError:
        # Windows with a selector event loop, which Langflow uses with PostgreSQL.
        yield _error("subprocess_unavailable", "This server cannot start the check. Run it from a terminal instead.")
        return
    except OSError:
        yield _error("install_failed", "The check could not be started.")
        return
    stderr = bytearray()
    drain = asyncio.ensure_future(_keep_tail(process.stderr, stderr))
    lines = _read_lines(process.stdout)
    next_line = asyncio.ensure_future(anext(lines, None))
    child_error: dict[str, Any] | None = None
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    timed_out = False
    try:
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                timed_out = True
                break
            done, _ = await asyncio.wait({next_line}, timeout=min(heartbeat, remaining))
            if not done:
                yield {"event": "heartbeat"}
                continue
            line = next_line.result()
            if line is None:
                break
            next_line = asyncio.ensure_future(anext(lines, None))
            event = _translate(line)
            if event is None:
                continue
            if event["event"] == "error":
                child_error = {**event, "message": redact(event["message"])}
            else:
                yield event
        if not timed_out:
            await asyncio.wait_for(process.wait(), max(deadline - loop.time(), 0))
    except asyncio.TimeoutError:
        timed_out = True
    finally:
        # A cancelled request must still stop the child before its folder goes.
        with anyio.CancelScope(shield=True):
            next_line.cancel()
            await _stop(process)
            # A grandchild that holds the pipe open must not hold the run.
            with contextlib.suppress(Exception):
                await asyncio.wait_for(drain, DRAIN_SECONDS)
    if timed_out:
        yield _error("timeout", f"The check did not finish within {round(timeout / 60)} minutes.")
    elif child_error is not None:
        yield child_error
    elif process.returncode not in {0, 1}:
        tail = bytes(stderr).decode(errors="replace").strip()
        yield _error("install_failed", redact(tail)[-MAX_STDERR_CHARS:] or "The check ended without a report.")


async def run_check(
    target: Version, *, current: Version, package: str, admin_id: UUID
) -> AsyncIterator[dict[str, Any]]:
    """Run the check and import its report. The last event is `imported` or `error`."""
    if check_lock.locked():
        yield _error("check_running", "An upgrade check is already running on this server.")
        return
    await check_lock.acquire()
    folder = Path(tempfile.mkdtemp(prefix="langflow-upgrade-check-run-"))
    try:
        download = target != current
        async with session_scope() as session:
            total = await count_checked_flows(session)
        yield {"event": "started", "target_version": str(target), "download": download, "total": total}
        database_url = get_db_service().database_url
        output = folder / "report.json"
        # ponytail: without an upload time the install resolves today's dependencies. The pin is an extra
        # guard, so a failed lookup does not stop the check.
        exclude_newer = await fetch_upload_time(package, target) if download else None
        command = check_command(
            target=target,
            current=current,
            package=package,
            output=output,
            settings=get_settings_service().settings,
            uvx=shutil.which("uvx") or "uvx",
            exclude_newer=exclude_newer,
        )
        env = check_environment(os.environ, database_url=database_url, cache_dir=folder / "uv-cache")
        async with contextlib.aclosing(
            _child_events(
                command,
                env,
                timeout=TIMEOUT_SECONDS,
                heartbeat=HEARTBEAT_SECONDS,
                redact=lambda text: _redact(text, database_url),
            )
        ) as events:
            async for event in events:
                yield event
                if event["event"] == "error":
                    return
        if not output.is_file():
            yield _error("install_failed", "The check ended without a report.")
            return
        async with await anyio.open_file(output, "rb") as report:
            content = await report.read(MAX_REPORT_BYTES + 1)
        async with write_admission("request", method="POST", path=CHECKS_PATH, caller_id=admin_id) as refusal:
            if refusal is not None:
                final = _error("import_refused", refusal)
            else:
                try:
                    async with session_scope() as session:
                        row = await import_report_content(session, content, admin_id)
                except UnsupportedReportFormatError:
                    final = _error(
                        "unsupported_upgrade_report_format",
                        "The target release wrote a report format this release cannot import.",
                    )
                except (ValueError, UnicodeError, RecursionError):
                    final = _error("invalid_upgrade_report", "The check produced a report that Langflow cannot import.")
                else:
                    # The counts let the page say what the report found without loading it.
                    flows = {
                        "ok": row.flow_count - row.warning_count - row.failing_count,
                        "warn": row.warning_count,
                        "fail": row.failing_count,
                    }
                    final = {"event": "imported", "report_id": str(row.id), "flows": flows}
        yield final
    except Exception:  # noqa: BLE001
        await logger.aexception("The upgrade check stopped unexpectedly")
        yield _error("check_failed", "The check stopped unexpectedly. The server log has the details.")
    finally:
        # The cache of a download is large: remove it off the event loop, and also when the request is cancelled.
        with anyio.CancelScope(shield=True):
            await anyio.to_thread.run_sync(partial(shutil.rmtree, folder, ignore_errors=True))
        check_lock.release()


def ndjson(event: Mapping[str, Any]) -> str:
    """One event as the frontend's stream reader splits them: JSON, then a blank line."""
    return json.dumps(event) + "\n\n"
