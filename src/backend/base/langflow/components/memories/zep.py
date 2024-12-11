from langflow.base.memory.model import LCChatMemoryComponent
from langflow.field_typing import BaseChatMessageHistory
from langflow.inputs import DropdownInput, MessageTextInput, SecretStrInput


class ZepChatMemory(LCChatMemoryComponent):
    display_name = "Zep Chat Memory"
    description = "Retrieves and store chat messages from Zep."
    name = "ZepChatMemory"
    icon = "ZepMemory"

    inputs = [
        MessageTextInput(
            name="url",
            display_name="Zep URL",
            info="URL of the Zep instance. Keep empty for cloud Zep instance.",
            advanced=True,
        ),
        SecretStrInput(name="api_key", display_name="API Key", info="API Key for the Zep instance."),
        MessageTextInput(
            name="session_id", display_name="Session ID", info="Session ID for the message.", advanced=True
        ),
    ]

    def build_message_history(self) -> BaseChatMessageHistory:
        try:
            # Monkeypatch API_BASE_PATH to
            # avoid 404
            # This is a workaround for the local Zep instance
            # cloud Zep works with v2
            from langchain_community.chat_message_histories.zep_cloud import ZepCloudChatMessageHistory


        except ImportError as e:
            msg = "Could not import zep-python package. Please install it with `pip install zep-python`."
            raise ImportError(msg) from e

        return ZepCloudChatMessageHistory(session_id=self.session_id, api_key=self.api_key,memory_type="perpetual")
