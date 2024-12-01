from typing import Any
from urllib.parse import urljoin

import httpx
from langchain_ollama import ChatOllama

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.inputs.inputs import HandleInput
from langflow.io import BoolInput, DictInput, DropdownInput, FloatInput, IntInput, StrInput


class ChatOllamaComponent(LCModelComponent):
    display_name = "Ollama"
    description = "Generate text using Ollama Local LLMs."
    icon = "Ollama"
    name = "OllamaModel"

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None):
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

        if field_name == "model_name":
            base_url_dict = build_config.get("base_url", {})
            base_url_load_from_db = base_url_dict.get("load_from_db", False)
            base_url_value = base_url_dict.get("value")
            if base_url_load_from_db:
                base_url_value = self.variables(base_url_value, field_name)
            elif not base_url_value:
                base_url_value = "http://localhost:11434"
            build_config["model_name"]["options"] = self.get_model(base_url_value)
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

    def get_model(self, base_url_value: str) -> list[str]:
        try:
            url = urljoin(base_url_value, "/api/tags")
            with httpx.Client() as client:
                response = client.get(url)
                response.raise_for_status()
                data = response.json()

                return [model["name"] for model in data.get("models", [])]
        except Exception as e:
            msg = "Could not retrieve models. Please, make sure Ollama is running."
            raise ValueError(msg) from e

    inputs = [
        StrInput(
            name="base_url",
            display_name="Base URL",
            info="Endpoint of the Ollama API. Defaults to 'http://localhost:11434' if not specified.",
            value="http://localhost:11434",
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            value="llama3.1",
            info="Refer to https://ollama.com/library for more models.",
            refresh_button=True,
        ),
        FloatInput(
            name="temperature",
            display_name="Temperature",
            value=0.2,
            info="Controls the creativity of model responses.",
        ),
        StrInput(
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
        StrInput(
            name="tags",
            display_name="Tags",
            info="Comma-separated list of tags to add to the run trace.",
            advanced=True,
        ),
        StrInput(
            name="stop_tokens",
            display_name="Stop Tokens",
            info="Comma-separated list of tokens to signal the model to stop generating text.",
            advanced=True,
        ),
        StrInput(name="system", display_name="System", info="System to use for generating text.", advanced=True),
        StrInput(name="template", display_name="Template", info="Template to use for generating text.", advanced=True),
        HandleInput(
            name="output_parser",
            display_name="Output Parser",
            info="The parser to use to parse the output of the model",
            advanced=True,
            input_types=["OutputParser"],
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
            "template": self.template,
            "tfs_z": self.tfs_z or None,
            "timeout": self.timeout or None,
            "top_k": self.top_k or None,
            "top_p": self.top_p or None,
            "verbose": self.verbose,
        }

        # Remove parameters with None values
        llm_params = {k: v for k, v in llm_params.items() if v is not None}

        try:
            output = ChatOllama(**llm_params)
        except Exception as e:
            msg = "Could not initialize Ollama LLM."
            raise ValueError(msg) from e

        return output
