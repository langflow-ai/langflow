"""Component re-exports for the ``slack`` bundle.

Saved-flow migration entries that target ``lfx.components.slack.<Class>``
resolve through this package, so every Component class must be importable
from here by name.

The two trigger components are imported lazily. They subclass
``lfx.base.triggers``, which lfx first shipped in 1.13.0.dev17, while this
bundle's lfx floor is the whole 1.13 line. Every action module imports this
package on its way to ``lfx_slack._base``, so importing the triggers eagerly
would take the actions down with them on an earlier 1.13 nightly; lazily, only
the triggers are missing there.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.utils.lazy_import import import_mod

from .slack_add_reaction import SlackAddReactionComponent
from .slack_canvas import SlackCanvasComponent
from .slack_list_channel_members import SlackListChannelMembersComponent
from .slack_post_as_app import SlackPostAsAppComponent
from .slack_read_thread import SlackReadThreadComponent
from .slack_search import SlackSearchComponent
from .slack_send_as_user import SlackSendAsUserComponent

if TYPE_CHECKING:
    from .slack_on_message import SlackOnMessageTriggerComponent
    from .slack_on_reaction import SlackOnReactionTriggerComponent

_dynamic_imports = {
    "SlackOnMessageTriggerComponent": "slack_on_message",
    "SlackOnReactionTriggerComponent": "slack_on_reaction",
}

__all__ = [
    "SlackAddReactionComponent",
    "SlackCanvasComponent",
    "SlackListChannelMembersComponent",
    "SlackOnMessageTriggerComponent",
    "SlackOnReactionTriggerComponent",
    "SlackPostAsAppComponent",
    "SlackReadThreadComponent",
    "SlackSearchComponent",
    "SlackSendAsUserComponent",
]


def __getattr__(attr_name: str) -> Any:
    """Import a trigger component on first access."""
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
