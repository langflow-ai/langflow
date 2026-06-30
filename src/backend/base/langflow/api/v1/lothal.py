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

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from lfx.log.logger import logger
from sqlmodel import select

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.lothal import prototype as prototype_engine
from langflow.lothal.d2_compile import D2CompilerUnavailableError, render_d2
from langflow.lothal.llm import LLMConfigError, LLMConnectionError, call_llm
from langflow.lothal.od_client import ODConfigError, ODError
from langflow.lothal.pm_client import PMClient, PMConfigError, PMError
from langflow.lothal.router import available_phases, process_turn
from langflow.lothal.schemas import (
    ArtifactsResponse,
    ChatRequest,
    CodeResponse,
    DebugLLMRequest,
    DebugLLMResponse,
    DiagramApproveResponse,
    DiagramResponse,
    MessageRead,
    NotImplementedResponse,
    PRDResponse,
    ProjectCreate,
    ProjectRead,
    PrototypeApproveResponse,
    PrototypeArtifactRead,
    PrototypeRefineRequest,
    PrototypeStateResponse,
)
from langflow.services.auth.utils import get_current_active_superuser, get_current_active_user
from langflow.services.database.models.lothal_project.model import (
    Message,
    MessageRole,
    Project,
    ProjectPhase,
    PrototypeArtifact,
    PrototypeStatus,
)

# Phases in which the diagram exists and is readable — the `GET /diagram` phase
# gate from `api-endpoints.md`. CLARIFICATION precedes the architecture stage, so
# the diagram read 403s there (no diagram can exist yet); every later phase may
# read it. Epic E.2 merged the two diagram phases into ARCHITECTURE; Epic UI
# (U.0) inserts PROTOTYPE after it, where the approved diagram stays readable.
_DIAGRAM_VISIBLE_PHASES = frozenset(
    {
        ProjectPhase.ARCHITECTURE.value,
        ProjectPhase.PROTOTYPE.value,
        ProjectPhase.CODE_GENERATION.value,
        ProjectPhase.DONE.value,
    }
)

# Phases in which the prototype stage is readable — the `GET /prototype` phase
# gate. The prototype doesn't exist until the architecture is approved, so a read
# before PROTOTYPE 403s; it stays readable through code generation and done so the
# approved prototype keeps surfacing.
_PROTOTYPE_VISIBLE_PHASES = frozenset(
    {
        ProjectPhase.PROTOTYPE.value,
        ProjectPhase.PLAN.value,
        ProjectPhase.CODE_GENERATION.value,
        ProjectPhase.DONE.value,
    }
)

# Phases in which the planning tree is readable — the `GET /plan` phase gate. The
# plan stage opens when the prototype is approved, so a read before PLAN 403s; it
# stays readable through code generation and done so the ratified tree keeps
# surfacing. The tree itself lives in the standalone PM service (pm_client).
_PLAN_VISIBLE_PHASES = frozenset(
    {
        ProjectPhase.PLAN.value,
        ProjectPhase.CODE_GENERATION.value,
        ProjectPhase.DONE.value,
    }
)

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

    `diagram_json` is stored as a JSON string of the full xyflow graph but the
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
        diagram_json=project.diagram_json,
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


def _od_error_to_http(exc: ODError) -> HTTPException:
    """Map the Open Design client errors to HTTP, mirroring the LLM bridge split.

    A misconfigured prototyping engine (e.g. a blank base URL) is a 503; a failed
    call to a reachable-but-unhappy OD daemon is a 502 — the same setup-gap vs
    runtime-fault distinction `_llm_error_to_http` makes.
    """
    if isinstance(exc, ODConfigError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"The prototype engine is not configured: {exc}",
        )
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"The prototype engine call failed: {exc}")


