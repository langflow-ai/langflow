"""Image annotation projects: project CRUD, image upload, annotation storage.

Data layout mirrors a simplified Label Studio:

* project  — label set stored as JSON (``[{"value": ..., "background": ...}]``)
* image    — binary in the storage service (flat per-user namespace, uuid
             prefix), metadata + LS-compatible ``result`` JSON in the DB

Region coordinates are percentages (0-100) of the natural image size, with
``original_width`` / ``original_height`` carried per region — identical to
Label Studio's RectangleLabels result, so data can round-trip to LS / COCO.
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from lfx.log.logger import logger
from sqlmodel import select

from langflow.api.utils import CurrentActiveUser, DbSession, build_content_disposition
from langflow.services.authorization import (
    AnnotationProjectAction,
    ensure_annotation_project_permission,
    filter_visible_resources,
)
from langflow.services.authorization.fetch import authorized_or_owner_scoped, deny_to_404
from langflow.services.authorization.utils import _resolve_authz_domain
from langflow.services.database.models.annotation.model import (
    AnnotationImage,
    AnnotationImageRead,
    AnnotationImageUpdate,
    AnnotationProject,
    AnnotationProjectCreate,
    AnnotationProjectDetail,
    AnnotationProjectRead,
    AnnotationProjectUpdate,
    AnnotationResultRead,
    AnnotationResultUpdate,
)
from langflow.services.deps import get_settings_service, get_storage_service
from langflow.services.storage.service import StorageService

router = APIRouter(prefix="/annotation-projects", tags=["Annotation Projects"])

ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
_MEDIA_TYPES_BY_EXTENSION = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
}
_NOT_FOUND_DETAIL = "Annotation project not found"
_IMAGE_NOT_FOUND_DETAIL = "Annotation image not found"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _sanitize_filename(filename: str) -> str:
    """Validate + normalize a multipart upload filename (mirrors v2 files rules)."""
    dangerous_chars = ["..", "/", "\\", "\x00", "\n", "\r"]
    if any(char in filename for char in dangerous_chars):
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid file name. Filename must not contain directory paths, '..' sequences, or control characters."
            ),
        )
    max_filename_bytes = 255
    if len(filename.encode("utf-8")) > max_filename_bytes:
        raise HTTPException(status_code=400, detail="File name is too long. Maximum 255 bytes allowed.")
    sanitized = Path(filename).name
    if not sanitized or sanitized in (".", ".."):
        raise HTTPException(status_code=400, detail="Invalid file name after sanitization")
    return sanitized


async def _get_project_or_404(
    session: DbSession,
    project_id: UUID,
    current_user: CurrentActiveUser,
) -> AnnotationProject:
    project = await authorized_or_owner_scoped(
        session,
        AnnotationProject,
        id_column=AnnotationProject.id,
        resource_id=project_id,
        owner_column=AnnotationProject.user_id,
        owner_id=current_user.id,
    )
    if not project:
        raise HTTPException(status_code=404, detail=_NOT_FOUND_DETAIL)
    return project


async def _ensure_project_permission(
    current_user: CurrentActiveUser,
    act: AnnotationProjectAction,
    project: AnnotationProject,
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


async def _get_image_or_404(
    session: DbSession,
    *,
    project_id: UUID,
    image_id: UUID,
) -> AnnotationImage:
    stmt = select(AnnotationImage).where(
        AnnotationImage.id == image_id,
        AnnotationImage.project_id == project_id,
    )
    image = (await session.exec(stmt)).first()
    if not image:
        raise HTTPException(status_code=404, detail=_IMAGE_NOT_FOUND_DETAIL)
    return image


def _to_project_read(
    project: AnnotationProject,
    *,
    image_count: int = 0,
    labeled_count: int = 0,
) -> AnnotationProjectRead:
    read = AnnotationProjectRead.model_validate(project, from_attributes=True)
    read.image_count = image_count
    read.labeled_count = labeled_count
    return read


def _to_image_read(image: AnnotationImage) -> AnnotationImageRead:
    read = AnnotationImageRead.model_validate(image, from_attributes=True)
    read.annotation_count = len(image.result or [])
    read.is_labeled = read.annotation_count > 0
    return read


async def _delete_image_from_storage(
    storage_service: StorageService,
    image: AnnotationImage,
) -> None:
    """Best-effort storage delete; permanent failures are tolerated (file already gone)."""
    file_name = Path(image.path).name
    try:
        await storage_service.delete_file(flow_id=str(image.user_id), file_name=file_name)
    except Exception as err:  # noqa: BLE001
        await logger.awarning(
            "Failed to delete annotation image %s from storage (continuing with DB delete): %s",
            file_name,
            err,
        )


# --------------------------------------------------------------------------- #
# Project CRUD
# --------------------------------------------------------------------------- #


@router.post("/", response_model=AnnotationProjectRead, status_code=201)
async def create_annotation_project(
    *,
    session: DbSession,
    project: AnnotationProjectCreate,
    current_user: CurrentActiveUser,
):
    await ensure_annotation_project_permission(current_user, AnnotationProjectAction.CREATE)
    try:
        new_project = AnnotationProject(
            name=project.name,
            description=project.description,
            labels=[label.model_dump(mode="json") for label in project.labels],
            user_id=current_user.id,
        )
        session.add(new_project)
        await session.flush()
        await session.refresh(new_project)
        return _to_project_read(new_project)
    except HTTPException:
        raise
    except Exception as e:
        if "uq_annotation_project_user_name" in str(e) or "UNIQUE constraint failed" in str(e):
            raise HTTPException(status_code=400, detail="A project with this name already exists") from e
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/", response_model=list[AnnotationProjectRead], status_code=200)
async def read_annotation_projects(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    try:
        projects = list(
            (
                await session.exec(
                    select(AnnotationProject)
                    .where(AnnotationProject.user_id == current_user.id)
                    .order_by(AnnotationProject.updated_at.desc())  # type: ignore[attr-defined]
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
        images = (
            await session.exec(
                select(AnnotationImage.project_id, AnnotationImage.result).where(
                    AnnotationImage.user_id == current_user.id
                )
            )
        ).all()
        image_counts: dict[UUID, int] = {}
        labeled_counts: dict[UUID, int] = {}
        for image_project_id, result in images:
            image_counts[image_project_id] = image_counts.get(image_project_id, 0) + 1
            if result:
                labeled_counts[image_project_id] = labeled_counts.get(image_project_id, 0) + 1
        return [
            _to_project_read(
                project,
                image_count=image_counts.get(project.id, 0),
                labeled_count=labeled_counts.get(project.id, 0),
            )
            for project in projects
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{project_id}", response_model=AnnotationProjectDetail, status_code=200)
async def read_annotation_project(
    *,
    session: DbSession,
    project_id: UUID,
    current_user: CurrentActiveUser,
):
    project = await _get_project_or_404(session, project_id, current_user)
    await _ensure_project_permission(current_user, AnnotationProjectAction.READ, project)
    try:
        images = list(
            (
                await session.exec(
                    select(AnnotationImage)
                    .where(AnnotationImage.project_id == project_id)
                    .order_by(AnnotationImage.created_at)  # type: ignore[attr-defined]
                )
            ).all()
        )
        detail = AnnotationProjectDetail.model_validate(project, from_attributes=True)
        detail.image_count = len(images)
        detail.labeled_count = sum(1 for image in images if image.result)
        detail.images = [_to_image_read(image) for image in images]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    else:
        return detail


@router.patch("/{project_id}", response_model=AnnotationProjectRead, status_code=200)
async def update_annotation_project(
    *,
    session: DbSession,
    project_id: UUID,
    project: AnnotationProjectUpdate,
    current_user: CurrentActiveUser,
):
    existing_project = await _get_project_or_404(session, project_id, current_user)
    await _ensure_project_permission(current_user, AnnotationProjectAction.WRITE, existing_project)
    try:
        if project.name is not None:
            existing_project.name = project.name
        if project.description is not None:
            existing_project.description = project.description
        if project.labels is not None:
            existing_project.labels = [label.model_dump(mode="json") for label in project.labels]
        existing_project.updated_at = datetime.now(timezone.utc)
        session.add(existing_project)
        await session.flush()
        await session.refresh(existing_project)
        return _to_project_read(existing_project)
    except HTTPException:
        raise
    except Exception as e:
        if "uq_annotation_project_user_name" in str(e) or "UNIQUE constraint failed" in str(e):
            raise HTTPException(status_code=400, detail="A project with this name already exists") from e
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/{project_id}", status_code=204)
async def delete_annotation_project(
    *,
    session: DbSession,
    project_id: UUID,
    current_user: CurrentActiveUser,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
):
    project = await _get_project_or_404(session, project_id, current_user)
    await _ensure_project_permission(current_user, AnnotationProjectAction.DELETE, project)
    try:
        images = list(
            (await session.exec(select(AnnotationImage).where(AnnotationImage.project_id == project_id))).all()
        )
        for image in images:
            await _delete_image_from_storage(storage_service, image)
            await session.delete(image)
        await session.delete(project)
        # Flush eagerly so constraint errors surface in-request rather than at teardown commit.
        await session.flush()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# --------------------------------------------------------------------------- #
# Image upload / metadata / delete / download
# --------------------------------------------------------------------------- #


@router.post("/{project_id}/images", response_model=list[AnnotationImageRead], status_code=201)
async def upload_annotation_images(
    *,
    session: DbSession,
    project_id: UUID,
    current_user: CurrentActiveUser,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
    files: Annotated[list[UploadFile], File()],
):
    project = await _get_project_or_404(session, project_id, current_user)
    await _ensure_project_permission(current_user, AnnotationProjectAction.WRITE, project)

    max_file_size_upload = get_settings_service().settings.max_file_size_upload
    created_images: list[AnnotationImage] = []

    for file in files:
        if not file or not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        safe_name = _sanitize_filename(file.filename)
        extension = Path(safe_name).suffix.lower()
        if extension not in ALLOWED_IMAGE_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported image type '{extension}'. Allowed: {sorted(ALLOWED_IMAGE_EXTENSIONS)}",
            )
        if file.size is not None and file.size > max_file_size_upload * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail=f"File size is larger than the maximum file size {max_file_size_upload}MB.",
            )

        # uuid-prefixed flat name keeps the per-user storage namespace collision-free.
        stored_file_name = f"{uuid.uuid4().hex}-{safe_name}"
        try:
            file_content = await file.read()
            await storage_service.save_file(
                flow_id=str(current_user.id),
                file_name=stored_file_name,
                data=file_content,
            )
            file_size = await storage_service.get_file_size(
                flow_id=str(current_user.id),
                file_name=stored_file_name,
            )
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except PermissionError as e:
            raise HTTPException(status_code=500, detail="Error accessing storage") from e
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error accessing file: {e}") from e

        new_image = AnnotationImage(
            project_id=project_id,
            user_id=current_user.id,
            name=safe_name,
            path=f"{current_user.id}/{stored_file_name}",
            size=file_size,
        )
        session.add(new_image)
        try:
            await session.flush()
            await session.refresh(new_image)
        except Exception as db_err:
            # DB insert failed — clean up the stored file to avoid orphans.
            try:
                await storage_service.delete_file(flow_id=str(current_user.id), file_name=stored_file_name)
            except OSError as cleanup_err:
                await logger.aerror(f"Failed to clean up uploaded file {stored_file_name}: {cleanup_err}")
            raise HTTPException(
                status_code=500, detail=f"Error inserting image metadata into database: {db_err}"
            ) from db_err
        created_images.append(new_image)

    return [_to_image_read(image) for image in created_images]


@router.patch("/{project_id}/images/{image_id}", response_model=AnnotationImageRead, status_code=200)
async def update_annotation_image(
    *,
    session: DbSession,
    project_id: UUID,
    image_id: UUID,
    image: AnnotationImageUpdate,
    current_user: CurrentActiveUser,
):
    project = await _get_project_or_404(session, project_id, current_user)
    await _ensure_project_permission(current_user, AnnotationProjectAction.WRITE, project)
    existing_image = await _get_image_or_404(session, project_id=project_id, image_id=image_id)
    try:
        if image.name is not None:
            existing_image.name = _sanitize_filename(image.name)
        if image.width is not None:
            existing_image.width = image.width
        if image.height is not None:
            existing_image.height = image.height
        existing_image.updated_at = datetime.now(timezone.utc)
        session.add(existing_image)
        await session.flush()
        await session.refresh(existing_image)
        return _to_image_read(existing_image)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/{project_id}/images/{image_id}", status_code=204)
async def delete_annotation_image(
    *,
    session: DbSession,
    project_id: UUID,
    image_id: UUID,
    current_user: CurrentActiveUser,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
):
    project = await _get_project_or_404(session, project_id, current_user)
    await _ensure_project_permission(current_user, AnnotationProjectAction.DELETE, project)
    image = await _get_image_or_404(session, project_id=project_id, image_id=image_id)
    try:
        await _delete_image_from_storage(storage_service, image)
        await session.delete(image)
        await session.flush()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{project_id}/images/{image_id}/file")
async def download_annotation_image(
    *,
    session: DbSession,
    project_id: UUID,
    image_id: UUID,
    current_user: CurrentActiveUser,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
):
    project = await _get_project_or_404(session, project_id, current_user)
    await _ensure_project_permission(current_user, AnnotationProjectAction.READ, project)
    image = await _get_image_or_404(session, project_id=project_id, image_id=image_id)

    file_name = Path(image.path).name
    owner_id = str(image.user_id)
    try:
        # Check existence before streaming (headers cannot change once streaming starts).
        await storage_service.get_file_size(flow_id=owner_id, file_name=file_name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"File not found: {e}") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error accessing file: {e}") from e

    file_stream = storage_service.get_file_stream(flow_id=owner_id, file_name=file_name)
    media_type = _MEDIA_TYPES_BY_EXTENSION.get(Path(image.name).suffix.lower(), "application/octet-stream")
    content_disposition = build_content_disposition(image.name)
    return StreamingResponse(
        file_stream,
        media_type=media_type,
        headers={"Content-Disposition": content_disposition},
    )


# --------------------------------------------------------------------------- #
# Annotations (Label-Studio-compatible result JSON)
# --------------------------------------------------------------------------- #


@router.get("/{project_id}/images/{image_id}/annotations", response_model=AnnotationResultRead, status_code=200)
async def read_image_annotations(
    *,
    session: DbSession,
    project_id: UUID,
    image_id: UUID,
    current_user: CurrentActiveUser,
):
    project = await _get_project_or_404(session, project_id, current_user)
    await _ensure_project_permission(current_user, AnnotationProjectAction.READ, project)
    image = await _get_image_or_404(session, project_id=project_id, image_id=image_id)
    return AnnotationResultRead(result=image.result or [], updated_at=image.updated_at)


@router.put("/{project_id}/images/{image_id}/annotations", response_model=AnnotationResultRead, status_code=200)
async def save_image_annotations(
    *,
    session: DbSession,
    project_id: UUID,
    image_id: UUID,
    annotations: AnnotationResultUpdate,
    current_user: CurrentActiveUser,
):
    project = await _get_project_or_404(session, project_id, current_user)
    await _ensure_project_permission(current_user, AnnotationProjectAction.WRITE, project)
    image = await _get_image_or_404(session, project_id=project_id, image_id=image_id)

    # Region labels must come from the project's label set.
    allowed_labels = {label.get("value") for label in project.labels or []}
    for region in annotations.result:
        for label_value in region.value.rectanglelabels:
            if label_value not in allowed_labels:
                raise HTTPException(
                    status_code=400,
                    detail=f"Label '{label_value}' is not part of this project's label set",
                )

    try:
        image.result = [region.model_dump(mode="json") for region in annotations.result]
        image.updated_at = datetime.now(timezone.utc)
        # Backfill natural dimensions from the regions when not yet known.
        if image.width is None or image.height is None:
            for region in annotations.result:
                if region.original_width and region.original_height:
                    image.width = region.original_width
                    image.height = region.original_height
                    break
        session.add(image)
        await session.flush()
        await session.refresh(image)
        return AnnotationResultRead(result=image.result, updated_at=image.updated_at)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
