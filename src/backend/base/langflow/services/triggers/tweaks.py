"""Build the ``SimplifiedAPIRequest`` payload for a CronTrigger fire.

Sole reason for this module's existence: the worker dispatches via
``simple_run_flow`` (same path the HTTP run endpoint uses) and needs
to inject the fire timestamp into the CronTrigger node's ``fire_time``
input. The tweak format that ``simple_run_flow`` accepts is shared
with the webhook handler, so we use the same shape here for
consistency.

Anything related to "how the worker talks to the executor" lives here
so the worker stays focused on queue mechanics and the executor stays
agnostic of the trigger system.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

    from langflow.services.triggers.discovery import CronTriggerConfig


def build_simplified_request_kwargs(
    config: CronTriggerConfig,
    *,
    fire_time: datetime,
) -> dict[str, Any]:
    """Return kwargs for constructing a ``SimplifiedAPIRequest``.

    Caller does the import + instantiation so the simplified-request
    class stays loaded only when actually needed (avoids pulling the
    api.v1 module at worker import time, which would create a circular
    import with the endpoint module that hosts ``simple_run_flow``).
    """
    payload = dict(config.payload or {})
    tweaks = dict(payload.get("tweaks") or {})
    component_tweaks = dict(tweaks.get(config.component_id) or {})
    component_tweaks.setdefault("fire_time", fire_time.isoformat())
    tweaks[config.component_id] = component_tweaks

    return {
        "input_value": payload.get("input_value"),
        "input_type": payload.get("input_type"),
        "output_type": payload.get("output_type"),
        "output_component": payload.get("output_component"),
        "tweaks": tweaks,
        "session_id": payload.get("session_id"),
    }
