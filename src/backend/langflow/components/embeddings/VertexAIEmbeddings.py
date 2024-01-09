
from langflow import CustomComponent
from langchain.embeddings import VertexAIEmbeddings
from typing import Optional, List

class VertexAIEmbeddingsComponent(CustomComponent):
    display_name = "VertexAIEmbeddings"
    description = "Google Cloud VertexAI embedding models."

    def build_config(self):
        return {
            "client": {"display_name": "Client", "advanced": True},
            "credentials": {"display_name": "Credentials", "default": '', "file_types": ['json']},
            "location": {"display_name": "Location", "default": 'us-central1', "advanced": True},
            "max_output_tokens": {"display_name": "Max Output Tokens", "default": 128},
            "max_retries": {"display_name": "Max Retries", "default": 6, "advanced": True},
            "model_name": {"display_name": "Model Name", "default": 'textembedding-gecko'},
            "n": {"display_name": "N", "default": 1, "advanced": True},
            "project": {"display_name": "Project", "advanced": True},
            "request_parallelism": {"display_name": "Request Parallelism", "default": 5, "advanced": True},
            "stop": {"display_name": "Stop", "advanced": True},
            "streaming": {"display_name": "Streaming", "default": False, "advanced": True},
            "temperature": {"display_name": "Temperature", "default": 0.0},
            "top_k": {"display_name": "Top K", "default": 40, "advanced": True},
            "top_p": {"display_name": "Top P", "default": 0.95, "advanced": True},
        }

    def build(
        self,
        client: Optional[str] = None,
        credentials: Optional[str] = None,
        location: str = 'us-central1',
        max_output_tokens: int = 128,
        max_retries: int = 6,
        model_name: str = 'textembedding-gecko',
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
            client=client,
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
