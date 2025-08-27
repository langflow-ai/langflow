"""Schema modules for lfx package."""

__all__ = ["Data", "DataFrame", "InputValue", "Message", "Tweaks", "dotdict"]


def __getattr__(name: str):
    # Import to avoid circular dependencies
    if name == "Data":
        from .data import Data
        return Data
    if name == "DataFrame":
        from .dataframe import DataFrame
        return DataFrame
    if name == "dotdict":
        from .dotdict import dotdict
        return dotdict
    if name == "InputValue":
        from .graph import InputValue
        return InputValue
    if name == "Tweaks":
        from .graph import Tweaks
        return Tweaks
    if name == "Message":
        from .message import Message
        return Message

    msg = f"module '{__name__}' has no attribute '{name}'"
    raise AttributeError(msg)
