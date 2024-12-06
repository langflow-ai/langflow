import hashlib
from datetime import datetime, timezone
from http import HTTPStatus
from io import BytesIO
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from langflow.api.utils import AsyncDbSession, CurrentActiveUser
from langflow.api.v1.schemas import UploadFileResponse
from langflow.graph.schema import ResultData, RunOutputs
from langflow.helpers.flow import get_flow_by_id_or_endpoint_name
from langflow.services.auth.utils import api_key_security
from langflow.services.database.models.flow import Flow
from langflow.services.database.models.flow.model import FlowRead
from langflow.services.database.models.user.model import UserRead
from langflow.services.deps import get_storage_service
from langflow.services.storage.service import StorageService
from langflow.services.storage.utils import build_content_type_from_extension

from .endpoints import RunResponse, SimplifiedAPIRequest, simplified_run_flow

router = APIRouter(tags=["Files"], prefix="/files")


# Create dep that gets the flow_id from the request
# then finds it in the database and returns it while
# using the current user as the owner
async def get_valid_flow_obj(
    flow: FlowRead | None,
    user: UserRead | None,
    session: AsyncDbSession,
) -> Flow:
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    flow_id_str = str(flow.id)
    # AttributeError: 'SelectOfScalar' object has no attribute 'first'
    flow = await session.get(Flow, flow_id_str)

    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")
    if flow.user_id != user.id:
        raise HTTPException(status_code=403, detail="You don't have access to this flow")

    return flow


async def get_flow_id(
    flow_id: UUID,
    current_user: CurrentActiveUser,
    session: AsyncDbSession,
) -> str:
    user = UserRead(id=current_user.id)
    flow = FlowRead(id=flow_id, user_id=current_user.id)
    flow_obj = await get_valid_flow_obj(flow=flow, user=user, session=session)
    return str(flow_obj.id)


