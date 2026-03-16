from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from lfx.components.input_output.chat import ChatInput
    from lfx.components.input_output.chat_output import ChatOutput
    from lfx.components.input_output.text import TextInputComponent
    from lfx.components.input_output.text_output import TextOutputComponent
    from lfx.components.input_output.webhook import WebhookComponent

_dynamic_imports = {
    "ChatInput": "chat",
    "ChatOutput": "chat_output",
    "TextInputComponent": "text",
    "TextOutputComponent": "text_output",
    "WebhookComponent": "webhook",
}

__all__ = ["ChatInput", "ChatOutput", "TextInputComponent", "TextOutputComponent", "WebhookComponent"]


def __getattr__(attr_name: str) -> Any:
    """Lazily import input/output components on attribute access."""
    if attr_name not in _dynamic_imports:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)
    try:
        result = import_mod(attr_name, _dynamic_imports[attr_name], __spec__.parent)
    except (ModuleNotFoundError, ImportError, AttributeError) as e:
        msg = f"Could not import '{attr_name}' from '{__name__}': {e}"
        raise AttributeError(msg) from e
    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    return list(__all__)
