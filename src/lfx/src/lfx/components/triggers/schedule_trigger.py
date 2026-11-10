"""Fire a flow on a cron schedule, in a named timezone."""

from __future__ import annotations

from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from lfx.base.triggers.base import BaseTriggerComponent
from lfx.base.triggers.schedule import (
    FIELDS_BY_TYPE,
    INTERVALS,
    MONTH_DAYS,
    PICKER_FIELDS,
    SCHEDULE_CUSTOM,
    SCHEDULE_TYPES,
    SCHEDULE_WEEKLY,
    TIMES_OF_DAY,
    WEEKDAYS,
    ScheduleTriggerError,
    picker_cron,
    timezone_options,
)
from lfx.io import BoolInput, DropdownInput, MessageTextInput, MultiselectInput

#: Catch-up policies, mirroring ``TriggerCatchupPolicy`` on the server.
CATCHUP_COALESCE = "coalesce"
CATCHUP_SKIP = "skip"

_CRON_FIELD_COUNT = 5


def validate_cron_expression(expression: str) -> str:
    """Check the shape of a five-field cron expression.

    Deliberately syntactic only. The server validates the expression with the
    same library that computes fire times, so the two can never disagree about
    what a given expression means; this check exists to give the person editing
    the canvas an answer without a round trip.
    """
    if not expression or expression.isspace():
        msg = "A cron expression is required, for example '0 8 * * 1-5'."
        raise ScheduleTriggerError(msg)
    fields = expression.split()
    if len(fields) != _CRON_FIELD_COUNT:
        msg = (
            f"A cron expression has {_CRON_FIELD_COUNT} fields "
            "(minute hour day-of-month month day-of-week), "
            f"got {len(fields)}: {expression!r}"
        )
        raise ScheduleTriggerError(msg)
    return " ".join(fields)


def validate_timezone(name: str) -> str:
    """Check that the timezone is a real IANA zone.

    An unknown zone must fail here, on save, rather than silently falling back
    to UTC and firing the digest at the wrong local hour every day.
    """
    if not name or name.isspace():
        msg = "A timezone is required, for example 'Europe/Lisbon'."
        raise ScheduleTriggerError(msg)
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        msg = f"Unknown timezone {name!r}; use an IANA name such as 'Europe/Lisbon'."
        raise ScheduleTriggerError(msg) from exc
    return name


class ScheduleTriggerComponent(BaseTriggerComponent):
    display_name = "Schedule"
    description = "Run this flow on a schedule, evaluated in a timezone you choose."
    documentation: str = "https://docs.langflow.org/triggers"
    name = "ScheduleTrigger"
    icon = "Clock"

    trigger_kind = "schedule"

    inputs = [
        DropdownInput(
            name="schedule_type",
            display_name="Schedule type",
            options=SCHEDULE_TYPES,
            value=SCHEDULE_WEEKLY,
            info="How often the flow runs. Pick Custom (cron) to write a cron expression.",
            real_time_refresh=True,
        ),
        DropdownInput(
            name="interval",
            display_name="Every",
            options=list(INTERVALS),
            value="15 minutes",
            real_time_refresh=True,
            show=False,
        ),
        MultiselectInput(
            name="days_of_week",
            display_name="Days of the week",
            options=list(WEEKDAYS),
            value=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            real_time_refresh=True,
        ),
        MultiselectInput(
            name="days_of_month",
            display_name="Days of the month",
            options=MONTH_DAYS,
            value=["1"],
            info="A month without the picked day is skipped.",
            real_time_refresh=True,
            show=False,
        ),
        DropdownInput(
            name="time_of_day",
            display_name="Time of day",
            options=TIMES_OF_DAY,
            value="08:00",
            info="24-hour time in the timezone below. Type another time, such as 08:15, to use it.",
            combobox=True,
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="cron_expression",
            display_name="Cron expression",
            value="0 8 * * 1-5",
            info=(
                "Five fields: minute hour day-of-month month day-of-week. "
                "'0 8 * * 1-5' is every weekday at 08:00 in the timezone below."
            ),
            input_types=[],
            required=True,
            show=False,
        ),
        DropdownInput(
            name="timezone",
            display_name="Timezone",
            options=timezone_options(),
            value="UTC",
            info="The schedule runs in this timezone. Daylight-saving changes are applied, so 08:00 stays 08:00 local.",
            required=True,
        ),
        DropdownInput(
            name="catchup_policy",
            display_name="After downtime",
            options=[CATCHUP_COALESCE, CATCHUP_SKIP],
            value=CATCHUP_COALESCE,
            info=(
                "What to do with ticks missed while the server was down. "
                "'coalesce' runs once and reports the ticks that were missed; "
                "'skip' waits for the next scheduled time."
            ),
            advanced=True,
        ),
        BoolInput(
            name="share_session",
            display_name="Share session across runs",
            value=False,
            info=(
                "Off: every run gets its own session. On: all runs share one session, "
                "so an agent downstream keeps memory between ticks."
            ),
            advanced=True,
        ),
    ]

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        """Show the fields the schedule type needs and keep the cron the server reads in step."""
        if field_name in build_config:
            build_config[field_name]["value"] = field_value
        return _sync_picker(build_config, field_name)

    async def update_frontend_node(self, new_frontend_node: dict, current_frontend_node: dict):
        """On a component update, open a node saved before the picker on its own cron."""
        node = await super().update_frontend_node(new_frontend_node, current_frontend_node)
        _sync_picker(node["template"], None)
        return node

    def trigger_config(self) -> dict[str, Any]:
        """The JSON the flow-save reconciler copies onto the trigger row."""
        return {
            "cron": validate_cron_expression(self.cron_expression or ""),
            "timezone": validate_timezone(self.timezone or ""),
            "catchup_policy": self.catchup_policy or CATCHUP_COALESCE,
            "share_session": bool(self.share_session),
        }


def _sync_picker(build_config: dict, field_name: str | None) -> dict:
    values = {name: (build_config.get(name) or {}).get("value") for name in PICKER_FIELDS}
    if field_name in PICKER_FIELDS:
        cron = picker_cron(values)
        if cron is not None:
            build_config["cron_expression"]["value"] = cron
    elif values["schedule_type"] != SCHEDULE_CUSTOM and _picker_disagrees(values, build_config):
        # A node saved before the picker existed keeps its cron; show it rather than a guess.
        build_config["schedule_type"]["value"] = SCHEDULE_CUSTOM
    shown = FIELDS_BY_TYPE.get(build_config["schedule_type"]["value"], FIELDS_BY_TYPE[SCHEDULE_CUSTOM])
    for name in {field for fields in FIELDS_BY_TYPE.values() for field in fields}:
        if name in build_config:
            build_config[name]["show"] = name in shown
    return build_config


def _picker_disagrees(values: dict[str, Any], build_config: dict) -> bool:
    try:
        cron = picker_cron(values)
    except ScheduleTriggerError:
        return True
    stored = (build_config.get("cron_expression") or {}).get("value") or ""
    return cron is not None and " ".join(stored.split()) != cron