@router.post("/upload/{flow_id_or_name}", status_code=HTTPStatus.CREATED)
async def upload_file(
    *,
    file: UploadFile,
    api_key_user: Annotated[UserRead | None, Depends(api_key_security)],
    flow: Annotated[FlowRead | None, Depends(get_flow_by_id_or_endpoint_name)],
    session: AsyncDbSession,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
) -> UploadFileResponse:
    """Handles file uploads to a specific flow."""
    try:
        flow_obj = await get_valid_flow_obj(flow=flow, user=api_key_user, session=session)
        flow_id_str = str(flow_obj.id)

        file_content = await file.read()

        timestamp = datetime.now(tz=timezone.utc).astimezone().strftime("%Y-%m-%d_%H-%M-%S")
        file_name = file.filename or hashlib.sha256(file_content).hexdigest()
        full_file_name = f"{timestamp}_{file_name}"
        folder = flow_id_str

        await storage_service.save_file(flow_id=folder, file_name=full_file_name, data=file_content)

        file_path = storage_service.build_full_path(folder, full_file_name)

        return UploadFileResponse(flow_id=flow_id_str, file_path=file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/upload/run/{flow_id_or_name}", status_code=HTTPStatus.CREATED)
async def upload_and_run_file(
    *,
    file: UploadFile,
    api_key_user: Annotated[UserRead, Depends(api_key_security)],
    flow: Annotated[FlowRead | None, Depends(get_flow_by_id_or_endpoint_name)],
    session: AsyncDbSession,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
    input_request: SimplifiedAPIRequest | None = None,
    file_path_field: str = Query("input_value"),
    input_type: str = Query("text"),
    output_type: str = Query("text"),
    stream: bool = Query(default=False),
    background_tasks: BackgroundTasks,
) -> RunResponse:
    try:
        # Rely on upload_file to validate the user/flow combination
        upload_results = await upload_file(
            file=file,
            api_key_user=api_key_user,
            flow=flow,
            session=session,
            storage_service=storage_service,
        )

        upload_outputs = RunOutputs(
            inputs={
                "filename": file.filename,
                "content_type": file.content_type,
                "size": file.size,
            },
            outputs=[ResultData(results=upload_results)],
        )

        if not hasattr(upload_results, "file_path") or not upload_results.file_path:
            raise HTTPException(status_code=500, detail="Invalid upload response")

        full_path = str(upload_results.file_path)

        if not input_request:
            input_request = SimplifiedAPIRequest(
                input_value=full_path,
                input_type=input_type,
                output_type=output_type,
            )
        else:
            input_request.set_value_by_path(file_path_field, full_path)

        run_response = await simplified_run_flow(
            background_tasks=background_tasks,
            flow=flow,
            input_request=input_request,
            stream=stream,
            api_key_user=api_key_user,
        )

        # Prepend the upload outputs as that happened first
        run_response.outputs.insert(0, upload_outputs)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    else:
        return run_response


@router.get("/download/{flow_id_or_name}/{file_name}")
async def download_file(
    file_name: str,
    flow: Annotated[FlowRead | None, Depends(get_flow_by_id_or_endpoint_name)],
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
):
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")

    flow_id_str = str(flow.id)
    extension = file_name.split(".")[-1]

    if not extension:
        raise HTTPException(status_code=500, detail=f"Extension not found for file {file_name}")
    try:
        content_type = build_content_type_from_extension(extension)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    if not content_type:
        raise HTTPException(status_code=500, detail=f"Content type not found for extension {extension}")

    try:
        file_content = await storage_service.get_file(flow_id=flow_id_str, file_name=file_name)
        headers = {
            "Content-Disposition": f"attachment; filename={file_name} filename*=UTF-8''{file_name}",
            "Content-Type": "application/octet-stream",
            "Content-Length": str(len(file_content)),
        }
        return StreamingResponse(BytesIO(file_content), media_type=content_type, headers=headers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/images/{flow_id_or_name}/{file_name}")
async def download_image(
    file_name: str,
    flow: Annotated[FlowRead | None, Depends(get_flow_by_id_or_endpoint_name)],
):
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")

    storage_service = get_storage_service()
    extension = file_name.split(".")[-1]
    flow_id_str = str(flow.id)

    if not extension:
        raise HTTPException(status_code=500, detail=f"Extension not found for file {file_name}")
    try:
        content_type = build_content_type_from_extension(extension)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    if not content_type:
        raise HTTPException(status_code=500, detail=f"Content type not found for extension {extension}")
    if not content_type.startswith("image"):
        raise HTTPException(status_code=500, detail=f"Content type {content_type} is not an image")

    try:
        file_content = await storage_service.get_file(flow_id=flow_id_str, file_name=file_name)
        return StreamingResponse(BytesIO(file_content), media_type=content_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/profile_pictures/{folder_name}/{file_name}")
async def download_profile_picture(
    folder_name: str,
    file_name: str,
):
    try:
        storage_service = get_storage_service()
        extension = file_name.split(".")[-1]
        config_dir = storage_service.settings_service.settings.config_dir
        config_path = Path(config_dir)  # type: ignore[arg-type]
        folder_path = config_path / "profile_pictures" / folder_name
        content_type = build_content_type_from_extension(extension)
        file_content = await storage_service.get_file(flow_id=folder_path, file_name=file_name)  # type: ignore[arg-type]
        return StreamingResponse(BytesIO(file_content), media_type=content_type)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/profile_pictures/list")
async def list_profile_pictures():
    try:
        storage_service = get_storage_service()
        config_dir = storage_service.settings_service.settings.config_dir
        config_path = Path(config_dir)  # type: ignore[arg-type]

        people_path = config_path / "profile_pictures/People"
        space_path = config_path / "profile_pictures/Space"

        people = await storage_service.list_files(flow_id=people_path)  # type: ignore[arg-type]
        space = await storage_service.list_files(flow_id=space_path)  # type: ignore[arg-type]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    files = [f"People/{i}" for i in people]
    files += [f"Space/{i}" for i in space]

    return {"files": files}


@router.get("/list/{flow_id_or_name}")
async def list_files(
    flow: Annotated[FlowRead | None, Depends(get_flow_by_id_or_endpoint_name)],
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
):
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")

    try:
        flow_id_str = str(flow.id)
        files = await storage_service.list_files(flow_id=flow_id_str)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return {"files": files}


@router.delete("/delete/{flow_id_or_name}/{file_name}")
async def delete_file(
    file_name: str,
    flow: Annotated[FlowRead | None, Depends(get_flow_by_id_or_endpoint_name)],
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
):
    if not flow:
        raise HTTPException(status_code=404, detail="Flow not found")

    try:
        flow_id_str = str(flow.id)
        await storage_service.delete_file(flow_id=flow_id_str, file_name=file_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return {"message": f"File {file_name} deleted successfully"}
