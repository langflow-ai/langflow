import asyncio
import time
from datetime import datetime, timezone
from difflib import SequenceMatcher
from http import HTTPStatus
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlmodel import col, select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.processing.process import process_tweaks, run_graph
from langflow.services.database.models.dataset.model import Dataset
from langflow.services.database.models.evaluation.model import (
    Evaluation,
    EvaluationCreate,
    EvaluationRead,
    EvaluationReadWithResults,
    EvaluationResult,
    EvaluationResultRead,
    EvaluationStatus,
    EvaluationUpdate,
    ScoringMethod,
)
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import session_scope
from lfx.graph import Graph

router = APIRouter(prefix="/evaluations", tags=["Evaluations"])


def calculate_score(method: str, expected: str, actual: str) -> float:
    """Calculate score based on the scoring method."""
    if not actual:
        return 0.0

    if method == ScoringMethod.EXACT_MATCH.value:
        return 1.0 if expected.strip() == actual.strip() else 0.0

    if method == ScoringMethod.CONTAINS.value:
        return 1.0 if expected.strip().lower() in actual.strip().lower() else 0.0

    if method == ScoringMethod.SIMILARITY.value:
        return SequenceMatcher(None, expected.strip().lower(), actual.strip().lower()).ratio()

    # LLM_JUDGE would require an LLM call - for now return 0.5 as placeholder
    if method == ScoringMethod.LLM_JUDGE.value:
        return 0.5

    return 0.0


async def run_single_evaluation_item(
    flow_data: dict,
    flow_id: UUID,
    flow_name: str,
    user_id: UUID,
    input_value: str,
    scoring_methods: list[str],
    expected_output: str,
) -> dict:
    """Run a single evaluation item and return results."""
    start_time = time.time()
    actual_output = None
    error = None

    try:
        session_id = str(uuid4())
        graph = Graph.from_payload(
            payload=flow_data,
            flow_id=str(flow_id),
            flow_name=flow_name,
            user_id=str(user_id),
        )
        graph.session_id = session_id
        graph.set_run_id(session_id)
        graph.user_id = str(user_id)
        await graph.initialize_run()

        result = await run_graph(
            graph=graph,
            session_id=session_id,
            input_value=input_value,
            fallback_to_env_vars=True,
            input_type="chat",
            output_type="chat",
            stream=False,
        )

        # Extract output from result
        if result and len(result) > 0:
            first_result = result[0]
            if hasattr(first_result, "results") and first_result.results:
                # Get the message from the first output
                output_data = first_result.results.get("message", {})
                if hasattr(output_data, "text"):
                    actual_output = output_data.text
                elif isinstance(output_data, dict) and "text" in output_data:
                    actual_output = output_data["text"]
                elif isinstance(output_data, str):
                    actual_output = output_data
                else:
                    actual_output = str(output_data) if output_data else None
            elif hasattr(first_result, "outputs") and first_result.outputs:
                # Try to get from outputs
                for output in first_result.outputs.values():
                    if hasattr(output, "message") and output.message:
                        if hasattr(output.message, "text"):
                            actual_output = output.message.text
                        else:
                            actual_output = str(output.message)
                        break

    except Exception as e:
        error = str(e)

    duration_ms = int((time.time() - start_time) * 1000)

    # Calculate scores
    scores = {}
    for method in scoring_methods:
        scores[method] = calculate_score(method, expected_output, actual_output or "")

    # Determine if passed (average score > 0.5)
    avg_score = sum(scores.values()) / len(scores) if scores else 0.0
    passed = avg_score >= 0.5

    return {
        "actual_output": actual_output,
        "duration_ms": duration_ms,
        "scores": scores,
        "passed": passed,
        "error": error,
    }


