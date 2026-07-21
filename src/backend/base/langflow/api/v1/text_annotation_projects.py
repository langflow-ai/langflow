"""Text annotation projects: project CRUD, task import, annotation storage, BERT export.

Data layout mirrors a simplified Label Studio (same shape as the image-annotation
feature):

* project — task type (``ner`` | ``classification``) + label sets stored as JSON
  (``[{"value": ..., "background": ...}]``)
* task    — raw text + LS-compatible ``result`` JSON in the DB
  (``labels`` span regions with character offsets for NER, ``choices`` regions
  for text classification)

Import sources: pasted text, plain-text files, CSV upload, or a SQL database
connection (SQLAlchemy URI + table/column config). Exports target BERT training:

* ``json``  — Label-Studio-compatible task list (round-trip)
* ``csv``   — classification: ``text,label``; NER: one row per span
* ``conll`` — NER only: BIO-tagged token lines (char-level for CJK text,
  word-level otherwise), blank line between samples
"""

import csv
import io
import re
from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlmodel import select
from starlette.concurrency import run_in_threadpool

from langflow.api.utils import CurrentActiveUser, DbSession, build_content_disposition
from langflow.services.authorization import (
    AnnotationProjectAction,
    ensure_annotation_project_permission,
    filter_visible_resources,
)
from langflow.services.authorization.fetch import authorized_or_owner_scoped, deny_to_404
from langflow.services.authorization.utils import _resolve_authz_domain
from langflow.services.database.models.text_annotation.model import (
    IMPORT_ROW_LIMIT,
    TASK_TYPE_CLASSIFICATION,
    DatabaseImportPreviewRequest,
    DatabaseImportPreviewResponse,
    DatabaseImportRequest,
    TextAnnotationImportResponse,
    TextAnnotationProject,
    TextAnnotationProjectCreate,
    TextAnnotationProjectDetail,
    TextAnnotationProjectRead,
    TextAnnotationProjectUpdate,
    TextAnnotationResultRead,
    TextAnnotationResultUpdate,
    TextAnnotationTask,
    TextAnnotationTaskRead,
    TextAnnotationTasksBulkCreate,
    TextAnnotationTaskUpdate,
    TextChoicesValue,
    TextSpanValue,
)
from langflow.services.deps import get_settings_service

router = APIRouter(prefix="/text-annotation-projects", tags=["Text Annotation Projects"])

_NOT_FOUND_DETAIL = "Text annotation project not found"
_TASK_NOT_FOUND_DETAIL = "Text annotation task not found"

EXPORT_FORMATS = {"json", "csv", "conll"}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


async def _get_project_or_404(
    session: DbSession,
    project_id: UUID,
    current_user: CurrentActiveUser,
) -> TextAnnotationProject:
    project = await authorized_or_owner_scoped(
        session,
        TextAnnotationProject,
        id_column=TextAnnotationProject.id,
        resource_id=project_id,
        owner_column=TextAnnotationProject.user_id,
        owner_id=current_user.id,
    )
    if not project:
        raise HTTPException(status_code=404, detail=_NOT_FOUND_DETAIL)
    return project


async def _ensure_project_permission(
    current_user: CurrentActiveUser,
    act: AnnotationProjectAction,
    project: TextAnnotationProject,
) -> None:
    try:
        await ensure_annotation_project_permission(
            current_user,
            act,
            annotation_project_id=project.id,
            annotation_project_user_id=project.user_id,
        )
    except HTTPException as exc:
        raise deny_to_404(exc, detail=_NOT_FOUND_DETAIL) from exc


async def _get_task_or_404(
    session: DbSession,
    *,
    project_id: UUID,
    task_id: UUID,
) -> TextAnnotationTask:
    stmt = select(TextAnnotationTask).where(
        TextAnnotationTask.id == task_id,
        TextAnnotationTask.project_id == project_id,
    )
    task = (await session.exec(stmt)).first()
    if not task:
        raise HTTPException(status_code=404, detail=_TASK_NOT_FOUND_DETAIL)
    return task


