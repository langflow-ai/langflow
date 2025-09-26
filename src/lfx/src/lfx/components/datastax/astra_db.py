from lfx.base.datastax.astradb_base import AstraDBBaseComponent
from lfx.base.memory.model import LCChatMemoryComponent
from lfx.field_typing.constants import Memory
from lfx.inputs.inputs import MessageTextInput


class AstraDBChatMemory(AstraDBBaseComponent, LCChatMemoryComponent):
    display_name = "Astra DB Chat Memory"
    description = "Retrieves and store chat messages from Astra DB."
    name = "AstraDBChatMemory"
    icon: str = "AstraDB"

    inputs = [
        *AstraDBBaseComponent.inputs,
        MessageTextInput(
            name="session_id",
            display_name="Session ID",
            info="The session ID of the chat. If empty, the current session ID parameter will be used.",
            advanced=True,
        ),
    ]

    def build_message_history(self) -> Memory:
        try:
            from astrapy.admin import parse_api_endpoint
            from langchain_astradb.chat_message_histories import AstraDBChatMessageHistory

        except ImportError as e:
            msg = (
                "Could not import langchain Astra DB integration package. "
                "Please install it with `pip install langchain-astradb`."
            )
            raise ImportError(msg) from e

        try:
            from astrapy.admin import parse_api_endpoint

        except ImportError as e:
            msg = "Could not import astrapy package. "
            raise ImportError(msg) from e

        return AstraDBChatMessageHistory(
            session_id=self.session_id,
            collection_name=self.collection_name,
            token=self.token,
            api_endpoint=self.api_endpoint,
            namespace=self.namespace or None,
            environment=parse_api_endpoint(self.api_endpoint).environment,
        )
