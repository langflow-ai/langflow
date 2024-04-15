from typing import Optional

from langchain.embeddings.base import Embeddings
from langchain_community.embeddings import OllamaEmbeddings

from langflow.interface.custom.custom_component import CustomComponent
import asyncio
import json

import httpx

class OllamaEmbeddingsComponent(CustomComponent):
    display_name: str = "Ollama Embeddings"
    description: str = "Generate embeddings using Ollama models."
    documentation = "https://python.langchain.com/docs/integrations/text_embedding/ollama"
    
    field_order = [
        "base_url",      
        "embed_instruction",
        "headers",
        "model",
        "model_kwargs",
        "num_ctx",
        "num_gpu",
        "num_thread",
        "query_instruction",
        "repeat_last_n",
        "repeat_penalty",
        "show_progress",
        "stop",
        "temperature",
        "tfs_z",
        "top_k",
        "top_p",
    ]


    def build_config(self):
        return {
            "base_url": {
                "display_name": "Base URL",
                "info": "The base URL of the API.",
                "default": "http://localhost:11434"
            },
            "embed_instruction": {
                "display_name": "Embedding Instruction",
                "info": "The prefix instruction for embedding generation.",
                "default": "passage: "
            },
            "headers": {
                "display_name": "HTTP Headers",
                "info": "Optional dictionary of HTTP headers to send with the request.",
                "advanced": True
            },
            "mirostat": {
                "display_name": "Mirostat Value",
                "info": "Optional integer value for mirostat adjustments.",
                "advanced": True
            },
            "mirostat_eta": {
                "display_name": "Mirostat Eta",
                "info": "Optional floating-point for mirostat eta adjustments.",
                "advanced": True
            },
            "mirostat_tau": {
                "display_name": "Mirostat Tau",
                "info": "Optional floating-point for mirostat tau adjustments.",
                "advanced": True
            },
            "model": {
                "display_name": "Model",
                "info": "The model used for embedding generation, e.g., 'llama2'.",
                "real_time_refresh": True,
                "refresh_button": True,
            },
            "model_kwargs": {
                "display_name": "Model Keyword Arguments",
                "info": "Optional dictionary for additional model-specific parameters.",
                "advanced": True
            },
            "num_ctx": {
                "display_name": "Context Number",
                "info": "Optional number of contexts to use.",
                "advanced": True
            },
            "num_gpu": {
                "display_name": "Number of GPUs",
                "info": "Optional number of GPUs to utilize.",
                "advanced": True
            },
            "num_thread": {
                "display_name": "Number of Threads",
                "info": "Optional number of threads to utilize.",
                "advanced": True
            },
            "query_instruction": {
                "display_name": "Query Instruction",
                "info": "The prefix instruction for query generation.",
                "default": "query: "
            },
            "repeat_last_n": {
                "display_name": "Repeat Last N",
                "info": "Optional parameter to repeat the last N operations.",
                "advanced": True
            },
            "repeat_penalty": {
                "display_name": "Repeat Penalty",
                "info": "Optional floating-point to penalize repeating operations.",
                "advanced": True
            },
            "show_progress": {
                "display_name": "Show Progress",
                "info": "Whether to show progress during operations.",
                "default": False
            },
            "stop": {
                "display_name": "Stop Tokens",
                "info": "Optional list of stop tokens.",
                "advanced": True
            },
            "temperature": {
                "display_name": "Temperature",
                "info": "Optional floating-point to adjust the randomness of responses.",

            },
            "tfs_z": {
                "display_name": "TFS Z",
                "info": "Optional floating-point for TFS adjustments.",
                "advanced": True
            },
            "top_k": {
                "display_name": "Top K",
                "info": "Optional integer to limit the number of top probabilities.",
                "advanced": True
            },
            "top_p": {
                "display_name": "Top P",
                "info": "Optional floating-point to use top-p probability filtering.",
                "advanced": True
            }
            
            
            
            
        }
        
    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None):

                    
        if field_name == "model":
            # base_url 값 사용
            base_url = build_config.get("base_url", {}).get("value", "http://localhost:11434")
            build_config["model"]["options"] = self.get_model(base_url + "/api/tags")
            
                        
                    
        return build_config       
        
        
            
    def get_model(self, url: str) -> List[str]:
        try:
            with httpx.Client() as client:
                response = client.get(url)
                response.raise_for_status()  # 응답 코드가 200이 아니면 예외 발생
                data = response.json()
                # ":latest" 문자열을 제거하고 모델 이름 목록을 생성
                model_names = [model['name'] for model in data.get("models", [])]
                return model_names
        except Exception as e:
            raise ValueError("Could not retrieve models") from e
            return [""]  # API 호출 실패 시 빈 리스트 반환
        
        
    def build(self, 
              base_url: str = 'http://localhost:11434',
              embed_instruction: str = 'passage: ',
              headers: Optional[dict] = None,
              mirostat: Optional[int] = None,
              mirostat_eta: Optional[float] = None,
              mirostat_tau: Optional[float] = None,
              model: str = 'llama2',
              model_kwargs: Optional[dict] = None,
              num_ctx: Optional[int] = None,
              num_gpu: Optional[int] = None,
              num_thread: Optional[int] = None,
              query_instruction: str = 'query: ',
              repeat_last_n: Optional[int] = None,
              repeat_penalty: Optional[float] = None,
              show_progress: bool = False,
              stop: Optional[List[str]] = None,
              temperature: Optional[float] = None,
              tfs_z: Optional[float] = None,
              top_k: Optional[int] = None,
              top_p: Optional[float] = None
              ) -> Embeddings:
        
        try:
            output = OllamaEmbeddings(model=model, base_url=base_url, temperature=temperature)  # type: ignore
        except Exception as e:
            raise ValueError("Could not connect to Ollama API.") from e
        return output
