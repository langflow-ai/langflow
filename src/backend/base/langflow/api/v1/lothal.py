"""Lothal API — the full `/api/v1/lothal/` contract surface (Story A.1).

Every endpoint from `api-endpoints.md` is declared here so the UI can be built
against the real surface up front. For now each one returns a structured `501`
(`{detail, status: "not_implemented"}`) that the frontend's single `NotReady`
state keys off. An endpoint "goes live" by replacing its `stub(...)` body with a
real implementation — its signature, response model, and the UI stay unchanged.

Auth is enforced router-wide via `get_current_active_user`. A missing token
returns `403` (mapped from `MissingCredentialsError` by `_auth_error_to_http`
in `services/auth/utils.py`); an invalid or expired token returns `401`. The
auth tests accept either status.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlmodel import select

from langflow.api.utils import CurrentActiveUser, DbSession
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
from langflow.services.database.models.lothal_project.model import Project

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


def _to_project_read(project: Project) -> ProjectRead:
    """Map the ORM row to the contract shape.

    `diagram_layout` is stored as a JSON string of xyflow positions but the
    contract exposes it as an object; `ProjectRead`'s validator parses it once
    at the schema boundary (it is `None` for every B.2 flow — only the diagram
    stories populate it).
    """
    return ProjectRead(
        id=project.id,
        user_id=project.user_id,
        name=project.name,
        phase=project.phase,
        prd_content=project.prd_content,
        diagram_mmd=project.diagram_mmd,
        diagram_layout=project.diagram_layout,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


async def _get_owned_project(session: DbSession, project_id: UUID, user_id: UUID) -> Project:
    """Fetch a project owned by `user_id`, or raise 404.

    Ownership is enforced by the `user_id` predicate: another user's project is
    indistinguishable from a missing one, so it 404s rather than 403 — we never
    confirm a project's existence to a user who can't see it.
    """
    project = (await session.exec(select(Project).where(Project.id == project_id, Project.user_id == user_id))).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return project


# --- Projects ----------------------------------------------------------------


@router.post(
    "/projects/",
    status_code=status.HTTP_201_CREATED,
    summary="Create a project",
)
async def create_project(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    body: ProjectCreate,
) -> ProjectRead:
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Project name cannot be empty.")
    project = Project(name=name, user_id=current_user.id)
    session.add(project)
    await session.flush()
    await session.refresh(project)
    return _to_project_read(project)


@router.get(
    "/projects/",
    summary="List the authenticated user's projects",
)
async def list_projects(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
) -> list[ProjectRead]:
    projects = (
        await session.exec(
            select(Project).where(Project.user_id == current_user.id).order_by(Project.updated_at.desc())  # type: ignore[attr-defined]
        )
    ).all()
    return [_to_project_read(p) for p in projects]


@router.get(
    "/projects/{project_id}",
    summary="Get a project",
)
async def get_project(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    project_id: UUID,
) -> ProjectRead:
    project = await _get_owned_project(session, project_id, current_user.id)
    return _to_project_read(project)


@router.delete(
    "/projects/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a project",
)
async def delete_project(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    project_id: UUID,
) -> Response:
    """Delete a project, cascading to its messages and code files (404 if not owned)."""
    project = await _get_owned_project(session, project_id, current_user.id)
    await session.delete(project)
    # Flush eagerly so cascade/constraint errors surface in-request (as a 5xx)
    # rather than at the post-response teardown commit — by then the client has
    # already been told 204. Mirrors the upstream `projects.py` delete handler.
    await session.flush()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
