from typing import Any, Dict, List, Optional

# from langchain_community.chat_models import ChatOllama
from langchain_community.chat_models import ChatOllama

from langflow.base.constants import STREAM_INFO_TEXT
from langflow.base.models.model import LCModelComponent
from langchain_core.caches import BaseCache
# from langchain.chat_models import ChatOllama
from langflow.field_typing import Text


import asyncio
import json

import httpx


# whe When a callback component is added to Langflow, the comment must be uncommented.
# from langchain.callbacks.manager import CallbackManager


class ChatOllamaComponent(LCModelComponent):
    display_name = "Ollama"
    description = "Generate text using Ollama Local LLMs."
    icon = "Ollama"
    

    
    field_order = [
        "base_url",
        "model",
        "temperature",
        "cache",
        "callbacks",
        "format",
        "metadata",
        "mirostat",
        "mirostat_eta",
        "mirostat_tau",
        "num_ctx",
        "num_gpu",
        "num_thread",
        "repeat_last_n",
        "repeat_penalty",
        "tfs_z",
        "timeout",
        "top_k",
        "top_p",
        "verbose",
        "tags",
        "stop",
        "system",
        "template",
        "input_value",
        "system_message",
        "stream",
    ]

    def build_config(self) -> dict:
        return {
            "base_url": {
                "display_name": "Base URL",
                "info": "Endpoint of the Ollama API. Defaults to 'http://localhost:11434' if not specified.",
                "advanced": True,
            },
            "cache": {
                "display_name": "Cache",
                "info": "If true, will use the global cache. If false, will not use a cache If None, will use the global cache if it’s set, otherwise no cache. If instance of BaseCache, will use the provided cache.",
                "advanced": True,
                "value": False,
            },
            "format": {
                "display_name": "Format",
                "info": "Specify the format of the output (e.g., json)",
            },
            "headers":{
                "display_name": "Headers",
                
                
            },
            "keep_alive":{
                "display_name": "Keep Alive",
                "info": "How long the model will stay loaded into memory.",             
                
            },
            
            
            "model": {
                "display_name": "Model Name",
                "options":[],
                "value": "llama2",
                "info": "Refer to https://ollama.ai/library for more models.",
                "real_time_refresh": True,
                "refresh_button": True,
            },
            "temperature": {
                "display_name": "Temperature",
                "field_type": "float",
                "value": 0.8,
                "info": "Controls the creativity of model responses.",
            },

            ### When a callback component is added to Langflow, the comment must be uncommented. ###
            # "callbacks": {
            #     "display_name": "Callbacks",
            #     "info": "Callbacks to execute during model runtime.",
            #     "advanced": True,
            # },
            ########################################################################################
            "format": {
                "display_name": "Format",
                "field_type": "str",
                "info": "Specify the format of the output (e.g., json).",
            },
            "metadata": {
                "display_name": "Metadata",
                "info": "Metadata to add to the run trace.",
                "advanced": True,
            },
            "mirostat": {
                "display_name": "Mirostat",
                "options": ["Disabled", "Mirostat", "Mirostat 2.0"],
                "info": "Enable/disable Mirostat sampling for controlling perplexity.",
                "value": "Disabled",
                "advanced": False,
                "real_time_refresh": True,

            },
            "mirostat_eta": {
                "display_name": "Mirostat Eta",
                "field_type": "float",
                "info": "Learning rate for Mirostat algorithm. (Default: 0.1)",
                "advanced": True,
            },
            "mirostat_tau": {
                "display_name": "Mirostat Tau",
                "field_type": "float",
                "info": "Controls the balance between coherence and diversity of the output. (Default: 5.0)",
                "advanced": True,
            },
            "num_ctx": {
                "display_name": "Context Window Size",
                "field_type": "int",
                "info": "Size of the context window for generating tokens. (Default: 2048)",
                "advanced": True,
            },
            "num_gpu": {
                "display_name": "Number of GPUs",
                "field_type": "int",
                "info": "Number of GPUs to use for computation. (Default: 1 on macOS, 0 to disable)",
                "advanced": True,
            },
            "num_thread": {
                "display_name": "Number of Threads",
                "field_type": "int",
                "info": "Number of threads to use during computation. (Default: detected for optimal performance)",
                "advanced": True,
            },
            "repeat_last_n": {
                "display_name": "Repeat Last N",
                "field_type": "int",
                "info": "How far back the model looks to prevent repetition. (Default: 64, 0 = disabled, -1 = num_ctx)",
                "advanced": True,
            },
            "repeat_penalty": {
                "display_name": "Repeat Penalty",
                "field_type": "float",
                "info": "Penalty for repetitions in generated text. (Default: 1.1)",
                "advanced": True,
            },
            "tfs_z": {
                "display_name": "TFS Z",
                "field_type": "float",
                "info": "Tail free sampling value. (Default: 1)",
                "advanced": True,
            },
            "timeout": {
                "display_name": "Timeout",
                "field_type": "int",
                "info": "Timeout for the request stream.",
                "advanced": True,
            },
            "top_k": {
                "display_name": "Top K",
                "field_type": "int",
                "info": "Limits token selection to top K. (Default: 40)",
                "advanced": True,
            },
            "top_p": {
                "display_name": "Top P",
                "field_type": "float",
                "info": "Works together with top-k. (Default: 0.9)",
                "advanced": True,
            },
            "verbose": {
                "display_name": "Verbose",
                "field_type": "bool",
                "info": "Whether to print out response text.",
            },
            "tags": {
                "display_name": "Tags",
                "field_type": "list",
                "info": "Tags to add to the run trace.",
                "advanced": True,
            },
            "stop": {
                "display_name": "Stop Tokens",
                "field_type": "list",
                "info": "List of tokens to signal the model to stop generating text.",
                "advanced": True,
            },
            "system": {
                "display_name": "System",
                "field_type": "str",
                "info": "System to use for generating text.",
                "advanced": True,
            },
            "template": {
                "display_name": "Template",
                "field_type": "str",
                "info": "Template to use for generating text.",
                "advanced": True,
            },
            "input_value": {"display_name": "Input"},
            "stream": {
                "display_name": "Stream",
                "info": STREAM_INFO_TEXT,
            },
            "system_message": {
                "display_name": "System Message",
                "info": "System message to pass to the model.",
                "advanced": True,
            },
        }
        
        
    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None):
        if field_name == "mirostat":
            if field_value == "Disabled":
                build_config["mirostat_eta"]["advanced"] = True
                build_config["mirostat_tau"]["advanced"] = True
            else:
                build_config["mirostat_eta"]["advanced"] = False
                build_config["mirostat_tau"]["advanced"] = False
                # Mirostat 2.0이 선택된 경우, 특정 기본값을 설정
                if field_value == "Mirostat 2.0":
                    build_config["mirostat_eta"]["value"] = 0.2
                    build_config["mirostat_tau"]["value"] = 10
                else:
                    build_config["mirostat_eta"]["value"] = 0.1
                    build_config["mirostat_tau"]["value"] = 5
        #if keep_alive ==              
        if field_name == "model":
            build_config["model"]["options"] = self.get_model()
                    
                    
                    
        return build_config        
    
    
    def get_model(url:str) -> List[str]:
        url = "http://localhost:11434/api/tags"
        try:
            with httpx.Client() as client:
                response = client.get(url)
                response.raise_for_status()  # 응답 코드가 200이 아니면 예외 발생
                data = response.json()
                model_names = [model['name'] for model in data.get("models", [])]
                return model_names
        except Exception as e:
            print(f"API 호출 중 오류 발생: {str(e)}")
            return ["ge"]  # API 호출 실패 시 빈 리스트 반환

    def build(
        self,
        base_url: Optional[str],
        model: str,
        input_value: Text,
        mirostat: Optional[str],
        mirostat_eta: Optional[float] = None,
        mirostat_tau: Optional[float] = None,
        ### When a callback component is added to Langflow, the comment must be uncommented.###
        # callbacks: Optional[List[Callbacks]] = None,
        #######################################################################################
        repeat_last_n: Optional[int] = None,
        verbose: Optional[bool] = None,
        cache: Union[BaseCache, bool, None] = None,
        keep_alive: Optional[Union[int, str]] = None,
        num_ctx: Optional[int] = None,
        num_gpu: Optional[int] = None,
        format: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        num_thread: Optional[int] = None,
        repeat_penalty: Optional[float] = None,
        stop: Optional[List[str]] = None,
        system: Optional[str] = None,
        tags: Optional[List[str]] = None,
        temperature: Optional[float] = None,
        template: Optional[str] = None,
        tfs_z: Optional[float] = None,
        timeout: Optional[int] = None,
        top_k: Optional[int] = None,
        top_p: Optional[int] = None,
        stream: bool = False,
        system_message: Optional[str] = None,
    ) -> Text:
        

            
            
        
        if not base_url:
            base_url = "http://localhost:11434"
            
        ModelUrl = base_url + "/api/tags"    


        model_record=self.get_model(url=ModelUrl)
        if not model_record:
            raise ValueError("Model not found.")

        # Mapping mirostat settings to their corresponding values
        mirostat_options = {"Mirostat": 1, "Mirostat 2.0": 2}

        # Default to 0 for 'Disabled'
        mirostat_value = mirostat_options.get(mirostat, 0)  # type: ignore

        # Set mirostat_eta and mirostat_tau to None if mirostat is disabled
        if mirostat_value == 0:
            mirostat_eta = None
            mirostat_tau = None

        # Mapping system settings to their corresponding values
        llm_params = {
            "base_url": base_url,
            "cache": cache,
            "model": model,
            "mirostat": mirostat_value,
            "format": format,
            "metadata": metadata,
            "tags": tags,
            ## When a callback component is added to Langflow, the comment must be uncommented.##
            # "callback_manager": callback_manager,
            # "callbacks": callbacks,
            #####################################################################################
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
        }

        # None Value remove
        llm_params = {k: v for k, v in llm_params.items() if v is not None}

        try:
            output = ChatOllama(**llm_params)  # type: ignore
        except Exception as e:
            raise ValueError("Could not initialize Ollama LLM.") from e

        return self.get_chat_result(output, stream, input_value, system_message)
