"""A2A client transport (the "caller" half of the bridge).

The implementation lives in :mod:`lfx.base.a2a.client` so that lfx canvas
components (e.g. the "A2A Agent" node) can use it without importing the
langflow backend. This module re-exports it for backend callers and tests.
"""

from lfx.base.a2a.client import (
    A2AClient,
    A2AClientError,
    build_message,
    extract_text_artifacts,
)

__all__ = ["A2AClient", "A2AClientError", "build_message", "extract_text_artifacts"]
