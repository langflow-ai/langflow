"""Per-family execution principals for dependency (connection) resolution.

Every entry point in ``scripts/ci/execution_principal_matrix.json`` stamps the
graph it is about to run with the identity that governs connection resolution.
An unstamped graph carries ``ExecutionPrincipal.unknown()`` and the portable
deny floor in ``lfx.services.connection.base`` refuses every connection, so a
missed stamping site fails closed rather than resolving someone else's
credential.

The family strings here are the matrix's ``family`` values verbatim. They are
the canonical names: the ``execution_protocol`` ContextVar is telemetry and must
never be used for an authorization decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from lfx.services.authorization.base import PUBLIC_ANONYMOUS_ACTOR_ID, ExecutionPrincipal

if TYPE_CHECKING:
    from uuid import UUID

FAMILY_INTERACTIVE_CHAT = "interactive_chat"
FAMILY_LEGACY_PUBLIC_CHAT = "legacy_public_chat"
FAMILY_V1_RUN = "v1_run"
FAMILY_WEBHOOK = "webhook"
FAMILY_OPENAI_RESPONSES = "openai_responses"
FAMILY_LEGACY_MCP = "legacy_mcp"
FAMILY_MCP_PROJECTS = "mcp_projects"
FAMILY_A2A = "a2a"
FAMILY_VOICE = "voice"
FAMILY_DEPLOYMENTS = "deployments"
FAMILY_WORKFLOW_V2 = "workflow_v2"
FAMILY_WORKFLOW_HITL_V2 = "workflow_hitl_v2"
FAMILY_WORKFLOW_PUBLIC_V2 = "workflow_public_v2"

EXECUTION_FAMILIES = frozenset(
    {
        FAMILY_INTERACTIVE_CHAT,
        FAMILY_LEGACY_PUBLIC_CHAT,
        FAMILY_V1_RUN,
        FAMILY_WEBHOOK,
        FAMILY_OPENAI_RESPONSES,
        FAMILY_LEGACY_MCP,
        FAMILY_MCP_PROJECTS,
        FAMILY_A2A,
        FAMILY_VOICE,
        FAMILY_DEPLOYMENTS,
        FAMILY_WORKFLOW_V2,
        FAMILY_WORKFLOW_HITL_V2,
        FAMILY_WORKFLOW_PUBLIC_V2,
    }
)

# Connection-resolution vocabulary shared with the CI matrix. INT-6 owns both.
RESOLUTION_OWNER_OR_EXPLICIT_SHARE = "owner_or_explicit_share"
RESOLUTION_OWNER_ONLY = "owner_only"
RESOLUTION_OWNER_NON_INTERACTIVE_OPT_IN = "owner_non_interactive_opt_in"
RESOLUTION_JOB_OWNER_RERESOLVED = "job_owner_reresolved"
RESOLUTION_NEVER = "never"


@dataclass(frozen=True, slots=True)
class _FamilyRule:
    """How one matrix family maps onto an ``ExecutionPrincipal``."""

    kind: str
    interactive: bool
    allow_explicit_shares: bool
    connection_resolution: str


_FAMILY_RULES: dict[str, _FamilyRule] = {
    FAMILY_INTERACTIVE_CHAT: _FamilyRule(
        kind="actor",
        interactive=True,
        allow_explicit_shares=True,
        connection_resolution=RESOLUTION_OWNER_OR_EXPLICIT_SHARE,
    ),
    FAMILY_LEGACY_PUBLIC_CHAT: _FamilyRule(
        kind="anonymous_public",
        interactive=False,
        allow_explicit_shares=False,
        connection_resolution=RESOLUTION_NEVER,
    ),
    FAMILY_V1_RUN: _FamilyRule(
        kind="actor",
        interactive=True,
        allow_explicit_shares=True,
        connection_resolution=RESOLUTION_OWNER_OR_EXPLICIT_SHARE,
    ),
    # The webhook caller is never the human at the keyboard: the published flow's
    # owner runs it unattended, so the owner's connection must carry the explicit
    # per-connection non-interactive opt-in.
    FAMILY_WEBHOOK: _FamilyRule(
        kind="flow_owner",
        interactive=False,
        allow_explicit_shares=False,
        connection_resolution=RESOLUTION_OWNER_NON_INTERACTIVE_OPT_IN,
    ),
    FAMILY_OPENAI_RESPONSES: _FamilyRule(
        kind="actor",
        interactive=True,
        allow_explicit_shares=True,
        connection_resolution=RESOLUTION_OWNER_OR_EXPLICIT_SHARE,
    ),
    # Legacy MCP and MCP projects admit only the transport actor's own flows;
    # a delegated share is not admitted there and must not resolve either.
    FAMILY_LEGACY_MCP: _FamilyRule(
        kind="actor",
        interactive=True,
        allow_explicit_shares=False,
        connection_resolution=RESOLUTION_OWNER_ONLY,
    ),
    FAMILY_MCP_PROJECTS: _FamilyRule(
        kind="actor",
        interactive=True,
        allow_explicit_shares=False,
        connection_resolution=RESOLUTION_OWNER_ONLY,
    ),
    FAMILY_A2A: _FamilyRule(
        kind="anonymous_public",
        interactive=False,
        allow_explicit_shares=False,
        connection_resolution=RESOLUTION_NEVER,
    ),
    FAMILY_VOICE: _FamilyRule(
        kind="actor",
        interactive=True,
        allow_explicit_shares=True,
        connection_resolution=RESOLUTION_OWNER_OR_EXPLICIT_SHARE,
    ),
    FAMILY_DEPLOYMENTS: _FamilyRule(
        kind="deployment_owner",
        interactive=False,
        allow_explicit_shares=False,
        connection_resolution=RESOLUTION_OWNER_NON_INTERACTIVE_OPT_IN,
    ),
    FAMILY_WORKFLOW_V2: _FamilyRule(
        kind="actor",
        interactive=True,
        allow_explicit_shares=True,
        connection_resolution=RESOLUTION_OWNER_OR_EXPLICIT_SHARE,
    ),
    FAMILY_WORKFLOW_HITL_V2: _FamilyRule(
        kind="job_owner",
        interactive=False,
        allow_explicit_shares=False,
        connection_resolution=RESOLUTION_JOB_OWNER_RERESOLVED,
    ),
    FAMILY_WORKFLOW_PUBLIC_V2: _FamilyRule(
        kind="anonymous_public",
        interactive=False,
        allow_explicit_shares=False,
        connection_resolution=RESOLUTION_NEVER,
    ),
}

CONNECTION_RESOLUTION_BY_FAMILY = {family: rule.connection_resolution for family, rule in _FAMILY_RULES.items()}


def _identifier(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None


def _user_identifier(user: Any) -> str | None:
    return _identifier(getattr(user, "id", None) if user is not None else None)


def execution_principal_for(
    family: str,
    *,
    user: Any = None,
    user_id: str | UUID | None = None,
    flow_owner_id: str | UUID | None = None,
    interactive: bool | None = None,
    end_user_id: str | None = None,
) -> ExecutionPrincipal:
    """Build the principal a matrix family runs under.

    ``user`` is the route's effective execution user (``User``/``UserRead``);
    ``user_id`` overrides it when a route has only an id. A caller identified as
    the stable anonymous actor always collapses to ``anonymous_public`` no matter
    which family asked, so a public admission can never be widened by a caller
    passing an interactive family name.

    ``interactive`` overrides the family default for the one route that varies
    inside its family: MCP project transports authenticated with ``auth_type=none``
    run unattended and must be treated as non-interactive.
    """
    rule = _FAMILY_RULES.get(family)
    if rule is None:
        msg = (
            f"unknown execution family {family!r}; add it to EXECUTION_FAMILIES and to "
            "scripts/ci/execution_principal_matrix.json"
        )
        raise ValueError(msg)

    actor_id = _identifier(user_id) if user_id is not None else _user_identifier(user)
    is_anonymous_actor = actor_id is not None and actor_id == str(PUBLIC_ANONYMOUS_ACTOR_ID)
    effective_interactive = rule.interactive if interactive is None else interactive

    if rule.kind == "anonymous_public" or is_anonymous_actor:
        # No user_id: the anonymous actor id is a marker, never a credential owner.
        return ExecutionPrincipal(
            kind="anonymous_public",
            actor_id=str(PUBLIC_ANONYMOUS_ACTOR_ID),
            family=family,
            interactive=False,
            end_user_id=end_user_id,
            allow_explicit_shares=False,
        )

    # flow_owner / deployment_owner / job_owner run as the resource owner, not the
    # caller. Fall back to the actor only when the route could not supply an owner.
    owner_id = _identifier(flow_owner_id)
    dependency_user_id = owner_id if rule.kind in {"flow_owner", "deployment_owner", "job_owner"} else actor_id
    if dependency_user_id is None:
        dependency_user_id = actor_id

    return ExecutionPrincipal(
        kind=rule.kind,  # type: ignore[arg-type]
        user_id=dependency_user_id,
        actor_id=actor_id,
        family=family,
        interactive=effective_interactive,
        end_user_id=end_user_id,
        allow_explicit_shares=rule.allow_explicit_shares,
    )


def execution_principal_for_job(
    *,
    user_id: str | UUID | None,
    family: str = FAMILY_WORKFLOW_HITL_V2,
) -> ExecutionPrincipal:
    """Graph-free principal for worker paths that own a job row but no graph.

    Background/HITL resumes and knowledge-base ingestion jobs (``JobType.INGESTION``,
    whose sources are not Components and therefore have no ``self.graph``) resolve
    connections through this. It is deliberately non-interactive: nobody is present
    to complete an OAuth prompt, so the owner's connection needs the per-connection
    non-interactive opt-in.
    """
    return execution_principal_for(family, user_id=user_id, flow_owner_id=user_id, interactive=False)


def stamp_execution_principal(graph: Any, principal: ExecutionPrincipal) -> Any:
    """Attach ``principal`` to ``graph`` and return the graph.

    Safe on ``None`` so call sites that may not have built a graph stay linear.
    """
    if graph is not None:
        graph.execution_principal = principal
    return graph
