import json

import requests

from langflow.base.models.chat_result import get_chat_result
from langflow.base.models.model_utils import get_model_name
from langflow.custom import Component
from langflow.io import DropdownInput, HandleInput, Output
from langflow.schema.message import Message


class LLMRouterComponent(Component):
    display_name = "LLM Router"
    description = "Routes the input to the most appropriate LLM based on OpenRouter model specifications"
    icon = "git-branch"

    inputs = [
        HandleInput(
            name="models",
            display_name="Language Models",
            input_types=["LanguageModel"],
            required=True,
            is_list=True,
            info="List of LLMs to route between",
        ),
        HandleInput(
            name="input_value",
            display_name="Input",
            input_types=["Message"],
            info="The input message to be routed",
        ),
        HandleInput(
            name="judge_llm",
            display_name="Judge LLM",
            input_types=["LanguageModel"],
            info="LLM that will evaluate and select the most appropriate model",
        ),
        DropdownInput(
            name="optimization",
            display_name="Optimization",
            options=["quality", "speed", "cost", "balanced"],
            value="balanced",
            info="Optimization preference for model selection",
        ),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="route_to_model"),
        Output(
            display_name="Selected Model",
            name="selected_model",
            method="get_selected_model",
            required_inputs=["output"],
        ),
    ]

    _selected_model_name: str | None = None

    def get_selected_model(self) -> str:
        return self._selected_model_name or ""

    def _get_model_specs(self, model_name: str) -> str:
        """Fetch specific model information from OpenRouter API."""
        http_success = 200
        base_info = f"Model: {model_name}\n"

        # Remove any special characters and spaces, keep only alphanumeric
        clean_name = "".join(c.lower() for c in model_name if c.isalnum())
        url = f"https://openrouter.ai/api/v1/models/{clean_name}/endpoints"

        try:
            response = requests.get(url, timeout=10)
        except requests.exceptions.RequestException as e:
            return base_info + f"Error fetching specs: {e!s}"

        if response.status_code != http_success:
            return base_info + "No specifications available"

        try:
            data = response.json().get("data", {})
        except (json.JSONDecodeError, requests.exceptions.JSONDecodeError):
            return base_info + "Error parsing response data"

        # Extract relevant information
        context_length = data.get("context_length", "Unknown")
        max_completion_tokens = data.get("max_completion_tokens", "Unknown")
        architecture = data.get("architecture", {})
        tokenizer = architecture.get("tokenizer", "Unknown")
        instruct_type = architecture.get("instruct_type", "Unknown")

        pricing = data.get("pricing", {})
        prompt_price = pricing.get("prompt", "Unknown")
        completion_price = pricing.get("completion", "Unknown")

        description = data.get("description", "No description available")
        created = data.get("created", "Unknown")

        return f"""
Model: {model_name}
Description: {description}
Context Length: {context_length} tokens
Max Completion Tokens: {max_completion_tokens}
Tokenizer: {tokenizer}
Instruct Type: {instruct_type}
Pricing: ${prompt_price}/1k tokens (prompt), ${completion_price}/1k tokens (completion)
Created: {created}
"""

    MISSING_INPUTS_MSG = "Missing required inputs: models, input_value, or judge_llm"

    async def route_to_model(self) -> Message:
        if not self.models or not self.input_value or not self.judge_llm:
            raise ValueError(self.MISSING_INPUTS_MSG)

        system_prompt = {
            "role": "system",
            "content": (
                "You are a model selection expert. Analyze the input and select the most "
                "appropriate model based on:\n"
                "1. Task complexity and requirements\n"
                "2. Context length needed\n"
                "3. Model capabilities\n"
                "4. Cost considerations\n"
                "5. Speed requirements\n\n"
                "Consider the detailed model specifications provided and the user's "
                "optimization preference. Return only the index number (0-based) of the best model."
            ),
        }

        # Create list of available models with their detailed specs
        models_info = []
        for i, model in enumerate(self.models):
            model_name = get_model_name(model)
            model_specs = self._get_model_specs(model_name)
            models_info.append(f"=== Model {i} ===\n{model_specs}")

        models_str = "\n\n".join(models_info)

        user_message = {
            "role": "user",
            "content": f"""Available Models with Specifications:\n{models_str}\n
            Optimization Preference: {self.optimization}\n
            Input Query: "{self.input_value.text}"\n
            Based on the model specifications and optimization preference,
            select the most appropriate model (return only the index number):""",
        }

        try:
            # Get judge's decision
            response = await self.judge_llm.ainvoke([system_prompt, user_message])

            try:
                selected_index = int(response.content.strip())
                if 0 <= selected_index < len(self.models):
                    chosen_model = self.models[selected_index]
                    self._selected_model_name = get_model_name(chosen_model)
                else:
                    chosen_model = self.models[0]
                    self._selected_model_name = get_model_name(chosen_model)
            except ValueError:
                chosen_model = self.models[0]
                self._selected_model_name = get_model_name(chosen_model)

            # Get response from chosen model
            return get_chat_result(
                runnable=chosen_model,
                input_value=self.input_value,
            )

        except (RuntimeError, ValueError) as e:
            self.status = f"Error: {e!s}"
            # Fallback to first model
            chosen_model = self.models[0]
            self._selected_model_name = get_model_name(chosen_model)
            return get_chat_result(
                runnable=chosen_model,
                input_value=self.input_value,
            )
