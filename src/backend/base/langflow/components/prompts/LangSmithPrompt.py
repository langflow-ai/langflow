from langchain import hub
from langflow.base.agents.agent import PromptComponent
from langflow.inputs import StrInput, SecretStrInput
from langflow.io import Output
from langflow.schema.message import Message


class LangSmithPromptComponent(PromptComponent):
    display_name: str = "LangSmith Prompt Component"
    description: str = "Prompt Component that uses LangSmith prompts"
    beta = True
    icon = "prompts"
    trace_type = "prompt"
    name = "LangSmith Prompt"

    inputs = PromptComponent._base_inputs + [
        SecretStrInput(
            name="langchain_api_key",
            display_name="Your LangChain API Key",
            info="The LangChain API Key to use.",
        ),
        StrInput(
            name="langsmith_prompt",
            display_name="LangSmith Prompt",
            info="The LangSmith prompt to use.",
            value="efriis/my-first-prompt",
        ),
    ]

    outputs = [
        Output(display_name="Prompt Message", name="prompt", method="build_prompt"),
    ]

    def build_prompt(
        self,
    ) -> Message:
        # Pull the prompt from LangChain Hub
        prompt_data = hub.pull(self.langsmith_prompt)

        # Extract the messages from the prompt data
        message_list = []
        for message_data in prompt_data.messages:
            message_list.append(message_data.prompt)

        # Create a Message object from the messages
        messages = Message(messages=message_list)

        # Set the status to the messages
        self.status = str(messages)
        
        return messages
