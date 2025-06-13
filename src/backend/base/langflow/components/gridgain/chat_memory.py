from langflow.base.memory.model import LCChatMemoryComponent
from langflow.field_typing.constants import Memory
from langflow.inputs import IntInput, MessageTextInput, StrInput


class GridGainChatMemory(LCChatMemoryComponent):
    """Chat memory component that stores history in GridGain."""

    display_name = "GridGain Chat Memory"
    description = "Retrieves and stores chat messages using GridGain."
    name = "GridGainChatMemory"
    icon: str = "GridGain"

    inputs = [
        StrInput(
            name="host",
            display_name="Host",
            info="GridGain server host address.",
            required=True,
            value="localhost",
        ),
        IntInput(
            name="port",
            display_name="Port",
            info="GridGain server port number.",
            required=True,
            value=10800,
        ),
        StrInput(
            name="cache_name",
            display_name="Cache Name",
            info="The name of the cache within GridGain where messages will be stored.",
            required=True,
            value="langchain_message_store",
        ),
        MessageTextInput(
            name="session_id",
            display_name="Session ID",
            info="The session ID of the chat. If empty, the current session ID parameter will be used.",
            advanced=True,
        ),
        StrInput(
            name="client_type",
            display_name="Client Type",
            info="Type of client to use (pygridgain).",
            required=True,
            value="pygridgain",
        ),
    ]

    def build_message_history(self) -> Memory:
        """Build and return a GridGain chat message history instance."""
        try:
            from langchain_gridgain.chat_message_histories import GridGainChatMessageHistory
        except ImportError as e:
            msg = (
                "Could not import GridGain chat message history implementation. "
                "Please ensure the implementation file is in the correct location."
            )
            raise ImportError(msg) from e

        try:
            import pygridgain
        except ModuleNotFoundError:
            pygridgain = None

        # Create the appropriate client based on the specified type
        if self.client_type.lower() == "pygridgain":
            client = pygridgain.Client()
        else:
            msg = "Invalid client_type. Must be 'pygridgain'."
            raise ValueError(msg)

        # Connect to the GridGain server
        try:
            client.connect(self.host, int(self.port))
        except Exception as e:
            msg = f"Failed to connect to GridGain server at {self.host}:{self.port}: {(e)}"
            raise ConnectionError(msg) from e

        return GridGainChatMessageHistory(
            session_id=self.session_id,
            cache_name=self.cache_name,
            client=client,
        )
