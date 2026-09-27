"""Cloudflare Workers AI embeddings with the async contract of the retired Community class.

The subclass lives in an importable module rather than inside the component, so built
embeddings pickle by reference; the Redis cache serializes vertex results.
"""

from langchain_cloudflare import CloudflareWorkersAIEmbeddings
from langchain_core.runnables.config import run_in_executor


class CompatibleCloudflareEmbeddings(CloudflareWorkersAIEmbeddings):
    """Run async calls on the executor, as the Community class inherited from ``Embeddings``.

    The provider's async methods use an unconfigured ``httpx.AsyncClient``, whose default
    five-second timeout fails slow but successful requests made by knowledge-base calls.
    """

    async def aembed_query(self, text: str) -> list[float]:
        return await run_in_executor(None, self.embed_query, text)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return await run_in_executor(None, self.embed_documents, texts)
