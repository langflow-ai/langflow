"""Dataset and dataset-item persistence, always scoped to the owning user."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Text, cast, delete, func, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select

from langflow.services.database.models.evaluation import Dataset, DatasetItem
from langflow.services.evaluations.errors import EvalsConflictError, EvalsNotFoundError
from langflow.services.evaluations.schemas import DatasetItemRead, DatasetRead

if TYPE_CHECKING:
    from collections.abc import Sequence
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.evaluations.csv_io import ParsedRow
    from langflow.services.evaluations.schemas import DatasetCreate, DatasetItemUpdate, DatasetItemWrite, DatasetUpdate

DUPLICATE_SUFFIX = " (copy)"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def item_text(payload: dict | None) -> str | None:
    if not isinstance(payload, dict):
        return None
    text = payload.get("text")
    return text if isinstance(text, str) else None


def to_item_read(item: DatasetItem) -> DatasetItemRead:
    return DatasetItemRead(
        id=item.id,
        position=item.position,
        input=item_text(item.input) or "",
        expected_output=item_text(item.expected_output),
        source=item.source,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def to_dataset_read(dataset: Dataset, item_count: int) -> DatasetRead:
    return DatasetRead(
        id=dataset.id,
        name=dataset.name,
        description=dataset.description,
        revision=dataset.revision,
        item_count=item_count,
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
    )


async def count_items(session: AsyncSession, dataset_id: UUID) -> int:
    stmt = select(func.count()).select_from(DatasetItem).where(DatasetItem.dataset_id == dataset_id)
    return int((await session.exec(stmt)).one())


async def list_datasets(
    session: AsyncSession, user_id: UUID, *, search: str | None, page: int, size: int
) -> tuple[list[DatasetRead], int]:
    where = [Dataset.user_id == user_id]
    if search:
        where.append(col(Dataset.name).icontains(search, autoescape=True))
    total = int((await session.exec(select(func.count()).select_from(Dataset).where(*where))).one())
    counts = (
        select(DatasetItem.dataset_id, func.count().label("item_count")).group_by(DatasetItem.dataset_id).subquery()
    )
    stmt = (
        select(Dataset, func.coalesce(counts.c.item_count, 0))
        .outerjoin(counts, counts.c.dataset_id == Dataset.id)
        .where(*where)
        .order_by(col(Dataset.updated_at).desc(), col(Dataset.id))
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = (await session.exec(stmt)).all()
    return [to_dataset_read(dataset, int(item_count)) for dataset, item_count in rows], total


async def _name_taken(session: AsyncSession, user_id: UUID, name: str, *, exclude_id: UUID | None = None) -> bool:
    stmt = select(Dataset.id).where(Dataset.user_id == user_id, Dataset.name == name)
    if exclude_id is not None:
        stmt = stmt.where(Dataset.id != exclude_id)
    return (await session.exec(stmt.limit(1))).first() is not None


async def _flush_or_conflict(session: AsyncSession, name: str) -> None:
    try:
        await session.flush()
    except IntegrityError as exc:
        msg = f"A dataset named {name!r} already exists"
        raise EvalsConflictError(msg) from exc


async def create_dataset(session: AsyncSession, user_id: UUID, payload: DatasetCreate) -> Dataset:
    if await _name_taken(session, user_id, payload.name):
        msg = f"A dataset named {payload.name!r} already exists"
        raise EvalsConflictError(msg)
    dataset = Dataset(user_id=user_id, name=payload.name, description=payload.description)
    session.add(dataset)
    await _flush_or_conflict(session, payload.name)
    return dataset


async def update_dataset(session: AsyncSession, dataset: Dataset, payload: DatasetUpdate) -> Dataset:
    if payload.name is not None and payload.name != dataset.name:
        if await _name_taken(session, dataset.user_id, payload.name, exclude_id=dataset.id):
            msg = f"A dataset named {payload.name!r} already exists"
            raise EvalsConflictError(msg)
        dataset.name = payload.name
    if "description" in payload.model_fields_set:
        dataset.description = payload.description
    dataset.updated_at = _now()
    session.add(dataset)
    await _flush_or_conflict(session, dataset.name)
    return dataset


async def ensure_idle(session: AsyncSession, dataset_id: UUID) -> None:
    """Refuse item changes while a run reads this dataset: rows are matched to items by position."""
    from langflow.services.database.models.evaluation import EvaluationRun
    from langflow.services.evaluations.run_reconcile import active_runs

    if await active_runs(session, EvaluationRun.dataset_id == dataset_id):
        msg = "An evaluation run is using this dataset. Wait for it to finish or cancel it, then try again."
        raise EvalsConflictError(msg)


async def delete_dataset(session: AsyncSession, dataset: Dataset) -> None:
    # Evaluations keep their history: the FK nulls dataset_id, and results hold their own copies.
    from langflow.services.database.models.evaluation import Evaluation

    await session.exec(update(Evaluation).where(Evaluation.dataset_id == dataset.id).values(dataset_id=None))
    await session.exec(delete(DatasetItem).where(DatasetItem.dataset_id == dataset.id))
    await session.delete(dataset)
    await session.flush()


async def _unique_copy_name(session: AsyncSession, user_id: UUID, name: str) -> str:
    base = f"{name}{DUPLICATE_SUFFIX}"
    candidate = base
    attempt = 2
    while await _name_taken(session, user_id, candidate):
        candidate = f"{base} {attempt}"
        attempt += 1
    return candidate


async def duplicate_dataset(session: AsyncSession, dataset: Dataset, owner_id: UUID) -> Dataset:
    """Copy ``dataset`` into ``owner_id``'s account (the caller, who may only have read access)."""
    copy = Dataset(
        user_id=owner_id,
        name=await _unique_copy_name(session, owner_id, dataset.name),
        description=dataset.description,
    )
    session.add(copy)
    await _flush_or_conflict(session, copy.name)
    items = (await session.exec(select(DatasetItem).where(DatasetItem.dataset_id == dataset.id))).all()
    now = _now()
    session.add_all(
        DatasetItem(
            dataset_id=copy.id,
            position=item.position,
            input=item.input,
            expected_output=item.expected_output,
            meta=item.meta,
            source=item.source,
            created_at=now,
            updated_at=now,
        )
        for item in items
    )
    await session.flush()
    return copy


