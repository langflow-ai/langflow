import warnings

import requests
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic.v1 import SecretStr

from langflow.base.models.model import LCModelComponent
from langflow.io import (
    BoolInput,
    DropdownInput,
    MultiselectInput,
    Output,
    SecretStrInput,
    StrInput,
)
from langflow.schema.message import Message

ND_MODEL_MAPPING = {
    "gpt-4o": {"provider": "openai", "model": "gpt-4o"},
    "gpt-4o-mini": {"provider": "openai", "model": "gpt-4o-mini"},
    "gpt-4-turbo": {"provider": "openai", "model": "gpt-4-turbo-2024-04-09"},
    "claude-3-5-haiku": {"provider": "anthropic", "model": "claude-3-5-haiku-20241022"},
    "claude-3.5-sonnet V2": {"provider": "anthropic", "model": "claude-3-5-sonnet-20241022"},
    "gemini-1.5-pro": {"provider": "google", "model": "gemini-1.5-pro-latest"},
    "gemini-1.5-flash": {"provider": "google", "model": "gemini-1.5-flash-latest"},
    "llama-3.1-70B": {"provider": "togetherai", "model": "Meta-Llama-3.1-70B-Instruct-Turbo"},
    "llama-3.1-405B": {"provider": "togetherai", "model": "Meta-Llama-3.1-405B-Instruct-Turbo"},
    "perplexity": {"provider": "perplexity", "model": "llama-3.1-sonar-large-128k-online"},
    "mistral-large-2": {"provider": "mistral", "model": "mistral-large-2407"},
}


class NotDiamondComponent(LCModelComponent):
    display_name = "Not Diamond Router"
    description = "Call the right model at the right time with the world's most powerful AI model router."
    icon = "split"
    name = "NotDiamond"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    inputs = [
        *LCModelComponent._base_inputs,
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
            options=ND_MODEL_MAPPING.keys(),
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
            options=["quality", "cost", "latency"],
            value="quality",
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
        api_key = SecretStr(self.api_key).get_secret_value() if self.api_key else None
        input_value = self.input_value
        system_message = self.system_message
        messages = self._format_input(input_value, system_message)
        selected_models = []

        if self.models:
            selected_models = list(filter(None, [ND_MODEL_MAPPING.get(model) for model in self.models]))

        payload = {
            "messages": messages,
            "llm_providers": selected_models,
            "hash_content": self.hash_content,
        }

        if self.tradeoff != "quality":
            payload["tradeoff"] = self.tradeoff

        if self.preference_id and self.preference_id != "":
            payload["preference_id"] = self.preference_id

        header = {
            "Authorization": f"Bearer {api_key}",
            "accept": "application/json",
            "content-type": "application/json",
        }

        response = requests.post(
            "https://api.notdiamond.ai/v2/modelRouter/modelSelect",
            json=payload,
            headers=header,
            timeout=10,
        )

        result = response.json()

        if "providers" not in result:
            return result

        providers = result["providers"]

        if len(providers) == 0:
            return "No providers returned from NotDiamond API."

        chosen_provider = providers[0]
        chosen_model = [
            k
            for k, v in ND_MODEL_MAPPING.items()
            if v["provider"] == chosen_provider["provider"] and v["model"] == chosen_provider["model"]
        ]

        if len(chosen_model) == 0:
            return "No model found by NotDiamond API."

        return chosen_model[0]

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
                        messages.extend(prompt.messages)
                    else:
                        messages.append(input_value.to_lc_message())
            else:
                messages.append(HumanMessage(content=input_value))

        if system_message and not system_message_added:
            messages.insert(0, SystemMessage(content=system_message))

        # Convert Langchain messages to OpenAI format
        openai_messages = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                openai_messages.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                openai_messages.append({"role": "assistant", "content": msg.content})
            elif isinstance(msg, SystemMessage):
                openai_messages.append({"role": "system", "content": msg.content})

        return openai_messages
