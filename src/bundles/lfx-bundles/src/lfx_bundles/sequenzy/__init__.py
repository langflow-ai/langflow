from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.utils.lazy_import import import_mod

if TYPE_CHECKING:
    from .sequenzy_campaigns import SequenzyListCampaignsComponent
    from .sequenzy_event import SequenzyTriggerEventComponent
    from .sequenzy_send_email import SequenzySendEmailComponent
    from .sequenzy_subscriber import SequenzyAddSubscriberComponent, SequenzyGetSubscriberComponent
    from .sequenzy_tag import SequenzyTagSubscriberComponent

_dynamic_imports = {
    "SequenzyAddSubscriberComponent": "sequenzy_subscriber",
    "SequenzyGetSubscriberComponent": "sequenzy_subscriber",
    "SequenzyListCampaignsComponent": "sequenzy_campaigns",
    "SequenzySendEmailComponent": "sequenzy_send_email",
    "SequenzyTagSubscriberComponent": "sequenzy_tag",
    "SequenzyTriggerEventComponent": "sequenzy_event",
}

__all__ = [
    "SequenzyAddSubscriberComponent",
    "SequenzyGetSubscriberComponent",
    "SequenzyListCampaignsComponent",
    "SequenzySendEmailComponent",
    "SequenzyTagSubscriberComponent",
    "SequenzyTriggerEventComponent",
]


def __getattr__(attr_name: str) -> Any:
    """Lazily import Sequenzy components on attribute access."""
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
