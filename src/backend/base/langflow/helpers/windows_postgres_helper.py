"""Helper for Windows + PostgreSQL event loop configuration."""

import asyncio
import os
import platform

from lfx.log.logger import logger

LANGFLOW_DATABASE_URL = "LANGFLOW_DATABASE_URL"
POSTGRESQL_PREFIXES = ("postgresql", "postgres")


def configure_windows_postgres_event_loop(source: str | None = None) -> bool:
    """Configure event loop for Windows + PostgreSQL compatibility.

    Args:
        source: Optional identifier for logging context

    Returns:
        True if configuration was applied, False otherwise
    """
    if platform.system() != "Windows":
        return False

    db_url = os.environ.get(LANGFLOW_DATABASE_URL, "")
    if not db_url or not any(db_url.startswith(prefix) for prefix in POSTGRESQL_PREFIXES):
        return False

    # Use getattr to safely access the Windows-only class on all platforms
    selector_policy = getattr(asyncio, "WindowsSelectorEventLoopPolicy", None)
    if selector_policy is None:
        return False

    current_policy = asyncio.get_event_loop_policy()
    if isinstance(current_policy, selector_policy):
        return False

    asyncio.set_event_loop_policy(selector_policy())

    log_context = {"event_loop": "WindowsSelectorEventLoop", "reason": "psycopg_compatibility"}
    if source:
        log_context["source"] = source

    logger.debug("Windows PostgreSQL event loop configured", extra=log_context)
    return True
