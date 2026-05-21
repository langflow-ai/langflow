"""Cron Trigger component.

A trigger that fires the surrounding flow on a recurring schedule.
The component is a *marker*: it lives in the canvas to declare "this
flow runs on this schedule" and to hold the schedule configuration.
It does NOT participate in the data graph — there is no output handle
and no upstream connections to make. The flow itself owns its
ChatInput / Input / Agent / whatever, and runs to completion every
time the worker fires it.

Design notes:

* ``name = "CronTrigger"`` is the immutable identifier. It is used
  both by the backend detection helper (``services.triggers.discovery``)
  and as the prefix of the node id in ``flow.data`` (e.g.
  ``"CronTrigger-abc12"``). Renaming would be a breaking change for
  every saved flow.
* The canvas UX is binary: an ``at_specific_time`` toggle picks
  between "fire every N units" (intervals — timezone-agnostic) and
  "fire daily at HH:MM in a specific timezone". Each path shows only
  the fields it needs.
* ``cron_expression`` remains the single source of truth on the wire
  — what gets read by the trigger worker and the discovery helper.
  The visible fields are the *user-facing* representation; the
  derived cron is the *system-facing* representation. They are kept
  in sync at every input change by :meth:`update_build_config`.
* No ``outputs``: the trigger does not feed downstream nodes. It
  kicks the whole flow off when the worker fires; the flow uses its
  own inputs.
* No ``is_active`` field: the presence of the node in the flow IS the
  activation. To pause a trigger, the user removes the node (or the
  containing flow).
"""

from __future__ import annotations

from typing import Any

from lfx.components.triggers.constants import (
    COMMON_TIMEZONES,
    DEFAULT_CRON_EXPRESSION,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_TIMEZONE,
    MAX_ATTEMPTS_LIMIT,
)
from lfx.components.triggers.cron_builder import (
    INTERVAL_UNITS,
    UNIT_MINUTES,
    compose_cron,
)
from lfx.custom.custom_component.component import Component
from lfx.field_typing.range_spec import RangeSpec
from lfx.io import BoolInput, DropdownInput, IntInput, MessageTextInput

# Defaults sized to be sensible the moment the user drops the
# component on the canvas — without typing anything else, the
# trigger is already configured for "every 5 minutes".
_DEFAULT_INTERVAL_VALUE = 5
_DEFAULT_TIME_OF_DAY = "09:00"


class CronTriggerComponent(Component):
    display_name = "Cron Trigger"
    description = "Fire this flow on a recurring schedule."
    documentation: str = "https://docs.langflow.org/component-cron-trigger"
    # The class name pinned by the persisted node id. Do not rename.
    name = "CronTrigger"
    icon = "clock"

    inputs = [
        # ----- top-level switch -----
        BoolInput(
            name="at_specific_time",
            display_name="Schedule at specific time",
            info=(
                "Off (default): fire at fixed intervals (every N minutes or hours). "
                "On: fire at a specific time of day in a chosen timezone."
            ),
            value=False,
            real_time_refresh=True,
        ),
        # ----- interval branch (shown when at_specific_time is False) -----
        IntInput(
            name="interval_value",
            display_name="Every",
            info="How many units between fires.",
            value=_DEFAULT_INTERVAL_VALUE,
            range_spec=RangeSpec(min=1, max=59, step=1),
            real_time_refresh=True,
        ),
        DropdownInput(
            name="interval_unit",
            display_name="Unit",
            info="The unit paired with the 'Every' number.",
            options=list(INTERVAL_UNITS),
            value=UNIT_MINUTES,
            real_time_refresh=True,
        ),
        # ----- specific-time branch (shown when at_specific_time is True) -----
        MessageTextInput(
            name="time_of_day",
            display_name="Time of day (HH:MM)",
            info="24-hour clock, in the timezone selected below.",
            value=_DEFAULT_TIME_OF_DAY,
            input_types=[],
            real_time_refresh=True,
            show=False,
        ),
        DropdownInput(
            name="timezone",
            display_name="Timezone",
            info=(
                "IANA timezone name used to interpret the time of day. "
                "Type any IANA name to use a timezone not in the list."
            ),
            options=list(COMMON_TIMEZONES),
            value=DEFAULT_TIMEZONE,
            combobox=True,
            show=False,
        ),
        # ----- system-facing derived field (never visible) -----
        # Persisted in flow.data so the backend worker can read the
        # current cron without re-running update_build_config. Always
        # hidden; the user edits the controls above and this field
        # is recomputed for them on every change.
        MessageTextInput(
            name="cron_expression",
            display_name="Cron Expression",
            info="Auto-derived from the schedule controls above.",
            value=DEFAULT_CRON_EXPRESSION,
            input_types=[],
            show=False,
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
    ]

    # No outputs — see module docstring.
    outputs = []

    # ------------------------------------------------------------------ #
    #  Dynamic build config — show/hide fields by toggle, derive cron
    # ------------------------------------------------------------------ #

    # Field groups: which fields belong to each side of the toggle.
    # Centralised so the visibility rule lives in exactly one place
    # and the matching unit tests can assert against the same tuples.
    _INTERVAL_FIELDS: tuple[str, ...] = ("interval_value", "interval_unit")
    _SPECIFIC_TIME_FIELDS: tuple[str, ...] = ("time_of_day", "timezone")

    def update_build_config(
        self,
        build_config: dict,
        field_value: Any,
        field_name: str | None = None,
    ) -> dict:
        """React to canvas edits: toggle visibility + derive cron.

        Called by the canvas whenever an input flagged with
        ``real_time_refresh=True`` changes. Two responsibilities:

        1. Show only the field group relevant to the current
           ``at_specific_time`` value.
        2. Re-derive ``cron_expression`` from the structured controls.
        """
        if field_name == "at_specific_time":
            at_specific_time = bool(field_value)
        else:
            at_specific_time = bool(
                build_config.get("at_specific_time", {}).get("value", False),
            )

        # Visibility — the two branches are exclusive.
        for fname in self._INTERVAL_FIELDS:
            if fname in build_config:
                build_config[fname]["show"] = not at_specific_time
        for fname in self._SPECIFIC_TIME_FIELDS:
            if fname in build_config:
                build_config[fname]["show"] = at_specific_time

        # Re-derive the cron expression. Always — both branches.
        build_config["cron_expression"]["value"] = compose_cron(
            at_specific_time=at_specific_time,
            interval_value=build_config.get("interval_value", {}).get(
                "value", _DEFAULT_INTERVAL_VALUE
            ),
            interval_unit=build_config.get("interval_unit", {}).get(
                "value", UNIT_MINUTES
            ),
            time_of_day=build_config.get("time_of_day", {}).get(
                "value", _DEFAULT_TIME_OF_DAY
            ),
        )

        return build_config
