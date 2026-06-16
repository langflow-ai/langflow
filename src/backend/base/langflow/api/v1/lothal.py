"""Lothal API — the full `/api/v1/lothal/` contract surface (Story A.1).

Every endpoint from `api-endpoints.md` is declared here so the UI can be built
against the real surface up front. For now each one returns a structured `501`
(`{detail, status: "not_implemented"}`) that the frontend's single `NotReady`
state keys off. An endpoint "goes live" by replacing its `stub(...)` body with a
real implementation — its signature, response model, and the UI stay unchanged.

Auth is enforced router-wide via `get_current_active_user`. A missing token
returns `403` (mapped from `MissingCredentialsError` by `_auth_error_to_http`
in `services/auth/utils.py`); an invalid or expired token returns `401`. The
auth tests accept either status. `POST /debug/llm` narrows this to
`get_current_active_superuser` — it triggers a real model call, so it is
admin-only and not exposed to ordinary users in production.

Ownership is enforced per-route via the `OwnedProject` dependency: every
project-scoped route — stubs included — resolves `{project_id}` to a project
owned by the caller or 404s, so an endpoint going live can never forget the
check.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlmodel import select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.lothal.llm import LLMConfigError, LLMConnectionError, call_llm
from langflow.lothal.router import process_turn
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
from langflow.services.auth.utils import get_current_active_superuser, get_current_active_user
from langflow.services.database.models.lothal_project.model import Message, MessageRole, Project, ProjectPhase

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


def _to_message_read(message: Message) -> MessageRead:
    """Map a stored `Message` row to the contract shape.

    `suggestions` is `[]` for USER turns and non-clarification replies, and the
    clarification chips for a CLARIFICATION assistant turn.
    """
    return MessageRead(
        id=message.id,
        project_id=message.project_id,
        role=message.role,
        content=message.content,
        suggestions=message.suggestions,
        phase=message.phase,
        created_at=message.created_at,
    )


def _llm_error_to_http(exc: LLMConfigError | LLMConnectionError) -> HTTPException:
    """Map the typed LLM bridge errors to distinct HTTP statuses.

    A misconfigured environment (SDK missing or not logged in) is a 503; a failed
    model round-trip is a 502 — the same split `POST /debug/llm` exposes.
    """
    if isinstance(exc, LLMConfigError):
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"LLM is not configured: {exc}")
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"LLM call failed: {exc}")


async def _get_owned_project(session: DbSession, current_user: CurrentActiveUser, project_id: UUID) -> Project:
    """Resolve the `{project_id}` path param to a project owned by the caller, or raise 404.

    Ownership is enforced by the `user_id` predicate: another user's project is
    indistinguishable from a missing one, so it 404s rather than 403 — we never
    confirm a project's existence to a user who can't see it.
    """
    project = (
        await session.exec(select(Project).where(Project.id == project_id, Project.user_id == current_user.id))
    ).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
    return project


# Declared on every project-scoped route (stubs included) so ownership is
# checked at declaration time — replacing a stub body can't drop the check.
OwnedProject = Annotated[Project, Depends(_get_owned_project)]


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
async def get_project(*, project: OwnedProject) -> ProjectRead:
    return _to_project_read(project)


@router.delete(
    "/projects/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a project",
)
async def delete_project(
    *,
    session: DbSession,
    project: OwnedProject,
) -> Response:
    """Delete a project, cascading to its messages and code files (404 if not owned)."""
    await session.delete(project)
    # Flush eagerly so cascade/constraint errors surface in-request (as a 5xx)
    # rather than at the post-response teardown commit — by then the client has
    # already been told 204. Mirrors the upstream `projects.py` delete handler.
    await session.flush()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Chat --------------------------------------------------------------------


async def _project_messages(session: DbSession, project_id: UUID) -> list[Message]:
    """Load a project's turns, oldest first.

    Ordered by `created_at` (the only temporal column), with `id` as a stable
    tiebreaker so same-timestamp rows replay in a deterministic order.
    """
    return list(
        (
            await session.exec(
                select(Message).where(Message.project_id == project_id).order_by(Message.created_at, Message.id)  # type: ignore[arg-type]
            )
        ).all()
    )


@router.post(
    "/projects/{project_id}/chat",
    summary="Send a chat message (routes to the phase engine)",
)
async def chat(*, session: DbSession, project: OwnedProject, body: ChatRequest) -> MessageRead:
    """Run one conversation turn (Story 1.2).

    Stores the user message, routes the turn to the engine for the project's
    current phase (`process_turn`), stores the assistant reply with its
    clarification `suggestions`, and persists any phase transition the engine
    signalled. The returned assistant `Message` carries `content`, `suggestions`,
    and `phase` — the `{message, suggestions, phase}` the chat UI consumes.

    Both turns are stamped with the phase the turn *ran under* (the project's
    phase at send time); a transition takes effect on the project for the next
    turn. On leaving CLARIFICATION the assistant reply is the synthesised PRD, so
    it is stored on the project (surfaced by `GET /prd`). The whole turn is one
    transaction: an LLM failure rolls back the user message too, so a retry
    starts clean.
    """
    content = body.content.strip()
    if not content:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Message content cannot be empty.")

    turn_phase = project.phase

    # Prior turns only — loaded before the new user message is added so the engine
    # sees the history that preceded this turn (it appends `content` itself).
    history = await _project_messages(session, project.id)

    session.add(Message(project_id=project.id, role=MessageRole.USER, content=content, phase=turn_phase))

    try:
        response = await process_turn(turn_phase, history, content)
    except (LLMConfigError, LLMConnectionError) as exc:
        raise _llm_error_to_http(exc) from exc

    assistant_message = Message(
        project_id=project.id,
        role=MessageRole.ASSISTANT,
        content=response.text,
        suggestions=response.suggestions,
        phase=turn_phase,
    )
    session.add(assistant_message)

    if response.next_phase is not None and response.next_phase != turn_phase:
        # The PRD is the clarification engine's parting summary; capture it as the
        # project leaves CLARIFICATION (`GET /prd` reads it, Story 1.3).
        if turn_phase == ProjectPhase.CLARIFICATION:
            project.prd_content = response.text
        project.phase = response.next_phase
        session.add(project)

    await session.flush()
    await session.refresh(assistant_message)
    return _to_message_read(assistant_message)


@router.get(
    "/projects/{project_id}/messages",
    summary="List a project's messages",
)
async def list_messages(*, session: DbSession, project: OwnedProject) -> list[MessageRead]:
    """Return the project's conversation, oldest first, each with its `suggestions`.

    History replay rehydrates the chat — including the clarification chips on each
    assistant turn — so a reopened project shows exactly what the user last saw.
    """
    return [_to_message_read(m) for m in await _project_messages(session, project.id)]


# --- PRD ---------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/prd",
    response_model=PRDResponse,
    responses=_NOT_IMPLEMENTED,
    summary="Get the project's PRD summary",
)
async def get_prd(project: OwnedProject) -> JSONResponse:
    return stub("The PRD endpoint is not implemented yet.")


# --- Diagram -----------------------------------------------------------------


@router.get(
    "/projects/{project_id}/diagram",
    response_model=DiagramResponse,
    responses=_NOT_IMPLEMENTED,
    summary="Get the diagram (Mermaid + xyflow)",
)
async def get_diagram(project: OwnedProject) -> JSONResponse:
    return stub("The diagram endpoint is not implemented yet.")


@router.post(
    "/projects/{project_id}/diagram/save",
    response_model=DiagramSaveResponse,
    responses=_NOT_IMPLEMENTED,
    summary="Save the canvas (xyflow → Mermaid + validate)",
)
async def save_diagram(project: OwnedProject, body: DiagramSaveRequest) -> JSONResponse:
    return stub("Saving the diagram is not implemented yet.")


@router.post(
    "/projects/{project_id}/diagram/approve",
    response_model=DiagramApproveResponse,
    responses=_NOT_IMPLEMENTED,
    summary="Approve the diagram and advance to code generation",
)
async def approve_diagram(project: OwnedProject) -> JSONResponse:
    return stub("Approving the diagram is not implemented yet.")


# --- Code --------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/code",
    response_model=CodeResponse,
    responses=_NOT_IMPLEMENTED,
    summary="Get generated code files",
)
async def get_code(project: OwnedProject) -> JSONResponse:
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
async def download_project(project: OwnedProject) -> JSONResponse:
    return stub("Downloading the project is not implemented yet.")


# --- Debug -------------------------------------------------------------------


@router.post(
    "/debug/llm",
    dependencies=[Depends(get_current_active_superuser)],
    summary="Test LLM connectivity (superuser only)",
)
async def debug_llm(body: DebugLLMRequest) -> DebugLLMResponse:
    """Round-trip one message through the configured LLM (Story 0.4).

    Superuser-gated: every call is a real, billable model round-trip, so this
    connectivity probe is restricted to admins (an ordinary authenticated user
    must not be able to drive unmetered LLM calls against the operator's
    subscription). The router-wide `get_current_active_user` is narrowed here to
    `get_current_active_superuser`.

    The typed bridge errors map to distinct statuses so a curl can tell a
    misconfigured environment (503 — e.g. SDK missing or not logged in) apart
    from a failed model call (502).
    """
    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Message cannot be empty.")
    try:
        reply = await call_llm([{"role": "user", "content": message}])
    except (LLMConfigError, LLMConnectionError) as exc:
        raise _llm_error_to_http(exc) from exc
    return DebugLLMResponse(response=reply)
