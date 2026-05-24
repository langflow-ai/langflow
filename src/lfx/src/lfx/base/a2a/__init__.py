"""Shared A2A (Agent-to-Agent) building blocks for lfx components.

Currently exposes a thin, transport-injectable A2A REST client used by the
"A2A Agent" canvas component. It has no dependency on the langflow backend,
so it is safe to import from lfx components.
"""

from lfx.base.a2a.client import (
    A2AClient,
    A2AClientError,
    build_message,
    extract_text_artifacts,
)

__all__ = ["A2AClient", "A2AClientError", "build_message", "extract_text_artifacts"]
