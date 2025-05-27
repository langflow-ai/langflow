import asyncio
from typing import Any
from urllib.parse import urljoin

import httpx
from langchain_ollama import ChatOllama

from langflow.base.models.model import LCModelComponent
from langflow.base.models.ollama_constants import URL_LIST
from langflow.field_typing import LanguageModel
from langflow.field_typing.range_spec import RangeSpec
from langflow.io import (
    BoolInput, DictInput, DropdownInput, FloatInput, IntInput,
    MessageTextInput, SliderInput, TabInput
)
from langflow.logging import logger

HTTP_STATUS_OK = 200


class ChatOllamaComponent(LCModelComponent):
    display_name = "Ollama"
    description = "Generate text using Ollama Local LLMs."
    icon = "Ollama"
    name = "OllamaModel"

    # Define constants for JSON keys
    JSON_MODELS_KEY = "models"
    JSON_NAME_KEY = "name"
    JSON_CAPABILITIES_KEY = "capabilities"
    DESIRED_CAPABILITY = "completion"
    TOOL_CALLING_CAPABILITY = "tools"

    inputs = [
        MessageTextInput(name="base_url", display_name="Base URL", info="Endpoint of the Ollama API."),
        DropdownInput(name="model_name", display_name="Model Name", options=[],
                      info="Refer to https://ollama.com/library for more models.", refresh_button=True,required=True,
                      real_time_refresh=True),
        SliderInput(name="temperature", display_name="Temperature", value=0.1,
                    range_spec=RangeSpec(min=0, max=1, step=0.01), advanced=True),
        MessageTextInput(name="format", display_name="Format", info="Specify the format of the output (e.g., json).",
                         advanced=True),
        DictInput(name="metadata", display_name="Metadata", info="Metadata to add to the run trace.", advanced=True),
        TabInput(name="mirostat", display_name="Mirostat Mode", options=["Disabled", "Mirostat", "Mirostat 2.0"],
                 value="Disabled", info="Enable/disable Mirostat sampling for controlling perplexity.",
                 real_time_refresh=True),
                 
        SliderInput(
            name="mirostat_eta",
            display_name="Mirostat Eta",
            value=0.1,
            range_spec=RangeSpec(min=0.05, max=0.3, step=0.01),
            show=False,
            info="Learning rate for Mirostat algorithm"
        ),

        SliderInput(
            name="mirostat_tau",
            display_name="Mirostat Tau",
            value=5.0,
            range_spec=RangeSpec(min=2.0, max=6.0, step=0.5),
            show=False,
            info="Controls the balance between coherence and diversity"
        ),

        IntInput(name="num_ctx", display_name="Context Window Size",
                 info="Size of the context window for generating tokens. (Default: 2048)", advanced=True),
        IntInput(name="num_gpu", display_name="Number of GPUs",
                 info="Number of GPUs to use. (Default: 1 on macOS, 0 to disable)", advanced=True),
        IntInput(name="num_thread", display_name="Number of Threads",
                 info="Number of threads to use during computation.", advanced=True),
        IntInput(name="repeat_last_n", display_name="Repeat Last N",
                 info="How far back the model looks to prevent repetition. (Default: 64)", advanced=True),
        FloatInput(name="repeat_penalty", display_name="Repeat Penalty",
                   info="Penalty for repetitions. (Default: 1.1)", advanced=True),
        
        SliderInput(
            name="tfs_z",
            display_name="TFS Z",
            value=1.0,
            range_spec=RangeSpec(min=1.0, max=5.0, step=0.1),
            advanced=True,
            info="Tail free sampling value, where higher values reduce low-probability tokens"
        ),

        
        
        IntInput(name="timeout", display_name="Timeout", info="Timeout for the request stream.", advanced=True),
        IntInput(name="top_k", display_name="Top K", info="Limits token selection to top K.", advanced=True),
        
        
        SliderInput(
            name="top_p",
            display_name="Top P",
            value=0.9,
            range_spec=RangeSpec(min=0.0, max=1.0, step=0.01),
            advanced=True,
            info="Nucleus sampling threshold: lower = more focused, higher = more random"
        ),
        
        TabInput(
            name="keep_alive_mode",
            display_name="Keep Alive Mode",
            options=["Timed", "Forever", "Unload Immediately"],
            value="Timed",
            real_time_refresh=True,
            info="How long to keep the model in memory"
        ),

        IntInput(
            name="keep_alive_value",
            display_name="Duration Value",
            value=5,
            info="Value for keep-alive duration",
            show=True
        ),
        TabInput(
            name="keep_alive_unit",
            display_name="Duration Unit",
            options=["seconds", "minutes", "hours"],
            value="minutes",
            show=True
        ),

        
        IntInput(
            name="num_keep",
            display_name="Num Keep",
            info="Number of tokens to retain (e.g., system prompt)",
            value=4,
            advanced=True,
        ),
        
        IntInput(
            name="num_predict",
            display_name="Num Predict",
            info="Max tokens to generate (-1: unlimited, -2: remaining context)",
            value=-1,
            advanced=True,
        ),
        
        IntInput(
            name="seed",
            display_name="Seed",
            info="Random seed for reproducibility (-1: random)",
            value=-1,
            advanced=True,
        ),
        
        FloatInput(
            name="min_p",
            display_name="Min P",
            info="Minimum probability filtering threshold",
            value=0.0,
            advanced=True,
        ),
        
        FloatInput(
            name="typical_p",
            display_name="Typical P",
            info="Typical sampling threshold (1.0 disables it)",
            value=1.0,
            advanced=True,
        ),
        
        FloatInput(
            name="presence_penalty",
            display_name="Presence Penalty",
            info="Penalty for using previously appeared words",
            value=0.0,
            advanced=True,
        ),
        
        FloatInput(
            name="frequency_penalty",
            display_name="Frequency Penalty",
            info="Penalty for frequent words",
            value=0.0,
            advanced=True,
        ),
        
        BoolInput(
            name="penalize_newline",
            display_name="Penalize Newline",
            info="Apply penalty to newline tokens",
            value=True,
            advanced=True,
        ),
        
        BoolInput(
            name="truncate",
            display_name="Truncate Prompt",
            info="Trim the beginning of the prompt if it exceeds context length",
            value=True,
            advanced=True,
        ),
        
        IntInput(
            name="num_batch",
            display_name="Num Batch",
            info="Number of tokens processed per batch",
            value=512,
            advanced=True,
        ),
        
        IntInput(
            name="main_gpu",
            display_name="Main GPU Index",
            info="Index of the main GPU in multi-GPU setups",
            value=0,
            advanced=True,
        ),
        
        BoolInput(
            name="use_mmap",
            display_name="Use Mmap",
            info="Whether to use memory-mapped file I/O",
            value=True,
            advanced=True,
        ),
        
        BoolInput(
            name="use_mlock",
            display_name="Use Mlock",
            info="Lock mapped memory into RAM",
            value=False,
            advanced=True,
        ),
        
        BoolInput(
            name="low_vram",
            display_name="Low VRAM Mode",
            info="Minimize VRAM usage",
            value=False,
            advanced=True,
        ),
        
        BoolInput(
            name="f16_kv",
            display_name="FP16 KV Cache",
            info="Store key-value cache in FP16 for memory savings",
            value=True,
            advanced=True,
        ),
        
        BoolInput(
            name="logits_all",
            display_name="Logits All",
            info="Return logits for all tokens",
            value=False,
            advanced=True,
        ),
        
        BoolInput(
            name="vocab_only",
            display_name="Vocab Only",
            info="Only load vocabulary without model weights",
            value=False,
            advanced=True,
        ),
        
        BoolInput(
            name="cache_prompt",
            display_name="Cache Prompt",
            info="Enable prompt caching for faster responses",
            value=True,
            advanced=True,
        ),

        

        BoolInput(name="verbose", display_name="Verbose", info="Print out response text.", advanced=True),
        MessageTextInput(name="tags", display_name="Tags", info="Comma-separated tags.", advanced=True),
        MessageTextInput(name="stop_tokens", display_name="Stop Tokens",
                         info="Comma-separated list of stop tokens.", advanced=True),
        MessageTextInput(name="system", display_name="System", info="System prompt.", advanced=True),
        BoolInput(name="tool_model_enabled", display_name="Tool Model Enabled",
                  info="Enable tool calling support.", value=True, real_time_refresh=True),
        MessageTextInput(name="template", display_name="Template", info="Template to use for text generation.",
                         advanced=True),
        *LCModelComponent._base_inputs,
    ]


    def build_model(self) -> LanguageModel:# type: ignore[type-var]
        # Mapping mirostat settings to their corresponding values
        mirostat_map = {"Mirostat": 1, "Mirostat 2.0": 2}
        mirostat_val = mirostat_map.get(self.mirostat, 0)
        mirostat_eta = self.mirostat_eta if mirostat_val else None
        mirostat_tau = self.mirostat_tau if mirostat_val else None

        # Keep Alive 
        if self.keep_alive_mode == "Forever":
            keep_alive = "-1"
        elif self.keep_alive_mode == "Unload Immediately":
            keep_alive = "0"
        else:
            unit = self.keep_alive_unit[0]  # 's', 'm', 'h'
            keep_alive = f"{self.keep_alive_value}{unit}"
            
        """
        Attempt to cast `value` to `cast_type`. Return None if casting fails.
        This avoids runtime errors when optional fields are left blank.
        """

        def safe_cast(value, cast_type):
            try:
                return cast_type(value)
            except (ValueError, TypeError):
                return None
                
        # Mapping system settings to their corresponding values        

        params = {
            "base_url": self.base_url,
            "model": self.model_name,
            "mirostat": mirostat_val,
            "format": self.format,
            "metadata": self.metadata,
            "tags": self.tags.split(",") if self.tags else None,
            "mirostat_eta": mirostat_eta,
            "mirostat_tau": mirostat_tau,
            "num_ctx": safe_cast(self.num_ctx, int),
            "num_gpu": safe_cast(self.num_gpu, int),
            "num_thread": safe_cast(self.num_thread, int),
            "repeat_last_n": safe_cast(self.repeat_last_n, int),
            "repeat_penalty": safe_cast(self.repeat_penalty, float),
            "temperature": self.temperature,
            "stop": self.stop_tokens.split(",") if self.stop_tokens else None,
            "system": self.system,
            "tfs_z": self.tfs_z,
            "timeout": safe_cast(self.timeout, int),
            "top_k": safe_cast(self.top_k, int),
            "top_p": self.top_p,
            "verbose": self.verbose,
            "template": self.template,
            "keep_alive": keep_alive,
            "num_keep": safe_cast(self.num_keep, int),
            "num_predict": safe_cast(self.num_predict, int),
            "seed": safe_cast(self.seed, int),
            "min_p": self.min_p,
            "typical_p": self.typical_p,
            "presence_penalty": self.presence_penalty,
            "frequency_penalty": self.frequency_penalty,
            "penalize_newline": self.penalize_newline,
            "truncate": self.truncate,
            "num_batch": safe_cast(self.num_batch, int),
            "main_gpu": safe_cast(self.main_gpu, int),
            "use_mmap": self.use_mmap,
            "use_mlock": self.use_mlock,
            "low_vram": self.low_vram,
            "f16_kv": self.f16_kv,
            "logits_all": self.logits_all,
            "vocab_only": self.vocab_only,
            "cache_prompt": self.cache_prompt,
        }
        
        # Remove parameters with None values

        params = {k: v for k, v in params.items() if v is not None}

        try:
            return ChatOllama(**params)
        except Exception as e:
            raise ValueError("Could not initialize Ollama LLM.") from e




    async def is_valid_ollama_url(self, url: str) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                return (await client.get(urljoin(url, "api/tags"))).status_code == HTTP_STATUS_OK
        except httpx.RequestError:
            return False

    async def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None):
        if field_name == "mirostat":
            show = field_value != "Disabled"
            build_config["mirostat_eta"].update({"show": show})
            build_config["mirostat_tau"].update({"show": show})
            if field_value == "Mirostat 2.0":
                build_config["mirostat_eta"]["value"] = 0.2
                build_config["mirostat_tau"]["value"] = 10
            elif field_value == "Mirostat":
                build_config["mirostat_eta"]["value"] = 0.1
                build_config["mirostat_tau"]["value"] = 5
            else:
                build_config["mirostat_eta"]["value"] = None
                build_config["mirostat_tau"]["value"] = None

        if field_name in {"base_url", "model_name"}:
            base_url = build_config["base_url"].get("value")
            if not await self.is_valid_ollama_url(base_url):
                for url in [self.base_url] + URL_LIST:
                    if await self.is_valid_ollama_url(url):
                        build_config["base_url"]["value"] = url
                        break
                else:
                    raise ValueError("No valid Ollama URL found.")
                    
                    
        if field_name == "keep_alive_mode":
            timed = field_value == "Timed"
            build_config["keep_alive_value"].update({"show": timed})
            build_config["keep_alive_unit"].update({"show": timed})


        if field_name in {"model_name", "base_url", "tool_model_enabled"}:
            url = self.base_url or build_config["base_url"].get("value", "")
            if await self.is_valid_ollama_url(url):
                enabled = build_config["tool_model_enabled"].get("value", False) or self.tool_model_enabled
                build_config["model_name"]["options"] = await self.get_models(url, enabled)
            else:
                build_config["model_name"]["options"] = []

        return build_config

    async def get_models(self, base_url: str, tool_model_enabled: bool = False) -> list[str]:
        
        """Fetches a list of models from the Ollama API that do not have the "embedding" capability.

        Args:
            base_url_value (str): The base URL of the Ollama API.
            tool_model_enabled (bool | None, optional): If True, filters the models further to include
                only those that support tool calling. Defaults to None.

        Returns:
            list[str]: A list of model names that do not have the "embedding" capability. If
                `tool_model_enabled` is True, only models supporting tool calling are included.

        Raises:
            ValueError: If there is an issue with the API request or response, or if the model
                names cannot be retrieved.
        """
        
        try:
            tags_url = urljoin(base_url.rstrip("/"), "/api/tags")
            show_url = urljoin(base_url.rstrip("/"), "/api/show")

            async with httpx.AsyncClient() as client:
                tags_res = await client.get(tags_url)
                tags_res.raise_for_status()
                models = tags_res.json().get(self.JSON_MODELS_KEY, [])
                # Fetch available models
                valid_models = []
                
                # Filter models that are NOT embedding models
                for model in models:
                    name = model.get(self.JSON_NAME_KEY)
                    show_res = await client.post(show_url, json={"model": name})
                    show_res.raise_for_status()
                    capabilities = show_res.json().get(self.JSON_CAPABILITIES_KEY, [])
                    if self.DESIRED_CAPABILITY in capabilities:
                        if not tool_model_enabled or self.TOOL_CALLING_CAPABILITY in capabilities:
                            valid_models.append(name)

                return valid_models
        except Exception as e:
            raise ValueError("Could not get model names from Ollama.") from e
