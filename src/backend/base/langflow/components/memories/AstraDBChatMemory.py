from langflow.base.memory.model import LCChatMemoryComponent
from langflow.inputs import MessageTextInput, StrInput, SecretStrInput
from langflow.field_typing import BaseChatMessageHistory


class AstraDBChatMemory(LCChatMemoryComponent):
    display_name = "Astra DB Chat Memory"
    description = "Retrieves and store chat messages from Astra DB."
    name = "AstraDBChatMemory"
    icon: str = "AstraDB"

    inputs = [
        StrInput(
            name="collection_name",
            display_name="Collection Name",
            info="The name of the collection within Astra DB where the vectors will be stored.",
            required=True,
        ),
        SecretStrInput(
            name="token",
            display_name="Astra DB Application Token",
            info="Authentication token for accessing Astra DB.",
            value="ASTRA_DB_APPLICATION_TOKEN",
            required=True,
        ),
        SecretStrInput(
            name="api_endpoint",
            display_name="API Endpoint",
            info="API endpoint URL for the Astra DB service.",
            value="ASTRA_DB_API_ENDPOINT",
            required=True,
        ),
        StrInput(
            name="namespace",
            display_name="Namespace",
            info="Optional namespace within Astra DB to use for the collection.",
            advanced=True,
        ),
        MessageTextInput(
            name="session_id",
            display_name="Session ID",
            info="The session ID of the chat. If empty, the current session ID parameter will be used.",
            advanced=True,
        ),
    ]

    def build_message_history(self) -> BaseChatMessageHistory:
        try:
            from langchain_astradb.chat_message_histories import AstraDBChatMessageHistory
        except ImportError:
            raise ImportError(
                "Could not import langchain Astra DB integration package. "
                "Please install it with `pip install langchain-astradb`."
            )

        memory = AstraDBChatMessageHistory(
            session_id=self.session_id,
            collection_name=self.collection_name,
            token=self.token,
            api_endpoint=self.api_endpoint,
            namespace=self.namespace or None,
        )
        return memory
