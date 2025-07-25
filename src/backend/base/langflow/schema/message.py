"""Message schema module using inheritance approach.

This module imports the enhanced Message class that inherits from the base lfx.schema.message.Message.
This approach breaks circular dependencies while maintaining backward compatibility.
"""

from langflow.schema.content_block import ContentBlock
from langflow.schema.message_enhanced import ErrorMessage, Message
from langflow.schema.message_original import MessageResponse

__all__ = ["ContentBlock", "ErrorMessage", "Message", "MessageResponse"]
