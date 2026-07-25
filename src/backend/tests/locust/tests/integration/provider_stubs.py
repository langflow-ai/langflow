"""Provider-boundary stubs (LLM / embeddings) and outbound variable provisioning."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

# Non-secret sentinel (avoid ``sk-`` so scanners do not flag it).
PERF_MOCK_OPENAI_API_KEY = "perf-suite-mock-openai-key-not-used"  # pragma: allowlist secret

if TYPE_CHECKING:
    from collections.abc import Iterator


async def provision_openai_api_key_variable(
    *,
    user_id: Any,
    value: str = PERF_MOCK_OPENAI_API_KEY,
) -> None:
    """Create the OPENAI_API_KEY global variable for a user (live variable store).

    Needed so fixture ``api_key`` fields with ``load_from_db=True`` resolve like a
    provisioned environment. Pair with ``mock_language_model_responses`` so the
    value is never sent to a real provider.
    """
    from lfx.services.deps import get_variable_service, session_scope

    from tests.locust.langflow_runtime.flows.defaults import DEFAULT_OUTBOUND_API_KEY_VAR

    variable_service = get_variable_service()
    async with session_scope() as session:
        try:
            await variable_service.get_variable_object(user_id, DEFAULT_OUTBOUND_API_KEY_VAR, session)
        except ValueError:
            await variable_service.create_variable(
                user_id,
                DEFAULT_OUTBOUND_API_KEY_VAR,
                value,
                session=session,
            )


@contextmanager
def mock_language_model_responses(*responses: str) -> Iterator[Any]:
    """Patch only provider model construction with a LangChain-compatible chat model.

    Patches ``lfx.base.models.unified_models.get_llm`` (the shared factory) so both
    installed and fixture-embedded ``LanguageModelComponent`` source see the fake.
    """
    from unittest.mock import patch

    from langchain_core.language_models.fake_chat_models import FakeListChatModel

    texts = list(responses) if responses else ["perf-outbound-ok"]
    llm = FakeListChatModel(responses=texts)
    with patch("lfx.base.models.unified_models.get_llm", return_value=llm):
        yield llm


@contextmanager
def mock_embedding_model(*, size: int = 8) -> Iterator[Any]:
    """Patch only embedding-model construction; KB ingest/retrieve components stay live.

    Uses a deterministic stub (not LangChain ``FakeEmbeddings``, which is
    non-deterministic and can flake retrieval).
    """
    from unittest.mock import patch

    class _DeterministicEmbeddings:
        def __init__(self, dimension: int) -> None:
            self.dimension = dimension

        def _embed(self, text: str) -> list[float]:
            digest = abs(hash(text))
            return [((digest >> (i * 4)) & 0xF) / 15.0 for i in range(self.dimension)]

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [self._embed(t) for t in texts]

        def embed_query(self, text: str) -> list[float]:
            return self._embed(text)

    embeddings = _DeterministicEmbeddings(size)
    with patch("lfx.base.models.unified_models.get_embeddings", return_value=embeddings):
        yield embeddings
