"""Bounded evaluation runs using the same execution path as the v2 Workflows API.

There is no automatic retry of candidate side effects. Incomplete evaluations never
qualify as passing; the job retains the suite and both executable archives.
"""

from __future__ import annotations

import asyncio
import json
import time
from contextlib import suppress
from functools import partial
from uuid import UUID, uuid4

from fastapi import BackgroundTasks, HTTPException, Request
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
from lfx.workflow.converters import parse_workflow_run_request
from lfx.workflow.host import ResolvedFlow
from lfx.workflow.router import _scope_parsed_to_end_user, check_developer_api_enabled
from sqlalchemy.exc import IntegrityError

from langflow.api.v2.workflow import authorize_flow_action, resolve_flow_for_execution, run_sync_with_mapping
from langflow.api.v2.workflow_host import LangflowWorkflowHost
from langflow.services.authorization import FlowAction
from langflow.services.database.models.flow.model import FlowRead
from langflow.services.database.models.folder.flow_bindings import _authorize, resolve_binding_snapshot
from langflow.services.database.models.jobs.model import JobStatus, JobType
from langflow.services.deployment_artifacts.builder import _run_sync_non_abandoning
from langflow.services.deployment_artifacts.harness import _pack_definitions
from langflow.services.deployment_artifacts.harness_runtime import (
    CANDIDATE_KIND,
    bind_flow,
    candidate_checkpoint,
    retained_candidate,
    validate_candidate_request,
)
from langflow.services.deps import get_job_service, session_scope

MAX_RUN_SECONDS = 300
MAX_RESPONSE_BYTES = 48_000
_SLOTS = asyncio.Semaphore(2)


def present_run(job):
    result = job.result or None
    return {
        "id": str(job.job_id),
        "status": job.status.value,
        "created_at": job.created_timestamp.isoformat(),
        "candidate_digest": (job.job_metadata or {}).get("candidate_digest"),
        "suite_revision": (job.job_metadata or {}).get("suite_revision"),
        "scorer_digest": (job.job_metadata or {}).get("scorer_digest"),
        "passed": job.status == JobStatus.COMPLETED
        and result is not None
        and result.get("complete") is True
        and result.get("passed") is True,
        "result": result,
    }


