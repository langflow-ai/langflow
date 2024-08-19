from abc import abstractmethod

from langflow.custom import Component
from langflow.field_typing import BaseChatMessageHistory, BaseChatMemory
from langflow.template import Output
from langchain.memory import ConversationBufferMemory


class LCChatMemoryComponent(Component):
    trace_type = "chat_memory"
    outputs = [
        Output(
            display_name="Memory",
            name="memory",
            method="build_message_history",
        )
    ]

    def _validate_outputs(self):
        required_output_methods = ["build_message_history"]
        output_names = [output.name for output in self.outputs]
        for method_name in required_output_methods:
            if method_name not in output_names:
                raise ValueError(f"Output with name '{method_name}' must be defined.")
            elif not hasattr(self, method_name):
                raise ValueError(f"Method '{method_name}' must be defined.")

    def build_base_memory(self) -> BaseChatMemory:
        return ConversationBufferMemory(chat_memory=self.build_message_history())

    @abstractmethod
    def build_message_history(self) -> BaseChatMessageHistory:
        """
        Builds the chat message history memory.
        """
