from typing import List, Optional

from langchain_google_vertexai import VertexAIEmbeddings

from langflow.custom import CustomComponent


class VertexAIEmbeddingsComponent(CustomComponent):
    display_name = "VertexAI Embeddings"
    description = "Generate embeddings using Google Cloud VertexAI models."

    def build_config(self):
        return {
            "credentials": {
                "display_name": "Credentials",
                "value": "",
                "file_types": [".json"],
                "field_type": "file",
            },
            "instance": {
                "display_name": "instance",
                "advanced": True,
                "field_type": "dict",
            },
            "location": {
                "display_name": "Location",
                "value": "us-central1",
                "advanced": True,
            },
            "max_output_tokens": {"display_name": "Max Output Tokens", "value": 128},
            "max_retries": {
                "display_name": "Max Retries",
                "value": 6,
                "advanced": True,
            },
            "model_name": {
                "display_name": "Model Name",
                "value": "textembedding-gecko",
            },
            "n": {"display_name": "N", "value": 1, "advanced": True},
            "project": {"display_name": "Project", "advanced": True},
            "request_parallelism": {
                "display_name": "Request Parallelism",
                "value": 5,
                "advanced": True,
            },
            "stop": {"display_name": "Stop", "advanced": True},
            "streaming": {
                "display_name": "Streaming",
                "value": False,
                "advanced": True,
            },
            "temperature": {"display_name": "Temperature", "value": 0.0},
            "top_k": {"display_name": "Top K", "value": 40, "advanced": True},
            "top_p": {"display_name": "Top P", "value": 0.95, "advanced": True},
        }

    def build(
        self,
        instance: Optional[str] = None,
        credentials: Optional[str] = None,
        location: str = "us-central1",
        max_output_tokens: int = 128,
        max_retries: int = 6,
        model_name: str = "textembedding-gecko",
        n: int = 1,
        project: Optional[str] = None,
        request_parallelism: int = 5,
        stop: Optional[List[str]] = None,
        streaming: bool = False,
        temperature: float = 0.0,
        top_k: int = 40,
        top_p: float = 0.95,
    ) -> VertexAIEmbeddings:
        return VertexAIEmbeddings(
            instance=instance,
            credentials=credentials,
            location=location,
            max_output_tokens=max_output_tokens,
            max_retries=max_retries,
            model_name=model_name,
            n=n,
            project=project,
            request_parallelism=request_parallelism,
            stop=stop,
            streaming=streaming,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
        )