async def run_evaluation_background(evaluation_id: UUID, user_id: UUID):
    """Background task to run the evaluation."""
    async with session_scope() as session:
        # Get the evaluation
        statement = select(Evaluation).where(Evaluation.id == evaluation_id)
        result = await session.exec(statement)
        evaluation = result.first()

        if not evaluation:
            return

        # Update status to running
        evaluation.status = EvaluationStatus.RUNNING.value
        evaluation.started_at = datetime.now(timezone.utc)
        evaluation.updated_at = datetime.now(timezone.utc)
        session.add(evaluation)
        await session.commit()

        try:
            # Get the dataset
            dataset_statement = select(Dataset).where(Dataset.id == evaluation.dataset_id)
            dataset_result = await session.exec(dataset_statement)
            dataset = dataset_result.first()

            if not dataset:
                raise ValueError("Dataset not found")

            # Get the flow
            flow_statement = select(Flow).where(Flow.id == evaluation.flow_id)
            flow_result = await session.exec(flow_statement)
            flow = flow_result.first()

            if not flow:
                raise ValueError("Flow not found")

            # Sort items by order
            sorted_items = sorted(dataset.items, key=lambda x: x.order) if dataset.items else []
            evaluation.total_items = len(sorted_items)
            session.add(evaluation)
            await session.commit()

            total_score = 0.0
            total_duration = 0
            passed_count = 0

            # Run each item
            for idx, item in enumerate(sorted_items):
                item_result = await run_single_evaluation_item(
                    flow_data=flow.data,
                    flow_id=flow.id,
                    flow_name=flow.name,
                    user_id=user_id,
                    input_value=item.input,
                    scoring_methods=evaluation.scoring_methods,
                    expected_output=item.expected_output,
                )

                # Create result record
                db_result = EvaluationResult(
                    evaluation_id=evaluation_id,
                    dataset_item_id=item.id,
                    input=item.input,
                    expected_output=item.expected_output,
                    actual_output=item_result["actual_output"],
                    duration_ms=item_result["duration_ms"],
                    scores=item_result["scores"],
                    passed=item_result["passed"],
                    error=item_result["error"],
                    order=idx,
                    created_at=datetime.now(timezone.utc),
                )
                session.add(db_result)

                # Update metrics
                if item_result["scores"]:
                    avg_score = sum(item_result["scores"].values()) / len(item_result["scores"])
                    total_score += avg_score
                if item_result["duration_ms"]:
                    total_duration += item_result["duration_ms"]
                if item_result["passed"]:
                    passed_count += 1

                # Update progress
                evaluation.completed_items = idx + 1
                session.add(evaluation)
                await session.commit()

            # Update final metrics
            evaluation.status = EvaluationStatus.COMPLETED.value
            evaluation.completed_at = datetime.now(timezone.utc)
            evaluation.updated_at = datetime.now(timezone.utc)
            evaluation.passed_items = passed_count
            evaluation.mean_score = total_score / len(sorted_items) if sorted_items else None
            evaluation.mean_duration_ms = total_duration / len(sorted_items) if sorted_items else None
            evaluation.total_runtime_ms = (
                int((evaluation.completed_at - evaluation.started_at).total_seconds() * 1000)
                if evaluation.started_at
                else None
            )
            session.add(evaluation)
            await session.commit()

        except Exception as e:
            evaluation.status = EvaluationStatus.FAILED.value
            evaluation.error_message = str(e)
            evaluation.updated_at = datetime.now(timezone.utc)
            session.add(evaluation)
            await session.commit()


