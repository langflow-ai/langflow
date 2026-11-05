"""Load the resources an evaluation touches, with the same owner/plugin rules as the rest of the API."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException

from langflow.services.authorization import DatasetAction, FlowAction, ensure_dataset_permission, ensure_flow_permission
from langflow.services.authorization.fetch import authorized_or_owner_scoped, deny_to_404
from langflow.services.database.models.evaluation import Dataset, Evaluation
from langflow.services.database.models.flow.model import Flow
from langflow.services.evaluations.errors import EvalsNotFoundError

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.user.model import User


async def load_eval_flow(session: AsyncSession, user: User, flow_id: UUID, action: FlowAction) -> Flow:
    flow = await authorized_or_owner_scoped(
        session, Flow, id_column=Flow.id, resource_id=flow_id, owner_column=Flow.user_id, owner_id=user.id
    )
    if flow is None:
        msg = "Flow not found"
        raise EvalsNotFoundError(msg)
    try:
        await ensure_flow_permission(
            user,
            action,
            flow_id=flow.id,
            flow_user_id=flow.user_id,
            folder_id=flow.folder_id,
            workspace_id=getattr(flow, "workspace_id", None),
        )
    except HTTPException as exc:
        raise deny_to_404(exc, "Flow not found") from exc
    return flow


async def load_eval_dataset(session: AsyncSession, user: User, dataset_id: UUID, action: DatasetAction) -> Dataset:
    dataset = await authorized_or_owner_scoped(
        session, Dataset, id_column=Dataset.id, resource_id=dataset_id, owner_column=Dataset.user_id, owner_id=user.id
    )
    if dataset is None:
        msg = "Dataset not found"
        raise EvalsNotFoundError(msg)
    try:
        await ensure_dataset_permission(user, action, dataset_id=dataset.id, dataset_user_id=dataset.user_id)
    except HTTPException as exc:
        raise deny_to_404(exc, "Dataset not found") from exc
    return dataset


async def ensure_dataset_create(user: User) -> None:
    await ensure_dataset_permission(user, DatasetAction.CREATE)


async def load_evaluation(session: AsyncSession, user: User, evaluation_id: UUID) -> Evaluation:
    """Evaluations are owner-scoped; access to run one is re-checked on the flow at every run start."""
    evaluation = await authorized_or_owner_scoped(
        session,
        Evaluation,
        id_column=Evaluation.id,
        resource_id=evaluation_id,
        owner_column=Evaluation.user_id,
        owner_id=user.id,
    )
    if evaluation is None or (evaluation.user_id != user.id and not user.is_superuser):
        msg = "Evaluation not found"
        raise EvalsNotFoundError(msg)
    return evaluation
