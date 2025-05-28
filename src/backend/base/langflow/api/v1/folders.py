from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import RedirectResponse
from fastapi_pagination import Params

from langflow.api.utils import custom_params
from langflow.services.database.models.flow.model import FlowRead
from langflow.services.database.models.folder.model import (
    FolderRead,
    FolderReadWithFlows,
)
from langflow.services.database.models.folder.pagination_model import FolderWithPaginatedFlows

router = APIRouter(prefix="/folders", tags=["Folders"])

# This file now serves as a redirection to the projects endpoint
# All routes will redirect to the corresponding projects endpoint


@router.post("/", response_model=FolderRead, status_code=201)
async def create_folder_redirect():
    """Redirect to the projects endpoint."""
    return RedirectResponse(url="/api/v1/projects/", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/", response_model=list[FolderRead], status_code=200)
async def read_folders_redirect():
    """Redirect to the projects endpoint."""
    return RedirectResponse(url="/api/v1/projects/", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/{folder_id}", response_model=FolderWithPaginatedFlows | FolderReadWithFlows, status_code=200)
async def read_folder_redirect(
    *,
    folder_id: UUID,
    params: Annotated[Params | None, Depends(custom_params)],
    is_component: bool = False,
    is_flow: bool = False,
    search: str = "",
):
    """Redirect to the projects endpoint."""
    redirect_url = f"/api/v1/projects/{folder_id}"
    params_list = []
    if is_component:
        params_list.append(f"is_component={is_component}")
    if is_flow:
        params_list.append(f"is_flow={is_flow}")
    if search:
        params_list.append(f"search={search}")
    if params and params.page:
        params_list.append(f"page={params.page}")
    if params and params.size:
        params_list.append(f"size={params.size}")

    if params_list:
        redirect_url += "?" + "&".join(params_list)

    return RedirectResponse(url=redirect_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.patch("/{folder_id}", response_model=FolderRead, status_code=200)
async def update_folder_redirect(
    *,
    folder_id: UUID,
):
    """Redirect to the projects endpoint."""
    return RedirectResponse(url=f"/api/v1/projects/{folder_id}", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.delete("/{folder_id}", status_code=204)
async def delete_folder_redirect(
    *,
    folder_id: UUID,
):
    """Redirect to the projects endpoint."""
    return RedirectResponse(url=f"/api/v1/projects/{folder_id}", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/download/{folder_id}", status_code=200)
async def download_file_redirect(
    *,
    folder_id: UUID,
):
    """Redirect to the projects endpoint."""
    return RedirectResponse(
        url=f"/api/v1/projects/download/{folder_id}", status_code=status.HTTP_307_TEMPORARY_REDIRECT
    )


@router.post("/upload/", response_model=list[FlowRead], status_code=201)
async def upload_file_redirect():
    """Redirect to the projects endpoint."""
    return RedirectResponse(url="/api/v1/projects/upload/", status_code=status.HTTP_307_TEMPORARY_REDIRECT)