async def _workflow(flow, caller, request, *, input_value="", variables=None, output_ids=None):
    parsed = parse_workflow_run_request(
        WorkflowRunRequest(
            flow_id=str(flow.id),
            mode="sync",
            input_value=input_value,
            session_id=str(uuid4()),
            globals=variables or {},
            output_ids=output_ids,
        )
    )
    parsed = _scope_parsed_to_end_user(parsed, ResolvedFlow(flow_id=str(flow.id), graph=flow), request)
    return await run_sync_with_mapping(parsed, flow, caller, http_request=request, background_tasks=BackgroundTasks())


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
    suite.require_runnable()
    if suite.revision != expected_revision or suite.candidate_digest != expected_candidate_digest:
        raise HTTPException(409, "The saved suite changed. Reload it before running.")
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
        if (existing.job_metadata or {}).get("suite_revision") != suite.revision or (existing.job_metadata or {}).get(
            "candidate_digest"
        ) != suite.candidate_digest:
            raise HTTPException(409, "This run ID already belongs to a different evaluation.")
        return present_run(existing)

    host = LangflowWorkflowHost()
    target = await host.get_flow(str(suite.workflow_id), caller)
    await host.authorize(caller, target, WorkflowAction.EXECUTE)
    candidate = target.graph.runtime_candidate
    if candidate is None or candidate.digest != suite.candidate_digest:
        raise HTTPException(
            409, "The mounted candidate does not match the suite. Choose its exact digest before running."
        )
    # Preflight the profile before starting any model calls. Approval candidates
    # require the durable Workflows runner and are not supported by this inline evaluator.
    validate_candidate_request(
        parse_workflow_run_request(WorkflowRunRequest(flow_id=str(suite.workflow_id))), target.graph
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
        parse_workflow_run_request(WorkflowRunRequest(flow_id=suite.scorer.flow_id)), scorer_flow
    )
    try:
        job = await jobs.create_job(
            job_id=run_id,
            flow_id=suite.workflow_id,
            user_id=caller.id,
            job_type=JobType.EVALUATION,
            asset_id=project.id,
            asset_type="eval-suite",
            initial_metadata={
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

    report = {"suite": suite.model_dump(mode="json"), "cases": [], "complete": False, "passed": False}
    await jobs.set_result(run_id, report)

    async def execute():
        for case in suite.cases:
            result = EvalCaseResult(case_id=case.id)
            try:
                # Recheck current destination rights/disablement, retaining the exact
                # candidate rather than selecting a new mount between cases.
                frozen = await retained_candidate(job)
                current = await resolve_flow_for_execution(str(suite.workflow_id), caller)
                await authorize_flow_action(caller, current, WorkflowAction.EXECUTE)
                bound = await bind_flow(current, frozen, caller)
                started = time.perf_counter()
                response = await _workflow(bound, caller, request, input_value=case.input)
                result.latency_ms = max(1, round((time.perf_counter() - started) * 1000))
                result.workflow_job_id = UUID(str(response.job_id))
                wire = response.model_dump(mode="json")
                if len(json.dumps(wire).encode()) > MAX_RESPONSE_BYTES:
                    result.failures.append("workflow_output_too_large")
                else:
                    result.output = wire
                if response.status.value != "completed" or response.candidate_digest != candidate.digest:
                    result.failures.append("workflow_failed_or_candidate_mismatch")
                scorer_input = json.dumps({"case": case.model_dump(), "response": wire}, ensure_ascii=False)
                if len(scorer_input) > GLOBAL_VALUE_MAX_LEN:
                    result.failures.append("scorer_input_too_large")
                if not result.failures:
                    async with session_scope() as session:
                        await resolve_binding_snapshot(session, caller, suite.scorer, "scorer", require_current=False)
                        scorer_row = await _authorize(session, caller, suite.scorer.flow_id, FlowAction.EXECUTE)
                        current_scorer = FlowRead.model_validate(scorer_row, from_attributes=True)
                    current_scorer = await bind_flow(current_scorer, scorer_candidate, caller)
                    scored = await _workflow(
                        current_scorer,
                        caller,
                        request,
                        variables={EVAL_INPUT_VARIABLE: scorer_input},
                        output_ids=[suite.scorer.node_id],
                    )
                    result.scorer_job_id = UUID(str(scored.job_id))
                    if scored.status.value != "completed" or scored.candidate_digest != scorer_candidate.digest:
                        result.failures.append("scorer_execution_failed")
                    else:
                        output = scored.model_dump(mode="json")["outputs"].get(suite.scorer.node_id, {})
                        result.verdict = EvalVerdict.model_validate(
                            output_data(output, suite.scorer.output_name).get("evaluation")
                        )
            except (HTTPException, ValueError, KeyError, TypeError):
                # Never convert a failed scorer or unavailable evidence into a pass.
                result.failures.append("execution_or_scorer_contract_error")
            assessed = assess_case(case, result)
            report["cases"].append(assessed.model_dump(mode="json"))
            await jobs.set_result(run_id, report)
        report.update(complete=True, passed=all(case["passed"] for case in report["cases"]))
        await jobs.set_result(run_id, report)

    async def queued():
        async with _SLOTS:
            await execute()

    async def bounded():
        await asyncio.wait_for(queued(), timeout=MAX_RUN_SECONDS)

    # Durable TIMED_OUT status and partial report remain visible.
    with suppress(TimeoutError):
        await jobs.execute_with_status(run_id, bounded)
    return present_run(await jobs.get_job_by_job_id(run_id))
