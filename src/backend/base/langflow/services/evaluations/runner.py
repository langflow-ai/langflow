"""Persistent evaluation coordination over existing durable Workflows child jobs.

Progress and child creation commit atomically. Recovery observes child jobs; it
never retries interrupted tool effects or replaces the frozen suite/scorer.
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from functools import partial
from uuid import UUID, uuid4

from fastapi import HTTPException, Request
from lfx.projects.evaluations import (
    EVAL_INPUT_VARIABLE,
    EvalCaseResult,
    EvalSuiteConfig,
    EvalVerdict,
    assess_case,
    output_data,
)
from lfx.schema.workflow import GLOBAL_VALUE_MAX_LEN, WorkflowRunRequest
from lfx.workflow.actions import WorkflowAction
from lfx.workflow.converters import parse_workflow_run_request, workflow_response_from_output_events
from lfx.workflow.router import check_developer_api_enabled
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select

from langflow.api.v2.workflow import authorize_flow_action, resolve_flow_for_execution
from langflow.api.v2.workflow_host import LangflowWorkflowHost
from langflow.services.authorization import FlowAction
from langflow.services.database.models.flow.model import FlowRead
from langflow.services.database.models.folder.flow_bindings import _authorize, resolve_binding_snapshot
from langflow.services.database.models.jobs.model import Job, JobStatus, JobType, SignalType
from langflow.services.database.models.user.model import User, UserRead
from langflow.services.deployment_artifacts.builder import _run_sync_non_abandoning
from langflow.services.deployment_artifacts.harness import _pack_definitions
from langflow.services.deployment_artifacts.harness_runtime import (
    CANDIDATE_KIND,
    bind_flow,
    candidate_checkpoint,
    retained_candidate,
    validate_candidate_request,
)
from langflow.services.deps import (
    get_background_execution_service,
    get_job_service,
    session_scope,
)
from langflow.services.evaluations.state import ACTIVE, save_progress
from langflow.services.jobs.exceptions import ParentJobChangedError

MAX_RUN_SECONDS = 300
MAX_RESPONSE_BYTES = 48_000


def present_run(job):
    result = job.result or None
    created = job.created_timestamp
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return {
        "id": str(job.job_id),
        "status": job.status.value,
        "created_at": created.isoformat(),
        "candidate_digest": (job.job_metadata or {}).get("candidate_digest"),
        "suite_revision": (job.job_metadata or {}).get("suite_revision"),
        "scorer_digest": (job.job_metadata or {}).get("scorer_digest"),
        "passed": job.status == JobStatus.COMPLETED
        and result is not None
        and result.get("complete") is True
        and result.get("passed") is True,
        "result": result,
        "pending_approval": (result or {}).get("pending_approval"),
        "cancel_requested": (result or {}).get("cancel_requested", False),
        "error": (result or {}).get("error"),
    }


async def run_suite(
    project,
    suite: EvalSuiteConfig,
    caller,
    request: Request,
    run_id: UUID,
    expected_revision: str,
    expected_candidate_digest: str,
):
    await check_developer_api_enabled()
    if any(key.lower().startswith("x-langflow-global-var-") for key in request.headers):
        raise HTTPException(422, "Evaluation runs do not accept request variable overrides.")
    # Evaluation records are an authoring surface. Do not allow serving identities
    # to select another user's private evaluation via a shared service account.
    from lfx.workflow.end_user_identity import serving_end_user_enabled

    if serving_end_user_enabled():
        raise HTTPException(422, "Run Eval Suites on the authenticated authoring host, outside serving end-user mode.")
    jobs = get_job_service()
    existing = await jobs.get_job_by_job_id(run_id)
    if existing is not None:
        if existing.user_id != caller.id or existing.asset_id != project.id or existing.type != JobType.EVALUATION:
            raise HTTPException(404, "Evaluation not found.")
        if (existing.job_metadata or {}).get("suite_revision") != expected_revision or (
            existing.job_metadata or {}
        ).get("candidate_digest") != expected_candidate_digest:
            raise HTTPException(409, "This run ID already belongs to a different evaluation.")
        return present_run(existing)

    suite.require_runnable()
    if suite.revision != expected_revision or suite.candidate_digest != expected_candidate_digest:
        raise HTTPException(409, "The saved suite changed. Reload it before running.")
    host = LangflowWorkflowHost()
    target = await host.get_flow(str(suite.workflow_id), caller)
    await host.authorize(caller, target, WorkflowAction.EXECUTE)
    candidate = target.graph.runtime_candidate
    if candidate is None or candidate.digest != suite.candidate_digest:
        raise HTTPException(
            409, "The mounted candidate does not match the suite. Choose its exact digest before running."
        )
    # Both root graphs use the durable Workflows runner, including approval paths.
    validate_candidate_request(
        parse_workflow_run_request(WorkflowRunRequest(flow_id=str(suite.workflow_id), mode="background")), target.graph
    )
    async with session_scope() as session:
        source = await resolve_binding_snapshot(session, caller, suite.scorer, "scorer", require_current=False)
        scorer_row = await _authorize(session, caller, suite.scorer.flow_id, FlowAction.EXECUTE)
        scorer_flow = FlowRead.model_validate(scorer_row, from_attributes=True)
    scorer_candidate = await _run_sync_non_abandoning(
        partial(_pack_definitions, suite.scorer.flow_id, source.data["dependencies"])
    )
    scorer_flow = await bind_flow(scorer_flow, scorer_candidate, caller)
    validate_candidate_request(
        parse_workflow_run_request(WorkflowRunRequest(flow_id=suite.scorer.flow_id, mode="background")), scorer_flow
    )
    try:
        job = await jobs.create_job(
            job_id=run_id,
            flow_id=suite.workflow_id,
            user_id=caller.id,
            job_type=JobType.EVALUATION,
            asset_id=project.id,
            asset_type="eval-suite",
            initial_result={
                "version": 0,
                "suite": suite.model_dump(mode="json"),
                "cases": [],
                "complete": False,
                "passed": False,
                "current": None,
                "phase": "candidate",
            },
            initial_metadata={
                "evaluation_format": 1,
                "candidate_digest": candidate.digest,
                "scorer_digest": scorer_candidate.digest,
                "suite_revision": suite.revision,
                "suite": suite.model_dump(mode="json"),
            },
            initial_checkpoints={
                CANDIDATE_KIND: await candidate_checkpoint(candidate),
                "eval-scorer": await candidate_checkpoint(scorer_candidate),
            },
        )
    except IntegrityError:
        # Concurrent retry of the same client-generated run ID must not execute twice.
        existing = await jobs.get_job_by_job_id(run_id)
        if (
            existing is None
            or existing.user_id != caller.id
            or existing.asset_id != project.id
            or existing.type != JobType.EVALUATION
            or (existing.job_metadata or {}).get("suite_revision") != suite.revision
            or (existing.job_metadata or {}).get("candidate_digest") != suite.candidate_digest
        ):
            raise HTTPException(409, "Evaluation submission conflicted. Reload its status.") from None
        return present_run(existing)

    await get_background_execution_service().start()
    return present_run(job)


def _now():
    return datetime.now(timezone.utc)


def _child_response(child):
    captures = (child.result or {}).get("outputs")
    if not isinstance(captures, list) or not captures:
        msg = "Workflow outputs are unavailable."
        raise ValueError(msg)
    request = (child.job_metadata or {}).get("request") or {}
    response = workflow_response_from_output_events(
        captures,
        flow_id=str(child.flow_id),
        job_id=str(child.job_id),
        session_id=request.get("session_id") or str(child.flow_id),
        fail_on_rejected=True,
    )
    return response.model_copy(
        update={"candidate_digest": (child.job_metadata or {}).get("candidate_digest")}
    ).model_dump(mode="json")


async def _caller(job):
    from langflow.api.v1.project_evaluations import eval_project

    await check_developer_api_enabled()
    async with session_scope() as session:
        user = await session.get(User, job.user_id)
        if user is None or not user.is_active:
            raise HTTPException(403, "Evaluation owner is unavailable.")
        caller = UserRead.model_validate(user, from_attributes=True)
        await eval_project(session, caller, job.asset_id, write=True)
    return caller


async def _submit_child(service, job, progress, suite, caller):
    from langflow.api.v2.workflow import _default_frame_source_factory

    phase = progress.get("phase", "candidate")
    case = suite.cases[len(progress["cases"])]
    variables = {}
    output_ids = None
    if phase == "candidate":
        candidate = await retained_candidate(job)
        flow = await resolve_flow_for_execution(str(suite.workflow_id), caller)
        await authorize_flow_action(caller, flow, WorkflowAction.EXECUTE)
        input_value = case.input
    else:
        async with session_scope() as session:
            # Submission retained the reviewed definitions. Authoring snapshots may
            # be pruned while awaiting approval; only current access is checked here.
            row = await _authorize(session, caller, suite.scorer.flow_id, FlowAction.EXECUTE)
            for dependency in suite.scorer.dependencies:
                await _authorize(session, caller, dependency.flow_id, FlowAction.EXECUTE)
            flow = FlowRead.model_validate(row, from_attributes=True)
        scorer_job = job.model_copy(
            update={
                "flow_id": UUID(suite.scorer.flow_id),
                "job_metadata": {"candidate_digest": job.job_metadata["scorer_digest"]},
            }
        )
        candidate = await retained_candidate(scorer_job, kind="eval-scorer")
        variables[EVAL_INPUT_VARIABLE] = json.dumps(
            {"case": case.model_dump(), "response": progress["case_result"]["output"]}, ensure_ascii=False
        )
        if len(variables[EVAL_INPUT_VARIABLE]) > GLOBAL_VALUE_MAX_LEN:
            msg = "Scorer input is too large."
            raise ValueError(msg)
        input_value = ""
        output_ids = [suite.scorer.node_id]
    bound = await bind_flow(flow, candidate, caller)
    validate_candidate_request(
        parse_workflow_run_request(WorkflowRunRequest(flow_id=str(flow.id), mode="background")), bound
    )
    child_id = uuid4()
    next_progress = {
        **progress,
        "current": {
            "job_id": str(child_id),
            "phase": phase,
            "case_id": case.id,
        },
        "pending_approval": None,
    }
    request = {
        "flow_id": str(flow.id),
        "mode": "background",
        "stream_protocol": "langflow",
        "input_value": input_value,
        "session_id": str(child_id),
        "globals": variables,
        "output_ids": output_ids,
        "evaluation_timeout_s": MAX_RUN_SECONDS,
    }
    if service._frame_source_factory is None:  # noqa: SLF001 -- same wiring as the Workflows host
        service._frame_source_factory = _default_frame_source_factory  # noqa: SLF001
    await service.submit(
        flow_id=flow.id,
        request=request,
        user=caller,
        runtime_candidate=candidate,
        job_id=child_id,
        parent_update=(job.job_id, progress["version"], next_progress),
    )


async def _advance(service, job):
    jobs = get_job_service()
    progress = deepcopy(job.result)
    suite = EvalSuiteConfig.model_validate(job.job_metadata["suite"])
    suite.require_runnable()
    current = progress.get("current")
    child = await jobs.get_job_by_job_id(UUID(current["job_id"])) if current else None
    # Stop requests persist before cancellation is attempted. The same compare-and-set
    # used when creating children prevents a late coordinator from creating new work.
    if progress.get("cancel_requested"):
        if child is not None and child.status in ACTIVE:
            signals = await jobs.unconsumed_signals(child.job_id)
            if child.status == JobStatus.SUSPENDED or not any(
                signal.signal_type == SignalType.STOP for signal in signals
            ):
                await service.stop_job(child.job_id, service._user_stub(job.user_id))  # noqa: SLF001
            return
        progress.update(passed=False, complete=False, pending_approval=None)
        await save_progress(job, progress, JobStatus(progress.get("stop_status", "cancelled")))
        return
    try:
        caller = await _caller(job)
        if current is None:
            if len(progress["cases"]) == len(suite.cases):
                progress.update(complete=True, passed=all(item["passed"] for item in progress["cases"]))
                await save_progress(job, progress, JobStatus.COMPLETED)
            else:
                await _submit_child(service, job, progress, suite, caller)
            return
        if child is None or child.user_id != job.user_id or child.type != JobType.WORKFLOW:
            msg = "Evaluation child is unavailable."
            raise ValueError(msg)
        if child.status == JobStatus.SUSPENDED:
            pending = await jobs.get_pending_human_request(child.job_id)
            approval = {**current, "request": pending} if pending else None
            if job.status != JobStatus.SUSPENDED or progress.get("pending_approval") != approval:
                progress["pending_approval"] = approval
                await save_progress(job, progress, JobStatus.SUSPENDED)
            return
        if child.status in ACTIVE:
            if job.status != JobStatus.IN_PROGRESS or progress.get("pending_approval"):
                progress["pending_approval"] = None
                await save_progress(job, progress, JobStatus.IN_PROGRESS)
            return
        case = suite.cases[len(progress["cases"])]
        result = EvalCaseResult.model_validate(progress.get("case_result") or {"case_id": case.id})
        phase = current["phase"]
        expected = job.job_metadata["candidate_digest" if phase == "candidate" else "scorer_digest"]
        setattr(result, "workflow_job_id" if phase == "candidate" else "scorer_job_id", child.job_id)
        if child.status != JobStatus.COMPLETED or (child.job_metadata or {}).get("candidate_digest") != expected:
            result.failures.append(
                "workflow_failed_or_candidate_mismatch" if phase == "candidate" else "scorer_execution_failed"
            )
        else:
            wire = _child_response(child)
            if phase == "candidate":
                start = (
                    child.created_timestamp.replace(tzinfo=timezone.utc)
                    if child.created_timestamp.tzinfo is None
                    else child.created_timestamp
                )
                finish = child.finished_timestamp or _now()
                finish = finish.replace(tzinfo=timezone.utc) if finish.tzinfo is None else finish
                result.latency_ms = max(1, round((finish - start).total_seconds() * 1000))
                if len(json.dumps(wire).encode()) > MAX_RESPONSE_BYTES:
                    result.failures.append("workflow_output_too_large")
                else:
                    result.output = wire
                scorer_input = json.dumps({"case": case.model_dump(), "response": wire}, ensure_ascii=False)
                if len(scorer_input) > GLOBAL_VALUE_MAX_LEN:
                    result.failures.append("scorer_input_too_large")
                if not result.failures:
                    progress.update(
                        current=None, pending_approval=None, phase="scorer", case_result=result.model_dump(mode="json")
                    )
                    await save_progress(job, progress, JobStatus.IN_PROGRESS)
                    return
            else:
                output = wire["outputs"].get(suite.scorer.node_id, {})
                result.verdict = EvalVerdict.model_validate(
                    output_data(output, suite.scorer.output_name).get("evaluation")
                )
        assessed = assess_case(case, result)
        progress["cases"].append(assessed.model_dump(mode="json"))
        progress.update(current=None, pending_approval=None, phase="candidate", case_result=None)
        if child.status in {JobStatus.FAILED, JobStatus.TIMED_OUT, JobStatus.CANCELLED}:
            progress["error"] = (
                "workflow_interrupted"
                if child.status == JobStatus.FAILED and (not child.error or child.error.get("type") == "worker_lost")
                else f"workflow_{child.status.value}"
            )
            await save_progress(job, progress, child.status)
        else:
            await save_progress(job, progress, JobStatus.IN_PROGRESS)
    except ParentJobChangedError:
        return  # Another coordinator or cancellation won; no child was created.
    except (HTTPException, ValueError, KeyError, TypeError):
        # Keep evidence; authorization, corruption and missing dependencies must not
        # strand an active child or advance the suite with incomplete evidence.
        progress.update(cancel_requested=True, stop_status="failed", error="execution_or_scorer_contract_error")
        await save_progress(job, progress, JobStatus.IN_PROGRESS)


async def advance_evaluations(service):
    """Recover and advance persisted coordinators without occupying a workflow worker."""
    async with session_scope() as session:
        rows = (
            await session.exec(
                select(Job)
                .where(
                    Job.type == JobType.EVALUATION,
                    col(Job.status).in_(ACTIVE),
                    col(Job.job_metadata)["evaluation_format"].as_integer() == 1,
                )
                .order_by(Job.created_timestamp)
            )
        ).all()
    # Children share the host's existing bounded executor. Suspended evaluations
    # consume no worker, so approvals cannot starve unrelated workflow execution.
    for job in rows:
        await _advance(service, job)