@router.post("/", response_model=EvaluationRead, status_code=HTTPStatus.CREATED)
async def create_evaluation(
    *,
    session: DbSession,
    evaluation: EvaluationCreate,
    current_user: CurrentActiveUser,
    background_tasks: BackgroundTasks,
    run_immediately: bool = False,
):
    """Create a new evaluation."""
    # Verify dataset exists
    dataset_statement = select(Dataset).where(Dataset.id == evaluation.dataset_id, Dataset.user_id == current_user.id)
    dataset_result = await session.exec(dataset_statement)
    dataset = dataset_result.first()
    if not dataset:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Dataset not found")

    # Verify flow exists
    flow_statement = select(Flow).where(Flow.id == evaluation.flow_id)
    flow_result = await session.exec(flow_statement)
    flow = flow_result.first()
    if not flow:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Flow not found")

    # Generate name if not provided
    name = evaluation.name
    if not name:
        name = f"Evaluation {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"

    db_evaluation = Evaluation(
        name=name,
        scoring_methods=evaluation.scoring_methods,
        user_id=current_user.id,
        dataset_id=evaluation.dataset_id,
        flow_id=evaluation.flow_id,
        status=EvaluationStatus.PENDING.value,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        total_items=len(dataset.items) if dataset.items else 0,
    )

    session.add(db_evaluation)
    await session.commit()
    await session.refresh(db_evaluation)

    if run_immediately:
        background_tasks.add_task(run_evaluation_background, db_evaluation.id, current_user.id)

    return EvaluationRead(
        id=db_evaluation.id,
        name=db_evaluation.name,
        status=db_evaluation.status,
        scoring_methods=db_evaluation.scoring_methods,
        user_id=db_evaluation.user_id,
        dataset_id=db_evaluation.dataset_id,
        flow_id=db_evaluation.flow_id,
        dataset_name=dataset.name,
        flow_name=flow.name,
        created_at=db_evaluation.created_at,
        updated_at=db_evaluation.updated_at,
        total_items=db_evaluation.total_items,
    )


@router.get("/", response_model=list[EvaluationRead], status_code=HTTPStatus.OK)
async def list_evaluations(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    flow_id: UUID | None = None,
):
    """List all evaluations for the current user, optionally filtered by flow."""
    statement = select(Evaluation).where(Evaluation.user_id == current_user.id)
    if flow_id:
        statement = statement.where(Evaluation.flow_id == flow_id)
    statement = statement.order_by(col(Evaluation.created_at).desc())

    result = await session.exec(statement)
    evaluations = result.all()

    # Get dataset and flow names
    response = []
    for ev in evaluations:
        dataset_name = None
        flow_name = None

        ds_stmt = select(Dataset).where(Dataset.id == ev.dataset_id)
        ds_result = await session.exec(ds_stmt)
        ds = ds_result.first()
        if ds:
            dataset_name = ds.name

        fl_stmt = select(Flow).where(Flow.id == ev.flow_id)
        fl_result = await session.exec(fl_stmt)
        fl = fl_result.first()
        if fl:
            flow_name = fl.name

        response.append(
            EvaluationRead(
                id=ev.id,
                name=ev.name,
                status=ev.status,
                scoring_methods=ev.scoring_methods,
                user_id=ev.user_id,
                dataset_id=ev.dataset_id,
                flow_id=ev.flow_id,
                dataset_name=dataset_name,
                flow_name=flow_name,
                created_at=ev.created_at,
                updated_at=ev.updated_at,
                started_at=ev.started_at,
                completed_at=ev.completed_at,
                error_message=ev.error_message,
                total_items=ev.total_items,
                completed_items=ev.completed_items,
                passed_items=ev.passed_items,
                mean_score=ev.mean_score,
                mean_duration_ms=ev.mean_duration_ms,
                total_runtime_ms=ev.total_runtime_ms,
            )
        )

    return response


