"""SSE event emitters for the assistant's retry cycle.

Kept separate from the orchestration service so the retry-event composition
lives in one place and the orchestrator stays under the file-size limit.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from langflow.agentic.helpers.sse import format_complete_event, format_progress_event
from langflow.agentic.services.flow_types import VALIDATION_UI_DELAY_SECONDS

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


async def emit_execution_retry_events(
    *,
    attempt: int,
    total_attempts: int,
    error: str,
) -> AsyncGenerator[str, None]:
    """Yield SSE events for a flow-execution failure inside the retry loop.

    Emits a ``validation_failed`` event, waits for the UX delay, and then either:
    - emits a final ``complete`` event with ``validated=False`` if attempts are
      exhausted (so the frontend renders the "Component generation failed" card), or
    - emits a ``retrying`` event so the caller can try again with an updated prompt.

    Args:
        attempt: Zero-based index of the attempt that just failed.
        total_attempts: Total attempts allowed before giving up.
        error: User-facing friendly error message produced by extract_friendly_error.
    """
    yield format_progress_event(
        "validation_failed",
        attempt + 1,
        total_attempts,
        message="Generation failed",
        error=error,
    )
    await asyncio.sleep(VALIDATION_UI_DELAY_SECONDS)

    if attempt >= total_attempts - 1:
        yield format_complete_event(
            {
                "result": "",
                "validated": False,
                "validation_error": error,
                "validation_attempts": attempt + 1,
            }
        )
        return

    yield format_progress_event(
        "retrying",
        attempt + 1,
        total_attempts,
        message="Retrying with error context...",
        error=error,
    )
    await asyncio.sleep(VALIDATION_UI_DELAY_SECONDS)
