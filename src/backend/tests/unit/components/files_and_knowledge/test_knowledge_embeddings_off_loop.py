"""Knowledge-base embedding construction keeps the event loop free.

``get_embeddings`` is synchronous. It reads the user's credentials and enabled
providers from the database through ``run_until_complete``, which waits for a
second event loop in another thread. Called on the server's event loop, that
wait stops every other task on the loop, including tasks that hold database
connections the lookup itself needs. These tests run Knowledge ingestion and
retrieval and the KB API's embedding builder with the real ``get_embeddings``,
and record whether an event loop is running in the thread of each lookup.
"""

from __future__ import annotations

import asyncio
import threading

import pytest
from langchain_core.embeddings import Embeddings
from langflow.api.utils.kb_helpers import KBIngestionHelper
from langflow.services.deps import get_settings_service
from lfx.base.models import model_utils
from lfx.base.models.unified_models import credentials, instantiation, model_catalog
from lfx.components.files_and_knowledge import knowledge
from lfx.components.files_and_knowledge.knowledge import MODE_RETRIEVE, KnowledgeComponent
from lfx.components.models_and_agents import embedding_model
from lfx.schema.dataframe import DataFrame

BRIDGE_MODULES = (credentials, instantiation, model_catalog, model_utils)


class LocalEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return [[float(len(text)), 1.0, 0.5] for text in texts]

    def embed_query(self, text):
        return self.embed_documents([text])[0]


def _loop_running_in_this_thread() -> bool:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True


@pytest.fixture
def bridge_calls(monkeypatch) -> list[tuple[str, bool]]:
    """Record (module, loop running in the calling thread) for each ``run_until_complete`` call."""
    calls: list[tuple[str, bool]] = []
    for module in BRIDGE_MODULES:
        original = module.run_until_complete

        def spy(coro, _original=original, _name=module.__name__):
            calls.append((_name, _loop_running_in_this_thread()))
            return _original(coro)

        monkeypatch.setattr(module, "run_until_complete", spy)
    return calls


@pytest.fixture
def real_get_embeddings_with_local_vectors(monkeypatch) -> list[threading.Thread]:
    """Run the real ``get_embeddings`` (credential lookups included), then embed locally."""
    threads: list[threading.Thread] = []
    real_get_embeddings = knowledge.get_embeddings

    def get_embeddings(**kwargs):
        threads.append(threading.current_thread())
        real_get_embeddings(**kwargs)
        return LocalEmbeddings()

    monkeypatch.setattr(knowledge, "get_embeddings", get_embeddings)
    return threads


async def test_knowledge_ingest_and_retrieve_resolve_embeddings_off_the_event_loop(
    client,
    logged_in_headers,
    active_user,
    monkeypatch,
    tmp_path,
    bridge_calls,
    real_get_embeddings_with_local_vectors,
):
    monkeypatch.setattr(get_settings_service().settings, "knowledge_bases_dir", str(tmp_path))
    monkeypatch.delenv("PGVECTOR_CONNECTION_STRING", raising=False)
    # get_embeddings looks the key up in the user's variables first, then falls back to the environment.
    monkeypatch.setenv("OPENAI_API_KEY", "sk-local-test-key")
    name = "embeddings_off_loop"
    response = await client.post(
        "/api/v1/knowledge_bases",
        json={"name": name, "embedding_provider": "OpenAI", "embedding_model": "text-embedding-3-small"},
        headers=logged_in_headers,
    )
    assert response.status_code == 201, response.text

    ingest = KnowledgeComponent(
        knowledge_base=name,
        column_config=[{"column_name": "text", "vectorize": True, "identifier": False}],
        _user_id=active_user.id,
    )
    ingest.set(input_df=DataFrame({"text": ["cats purr", "dogs bark", "birds sing"]}))
    await ingest.build_kb_info()

    retrieve = KnowledgeComponent(
        knowledge_base=name, mode=MODE_RETRIEVE, search_query="cats", top_k=2, _user_id=active_user.id
    )
    assert len(await retrieve.retrieve_data()) == 2

    assert bridge_calls, "get_embeddings made no database lookups; the test no longer covers them"
    assert [module for module, loop_running in bridge_calls if loop_running] == []
    assert len(real_get_embeddings_with_local_vectors) == 2
    assert threading.current_thread() not in real_get_embeddings_with_local_vectors


@pytest.mark.usefixtures("client")
async def test_kb_api_builds_embeddings_off_the_event_loop(active_user, monkeypatch, bridge_calls):
    # get_embeddings looks the key up in the user's variables first, then falls back to the environment.
    monkeypatch.setenv("OPENAI_API_KEY", "sk-local-test-key")
    threads: list[threading.Thread] = []
    real_get_embeddings = embedding_model.get_embeddings

    def get_embeddings(**kwargs):
        threads.append(threading.current_thread())
        return real_get_embeddings(**kwargs)

    monkeypatch.setattr(embedding_model, "get_embeddings", get_embeddings)

    embeddings = await KBIngestionHelper.build_embeddings("OpenAI", "text-embedding-3-small", active_user)

    assert embeddings is not None
    assert bridge_calls, "get_embeddings made no database lookups; the test no longer covers them"
    assert [module for module, loop_running in bridge_calls if loop_running] == []
    assert len(threads) == 1
    assert threads[0] is not threading.current_thread()
