"""Flexstore API endpoints - ported from genesis-bff.

This module provides proxy endpoints to the Flexstore service for Azure Blob Storage operations.
These endpoints were previously in the BFF layer and are now moved directly to the backend.
"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from langflow.services.deps import get_flexstore_service
from langflow.services.flexstore.service import FlexStoreService

router = APIRouter(prefix="/flexstore", tags=["Flexstore"])


# ============================================================================
# Request/Response Models
# ============================================================================


class SourceDetails(BaseModel):
    """Source details for Azure Blob Storage operations."""

    containerName: str | None = Field(None, description="Azure blob container name")
    storageAccount: str | None = Field(None, description="Azure storage account name")


class SignedUrlRequest(BaseModel):
    """Request model for generating signed URLs."""

    fileName: str = Field(..., description="File name/path in the storage")
    sourceType: str = Field(default="azureblobstorage", description="Storage type")
    sourceDetails: SourceDetails = Field(default_factory=SourceDetails)


class ContainerListRequest(BaseModel):
    """Request model for listing containers."""

    sourceType: str = Field(default="azureblobstorage", description="Storage type")
    storageAccount: str | None = Field(None, description="Azure storage account name")


class ContainerFilesRequest(BaseModel):
    """Request model for listing files in a container."""

    sourceType: str = Field(default="azureblobstorage", description="Storage type")
    sourceDetails: SourceDetails


# ============================================================================
# Endpoints (Ported from BFF)
# ============================================================================


@router.post("/signedurl/upload")
async def get_upload_signed_url(
    request: SignedUrlRequest, flexstore_service: FlexStoreService = Depends(get_flexstore_service)
) -> dict[str, Any]:
    """
    Get presigned URL for uploading files to Azure Blob Storage.

    This endpoint proxies the request to the Flexstore service which generates
    a time-limited signed URL that allows direct upload to Azure Blob Storage.

    Ported from: BFF flexstore.controller.ts::getPresignedUrl()

    Args:
        request: Upload signed URL request containing fileName and storage details
        flexstore_service: Injected FlexStore service instance

    Returns:
        Response containing the presigned upload URL

    Example:
        {
            "presignedUrl": {
                "data": {
                    "signedUrl": "https://..."
                },
                "status": "success"
            }
        }
    """
    signed_url = await flexstore_service.get_signed_url_upload(
        storage_account=request.sourceDetails.storageAccount,
        container_name=request.sourceDetails.containerName,
        file_name=request.fileName,
    )

    return {"presignedUrl": {"data": {"signedUrl": signed_url}, "status": "success"}}


@router.post("/signedurl/read")
async def get_read_signed_url(
    request: SignedUrlRequest, flexstore_service: FlexStoreService = Depends(get_flexstore_service)
) -> dict[str, Any]:
    """
    Get presigned URL for reading files from Azure Blob Storage.

    This endpoint proxies the request to the Flexstore service which generates
    a time-limited signed URL that allows direct read access to Azure Blob Storage.

    Ported from: BFF flexstore.controller.ts::getReadUrl()

    Args:
        request: Read signed URL request containing fileName and storage details
        flexstore_service: Injected FlexStore service instance

    Returns:
        Response containing the presigned read URL

    Example:
        {
            "presignedUrl": {
                "data": {
                    "signedUrl": "https://..."
                },
                "status": "success"
            }
        }
    """
    signed_url = await flexstore_service.get_signed_url(
        storage_account=request.sourceDetails.storageAccount,
        container_name=request.sourceDetails.containerName,
        file_name=request.fileName,
    )

    return {"presignedUrl": {"data": {"signedUrl": signed_url}, "status": "success"}}


@router.post("/containers/containers")
async def get_containers(
    request: ContainerListRequest, flexstore_service: FlexStoreService = Depends(get_flexstore_service)
) -> dict[str, Any]:
    """
    Get list of containers from Azure Storage account.

    This endpoint proxies the request to the Flexstore service to retrieve
    all available containers in the specified storage account.

    Ported from: BFF flexstore-containers.controller.ts::getContainersList()

    Args:
        request: Container list request with optional storage account
        flexstore_service: Injected FlexStore service instance

    Returns:
        Response containing list of container names

    Example:
        {
            "data": {
                "containers": ["container1", "container2"]
            },
            "status": "success"
        }
    """
    containers = await flexstore_service.get_containers(storage_account=request.storageAccount)

    return {"data": {"containers": containers}, "status": "success"}


@router.post("/containers/files")
async def get_container_files(
    request: ContainerFilesRequest, flexstore_service: FlexStoreService = Depends(get_flexstore_service)
) -> dict[str, Any]:
    """
    Get list of files from a specific container.

    This endpoint proxies the request to the Flexstore service to retrieve
    all files in the specified container.

    Ported from: BFF flexstore-containers.controller.ts::getContainersFiles()

    Args:
        request: Container files request with storage account and container name
        flexstore_service: Injected FlexStore service instance

    Returns:
        Response containing list of file names/paths

    Example:
        {
            "data": {
                "files": ["file1.txt", "folder/file2.pdf"]
            },
            "status": "success"
        }
    """
    files = await flexstore_service.get_files(
        storage_account=request.sourceDetails.storageAccount, container_name=request.sourceDetails.containerName
    )

    return {"data": {"files": files}, "status": "success"}