@router.get("/{evaluation_id}", response_model=EvaluationReadWithResults, status_code=HTTPStatus.OK)
async def get_evaluation(
    *,
    session: DbSession,
    evaluation_id: UUID,
    current_user: CurrentActiveUser,
):
    """Get an evaluation with all its results."""
    statement = select(Evaluation).where(Evaluation.id == evaluation_id, Evaluation.user_id == current_user.id)
    result = await session.exec(statement)
    evaluation = result.first()

    if not evaluation:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Evaluation not found")

    # Get dataset and flow names
    dataset_name = None
    flow_name = None

    ds_stmt = select(Dataset).where(Dataset.id == evaluation.dataset_id)
    ds_result = await session.exec(ds_stmt)
    ds = ds_result.first()
    if ds:
        dataset_name = ds.name

    fl_stmt = select(Flow).where(Flow.id == evaluation.flow_id)
    fl_result = await session.exec(fl_stmt)
    fl = fl_result.first()
    if fl:
        flow_name = fl.name

    # Sort results by order
    sorted_results = sorted(evaluation.results, key=lambda x: x.order) if evaluation.results else []

    return EvaluationReadWithResults(
        id=evaluation.id,
        name=evaluation.name,
        status=evaluation.status,
        scoring_methods=evaluation.scoring_methods,
        user_id=evaluation.user_id,
        dataset_id=evaluation.dataset_id,
        flow_id=evaluation.flow_id,
        dataset_name=dataset_name,
        flow_name=flow_name,
        created_at=evaluation.created_at,
        updated_at=evaluation.updated_at,
        started_at=evaluation.started_at,
        completed_at=evaluation.completed_at,
        error_message=evaluation.error_message,
        total_items=evaluation.total_items,
        completed_items=evaluation.completed_items,
        passed_items=evaluation.passed_items,
        mean_score=evaluation.mean_score,
        mean_duration_ms=evaluation.mean_duration_ms,
        total_runtime_ms=evaluation.total_runtime_ms,
        results=[
            EvaluationResultRead(
                id=r.id,
                evaluation_id=r.evaluation_id,
                dataset_item_id=r.dataset_item_id,
                input=r.input,
                expected_output=r.expected_output,
                actual_output=r.actual_output,
                duration_ms=r.duration_ms,
                scores=r.scores,
                passed=r.passed,
                error=r.error,
                order=r.order,
                created_at=r.created_at,
            )
            for r in sorted_results
        ],
    )


@router.post("/{evaluation_id}/run", response_model=EvaluationRead, status_code=HTTPStatus.OK)
async def run_evaluation(
    *,
    session: DbSession,
    evaluation_id: UUID,
    current_user: CurrentActiveUser,
    background_tasks: BackgroundTasks,
):
    """Start or re-run an evaluation."""
    statement = select(Evaluation).where(Evaluation.id == evaluation_id, Evaluation.user_id == current_user.id)
    result = await session.exec(statement)
    evaluation = result.first()

    if not evaluation:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Evaluation not found")

    if evaluation.status == EvaluationStatus.RUNNING.value:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Evaluation is already running")

    # Clear previous results if re-running
    if evaluation.results:
        for r in evaluation.results:
            await session.delete(r)

    # Reset evaluation state
    evaluation.status = EvaluationStatus.PENDING.value
    evaluation.completed_items = 0
    evaluation.passed_items = 0
    evaluation.mean_score = None
    evaluation.mean_duration_ms = None
    evaluation.total_runtime_ms = None
    evaluation.error_message = None
    evaluation.started_at = None
    evaluation.completed_at = None
    evaluation.updated_at = datetime.now(timezone.utc)

    session.add(evaluation)
    await session.commit()

    # Start background task
    background_tasks.add_task(run_evaluation_background, evaluation_id, current_user.id)

    # Get names
    dataset_name = None
    flow_name = None
    ds_stmt = select(Dataset).where(Dataset.id == evaluation.dataset_id)
    ds_result = await session.exec(ds_stmt)
    ds = ds_result.first()
    if ds:
        dataset_name = ds.name

    fl_stmt = select(Flow).where(Flow.id == evaluation.flow_id)
    fl_result = await session.exec(fl_stmt)
    fl = fl_result.first()
    if fl:
        flow_name = fl.name

    return EvaluationRead(
        id=evaluation.id,
        name=evaluation.name,
        status=evaluation.status,
        scoring_methods=evaluation.scoring_methods,
        user_id=evaluation.user_id,
        dataset_id=evaluation.dataset_id,
        flow_id=evaluation.flow_id,
        dataset_name=dataset_name,
        flow_name=flow_name,
        created_at=evaluation.created_at,
        updated_at=evaluation.updated_at,
        total_items=evaluation.total_items,
    )


@router.delete("/{evaluation_id}", status_code=HTTPStatus.NO_CONTENT)
async def delete_evaluation(
    *,
    session: DbSession,
    evaluation_id: UUID,
    current_user: CurrentActiveUser,
) -> None:
    """Delete an evaluation and all its results."""
    statement = select(Evaluation).where(Evaluation.id == evaluation_id, Evaluation.user_id == current_user.id)
    result = await session.exec(statement)
    evaluation = result.first()

    if not evaluation:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Evaluation not found")

    await session.delete(evaluation)
    await session.commit()
