from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status
from fastapi.responses import StreamingResponse

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.evals_errors import evals_http_errors, evals_write
from langflow.services.authorization import DatasetAction, FlowAction
from langflow.services.database.models.evaluation import Evaluation, EvaluationResult, EvaluationRun
from langflow.services.deps import get_settings_service
from langflow.services.evaluations import evaluation_service, run_service
from langflow.services.evaluations.access import load_eval_dataset, load_eval_flow, load_evaluation
from langflow.services.evaluations.dataset_service import item_text
from langflow.services.evaluations.estimate import estimate_run
from langflow.services.evaluations.flow_checks import check_flow
from langflow.services.evaluations.results_export import export_results
from langflow.services.evaluations.schemas import (
    EstimateRead,
    EstimateRequest,
    EvaluationCreate,
    EvaluationPage,
    EvaluationRead,
    EvaluationResultPage,
    EvaluationResultRead,
    EvaluationRunPage,
    EvaluationRunRead,
    EvaluationUpdate,
    FlowCheckReport,
    RunStart,
)

router = APIRouter(tags=["Evals"])

RESULT_PREVIEW_CHARS = 500

PageParam = Annotated[int, Query(ge=1)]
SizeParam = Annotated[int, Query(ge=1, le=200)]
# Tables that page on the client load a whole dataset or run (both capped at a few thousand rows).
LargeSizeParam = Annotated[int, Query(ge=1, le=5000)]


async def _evaluation_read(session, evaluation) -> EvaluationRead:
    return (await evaluation_service.to_evaluation_reads(session, [evaluation]))[0]


@router.get("/evaluations", response_model=EvaluationPage)
async def list_evaluations(
    current_user: CurrentActiveUser,
    session: DbSession,
    project_id: UUID | None = None,
    flow_id: UUID | None = None,
    page: PageParam = 1,
    size: SizeParam = 50,
) -> EvaluationPage:
    rows, total = await evaluation_service.list_evaluations(
        session, current_user, project_id=project_id, flow_id=flow_id, page=page, size=size
    )
    items = await evaluation_service.to_evaluation_reads(session, rows)
    return EvaluationPage(items=items, total=total, page=page, size=size)


@router.post("/evaluations", response_model=EvaluationRunRead | EvaluationRead, status_code=status.HTTP_201_CREATED)
async def create_evaluation(
    payload: EvaluationCreate,
    current_user: CurrentActiveUser,
    session: DbSession,
    run: bool = False,  # noqa: FBT001, FBT002 - query flag for "Create & Run"
) -> EvaluationRead | EvaluationRunRead:
    async def operation() -> Evaluation | EvaluationRun:
        evaluation = await evaluation_service.create_evaluation(session, current_user, payload)
        if run:
            return await run_service.start_evaluation_run(session, current_user, evaluation, payload.flow_version_id)
        return evaluation

    async with evals_http_errors():
        created = await evals_write(session, "create_evaluation", operation)
    if isinstance(created, EvaluationRun):
        return evaluation_service.to_run_read(created)
    return await _evaluation_read(session, created)


@router.get("/evaluations/check", response_model=FlowCheckReport)
async def check_flow_for_evaluation(
    current_user: CurrentActiveUser,
    session: DbSession,
    flow_id: UUID,
    output_vertex_id: str | None = None,
) -> FlowCheckReport:
    async with evals_http_errors():
        flow = await load_eval_flow(session, current_user, flow_id, FlowAction.READ)
    return check_flow(flow.data, output_vertex_id)


@router.post("/evaluations/estimate", response_model=EstimateRead)
async def estimate_evaluation(
    payload: EstimateRequest, current_user: CurrentActiveUser, session: DbSession
) -> EstimateRead:
    async with evals_http_errors():
        flow = await load_eval_flow(session, current_user, payload.flow_id, FlowAction.READ)
        dataset = await load_eval_dataset(session, current_user, payload.dataset_id, DatasetAction.READ)
    return await estimate_run(
        session,
        flow_id=flow.id,
        flow_data=flow.data,
        dataset_id=dataset.id,
        scorers=[spec.model_dump() for spec in payload.scorers],
        judge_max_output_tokens=get_settings_service().settings.evals_judge_max_output_tokens,
    )


@router.get("/evaluations/{evaluation_id}", response_model=EvaluationRead)
async def get_evaluation(evaluation_id: UUID, current_user: CurrentActiveUser, session: DbSession) -> EvaluationRead:
    async with evals_http_errors():
        evaluation = await load_evaluation(session, current_user, evaluation_id)
    return await _evaluation_read(session, evaluation)


@router.patch("/evaluations/{evaluation_id}", response_model=EvaluationRead)
async def update_evaluation(
    evaluation_id: UUID, payload: EvaluationUpdate, current_user: CurrentActiveUser, session: DbSession
) -> EvaluationRead:
    async with evals_http_errors():
        evaluation = await load_evaluation(session, current_user, evaluation_id)
        evaluation = await evaluation_service.update_evaluation(session, current_user, evaluation, payload)
    return await _evaluation_read(session, evaluation)


