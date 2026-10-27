from __future__ import annotations

import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.evals_errors import evals_http_errors, evals_write
from langflow.services.authorization import DatasetAction
from langflow.services.database.models.evaluation import DatasetItem
from langflow.services.deps import get_settings_service
from langflow.services.evaluations import csv_io, dataset_service
from langflow.services.evaluations.access import ensure_dataset_create, load_eval_dataset
from langflow.services.evaluations.schemas import (
    CsvImportResult,
    CsvPreview,
    DatasetCreate,
    DatasetItemPage,
    DatasetItemRead,
    DatasetItemsCreate,
    DatasetItemsDelete,
    DatasetItemUpdate,
    DatasetPage,
    DatasetRead,
    DatasetUpdate,
    SkippedRow,
)

router = APIRouter(prefix="/datasets", tags=["Evals"])

PageParam = Annotated[int, Query(ge=1)]
SizeParam = Annotated[int, Query(ge=1, le=200)]
# Tables that page on the client load a whole dataset or run (both capped at a few thousand rows).
LargeSizeParam = Annotated[int, Query(ge=1, le=5000)]
SearchParam = Annotated[str | None, Query(max_length=200)]


async def _read_upload(file: UploadFile) -> str:
    settings = get_settings_service().settings
    max_bytes = min(settings.evals_csv_max_bytes, settings.max_file_size_upload * 1024 * 1024)
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        detail = f"The file is larger than {max_bytes // (1024 * 1024)} MB."
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=detail)
    try:
        return csv_io.decode_upload(content)
    except csv_io.CsvFormatError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/", response_model=DatasetPage)
async def list_datasets(
    current_user: CurrentActiveUser,
    session: DbSession,
    search: SearchParam = None,
    page: PageParam = 1,
    size: SizeParam = 50,
) -> DatasetPage:
    items, total = await dataset_service.list_datasets(session, current_user.id, search=search, page=page, size=size)
    return DatasetPage(items=items, total=total, page=page, size=size)


@router.post("/", response_model=DatasetRead, status_code=status.HTTP_201_CREATED)
async def create_dataset(payload: DatasetCreate, current_user: CurrentActiveUser, session: DbSession) -> DatasetRead:
    async with evals_http_errors():
        await ensure_dataset_create(current_user)
        dataset = await dataset_service.create_dataset(session, current_user.id, payload)
    return dataset_service.to_dataset_read(dataset, 0)


@router.get("/{dataset_id}", response_model=DatasetRead)
async def get_dataset(dataset_id: UUID, current_user: CurrentActiveUser, session: DbSession) -> DatasetRead:
    async with evals_http_errors():
        dataset = await load_eval_dataset(session, current_user, dataset_id, DatasetAction.READ)
    return dataset_service.to_dataset_read(dataset, await dataset_service.count_items(session, dataset.id))


@router.patch("/{dataset_id}", response_model=DatasetRead)
async def update_dataset(
    dataset_id: UUID, payload: DatasetUpdate, current_user: CurrentActiveUser, session: DbSession
) -> DatasetRead:
    async with evals_http_errors():
        dataset = await load_eval_dataset(session, current_user, dataset_id, DatasetAction.WRITE)
        dataset = await dataset_service.update_dataset(session, dataset, payload)
    return dataset_service.to_dataset_read(dataset, await dataset_service.count_items(session, dataset.id))


@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataset(dataset_id: UUID, current_user: CurrentActiveUser, session: DbSession) -> None:
    async def operation() -> None:
        dataset = await load_eval_dataset(session, current_user, dataset_id, DatasetAction.DELETE)
        await dataset_service.ensure_idle(session, dataset.id)
        await dataset_service.delete_dataset(session, dataset)

    async with evals_http_errors():
        await evals_write(session, "delete_dataset", operation)


@router.post("/{dataset_id}/duplicate", response_model=DatasetRead, status_code=status.HTTP_201_CREATED)
async def duplicate_dataset(dataset_id: UUID, current_user: CurrentActiveUser, session: DbSession) -> DatasetRead:
    async with evals_http_errors():
        source = await load_eval_dataset(session, current_user, dataset_id, DatasetAction.READ)
        await ensure_dataset_create(current_user)
        copy = await dataset_service.duplicate_dataset(session, source, current_user.id)
    return dataset_service.to_dataset_read(copy, await dataset_service.count_items(session, copy.id))


@router.get("/{dataset_id}/items", response_model=DatasetItemPage)
async def list_dataset_items(
    dataset_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
    search: SearchParam = None,
    page: PageParam = 1,
    size: LargeSizeParam = 50,
) -> DatasetItemPage:
    async with evals_http_errors():
        dataset = await load_eval_dataset(session, current_user, dataset_id, DatasetAction.READ)
    items, total = await dataset_service.list_items(session, dataset.id, search=search, page=page, size=size)
    return DatasetItemPage(items=items, total=total, page=page, size=size)


