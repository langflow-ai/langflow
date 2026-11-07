from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.utils.lazy_import import import_mod

if TYPE_CHECKING:
    from .cloro_ai_mode import CloroAIModeComponent
    from .cloro_bing_ai_mode import CloroBingAIModeComponent
    from .cloro_chatgpt import CloroChatGPTComponent
    from .cloro_gemini import CloroGeminiComponent
    from .cloro_google_search import CloroGoogleSearchComponent

_dynamic_imports = {
    "CloroAIModeComponent": "cloro_ai_mode",
    "CloroBingAIModeComponent": "cloro_bing_ai_mode",
    "CloroChatGPTComponent": "cloro_chatgpt",
    "CloroGeminiComponent": "cloro_gemini",
    "CloroGoogleSearchComponent": "cloro_google_search",
}

__all__ = [
    "CloroAIModeComponent",
    "CloroBingAIModeComponent",
    "CloroChatGPTComponent",
    "CloroGeminiComponent",
    "CloroGoogleSearchComponent",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import cloro components on attribute access."""
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