def _pm_error_to_http(exc: PMError) -> HTTPException:
    """Map the Lothal PM client errors to HTTP, mirroring `_od_error_to_http`.

    A misconfigured bridge (e.g. a blank base URL) is a 503; a failed call to a
    reachable-but-unhappy PM service is a 502 — the same setup-gap vs runtime-fault
    split. (Finer 4xx pass-through for PM validation errors is a follow-up; the
    shell sends PM-shaped bodies, so a 422 from PM should not arise in practice.)
    """
    if isinstance(exc, PMConfigError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"The planning service is not configured: {exc}",
        )
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"The planning service call failed: {exc}")


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

    # Serialize concurrent turns on the same project (double-submit, two tabs).
    # Re-read the project row under a FOR UPDATE lock before deriving phase and
    # history: a second in-flight turn blocks here until this one commits, then
    # sees the committed phase and the messages this turn added — so turns can't
    # interleave or double-apply a transition. No-op on SQLite (the test DB),
    # whose dialect omits FOR UPDATE and which serializes writes DB-wide anyway.
    await session.refresh(project, with_for_update=True)

    turn_phase = project.phase

    # Not every phase has a conversation step: PROTOTYPE, CODE_GENERATION and
    # DONE have no registered chat engine. Approving a diagram (D.11) is the first
    # in-app path into PROTOTYPE, so this is now reachable — reject it as a clean 409 rather
    # than letting `process_turn` raise an uncaught `ValueError` (a 500 that also
    # leaks the engine registry, and 500s again on every retry — a stuck state).
    if turn_phase not in available_phases():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This project's current phase has no conversation step.",
        )

    # A refine turn may name which artifact it edits (Epic E.3). Reject an unknown
    # explicit target up front (422) — never silently edit a different artifact
    # than the client asked for. Skipped when no target is named or no artifact
    # map exists yet (the generation turn), where the engine defaults sensibly.
    if body.artifact and project.artifacts and body.artifact not in project.artifacts:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown artifact: {body.artifact!r}.",
        )

    # Prior turns only — loaded before the new user message is added so the engine
    # sees the history that preceded this turn (it appends `content` itself).
    history = await _project_messages(session, project.id)

    session.add(Message(project_id=project.id, role=MessageRole.USER, content=content, phase=turn_phase))

    try:
        # `prd`/`current_d2`/`artifacts`/`target_artifact` give the architecture
        # engine the state it edits: the synthesised spec, the legacy single
        # diagram, the artifact map (`adr.md` + `diagrams/*`, Epic E.3), and the
        # active artifact key the user is refining. Other phases ignore them.
        response = await process_turn(
            turn_phase,
            history,
            content,
            prd=project.prd_content,
            current_d2=project.diagram_d2,
            artifacts=project.artifacts,
            target_artifact=body.artifact,
        )
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

    if response.warning is not None:
        # Epic D.10: the refinement engine ran a coherence check of the edited D2
        # against the PRD and flagged a contradiction. Surface it as its own
        # ASSISTANT turn right after the reply so it shows in `/messages` — a
        # valid edit returns `warning=None` and adds no message. Stamp its
        # `created_at` one tick past the reply's so `/messages` (ordered by
        # created_at, then a random uuid4 id) always replays the warning *below*
        # the reply it annotates — `datetime.now()` is not strictly monotonic, so
        # relying on wall-clock distinctness alone could invert the two on a tie.
        session.add(
            Message(
                project_id=project.id,
                role=MessageRole.ASSISTANT,
                content=response.warning,
                suggestions=[],
                phase=turn_phase,
                created_at=assistant_message.created_at + timedelta(microseconds=1),
            )
        )

    if response.artifacts is not None:
        # Epic E.3: the architecture engine emits the full artifact file-map
        # (`adr.md` + `diagrams/*.d2`) for us to persist verbatim — the future git
        # commit tree. A fresh dict is assigned (not mutated in place) so the JSON
        # column tracks the change. `diagram_d2` below mirrors the sequence diagram
        # so the single-diagram read/approve flow keeps working until E.4.
        project.artifacts = response.artifacts
        session.add(project)

    if response.diagram_d2 is not None:
        # Epic D.2: the diagram generator emits D2 source for us to persist;
        # `diagram_d2` is the canonical single-diagram store (D.4 points
        # `GET /diagram` at it). Stored verbatim — D2 owns its own layout.
        project.diagram_d2 = response.diagram_d2
        session.add(project)

    if response.next_phase is not None and response.next_phase != turn_phase:
        # The PRD is the clarification engine's parting summary; capture it as the
        # project leaves CLARIFICATION (`GET /prd` reads it, Story 1.3).
        if turn_phase == ProjectPhase.CLARIFICATION:
            project.prd_content = response.text
        project.phase = response.next_phase
        session.add(project)

    # Every successful turn is project activity: bump updated_at so list ordering
    # (updated_at DESC) surfaces recently-chatted projects. A no-signal
    # clarification turn changes neither the diagram nor the phase, so without
    # this the project row stays unmodified and its timestamp would freeze at
    # creation despite active conversation.
    project.updated_at = datetime.now(timezone.utc)
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
    summary="Get the project's PRD summary",
)
async def get_prd(project: OwnedProject) -> PRDResponse:
    """Return the synthesised PRD (Story 1.3).

    `content` is `null` while the project is still in CLARIFICATION and becomes
    the stored summary once the clarification engine reaches clarity and the
    project leaves that phase (see `chat`, which writes `prd_content` on the
    transition). This is a plain read of `lothal_project.prd_content` behind the
    shared ownership check.
    """
    return PRDResponse(content=project.prd_content)


