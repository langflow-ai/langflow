"""Validate stored job timestamp components before normalizing them to UTC."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

_STORED_TIMESTAMP = re.compile(
    r"(?P<year>[0-9]{4})-(?P<month>[0-9]{2})-(?P<day>[0-9]{2})[T ]"
    r"(?P<hour>[0-9]{2}):(?P<minute>[0-9]{2}):(?P<second>[0-9]{2})"
    r"(?:\.(?P<fraction>[0-9]+))?"
    r"(?P<offset>Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])?"
)


def normalize_usage_timestamp(value: object) -> str | None:
    """Return fixed-width UTC microseconds, or unknown for invalid original metadata.

    SQLite can repair an impossible date when normalizing it. Constructing the
    original datetime first rejects that date consistently across Python versions.
    Naive stored datetimes use UTC, matching Langflow's database serializers.
    """
    try:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str):
            match = _STORED_TIMESTAMP.fullmatch(value)
            if match is None:
                return None
            offset = match["offset"]
            tz = timezone.utc
            if offset not in (None, "Z"):
                delta = timedelta(hours=int(offset[1:3]), minutes=int(offset[4:6]))
                tz = timezone(delta if offset.startswith("+") else -delta)
            parsed = datetime(
                int(match["year"]),
                int(match["month"]),
                int(match["day"]),
                int(match["hour"]),
                int(match["minute"]),
                int(match["second"]),
                int((match["fraction"] or "")[:6].ljust(6, "0")),
                tzinfo=tz,
            )
        else:
            return None
        normalized = parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None
    return normalized.isoformat(timespec="microseconds").replace("+00:00", "Z")
