from typing import Any, List, Optional

import httpx
from langchain_community.chat_models.ollama import ChatOllama

from langflow.base.constants import STREAM_INFO_TEXT
from langflow.base.models.model import LCModelComponent
from langflow.field_typing import BaseLanguageModel, Text
from langflow.template.field.base import Input, Output


class ChatOllamaComponent(LCModelComponent):
    display_name = "Ollama"
    description = "Generate text using Ollama Local LLMs."
    icon = "Ollama"

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

        if field_name == "model":
            base_url_dict = build_config.get("base_url", {})
            base_url_load_from_db = base_url_dict.get("load_from_db", False)
            base_url_value = base_url_dict.get("value")
            if base_url_load_from_db:
                base_url_value = self.variables(base_url_value)
            elif not base_url_value:
                base_url_value = "http://localhost:11434"
            build_config["model"]["options"] = self.get_model(base_url_value + "/api/tags")

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

    def get_model(self, url: str) -> List[str]:
        try:
            with httpx.Client() as client:
                response = client.get(url)
                response.raise_for_status()
                data = response.json()

                model_names = [model["name"] for model in data.get("models", [])]
                return model_names
        except Exception as e:
            raise ValueError("Could not retrieve models") from e

    inputs = [
        Input(
            name="base_url",
            type=Optional[str],
            display_name="Base URL",
            info="Endpoint of the Ollama API. Defaults to 'http://localhost:11434' if not specified.",
            value="http://localhost:11434",
        ),
        Input(
            name="model",
            type=str,
            display_name="Model Name",
            options=[],  # This should be dynamically loaded if possible
            info="Refer to https://ollama.ai/library for more models.",
            real_time_refresh=True,
            refresh_button=True,
        ),
        Input(
            name="mirostat",
            type=str,
            display_name="Mirostat",
            options=["Disabled", "Mirostat", "Mirostat 2.0"],
            info="Enable/disable Mirostat sampling for controlling perplexity.",
            advanced=False,
            real_time_refresh=True,
            refresh_button=True,
            value="Disabled",
        ),
        Input(
            name="mirostat_eta",
            type=Optional[float],
            display_name="Mirostat Eta",
            info="Learning rate for Mirostat algorithm.",
            advanced=True,
            real_time_refresh=True,
            value=None,  # Default can vary based on mirostat status
        ),
        Input(
            name="mirostat_tau",
            type=Optional[float],
            display_name="Mirostat Tau",
            info="Controls the balance between coherence and diversity of the output.",
            advanced=True,
            real_time_refresh=True,
            value=None,  # Default can vary based on mirostat status
        ),
        Input(
            name="temperature",
            type=float,
            display_name="Temperature",
            info="Controls the creativity of model responses.",
            value=0.8,
        ),
        Input(name="input_value", type=str, display_name="Input", input_types=["Text", "Record", "Prompt"]),
        Input(name="stream", type=bool, display_name="Stream", info=STREAM_INFO_TEXT, value=False),
        Input(
            name="system_message",
            type=Optional[str],
            display_name="System Message",
            info="System message to pass to the model.",
            advanced=True,
            value=None,
        ),
        Input(
            name="headers",
            type=dict,
            display_name="Headers",
            info="Additional headers to send with the request.",
            advanced=True,
        ),
        Input(
            name="keep_alive_flag",
            type=str,
            display_params=["Keep", "Immediately", "Minute", "Hour", "sec"],
            display_name="Unload interval",
            info="Controls how the model unload interval is managed.",
            real_time_refresh=True,
            refresh_button=True,
        ),
        Input(
            name="keep_alive",
            type=int,
            display_name="Interval",
            info="How long the model will stay loaded into memory.",
            value=None,
        ),
    ]
    outputs = [
        Output(display_name="Text", name="text_output", method="text_response"),
        Output(display_name="Language Model", name="model_output", method="model_response"),
    ]

    def text_response(self) -> Text:
        input_value = self.input_value
        stream = self.stream
        system_message = self.system_message
        output = self.model_response()
        result = self.get_chat_result(output, stream, input_value, system_message)
        self.status = result
        return result

    def model_response(self) -> BaseLanguageModel:
        base_url = self.base_url or "http://localhost:11434"
        model = self.model
        mirostat = self.mirostat or "Disabled"
        mirostat_eta = self.mirostat_eta
        mirostat_tau = self.mirostat_tau
        repeat_last_n = self.repeat_last_n
        verbose = self.verbose
        keep_alive = self.keep_alive
        keep_alive_flag = self.keep_alive_flag or "Keep"
        num_ctx = self.num_ctx
        num_gpu = self.num_gpu
        _format = self.format
        metadata = self.metadata
        num_thread = self.num_thread
        repeat_penalty = self.repeat_penalty
        stop = self.stop
        system = self.system
        tags = self.tags
        temperature = self.temperature
        template = self.template
        tfs_z = self.tfs_z
        timeout = self.timeout
        top_k = self.top_k
        top_p = self.top_p
        headers = self.headers

        if keep_alive_flag == "Minute":
            keep_alive_instance = f"{keep_alive}m"
        elif keep_alive_flag == "Hour":
            keep_alive_instance = f"{keep_alive}h"
        elif keep_alive_flag == "sec":
            keep_alive_instance = f"{keep_alive}s"
        elif keep_alive_flag == "Keep":
            keep_alive_instance = "-1"
        elif keep_alive_flag == "Immediately":
            keep_alive_instance = "0"
        else:
            keep_alive_instance = "Invalid option"

        mirostat_instance = 0
        if mirostat == "disable":
            mirostat_instance = 0

        llm_params = {
            "base_url": base_url,
            "model": model,
            "mirostat": mirostat_instance,
            "keep_alive": keep_alive_instance,
            "format": _format,
            "metadata": metadata,
            "tags": tags,
            "mirostat_eta": mirostat_eta,
            "mirostat_tau": mirostat_tau,
            "num_ctx": num_ctx,
            "num_gpu": num_gpu,
            "num_thread": num_thread,
            "repeat_last_n": repeat_last_n,
            "repeat_penalty": repeat_penalty,
            "temperature": temperature,
            "stop": stop,
            "system": system,
            "template": template,
            "tfs_z": tfs_z,
            "timeout": timeout,
            "top_k": top_k,
            "top_p": top_p,
            "verbose": verbose,
            "headers": headers,
        }

        llm_params = {k: v for k, v in llm_params.items() if v is not None}

        try:
            output = ChatOllama(**llm_params)
        except Exception as e:
            raise ValueError("Could not initialize Ollama LLM.") from e

        return output
