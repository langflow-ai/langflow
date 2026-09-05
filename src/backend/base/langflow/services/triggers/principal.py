"""The identity a trigger-dispatched run executes as, and its fail-closed gate.

A trigger run has no caller. It executes as the trigger owner, non-interactively
— ``ExecutionPrincipal(kind="flow_owner", interactive=False)`` — carrying the
family (``trigger_push`` or ``trigger_listener``) that the execution-principal
matrix classifies.

``interactive=False`` is the load-bearing part. The shared connection resolver
already refuses a user connection to a non-interactive principal unless that row
carries ``allow_non_interactive`` (lfx ``BaseConnectionResolverService``
:meth:`authorize_principal`), and refuses anonymous principals outright. This
module runs that same check as a dispatch preflight so a trigger bound to a
connection without the opt-in fails closed *before* a job exists, instead of
failing deep inside a component where the owner would see it as a run error.

INT-6 owns stamping the principal onto every graph. Until it lands, the
dispatcher passes the family on the job request under the agreed
``execution_family`` key; INT-6's worker-side helper reads it back.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.integrations.errors import ConnectionNotAuthorizedError
from lfx.integrations.models import ConnectionRef, ConnectionResolutionRequest
from lfx.services.authorization.base import ExecutionPrincipal
from pydantic import ValidationError

from langflow.services.database.models.connection.model import Connection
from langflow.services.deps import get_connection_resolver_service
from langflow.services.triggers.constants import ACTOR_TRIGGER_DISPATCHER, FAMILY_TRIGGER_LISTENER

if TYPE_CHECKING:
    from lfx.integrations.errors import IntegrationError
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.trigger.model import Trigger


def trigger_execution_principal(trigger: Trigger, *, family: str = FAMILY_TRIGGER_LISTENER) -> ExecutionPrincipal:
    """Build the principal a dispatched run executes under.

    Never ``anonymous_public`` and never ``unknown``: a trigger with no
    resolvable owner is a trigger that does not run, which the ``user_id`` NOT
    NULL column on ``trigger`` already guarantees at the schema level.
    """
    return ExecutionPrincipal(
        kind="flow_owner",
        user_id=str(trigger.user_id),
        actor_id=str(trigger.user_id),
        family=family,
        interactive=False,
        actor_label=ACTOR_TRIGGER_DISPATCHER,
    )


async def connection_preflight(
    session: AsyncSession,
    trigger: Trigger,
    *,
    family: str = FAMILY_TRIGGER_LISTENER,
) -> IntegrationError | None:
    """Return the denial an unattended run would hit, or None when it may proceed.

    Only triggers that name a connection are checked; a trigger whose flow
    resolves connections by handle is authorized inside the run, by the same
    resolver, with the same principal.
    """
    if trigger.connection_id is None:
        return None
    row = await session.get(Connection, trigger.connection_id)
    if row is None:
        # A deleted connection is a configuration failure, not an authorization
        # one; the run will surface it through the resolver's own unresolved
        # error. Nothing to pre-deny here.
        return None
    resolver = get_connection_resolver_service()
    try:
        request = ConnectionResolutionRequest(
            ref=ConnectionRef(provider=row.provider_key, name=row.name),
            principal=trigger_execution_principal(trigger, family=family),
            required_scopes=frozenset(),
        )
    except ValidationError:
        # A row whose handle does not even parse cannot be authorized. Fail
        # closed rather than letting the exception escape and leave the event
        # claimed until its lease expires.
        return ConnectionNotAuthorizedError(provider=row.provider_key)
    return resolver.authorize_principal(
        request,
        connection_owner_id=str(row.owner_id) if row.owner_id is not None else None,
        owner_kind=row.ownership_mode,
        allow_non_interactive=row.allow_non_interactive,
    )
