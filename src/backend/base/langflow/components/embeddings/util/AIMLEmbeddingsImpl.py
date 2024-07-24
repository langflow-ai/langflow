import json
from typing import List

import httpx
from langflow.field_typing import Embeddings
from langchain_core.pydantic_v1 import BaseModel, SecretStr
from loguru import logger


class AIMLEmbeddingsImpl(BaseModel, Embeddings):
    embeddings_completion_url: str = "https://api.aimlapi.com/v1/embeddings"

    api_key: SecretStr
    model: str

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        embeddings = []
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key.get_secret_value()}",
        }

        import time
        start = time.time()

        with httpx.Client() as client:
            for text in texts:
                print(f"Text: {text}")
                # This is inefficient - we should be batching up to the maximum length
                # allowed by the model. However, that requires maintaining a mapping of the
                # model and input length.
                #
                # Another option would be, when available, utilize the langchain impl of
                # for the specific embedding models, which generally handle batching and retries.
                payload = {
                    "model": self.model,
                    "input": text,
                }

                try:
                    start_req = time.time()
                    response = client.post(
                        self.embeddings_completion_url,
                        headers=headers,
                        json=payload,
                    )
                    print(f"Time taken for request: {time.time() - start_req}")
                    response.raise_for_status()
                    result_data = response.json()
                    print(f"Result data: {result_data}")
                    assert len(result_data["data"]) == 1, "Expected one embedding"
                    # embeddings.append([item["embedding"] for item in result_data["data"]])
                    embeddings.append(result_data["data"][0]["embedding"])
                except (
                    httpx.HTTPStatusError,
                    httpx.RequestError,
                    json.JSONDecodeError,
                    KeyError,
                ) as e:
                    logger.error(f"Error occurred: {e}")
                    raise

        end = time.time()
        print(f"Time taken: {end - start}")
        return embeddings

    def embed_query(self, text: str) -> List[float]:
        return self.embed_documents([text])[0]
