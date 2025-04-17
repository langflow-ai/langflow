from typing import Any
from urllib.parse import urljoin

import httpx
from langchain_ollama import ChatOllama

from langflow.base.models.model import LCModelComponent
from langflow.base.models.ollama_constants import OLLAMA_EMBEDDING_MODELS, OLLAMA_TOOL_MODELS_BASE, URL_LIST
from langflow.field_typing import LanguageModel
from langflow.field_typing.range_spec import RangeSpec
from langflow.io import BoolInput, DictInput, DropdownInput, FloatInput, IntInput, MessageTextInput, SliderInput

HTTP_STATUS_OK = 200


class ChatOllamaComponent(LCModelComponent):
    display_name = "Ollama"
    description = "Generate text using Ollama Local LLMs."
    icon = "Ollama"
    name = "OllamaModel"

    inputs = [
        MessageTextInput(
            name="base_url",
            display_name="Base URL",
            info="Endpoint of the Ollama API.",
            value="",
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            options=[],
            info="Refer to https://ollama.com/library for more models.",
            refresh_button=True,
            real_time_refresh=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.1,
            range_spec=RangeSpec(min=0, max=1, step=0.01),
            advanced=True,
        ),
        MessageTextInput(
            name="format", display_name="Format", info="Specify the format of the output (e.g., json).", advanced=True
        ),
        DictInput(name="metadata", display_name="Metadata", info="Metadata to add to the run trace.", advanced=True),
        DropdownInput(
            name="mirostat",
            display_name="Mirostat",
            options=["Disabled", "Mirostat", "Mirostat 2.0"],
            info="Enable/disable Mirostat sampling for controlling perplexity.",
            value="Disabled",
            advanced=True,
            real_time_refresh=True,
        ),
        FloatInput(
            name="mirostat_eta",
            display_name="Mirostat Eta",
            info="Learning rate for Mirostat algorithm. (Default: 0.1)",
            advanced=True,
        ),
        FloatInput(
            name="mirostat_tau",
            display_name="Mirostat Tau",
            info="Controls the balance between coherence and diversity of the output. (Default: 5.0)",
            advanced=True,
        ),
        IntInput(
            name="num_ctx",
            display_name="Context Window Size",
            info="Size of the context window for generating tokens. (Default: 2048)",
            advanced=True,
        ),
        IntInput(
            name="num_gpu",
            display_name="Number of GPUs",
            info="Number of GPUs to use for computation. (Default: 1 on macOS, 0 to disable)",
            advanced=True,
        ),
        IntInput(
            name="num_thread",
            display_name="Number of Threads",
            info="Number of threads to use during computation. (Default: detected for optimal performance)",
            advanced=True,
        ),
        IntInput(
            name="repeat_last_n",
            display_name="Repeat Last N",
            info="How far back the model looks to prevent repetition. (Default: 64, 0 = disabled, -1 = num_ctx)",
            advanced=True,
        ),
        FloatInput(
            name="repeat_penalty",
            display_name="Repeat Penalty",
            info="Penalty for repetitions in generated text. (Default: 1.1)",
            advanced=True,
        ),
        FloatInput(name="tfs_z", display_name="TFS Z", info="Tail free sampling value. (Default: 1)", advanced=True),
        IntInput(name="timeout", display_name="Timeout", info="Timeout for the request stream.", advanced=True),
        IntInput(
            name="top_k", display_name="Top K", info="Limits token selection to top K. (Default: 40)", advanced=True
        ),
        FloatInput(name="top_p", display_name="Top P", info="Works together with top-k. (Default: 0.9)", advanced=True),
        BoolInput(name="verbose", display_name="Verbose", info="Whether to print out response text.", advanced=True),
        MessageTextInput(
            name="tags",
            display_name="Tags",
            info="Comma-separated list of tags to add to the run trace.",
            advanced=True,
        ),
        MessageTextInput(
            name="stop_tokens",
            display_name="Stop Tokens",
            info="Comma-separated list of tokens to signal the model to stop generating text.",
            advanced=True,
        ),
        MessageTextInput(
            name="system", display_name="System", info="System to use for generating text.", advanced=True
        ),
        BoolInput(
            name="tool_model_enabled",
            display_name="Tool Model Enabled",
            info="Whether to enable tool calling in the model.",
            value=False,
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="template", display_name="Template", info="Template to use for generating text.", advanced=True
        ),
        *LCModelComponent._base_inputs,
    ]

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        # Mapping mirostat settings to their corresponding values
        mirostat_options = {"Mirostat": 1, "Mirostat 2.0": 2}

        # Default to 0 for 'Disabled'
        mirostat_value = mirostat_options.get(self.mirostat, 0)

        # Set mirostat_eta and mirostat_tau to None if mirostat is disabled
        if mirostat_value == 0:
            mirostat_eta = None
            mirostat_tau = None
        else:
            mirostat_eta = self.mirostat_eta
            mirostat_tau = self.mirostat_tau

        # Mapping system settings to their corresponding values
        llm_params = {
            "base_url": self.base_url,
            "model": self.model_name,
            "mirostat": mirostat_value,
            "format": self.format,
            "metadata": self.metadata,
            "tags": self.tags.split(",") if self.tags else None,
            "mirostat_eta": mirostat_eta,
            "mirostat_tau": mirostat_tau,
            "num_ctx": self.num_ctx or None,
            "num_gpu": self.num_gpu or None,
            "num_thread": self.num_thread or None,
            "repeat_last_n": self.repeat_last_n or None,
            "repeat_penalty": self.repeat_penalty or None,
            "temperature": self.temperature or None,
            "stop": self.stop_tokens.split(",") if self.stop_tokens else None,
            "system": self.system,
            "tfs_z": self.tfs_z or None,
            "timeout": self.timeout or None,
            "top_k": self.top_k or None,
            "top_p": self.top_p or None,
            "verbose": self.verbose,
            "template": self.template,
        }

        # Remove parameters with None values
        llm_params = {k: v for k, v in llm_params.items() if v is not None}

        try:
            output = ChatOllama(**llm_params)
        except Exception as e:
            msg = (
                "Unable to connect to the Ollama API. ",
                "Please verify the base URL, ensure the relevant Ollama model is pulled, and try again.",
            )
            raise ValueError(msg) from e

        return output

    async def is_valid_ollama_url(self, url: str) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                return (await client.get(urljoin(url, "api/tags"))).status_code == HTTP_STATUS_OK
        except httpx.RequestError:
            return False

    async def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None):
        if field_name == "mirostat":
            if field_value == "Disabled":
                build_config["mirostat_eta"]["advanced"] = True
                build_config["mirostat_tau"]["advanced"] = True
                build_config["mirostat_eta"]["value"] = None
                build_config["mirostat_tau"]["value"] = None

            else:
                build_config["mirostat_eta"]["advanced"] = False
                build_config["mirostat_tau"]["advanced"] = False

                if field_value == "Mirostat 2.0":
                    build_config["mirostat_eta"]["value"] = 0.2
                    build_config["mirostat_tau"]["value"] = 10
                else:
                    build_config["mirostat_eta"]["value"] = 0.1
                    build_config["mirostat_tau"]["value"] = 5

        if field_name in {"base_url", "model_name"} and not await self.is_valid_ollama_url(
            build_config["base_url"].get("value", "")
        ):
            # Check if any URL in the list is valid
            valid_url = ""
            for url in URL_LIST:
                if await self.is_valid_ollama_url(url):
                    valid_url = url
                    break
            if valid_url != "":
                build_config["base_url"]["value"] = valid_url
            else:
                msg = "No valid Ollama URL found."
                raise ValueError(msg)
        if field_name in {"model_name", "base_url", "tool_model_enabled"}:
            if await self.is_valid_ollama_url(self.base_url):
                tool_model_enabled = build_config["tool_model_enabled"].get("value", False) or self.tool_model_enabled
                build_config["model_name"]["options"] = await self.get_model(self.base_url, tool_model_enabled)
            elif await self.is_valid_ollama_url(build_config["base_url"].get("value", "")):
                tool_model_enabled = build_config["tool_model_enabled"].get("value", False) or self.tool_model_enabled
                build_config["model_name"]["options"] = await self.get_model(
                    build_config["base_url"].get("value", ""), tool_model_enabled
                )
            else:
                build_config["model_name"]["options"] = []
        if field_name == "keep_alive_flag":
            if field_value == "Keep":
                build_config["keep_alive"]["value"] = "-1"
                build_config["keep_alive"]["advanced"] = True
            elif field_value == "Immediately":
                build_config["keep_alive"]["value"] = "0"
                build_config["keep_alive"]["advanced"] = True
            else:
                build_config["keep_alive"]["advanced"] = False

        return build_config

    async def get_model(self, base_url_value: str, tool_model_enabled: bool | None = None) -> list[str]:
        try:
            url = urljoin(base_url_value, "api/tags")
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

            model_ids = [model["name"] for model in data.get("models", [])]
            # this to ensure that not embedding models are included.
            # not even the base models since models can have 1b 2b etc
            # handles cases when embeddings models have tags like :latest - etc.
            model_ids = [
                model
                for model in model_ids
                if not any(
                    model == embedding_model or model.startswith(embedding_model.split("-")[0])
                    for embedding_model in OLLAMA_EMBEDDING_MODELS
                )
            ]

        except (ImportError, ValueError, httpx.RequestError, Exception) as e:
            msg = "Could not get model names from Ollama."
            raise ValueError(msg) from e
        return (
            model_ids if not tool_model_enabled else [model for model in model_ids if self.supports_tool_calling(model)]
        )

    def supports_tool_calling(self, model: str) -> bool:
        """Check if model name is in the base of any models example llama3.3 can have 1b and 2b."""
        return any(model.startswith(f"{tool_model}") for tool_model in OLLAMA_TOOL_MODELS_BASE)
