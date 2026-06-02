"""Lothal API — the full `/api/v1/lothal/` contract surface (Story A.1).

Every endpoint from `api-endpoints.md` is declared here so the UI can be built
against the real surface up front. For now each one returns a structured `501`
(`{detail, status: "not_implemented"}`) that the frontend's single `NotReady`
state keys off. An endpoint "goes live" by replacing its `stub(...)` body with a
real implementation — its signature, response model, and the UI stay unchanged.

Auth is enforced router-wide via `get_current_active_user`, so every route
returns `401` without a valid token.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from langflow.lothal.schemas import (
    ChatRequest,
    CodeResponse,
    DebugLLMRequest,
    DebugLLMResponse,
    DiagramApproveResponse,
    DiagramResponse,
    DiagramSaveRequest,
    DiagramSaveResponse,
    MessageRead,
    NotImplementedResponse,
    PRDResponse,
    ProjectCreate,
    ProjectRead,
)
from langflow.services.auth.utils import get_current_active_user

router = APIRouter(
    prefix="/lothal",
    tags=["Lothal"],
    dependencies=[Depends(get_current_active_user)],
)

# Document the structured 501 on every stubbed route so `/docs` advertises the
# exact shape the frontend's `NotReady` state consumes.
_NOT_IMPLEMENTED: dict[int | str, dict[str, object]] = {
    status.HTTP_501_NOT_IMPLEMENTED: {
        "model": NotImplementedResponse,
        "description": "Declared by the contract but not implemented yet.",
    },
}


def stub(detail: str) -> JSONResponse:
    """Return the structured `501` body every not-yet-built endpoint shares."""
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={"detail": detail, "status": "not_implemented"},
    )


# --- Projects ----------------------------------------------------------------


@router.post(
    "/projects/",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
    responses=_NOT_IMPLEMENTED,
    summary="Create a project",
)
async def create_project(body: ProjectCreate) -> JSONResponse:
    return stub("Project creation is not implemented yet.")


@router.get(
    "/projects/",
    response_model=list[ProjectRead],
    responses=_NOT_IMPLEMENTED,
    summary="List the authenticated user's projects",
)
async def list_projects() -> JSONResponse:
    return stub("Listing projects is not implemented yet.")


@router.get(
    "/projects/{project_id}",
    response_model=ProjectRead,
    responses=_NOT_IMPLEMENTED,
    summary="Get a project",
)
async def get_project(project_id: UUID) -> JSONResponse:
    return stub("Fetching a project is not implemented yet.")


@router.delete(
    "/projects/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_NOT_IMPLEMENTED,
    summary="Delete a project",
)
async def delete_project(project_id: UUID) -> JSONResponse:
    return stub("Deleting a project is not implemented yet.")


# --- Chat --------------------------------------------------------------------


@router.post(
    "/projects/{project_id}/chat",
    response_model=MessageRead,
    responses=_NOT_IMPLEMENTED,
    summary="Send a chat message (routes to the phase engine)",
)
async def chat(project_id: UUID, body: ChatRequest) -> JSONResponse:
    return stub("Chat is not implemented yet.")


@router.get(
    "/projects/{project_id}/messages",
    response_model=list[MessageRead],
    responses=_NOT_IMPLEMENTED,
    summary="List a project's messages",
)
async def list_messages(project_id: UUID) -> JSONResponse:
    return stub("Listing messages is not implemented yet.")


# --- PRD ---------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/prd",
    response_model=PRDResponse,
    responses=_NOT_IMPLEMENTED,
    summary="Get the project's PRD summary",
)
async def get_prd(project_id: UUID) -> JSONResponse:
    return stub("The PRD endpoint is not implemented yet.")


# --- Diagram -----------------------------------------------------------------


@router.get(
    "/projects/{project_id}/diagram",
    response_model=DiagramResponse,
    responses=_NOT_IMPLEMENTED,
    summary="Get the diagram (Mermaid + xyflow)",
)
async def get_diagram(project_id: UUID) -> JSONResponse:
    return stub("The diagram endpoint is not implemented yet.")


@router.post(
    "/projects/{project_id}/diagram/save",
    response_model=DiagramSaveResponse,
    responses=_NOT_IMPLEMENTED,
    summary="Save the canvas (xyflow → Mermaid + validate)",
)
async def save_diagram(project_id: UUID, body: DiagramSaveRequest) -> JSONResponse:
    return stub("Saving the diagram is not implemented yet.")


@router.post(
    "/projects/{project_id}/diagram/approve",
    response_model=DiagramApproveResponse,
    responses=_NOT_IMPLEMENTED,
    summary="Approve the diagram and advance to code generation",
)
async def approve_diagram(project_id: UUID) -> JSONResponse:
    return stub("Approving the diagram is not implemented yet.")


# --- Code --------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/code",
    response_model=CodeResponse,
    responses=_NOT_IMPLEMENTED,
    summary="Get generated code files",
)
async def get_code(project_id: UUID) -> JSONResponse:
    return stub("The code endpoint is not implemented yet.")


# --- Delivery ----------------------------------------------------------------


@router.get(
    "/projects/{project_id}/download",
    responses={
        status.HTTP_200_OK: {
            "content": {"application/zip": {}},
            "description": "ZIP archive of the project's artifacts.",
        },
        **_NOT_IMPLEMENTED,
    },
    summary="Download the project as a ZIP",
)
async def download_project(project_id: UUID) -> JSONResponse:
    return stub("Downloading the project is not implemented yet.")


# --- Debug -------------------------------------------------------------------


@router.post(
    "/debug/llm",
    response_model=DebugLLMResponse,
    responses=_NOT_IMPLEMENTED,
    summary="Test LLM connectivity (dev only)",
)
async def debug_llm(body: DebugLLMRequest) -> JSONResponse:
    return stub("The LLM debug endpoint is not implemented yet.")
