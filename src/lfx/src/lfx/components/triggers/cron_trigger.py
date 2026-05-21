"""Cron Trigger component.

A trigger that fires the surrounding flow on a recurring cron schedule.
The component lives in the flow canvas like any other node; its
configuration (``cron_expression``, ``timezone``) is the source of
truth and is read by the in-process trigger worker — there is no
parallel registry table.

Design notes:

* ``name = "CronTrigger"`` is the immutable identifier. It is used
  both by the backend detection helper (``services.triggers.discovery``)
  and as the prefix of the node id in ``flow.data`` (e.g.
  ``"CronTrigger-abc12"``). Renaming would be a breaking change for
  every saved flow.
* The ``fire_time`` input is invisible to manual canvas runs. The
  worker injects it via the same tweak mechanism the webhook handler
  uses, so the component can pass the actual fire instant downstream
  without needing a dedicated runtime channel.
* Manual canvas runs (Play button) are a no-op: the component emits
  the current UTC time as the event message. That's deliberate —
  matches the Webhook behaviour, which is also inert outside its HTTP
  trigger path.
* No ``is_active`` field: the presence of the node in the flow IS the
  activation. To pause a trigger, the user removes the node (or the
  containing flow). Simpler invariant, less to keep in sync.
"""

from __future__ import annotations

from datetime import datetime, timezone

from lfx.components.triggers.constants import (
    COMMON_TIMEZONES,
    DEFAULT_CRON_EXPRESSION,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_TIMEZONE,
    MAX_ATTEMPTS_LIMIT,
)
from lfx.custom.custom_component.component import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.io import (
    DropdownInput,
    IntInput,
    MessageTextInput,
    MultilineInput,
    Output,
)
from lfx.schema.message import Message


class CronTriggerComponent(Component):
    display_name = "Cron Trigger"
    description = "Fire this flow on a recurring cron schedule."
    documentation: str = "https://docs.langflow.org/component-cron-trigger"
    # The class name pinned by the persisted node id. Do not rename.
    name = "CronTrigger"
    icon = "clock"

    inputs = [
        MessageTextInput(
            name="cron_expression",
            display_name="Cron Expression",
            info=(
                "Standard 5-field POSIX cron (minute hour day month weekday). "
                "Example: '*/5 * * * *' fires every five minutes."
            ),
            value=DEFAULT_CRON_EXPRESSION,
            required=True,
            # No upstream connection — this is a config value, not data.
            input_types=[],
        ),
        DropdownInput(
            name="timezone",
            display_name="Timezone",
            info=(
                "IANA timezone name used to interpret the cron expression. "
                "Type any IANA name to use a timezone not in the list."
            ),
            options=list(COMMON_TIMEZONES),
            value=DEFAULT_TIMEZONE,
            combobox=True,
        ),
        IntInput(
            name="max_attempts",
            display_name="Max Attempts",
            info="Retry budget per fire. Failed runs are retried with exponential backoff up to this many times.",
            value=DEFAULT_MAX_ATTEMPTS,
            range_spec=RangeSpec(min=1, max=MAX_ATTEMPTS_LIMIT, step=1),
            advanced=True,
        ),
        MultilineInput(
            name="payload",
            display_name="Payload (JSON)",
            info=(
                "Optional JSON object merged into the SimplifiedAPIRequest fields "
                "(input_value, input_type, output_type, tweaks, session_id) when the trigger fires."
            ),
            advanced=True,
            input_types=[],
        ),
        # Worker-populated. Empty on manual canvas runs.
        MessageTextInput(
            name="fire_time",
            display_name="Fire Time",
            info="Set by the trigger worker at fire time. Empty on manual runs.",
            advanced=True,
            input_types=[],
        ),
    ]

    outputs = [
        Output(
            display_name="Trigger Event",
            name="event",
            method="build_event",
        ),
    ]

    def build_event(self) -> Message:
        """Emit the event message that downstream nodes consume.

        Returns the worker-injected ``fire_time`` when present, otherwise
        the current UTC instant. Either value is a tz-aware ISO 8601
        string, so downstream components see a consistent shape
        regardless of how the flow was kicked off.
        """
        fire_time = (self.fire_time or "").strip()
        text = fire_time or datetime.now(timezone.utc).isoformat()
        self.status = f"Cron trigger fired at {text}"
        return Message(text=text)
