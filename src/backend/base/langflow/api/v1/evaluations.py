import asyncio
import logging
import re
import time
from datetime import datetime, timezone
from difflib import SequenceMatcher
from http import HTTPStatus
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from sqlmodel import col, select

from langflow.api.utils import CurrentActiveUser, DbSession

logger = logging.getLogger(__name__)
from langflow.processing.process import run_graph
from langflow.services.database.models.dataset.model import Dataset
from langflow.services.database.models.traces.model import TraceTable
from langflow.services.database.models.evaluation.model import (
    Evaluation,
    EvaluationCreate,
    EvaluationRead,
    EvaluationReadWithResults,
    EvaluationResult,
    EvaluationResultRead,
    EvaluationStatus,
    ScoringMethod,
)
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import session_scope
from lfx.base.models.unified_models import get_llm, normalize_model_names_to_dicts
from lfx.graph import Graph

router = APIRouter(prefix="/evaluations", tags=["Evaluations"])

# Default LLM Judge prompt template
LLM_JUDGE_TEMPLATE = """You are evaluating an AI assistant's response.

Input: {input}

Expected Output: {expected_output}
Actual Output: {actual_output}

{custom_prompt}"""


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

    return 0.0


def _extract_token_usage(response) -> int | None:
    """Extract total token count from an LLM response."""
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        usage = response.usage_metadata
        total = getattr(usage, "total_tokens", None) or (
            usage.get("total_tokens") if isinstance(usage, dict) else None
        )
        if total:
            return int(total)
    if hasattr(response, "response_metadata") and response.response_metadata:
        rm = response.response_metadata
        for key in ("token_usage", "usage"):
            if key in rm and isinstance(rm[key], dict):
                total = rm[key].get("total_tokens")
                if total:
                    return int(total)
    return None


async def run_llm_judge(
    input_value: str,
    expected_output: str,
    actual_output: str,
    custom_prompt: str,
    model_config: dict | None,
    user_id: UUID | str,
) -> tuple[float | None, str | None, int | None]:
    """Run the LLM Judge using the unified model provider and return a (score, error, tokens) tuple."""
    try:
        if not model_config:
            return None, "No model configuration provided for LLM Judge", None

        model_name = model_config.get("name")
        if not model_name:
            return None, "No model name in LLM Judge configuration", None

        # Build the prompt
        prompt = LLM_JUDGE_TEMPLATE.format(
            input=input_value,
            expected_output=expected_output,
            actual_output=actual_output or "(no output)",
            custom_prompt=custom_prompt,
        )

        # Use the model_config from the frontend directly — it already contains
        # full metadata (model_class, api_key_param, etc.) from the model picker.
        # Falling back to normalize_model_names_to_dicts only if metadata is missing,
        # since that function can fail in background tasks due to DB session issues.
        enriched_model = dict(model_config)
        if not enriched_model.get("metadata", {}).get("model_class"):
            enriched_models = normalize_model_names_to_dicts(model_name)
            if enriched_models and enriched_models[0].get("metadata", {}).get("model_class"):
                enriched_model = enriched_models[0]
                if model_config.get("provider"):
                    enriched_model["provider"] = model_config["provider"]
            else:
                return None, f"Could not find model class for {model_name}", None

        # Create LLM using unified model provider
        llm = get_llm(
            model=[enriched_model],
            user_id=user_id,
            temperature=0,
            stream=False,
        )

        response = await llm.ainvoke(prompt)
        output_text = response.content if hasattr(response, "content") else str(response)
        tokens = _extract_token_usage(response)

        # Parse score from output
        if output_text:
            # Try to find a decimal number
            match = re.search(r"(\d+\.?\d*)", output_text.strip())
            if match:
                score = float(match.group(1))
                # Clamp to 0-1 range
                return max(0.0, min(1.0, score)), None, tokens

        logger.warning(f"Could not parse LLM Judge output: {output_text}")
        return None, f"Could not parse score from LLM output: {output_text[:200]}", tokens

    except Exception as e:
        logger.exception(f"Error running LLM Judge: {e}")
        return None, f"LLM Judge error: {e}", None


