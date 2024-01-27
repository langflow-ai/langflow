import hashlib
from http import HTTPStatus
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from langflow.services.deps import get_storage_service
from langflow.services.storage.service import StorageService
from langflow.services.storage.utils import build_content_type_from_extension

router = APIRouter(tags=["Files"], prefix="/files")


@router.post("/upload/{flow_id}", status_code=HTTPStatus.CREATED)
async def upload_file(flow_id: str, file: UploadFile, storage_service: StorageService = Depends(get_storage_service)):
    try:
        file_content = await file.read()
        file_name = file.filename or hashlib.sha256(file_content).hexdigest()
        folder = flow_id
        storage_service.save_file(folder=folder, file_name=file_name, data=file_content)
        return {"message": "File uploaded successfully", "file_path": f"{folder}/{file.filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{flow_id}/{file_name}")
async def download_file(flow_id: str, file_name: str, storage_service: StorageService = Depends(get_storage_service)):
    try:
        extension = file_name.split(".")[-1]

        if not extension:
            raise HTTPException(status_code=500, detail=f"Extension not found for file {file_name}")

        content_type = build_content_type_from_extension(extension)

        if not content_type:
            raise HTTPException(status_code=500, detail=f"Content type not found for extension {extension}")

        file_content = storage_service.get_file(folder=flow_id, file_name=file_name)
        return StreamingResponse(BytesIO(file_content), media_type=content_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list/{flow_id}")
async def list_files(flow_id: str, storage_service: StorageService = Depends(get_storage_service)):
    try:
        files = storage_service.list_files(folder=flow_id)
        return {"files": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete/{flow_id}/{file_name}")
async def delete_file(flow_id: str, file_name: str, storage_service: StorageService = Depends(get_storage_service)):
    try:
        storage_service.delete_file(folder=flow_id, file_name=file_name)
        return {"message": f"File {file_name} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
