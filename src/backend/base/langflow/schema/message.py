"""Message class for langflow - imports from lfx.

This maintains backward compatibility while using the lfx implementation.
"""

# Import and re-export to ensure class identity is preserved
from lfx.schema.message import ContentBlock, DefaultModel, ErrorMessage, Message, MessageResponse

__all__ = ["ContentBlock", "DefaultModel", "ErrorMessage", "Message", "MessageResponse"]