def _to_project_read(
    project: TextAnnotationProject,
    *,
    task_count: int = 0,
    labeled_count: int = 0,
) -> TextAnnotationProjectRead:
    read = TextAnnotationProjectRead.model_validate(project, from_attributes=True)
    read.task_count = task_count
    read.labeled_count = labeled_count
    return read


def _to_task_read(task: TextAnnotationTask) -> TextAnnotationTaskRead:
    read = TextAnnotationTaskRead.model_validate(task, from_attributes=True)
    read.is_labeled = bool(task.result)
    return read


def _allowed_labels(project: TextAnnotationProject) -> set[str]:
    if project.task_type == TASK_TYPE_CLASSIFICATION:
        return {label.get("value") for label in project.category_labels or []}
    return {label.get("value") for label in project.entity_labels or []}


async def _insert_tasks(
    session: DbSession,
    *,
    project: TextAnnotationProject,
    current_user: CurrentActiveUser,
    rows: list[tuple[str, str]],
    source: str,
) -> TextAnnotationImportResponse:
    """Insert ``(text, name)`` rows as tasks; returns created/skipped counts."""
    created = 0
    skipped = 0
    for text, name in rows:
        if not text or not text.strip():
            skipped += 1
            continue
        session.add(
            TextAnnotationTask(
                project_id=project.id,
                user_id=current_user.id,
                name=name or f"text-{created + 1}",
                text=text,
                source=source,
            )
        )
        created += 1
    if created:
        await session.flush()
    return TextAnnotationImportResponse(created=created, skipped=skipped)


# --------------------------------------------------------------------------- #
# Project CRUD
# --------------------------------------------------------------------------- #


