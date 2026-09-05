"""What a fired trigger actually runs.

Three shapes, decided per event:

* **saved flow** — the default. The run builds from the flow as it stands.
* **pinned flow version** — ``trigger.flow_version_id`` set. The run carries the
  pinned version's canvas data, so edits to the flow do not change what fires
  until the pin moves. This is the "pin to v3" story.
* **deployment** — stored, never dispatched in 1.13. Deployments execute through
  provider adapters as an external data plane: a different principal
  (deployment owner, not flow owner), a provider run id instead of a ``Job``
  row, and no way to write a job id back into the ledger. Rather than silently
  running the flow instead, dispatch raises a typed
  :class:`BindingUnsupportedError` so the owner sees what did not happen.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.trigger.schemas import TriggerBindingTarget
from langflow.services.triggers.errors import BindingUnsupportedError

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.trigger.model import Trigger


@dataclass(frozen=True)
class ResolvedBinding:
    """The flow a run targets, plus the canvas data to run when pinned."""

    flow_id: UUID
    flow_version_id: UUID | None
    data: dict[str, Any] | None

    @property
    def is_pinned(self) -> bool:
        return self.flow_version_id is not None


async def resolve_binding(session: AsyncSession, trigger: Trigger) -> ResolvedBinding:
    """Resolve what this trigger fires, or raise for a target we do not dispatch."""
    if trigger.binding_target == TriggerBindingTarget.DEPLOYMENT.value:
        raise BindingUnsupportedError(trigger.binding_target)

    if trigger.flow_version_id is None:
        return ResolvedBinding(flow_id=trigger.flow_id, flow_version_id=None, data=None)

    version = await session.get(FlowVersion, trigger.flow_version_id)
    if version is None or version.flow_id != trigger.flow_id:
        # A pin that no longer resolves must not silently degrade into "run the
        # current flow": the whole point of a pin is that the owner chose which
        # version runs.
        msg = "pinned_version_missing"
        raise BindingUnsupportedError(msg)
    return ResolvedBinding(flow_id=trigger.flow_id, flow_version_id=version.id, data=version.data)
