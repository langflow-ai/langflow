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
from typing import TYPE_CHECKING, Annotated, Any, Literal

import psutil
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from lfx.base.knowledge_bases.backends import is_local_backend
from lfx.log.logger import logger
from pydantic import BaseModel, SecretStr, ValidationError
from sqlalchemy.engine import make_url
from sqlmodel import select

from langflow.api.utils.migration_jobs import active_jobs, live_listeners
from langflow.api.utils.migration_pause import drained
from langflow.api.utils.migration_probes import location, probe_database, probe_files, probe_vectors
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
# Seconds a pause waits for the changes that were let in before it. Past that it is refused.
_DRAIN_SECONDS = 5
# The steps after the check, in page order.
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
# ponytail: a destination's password and keys are held here, in this worker's memory, and nowhere else.
# A restart or a second worker has none, and the page asks for them again. Move them to an encrypted
# file or to Redis when a copy has to be able to start on any worker.
_secrets: dict[str, Any] = {}


class CheckRequest(BaseModel):
    target_version: str


class FindingRequest(BaseModel):
    name: str


class VectorsDestination(BaseModel):
    # OpenSearch comes once its copy takes the password from the environment and not from the command line.
    kind: Literal["pgvector"]


class FilesDestination(BaseModel):
    bucket: str
    prefix: str
    access_key_id: SecretStr
    secret_access_key: SecretStr
    endpoint_url: str | None = None
    ca_bundle: str | None = None


class DestinationsRequest(BaseModel):
    # The address holds a password, so no error and no log line spells it out.
    database_url: SecretStr | None = None
    vectors: VectorsDestination | None = None
    files: FilesDestination | None = None


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


@router.post("/pause")
async def pause_changes(admin: Superuser) -> dict[str, Any]:
    """Stop changes to this instance, so that what is copied next is all of it.

    Nothing is cancelled here. The admin ends what is still writing, then asks again.
    """
    record = _read_record()
    state = await _state(record)
    if record.get("pause"):
        # The moment the re-check and the copies are measured against stays the first one.
        return state
    _require_unlocked(state, "pause")
    # Written first, so that no worker lets a new change in. Read again, with nothing awaited
    # before the write, so that what another request saved meanwhile is kept.
    record = _read_record()
    if record.get("pause"):
        return await _state(record)
    pause = record["pause"] = {"frozen_at": _now(), "frozen_by": admin.username}
    _write_record(record)
    try:
        refusal = await _still_writing(admin)
    except BaseException:
        # A request that is cut off while it waits must not leave a pause that nobody checked.
        _lift(pause)
        raise
    if refusal:
        _lift(pause)
        raise HTTPException(status_code=409, detail=refusal)
    record = _read_record()
    # Another request may have resumed, or paused for itself, while this one waited. Its word stands.
    if record.get("pause") == pause:
        # The instance is still from this moment. The re-check and the copies are measured against it.
        record["pause"] = {**pause, "frozen_at": _now()}
        _write_record(record)
        await logger.ainfo(f"Migration: user_id={admin.id} paused changes to this instance")
    return await _state(record)


@router.delete("/pause")
async def resume_changes(admin: Superuser) -> dict[str, Any]:
    """End the pause. What was checked or copied during it no longer counts, because later changes are in none of it."""
    record = _read_record()
    if record.pop("pause", None):
        _write_record(record)
        await logger.ainfo(f"Migration: user_id={admin.id} resumed changes to this instance")
    return await _state(record)


@router.put("/destinations")
async def save_destinations(http_request: Request, admin: Superuser) -> dict[str, Any]:
    """Test where this instance's data will go, and save what was tested.

    A part that is sent replaces what was saved for it, whether it passed or not. A part
    that is left out stays as it was.
    """
    # Read and checked here, so that a body that fails is answered and never logged: it holds a password
    # and keys. The answer names each field that failed and repeats no value.
    try:
        request = DestinationsRequest.model_validate_json(await http_request.body())
    except ValidationError as exc:
        errors = exc.errors(include_url=False, include_context=False, include_input=False)
        detail = [{**error, "loc": ("body", *error["loc"])} for error in errors]
        raise HTTPException(status_code=422, detail=detail) from None
    instance = await _instance()
    needed = _needed_destinations(instance)
    sent = {"database": request.database_url, "vectors": request.vectors, "files": request.files}
    if unneeded := sorted(part for part in sent if sent[part] and part not in needed):
        raise HTTPException(status_code=422, detail={"code": "not_needed", "parts": unneeded})
    parts: dict[str, dict[str, Any]] = {}
    results: dict[str, dict[str, Any]] = {}
    if request.database_url:
        address = request.database_url.get_secret_value()
        results["database"] = await asyncio.to_thread(probe_database, address, get_db_service().database_url)
        parts["database"] = {"location": location(address)}
        _hold("database_url", address, results["database"])
    if request.vectors:
        # Knowledge bases go into the destination database. An instance already on PostgreSQL keeps them in its own.
        own = instance["database"]["type"] == "postgresql"
        address = get_db_service().database_url if own else _secrets.get("database_url")
        results["vectors"] = (
            await asyncio.to_thread(probe_vectors, address)
            if address
            else {"ok": False, "code": "secrets_missing", "reason": "Enter the database address again."}
        )
        parts["vectors"] = {"kind": request.vectors.kind}
    if files := request.files:
        keys = {
            "access_key_id": files.access_key_id.get_secret_value(),
            "secret_access_key": files.secret_access_key.get_secret_value(),
            "endpoint_url": files.endpoint_url or None,
            "ca_bundle": files.ca_bundle or None,
        }
        results["files"] = await probe_files(bucket=files.bucket, prefix=files.prefix, **keys)
        parts["files"] = {"bucket": files.bucket, "prefix": files.prefix, "endpoint_url": keys["endpoint_url"]}
        _hold("files", keys, results["files"])
    # A test can take seconds. The record is read only now, so that what other requests saved meanwhile is kept.
    record = _read_record()
    saved = record.setdefault("destinations", {})
    # How each test ended is kept, and the driver's own words are not: they can name the database user.
    outcomes = {part: {key: result[key] for key in result if key != "reason"} for part, result in results.items()}
    saved.update(parts, results={**saved.get("results", {}), **outcomes}, saved_by=admin.username, saved_at=_now())
    _write_record(record)
    tested = ", ".join(f"{part} {outcome.get('code', 'ok')}" for part, outcome in outcomes.items())
    await logger.ainfo(f"Migration: user_id={admin.id} tested the destination: {tested}")
    return {**await _state(record), "results": results}


