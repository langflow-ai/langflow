from langflow.custom import Component
from langflow.inputs import HandleInput
from langflow.io import Output


class LangChainHubMessagesComponent(Component):
    display_name: str = "LangChain Hub Messages Component"
    description: str = "Messages Component that uses LangChain Hub prompts"
    beta = True
    icon = "prompts"
    trace_type = "prompt"
    name = "LangChain Hub Messages"

    inputs = [
        HandleInput(
            name="chat_prompt_value",
            display_name="ChatPromptValue",
            info="The ChatPromptValue object to extract messages from.",
            input_types=["ChatPromptValue"],
        )
    ]

    outputs = [
        Output(display_name="View Messages", name="messages", method="view_messages"),
    ]
    
    def view_messages(
        self,
    ) -> str:
        messages = self.chat_prompt_value.to_messages()
        self.status = str(messages)

        return self.status