"""Non-functional compatibility stub for the legacy Zep Chat Memory component.

The original implementation targeted the zep-python v1 SDK (``ZepClient`` plus
``zep_python.langchain.ZepChatMessageHistory``). zep-python 2.x removed both
symbols, and the bundle's ``zep`` extra pins ``zep-python==2.0.2``, so
``build_message_history`` could never succeed on a supported install -- it
always hit its ImportError guard, which misleadingly told users to
``pip install zep-python`` (already installed, just incompatible).

The component is deprecated (``legacy=True``, replaced by the Message History
component, ``helpers.Memory``). Rather than delete it outright -- which would
break saved flows that still reference it -- it is kept as a stub: existing
flows continue to load, and building the node now raises a clear error
pointing at the replacement instead of the misleading install hint.
"""

from lfx.base.memory.model import LCChatMemoryComponent
from lfx.field_typing.constants import Memory
from lfx.inputs.inputs import DropdownInput, MessageTextInput, SecretStrInput

DISABLED_MESSAGE = (
    "The legacy 'Zep Chat Memory' component no longer functions: it was built on the "
    "zep-python v1 API, which no longer exists in the zep-python 2.x release that "
    "Langflow installs. Replace this node with the 'Message History' component (its "
    "designated replacement) or another memory integration."
)


class ZepChatMemory(LCChatMemoryComponent):
    display_name = "Zep Chat Memory"
    # NOTE: display_name/description/input strings are intentionally kept identical to the
    # pre-stub component so flow identity and the i18n locale keys (locales/*.json) do not
    # change. The deprecation is signalled via legacy=True, the replacement below, and the
    # runtime error raised by build_message_history.
    description = "Retrieves and store chat messages from Zep."
    name = "ZepChatMemory"
    icon = "ZepMemory"
    legacy = True
    replacement = ["helpers.Memory"]

    inputs = [
        MessageTextInput(name="url", display_name="Zep URL", info="URL of the Zep instance."),
        SecretStrInput(name="api_key", display_name="Zep API Key", info="API Key for the Zep instance."),
        DropdownInput(
            name="api_base_path",
            display_name="API Base Path",
            options=["api/v1", "api/v2"],
            value="api/v1",
            advanced=True,
        ),
        MessageTextInput(
            name="session_id", display_name="Session ID", info="Session ID for the message.", advanced=True
        ),
    ]

    def build_message_history(self) -> Memory:
        """Always raise: the zep-python v1 API this component was built on is gone."""
        raise RuntimeError(DISABLED_MESSAGE)