# --- Diagram -----------------------------------------------------------------


async def _render_diagram_svg(d2: str, project_id) -> str | None:
    """Render stored D2 to SVG for the read, degrading to `None` (never raising).

    A render problem must not 500 the canvas: stored D2 was compile-validated at
    generation (D.3), so this normally succeeds, but an unavailable compiler or a
    render failure logs and returns `None` (the frontend shows "no diagram yet"
    rather than an error).
    """
    try:
        result = await render_d2(d2)
    except D2CompilerUnavailableError:
        logger.warning(f"d2 compiler unavailable; returning diagram for project {project_id} without an SVG.")
        return None
    if not result.ok:
        # Don't log the compiler stderr: it can echo fragments of the user's D2
        # (their project's content). The project id is enough to reproduce.
        logger.warning(f"Stored D2 for project {project_id} failed to render; returning it without an SVG.")
        return None
    return result.svg


@router.get(
    "/projects/{project_id}/diagram",
    summary="Get the diagram (D2 source + server-rendered SVG)",
)
async def get_diagram(project: OwnedProject) -> DiagramResponse:
    """Return the project's diagram as D2 source plus a server-rendered SVG (D.4/D.6).

    The diagram artifact is D2 source text — the generator emits it (D.2) and we
    persist it verbatim to `lothal_project.diagram_d2` (D2 owns its own layout).
    This read hands that source back and, alongside it, the SVG the backend
    renders from it via the `d2` compiler (D.6): the frontend just displays the
    SVG and ships no D2 compiler of its own. The SVG is rendered on read (the
    source is the single stored truth — there is no SVG to keep in sync).

    Phase-gated to `ARCHITECTURE` and later: the diagram doesn't exist
    during CLARIFICATION, so a read there is a `403` (ownership is checked first
    by `OwnedProject`, so an unowned project still 404s regardless of phase).
    Once the project enters the architecture stage but before the generator has emitted
    anything, `diagram_d2` is `null` and an empty payload (`d2: null, svg: null`)
    is returned — never an error. A blank or whitespace-only store is treated the
    same way (normalised to `null`): it is no diagram, not a renderable one.

    Rendering never 500s the canvas: stored D2 was compile-validated at
    generation (D.3) so it renders, but if the compiler is unavailable or the
    render fails we return the `d2` with `svg: null` and log it, rather than
    failing the read. Legacy projects that only have the old `diagram_json`
    xyflow graph read as empty here until they are migrated to D2 (Epic D.13).
    """
    if project.phase not in _DIAGRAM_VISIBLE_PHASES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The diagram is not available until the architecture stage begins.",
        )

    # Blank/whitespace-only is "no diagram" → empty payload; real source is
    # returned verbatim (D2 owns its own layout, so we never trim meaningful
    # content) plus the SVG rendered from it.
    d2 = project.diagram_d2
    if not (d2 and d2.strip()):
        return DiagramResponse(d2=None)
    return DiagramResponse(d2=d2, svg=await _render_diagram_svg(d2, project.id))


def _is_diagram_artifact(path: str) -> bool:
    """Whether an artifact path is a renderable D2 diagram (`diagrams/*.d2`).

    The Architecture stage's map holds the Markdown ADR alongside the diagrams
    (Epic E.3); only the `diagrams/*.d2` entries are D2 source the backend renders
    to SVG. Keying off the path (not a hardcoded list) keeps a future diagram —
    e.g. a deployment diagram, one entry in `DIAGRAM_SPECS` — rendering with no
    change here.
    """
    return path.startswith("diagrams/") and path.endswith(".d2")