@router.post("/{dataset_id}/items", response_model=list[DatasetItemRead], status_code=status.HTTP_201_CREATED)
async def add_dataset_items(
    dataset_id: UUID, payload: DatasetItemsCreate, current_user: CurrentActiveUser, session: DbSession
) -> list[DatasetItemRead]:
    async def operation() -> list[DatasetItem]:
        dataset = await load_eval_dataset(session, current_user, dataset_id, DatasetAction.WRITE)
        await dataset_service.ensure_idle(session, dataset.id)
        return await dataset_service.add_items(session, dataset, payload.items, source="manual")

    async with evals_http_errors():
        created = await evals_write(session, "add_dataset_items", operation)
    return [dataset_service.to_item_read(item) for item in created]


@router.patch("/{dataset_id}/items/{item_id}", response_model=DatasetItemRead)
async def update_dataset_item(
    dataset_id: UUID, item_id: UUID, payload: DatasetItemUpdate, current_user: CurrentActiveUser, session: DbSession
) -> DatasetItemRead:
    async def operation() -> DatasetItem:
        dataset = await load_eval_dataset(session, current_user, dataset_id, DatasetAction.WRITE)
        await dataset_service.ensure_idle(session, dataset.id)
        return await dataset_service.update_item(session, dataset, item_id, payload)

    async with evals_http_errors():
        item = await evals_write(session, "update_dataset_item", operation)
    return dataset_service.to_item_read(item)


@router.post("/{dataset_id}/items/delete", status_code=status.HTTP_200_OK)
async def delete_dataset_items(
    dataset_id: UUID, payload: DatasetItemsDelete, current_user: CurrentActiveUser, session: DbSession
) -> dict[str, int]:
    async def operation() -> int:
        dataset = await load_eval_dataset(session, current_user, dataset_id, DatasetAction.WRITE)
        await dataset_service.ensure_idle(session, dataset.id)
        return await dataset_service.delete_items(session, dataset, payload.ids)

    async with evals_http_errors():
        deleted = await evals_write(session, "delete_dataset_items", operation)
    return {"deleted": deleted}


@router.post("/{dataset_id}/import/preview", response_model=CsvPreview)
async def preview_csv_import(
    dataset_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
    file: Annotated[UploadFile, File()],
) -> CsvPreview:
    async with evals_http_errors():
        await load_eval_dataset(session, current_user, dataset_id, DatasetAction.WRITE)
    text = await _read_upload(file)
    try:
        headers, rows, total = await asyncio.to_thread(csv_io.preview, text)
    except csv_io.CsvFormatError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return CsvPreview(headers=headers, rows=rows, total_rows=total)


@router.post("/{dataset_id}/import", response_model=CsvImportResult)
async def import_csv(
    dataset_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
    file: Annotated[UploadFile, File()],
    input_column: Annotated[str, Form(min_length=1, max_length=255)],
    expected_column: Annotated[str | None, Form(max_length=255)] = None,
) -> CsvImportResult:
    async with evals_http_errors():
        dataset = await load_eval_dataset(session, current_user, dataset_id, DatasetAction.WRITE)
        await dataset_service.ensure_idle(session, dataset.id)
    text = await _read_upload(file)
    try:
        plan = await asyncio.to_thread(
            csv_io.plan_import,
            text,
            input_column=input_column,
            expected_column=expected_column or None,
            max_rows=get_settings_service().settings.evals_csv_max_rows,
        )
    except csv_io.CsvFormatError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    if plan.rows:

        async def operation() -> None:
            target = await load_eval_dataset(session, current_user, dataset.id, DatasetAction.WRITE)
            await dataset_service.ensure_idle(session, target.id)
            await dataset_service.add_items(session, target, plan.rows, source="csv")

        async with evals_http_errors():
            await evals_write(session, "import_dataset_items", operation)
    return CsvImportResult(
        imported=len(plan.rows), skipped=[SkippedRow(row=row, reason=reason) for row, reason in plan.skipped]
    )


@router.get("/{dataset_id}/export")
async def export_csv(dataset_id: UUID, current_user: CurrentActiveUser, session: DbSession) -> StreamingResponse:
    async with evals_http_errors():
        dataset = await load_eval_dataset(session, current_user, dataset_id, DatasetAction.READ)
    items = await dataset_service.all_items(session, dataset.id)
    rows = [(dataset_service.item_text(i.input) or "", dataset_service.item_text(i.expected_output)) for i in items]
    filename = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in dataset.name)[:80] or "dataset"
    return StreamingResponse(
        csv_io.export_rows(rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
    )
