from langflow.base.memory.model import LCChatMemoryComponent
from langflow.field_typing import BaseChatMessageHistory
from langflow.inputs import MessageTextInput, StrInput
import pyignite
import pygridgain
import json
from typing import List, Dict, Any
from langchain.schema import (BaseMessage,HumanMessage,AIMessage,SystemMessage,ChatMessage)

class JSONSerializableGridGainChatHistory:
    """Mixin class to add JSON serialization capabilities to GridGain chat history."""
    
    def _serialize_message(self, message: BaseMessage) -> Dict[str, Any]:
        """Serialize a message to a dictionary."""
        base_data = {
            "content": message.content,
            "additional_kwargs": message.additional_kwargs
        }
        
        if isinstance(message, HumanMessage):
            base_data["type"] = "human"
        elif isinstance(message, AIMessage):
            base_data["type"] = "ai"
        elif isinstance(message, SystemMessage):
            base_data["type"] = "system"
        elif isinstance(message, ChatMessage):
            base_data["type"] = "chat"
            base_data["role"] = message.role
        else:
            raise ValueError(f"Got unexpected message type: {type(message)}")
        
        return base_data

    def _deserialize_message(self, data: Dict[str, Any]) -> BaseMessage:
        """Deserialize a dictionary to a message."""
        content = data["content"]
        additional_kwargs = data.get("additional_kwargs", {})
        message_type = data["type"]

        if message_type == "human":
            return HumanMessage(content=content, additional_kwargs=additional_kwargs)
        elif message_type == "ai":
            return AIMessage(content=content, additional_kwargs=additional_kwargs)
        elif message_type == "system":
            return SystemMessage(content=content, additional_kwargs=additional_kwargs)
        elif message_type == "chat":
            return ChatMessage(
                content=content,
                additional_kwargs=additional_kwargs,
                role=data["role"]
            )
        else:
            raise ValueError(f"Unknown message type: {message_type}")

    def _save_messages(self, messages: List[BaseMessage]) -> None:
        """Save messages to GridGain cache."""
        try:
            cache = self.client.get_or_create_cache(self.cache_name)
            messages_list = [self._serialize_message(m) for m in messages]
            cache.put(self.session_id, json.dumps(messages_list))
        except Exception as e:
            print(f"Error saving messages: {str(e)}")

    def _load_messages(self) -> List[BaseMessage]:
        """Load messages from GridGain cache."""
        try:
            cache = self.client.get_or_create_cache(self.cache_name)
            stored_messages = cache.get(self.session_id)
            if stored_messages:
                messages_list = json.loads(stored_messages)
                return [self._deserialize_message(m) for m in messages_list]
        except Exception as e:
            print(f"Error loading messages: {str(e)}")
        return []

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
        StrInput(
            name="port",
            display_name="Port",
            info="GridGain server port number.",
            required=True,
            value="10800",
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

    def build_message_history(self) -> BaseChatMessageHistory:
        """Build and return a GridGain chat message history instance."""
        try:
            from langchain_gridgain.chat_message_histories import GridGainChatMessageHistory
        except ImportError as e:
            msg = (
                "Could not import GridGain chat message history implementation. "
                "Please ensure the implementation file is in the correct location."
            )
            raise ImportError(msg) from e

        # Create a custom class that combines GridGainChatMessageHistory with JSON serialization
        class EnhancedGridGainChatHistory(GridGainChatMessageHistory, JSONSerializableGridGainChatHistory):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._messages: List[BaseMessage] = self._load_messages()

            @property
            def messages(self) -> List[BaseMessage]:
                """Retrieve the messages from the store."""
                return self._messages

            @messages.setter
            def messages(self, value: List[BaseMessage]) -> None:
                """Set the messages in the store."""
                self._messages = value
                self._save_messages(value)

            def add_message(self, message: BaseMessage) -> None:
                """Add a message to the store."""
                self._messages.append(message)
                self._save_messages(self._messages)

            def clear(self) -> None:
                """Clear message history."""
                self._messages = []
                cache = self.client.get_or_create_cache(self.cache_name)
                cache.remove(self.session_id)

        # Create the appropriate client based on the specified type
        if self.client_type.lower() == "pyignite":
            client = pyignite.Client()
        elif self.client_type.lower() == "pygridgain":
            client = pygridgain.Client()
        else:
            raise ValueError(
                "Invalid client_type. Must be either 'pyignite' or 'pygridgain'."
            )

        # Connect to the GridGain server
        try:
            client.connect(self.host, int(self.port))
        except Exception as e:
            raise ConnectionError(
                f"Failed to connect to GridGain server at {self.host}:{self.port}: {str(e)}"
            )

        return EnhancedGridGainChatHistory(
            session_id=self.session_id,
            cache_name=self.cache_name,
            client=client,
        )
