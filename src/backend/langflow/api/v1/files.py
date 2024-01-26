import hashlib
from http import HTTPStatus
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from langflow.services.deps import get_storage_service
from langflow.services.storage.service import StorageService

router = APIRouter(tags=["Files"], prefix="/files")


@router.post("/upload/{folder}", status_code=HTTPStatus.CREATED)
async def upload_file(flow_id: str, file: UploadFile, storage_service: StorageService = Depends(get_storage_service)):
    try:
        file_content = await file.read()
        file_name = file.filename
        filename = file.filename
        if isinstance(filename, str) or isinstance(filename, Path):
            file_extension = Path(filename).suffix
        else:
            file_extension = ""
        file_object = file.file
        sha256_hash = hashlib.sha256()
        # Reset the file cursor to the beginning of the file
        file_object.seek(0)
        # Iterate over the uploaded file in small chunks to conserve memory
        while chunk := file_object.read(8192):  # Read 8KB at a time (adjust as needed)
            sha256_hash.update(chunk)

        # Use the hex digest of the hash as the file name
        hex_dig = sha256_hash.hexdigest()
        file_name = f"{hex_dig}{file_extension}"

        folder = flow_id
        storage_service.save_file(folder=folder, file_name=file_name, data=file_content)
        return {"message": "File uploaded successfully", "file_path": f"{folder}/{file.filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{folder}/{file_name}")
async def download_file(folder: str, file_name: str, storage_service: StorageService = Depends(get_storage_service)):
    try:
        file_content = storage_service.get_file(folder=folder, file_name=file_name)
        return {"file_content": file_content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list/{folder}")
async def list_files(folder: str, storage_service: StorageService = Depends(get_storage_service)):
    try:
        files = storage_service.list_files(folder=folder)
        return {"files": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete/{folder}/{file_name}")
async def delete_file(folder: str, file_name: str, storage_service: StorageService = Depends(get_storage_service)):
    try:
        storage_service.delete_file(folder=folder, file_name=file_name)
        return {"message": f"File {file_name} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
