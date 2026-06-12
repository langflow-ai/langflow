"""Knowledge Base tool component.

Voice-friendly RAG-style lookup. The LLM sends a `query`; this component asks
a backend KB (AWS Bedrock Knowledge Bases by default — easy to swap for any
retrieval API) and returns the top-K passages so the LLM can synthesise an
answer.

This is intentionally tiny: KB integrations vary widely. Use this as the
canonical example, then copy-paste-modify for your own retrieval backend.
"""

import asyncio
from typing import Any

from lfx.base.pipecat.tool import PipecatToolComponent
from lfx.field_typing.voice_types import PipecatToolHandler
from lfx.io import DropdownInput, FloatInput, IntInput, MultilineInput, SecretStrInput, StrInput


class KnowledgeBaseToolComponent(PipecatToolComponent):
    display_name = "Knowledge Base Tool"
    description = "Voice tool that retrieves passages from a knowledge base for the LLM."
    icon = "BookOpen"
    name = "KnowledgeBaseTool"

    inputs = [
        StrInput(
            name="tool_name",
            display_name="Tool Name",
            required=True,
            value="knowledge_base_lookup",
        ),
        MultilineInput(
            name="tool_description",
            display_name="Description",
            required=True,
            value=(
                "Look up information from the company knowledge base. "
                "Call this when the user asks a factual question that requires "
                "consulting documentation."
            ),
        ),
        DropdownInput(
            name="backend",
            display_name="Backend",
            options=["aws_bedrock"],
            value="aws_bedrock",
            info="Retrieval backend. Today only AWS Bedrock Knowledge Bases is wired.",
        ),
        StrInput(
            name="kb_id",
            display_name="Knowledge Base ID",
            required=True,
            info="e.g. AWS Bedrock KB ID such as 'EMHQQ3JZUV'.",
        ),
        StrInput(
            name="region",
            display_name="AWS Region",
            value="us-east-1",
            advanced=True,
        ),
        SecretStrInput(
            name="aws_access_key_id",
            display_name="AWS Access Key ID",
            required=False,
            info="Optional — falls back to the default boto3 credential chain.",
            advanced=True,
        ),
        SecretStrInput(
            name="aws_secret_access_key",
            display_name="AWS Secret Access Key",
            required=False,
            advanced=True,
        ),
        IntInput(
            name="top_k",
            display_name="Top K",
            value=3,
            advanced=True,
        ),
        FloatInput(
            name="score_threshold",
            display_name="Score Threshold",
            value=0.5,
            advanced=True,
            info="Drop results below this similarity score.",
        ),
    ]

    def build_function_schema(self) -> Any:
        from pipecat.adapters.schemas.function_schema import FunctionSchema

        return FunctionSchema(
            name=self.tool_name,
            description=self.tool_description,
            properties={
                "query": {
                    "type": "string",
                    "description": "Natural-language question to look up.",
                }
            },
            required=["query"],
        )

    def build_handler(self) -> PipecatToolHandler:
        kb_id = self.kb_id
        region = self.region or "us-east-1"
        access_key = self.aws_access_key_id or None
        secret_key = self.aws_secret_access_key or None
        top_k = int(self.top_k)
        threshold = float(self.score_threshold)

        async def _handler(params: Any) -> None:  # pragma: no cover — runtime wiring
            try:
                import boto3
            except ImportError:
                await params.result_callback({"error": "boto3 not installed; pip install boto3"})
                return

            args = dict(getattr(params, "arguments", {}) or {})
            query = (args.get("query") or "").strip()
            if not query:
                await params.result_callback({"error": "empty query"})
                return

            try:
                client_kwargs: dict[str, Any] = {"region_name": region}
                if access_key and secret_key:
                    client_kwargs["aws_access_key_id"] = access_key
                    client_kwargs["aws_secret_access_key"] = secret_key
                client = boto3.client("bedrock-agent-runtime", **client_kwargs)

                def _retrieve() -> dict:
                    return client.retrieve(
                        knowledgeBaseId=kb_id,
                        retrievalQuery={"text": query},
                        retrievalConfiguration={
                            "vectorSearchConfiguration": {"numberOfResults": top_k}
                        },
                    )

                resp = await asyncio.to_thread(_retrieve)
                results = []
                for item in resp.get("retrievalResults", []):
                    score = float(item.get("score", 0.0))
                    if score < threshold:
                        continue
                    results.append({
                        "content": item.get("content", {}).get("text", ""),
                        "score": score,
                        "location": item.get("location"),
                    })
                await params.result_callback({"results": results, "query": query})
            except Exception as exc:  # noqa: BLE001 — all errors must be surfaced to the LLM via result_callback
                await params.result_callback({"error": f"{type(exc).__name__}: {exc}"})

        return _handler