@router.post("/", response_model=TextAnnotationProjectRead, status_code=201)
async def create_text_annotation_project(
    *,
    session: DbSession,
    project: TextAnnotationProjectCreate,
    current_user: CurrentActiveUser,
):
    await ensure_annotation_project_permission(current_user, AnnotationProjectAction.CREATE)
    try:
        new_project = TextAnnotationProject(
            name=project.name,
            description=project.description,
            task_type=project.task_type,
            entity_labels=[label.model_dump(mode="json") for label in project.entity_labels],
            category_labels=[label.model_dump(mode="json") for label in project.category_labels],
            user_id=current_user.id,
        )
        session.add(new_project)
        await session.flush()
        await session.refresh(new_project)
        return _to_project_read(new_project)
    except HTTPException:
        raise
    except Exception as e:
        if "uq_text_annotation_project_user_name" in str(e) or "UNIQUE constraint failed" in str(e):
            raise HTTPException(status_code=400, detail="A project with this name already exists") from e
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/", response_model=list[TextAnnotationProjectRead], status_code=200)
async def read_text_annotation_projects(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    try:
        projects = list(
            (
                await session.exec(
                    select(TextAnnotationProject)
                    .where(TextAnnotationProject.user_id == current_user.id)
                    .order_by(TextAnnotationProject.updated_at.desc())  # type: ignore[attr-defined]
                )
            ).all()
        )
        projects = await filter_visible_resources(
            current_user,
            resource_type="annotation_project",
            candidates=projects,
            domain_extractor=lambda _project: _resolve_authz_domain(None, None),
            owner_extractor=lambda project: project.user_id,
            act=AnnotationProjectAction.READ,
        )
        tasks = (
            await session.exec(
                select(TextAnnotationTask.project_id, TextAnnotationTask.result).where(
                    TextAnnotationTask.user_id == current_user.id
                )
            )
        ).all()
        task_counts: dict[UUID, int] = {}
        labeled_counts: dict[UUID, int] = {}
        for task_project_id, result in tasks:
            task_counts[task_project_id] = task_counts.get(task_project_id, 0) + 1
            if result:
                labeled_counts[task_project_id] = labeled_counts.get(task_project_id, 0) + 1
        return [
            _to_project_read(
                project,
                task_count=task_counts.get(project.id, 0),
                labeled_count=labeled_counts.get(project.id, 0),
            )
            for project in projects
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{project_id}", response_model=TextAnnotationProjectDetail, status_code=200)
async def read_text_annotation_project(
    *,
    session: DbSession,
    project_id: UUID,
    current_user: CurrentActiveUser,
):
    project = await _get_project_or_404(session, project_id, current_user)
    await _ensure_project_permission(current_user, AnnotationProjectAction.READ, project)
    try:
        tasks = list(
            (
                await session.exec(
                    select(TextAnnotationTask)
                    .where(TextAnnotationTask.project_id == project_id)
                    .order_by(TextAnnotationTask.created_at)  # type: ignore[attr-defined]
                )
            ).all()
        )
        detail = TextAnnotationProjectDetail.model_validate(project, from_attributes=True)
        detail.task_count = len(tasks)
        detail.labeled_count = sum(1 for task in tasks if task.result)
        detail.tasks = [_to_task_read(task) for task in tasks]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    else:
        return detail


@router.patch("/{project_id}", response_model=TextAnnotationProjectRead, status_code=200)
async def update_text_annotation_project(
    *,
    session: DbSession,
    project_id: UUID,
    project: TextAnnotationProjectUpdate,
    current_user: CurrentActiveUser,
):
    existing_project = await _get_project_or_404(session, project_id, current_user)
    await _ensure_project_permission(current_user, AnnotationProjectAction.WRITE, existing_project)
    try:
        if project.name is not None:
            existing_project.name = project.name
        if project.description is not None:
            existing_project.description = project.description
        if project.task_type is not None:
            existing_project.task_type = project.task_type
        if project.entity_labels is not None:
            existing_project.entity_labels = [label.model_dump(mode="json") for label in project.entity_labels]
        if project.category_labels is not None:
            existing_project.category_labels = [label.model_dump(mode="json") for label in project.category_labels]
        existing_project.updated_at = datetime.now(timezone.utc)
        session.add(existing_project)
        await session.flush()
        await session.refresh(existing_project)
        return _to_project_read(existing_project)
    except HTTPException:
        raise
    except Exception as e:
        if "uq_text_annotation_project_user_name" in str(e) or "UNIQUE constraint failed" in str(e):
            raise HTTPException(status_code=400, detail="A project with this name already exists") from e
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/{project_id}", status_code=204)
async def delete_text_annotation_project(
    *,
    session: DbSession,
    project_id: UUID,
    current_user: CurrentActiveUser,
):
    project = await _get_project_or_404(session, project_id, current_user)
    await _ensure_project_permission(current_user, AnnotationProjectAction.DELETE, project)
    try:
        tasks = list(
            (await session.exec(select(TextAnnotationTask).where(TextAnnotationTask.project_id == project_id))).all()
        )
        for task in tasks:
            await session.delete(task)
        await session.delete(project)
        # Flush eagerly so constraint errors surface in-request rather than at teardown commit.
        await session.flush()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# --------------------------------------------------------------------------- #
# Tasks: add / rename / delete
# --------------------------------------------------------------------------- #


@router.post("/{project_id}/tasks", response_model=list[TextAnnotationTaskRead], status_code=201)
async def create_text_annotation_tasks(
    *,
    session: DbSession,
    project_id: UUID,
    payload: TextAnnotationTasksBulkCreate,
    current_user: CurrentActiveUser,
):
    project = await _get_project_or_404(session, project_id, current_user)
    await _ensure_project_permission(current_user, AnnotationProjectAction.WRITE, project)
    if len(payload.tasks) > IMPORT_ROW_LIMIT:
        raise HTTPException(status_code=400, detail=f"Too many tasks. Maximum {IMPORT_ROW_LIMIT} per request.")
    created: list[TextAnnotationTask] = []
    try:
        existing_count = len(
            (await session.exec(select(TextAnnotationTask.id).where(TextAnnotationTask.project_id == project_id))).all()
        )
        next_index = existing_count + 1
        for item in payload.tasks:
            task = TextAnnotationTask(
                project_id=project_id,
                user_id=current_user.id,
                name=item.name or f"text-{next_index}",
                text=item.text,
                source=payload.source or "paste",
            )
            next_index += 1
            session.add(task)
            created.append(task)
        await session.flush()
        for task in created:
            await session.refresh(task)
        return [_to_task_read(task) for task in created]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.patch("/{project_id}/tasks/{task_id}", response_model=TextAnnotationTaskRead, status_code=200)
async def update_text_annotation_task(
    *,
    session: DbSession,
    project_id: UUID,
    task_id: UUID,
    task: TextAnnotationTaskUpdate,
    current_user: CurrentActiveUser,
):
    project = await _get_project_or_404(session, project_id, current_user)
    await _ensure_project_permission(current_user, AnnotationProjectAction.WRITE, project)
    existing_task = await _get_task_or_404(session, project_id=project_id, task_id=task_id)
    try:
        if task.name is not None:
            existing_task.name = task.name
        if task.text is not None:
            if not task.text.strip():
                raise HTTPException(status_code=400, detail="Task text must not be empty")
            existing_task.text = task.text
        existing_task.updated_at = datetime.now(timezone.utc)
        session.add(existing_task)
        await session.flush()
        await session.refresh(existing_task)
        return _to_task_read(existing_task)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/{project_id}/tasks/{task_id}", status_code=204)
async def delete_text_annotation_task(
    *,
    session: DbSession,
    project_id: UUID,
    task_id: UUID,
    current_user: CurrentActiveUser,
):
    project = await _get_project_or_404(session, project_id, current_user)
    await _ensure_project_permission(current_user, AnnotationProjectAction.DELETE, project)
    task = await _get_task_or_404(session, project_id=project_id, task_id=task_id)
    try:
        await session.delete(task)
        await session.flush()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# --------------------------------------------------------------------------- #
# Annotations (Label-Studio-compatible result JSON)
# --------------------------------------------------------------------------- #


@router.get("/{project_id}/tasks/{task_id}/annotations", response_model=TextAnnotationResultRead, status_code=200)
async def read_task_annotations(
    *,
    session: DbSession,
    project_id: UUID,
    task_id: UUID,
    current_user: CurrentActiveUser,
):
    project = await _get_project_or_404(session, project_id, current_user)
    await _ensure_project_permission(current_user, AnnotationProjectAction.READ, project)
    task = await _get_task_or_404(session, project_id=project_id, task_id=task_id)
    return TextAnnotationResultRead(result=task.result or [], updated_at=task.updated_at)


@router.put("/{project_id}/tasks/{task_id}/annotations", response_model=TextAnnotationResultRead, status_code=200)
async def save_task_annotations(
    *,
    session: DbSession,
    project_id: UUID,
    task_id: UUID,
    annotations: TextAnnotationResultUpdate,
    current_user: CurrentActiveUser,
):
    project = await _get_project_or_404(session, project_id, current_user)
    await _ensure_project_permission(current_user, AnnotationProjectAction.WRITE, project)
    task = await _get_task_or_404(session, project_id=project_id, task_id=task_id)

    allowed_labels = _allowed_labels(project)
    expected_type = "choices" if project.task_type == TASK_TYPE_CLASSIFICATION else "labels"
    for region in annotations.result:
        if region.type != expected_type:
            raise HTTPException(
                status_code=400,
                detail=f"Region type '{region.type}' does not match this project's task type "
                f"('{project.task_type}' expects '{expected_type}')",
            )
        if isinstance(region.value, TextSpanValue):
            if region.value.start >= region.value.end:
                raise HTTPException(status_code=400, detail="Span start must be smaller than span end")
            if region.value.end > len(task.text):
                raise HTTPException(status_code=400, detail="Span offsets exceed the task text length")
            for label_value in region.value.labels:
                if label_value not in allowed_labels:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Label '{label_value}' is not part of this project's label set",
                    )
        elif isinstance(region.value, TextChoicesValue):
            for choice in region.value.choices:
                if choice not in allowed_labels:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Choice '{choice}' is not part of this project's category label set",
                    )

    try:
        task.result = [region.model_dump(mode="json") for region in annotations.result]
        task.updated_at = datetime.now(timezone.utc)
        session.add(task)
        await session.flush()
        await session.refresh(task)
        return TextAnnotationResultRead(result=task.result, updated_at=task.updated_at)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# --------------------------------------------------------------------------- #
