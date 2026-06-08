# colbert_embeddings_impl.py
# Not a Langflow component — imported by vllm_colbert_embeddings_component.py
from __future__ import annotations

import time

import requests
from langchain_core.embeddings import Embeddings as LCEmbeddings


class VllmColBERTEmbeddings(LCEmbeddings):
    """Multi-vector (ColBERT-style) embeddings via vLLM's /pooling endpoint.

    embed_documents -> List[List[List[float]]]  (n_docs, n_tokens, dim)
    embed_query     -> List[List[float]]         (n_tokens, dim)
    """

    def __init__(self, url: str, model: str, api_key: str = "", timeout: float = 60.0, max_retries: int = 1):
        self.url = url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self._headers: dict = {
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {api_key}"} if api_key else {}),
        }

    def __repr__(self) -> str:
        return f"VllmColBERTEmbeddings(url={self.url!r}, model={self.model!r})"

    def __hash__(self) -> int:
        return hash((self.url, self.model, self.api_key))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, type(self)):
            return False
        return (self.url, self.model, self.api_key) == (other.url, other.model, other.api_key)

    def _call_token_embed_once(
        self,
        texts: list[str],
    ) -> list[list[list[float]]]:
        payload = {
            "model": self.model,
            "input": texts,
            "task": "token_embed",
        }

        resp = requests.post(
            f"{self.url}/pooling",
            json=payload,
            headers=self._headers,
            timeout=self.timeout,
        )

        resp.raise_for_status()

        response_data = resp.json()
        results = sorted(response_data["data"], key=lambda x: x["index"])
        return [item["data"] for item in results]

    def _call_token_embed(
        self,
        texts: list[str],
    ) -> list[list[list[float]]]:
        last_exc: requests.RequestException | None = None

        for attempt in range(self.max_retries):
            try:
                return self._call_token_embed_once(texts)

            except requests.RequestException as exc:
                last_exc = exc

                if attempt < self.max_retries - 1:
                    time.sleep(2**attempt)

        if last_exc is None:
            msg = "Retry loop exited without an exception"
            raise RuntimeError(msg)

        raise last_exc

    def embed_documents(self, texts: list[str]) -> list[list[list[float]]]:  # type: ignore[override]
        if not texts:
            return []
        return self._call_token_embed(texts)

    def embed_query(self, text: str) -> list[list[float]]:  # type: ignore[override]
        return self._call_token_embed([text])[0]
