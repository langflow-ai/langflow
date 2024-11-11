import requests
import warnings

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from notdiamond import NotDiamond

from langflow.custom import Component
from langflow.io import (
    BoolInput,
    DropdownInput,
    MessageInput,
    MessageTextInput,
    MultiselectInput,
    Output,
    SecretStrInput,
    StrInput,
)
from langflow.schema.message import Message

ND_MODEL_MAPPING = {
    "gpt-4o": "openai/gpt-4o",
    "gpt-4o-mini": "openai/gpt-4o-mini",
    "gpt-4-turbo": "openai/gpt-4-turbo-2024-04-09",
    "claude-3-5-haiku": "anthropic/claude-3-5-haiku-20241022",
    "claude-3.5-sonnet": "anthropic/claude-3-5-sonnet-20241022",
    "gemini-1.5-pro": "google/gemini-1.5-pro-latest",
    "gemini-1.5-flash": "google/gemini-1.5-flash-latest",
    "llama-3.1-70B": "meta/Meta-Llama-3.1-70B-Instruct-Turbo",
    "llama-3.1-405B": "meta/Meta-Llama-3.1-405B-Instruct-Turbo",
    "perplexity": "perplexity/llama-3.1-sonar-large-128k-online",
    "mistral-large-2": "mistral/mistral-large-2407",
}


class NotDiamondComponent(Component):
    display_name = "Not Diamond Router"
    description = "Call the right model at the right time with the world's most powerful AI model router."
    icon = "split"
    name = "NotDiamond"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    inputs = [
        MessageInput(name="input_value", display_name="Input"),
        MessageTextInput(
            name="system_message",
            display_name="System Message",
            info="System message to pass to the model.",
            advanced=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="Not Diamond API Key",
            info="The Not Diamond API Key to use for routing.",
            advanced=False,
            value="NOTDIAMOND_API_KEY",
        ),
        MultiselectInput(
            name="models",
            display_name="Models",
            info="Select the models between which you want to route.",
            advanced=False,
            options=[
                "gpt-4o",
                "gpt-4o-mini",
                "gpt-4-turbo",
                "claude-3-5-haiku",
                "claude-3.5-sonnet",
                "gemini-1.5-pro",
                "gemini-1.5-flash",
                "llama-3.1-70B",
                "llama-3.1-405B",
                "perplexity",
                "mistral-large-2",
            ],
            value=["gpt-4o"],
        ),
        StrInput(
            name="preference_id",
            display_name="Preference ID",
            info="The ID of the router preference that was configured via the Dashboard.",
            advanced=False,
        ),
        DropdownInput(
            name="tradeoff",
            display_name="Tradeoff",
            info="The tradeoff between cost and latency for the router to determine the best LLM for a given query.",
            advanced=False,
            options=["cost", "latency"],
            value="cost",
        ),
        BoolInput(
            name="hash_content",
            display_name="Hash Content",
            info="Whether to hash the content before being sent to the NotDiamond API.",
            advanced=False,
            value=False,
        ),
    ]

    outputs = [Output(display_name="Model", name="model_selected", method="model_select")]

    def model_select(self) -> str:
        input_value = self.input_value
        system_message = self.system_message
        selected_models = []

        nd = NotDiamond(api_key=self.api_key)

        if self.models:
            selected_models = list(filter(None, [ND_MODEL_MAPPING.get(model) for model in self.models]))

        # response = requests.post(
        #     "https://api.notdiamond.ai/v2/modelRouter/modelSelect",
        #     json={
        #         "messages": [],
        #         "tradeoff": self.tradeoff,
        #         "llm_providers": selected_models,
        #         "hash_content": self.hash_content,
        #         "preference_id": self.preference_id,
        #     },
        # )

        # return response.json()

    def _format_input(
        self,
        input_value: str | Message,
        system_message: str | None = None,
    ):
        messages: list[BaseMessage] = []
        if not input_value and not system_message:
            msg = "The message you want to send to the router is empty."
            raise ValueError(msg)
        system_message_added = False
        if input_value:
            if isinstance(input_value, Message):
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    if "prompt" in input_value:
                        prompt = input_value.load_lc_prompt()
                        if system_message:
                            prompt.messages = [
                                SystemMessage(content=system_message),
                                *prompt.messages,  # type: ignore[has-type]
                            ]
                            system_message_added = True
                    else:
                        messages.append(input_value.to_lc_message())
            else:
                messages.append(HumanMessage(content=input_value))

        if system_message and not system_message_added:
            messages.insert(0, SystemMessage(content=system_message))

        return messages
