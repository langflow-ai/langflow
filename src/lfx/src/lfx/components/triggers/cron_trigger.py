"""Cron Trigger component.

A trigger that fires the surrounding flow on a recurring schedule.
The component lives in the flow canvas like any other node; its
configuration is the source of truth and is read by the in-process
trigger worker — there is no parallel registry table.

Design notes:

* ``name = "CronTrigger"`` is the immutable identifier. It is used
  both by the backend detection helper (``services.triggers.discovery``)
  and as the prefix of the node id in ``flow.data`` (e.g.
  ``"CronTrigger-abc12"``). Renaming would be a breaking change for
  every saved flow.
* The canvas UX is intentionally NOT raw cron syntax. A
  ``schedule_mode`` dropdown drives which friendly parameters
  (interval, time of day, day of week) are visible; the actual
  ``cron_expression`` field is derived from those inputs via
  :func:`compose_cron` and is only directly editable when the user
  picks the ``Custom (cron expression)`` mode.
* The single source of truth on the wire — what gets read by the
  trigger worker and the discovery helper — is still
  ``cron_expression``. The mode + parameter fields are the *user-
  facing* representation; the derived cron is the *system-facing*
  representation. They are kept in sync at every input change by
  :meth:`update_build_config`.
* The ``fire_time`` input is invisible to manual canvas runs. The
  worker injects it via the same tweak mechanism the webhook handler
  uses, so the component can pass the actual fire instant downstream
  without needing a dedicated runtime channel.
* Manual canvas runs (Play button) are a no-op: the component emits
  the current UTC time as the event message — matches the Webhook
  component's 'inert outside the trigger path' contract.
* No ``is_active`` field: the presence of the node in the flow IS the
  activation. To pause a trigger, the user removes the node (or the
  containing flow).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from lfx.components.triggers.constants import (
    COMMON_TIMEZONES,
    DEFAULT_CRON_EXPRESSION,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_TIMEZONE,
    MAX_ATTEMPTS_LIMIT,
)
from lfx.components.triggers.cron_builder import (
    DAYS_OF_WEEK,
    MODE_CUSTOM,
    MODE_DAILY,
    MODE_EVERY_N_HOURS,
    MODE_EVERY_N_MINUTES,
    MODE_WEEKLY,
    SCHEDULE_MODES,
    compose_cron,
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

# Default time-of-day for the Daily / Weekly modes — 09:00 in the
# trigger's selected timezone. Picked because it's a sensible
# business-hours default and matches what most cron tutorials show.
_DEFAULT_TIME_OF_DAY = "09:00"
_DEFAULT_DAY_OF_WEEK = "Monday"
_DEFAULT_MINUTES_INTERVAL = 5
_DEFAULT_HOURS_INTERVAL = 1


class CronTriggerComponent(Component):
    display_name = "Cron Trigger"
    description = "Fire this flow on a recurring schedule."
    documentation: str = "https://docs.langflow.org/component-cron-trigger"
    # The class name pinned by the persisted node id. Do not rename.
    name = "CronTrigger"
    icon = "clock"

    inputs = [
        # ----- friendly mode picker (shown to everyone) -----
        DropdownInput(
            name="schedule_mode",
            display_name="Schedule",
            info="Pick how often this flow should run.",
            options=list(SCHEDULE_MODES),
            value=MODE_EVERY_N_MINUTES,
            real_time_refresh=True,
        ),
        # ----- mode-specific parameters (one is visible at a time) -----
        IntInput(
            name="minutes_interval",
            display_name="Every (minutes)",
            info="Run every N minutes.",
            value=_DEFAULT_MINUTES_INTERVAL,
            range_spec=RangeSpec(min=1, max=59, step=1),
            real_time_refresh=True,
        ),
        IntInput(
            name="hours_interval",
            display_name="Every (hours)",
            info="Run every N hours, on the hour.",
            value=_DEFAULT_HOURS_INTERVAL,
            range_spec=RangeSpec(min=1, max=23, step=1),
            real_time_refresh=True,
            show=False,
        ),
        MessageTextInput(
            name="time_of_day",
            display_name="Time of day (HH:MM)",
            info="24-hour clock, in the timezone chosen below.",
            value=_DEFAULT_TIME_OF_DAY,
            input_types=[],
            real_time_refresh=True,
            show=False,
        ),
        DropdownInput(
            name="day_of_week",
            display_name="Day of week",
            options=list(DAYS_OF_WEEK),
            value=_DEFAULT_DAY_OF_WEEK,
            real_time_refresh=True,
            show=False,
        ),
        MessageTextInput(
            name="cron_expression",
            display_name="Cron Expression",
            info=(
                "Auto-filled from the Schedule above. Editable only when "
                "Schedule is set to 'Custom (cron expression)'. Five-field "
                "POSIX cron: 'minute hour day month weekday'."
            ),
            value=DEFAULT_CRON_EXPRESSION,
            input_types=[],
            show=False,
        ),
        # ----- always-visible secondary controls -----
        DropdownInput(
            name="timezone",
            display_name="Timezone",
            info=(
                "IANA timezone name used to interpret the schedule. "
                "Type any IANA name to use a timezone not in the list."
            ),
            options=list(COMMON_TIMEZONES),
            value=DEFAULT_TIMEZONE,
            combobox=True,
        ),
        # ----- advanced (collapsed by default) -----
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

    # ------------------------------------------------------------------ #
    #  Dynamic build config — show/hide fields by mode, derive cron
    # ------------------------------------------------------------------ #

    # Map mode → list of "user-editable parameter field names" that
    # should be visible in that mode. Centralised so the visibility
    # rule lives in exactly one place and the matching unit tests
    # can assert against the same dict.
    _MODE_VISIBLE_FIELDS: dict[str, tuple[str, ...]] = {
        MODE_EVERY_N_MINUTES: ("minutes_interval",),
        MODE_EVERY_N_HOURS: ("hours_interval",),
        MODE_DAILY: ("time_of_day",),
        MODE_WEEKLY: ("day_of_week", "time_of_day"),
        MODE_CUSTOM: ("cron_expression",),
    }

    # The full set of fields that ``update_build_config`` toggles.
    # Anything not in here keeps its declared visibility.
    _TOGGLEABLE_FIELDS: tuple[str, ...] = (
        "minutes_interval",
        "hours_interval",
        "time_of_day",
        "day_of_week",
        "cron_expression",
    )

    def update_build_config(
        self,
        build_config: dict,
        field_value: Any,
        field_name: str | None = None,
    ) -> dict:
        """React to canvas edits: toggle visibility + derive cron.

        Called by the canvas whenever an input flagged with
        ``real_time_refresh=True`` changes. Two responsibilities:

        1. Show only the parameter fields relevant to the current
           ``schedule_mode``.
        2. Re-derive ``cron_expression`` from the structured
           parameters whenever the user is NOT in custom mode. In
           custom mode the user types the cron themselves and we
           leave the field alone.
        """
        # Current mode value: either the one being set in this call,
        # or the existing one in the build_config (when the user
        # tweaked an interval / time field, not the mode itself).
        if field_name == "schedule_mode":
            mode = field_value
        else:
            mode = build_config.get("schedule_mode", {}).get("value", MODE_EVERY_N_MINUTES)

        visible = set(self._MODE_VISIBLE_FIELDS.get(mode, ()))
        for fname in self._TOGGLEABLE_FIELDS:
            if fname in build_config:
                build_config[fname]["show"] = fname in visible

        # Derive cron from the structured fields (skip in custom mode —
        # the user owns the cron_expression there).
        if mode != MODE_CUSTOM:
            build_config["cron_expression"]["value"] = compose_cron(
                mode=mode,
                minutes_interval=build_config.get("minutes_interval", {}).get(
                    "value", _DEFAULT_MINUTES_INTERVAL
                ),
                hours_interval=build_config.get("hours_interval", {}).get(
                    "value", _DEFAULT_HOURS_INTERVAL
                ),
                time_of_day=build_config.get("time_of_day", {}).get(
                    "value", _DEFAULT_TIME_OF_DAY
                ),
                day_of_week=build_config.get("day_of_week", {}).get(
                    "value", _DEFAULT_DAY_OF_WEEK
                ),
            )

        return build_config

    # ------------------------------------------------------------------ #
    #  Execution
    # ------------------------------------------------------------------ #

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
