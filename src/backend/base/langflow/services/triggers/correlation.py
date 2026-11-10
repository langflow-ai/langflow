"""Session-id derivation for trigger runs.

Two events from one provider conversation must start two runs that *share* a
session, so an agent has memory across the thread. Two ticks of a schedule have
no conversation at all, so they get fresh sessions unless the owner asked for a
shared one.

The precedence is deliberate:

1. the provider conversation key carried on the event payload
   (``session_key``, set by TRG-5/TRG-6 adapters as ``{provider}:{kind}:{id}``),
2. the trigger's ``session_policy``:
   ``shared`` -> ``trigger:{trigger_id}`` (one session for every run),
   ``per_event`` -> ``trigger:{trigger_id}:{event_id}`` (a fresh session each).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from langflow.services.database.models.trigger.schemas import TriggerSessionPolicy
from langflow.services.triggers.constants import SESSION_PREFIX

if TYPE_CHECKING:
    from langflow.services.database.models.trigger.model import Trigger, TriggerEvent

#: Payload key a provider adapter sets to carry its conversation identity.
PAYLOAD_SESSION_KEY = "session_key"


def derive_session_id(trigger: Trigger, event: TriggerEvent) -> str:
    """Return the session id the dispatched run should use."""
    payload = event.payload or {}
    provider_key = payload.get(PAYLOAD_SESSION_KEY)
    if isinstance(provider_key, str) and provider_key and not provider_key.isspace():
        return provider_key
    if trigger.session_policy == TriggerSessionPolicy.SHARED.value:
        return f"{SESSION_PREFIX}:{trigger.id}"
    return f"{SESSION_PREFIX}:{trigger.id}:{event.id}"