# CSV import
# --------------------------------------------------------------------------- #


def _decode_csv_bytes(content: bytes) -> str:
    """Decode CSV bytes: UTF-8 (with BOM) first, GB18030 fallback for Chinese exports."""
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise HTTPException(status_code=400, detail="Unsupported file encoding. Please use UTF-8 or GBK encoded CSV.")


@router.post("/{project_id}/import/csv", response_model=TextAnnotationImportResponse, status_code=201)
async def import_tasks_from_csv(
    *,
    session: DbSession,
    project_id: UUID,
    current_user: CurrentActiveUser,
    file: Annotated[UploadFile, File()],
    text_column: Annotated[str | None, Form()] = None,
    name_column: Annotated[str | None, Form()] = None,
    has_header: Annotated[bool, Form()] = True,
):
    """Import tasks from a CSV file.

    ``text_column`` is a header name (or a 0-based column index when
    ``has_header`` is false); defaults to the first column.
    """
    project = await _get_project_or_404(session, project_id, current_user)
    await _ensure_project_permission(current_user, AnnotationProjectAction.WRITE, project)

    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    max_file_size_upload = get_settings_service().settings.max_file_size_upload
    if file.size is not None and file.size > max_file_size_upload * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File size is larger than the maximum file size {max_file_size_upload}MB.",
        )

    content = await file.read()
    decoded = _decode_csv_bytes(content)
    try:
        dialect = csv.Sniffer().sniff(decoded[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(decoded), dialect)

    header: list[str] | None = None
    if has_header:
        try:
            header = next(reader)
        except StopIteration:
            raise HTTPException(status_code=400, detail="CSV file is empty") from None

    def _column_index(column: str | None, default: int) -> int:
        if column is None or column.strip() == "":
            return default
        column = column.strip()
        if header is not None:
            if column not in header:
                raise HTTPException(status_code=400, detail=f"Column '{column}' not found in CSV header {header}")
            return header.index(column)
        if not column.isdigit():
            raise HTTPException(status_code=400, detail="CSV has no header; please provide a 0-based column index")
        return int(column)

    text_idx = _column_index(text_column, 0)
    name_idx = _column_index(name_column, -1) if name_column else None

    rows: list[tuple[str, str]] = []
    skipped = 0
    for i, record in enumerate(reader):
        if len(rows) >= IMPORT_ROW_LIMIT:
            break
        if not record or all(not cell.strip() for cell in record):
            continue
        if text_idx >= len(record):
            skipped += 1
            continue
        text = record[text_idx]
        name = record[name_idx] if name_idx is not None and name_idx < len(record) else f"row-{i + 1}"
        rows.append((text, name))

    if not rows:
        raise HTTPException(status_code=400, detail="No valid text rows found in the CSV file")
    result = await _insert_tasks(session, project=project, current_user=current_user, rows=rows, source="csv")
    result.skipped += skipped
    return result


# --------------------------------------------------------------------------- #
# Database import
# --------------------------------------------------------------------------- #


def _fetch_table_sample(
    connection_uri: str,
    table_name: str,
    sample_size: int,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Blocking DB probe: column names + first rows (runs in a threadpool)."""
    engine = sa.create_engine(connection_uri)
    try:
        with engine.connect() as conn:
            inspector = sa.inspect(conn)
            columns = [col["name"] for col in inspector.get_columns(table_name)]
            if not columns:
                raise HTTPException(status_code=400, detail=f"Table '{table_name}' not found or has no columns")
            table = sa.table(table_name, *[sa.column(col) for col in columns])
            rows = conn.execute(sa.select(table).limit(sample_size)).mappings().all()
            return columns, [dict(row) for row in rows]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to connect or read table: {e}") from e
    finally:
        engine.dispose()


def _fetch_import_rows(
    request: DatabaseImportRequest,
) -> tuple[list[tuple[str, str]], int]:
    """Blocking DB fetch of ``(text, name)`` rows (runs in a threadpool).

    Returns the rows plus the count of rows skipped because the text column
    was NULL/empty.
    """
    engine = sa.create_engine(request.connection_uri)
    try:
        with engine.connect() as conn:
            inspector = sa.inspect(conn)
            columns = {col["name"] for col in inspector.get_columns(request.table_name)}
            if not columns:
                raise HTTPException(status_code=400, detail=f"Table '{request.table_name}' not found")
            if request.text_column not in columns:
                raise HTTPException(
                    status_code=400,
                    detail=f"Text column '{request.text_column}' not found. Available: {sorted(columns)}",
                )
            if request.name_column and request.name_column not in columns:
                raise HTTPException(
                    status_code=400,
                    detail=f"Name column '{request.name_column}' not found. Available: {sorted(columns)}",
                )
            selected = [request.text_column] + ([request.name_column] if request.name_column else [])
            table = sa.table(request.table_name, *[sa.column(col) for col in selected])
            stmt = sa.select(table).offset(request.offset).limit(request.limit)
            rows = conn.execute(stmt).all()
            result: list[tuple[str, str]] = []
            skipped = 0
            for i, row in enumerate(rows):
                text = row[0]
                if text is None or not str(text).strip():
                    skipped += 1
                    continue
                name = str(row[1]) if request.name_column and row[1] is not None else f"row-{request.offset + i + 1}"
                result.append((str(text), name))
            return result, skipped
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to import from database: {e}") from e
    finally:
        engine.dispose()


def _stringify_cell(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)


@router.post("/{project_id}/import/database/preview", response_model=DatabaseImportPreviewResponse, status_code=200)
async def preview_database_import(
    *,
    session: DbSession,
    project_id: UUID,
    payload: DatabaseImportPreviewRequest,
    current_user: CurrentActiveUser,
):
    """Test a database connection and return the table's columns + sample rows."""
    project = await _get_project_or_404(session, project_id, current_user)
    await _ensure_project_permission(current_user, AnnotationProjectAction.WRITE, project)
    columns, rows = await run_in_threadpool(
        _fetch_table_sample, payload.connection_uri, payload.table_name, payload.sample_size
    )
    return DatabaseImportPreviewResponse(
        columns=columns,
        rows=[{key: _stringify_cell(value) for key, value in row.items()} for row in rows],
    )


@router.post("/{project_id}/import/database", response_model=TextAnnotationImportResponse, status_code=201)
async def import_tasks_from_database(
    *,
    session: DbSession,
    project_id: UUID,
    payload: DatabaseImportRequest,
    current_user: CurrentActiveUser,
):
    """Import tasks from a SQL table (SQLAlchemy connection URI + column config)."""
    project = await _get_project_or_404(session, project_id, current_user)
    await _ensure_project_permission(current_user, AnnotationProjectAction.WRITE, project)
    rows, skipped = await run_in_threadpool(_fetch_import_rows, payload)
    if not rows:
        raise HTTPException(status_code=400, detail="No rows returned from the database query")
    result = await _insert_tasks(session, project=project, current_user=current_user, rows=rows, source="database")
    result.skipped += skipped
    return result


# --------------------------------------------------------------------------- #
# Export (BERT training formats)
# --------------------------------------------------------------------------- #

# CJK unified ideographs + common CJK punctuation/fullwidth forms.
_CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef\u3000-\u303f]")
_TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def _tokenize(text: str) -> list[tuple[int, int, str]]:
    """Return ``(start, end, token)`` triples.

    Character-level tokenization when the text contains CJK characters
    (standard practice for Chinese NER), regex word-level tokenization
    otherwise (CoNLL-style).
    """
    if _CJK_RE.search(text):
        return [(i, i + 1, ch) for i, ch in enumerate(text) if not ch.isspace()]
    return [(m.start(), m.end(), m.group()) for m in _TOKEN_RE.finditer(text)]


def _span_dicts(task: TextAnnotationTask) -> list[dict[str, Any]]:
    """Extract NER span dicts (start/end/labels) from an LS-style result."""
    spans = []
    for region in task.result or []:
        if region.get("type") != "labels":
            continue
        value = region.get("value") or {}
        labels = value.get("labels") or []
        if not labels:
            continue
        spans.append(
            {
                "start": int(value.get("start", 0)),
                "end": int(value.get("end", 0)),
                "text": value.get("text", ""),
                "labels": labels,
            }
        )
    return spans


def _choice_lists(task: TextAnnotationTask) -> list[str]:
    """Extract classification choices from an LS-style result."""
    choices: list[str] = []
    for region in task.result or []:
        if region.get("type") != "choices":
            continue
        value = region.get("value") or {}
        choices.extend(value.get("choices") or [])
    # Deduplicate while keeping order.
    return list(dict.fromkeys(choices))


def _export_json(tasks: list[TextAnnotationTask]) -> str:
    """Label-Studio-compatible export (round-trips through LS import)."""
    import json

    payload = [
        {
            "id": str(task.id),
            "data": {"text": task.text},
            "annotations": [
                {
                    "id": str(task.id),
                    "completed_by": str(task.user_id),
                    "result": task.result or [],
                    "created_at": task.created_at.isoformat(),
                    "updated_at": task.updated_at.isoformat(),
                }
            ]
            if task.result
            else [],
            "meta": {"name": task.name, "source": task.source},
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
        }
        for task in tasks
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _export_csv(project: TextAnnotationProject, tasks: list[TextAnnotationTask]) -> str:
    """BERT-friendly CSV.

    * classification: header ``text,label`` (multi-label joined with ``|``)
    * NER: header ``text,start,end,span_text,label`` — one row per span
    """
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    labeled = [task for task in tasks if task.result]
    if project.task_type == TASK_TYPE_CLASSIFICATION:
        writer.writerow(["text", "label"])
        for task in labeled:
            choices = _choice_lists(task)
            if choices:
                writer.writerow([task.text, "|".join(choices)])
    else:
        writer.writerow(["text", "start", "end", "span_text", "label"])
        for task in labeled:
            for span in _span_dicts(task):
                for label in span["labels"]:
                    writer.writerow([task.text, span["start"], span["end"], span["text"], label])
    # BOM keeps Excel happy with CJK text.
    return "\ufeff" + output.getvalue()


def _export_conll(tasks: list[TextAnnotationTask]) -> str:
    """CoNLL-style BIO export for BERT NER fine-tuning.

    One ``token BIO-TAG`` pair per line, blank line between samples.
    Char-level tokens for CJK text, word-level otherwise. Spans that do not
    align with token boundaries are skipped for the misaligned tokens.
    """
    documents: list[str] = []
    for task in tasks:
        if not task.result:
            continue
        spans = sorted(_span_dicts(task), key=lambda s: (s["start"], -s["end"]))
        if not spans:
            continue
        lines = []
        for start, end, token in _tokenize(task.text):
            tag = "O"
            for span in spans:
                if span["start"] <= start and end <= span["end"]:
                    prefix = "B-" if start == span["start"] else "I-"
                    tag = prefix + span["labels"][0]
                    break
                if span["start"] > start:
                    break
            lines.append(f"{token} {tag}")
        if lines:
            documents.append("\n".join(lines))
    return "\n\n".join(documents) + ("\n" if documents else "")


@router.get("/{project_id}/export", status_code=200)
async def export_text_annotation_project(
    *,
    session: DbSession,
    project_id: UUID,
    current_user: CurrentActiveUser,
    export_format: Annotated[str, Query(alias="format")] = "json",
):
    project = await _get_project_or_404(session, project_id, current_user)
    await _ensure_project_permission(current_user, AnnotationProjectAction.READ, project)
    if export_format not in EXPORT_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported export format '{export_format}'. Allowed: {sorted(EXPORT_FORMATS)}",
        )
    if export_format == "conll" and project.task_type == TASK_TYPE_CLASSIFICATION:
        raise HTTPException(status_code=400, detail="CoNLL export is only available for NER projects")

    tasks = list(
        (
            await session.exec(
                select(TextAnnotationTask)
                .where(TextAnnotationTask.project_id == project_id)
                .order_by(TextAnnotationTask.created_at)  # type: ignore[attr-defined]
            )
        ).all()
    )

    if export_format == "json":
        content, extension, media_type = _export_json(tasks), "json", "application/json"
    elif export_format == "csv":
        content, extension, media_type = _export_csv(project, tasks), "csv", "text/csv"
    else:
        content, extension, media_type = _export_conll(tasks), "txt", "text/plain"

    safe_name = re.sub(r"[^\w.-]+", "_", project.name) or "export"
    filename = f"{safe_name}-{export_format}.{extension}"
    return Response(
        content=content,
        media_type=f"{media_type}; charset=utf-8",
        headers={"Content-Disposition": build_content_disposition(filename)},
    )