@router.get(
    "/projects/{project_id}/artifacts",
    summary="Get the architecture artifact map (+ server-rendered diagram SVGs)",
)
async def get_artifacts(project: OwnedProject) -> ArtifactsResponse:
    """Return the Architecture stage's artifact map and a rendered SVG per diagram (Epic E.4).

    The ARCHITECTURE stage writes a flat `{path: content}` artifact map to
    `lothal_project.artifacts` (`adr.md` + `diagrams/*.d2`, Epic E.3) — the future
    git commit tree verbatim. This read hands that map back as `artifacts` and,
    alongside it, renders every `diagrams/*.d2` entry to SVG via the backend `d2`
    compiler (the same render path `GET /diagram` uses), keyed by the diagram's
    path in `svgs`. The frontend (E.5) renders the ADR Markdown itself and just
    displays the SVGs — it ships no D2 compiler of its own.

    Phase-gated to `ARCHITECTURE` and later, exactly like `GET /diagram`: no
    artifacts exist during CLARIFICATION, so a read there is a `403` (ownership is
    checked first by `OwnedProject`, so an unowned project still 404s regardless of
    phase). Once in the architecture stage but before the generator has emitted
    anything, `artifacts` is `null` and an empty map (`artifacts: {}, svgs: {}`) is
    returned — never an error.

    Rendering never 500s: each diagram was compile-validated at generation (E.3),
    but a missing compiler or a render failure yields `svg: null` for that entry
    (logged via `_render_diagram_svg`), rather than failing the whole read.
    Diagrams render concurrently so the read stays snappy across the full set.
    """
    if project.phase not in _DIAGRAM_VISIBLE_PHASES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Artifacts are not available until the architecture stage begins.",
        )

    artifacts = project.artifacts or {}

    # Render every diagram entry to SVG concurrently (gather preserves order), then
    # pair each SVG back with its artifact path. The ADR (`adr.md`) is Markdown and
    # gets no SVG. `_render_diagram_svg` fail-closes to `None` for a blank or
    # non-compiling entry, so the map shape is always {diagram_path: svg|null}.
    diagram_paths = [path for path in artifacts if _is_diagram_artifact(path)]
    svgs = await asyncio.gather(*(_render_diagram_svg(artifacts[path], project.id) for path in diagram_paths))
    return ArtifactsResponse(artifacts=artifacts, svgs=dict(zip(diagram_paths, svgs, strict=True)))


@router.post(
    "/projects/{project_id}/diagram/approve",
    summary="Approve the architecture and advance to the prototype stage",
)
async def approve_diagram(*, session: DbSession, project: OwnedProject) -> DiagramApproveResponse:
    """Approve the architecture and advance to PROTOTYPE (Epic D.11; retargeted by Epic UI U.0).

    The diagram surface has no canvas-save path (Epic D.9 retired it): the user
    shapes the D2 by conversation (the architecture engine, E.2), and *approving*
    is the single forward action that ends the architecture stage. Approval is
    therefore only valid in ARCHITECTURE — calling it in any other phase is a `409`
    (a no-op transition the UI shouldn't have offered) rather than silently
    re-approving. The approved D2 is retained verbatim in `lothal_project.diagram_d2`
    (the prototype stage and code generation both read it), so `GET /diagram`
    keeps returning it unchanged across the transition.

    The transition target is PROTOTYPE, not CODE_GENERATION: Epic UI inserts the
    prototype stage between architecture and code generation (the prototype is
    then approved separately to reach CODE_GENERATION, Story U.7).

    Serialized against concurrent turns the same way `chat` is: re-read the row
    under a `FOR UPDATE` lock before deciding, so a refine turn and an approve
    can't interleave and double-apply or skip the transition.
    """
    await session.refresh(project, with_for_update=True)

    if project.phase != ProjectPhase.ARCHITECTURE.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The architecture can only be approved during the architecture stage.",
        )

    # There must be a diagram to approve. On the happy path generation always
    # populates `diagram_d2` before refinement, but guard against advancing past
    # the architecture stage with nothing downstream (the prototype stage and code
    # generation) can read (e.g. a legacy project whose only diagram was the
    # dropped xyflow graph).
    if not (project.diagram_d2 and project.diagram_d2.strip()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="There is no diagram to approve yet.",
        )

    project.phase = ProjectPhase.PROTOTYPE.value
    project.updated_at = datetime.now(timezone.utc)
    session.add(project)
    await session.flush()
    await session.refresh(project)
    return DiagramApproveResponse(phase=project.phase)


# --- Prototype (Epic UI) -----------------------------------------------------
# The prototype stage drives Open Design (OD) as a headless prototyping engine
# (Stories U.4-U.7). The contract shipped as 501 stubs in U.0; these are the live
# backends. Each keeps the `OwnedProject` dependency (ownership 404 before any
# work), and the orchestration lives in `langflow.lothal.prototype` — the
# handlers only gate the phase, persist what it returns, and map OD errors.


def _prototype_state_response(project: Project, state: prototype_engine.StateResult) -> PrototypeStateResponse:
    """Assemble the wire response from the project linkage + a read-back state."""
    return PrototypeStateResponse(
        status=state.status,
        od_project_id=project.od_project_id,
        od_conversation_id=project.od_conversation_id,
        embed_url=state.embed_url,
        preview_html=state.preview_html,
        artifacts=[
            PrototypeArtifactRead(path=a.path, kind=a.kind, title=a.title, preview_url=a.preview_url)
            for a in state.artifacts
        ],
    )