def _hold(name: str, secret: Any, result: dict[str, Any]) -> None:
    """Keep a destination's secret while its test passes, and forget it when it does not."""
    if result["ok"]:
        _secrets[name] = secret
    else:
        _secrets.pop(name, None)


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
        "acceptable_findings": sorted(ACCEPTABLE_FINDINGS),
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
        database["location"] = location(get_db_service().database_url)
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


def _needed_destinations(instance: dict[str, Any]) -> list[str]:
    """The parts of a destination this instance has to name: one for each thing it keeps on its own disk."""
    needs = {
        "database": instance["database"]["type"] != "postgresql",
        "vectors": instance["knowledge_bases"]["local"],
        "files": instance["files"]["local"],
    }
    return [part for part, needed in needs.items() if needed]


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
    needed = _needed_destinations(instance)
    # Skipped always wins, even before a step ships.
    skipped = {
        "connect_target": None if needed else "nothing_to_connect",
        "copy_database": "already_postgresql" if postgresql else None,
        "copy_knowledge_bases": None if local_kbs else "no_local_knowledge_bases",
        "copy_files": "files_in_s3" if files["storage"] == "s3" else None if files["local"] else "no_local_files",
    }
    # What each later step says for itself. A step with no entry is not built yet.
    own = {
        "connect_target": _connect_step(record, needed),
        # The key gets its route next. Until then only the record can say that step is done.
        "secret_key": ("done", None) if record.get("secret_key") else ("current", "not_available"),
        "pause": _pause_step(record, blocking),
    }
    steps = [first]
    # The first step neither done nor skipped is the one to do now. A later step that has not started
    # waits for it, and one that has started keeps saying where it stands.
    frontier_open = first["state"] == "done"
    for step in _LATER_STEPS:
        state, reason = own.get(step, ("current", "not_available"))
        if skipped.get(step):
            state, reason = "skipped", skipped[step]
        elif state == "current" and not frontier_open:
            state, reason = "locked", "earlier_step"
        steps.append({"id": step, "state": state, "reason": reason})
        frontier_open = frontier_open and state in {"done", "skipped"}
    return steps


async def _still_writing(admin: User) -> dict[str, Any] | None:
    """What still writes now that no new change is let in: the refusal to answer with, or None."""
    # The changes that were let in before the pause end first. Only then is it known what writes
    # without a request: a job that one of those changes queued is in the table by now.
    if not await drained(_DRAIN_SECONDS):
        return {"code": "requests_active"}
    async with session_scope() as session:
        jobs, listeners = await active_jobs(session, admin.id), await live_listeners(session)
    return {"code": "jobs_active", "jobs": jobs, "listeners": listeners} if jobs or listeners else None


def _lift(pause: dict[str, Any]) -> None:
    """Take a pause out again, unless another request has since resumed or paused for itself."""
    record = _read_record()
    if record.get("pause") == pause:
        del record["pause"]
        _write_record(record)


def _connect_step(record: dict[str, Any], needed: list[str]) -> tuple[str, str | None]:
    """Where connecting stands. It is done once every part this instance needs was saved and passed its test."""
    saved = record.get("destinations") or {}
    if any(part not in saved for part in needed):
        return "current", None
    failed = [saved["results"][part]["code"] for part in needed if not saved["results"][part]["ok"]]
    return ("blocked", failed[0]) if failed else ("done", None)


def _pause_step(record: dict[str, Any], blocking: list[str]) -> tuple[str, str | None]:
    """Where the pause stands. It is done once a check that started during it has passed."""
    if not record.get("pause"):
        return "current", None
    check = record["steps"].get("check_source") or {}
    # The page starts that check. One from before the pause says nothing about what the instance held when it stopped.
    if check.get("status") != "done" or not _during_pause(record, check["started_at"]):
        return "blocked", "recheck_pending"
    return ("blocked", "recheck_failed") if blocking else ("done", None)


def _during_pause(record: dict[str, Any], moment: str | None) -> bool:
    """Whether this moment falls in the pause that is on now. What an earlier pause saw no longer counts."""
    pause = record.get("pause")
    return bool(pause and moment) and datetime.fromisoformat(moment) > datetime.fromisoformat(pause["frozen_at"])


def _require_unlocked(state: dict[str, Any], step_id: str) -> None:
    """Refuse to act on a step that still waits for an earlier one."""
    step = next(step for step in state["steps"] if step["id"] == step_id)
    if step["state"] == "locked":
        raise HTTPException(status_code=409, detail={"code": "locked", "reason": step["reason"]})


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
