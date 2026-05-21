"""Constants for the triggers component category.

Kept in its own module so the component file stays focused on the
``Component`` declaration and any downstream consumer (worker,
discovery helper) can import the same authoritative list.
"""

from __future__ import annotations

# Curated subset of IANA timezone names exposed in the CronTrigger
# dropdown. The list is intentionally short — a sensible default that
# covers the most common regions. Users needing a timezone outside
# this set can type any IANA name via the combobox mode.
#
# The order is roughly geographic (Americas → Europe → Asia →
# Australia → UTC last) so the dropdown reads naturally; UTC is also
# the dropdown default and the safe fallback elsewhere in the system.
COMMON_TIMEZONES: tuple[str, ...] = (
    "UTC",
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "America/Sao_Paulo",
    "America/Argentina/Buenos_Aires",
    "America/Mexico_City",
    "Europe/London",
    "Europe/Berlin",
    "Europe/Paris",
    "Europe/Madrid",
    "Asia/Tokyo",
    "Asia/Shanghai",
    "Asia/Kolkata",
    "Australia/Sydney",
)

DEFAULT_TIMEZONE: str = "UTC"
DEFAULT_CRON_EXPRESSION: str = "*/5 * * * *"
DEFAULT_MAX_ATTEMPTS: int = 3
MAX_ATTEMPTS_LIMIT: int = 10