def _is_html_artifact(path: str, kind: str) -> bool:
    return kind == "html" or path.endswith(".html")


def _approval_summary(artifacts: list[prototype_engine.ApprovedArtifact]) -> str:
    """The single-chat-bridge summary posted on approval (Story U.10)."""
    if not artifacts:
        return (
            "Prototype approved. Generating the code from your approved architecture next."
        )
    listed = "\n".join(f"- {a.title}" for a in artifacts)
    plural = "artifact" if len(artifacts) == 1 else "artifacts"
    return f"Prototype approved with {len(artifacts)} {plural}:\n{listed}\n\nPlanning the build next."


@router.get(
    "/projects/{project_id}/prototype",
    summary="Get the prototype stage state (OD linkage + embed URL + artifacts)",
)
async def get_prototype(*, session: DbSession, project: OwnedProject) -> PrototypeStateResponse:
    """Return the prototype run state: status, OD linkage, embed URL, and artifacts (Story U.5).

    Phase-gated to `PROTOTYPE` and later (a read before then is a `403` — there is
    no prototype yet); ownership is checked first by `OwnedProject`, so an unowned
    project still 404s regardless of phase.

    Once the prototype is `APPROVED` the finalised artifacts live in Lothal's own
    store (`lothal_prototype_artifact`), so they are read from the DB rather than
    from OD (whose copy may be gone). Otherwise the live state is read from OD and
    a forward status change (`GENERATING → READY`) is persisted so the dashboard
    badge and a reopened workspace reflect it. The read never 502s the polling UI:
    if OD is unreachable it degrades to the stored status with no artifacts (the
    same "never fail the read" posture `GET /diagram` takes for a failed render).
    """
    if project.phase not in _PROTOTYPE_VISIBLE_PHASES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The prototype is not available until the prototype stage begins.",
        )

    if project.prototype_status == PrototypeStatus.APPROVED.value:
        rows = (
            await session.exec(
                select(PrototypeArtifact)
                .where(PrototypeArtifact.project_id == project.id)
                .order_by(PrototypeArtifact.created_at, PrototypeArtifact.id)  # type: ignore[arg-type]
            )
        ).all()
        # The rendered design comes from the retained copy of the primary HTML row.
        preview_html = next((r.content for r in rows if _is_html_artifact(r.od_path, r.kind) and r.content), None)
        return PrototypeStateResponse(
            status=project.prototype_status,
            od_project_id=project.od_project_id,
            od_conversation_id=project.od_conversation_id,
            embed_url=prototype_engine.embed_url(project.od_project_id),
            preview_html=preview_html,
            artifacts=[
                PrototypeArtifactRead(
                    path=r.od_path,
                    kind=r.kind,
                    title=r.title,
                    preview_url=prototype_engine.preview_url(project.od_project_id, r.od_path),
                )
                for r in rows
            ],
        )

    try:
        state = await prototype_engine.collect_state(project)
    except ODError as exc:
        logger.warning(f"prototype state read for project {project.id} degraded (OD unreachable): {exc}")
        return PrototypeStateResponse(
            status=project.prototype_status,
            od_project_id=project.od_project_id,
            od_conversation_id=project.od_conversation_id,
            embed_url=prototype_engine.embed_url(project.od_project_id),
            artifacts=[],
        )

    # Sync the lifecycle status OD reports: READY once a run succeeded, and back to
    # GENERATING when a fresh run is in flight (e.g. a refine started inside OD), so
    # a reopened workspace / the dashboard badge reflect it. APPROVED is terminal
    # (handled above) and never overwritten; IDLE is never re-derived here
    # (collect_state only yields it pre-seed, where there is nothing to persist).
    if state.status != project.prototype_status and state.status in {
        PrototypeStatus.GENERATING.value,
        PrototypeStatus.READY.value,
    }:
        project.prototype_status = state.status
        session.add(project)
        await session.flush()

    return _prototype_state_response(project, state)


