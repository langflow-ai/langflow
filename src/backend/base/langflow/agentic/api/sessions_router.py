"""Session-lifecycle endpoints for the agentic assistant.

Today exposes a single ``POST /api/v1/agentic/sessions/reset`` that the
frontend calls on every "new session" boundary:
    - panel mount with a fresh ``session_id``
    - explicit New session button click

Combines two cleanup actions that share the same trigger:
    1. ``clear_session_history(session_id)`` — drops the conversation
       buffer entry so the prior session's turns don't leak into the
       next request prompt.
    2. ``clear_user_components(user_id)`` — wipes the user's registered
       components so each session starts with an empty registry overlay.

Authentication is enforced via the same ``CurrentActiveUser`` dependency
the assist endpoints use. An unauthenticated request never reaches the
handler. The handler also never trusts a ``user_id`` parameter — the
calling user is always ``current_user.id``, so a tenant can never wipe
another tenant's components by impersonating their id.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Query

from langflow.agentic.services.assistant_service import clear_session_history
from langflow.agentic.services.user_components import clear_user_components
from langflow.api.utils.core import CurrentActiveUser  # noqa: TC001 — FastAPI Depends alias needs the runtime symbol

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agentic/sessions", tags=["agentic"])


@router.post("/reset")
async def reset_session(
    *,
    current_user: CurrentActiveUser,
    session_id: Annotated[str | None, Query(max_length=128)] = None,
) -> dict:
    """Drop the calling user's session-scoped state.

    Wipes:
        - conversation buffer for ``session_id`` (if provided).
        - registered components under the user's FS sandbox.

    The user id is sourced from the authenticated session — the
    ``session_id`` query parameter only addresses the conversation
    buffer entry and is never trusted for path resolution.

    Returns a small envelope describing what was cleared, sufficient
    for ops/log correlation but stripped of anything sensitive:

    ```
    {"status": "ok", "components_cleared": <int>, "session_id": <str|null>}
    ```
    """
    user_id = str(current_user.id)
    components_cleared = clear_user_components(user_id=user_id)
    clear_session_history(user_id, session_id)
    logger.info(
        "agentic.session.reset user_id=%s session_id=%s components_cleared=%d",
        user_id,
        session_id,
        components_cleared,
    )
    return {
        "status": "ok",
        "components_cleared": components_cleared,
        "session_id": session_id,
    }
