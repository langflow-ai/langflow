from abc import abstractmethod

from langchain.memory import ConversationBufferMemory

from langflow.custom.custom_component.component import Component
from langflow.field_typing import BaseChatMemory
from langflow.field_typing.constants import Memory
from langflow.template.field.base import Output


class LCChatMemoryComponent(Component):
    trace_type = "chat_memory"
    outputs = [
        Output(
            display_name="Memory",
            name="memory",
            method="build_message_history",
        )
    ]

    def _validate_outputs(self) -> None:
        required_output_methods = ["build_message_history"]
        output_names = [output.name for output in self.outputs]
        for method_name in required_output_methods:
            if method_name not in output_names:
                msg = f"Output with name '{method_name}' must be defined."
                raise ValueError(msg)
            if not hasattr(self, method_name):
                msg = f"Method '{method_name}' must be defined."
                raise ValueError(msg)

    def build_base_memory(self) -> BaseChatMemory:
        """Builds the base memory."""
        return ConversationBufferMemory(chat_memory=self.build_message_history())

    @abstractmethod
    def build_message_history(self) -> Memory:
        """Builds the chat message history memory."""