@router.post(
    "/projects/{project_id}/prototype/generate",
    summary="Start (or restart) prototype generation",
)
async def generate_prototype(*, session: DbSession, project: OwnedProject) -> PrototypeStateResponse:
    """Seed an OD project from the brief and start a generation run (Story U.4).

    Only valid in the `PROTOTYPE` phase (a `409` otherwise — a no-op the UI
    shouldn't have offered). Idempotent: if the project is already linked to an OD
    project the existing run is reused and nothing is recreated or reset — so a
    re-entry or double-submit never duplicates work or clobbers a `READY` status.
    The first seed sets `prototype_status=GENERATING` and announces the stage in
    the single chat thread (Story U.10).

    Serialized against concurrent submits the same way `chat`/`approve` are: a
    `FOR UPDATE` re-read before deciding.
    """
    await session.refresh(project, with_for_update=True)
    if project.phase != ProjectPhase.PROTOTYPE.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Prototype generation is only available during the prototype stage.",
        )

    try:
        result = await prototype_engine.seed_and_generate(project)
    except ODError as exc:
        raise _od_error_to_http(exc) from exc

    if result.created:
        project.od_project_id = result.od_project_id
        project.od_conversation_id = result.od_conversation_id
        project.prototype_status = PrototypeStatus.GENERATING.value
        project.updated_at = datetime.now(timezone.utc)
        session.add(project)
        # U.10 seed-in: one ASSISTANT marker so the single chat thread shows the
        # stage was entered (the brief itself carries the PRD/architecture context,
        # so OD is never re-asking what Lothal already knows).
        session.add(
            Message(
                project_id=project.id,
                role=MessageRole.ASSISTANT,
                content=(
                    "Building an interactive prototype from your approved architecture. "
                    "You can refine it from here, then approve it to generate the code."
                ),
                suggestions=[],
                phase=ProjectPhase.PROTOTYPE.value,
            )
        )
        await session.flush()

    return _prototype_state_response(
        project,
        prototype_engine.StateResult(
            status=project.prototype_status,
            embed_url=prototype_engine.embed_url(project.od_project_id),
        ),
    )


@router.post(
    "/projects/{project_id}/prototype/refine",
    summary="Refine the prototype with a Lothal-side instruction",
)
async def refine_prototype(
    *, session: DbSession, project: OwnedProject, body: PrototypeRefineRequest
) -> PrototypeStateResponse:
    """Start a new OD run in the project's conversation carrying a refine instruction (Story U.6).

    The optional Lothal-side refine path (the primary one is inside OD). Only valid
    in `PROTOTYPE` (else `409`), and only once the prototype has been generated
    (else `409` — there is nothing to refine). Resumes the stored OD conversation
    and moves the status back to `GENERATING` while the new run produces.
    """
    content = body.content.strip()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Refine instruction cannot be empty.",
        )

    await session.refresh(project, with_for_update=True)
    if project.phase != ProjectPhase.PROTOTYPE.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Prototype refinement is only available during the prototype stage.",
        )
    if not project.od_project_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Generate a prototype before refining it.",
        )

    try:
        result = await prototype_engine.refine(project, content)
    except ODError as exc:
        raise _od_error_to_http(exc) from exc

    project.od_conversation_id = result.od_conversation_id
    project.prototype_status = PrototypeStatus.GENERATING.value
    project.updated_at = datetime.now(timezone.utc)
    session.add(project)
    # Record the refine turn in the single chat thread so the conversation carries
    # the prototype-stage history (the chat is the refine surface in PROTOTYPE).
    session.add(
        Message(
            project_id=project.id,
            role=MessageRole.USER,
            content=content,
            suggestions=[],
            phase=ProjectPhase.PROTOTYPE.value,
        )
    )
    session.add(
        Message(
            project_id=project.id,
            role=MessageRole.ASSISTANT,
            content="Updating the prototype with your change — it'll refresh on the right when it's ready.",
            suggestions=[],
            phase=ProjectPhase.PROTOTYPE.value,
        )
    )
    await session.flush()

    return _prototype_state_response(
        project,
        prototype_engine.StateResult(
            status=project.prototype_status,
            embed_url=prototype_engine.embed_url(project.od_project_id),
        ),
    )


