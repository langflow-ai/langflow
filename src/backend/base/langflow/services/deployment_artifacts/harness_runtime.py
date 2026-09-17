"""Operator-mounted candidates and job-owned retention on the existing workflow host.

No source database lookup resolves executable dependencies. Destination workflow
permissions and component/provider policy remain live. Mounts select new runs;
job-owned archive bytes select continuations, independently of later mounts.
"""

from __future__ import annotations

import asyncio
import base64
from functools import partial
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import HTTPException
from lfx.projects.runtime_artifacts import MAX_EXPANDED_BYTES, MAX_MANIFEST_BYTES, read_candidate, requirements_for
from lfx.projects.runtime_preflight import preflight_candidate
from lfx.utils.flow_validation import prepare_flow_build_for_user_from_cache

from langflow.services.deployment_artifacts.builder import _run_sync_non_abandoning
from langflow.services.deps import get_job_service, get_settings_service

if TYPE_CHECKING:
    from lfx.projects.runtime_artifacts import RuntimeCandidate
    from lfx.services.settings.groups.runtime import HarnessCandidateMount
    from lfx.workflow.converters import ParsedWorkflowRun

    from langflow.services.database.models.flow.model import FlowRead
    from langflow.services.database.models.jobs.model import Job
    from langflow.services.database.models.user.model import UserRead

CANDIDATE_KIND = "harness-candidate"
_MAX_ARCHIVE = MAX_EXPANDED_BYTES + MAX_MANIFEST_BYTES
_SLOTS = asyncio.Semaphore(2)


def candidate_error(message: str) -> HTTPException:
    return HTTPException(409, detail={"code": "HARNESS_CANDIDATE_NOT_READY", "message": message})


def _check_enabled(flow_id: UUID | str) -> HarnessCandidateMount | None:
    mount = get_settings_service().settings.harness_candidate_mounts.get(UUID(str(flow_id)))
    if mount is not None and not mount.enabled:
        msg = "This Harness candidate mount is disabled."
        raise candidate_error(msg)
    return mount


def _read_mount(mount: HarnessCandidateMount) -> RuntimeCandidate:
    with mount.path.open("rb") as file:
        content = file.read(_MAX_ARCHIVE + 1)
    return read_candidate(content, expected_digest=mount.digest)


async def mounted_flow(flow: FlowRead, caller: UserRead) -> FlowRead:
    """Called only after the destination flow's execute authorization."""
    mount = _check_enabled(flow.id)
    if mount is None:
        return flow
    try:
        async with _SLOTS:
            candidate = await _run_sync_non_abandoning(partial(_read_mount, mount))
        return await bind_flow(flow, candidate, caller)
    except (ValueError, OSError) as exc:
        msg = "The configured Harness candidate is unavailable or incompatible."
        raise candidate_error(msg) from exc


async def bind_flow(flow: FlowRead, candidate: RuntimeCandidate, caller: UserRead) -> FlowRead:
    async with _SLOTS:
        return await _run_sync_non_abandoning(partial(_bind_flow, flow, candidate, caller))


def _bind_flow(flow: FlowRead, candidate: RuntimeCandidate, caller: UserRead) -> FlowRead:
    from lfx.graph import Graph

    from langflow.services.model_provider_policy_scope import scoped_model_provider_policy_for_flow

    if candidate.manifest["entrypoints"] != [str(flow.id)]:
        msg = "The Harness candidate does not match this workflow entrypoint."
        raise candidate_error(msg)
    try:
        preflight_candidate(candidate, capabilities=("durable_approval",))
        for definition in candidate.definitions.values():
            if definition["id"] != str(flow.id) and requirements_for([definition])["capabilities"]:
                msg = "Durable approval inside a nested flow is not supported by this host yet."
                raise candidate_error(msg)
            sanitized = prepare_flow_build_for_user_from_cache(
                definition["data"], is_superuser=bool(getattr(caller, "is_superuser", False))
            )
            if sanitized is not None and sanitized != definition["data"]:
                msg = "Destination component policy would change this candidate. Rebuild it first."
                raise candidate_error(msg)
            with scoped_model_provider_policy_for_flow(
                flow, user_id=caller.id, is_superuser=bool(getattr(caller, "is_superuser", False))
            ):
                graph = Graph.from_payload(definition["data"], flow_id=definition["id"], user_id=str(caller.id))
                candidate.bind(graph)
                graph.prepare()
    except (ValueError, ImportError) as exc:
        raise candidate_error(str(exc)) from exc
    root = candidate.definitions[str(flow.id)]
    result = flow.model_copy(update={"data": root["data"], "name": root["name"]})
    result._runtime_candidate = candidate  # noqa: SLF001 -- server-only, non-serialized binding
    return result


def validate_candidate_request(parsed: ParsedWorkflowRun, flow: FlowRead) -> None:
    candidate = getattr(flow, "runtime_candidate", None)
    if candidate is None:
        return
    unsupported = [
        name
        for name in ("data", "tweaks", "files", "start_component_id", "stop_component_id")
        if getattr(parsed, name) or (name == "data" and parsed.data is not None)
    ]
    if unsupported:
        raise HTTPException(
            422,
            detail={
                "code": "HARNESS_CANDIDATE_OVERRIDES_UNSUPPORTED",
                "fields": unsupported,
                "message": "Candidate definitions are immutable. Use input_value, session_id, globals, or output_ids.",
            },
        )
    if "durable_approval" in candidate.manifest["requirements"]["capabilities"] and parsed.mode != "background":
        msg = "This candidate requires durable approval. Use mode='background'."
        raise candidate_error(msg)


async def candidate_checkpoint(candidate: RuntimeCandidate) -> str:
    """Encode outside the event loop; commit alongside the job, never after enqueue."""
    async with _SLOTS:
        return await _run_sync_non_abandoning(lambda: base64.b64encode(candidate.archive()).decode("ascii"))


async def retained_candidate(
    job: Job, *, check_enabled: bool = True, kind: str = CANDIDATE_KIND
) -> RuntimeCandidate | None:
    """No mount/draft fallback, including legacy jobs started without a candidate."""
    digest = (job.job_metadata or {}).get("candidate_digest")
    if digest is None:
        return None
    if check_enabled:
        _check_enabled(job.flow_id)
    blob = await get_job_service().load_checkpoint(job.job_id, kind)
    if not isinstance(blob, str) or len(blob) > ((_MAX_ARCHIVE + 2) // 3) * 4:
        msg = "The retained Harness candidate is missing or too large; this run cannot resume."
        raise candidate_error(msg)
    try:
        async with _SLOTS:
            candidate = await _run_sync_non_abandoning(
                lambda: read_candidate(base64.b64decode(blob, validate=True), expected_digest=digest)
            )
        if candidate.manifest["entrypoints"] != [str(job.flow_id)]:
            msg = "Candidate entrypoint mismatch"
            raise ValueError(msg)
    except ValueError as exc:
        msg = "The retained Harness candidate failed integrity verification."
        raise candidate_error(msg) from exc
    return candidate
