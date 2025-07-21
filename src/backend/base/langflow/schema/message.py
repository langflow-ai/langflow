"""Message schema module using inheritance approach.

This module imports the enhanced Message class that inherits from the base lfx.schema.message.Message.
This approach breaks circular dependencies while maintaining backward compatibility.
"""

from langflow.schema.message_enhanced import ErrorMessage, Message

__all__ = ["ErrorMessage", "Message"]