@router.post(
    "/projects/{project_id}/prototype/approve",
    summary="Approve the prototype and advance to the planning stage",
)
async def approve_prototype(*, session: DbSession, project: OwnedProject) -> PrototypeApproveResponse:
    """Finalise the prototype: copy artifacts, stamp approval, advance to PLAN (Story U.7, U-PLAN).

    Only valid in `PROTOTYPE` (else `409`). Pulls the finalised OD artifacts and
    copies them into `lothal_prototype_artifact` (DB-as-source-of-truth, so the
    prototype survives independent of OD), sets `prototype_status=APPROVED` +
    `prototype_approved_at`, posts a summary into the single chat thread (Story
    U.10), and transitions the phase to `PLAN` — the verification-driven planning
    stage now sits between prototype and code generation.

    Serialized against concurrent submits with a `FOR UPDATE` re-read, like
    `generate`/`approve_diagram`.
    """
    await session.refresh(project, with_for_update=True)
    if project.phase != ProjectPhase.PROTOTYPE.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The prototype can only be approved during the prototype stage.",
        )
    # Only a generated, READY prototype can be approved — otherwise a click during
    # IDLE/GENERATING would advance to PLAN with no prototype captured.
    if not project.od_project_id or project.prototype_status != PrototypeStatus.READY.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Approve the prototype after generation has completed.",
        )

    try:
        artifacts = await prototype_engine.collect_for_approval(project)
    except ODError as exc:
        raise _od_error_to_http(exc) from exc

    for artifact in artifacts:
        session.add(
            PrototypeArtifact(
                project_id=project.id,
                od_path=artifact.od_path,
                kind=artifact.kind,
                title=artifact.title,
                manifest=artifact.manifest,
                content=artifact.content,
            )
        )

    session.add(
        Message(
            project_id=project.id,
            role=MessageRole.ASSISTANT,
            content=_approval_summary(artifacts),
            suggestions=[],
            phase=ProjectPhase.PROTOTYPE.value,
        )
    )

    project.prototype_status = PrototypeStatus.APPROVED.value
    project.prototype_approved_at = datetime.now(timezone.utc)
    project.phase = ProjectPhase.PLAN.value
    project.updated_at = datetime.now(timezone.utc)
    session.add(project)
    await session.flush()
    await session.refresh(project)
    return PrototypeApproveResponse(phase=project.phase)


# --- Plan (verification-driven PM tree, bridged to the standalone PM service) ----
#
# These endpoints ARE the canonical Lothal API for the planning stage. The tree,
# contracts, ratify gate, links, and ledger all live in the standalone Lothal PM
# service (repo realbytecode/lothal_project); the backend bridges to it via
# `pm_client` and re-exposes the routes here, scoped to the Langflow project. The
# browser never calls the PM service directly. Responses are the PM service's own
# JSON (the PM service owns the typed contract), passed through unchanged.


def _require_plan_visible(project: Project) -> None:
    """403 unless the project has reached the planning stage (the `GET /plan` gate)."""
    if project.phase not in _PLAN_VISIBLE_PHASES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The plan is not available until the planning stage begins.",
        )


def _require_plan_active(project: Project) -> None:
    """409 unless the project is *in* PLAN — the tree is editable only during the stage."""
    if project.phase != ProjectPhase.PLAN.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The plan can only be edited during the planning stage.",
        )


@router.get(
    "/projects/{project_id}/plan",
    summary="Get the planning tree (nodes + links) for the project",
)
async def get_plan(*, project: OwnedProject) -> dict[str, Any]:
    """Return a snapshot of the project's PM tree: its `plan_id`, nodes, and links.

    Phase-gated to `PLAN` and later (a read before then 403s — the plan does not
    exist yet); ownership is checked first by `OwnedProject`. The PM tree is created
    on first access (`ensure_plan`), so opening the stage always yields an (initially
    empty) tree rather than a 404.
    """
    _require_plan_visible(project)
    try:
        async with PMClient.from_env() as pm:
            plan_id = await pm.ensure_plan(str(project.id))
            nodes = await pm.list_nodes(plan_id)
            links = await pm.list_links(plan_id)
    except PMError as exc:
        raise _pm_error_to_http(exc) from exc
    return {"plan_id": plan_id, "nodes": nodes, "links": links}


@router.post(
    "/projects/{project_id}/plan/nodes",
    summary="Add a node to the planning tree",
)
async def create_plan_node(*, project: OwnedProject, body: dict[str, Any]) -> dict[str, Any]:
    """Create a node in the PM tree (PM `NodeCreate` shape). Editable only in `PLAN`."""
    _require_plan_active(project)
    try:
        async with PMClient.from_env() as pm:
            plan_id = await pm.ensure_plan(str(project.id))
            return await pm.create_node(plan_id, body)
    except PMError as exc:
        raise _pm_error_to_http(exc) from exc


@router.get(
    "/projects/{project_id}/plan/nodes/{node_id}",
    summary="Get a planning-tree node with its contract",
)
async def get_plan_node(*, project: OwnedProject, node_id: UUID) -> dict[str, Any]:
    _require_plan_visible(project)
    try:
        async with PMClient.from_env() as pm:
            plan_id = await pm.ensure_plan(str(project.id))
            return await pm.get_node(plan_id, str(node_id))
    except PMError as exc:
        raise _pm_error_to_http(exc) from exc