async def run_single_evaluation_item(
    flow_data: dict,
    flow_id: UUID,
    flow_name: str,
    user_id: UUID,
    input_value: str,
    scoring_methods: list[str],
    expected_output: str,
    llm_judge_prompt: str | None = None,
    llm_judge_model: dict | None = None,
    session_id: str | None = None,
    pass_metric: str | None = None,
    pass_threshold: float = 0.5,
) -> dict:
    """Run a single evaluation item and return results."""
    start_time = time.time()
    actual_output = None
    error = None

    logger.info(f"Running evaluation item: input='{input_value[:50]}...' flow_id={flow_id}")

    try:
        if session_id is None:
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

        logger.info(f"Graph initialized, running with input: {input_value}")

        result = await run_graph(
            graph=graph,
            session_id=session_id,
            input_value=input_value,
            fallback_to_env_vars=True,
            input_type="chat",
            output_type="chat",
            stream=False,
        )

        logger.debug(f"Graph run complete. Result type: {type(result)}, length: {len(result) if result else 0}")

        # Extract output from result
        if result and len(result) > 0:
            run_output = result[0]
            logger.debug(
                f"RunOutput: inputs={run_output.inputs}, outputs_count={len(run_output.outputs) if run_output.outputs else 0}"
            )

            if run_output.outputs:
                for result_data in run_output.outputs:
                    if result_data is None:
                        continue

                    logger.debug(f"ResultData: messages={result_data.messages}, results={result_data.results}")

                    # Try to get from messages (ChatOutputResponse)
                    if result_data.messages:
                        for msg in result_data.messages:
                            if msg and msg.message:
                                if isinstance(msg.message, str):
                                    actual_output = msg.message
                                elif isinstance(msg.message, list):
                                    actual_output = " ".join(str(m) for m in msg.message)
                                else:
                                    actual_output = str(msg.message)
                                break
                        if actual_output:
                            break

                    # Fallback: try results dict
                    if not actual_output and result_data.results:
                        for key, value in result_data.results.items():
                            if hasattr(value, "text"):
                                actual_output = value.text
                                break
                            elif hasattr(value, "message"):
                                actual_output = str(value.message)
                                break
                            elif isinstance(value, str):
                                actual_output = value
                                break
                        if actual_output:
                            break

        logger.debug(f"Extracted actual_output: {actual_output[:100] if actual_output else None}")

    except Exception as e:
        logger.exception(f"Error running evaluation item: {e}")
        error = str(e)

    duration_ms = int((time.time() - start_time) * 1000)

    # Query flow token usage from the trace table
    flow_tokens = None
    try:
        async with session_scope() as trace_session:
            trace_stmt = select(TraceTable).where(TraceTable.session_id == session_id)
            trace_result = await trace_session.exec(trace_stmt)
            trace = trace_result.first()
            if trace and trace.total_tokens:
                flow_tokens = trace.total_tokens
    except Exception as e:
        logger.debug(f"Could not query flow tokens: {e}")

    # Calculate scores
    scores = {}
    llm_judge_tokens = None
    for method in scoring_methods:
        if method == ScoringMethod.LLM_JUDGE.value:
            # Run LLM Judge
            if llm_judge_prompt and llm_judge_model:
                score, llm_error, judge_tokens = await run_llm_judge(
                    input_value=input_value,
                    expected_output=expected_output,
                    actual_output=actual_output or "",
                    custom_prompt=llm_judge_prompt,
                    model_config=llm_judge_model,
                    user_id=user_id,
                )
                scores[method] = score
                llm_judge_tokens = judge_tokens
                if llm_error and not error:
                    error = llm_error
            else:
                scores[method] = None
                if not error:
                    error = "LLM Judge requires a prompt and model configuration"
        else:
            scores[method] = calculate_score(method, expected_output, actual_output or "")

    # Determine if passed based on configured criteria
    if pass_metric and pass_metric in scores and scores[pass_metric] is not None:
        passed = scores[pass_metric] >= pass_threshold
    else:
        valid_scores = [s for s in scores.values() if s is not None]
        avg_score = sum(valid_scores) / len(valid_scores) if valid_scores else 0.0
        passed = avg_score >= pass_threshold

    return {
        "actual_output": actual_output,
        "duration_ms": duration_ms,
        "scores": scores,
        "passed": passed,
        "error": error,
        "flow_tokens": flow_tokens,
        "llm_judge_tokens": llm_judge_tokens,
    }


