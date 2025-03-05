from langchain_openai import ChatOpenAI
from pydantic.v1 import SecretStr

from langflow.base.models.model import LCModelComponent
from langflow.base.models.sambanova_constants import SAMBANOVA_MODEL_NAMES
from langflow.field_typing import LanguageModel
from langflow.inputs.inputs import HandleInput
from langflow.io import DropdownInput, FloatInput, IntInput, SecretStrInput, StrInput, BoolInput


class MacrocosmosComponent(LCModelComponent):
    display_name = "Macrocosmos"
    description = "Generate text using Macrocosmos' Apex, powered by Bittensor."
    documentation = "https://app.macrocosmos.ai"
    icon = "SambaNova"
    name = "SambaNovaModel"

    inputs = [
        *LCModelComponent._base_inputs,
        StrInput(
            name="macrocosmos_url",
            display_name="Macrocosmos Base Url",
            advanced=True,
            info="The base URL of the Macrocosmos API. "
            "Defaults to https://sn1.api.macrocosmos.ai/v1/chat/completions "
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            advanced=True,
            options=["hugging-quants/Meta-Llama-3.1-70B-Instruct-AWQ-INT4", "Default"],
            value="Default",
        ),
        DropdownInput(
            name="inference_mode",
            display_name="Inference Mode",
            advanced=True,
            options = ["Base-Inference", "Chain-of-Thought", "Reasoning-Fast", "Mixture-of-Agents"],
            value="Base-Inference",
        ),
        SecretStrInput(
            name="macrocosmos_api_key",
            display_name="Macrocosmos API Key",
            info="The Macrocosmos API Key to use for Apex.",
            advanced=False,
            value="MACROCOSMOS_API_KEY",
        ),
        IntInput(
            name="max_new_tokens",
            display_name="Max New Tokens",
            advanced=True,
            value=4096,
            info="The maximum number of tokens to generate.",
        ),
        IntInput(name="top_k", display_name="Top-K", advanced=True, value=50),
        FloatInput(name="top_p", display_name="Top-P", advanced=True, value=0.95),
        FloatInput(name="temperature", display_name="Temperature", advanced=True, value=0.7),
        BoolInput(name= "do_sample", display_name="Do Sample", advanced=True, value=True),
        HandleInput(
            name="output_parser",
            display_name="Output Parser",
            info="The parser to use to parse the output of the model",
            advanced=True,
            input_types=["OutputParser"],
        ),
    ]

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        macrocosmos_url = self.macrocosmos_url
        macrocosmos_api_key = self.macrocosmos_api_key
        model_name = self.model_name
        sample_params = {
            "top_k": self.top_k,
            "top_p": self.top_p,
            "temperature": self.temperature,
            "do_sample": self.do_sample,
        }
        seed = self.seed
        inference_mode = self.inference_mode

        api_key = SecretStr(macrocosmos_api_key).get_secret_value() if macrocosmos_api_key else None

        return ChatOpenAI(
            model=model_name,
            base_url=macrocosmos_url,
            api_key=str(api_key),
            inference_mode=inference_mode,
            extra_body = sample_params,
            seed=seed,
        )