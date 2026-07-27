"""Provider-boundary stubs (LLM / embeddings) and outbound variable provisioning.

Stubs ``get_llm`` / ``get_embeddings`` so outbound, KB, and ensemble fixtures
can run without network credentials or model downloads. Also inserts the
mock OpenAI API-key variable when a fixture expects ``load_from_db``. Used by
``test_subsystem_coverage``.
"""

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

    from tests.locust.langflow_runtime.components.perf_deterministic_embeddings import DeterministicEmbeddings

    embeddings = DeterministicEmbeddings(size)
    with patch("lfx.base.models.unified_models.get_embeddings", return_value=embeddings):
        yield embeddings