async def list_items(
    session: AsyncSession, dataset_id: UUID, *, search: str | None, page: int, size: int
) -> tuple[list[DatasetItemRead], int]:
    where = [DatasetItem.dataset_id == dataset_id]
    stmt = select(DatasetItem).where(*where)
    total_stmt = select(func.count()).select_from(DatasetItem).where(*where)
    if search:
        # JSON columns are compared as text so the same filter works on SQLite and PostgreSQL.
        matches = cast(DatasetItem.input, Text).icontains(search, autoescape=True)
        stmt = stmt.where(matches)
        total_stmt = total_stmt.where(matches)
    total = int((await session.exec(total_stmt)).one())
    rows = (
        await session.exec(
            stmt.order_by(col(DatasetItem.position), col(DatasetItem.created_at)).offset((page - 1) * size).limit(size)
        )
    ).all()
    return [to_item_read(item) for item in rows], total


async def _next_position(session: AsyncSession, dataset_id: UUID) -> int:
    stmt = select(func.max(DatasetItem.position)).where(DatasetItem.dataset_id == dataset_id)
    current = (await session.exec(stmt)).one()
    return 0 if current is None else int(current) + 1


async def _touch(session: AsyncSession, dataset: Dataset) -> None:
    dataset.revision += 1
    dataset.updated_at = _now()
    session.add(dataset)


def _payload(text: str | None) -> dict | None:
    return None if text is None else {"text": text}


async def add_items(
    session: AsyncSession, dataset: Dataset, items: Sequence[DatasetItemWrite | ParsedRow], *, source: str
) -> list[DatasetItem]:
    position = await _next_position(session, dataset.id)
    now = _now()
    created = [
        DatasetItem(
            dataset_id=dataset.id,
            position=position + offset,
            input={"text": item.input},
            expected_output=_payload(item.expected_output),
            source=source,
            created_at=now,
            updated_at=now,
        )
        for offset, item in enumerate(items)
    ]
    session.add_all(created)
    await _touch(session, dataset)
    await session.flush()
    return created


async def update_item(
    session: AsyncSession, dataset: Dataset, item_id: UUID, payload: DatasetItemUpdate
) -> DatasetItem:
    item = (
        await session.exec(select(DatasetItem).where(DatasetItem.id == item_id, DatasetItem.dataset_id == dataset.id))
    ).first()
    if item is None:
        msg = "Dataset item not found"
        raise EvalsNotFoundError(msg)
    if payload.input is not None:
        item.input = {"text": payload.input}
    if payload.clear_expected_output:
        item.expected_output = None
    elif payload.expected_output is not None:
        item.expected_output = {"text": payload.expected_output}
    item.updated_at = _now()
    session.add(item)
    await _touch(session, dataset)
    await session.flush()
    return item


async def delete_items(session: AsyncSession, dataset: Dataset, item_ids: Sequence[UUID]) -> int:
    result = await session.exec(
        delete(DatasetItem).where(DatasetItem.dataset_id == dataset.id, col(DatasetItem.id).in_(list(item_ids)))
    )
    deleted = result.rowcount or 0
    if deleted:
        await _touch(session, dataset)
    await session.flush()
    return deleted


async def all_items(session: AsyncSession, dataset_id: UUID, *, limit: int | None = None) -> list[DatasetItem]:
    stmt = (
        select(DatasetItem)
        .where(DatasetItem.dataset_id == dataset_id)
        .order_by(col(DatasetItem.position), col(DatasetItem.created_at))
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    return list((await session.exec(stmt)).all())