@router.patch(
    "/projects/{project_id}/plan/nodes/{node_id}/contract",
    summary="Edit a node's assume-guarantee contract (draft only)",
)
async def update_plan_contract(
    *, project: OwnedProject, node_id: UUID, body: dict[str, Any]
) -> dict[str, Any]:
    _require_plan_active(project)
    try:
        async with PMClient.from_env() as pm:
            plan_id = await pm.ensure_plan(str(project.id))
            return await pm.update_contract(plan_id, str(node_id), body)
    except PMError as exc:
        raise _pm_error_to_http(exc) from exc


@router.post(
    "/projects/{project_id}/plan/nodes/{node_id}/ratify",
    summary="Run the roll-up ratify gate for a node",
)
async def ratify_plan_node(*, project: OwnedProject, node_id: UUID) -> dict[str, Any]:
    _require_plan_active(project)
    try:
        async with PMClient.from_env() as pm:
            plan_id = await pm.ensure_plan(str(project.id))
            return await pm.ratify(plan_id, str(node_id))
    except PMError as exc:
        raise _pm_error_to_http(exc) from exc


@router.get(
    "/projects/{project_id}/plan/links",
    summary="List the planning tree's dependency links",
)
async def list_plan_links(*, project: OwnedProject) -> list[dict[str, Any]]:
    _require_plan_visible(project)
    try:
        async with PMClient.from_env() as pm:
            plan_id = await pm.ensure_plan(str(project.id))
            return await pm.list_links(plan_id)
    except PMError as exc:
        raise _pm_error_to_http(exc) from exc


@router.post(
    "/projects/{project_id}/plan/links",
    summary="Add a dependency link between two nodes",
)
async def create_plan_link(*, project: OwnedProject, body: dict[str, Any]) -> dict[str, Any]:
    _require_plan_active(project)
    try:
        async with PMClient.from_env() as pm:
            plan_id = await pm.ensure_plan(str(project.id))
            return await pm.create_link(plan_id, body)
    except PMError as exc:
        raise _pm_error_to_http(exc) from exc


@router.get(
    "/projects/{project_id}/plan/activity",
    summary="Get the planning tree's decision/provenance ledger",
)
async def plan_activity(*, project: OwnedProject, limit: int = 200) -> list[dict[str, Any]]:
    _require_plan_visible(project)
    try:
        async with PMClient.from_env() as pm:
            plan_id = await pm.ensure_plan(str(project.id))
            return await pm.activity(plan_id, limit=limit)
    except PMError as exc:
        raise _pm_error_to_http(exc) from exc


@router.post(
    "/projects/{project_id}/plan/approve",
    summary="Approve the plan and advance to code generation",
)
async def approve_plan(*, session: DbSession, project: OwnedProject) -> dict[str, str]:
    """Lock the plan and advance `PLAN → CODE_GENERATION`.

    Only valid in `PLAN` (else `409`), serialized against concurrent submits with a
    `FOR UPDATE` re-read like `approve_prototype`. The PM tree stays the source of
    truth; this only moves the project phase forward.
    """
    await session.refresh(project, with_for_update=True)
    _require_plan_active(project)
    project.phase = ProjectPhase.CODE_GENERATION.value
    project.updated_at = datetime.now(timezone.utc)
    session.add(project)
    await session.flush()
    await session.refresh(project)
    return {"phase": project.phase}


# --- Code --------------------------------------------------------------------


@router.get(
    "/projects/{project_id}/code",
    response_model=CodeResponse,
    responses=_NOT_IMPLEMENTED,
    summary="Get generated code files",
)
async def get_code(project: OwnedProject) -> JSONResponse:
    # Epic 4 (code generation) is not built yet, so this is still a 501 stub.
    # When it lands, its diagram input is the **D2 source** in
    # `lothal_project.diagram_d2` (or a graph compiled from it) — Epic D.12.
    # Not Mermaid (dropped in migration a6ba6bdf00b7) and not the legacy
    # `diagram_json` xyflow graph (the xyflow path was removed in D.15). There is
    # no stale diagram-input wiring here to migrate — only this contract to honour
    # once code-gen is implemented.
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
    # Epics 5.1 (ZIP) / 5.2 (GitHub export) are not built yet, so this is still a
    # 501 stub. When the delivery bundle lands, it carries the **D2 source** from
    # `lothal_project.diagram_d2` (e.g. `diagrams/diagram.d2`, optionally plus a
    # rendered `.svg`) alongside `prd.md` and `code/` — Epic D.16. It must NOT
    # bundle a Mermaid `diagrams/sequence.mmd` (the `diagram_mmd` column was
    # dropped in migration a6ba6bdf00b7). No `.mmd` wiring exists here to remove —
    # only this contract to honour once delivery is implemented.
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
