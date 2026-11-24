"""Message class for langflow - imports from lfx.

This maintains backward compatibility while using the lfx implementation.
"""

# Import and re-export to ensure class identity is preserved
from lfx.schema.message import (
    MAX_ATTACHMENT_SIZE_BYTES,
    ContentBlock,
    DefaultModel,
    ErrorMessage,
    Message,
    MessageResponse,
)

__all__ = [
    "MAX_ATTACHMENT_SIZE_BYTES",
    "ContentBlock",
    "DefaultModel",
    "ErrorMessage",
    "Message",
    "MessageResponse",
]
