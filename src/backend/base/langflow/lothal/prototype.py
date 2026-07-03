"""The prototype engine — drives Open Design for the PROTOTYPE stage (Story U.4-U.7).

This is the orchestration layer between the prototype HTTP endpoints
(`api/v1/lothal.py`) and the OD daemon transport (`od_client.ODClient`). It owns
*what* to ask Open Design and *how to read it back*, and — like the chat phase
engines — never touches the database itself: every function takes the project
state it needs and returns plain results the endpoint persists.

The shape of the stage:

- **generate** (U.4): build a design brief from the project's PRD + approved
  architecture, create an OD project, and start a run. Idempotent — once a
  project is linked to an OD project it is reused, never duplicated.
- **state** (U.5): read OD's files + run status back into a prototype-state view
  (status, artifacts, an embeddable URL).
- **refine** (U.6): start a new OD run in the same conversation from a
  Lothal-side instruction.
- **approval collection** (U.7): pull the finalised artifacts (path + manifest +
  content) for the endpoint to copy into `lothal_prototype_artifact`.

OD's own LLM calls route back through Lothal's gateway (Story U.3); `generate`
points OD's agent at that gateway via `PATCH /api/app-config` (best-effort — a
config failure must not sink a run, since OD may already be configured).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger

from langflow.lothal.od_client import ODClient, ODError

if TYPE_CHECKING:
    from langflow.services.database.models.lothal_project.model import Project

# OD run status → our four-state lifecycle. OD has no FAILED state in
# ``PrototypeStatus`` (IDLE|GENERATING|READY|APPROVED), so a failed/canceled run
# stays GENERATING — the user can refine or retry rather than hitting a dead end.
_OD_STATUS_READY = "succeeded"
_OD_STATUS_IN_FLIGHT = frozenset({"queued", "running"})

# The OD agent Lothal drives. ``codex`` is OD's OpenAI-compatible agent, the one
# pointed at Lothal's gateway (Story U.3/U.4). Override with LOTHAL_OD_AGENT_ID;
# set it blank to let OD pick its own default agent.
_DEFAULT_OD_AGENT_ID = "codex"

# Where OD reaches Lothal's LLM gateway (OD's `OPENAI_BASE_URL`). The compose
# default targets the backend service; override for a different topology.
_DEFAULT_GATEWAY_URL = "http://backend:7860/api/v1/lothal/gateway/v1"


def _env(var: str, default: str | None = None) -> str | None:
    """An env var, stripped; an unset var returns ``default``, a blank one returns ``None``.

    Lets a deployment *omit* an optional field by setting it blank (e.g.
    ``LOTHAL_OD_AGENT_ID=`` to drop the agent override) distinctly from leaving
    it unset (which takes the default).
    """
    raw = os.getenv(var)
    if raw is None:
        return default
    return raw.strip() or None


@dataclass
class GenerateResult:
    """Outcome of seeding/generation — the OD linkage the endpoint persists.

    `created` is True only on the first seed; a re-entry that reused an existing
    OD project returns it False (so the endpoint can skip re-announcing the stage
    in the chat thread).
    """

    od_project_id: str
    od_conversation_id: str | None
    created: bool


@dataclass
class PrototypeArtifactView:
    """One OD artifact as the prototype state surfaces it (mirrors `PrototypeArtifactRead`)."""

    path: str
    kind: str
    title: str
    preview_url: str | None = None


@dataclass
class StateResult:
    """The live prototype state read back from OD (status + artifacts + the rendered design)."""

    status: str
    embed_url: str | None = None
    artifacts: list[PrototypeArtifactView] = field(default_factory=list)
    # The primary design artifact's HTML, ready to render directly (the prototype
    # pane shows this in a sandboxed iframe — the design itself, not OD's web UI).
    preview_html: str | None = None


@dataclass
class ApprovedArtifact:
    """A finalised OD artifact to copy into `lothal_prototype_artifact` on approval."""

    od_path: str
    kind: str
    title: str
    manifest: dict[str, Any] | None = None
    content: str | None = None


# --- brief -------------------------------------------------------------------


def build_brief(prd: str | None, diagram_d2: str | None, artifacts: dict[str, str] | None) -> str:
    """Compose the OD design brief from the project's PRD + approved architecture.

    The single-chat bridge (Story U.10): the brief is assembled from context the
    user already produced — the synthesised PRD and the approved architecture
    (the ADR + diagrams, or the legacy single diagram) — so OD never re-asks what
    Lothal already knows. The ADR (human-readable Markdown) leads; the D2 diagrams
    convey structure and flow.
    """
    parts: list[str] = [
        "Design an interactive UI/UX prototype for the product described below. "
        "Produce clickable prototype screens that cover the primary user flows. "
        "Use the product requirements and the approved architecture as the source of truth."
    ]

    if prd and prd.strip():
        parts.append(f"## Product requirements\n\n{prd.strip()}")

    artifacts = artifacts or {}
    adr = artifacts.get("adr.md")
    if adr and adr.strip():
        parts.append(f"## Architecture decisions\n\n{adr.strip()}")

    # The architecture diagrams as D2 source — prefer the full artifact set, fall
    # back to the legacy single diagram. They give OD the screens, entities, and
    # flow the prototype must reflect.
    diagram_blocks: list[str] = []
    for path, content in sorted(artifacts.items()):
        if path.endswith(".d2") and content and content.strip():
            diagram_blocks.append(f"### {path}\n\n```d2\n{content.strip()}\n```")
    if not diagram_blocks and diagram_d2 and diagram_d2.strip():
        diagram_blocks.append(f"```d2\n{diagram_d2.strip()}\n```")
    if diagram_blocks:
        parts.append("## Architecture diagrams\n\n" + "\n\n".join(diagram_blocks))

    return "\n\n".join(parts)


# --- OD agent wiring ---------------------------------------------------------


def _agent_cli_env(agent: str, byok_token: str | None) -> dict[str, str]:
    """The per-agent launch env for OD's `agentCliEnv` — model-agnostic BYOK injection.

    OD runs the coding agent as a local CLI and merges `agentCliEnv.<agent>` over the
    process env when it spawns it, so this is where the user's own key reaches the
    agent — the prototype-stage mirror of how the code sandbox injects the key. Each
    agent takes the credential in its own env var:

    - ``claude`` (Claude Code): the token is a Claude Code *subscription* token, so
      hand it straight to the CLI as ``CLAUDE_CODE_OAUTH_TOKEN``. The CLI runs the
      subscription natively — it adds the ``oauth-2025-04-20`` beta and calls
      Anthropic directly — so no gateway/translation is involved.
    - OpenAI-format agents (``codex``, …): route their OpenAI calls through Lothal's
      gateway (which translates to the subscription) with the key as
      ``OPENAI_API_KEY``.

    More agents slot in here as they are onboarded (Gemini, etc.). A missing token
    yields no credential entry, so OD falls back to whatever it is configured with
    (e.g. a token baked into the OD container env) — generation is never blocked on
    the user not having set their own key.
    """
    if agent == "claude":
        return {"CLAUDE_CODE_OAUTH_TOKEN": byok_token} if byok_token else {}
    # OpenAI-compatible agents transit Lothal's gateway so every model call is
    # observable/centrally controlled; OpenAI clients reject an empty key, so fall
    # back to the inbound gateway token (or a placeholder when inbound auth is off).
    gateway_url = _env("LOTHAL_GATEWAY_PUBLIC_URL", _DEFAULT_GATEWAY_URL)
    gateway_key = _env("LOTHAL_GATEWAY_TOKEN") or "lothal"
    return {"OPENAI_BASE_URL": gateway_url, "OPENAI_API_KEY": byok_token or gateway_key}


async def _configure_od_agent(od: ODClient, agent: str | None, byok_token: str | None = None) -> None:
    """Configure OD's agent — inject the user's key + pre-complete onboarding (`PUT /api/app-config`).

    Two jobs. (1) Hand OD's coding agent the credential to run on, in the env var
    that agent expects (`_agent_cli_env`): for `claude` this is the user's own
    `CLAUDE_CODE_OAUTH_TOKEN`, so the prototype stage runs on the *same* key the code
    stage does — update it once (in langflow's secret manager) and both follow. The
    token is never logged (only the failure is) and never leaves this internal call.
    (2) Flip the daemon's `onboardingCompleted` flag and pin `agentId`: OD's web UI
    bounces to its onboarding/"Sign in to Open Design Cloud" chooser whenever the
    daemon config reports `onboardingCompleted !== true`; since the daemon is
    authoritative across browsers (the web app merges it over localStorage on boot),
    setting it here means a Lothal deep-link to `/projects/<id>` lands straight on the
    project page — the user drives OD's own UI headlessly through Lothal.

    Best-effort: a config failure is logged but does not abort generation (OD may
    already be configured, or run on a token baked into its container env). `agent`
    is the resolved agent id (the caller reads it once and shares it, so the agent
    *configured* here can't drift from the one the run is *started* with); a
    blank/None agent skips the call (OD picks its own default agent).
    """
    if not agent:
        return
    body: dict[str, Any] = {
        # Skip OD's first-run onboarding / cloud sign-in chooser and select our agent,
        # so the embedded/deep-linked project page renders directly.
        "onboardingCompleted": True,
        "agentId": agent,
    }
    cli_env = _agent_cli_env(agent, byok_token)
    if cli_env:
        body["agentCliEnv"] = {agent: cli_env}
    try:
        await od.update_app_config(body)
    except ODError as exc:
        # Never interpolate the body/token — only the agent id and the error.
        logger.warning(f"could not configure OD agent {agent!r}: {exc}")


# --- generate ----------------------------------------------------------------


async def _find_od_project(od: ODClient, lothal_project_id: str) -> dict[str, Any] | None:
    """An existing OD project tagged with this Lothal project's id, or `None`.

    seed_and_generate stamps `metadata.lothalProjectId` on every OD project it
    creates. Looking it up before creating makes generation idempotent at the OD
    level: a prior attempt that created the OD project but failed before the
    linkage was persisted (e.g. the run enqueue errored) is reused on retry rather
    than orphaned + duplicated. Best-effort — if the list can't be read we fall
    through to create.
    """
    projects = await od.list_projects()
    for proj in projects:
        metadata = proj.get("metadata")
        if isinstance(metadata, dict) and metadata.get("lothalProjectId") == lothal_project_id and proj.get("id"):
            return proj
    return None


async def seed_and_generate(project: Project, byok_token: str | None = None) -> GenerateResult:
    """Seed an OD project from the brief and start a run (Story U.4).

    Idempotent at two levels: (1) if the Lothal project is already linked to an OD
    project, that linkage is returned unchanged with no OD call. (2) otherwise it
    reuses an OD project previously tagged with this project's id (so a retry after
    a create-succeeded/run-failed attempt doesn't orphan + duplicate it), creating
    one only if none exists; then it ensures a run is in flight (starting one only
    when the reused project has none). Returns the linkage for the endpoint to
    persist (with `prototype_status=GENERATING`).

    `byok_token` is the user's own model credential (their `CLAUDE_CODE_OAUTH_TOKEN`
    from langflow's secret manager, resolved by the endpoint); it is injected into
    OD's agent so the prototype runs on the user's key. `None` falls back to whatever
    OD is already configured with.
    """
    if project.od_project_id:
        return GenerateResult(
            od_project_id=project.od_project_id,
            od_conversation_id=project.od_conversation_id,
            created=False,
        )

    brief = build_brief(project.prd_content, project.diagram_d2, project.artifacts)
    agent_id = _env("LOTHAL_OD_AGENT_ID", _DEFAULT_OD_AGENT_ID)
    skill_id = _env("LOTHAL_OD_SKILL_ID")

    async with ODClient.from_env() as od:
        await _configure_od_agent(od, agent_id, byok_token)

        existing = await _find_od_project(od, str(project.id))
        if existing is not None:
            od_project_id = str(existing["id"])
        else:
            od_project = await od.create_project(
                project.name,
                # OD requires a client-supplied safe-slug id; derive a deterministic
                # one from the Lothal project id (also makes a retry's create
                # collide-or-reuse the same OD project rather than spawn a new one).
                project_id=f"lothal-{project.id}",
                skill_id=skill_id,
                metadata={"source": "lothal", "lothalProjectId": str(project.id)},
            )
            od_project_id = str(od_project["id"])

        # Ensure a usable run exists. A freshly created project has none; a reused
        # one may already (a prior attempt that got past the run enqueue) — don't
        # double-run it. But only reuse a run that is still in flight or already
        # succeeded: relinking a failed/canceled terminal run would persist
        # GENERATING and then poll forever (no run ever lands), so fall through to
        # start a fresh run in that case.
        runs = await od.list_runs(od_project_id)
        latest = _latest_run(runs)
        latest_status = str(latest.get("status") or "").lower() if latest is not None else ""
        if latest is not None and (latest_status in _OD_STATUS_IN_FLIGHT or latest_status == _OD_STATUS_READY):
            conversation_id = latest.get("conversationId")
        else:
            run = await od.start_run(
                project_id=od_project_id,
                message=brief,
                agent_id=agent_id,
                skill_id=skill_id,
            )
            conversation_id = run.get("conversationId")

    return GenerateResult(
        od_project_id=od_project_id,
        od_conversation_id=str(conversation_id) if conversation_id else None,
        created=True,
    )


# --- refine ------------------------------------------------------------------


async def refine(project: Project, instruction: str, byok_token: str | None = None) -> GenerateResult:
    """Start a new OD run in the project's conversation from a Lothal-side instruction (Story U.6).

    The primary refine path is inside OD itself; this is the secondary path — a
    chat-driven instruction becomes a new run on the stored `od_conversation_id`,
    so OD resumes the same session. The endpoint guarantees the project is already
    seeded (else it 409s), so a missing linkage here is a programming error.

    Re-applies the agent config first, so a refine picks up the user's *current*
    `byok_token` (they may have updated their key since the initial generate).
    """
    if not project.od_project_id:
        msg = "Cannot refine a prototype before it has been generated."
        raise ValueError(msg)

    agent_id = _env("LOTHAL_OD_AGENT_ID", _DEFAULT_OD_AGENT_ID)
    async with ODClient.from_env() as od:
        await _configure_od_agent(od, agent_id, byok_token)
        run = await od.start_run(
            project_id=project.od_project_id,
            message=instruction,
            conversation_id=project.od_conversation_id,
            agent_id=agent_id,
        )

    conversation_id = run.get("conversationId") or project.od_conversation_id
    return GenerateResult(
        od_project_id=project.od_project_id,
        od_conversation_id=str(conversation_id) if conversation_id else None,
        created=False,
    )


# --- state -------------------------------------------------------------------


def _latest_run(runs: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The most recent run, by `createdAt` when present, else list order (OD lists newest-last)."""
    if not runs:
        return None
    dated = [r for r in runs if r.get("createdAt")]
    if dated:
        return max(dated, key=lambda r: r["createdAt"])
    return runs[-1]


def _run_in_flight(runs: list[dict[str, Any]]) -> bool:
    """True when the latest run is queued/running (a generation/refine is active)."""
    latest = _latest_run(runs)
    return latest is not None and str(latest.get("status") or "").lower() in _OD_STATUS_IN_FLIGHT


def _derive_status(stored: str, runs: list[dict[str, Any]]) -> str:
    """Map OD's latest run status onto our lifecycle, defaulting to the stored status.

    A succeeded run means the prototype is READY; an in-flight run keeps it
    GENERATING; anything else (failed/canceled, or no runs yet) leaves the stored
    status untouched (the user can refine/retry — there is no FAILED state).
    """
    latest = _latest_run(runs)
    if latest is None:
        return stored
    od_status = str(latest.get("status") or "").lower()
    if od_status == _OD_STATUS_READY:
        return "READY"
    if od_status in _OD_STATUS_IN_FLIGHT:
        return "GENERATING"
    return stored


def _public_base() -> str | None:
    """The browser-facing OD base URL for embed/preview links, or `None` if unset.

    The internal `LOTHAL_OD_BASE_URL` (compose service name) is not reachable from
    a browser; embedding (Story U.9) needs the host-nginx-fronted public URL,
    which is a separate, optional setting. Unset → no embed/preview URLs.
    """
    base = _env("LOTHAL_OD_PUBLIC_BASE_URL")
    return base.rstrip("/") if base else None


def embed_url(od_project_id: str | None) -> str | None:
    """The OD web URL to iframe for this project (Story U.9), or `None` without a public base.

    Public so the endpoint can build it on the approved/degraded read paths (which
    don't go through `collect_state`). Pure string-building — no OD call — so it is
    safe even when OD is unreachable.
    """
    base = _public_base()
    return f"{base}/projects/{od_project_id}" if base and od_project_id else None


def preview_url(od_project_id: str | None, path: str) -> str | None:
    """A best-effort static-preview URL for one artifact (OD serves `/artifacts/*`).

    Best-effort: the exact OD preview routing is verified live in U.12, and the
    iframe embed (U.9) is the primary surface — so without a public base this is
    simply `None` and the UI lists the artifact without a deep link.
    """
    base = _public_base()
    return f"{base}/artifacts/{od_project_id}/{path.lstrip('/')}" if base and od_project_id else None


@dataclass
class _ParsedArtifact:
    """An OD file recognised as an artifact, with its fields pulled out."""

    path: str
    kind: str
    title: str
    manifest: dict[str, Any]


def _parse_artifact(file: dict[str, Any]) -> _ParsedArtifact | None:
    """Identify an OD `ProjectFile` as an artifact and extract its fields, or `None`.

    Single source of truth for "what counts as an OD artifact": only files carrying
    an `artifactManifest`/`artifactKind` qualify (the rest are plain sources). Both
    the state read (the list the user reviews) and approval (the set copied into the
    DB) go through this, so the two can never drift apart.
    """
    raw_manifest = file.get("artifactManifest") or {}
    # OD should send an object, but a non-dict would AttributeError on .get() below
    # and bypass the ODError→HTTP mapping; coerce defensively.
    manifest = raw_manifest if isinstance(raw_manifest, dict) else {}
    kind = file.get("artifactKind") or manifest.get("kind")
    path = file.get("path") or file.get("name")
    if not kind or not path:
        return None
    return _ParsedArtifact(path=str(path), kind=str(kind), title=str(manifest.get("title") or path), manifest=manifest)


def _artifact_view(file: dict[str, Any], od_project_id: str) -> PrototypeArtifactView | None:
    """Map an OD `ProjectFile` to an artifact view, or `None` if it is not an artifact."""
    parsed = _parse_artifact(file)
    if parsed is None:
        return None
    return PrototypeArtifactView(
        path=parsed.path,
        kind=parsed.kind,
        title=parsed.title,
        preview_url=preview_url(od_project_id, parsed.path),
    )


def _primary_html_path(files: list[dict[str, Any]]) -> str | None:
    """The path of the primary HTML design artifact (what the pane renders), or `None`.

    Prefers the artifact OD marked `primary`, then any HTML artifact (kind `html`,
    a `.html` path, or a manifest `entry` ending `.html`). This is the single
    screen the prototype pane renders inline.
    """
    candidates: list[tuple[bool, str]] = []
    for file in files:
        parsed = _parse_artifact(file)
        if parsed is None:
            continue
        entry = str(parsed.manifest.get("entry") or "")
        is_html = parsed.kind == "html" or parsed.path.endswith(".html") or entry.endswith(".html")
        if is_html:
            candidates.append((bool(parsed.manifest.get("primary")), parsed.path))
    if not candidates:
        return None
    candidates.sort(key=lambda c: not c[0])  # primary artifacts first
    return candidates[0][1]


async def collect_state(project: Project) -> StateResult:
    """Read OD's files + run status into a prototype-state view (Story U.5).

    Returns the stored status with no artifacts when the project has not been
    seeded yet. Once seeded, reads the artifact list and the latest run status
    from OD, derives the effective lifecycle status (GENERATING vs READY), and
    fetches the primary HTML design so the pane can render the design itself. The
    caller persists a forward status change and maps OD failures to HTTP.
    """
    if not project.od_project_id:
        return StateResult(status=project.prototype_status, embed_url=None, artifacts=[])

    async with ODClient.from_env() as od:
        files = await od.list_files(project.od_project_id)
        runs = await od.list_runs(project.od_project_id)
        preview_html: str | None = None
        primary = _primary_html_path(files)
        if primary is not None:
            try:
                preview_html = await od.get_file_content(project.od_project_id, primary)
            except ODError as exc:
                logger.warning(f"could not read prototype preview {primary!r}: {exc}")

    artifacts = [v for f in files if (v := _artifact_view(f, project.od_project_id)) is not None]
    # A prototype is "built" only once OD has produced a design artifact (the
    # primary HTML, or other artifact files). An OD run can "succeed" while the
    # agent is still working through the design brief — that completes a turn but
    # builds nothing, so it must NOT read READY (which would let Approve advance to
    # PLAN with no prototype captured). READY therefore requires an actual design
    # AND no active run; a succeeded-but-empty run stays GENERATING (the agent is
    # still gathering the brief — the user keeps interacting in the OD embed).
    has_design = preview_html is not None or bool(artifacts)
    if _run_in_flight(runs):
        status = "GENERATING"
    elif has_design:
        status = "READY"
    else:
        derived = _derive_status(project.prototype_status, runs)
        status = "GENERATING" if derived == "READY" else derived
    return StateResult(
        status=status,
        embed_url=embed_url(project.od_project_id),
        artifacts=artifacts,
        preview_html=preview_html,
    )


# --- approval ----------------------------------------------------------------


async def collect_for_approval(project: Project) -> list[ApprovedArtifact]:
    """Pull the finalised OD artifacts (path + manifest + content) to persist on approval (Story U.7).

    DB-as-source-of-truth: on approval the artifacts are copied into Lothal's own
    store so the prototype survives independent of OD. Reads the artifact files
    and their content; a file whose content can't be fetched (binary/media) keeps
    its manifest with `content=None` rather than being dropped.
    """
    if not project.od_project_id:
        return []

    async with ODClient.from_env() as od:
        files = await od.list_files(project.od_project_id)
        approved: list[ApprovedArtifact] = []
        for file in files:
            parsed = _parse_artifact(file)
            if parsed is None:
                continue
            try:
                content = await od.get_file_content(project.od_project_id, parsed.path)
            except ODError as exc:
                logger.warning(f"could not read OD artifact {parsed.path!r} content on approval: {exc}")
                content = None
            approved.append(
                ApprovedArtifact(
                    od_path=parsed.path,
                    kind=parsed.kind,
                    title=parsed.title,
                    manifest=dict(parsed.manifest) if parsed.manifest else None,
                    content=content,
                )
            )
    return approved
