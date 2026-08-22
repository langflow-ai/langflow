from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.utils.lazy_import import import_mod

if TYPE_CHECKING:
    from lfx_bundles.magic_hour.magic_hour_image_generator import MagicHourImageGeneratorComponent
    from lfx_bundles.magic_hour.magic_hour_image_to_video import MagicHourImageToVideoComponent
    from lfx_bundles.magic_hour.magic_hour_text_to_video import MagicHourTextToVideoComponent

_dynamic_imports = {
    "MagicHourImageGeneratorComponent": "magic_hour_image_generator",
    "MagicHourImageToVideoComponent": "magic_hour_image_to_video",
    "MagicHourTextToVideoComponent": "magic_hour_text_to_video",
}

__all__ = [
    "MagicHourImageGeneratorComponent",
    "MagicHourImageToVideoComponent",
    "MagicHourTextToVideoComponent",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import magic_hour components on attribute access."""
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
