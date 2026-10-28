"""Cloudflare Workers AI embeddings with the async contract of the retired Community class.

The subclass lives in an importable module rather than inside the component, so built
embeddings pickle by reference; the Redis cache serializes vertex results.
"""

from langchain_cloudflare import CloudflareWorkersAIEmbeddings
from langchain_core.runnables.config import run_in_executor
from lfx.base.models.provider_ssrf import provider_safe_httpx_post


class CompatibleCloudflareEmbeddings(CloudflareWorkersAIEmbeddings):
    """Run async calls on the executor, as the Community class inherited from ``Embeddings``.

    The provider's async methods use an unconfigured ``httpx.AsyncClient``, whose default
    five-second timeout fails slow but successful requests made by knowledge-base calls.
    """

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if self.strip_new_lines:
            texts = [text.replace("\n", " ") for text in texts]
        embeddings = []
        for start in range(0, len(texts), self.batch_size):
            response = provider_safe_httpx_post(
                self._inference_url,
                headers=self.headers,
                json={"text": texts[start : start + self.batch_size]},
                timeout=None,
            )
            response.raise_for_status()
            embeddings.extend(response.json()["result"]["data"])
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

    async def aembed_query(self, text: str) -> list[float]:
        return await run_in_executor(None, self.embed_query, text)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return await run_in_executor(None, self.embed_documents, texts)
