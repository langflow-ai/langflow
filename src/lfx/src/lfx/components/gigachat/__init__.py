from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.components._importing import import_mod

if TYPE_CHECKING:
    from lfx.components.gigachat.gigachat_embeddings import GigaChatEmbeddingsComponent
    from lfx.components.gigachat.gigachat_models import GigaChatComponent

_dynamic_imports = {
    "GigaChatComponent": "gigachat_models",
    "GigaChatEmbeddingsComponent": "gigachat_embeddings",
}

__all__ = ["GigaChatComponent", "GigaChatEmbeddingsComponent"]


def __getattr__(attr_name: str) -> Any:
    """Lazily import and cache a GigaChat component when accessed as a module attribute.

    Parameters:
        attr_name (str): The attribute name to resolve and import.

    Returns:
        Any: The imported component object.

    Raises:
        AttributeError: If attr_name is not a recognized public component name or if importing the component fails.
    """
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
    """Return the list of public attribute names exported by this module.

    Returns:
        list[str]: Public attribute names as defined in __all__.
    """
    return list(__all__)
