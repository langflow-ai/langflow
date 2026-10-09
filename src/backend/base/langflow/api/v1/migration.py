"""Admin endpoints that walk a superuser through moving this instance to a new Langflow instance.

Each step runs the verified command as a child process instead of calling its
functions here. The commands read their configuration from the environment, and the
moves write to a target this server is not configured for, so running them in this
process would change the server under the admin's feet.

The migration record lives in CONFIG_DIR/migrations, outside the database, because
the database is what moves.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

import psutil
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from lfx.base.knowledge_bases.backends import is_local_backend
from lfx.log.logger import logger
from pydantic import BaseModel
from sqlalchemy.engine import make_url
from sqlmodel import select

from langflow.cli.migration_preflight import check_target_version
from langflow.services.auth.utils import get_current_active_superuser
from langflow.services.database.models.file.model import File
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_db_service, get_settings_service, session_scope
from langflow.utils.version import get_version_info

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

router = APIRouter(prefix="/migration", tags=["Migration"], include_in_schema=False)

Superuser = Annotated[User, Depends(get_current_active_superuser)]

# Failing checks an admin may accept: the move stays safe, and what is left behind is known.
ACCEPTABLE_FINDINGS = frozenset(
    {"default superuser", "source: files", "source: knowledge bases", "source: vector counts"}
)
# The page never sends the target's key, so this check could only say "not checked". "Hand over the secret key" owns it.
_KEY_CHECK = "target key"
# How much of a failed command's stderr the record keeps.
_STDERR_LINES = 40
# The steps after the check, in page order. None of them ships yet.
_LATER_STEPS = (
    "connect_target",
    "secret_key",
    "pause",
    "backup",
    "copy_database",
    "copy_knowledge_bases",
    "copy_files",
    "start_target",
    "check_target",
)
# A report line holds every check's problems, which can pass asyncio's 64 KiB default.
_LINE_LIMIT = 16 * 1024 * 1024
_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


class CheckRequest(BaseModel):
    target_version: str


class FindingRequest(BaseModel):
    name: str


@router.get("")
async def get_migration(_admin: Superuser) -> dict[str, Any]:
    return await _state(_read_record())


@router.post("/checks")
async def run_checks(request: CheckRequest, admin: Superuser) -> StreamingResponse:
    """Run migration-preflight against this instance, one JSON line per check as it finishes.

    Read-only, so it is safe to run while the instance serves traffic.
    """
    # Admins paste what the target shows, such as "Langflow v1.13.0".
    version = re.sub(r"^(langflow\s+)?v?", "", request.target_version.strip(), flags=re.IGNORECASE)
    verdict = check_target_version(version)
    if verdict.status == "warn":
        raise HTTPException(status_code=422, detail={"code": "version_invalid"})
    if verdict.status == "fail":
        raise HTTPException(
            status_code=422, detail={"code": "version_older", "source_version": get_version_info()["version"]}
        )
    record = _read_record()
    live = record["steps"].get("check_source")
    # ponytail: two POSTs landing together can both start; both runs only read.
    if _is_live(live):
        raise HTTPException(
            status_code=409,
            detail={"code": "already_running", "by": live["started_by"], "started_at": live["started_at"]},
        )
    now = _now()
    record["target"] = {"version": version, "set_by": admin.username, "set_at": now}
    step: dict[str, Any] = {
        "status": "running",
        "started_by": admin.username,
        "started_at": now,
        "finished_at": None,
        "target_version": version,
        "exit_code": None,
        "pid": None,
        "report": None,
        "error": None,
    }
    record["steps"]["check_source"] = step
    _write_record(record)
    await logger.ainfo(f"Migration: user_id={admin.id} started the source checks against Langflow {version}")
    return StreamingResponse(_stream_checks(step), media_type="application/x-ndjson")


@router.post("/accepted-findings")
async def accept_finding(request: FindingRequest, admin: Superuser) -> dict[str, Any]:
    if request.name not in ACCEPTABLE_FINDINGS:
        raise HTTPException(status_code=400, detail={"code": "not_acceptable"})
    record = _read_record()
    check = _failing_checks(record).get(request.name)
    if check is None:
        raise HTTPException(status_code=400, detail={"code": "not_failing"})
    record["accepted_findings"] = [
        *(finding for finding in record["accepted_findings"] if finding["name"] != request.name),
        # Counts in a summary can stay the same while the affected resources change.
        {
            "name": request.name,
            "summary": check["summary"],
            "problems": check.get("problems", []),
            "accepted_by": admin.username,
            "accepted_at": _now(),
        },
    ]
    _write_record(record)
    await logger.ainfo(f"Migration: user_id={admin.id} accepted '{request.name}': {check['summary']}")
    return await _state(record)


@router.delete("/accepted-findings")
async def withdraw_finding(name: str, admin: Superuser) -> dict[str, Any]:
    record = _read_record()
    record["accepted_findings"] = [finding for finding in record["accepted_findings"] if finding["name"] != name]
    _write_record(record)
    await logger.ainfo(f"Migration: user_id={admin.id} withdrew the acceptance of '{name}'")
    return await _state(record)


async def _stream_checks(step: dict[str, Any]) -> AsyncIterator[bytes]:
    env = _source_env()
    # The page never sends the target's key, and the run takes none from the server's own environment.
    env.pop("LANGFLOW_TARGET_SECRET_KEY_FILE", None)
    stderr: deque[str] = deque(maxlen=_STDERR_LINES)
    process = drain = None
    try:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "langflow",
            "migration-preflight",
            "--json",
            "--target-version",
            step["target_version"],
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=_LINE_LIMIT,
        )
        # The record names the child, so any worker can tell whether the run is still live.
        step["pid"] = process.pid
        record = _read_record()
        record["steps"]["check_source"] = step
        _write_record(record)
        drain = asyncio.create_task(_collect(process.stderr, stderr))
        async for line in process.stdout:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("event") == "check" and event["check"]["name"] == _KEY_CHECK:
                continue
            if event.get("event") == "report":
                event["checks"] = [check for check in event["checks"] if check["name"] != _KEY_CHECK]
                step["report"] = event
            yield _event(event)
        step["exit_code"] = await process.wait()
        await drain
        if step["report"] is None:
            step["status"] = "failed"
            step["error"] = _ANSI.sub("", "".join(stderr)) or f"migration-preflight exited with {step['exit_code']}"
            yield _event({"event": "error", "message": step["error"]})
        else:
            step["status"] = "done"
    finally:
        # Stopped first, so a record that fails to save cannot leave the child running.
        if drain:
            drain.cancel()
        if process and process.returncode is None:
            process.kill()
        if step["status"] == "running":
            step["status"] = "cancelled"
        step["finished_at"] = _now()
        record = _read_record()
        record["steps"]["check_source"] = step
        _write_record(record)
        if process:
            await process.wait()


def _event(event: dict[str, Any]) -> bytes:
    # A blank line after each event, as Langflow's other streams send them.
    return (json.dumps(event) + "\n\n").encode()


async def _collect(stream: asyncio.StreamReader, lines: deque[str]) -> None:
    async for line in stream:
        lines.append(line.decode(errors="replace"))


def _source_env() -> dict[str, str]:
    """The environment that points a command at the instance this server runs."""
    settings_service = get_settings_service()
    settings = settings_service.settings
    return {
        **os.environ,
        "LANGFLOW_DATABASE_URL": get_db_service().database_url,
        "LANGFLOW_CONFIG_DIR": str(settings.config_dir),
        "LANGFLOW_KNOWLEDGE_BASES_DIR": str(settings.knowledge_bases_dir),
        "LANGFLOW_SECRET_KEY": settings_service.auth_settings.SECRET_KEY.get_secret_value(),
        # The default superuser check reads it, so the run reports on the value this server runs with.
        "LANGFLOW_AUTO_LOGIN": str(settings_service.auth_settings.AUTO_LOGIN).lower(),
    }


def _is_live(check: dict[str, Any] | None) -> bool:
    """Whether a recorded run is still going: it says running and its child still exists."""
    # ponytail: a pid reused after a restart reads as live until that process ends.
    return bool(check and check["status"] == "running" and check.get("pid") and psutil.pid_exists(check["pid"]))


async def _state(record: dict[str, Any]) -> dict[str, Any]:
    check = record["steps"].get("check_source")
    if check and check["status"] == "running" and not _is_live(check):
        # The server restarted mid-run, or the run's request was dropped.
        check["status"] = "cancelled"
    instance = await _instance()
    blocking = _blocking_findings(record)
    return {
        "instance": instance,
        "record": record,
        "steps": _steps(instance, record, blocking),
        "blocking_findings": blocking,
        "acceptable_checks": sorted(ACCEPTABLE_FINDINGS),
    }


async def _instance() -> dict[str, Any]:
    """What this instance runs on, which decides the steps it needs."""
    settings = get_settings_service().settings
    url = make_url(get_db_service().database_url)
    database: dict[str, Any] = {"type": url.get_backend_name()}
    if database["type"] == "sqlite":
        database["path"] = url.database
    else:
        # Never the user or password.
        database["location"] = f"{url.host}:{url.port}/{url.database}" if url.port else f"{url.host}/{url.database}"
    async with session_scope() as session:
        knowledge_bases = (
            await session.exec(select(KnowledgeBaseRecord.backend_type, KnowledgeBaseRecord.backend_config))
        ).all()
        has_files = (await session.exec(select(File.id).limit(1))).first() is not None
        # relocate-files copies from the folder of each user and each flow, and from no other.
        namespaces = {str(identifier) for model in (User, Flow) for identifier in await session.exec(select(model.id))}
    if settings.storage_type.lower() == "s3":
        files = {
            "storage": "s3",
            "bucket": settings.object_storage_bucket_name,
            "prefix": settings.object_storage_prefix,
            "local": False,
        }
    else:
        # Local storage keeps files under CONFIG_DIR, and any other type falls back to it.
        files = {
            "storage": "local",
            "folder": str(settings.config_dir),
            "local": has_files or _has_uploads(Path(settings.config_dir), namespaces),
        }
    return {
        "version": get_version_info()["version"],
        "database": database,
        "knowledge_bases": {
            "folder": str(Path(settings.knowledge_bases_dir).expanduser()) if settings.knowledge_bases_dir else None,
            "local": any(is_local_backend(backend, config) for backend, config in knowledge_bases),
        },
        "files": files,
    }


def _has_uploads(folder: Path, namespaces: set[str]) -> bool:
    """Whether CONFIG_DIR holds files relocate-files would copy.

    The v1 routes save uploads under a flow's id with no File row. relocate-files
    copies the regular files directly inside each user's and each flow's folder, so
    a folder left by a deleted flow, or files in a subfolder, do not count.
    """
    if not folder.is_dir():
        return False
    return any(
        child.name in namespaces and child.is_dir() and any(entry.is_file() for entry in child.iterdir())
        for child in folder.iterdir()
    )


def _steps(instance: dict[str, Any], record: dict[str, Any], blocking: list[str]) -> list[dict[str, Any]]:
    check = record["steps"].get("check_source") or {}
    if check.get("status") != "done":
        first = {"id": "check_source", "state": "current", "reason": None}
    elif blocking:
        first = {"id": "check_source", "state": "blocked", "reason": "blocking_findings"}
    else:
        first = {"id": "check_source", "state": "done", "reason": None}
    postgresql = instance["database"]["type"] == "postgresql"
    local_kbs = instance["knowledge_bases"]["local"]
    files = instance["files"]
    # Skipped always wins, even before a step ships.
    skipped = {
        "connect_target": "nothing_to_connect" if postgresql and files["storage"] == "s3" and not local_kbs else None,
        "copy_database": "already_postgresql" if postgresql else None,
        "copy_knowledge_bases": None if local_kbs else "no_local_knowledge_bases",
        "copy_files": "files_in_s3" if files["storage"] == "s3" else None if files["local"] else "no_local_files",
    }
    steps = [first]
    # The first step neither done nor skipped is the one to do now, and every later one waits for it.
    frontier_open = first["state"] == "done"
    for step in _LATER_STEPS:
        if skipped.get(step):
            steps.append({"id": step, "state": "skipped", "reason": skipped[step]})
        elif frontier_open:
            steps.append({"id": step, "state": "current", "reason": "not_available"})
            frontier_open = False
        else:
            steps.append({"id": step, "state": "locked", "reason": "earlier_step"})
    return steps


def _failing_checks(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    report = (record["steps"].get("check_source") or {}).get("report") or {"checks": []}
    return {check["name"]: check for check in report["checks"] if check["status"] == "fail"}


def _blocking_findings(record: dict[str, Any]) -> list[str]:
    # Older acceptances did not record the problems, so require the admin to accept them again.
    accepted = {
        (finding["name"], finding["summary"], tuple(finding["problems"]))
        for finding in record["accepted_findings"]
        if "problems" in finding
    }
    return [
        name
        for name, check in _failing_checks(record).items()
        if (name, check["summary"], tuple(check.get("problems", []))) not in accepted
    ]


def _record_path() -> Path:
    return Path(get_settings_service().settings.config_dir) / "migrations" / "migration.json"


def _read_record() -> dict[str, Any]:
    path = _record_path()
    if not path.exists():
        return {"target": {}, "steps": {}, "accepted_findings": []}
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise HTTPException(status_code=500, detail={"code": "record_unreadable", "path": str(path)}) from exc


def _write_record(record: dict[str, Any]) -> None:
    path = _record_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Named per process, so two workers writing at once never share a temp file.
    partial = path.with_suffix(f".{os.getpid()}.partial")
    partial.write_text(json.dumps(record, indent=2))
    partial.replace(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
