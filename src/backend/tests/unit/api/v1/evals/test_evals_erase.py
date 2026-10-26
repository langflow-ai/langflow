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