async def run_evaluation_background(evaluation_id: UUID, user_id: UUID):
    """Background task to run the evaluation."""
    logger.info(f"Starting background evaluation task: evaluation_id={evaluation_id}, user_id={user_id}")
    try:
        async with session_scope() as session:
            # Get the evaluation
            statement = select(Evaluation).where(Evaluation.id == evaluation_id)
            result = await session.exec(statement)
            evaluation = result.first()

            if not evaluation:
                logger.warning(f"Evaluation {evaluation_id} not found")
                return

            logger.info(f"Found evaluation {evaluation_id}, updating status to running")

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

                logger.info(f"Running evaluation with {len(dataset.items) if dataset.items else 0} items")

                # Sort items by order
                sorted_items = sorted(dataset.items, key=lambda x: x.order) if dataset.items else []
                evaluation.total_items = len(sorted_items)
                session.add(evaluation)
                await session.commit()

                total_score = 0.0
                total_duration = 0
                passed_count = 0
                total_flow_tokens = 0
                total_llm_judge_tokens = 0

                if dataset.dataset_type == "multi_turn":
                    # Group items by conversation_id, preserving order
                    conversations: dict[str, list] = {}
                    for item in sorted_items:
                        conv_id = item.conversation_id or "default"
                        conversations.setdefault(conv_id, []).append(item)

                    item_index = 0
                    for conv_id, turns in conversations.items():
                        conv_session_id = str(uuid4())  # One session per conversation
                        for turn in turns:
                            logger.info(
                                f"Running item {item_index + 1}/{len(sorted_items)} "
                                f"(conv={conv_id}): {turn.input[:30]}..."
                            )
                            item_result = await run_single_evaluation_item(
                                flow_data=flow.data,
                                flow_id=flow.id,
                                flow_name=flow.name,
                                user_id=user_id,
                                input_value=turn.input,
                                scoring_methods=evaluation.scoring_methods,
                                expected_output=turn.expected_output,
                                llm_judge_prompt=evaluation.llm_judge_prompt,
                                llm_judge_model=evaluation.llm_judge_model,
                                session_id=conv_session_id,
                                pass_metric=evaluation.pass_metric,
                                pass_threshold=evaluation.pass_threshold,
                            )

                            logger.info(
                                f"Item {item_index + 1} result: "
                                f"actual_output={item_result['actual_output']}, error={item_result['error']}"
                            )

                            # Create result record with conversation_id
                            db_result = EvaluationResult(
                                evaluation_id=evaluation_id,
                                dataset_item_id=turn.id,
                                input=turn.input,
                                expected_output=turn.expected_output,
                                actual_output=item_result["actual_output"],
                                duration_ms=item_result["duration_ms"],
                                scores=item_result["scores"],
                                passed=item_result["passed"],
                                error=item_result["error"],
                                order=item_index,
                                conversation_id=turn.conversation_id,
                                flow_tokens=item_result["flow_tokens"],
                                llm_judge_tokens=item_result["llm_judge_tokens"],
                                created_at=datetime.now(timezone.utc),
                            )
                            session.add(db_result)

                            # Update metrics
                            if item_result["scores"]:
                                valid_scores = [s for s in item_result["scores"].values() if s is not None]
                                if valid_scores:
                                    avg_score = sum(valid_scores) / len(valid_scores)
                                    total_score += avg_score
                            if item_result["duration_ms"]:
                                total_duration += item_result["duration_ms"]
                            if item_result["passed"]:
                                passed_count += 1
                            if item_result["flow_tokens"]:
                                total_flow_tokens += item_result["flow_tokens"]
                            if item_result["llm_judge_tokens"]:
                                total_llm_judge_tokens += item_result["llm_judge_tokens"]

                            # Update progress
                            evaluation.completed_items = item_index + 1
                            session.add(evaluation)
                            await session.commit()
                            item_index += 1
                else:
                    # Single-turn: current behavior unchanged
                    for idx, item in enumerate(sorted_items):
                        logger.info(f"Running item {idx + 1}/{len(sorted_items)}: {item.input[:30]}...")
                        item_result = await run_single_evaluation_item(
                            flow_data=flow.data,
                            flow_id=flow.id,
                            flow_name=flow.name,
                            user_id=user_id,
                            input_value=item.input,
                            scoring_methods=evaluation.scoring_methods,
                            expected_output=item.expected_output,
                            llm_judge_prompt=evaluation.llm_judge_prompt,
                            llm_judge_model=evaluation.llm_judge_model,
                            pass_metric=evaluation.pass_metric,
                            pass_threshold=evaluation.pass_threshold,
                        )

                        logger.info(
                            f"Item {idx + 1} result: actual_output={item_result['actual_output']}, error={item_result['error']}"
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
                            flow_tokens=item_result["flow_tokens"],
                            llm_judge_tokens=item_result["llm_judge_tokens"],
                            created_at=datetime.now(timezone.utc),
                        )
                        session.add(db_result)

                        # Update metrics
                        if item_result["scores"]:
                            valid_scores = [s for s in item_result["scores"].values() if s is not None]
                            if valid_scores:
                                avg_score = sum(valid_scores) / len(valid_scores)
                                total_score += avg_score
                        if item_result["duration_ms"]:
                            total_duration += item_result["duration_ms"]
                        if item_result["passed"]:
                            passed_count += 1
                        if item_result["flow_tokens"]:
                            total_flow_tokens += item_result["flow_tokens"]
                        if item_result["llm_judge_tokens"]:
                            total_llm_judge_tokens += item_result["llm_judge_tokens"]

                        # Update progress
                        evaluation.completed_items = idx + 1
                        session.add(evaluation)
                        await session.commit()

                # Update final metrics
                logger.info(f"Evaluation complete. Passed: {passed_count}/{len(sorted_items)}")
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
                evaluation.total_flow_tokens = total_flow_tokens or None
                evaluation.total_llm_judge_tokens = total_llm_judge_tokens or None
                session.add(evaluation)
                await session.commit()

            except Exception as e:
                logger.exception(f"Error running evaluation: {e}")
                evaluation.status = EvaluationStatus.FAILED.value
                evaluation.error_message = str(e)
                evaluation.updated_at = datetime.now(timezone.utc)
                session.add(evaluation)
                await session.commit()
    except Exception as e:
        logger.exception(f"Fatal error in background evaluation task: {e}")


