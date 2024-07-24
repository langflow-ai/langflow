import json
from typing import List

import httpx
from langflow.field_typing import Embeddings
from langchain_core.runnables.config import run_in_executor
from langchain_core.pydantic_v1 import BaseModel, SecretStr
from loguru import logger


class AIMLEmbeddingsImpl(BaseModel, Embeddings):
    embeddings_completion_url: str = "https://api.aimlapi.com/v1/embeddings"

    api_key: SecretStr
    model: str

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        result_vectors = []
        for text in texts:
            vector = self.embed_query(text)
            result_vectors.append(vector)

        return result_vectors

    def embed_query(self, text: str) -> List[float]:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key.get_secret_value()}",
        }

        payload = {
            "model": self.model,
            "input": text,
        }
        vector = []
        try:
            response = httpx.post(
                self.embeddings_completion_url,
                headers=headers,
                json=payload,
            )
            try:
                response.raise_for_status()
                result_data = response.json()
                vector = result_data["data"][0]["embedding"]
            except httpx.HTTPStatusError as http_err:
                logger.error(f"HTTP error occurred: {http_err}")
                raise http_err
            except httpx.RequestError as req_err:
                logger.error(f"Request error occurred: {req_err}")
                raise req_err
            except json.JSONDecodeError:
                logger.warning(f"Failed to decode JSON, response text: {response.text}")
            except KeyError as key_err:
                logger.warning(f"Key error: {key_err}, response content: {result_data}")
                raise key_err
        except httpx.TimeoutException:
            logger.error("Request timed out.")
            raise
        except Exception as exc:
            logger.error(f"Error: {exc}")
            raise

        return vector

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        return await run_in_executor(None, self.embed_documents, texts)

    async def aembed_query(self, text: str) -> List[float]:
        return await run_in_executor(None, self.embed_query, text)
