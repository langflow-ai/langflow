from __future__ import annotations

import base64
import io
import time
from typing import TYPE_CHECKING

import requests
from langchain_core.embeddings import Embeddings as LCEmbeddings

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage


class VllmMultivectorEmbeddings(LCEmbeddings):
    """Multi-vector embeddings via vLLM's /pooling endpoint.

    Works with any multi-vector model served by vLLM including:
      Text ColBERT  : answerdotai/answerai-colbert-small-v1
                      lightonai/ColBERT-Zero
      Multi-modal   : ModernVBERT/colmodernvbert
                      vidore/colqwen2-v1.0

    vLLM must be started with --runner pooling and the correct pooler config:
        vllm serve <model> --runner pooling

    For token-level (multi-vector) output, also pass:
        --pooler-config '{"task": "token_embed"}'

    Note: the `task` field in the HTTP request body is deprecated in vLLM >= 0.20.
    Set it at server startup instead.

    Shape contract (required by NextPlaid):
        embed_documents(texts) -> List[List[List[float]]]  (n_docs, n_tokens, dim)
        embed_query(text)      -> List[List[float]]         (n_tokens, dim)
        embed_images(images)   -> List[List[List[float]]]  (n_imgs, n_patches, dim)
            — only available for multi-modal ColPali models
    """

    def __init__(
        self,
        url: str,
        model: str,
        api_key: str = "",
        timeout: float = 60.0,
        max_retries: int = 1,
    ) -> None:
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
        return f"VllmMultivectorEmbeddings(url={self.url!r}, model={self.model!r})"

    def __hash__(self) -> int:
        return hash((self.url, self.model, self.api_key))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, type(self)):
            return False
        return (self.url, self.model, self.api_key) == (other.url, other.model, other.api_key)

    @staticmethod
    def _extract_embedding_rows(payload: object) -> list[dict]:
        """Validate the vLLM /pooling envelope before nested indexing.

        Raises a clear ``RuntimeError`` instead of letting a malformed or
        partial response crash with ``KeyError``/``IndexError`` downstream.
        """
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list) or not data:
            msg = "vLLM /pooling response missing non-empty 'data' list"
            raise RuntimeError(msg)
        return data

    def _post_pooling(self, input_data: list) -> list[list[list[float]]]:
        last_exc: Exception | None = None
        for attempt in range(max(self.max_retries, 1)):
            try:
                resp = requests.post(
                    f"{self.url}/pooling",
                    json={"model": self.model, "input": input_data},
                    headers=self._headers,
                    timeout=self.timeout,
                )
                resp.raise_for_status()
                rows = self._extract_embedding_rows(resp.json())
                try:
                    results = sorted(rows, key=lambda x: x["index"])
                    return [item["data"] for item in results]
                except (KeyError, TypeError) as exc:
                    msg = "vLLM /pooling response has invalid embedding row shape"
                    raise RuntimeError(msg) from exc
            except requests.HTTPError as exc:
                valid_client_status_codes = 500
                if exc.response is not None and exc.response.status_code < valid_client_status_codes:
                    raise  # don't retry 4xx — surface immediately
                last_exc = exc
                if attempt < self.max_retries - 1:
                    time.sleep(2**attempt)
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < self.max_retries - 1:
                    time.sleep(2**attempt)
        raise last_exc  # type: ignore[misc]

    @staticmethod
    def _pil_to_content_item(img: PILImage) -> dict:
        """Convert a PIL Image to an OpenAI Vision API content item.

        This is the format vLLM expects for multi-modal pooling input.
        """
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG")
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        return {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        }

    def embed_documents(self, texts: list[str]) -> list[list[list[float]]]:  # type: ignore[override]
        """Encode text documents. Returns one token matrix per document."""
        if not texts:
            return []
        return self._post_pooling(texts)

    def embed_query(self, text: str) -> list[list[float]]:  # type: ignore[override]
        """Encode a single query string. Returns one token matrix."""
        return self._post_pooling([text])[0]

    def embed_images(self, images: list[PILImage]) -> list[list[list[float]]]:
        if not images:
            return []

        embeddings: list[list[list[float]]] = []
        for img in images:
            last_exc: Exception | None = None
            for attempt in range(max(self.max_retries, 1)):
                try:
                    resp = requests.post(
                        f"{self.url}/pooling",
                        json={
                            "model": self.model,
                            "messages": [
                                {
                                    "role": "user",
                                    "content": [self._pil_to_content_item(img)],
                                }
                            ],
                        },
                        headers=self._headers,
                        timeout=self.timeout,
                    )
                    resp.raise_for_status()
                    rows = self._extract_embedding_rows(resp.json())
                    try:
                        embeddings.append(rows[0]["data"])
                    except (KeyError, TypeError, IndexError) as exc:
                        msg = "vLLM /pooling image response has invalid embedding row shape"
                        raise RuntimeError(msg) from exc
                    break
                except requests.HTTPError as exc:
                    valid_client_status_codes = 500
                    if exc.response is not None and exc.response.status_code < valid_client_status_codes:
                        msg = f"vLLM {exc.response.status_code}: {exc.response.text}"
                        raise RuntimeError(msg) from exc
                    last_exc = exc
                    if attempt < self.max_retries - 1:
                        time.sleep(2**attempt)
                except requests.RequestException as exc:
                    last_exc = exc
                    if attempt < self.max_retries - 1:
                        time.sleep(2**attempt)
            else:
                raise last_exc  # type: ignore[misc]

        return embeddings
