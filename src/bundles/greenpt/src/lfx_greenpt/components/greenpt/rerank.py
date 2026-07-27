"""GreenPT document reranking component."""

from collections.abc import Sequence
from typing import Any

import httpx
from langchain_core.callbacks import Callbacks
from langchain_core.documents import Document
from lfx.base.compressors.model import LCCompressorComponent
from lfx.field_typing import BaseDocumentCompressor
from lfx.inputs.inputs import SecretStrInput
from lfx.io import DropdownInput
from lfx.template.field.base import Output
from pydantic import SecretStr

RERANK_URL = "https://api.greenpt.ai/v1/rerank"


def _secret_value(value: str | SecretStr) -> str:
    return value.get_secret_value() if isinstance(value, SecretStr) else value


class GreenPTReranker(BaseDocumentCompressor):
    """LangChain document compressor backed by GreenPT's rerank endpoint."""

    api_key: SecretStr
    model: str = "green-rerank"
    top_n: int = 3

    def compress_documents(
        self,
        documents: Sequence[Document],
        query: str,
        callbacks: Callbacks = None,
    ) -> Sequence[Document]:
        del callbacks
        source_documents = list(documents)
        response = httpx.post(
            RERANK_URL,
            headers={"Authorization": f"Bearer {self.api_key.get_secret_value()}"},
            json={
                "model": self.model,
                "query": query,
                "documents": [document.page_content for document in source_documents],
                "top_n": self.top_n,
            },
            timeout=30,
        )
        response.raise_for_status()
        payload: Any = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            msg = "GreenPT returned an invalid rerank response."
            raise TypeError(msg)

        reranked: list[Document] = []
        for result in payload["results"]:
            if (
                not isinstance(result, dict)
                or isinstance(result.get("index"), bool)
                or not isinstance(result.get("index"), int)
            ):
                msg = "GreenPT returned an invalid rerank result."
                raise TypeError(msg)
            index = result["index"]
            if index < 0 or index >= len(source_documents):
                msg = "GreenPT returned a rerank result with an invalid document index."
                raise ValueError(msg)
            score = result.get("relevance_score", result.get("score"))
            if isinstance(score, bool) or not isinstance(score, int | float):
                msg = "GreenPT returned a rerank result without a relevance score."
                raise TypeError(msg)
            source = source_documents[index]
            reranked.append(
                Document(
                    page_content=source.page_content,
                    metadata={**source.metadata, "relevance_score": float(score)},
                )
            )
        return reranked


class GreenPTRerankComponent(LCCompressorComponent):
    display_name = "GreenPT Rerank"
    description = "Rerank documents with GreenPT's renewable-powered optimized AI infrastructure."
    name = "GreenPTRerank"
    icon = "GreenPT"

    inputs = [
        *LCCompressorComponent.inputs,
        SecretStrInput(
            name="api_key",
            display_name="GreenPT API Key",
            value="GREENPT_API_KEY",
            required=True,
        ),
        DropdownInput(
            name="model",
            display_name="Model",
            options=["green-rerank"],
            value="green-rerank",
        ),
    ]

    outputs = [
        Output(
            display_name="Reranked Documents",
            name="reranked_documents",
            method="compress_documents",
        )
    ]

    def build_compressor(self) -> BaseDocumentCompressor:
        return GreenPTReranker(
            api_key=SecretStr(_secret_value(self.api_key)),
            model=self.model,
            top_n=self.top_n,
        )
