# SPDX-License-Identifier: MIT
"""Lazy export entrypoint for the Langflow `lfx_bundles.silicium` component bundle."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

try:
    from lfx.components._importing import import_mod
except ImportError:
    try:
        from lfx.utils.lazy_import import import_mod
    except ImportError:
        import importlib

        def import_mod(attr_name: str, module_name: str, parent_pkg: str | None = None) -> Any:
            """Import `attr_name` from `module_name` within `parent_pkg` when `lfx` lazy loader is absent."""
            for candidate in (
                f"{__name__}.{module_name}",
                f"{parent_pkg}.{module_name}" if parent_pkg else "",
                module_name,
            ):
                if not candidate:
                    continue
                try:
                    mod = importlib.import_module(candidate)
                    return getattr(mod, attr_name)
                except (ImportError, AttributeError):
                    continue
            msg = f"No module named {module_name!r}"
            raise ModuleNotFoundError(msg)


if TYPE_CHECKING:
    from .silicium_pii_guardrail import SiliciumPiiGuardrailComponent
    from .silicium_semantic_cache import SiliciumSemanticCacheComponent
    from .silicium_vector_store import SiliciumVectorStoreComponent

_dynamic_imports = {
    "SiliciumPiiGuardrailComponent": "silicium_pii_guardrail",
    "SiliciumSemanticCacheComponent": "silicium_semantic_cache",
    "SiliciumVectorStoreComponent": "silicium_vector_store",
}

__all__ = [
    "SiliciumPiiGuardrailComponent",
    "SiliciumSemanticCacheComponent",
    "SiliciumVectorStoreComponent",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import Silicium components on attribute access."""
    if attr_name not in _dynamic_imports:
        msg = f"module '{__name__}' has no attribute '{attr_name}'"
        raise AttributeError(msg)
    parent = __spec__.parent if __spec__ is not None else __package__
    try:
        result = import_mod(attr_name, _dynamic_imports[attr_name], parent)
    except (ModuleNotFoundError, ImportError, AttributeError) as e:
        msg = f"Could not import '{attr_name}' from '{__name__}': {e}"
        raise AttributeError(msg) from e
    globals()[attr_name] = result
    return result


def __dir__() -> list[str]:
    """Return exported component names for module introspection."""
    return list(__all__)