@router.post("/", response_model=EvaluationRead, status_code=HTTPStatus.CREATED)
async def create_evaluation(
    *,
    session: DbSession,
    evaluation: EvaluationCreate,
    current_user: CurrentActiveUser,
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
        llm_judge_prompt=evaluation.llm_judge_prompt,
        llm_judge_model=evaluation.llm_judge_model,
        pass_metric=evaluation.pass_metric,
        pass_threshold=evaluation.pass_threshold,
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
        # Use asyncio.create_task to properly schedule the async background task
        asyncio.create_task(run_evaluation_background(db_evaluation.id, current_user.id))

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
        pass_metric=db_evaluation.pass_metric,
        pass_threshold=db_evaluation.pass_threshold,
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
                total_flow_tokens=ev.total_flow_tokens,
                total_llm_judge_tokens=ev.total_llm_judge_tokens,
                pass_metric=ev.pass_metric,
                pass_threshold=ev.pass_threshold,
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
        total_flow_tokens=evaluation.total_flow_tokens,
        total_llm_judge_tokens=evaluation.total_llm_judge_tokens,
        pass_metric=evaluation.pass_metric,
        pass_threshold=evaluation.pass_threshold,
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
                conversation_id=r.conversation_id,
                created_at=r.created_at,
                flow_tokens=r.flow_tokens,
                llm_judge_tokens=r.llm_judge_tokens,
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

    # Use asyncio.create_task to properly schedule the async background task
    asyncio.create_task(run_evaluation_background(evaluation_id, current_user.id))

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
        pass_metric=evaluation.pass_metric,
        pass_threshold=evaluation.pass_threshold,
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
