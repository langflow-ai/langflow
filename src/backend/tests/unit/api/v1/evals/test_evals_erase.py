from uuid import uuid4

from langflow.services.data_subjects.context import EraseContext
from langflow.services.data_subjects.evaluation_steps import EVALUATION_STEPS
from langflow.services.database.models.evaluation import (
    Dataset,
    DatasetItem,
    Evaluation,
    EvaluationResult,
    EvaluationRun,
)
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.traces.model import SpanTable, TraceTable
from langflow.services.deps import session_scope
from sqlmodel import func, select

MODELS = (Dataset, DatasetItem, Evaluation, EvaluationRun, EvaluationResult)


async def _seed(user_id):
    async with session_scope() as session:
        dataset = Dataset(user_id=user_id, name=f"ds-{uuid4().hex[:6]}")
        session.add(dataset)
        await session.flush()
        session.add(DatasetItem(dataset_id=dataset.id, position=0, input={"text": "personal question"}))
        evaluation = Evaluation(user_id=user_id, dataset_id=dataset.id, name="e", scorers=[])
        session.add(evaluation)
        await session.flush()
        run = EvaluationRun(
            evaluation_id=evaluation.id, user_id=user_id, flow_name="f", dataset_name="d", dataset_revision=1
        )
        session.add(run)
        await session.flush()
        session.add(EvaluationResult(run_id=run.id, position=0, input={"text": "personal question"}))


async def _counts() -> dict[str, int]:
    async with session_scope() as session:
        return {
            str(model.__tablename__): int((await session.exec(select(func.count()).select_from(model))).one())
            for model in MODELS
        }


async def test_should_erase_only_the_subjects_evals_rows(client, active_user, user_two):  # noqa: ARG001
    await _seed(active_user.id)
    await _seed(user_two.id)
    before = await _counts()
    ctx = EraseContext(request_id=uuid4(), subject_user_id=user_two.id)
    async with session_scope() as session:
        for _, step in EVALUATION_STEPS:
            while await step(session, ctx):
                pass
    after = await _counts()
    assert all(after[name] == before[name] - 1 for name in after), (before, after)


async def _seed_shared_flow_traces(subject_id, flow_owner_id):
    """The subject evaluates a flow someone else owns, so the row's trace is filed under that owner's flow."""
    async with session_scope() as session:
        flow = Flow(user_id=flow_owner_id, name=f"shared-{uuid4().hex[:6]}", data={})
        session.add(flow)
        await session.flush()
        row_trace = TraceTable(flow_id=flow.id, name="evaluation row")
        owner_trace = TraceTable(flow_id=flow.id, name="owner's own run")
        session.add_all([row_trace, owner_trace])
        await session.flush()
        session.add_all(
            [SpanTable(trace_id=row_trace.id, name="row span"), SpanTable(trace_id=owner_trace.id, name="x")]
        )
        dataset = Dataset(user_id=subject_id, name=f"ds-{uuid4().hex[:6]}")
        session.add(dataset)
        await session.flush()
        evaluation = Evaluation(user_id=subject_id, dataset_id=dataset.id, flow_id=flow.id, name="e", scorers=[])
        session.add(evaluation)
        await session.flush()
        run = EvaluationRun(
            evaluation_id=evaluation.id, user_id=subject_id, flow_name="f", dataset_name="d", dataset_revision=1
        )
        session.add(run)
        await session.flush()
        session.add_all(
            [
                EvaluationResult(run_id=run.id, position=0, input={"text": "personal"}, trace_id=str(row_trace.id)),
                # A malformed id must not stall the step.
                EvaluationResult(run_id=run.id, position=1, input={"text": "personal"}, trace_id="not-a-uuid"),
            ]
        )
        await session.commit()
        return row_trace.id, owner_trace.id


async def test_should_erase_row_traces_filed_under_a_flow_someone_else_owns(client, active_user, user_two):  # noqa: ARG001
    row_trace_id, owner_trace_id = await _seed_shared_flow_traces(user_two.id, active_user.id)
    ctx = EraseContext(request_id=uuid4(), subject_user_id=user_two.id)

    async with session_scope() as session:
        for _, step in EVALUATION_STEPS:
            while await step(session, ctx):
                pass

    async with session_scope() as session:
        assert await session.get(TraceTable, row_trace_id) is None
        row_spans = (await session.exec(select(SpanTable).where(SpanTable.trace_id == row_trace_id))).all()
        assert row_spans == []
        assert await session.get(TraceTable, owner_trace_id) is not None
