"""Fire a flow on a cron schedule, in a named timezone."""

from __future__ import annotations

from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from lfx.base.triggers.base import BaseTriggerComponent
from lfx.io import BoolInput, DropdownInput, MessageTextInput

#: Catch-up policies, mirroring ``TriggerCatchupPolicy`` on the server.
CATCHUP_COALESCE = "coalesce"
CATCHUP_SKIP = "skip"

_CRON_FIELD_COUNT = 5


class ScheduleTriggerError(ValueError):
    """The schedule cannot be armed as configured."""


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
    description = "Run this flow on a cron schedule, evaluated in a timezone you choose."
    documentation: str = "https://docs.langflow.org/triggers"
    name = "ScheduleTrigger"
    icon = "Clock"

    trigger_kind = "schedule"

    inputs = [
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
        ),
        MessageTextInput(
            name="timezone",
            display_name="Timezone",
            value="UTC",
            info=(
                "IANA timezone the expression is evaluated in, for example 'Europe/Lisbon'. "
                "Daylight-saving changes are applied, so 08:00 stays 08:00 local."
            ),
            input_types=[],
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

    def trigger_config(self) -> dict[str, Any]:
        """The JSON the flow-save reconciler copies onto the trigger row."""
        return {
            "cron": validate_cron_expression(self.cron_expression or ""),
            "timezone": validate_timezone(self.timezone or ""),
            "catchup_policy": self.catchup_policy or CATCHUP_COALESCE,
            "share_session": bool(self.share_session),
        }
