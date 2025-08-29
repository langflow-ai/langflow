"""Message class for langflow - imports from lfx.

This maintains backward compatibility while using the lfx implementation.
"""

from lfx.schema.message import ContentBlock, DefaultModel, ErrorMessage, Message, MessageResponse

__all__ = ["ContentBlock", "DefaultModel", "ErrorMessage", "Message", "MessageResponse"]
