"""A trigger listens only through a connection its owner owns.

A provider trigger turns a connection into a stream of that account's data - a
Slack workspace's messages, a mailbox, a drive - and writes it into a ledger the
trigger's flow readers can see. So the connection a trigger names must belong to
the trigger's owner (who is also the flow owner a triggered run executes as).

Two shapes are refused:

* **another user's connection.** Without this, anyone who can write a flow could
  point a trigger at a colleague's Slack connection and read their workspace.
* **an instance connection.** The instance floor lets every user *reference* an
  instance connection so an admin-configured bot can post on their behalf; that
  is a narrow write grant. A trigger on it would be a broad read grant nobody
  approved. Triggers on instance connections wait for an explicit policy
  (TRG-8).

The rule is checked where a trigger acquires a connection (reconciliation, the
owner API, enable) and again where one is used (the listener's desired state and
every fan-out query), so a row written before the rule existed cannot slip past.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import and_

from langflow.services.database.models.connection.model import Connection
from langflow.services.database.models.connection.schemas import ConnectionOwnershipMode
from langflow.services.database.models.trigger.model import Trigger

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.sql.elements import ColumnElement
    from sqlmodel.ext.asyncio.session import AsyncSession


class TriggerConnectionNotOwnedError(ValueError):
    """The connection does not exist or is not owned by the trigger's owner."""

    code = "trigger_connection_not_owned"

    def __init__(self) -> None:
        super().__init__(
            "A trigger can only use a connection its owner owns. Choose one of your own connections; "
            "shared and instance connections cannot back a trigger."
        )


def owned_by_trigger_owner() -> ColumnElement[bool]:
    """SQL clause for a ``Trigger`` joined to its ``Connection``: the owner owns it."""
    return and_(
        Connection.ownership_mode == ConnectionOwnershipMode.USER.value,
        Connection.owner_id == Trigger.user_id,
    )


def is_owned_by(connection: Connection, owner_id: UUID) -> bool:
    """The same rule as :func:`owned_by_trigger_owner`, for a loaded row."""
    return connection.ownership_mode == ConnectionOwnershipMode.USER.value and connection.owner_id == owner_id


async def require_owned_connection(session: AsyncSession, *, connection_id: UUID, owner_id: UUID) -> Connection:
    """Load ``connection_id`` or raise when ``owner_id`` does not own it.

    A missing row and a foreign row raise the same error, so the answer is not
    an oracle for connection ids that belong to someone else.
    """
    row = await session.get(Connection, connection_id)
    if row is None or not is_owned_by(row, owner_id):
        raise TriggerConnectionNotOwnedError
    return row