@router.delete("/evaluations/{evaluation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evaluation(evaluation_id: UUID, current_user: CurrentActiveUser, session: DbSession) -> None:
    async def operation() -> None:
        evaluation = await load_evaluation(session, current_user, evaluation_id)
        await evaluation_service.delete_evaluation(session, evaluation)

    async with evals_http_errors():
        await evals_write(session, "delete_evaluation", operation)


@router.post(
    "/evaluations/{evaluation_id}/runs", response_model=EvaluationRunRead, status_code=status.HTTP_202_ACCEPTED
)
async def start_evaluation_run_endpoint(
    evaluation_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
    payload: RunStart | None = None,
) -> EvaluationRunRead:
    # A repeated click cannot start two runs: an evaluation allows one active run (409 otherwise).
    version_id = payload.flow_version_id if payload else None

    async def operation() -> EvaluationRun:
        evaluation = await load_evaluation(session, current_user, evaluation_id)
        return await run_service.start_evaluation_run(session, current_user, evaluation, version_id)

    async with evals_http_errors():
        run = await evals_write(session, "start_evaluation_run", operation)
    return evaluation_service.to_run_read(run)


@router.get("/evaluations/{evaluation_id}/runs", response_model=EvaluationRunPage)
async def list_evaluation_runs(
    evaluation_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
    page: PageParam = 1,
    size: SizeParam = 50,
) -> EvaluationRunPage:
    async with evals_http_errors():
        evaluation = await load_evaluation(session, current_user, evaluation_id)
    runs, total = await run_service.list_runs(session, evaluation.id, page=page, size=size)
    items = [
        evaluation_service.to_run_read(run).model_copy(update={"summary": await run_service.live_summary(session, run)})
        for run in runs
    ]
    return EvaluationRunPage(items=items, total=total, page=page, size=size)


@router.get("/evaluation-runs/{run_id}", response_model=EvaluationRunRead)
async def get_evaluation_run(run_id: UUID, current_user: CurrentActiveUser, session: DbSession) -> EvaluationRunRead:
    async with evals_http_errors():
        run = await run_service.get_run(session, current_user, run_id)
    read = evaluation_service.to_run_read(run)
    return read.model_copy(update={"summary": await run_service.live_summary(session, run)})


@router.post("/evaluation-runs/{run_id}/cancel", response_model=EvaluationRunRead)
async def cancel_evaluation_run_endpoint(
    run_id: UUID, current_user: CurrentActiveUser, session: DbSession
) -> EvaluationRunRead:
    async def operation() -> EvaluationRun:
        run = await run_service.get_run(session, current_user, run_id)
        return await run_service.cancel_evaluation_run(session, run)

    async with evals_http_errors():
        run = await evals_write(session, "cancel_evaluation_run", operation)
    return evaluation_service.to_run_read(run)


def _clip(text: str | None, limit: int | None) -> tuple[str | None, bool]:
    if text is None or limit is None or len(text) <= limit:
        return text, False
    return text[:limit], True


def _result_read(row: EvaluationResult, *, preview_chars: int | None) -> EvaluationResultRead:
    question, clipped_input = _clip(item_text(row.input) or "", preview_chars)
    expected, clipped_expected = _clip(item_text(row.expected_output), preview_chars)
    actual, clipped_actual = _clip(row.actual_output, preview_chars)
    return EvaluationResultRead(
        id=row.id,
        position=row.position,
        input=question or "",
        expected_output=expected,
        actual_output=actual,
        output_truncated=row.output_truncated,
        error=row.error,
        scores=row.scores or {},
        passed=row.passed,
        duration_ms=row.duration_ms,
        tokens_flow=row.tokens_flow,
        tokens_judge=row.tokens_judge,
        cost_flow=row.cost_flow,
        cost_judge=row.cost_judge,
        trace_id=row.trace_id,
        preview=clipped_input or clipped_expected or clipped_actual,
    )


@router.get("/evaluation-runs/{run_id}/results", response_model=EvaluationResultPage)
async def list_evaluation_results(
    run_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
    passed: bool | None = None,  # noqa: FBT001
    page: PageParam = 1,
    size: LargeSizeParam = 50,
) -> EvaluationResultPage:
    async with evals_http_errors():
        run = await run_service.get_run(session, current_user, run_id)
    rows, total = await run_service.list_results(session, run.id, passed=passed, page=page, size=size)
    # The table loads a whole run and refetches while it runs: full texts would be megabytes per poll.
    items = [_result_read(row, preview_chars=RESULT_PREVIEW_CHARS) for row in rows]
    return EvaluationResultPage(items=items, total=total, page=page, size=size)


@router.get("/evaluation-runs/{run_id}/results/{result_id}", response_model=EvaluationResultRead)
async def get_evaluation_result(
    run_id: UUID, result_id: UUID, current_user: CurrentActiveUser, session: DbSession
) -> EvaluationResultRead:
    async with evals_http_errors():
        run = await run_service.get_run(session, current_user, run_id)
        row = await run_service.get_result(session, run.id, result_id)
    return _result_read(row, preview_chars=None)


@router.get("/evaluation-runs/{run_id}/export")
async def export_evaluation_run(run_id: UUID, current_user: CurrentActiveUser, session: DbSession) -> StreamingResponse:
    async with evals_http_errors():
        run = await run_service.get_run(session, current_user, run_id)
    rows, _ = await run_service.list_results(session, run.id, passed=None, page=1, size=run.total_items or 1)
    names = [spec["name"] for spec in run.config.get("scorers", [])]
    return StreamingResponse(
        export_results(rows, names),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="evaluation-run-{run.id}.csv"'},
    )
