"""Knowledge-base backends and the storage lease run on the caller's event loop.

The pgvector backend keeps one connection pool per event loop, and the remote
storage lease keeps one coordination engine per loop. If the Knowledge component
or the KB API reached either through ``run_until_complete`` (or any other new
event loop), each call would build its own pool. These tests run ingestion,
retrieval and the KB API and record the loop and thread of every backend call
and lease.

The ``postgres`` case runs against a live pgvector database when
``LANGFLOW_RUN_PGVECTOR_INTEGRATION_TESTS=1`` and ``PGVECTOR_CONNECTION_STRING``
are set and the pgvector extra is installed; it skips otherwise.
"""

from __future__ import annotations

import asyncio
import asyncio.events
import asyncio.runners
import functools
import inspect
import io
import os
import threading
import time
import types
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

import pytest
from langchain_core.embeddings import Embeddings
from langflow.api.utils.kb_helpers import KBIngestionHelper
from langflow.services.deps import get_settings_service
from langflow.services.knowledge_base_storage import runtime
from lfx.base.knowledge_bases.backends.registry import get_backend_class
from lfx.base.tools.component_tool import ComponentToolkit
from lfx.components.files_and_knowledge.knowledge import MODE_RETRIEVE, KnowledgeComponent
from lfx.schema.dataframe import DataFrame
from lfx.utils import async_helpers

TERMINAL_RUN_STATES = {"succeeded", "failed", "cancelled"}
LEASE_FUNCTIONS = ("operation", "exclusive_lock", "shared_lock", "_remote_lock", "_file_operation_lock")


class LocalEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return [[float(len(text)), 1.0, 0.5] for text in texts]

    def embed_query(self, text):
        return self.embed_documents([text])[0]


@contextmanager
def no_second_event_loop():
    """Record and refuse every attempt to start another event loop."""
    calls: list[str] = []

    def refuse(name):
        def _refuse(*args, **_kwargs):
            calls.append(name)
            for arg in args:
                if inspect.iscoroutine(arg):
                    arg.close()
            msg = f"{name} was called"
            raise AssertionError(msg)

        return _refuse

    with ExitStack() as stack:
        for target, attribute in (
            (async_helpers, "run_until_complete"),
            (asyncio, "run"),
            (asyncio.runners, "run"),
            (asyncio, "new_event_loop"),
            (asyncio.events, "new_event_loop"),
        ):
            stack.enter_context(patch.object(target, attribute, refuse(f"{target.__name__}.{attribute}")))
        yield calls


def _recorded(function, name: str, seen: list):
    def note() -> None:
        seen.append((name, asyncio.get_running_loop(), threading.current_thread()))

    if inspect.isasyncgenfunction(function):

        @functools.wraps(function)
        async def iterate(*args, **kwargs):
            note()
            async for item in function(*args, **kwargs):
                yield item

        return iterate
    if inspect.iscoroutinefunction(function):

        @functools.wraps(function)
        async def call(*args, **kwargs):
            note()
            return await function(*args, **kwargs)

        return call

    @functools.wraps(function)  # an asynccontextmanager factory: called on the loop that enters it
    def enter(*args, **kwargs):
        note()
        return function(*args, **kwargs)

    return enter


@pytest.fixture
def kb_loops(monkeypatch) -> list:
    """Record (name, loop, thread) for every backend coroutine and storage lease."""
    seen: list = []
    for backend_type in ("sqlite", "postgres"):
        backend_class = get_backend_class(backend_type)
        wrapped: set[str] = set()
        for klass in backend_class.__mro__:
            for name, value in vars(klass).items():
                if name.startswith("__") or name in wrapped or not isinstance(value, types.FunctionType):
                    continue
                if inspect.iscoroutinefunction(value) or inspect.isasyncgenfunction(value):
                    wrapped.add(name)
                    monkeypatch.setattr(backend_class, name, _recorded(value, f"{klass.__name__}.{name}", seen))
    for name in LEASE_FUNCTIONS:
        monkeypatch.setattr(runtime, name, _recorded(getattr(runtime, name), f"runtime.{name}", seen))
    return seen


def _require_backend(backend_type: str) -> None:
    if backend_type != "postgres":
        return
    if os.getenv("LANGFLOW_RUN_PGVECTOR_INTEGRATION_TESTS") != "1" or not os.getenv("PGVECTOR_CONNECTION_STRING"):
        pytest.skip("Set LANGFLOW_RUN_PGVECTOR_INTEGRATION_TESTS=1 and PGVECTOR_CONNECTION_STRING for pgvector")
    pytest.importorskip("psycopg")
    pytest.importorskip("pgvector")


async def _dispose_this_loops_engines() -> None:
    from lfx.base.knowledge_bases.backends import postgres

    for engine in postgres._ENGINES.pop(asyncio.get_running_loop(), {}).values():
        await engine.dispose()


async def _wait_for_runs(client, endpoint: str, headers: dict, count: int) -> list[dict]:
    deadline = time.monotonic() + 60
    while True:
        response = await client.get(f"{endpoint}/runs", headers=headers)
        assert response.status_code == 200, response.text
        runs = response.json()["runs"]
        if len(runs) >= count and all(run["status"] in TERMINAL_RUN_STATES for run in runs):
            return runs
        assert time.monotonic() < deadline, f"ingestion runs did not finish: {runs}"
        await asyncio.sleep(0.1)


@pytest.mark.parametrize("backend_type", ["sqlite", "postgres"])
async def test_knowledge_and_kb_api_use_backends_on_the_callers_loop(
    client, logged_in_headers, active_user, monkeypatch, tmp_path, kb_loops, backend_type
):
    _require_backend(backend_type)
    monkeypatch.setattr(get_settings_service().settings, "knowledge_bases_dir", str(tmp_path))
    if backend_type == "sqlite":
        monkeypatch.delenv("PGVECTOR_CONNECTION_STRING", raising=False)
    monkeypatch.setattr(
        "lfx.components.files_and_knowledge.knowledge.get_embeddings", lambda **_kwargs: LocalEmbeddings()
    )

    async def local_embeddings(*_args, **_kwargs):
        return LocalEmbeddings()

    monkeypatch.setattr(KBIngestionHelper, "build_embeddings", staticmethod(local_embeddings))
    name = f"loop_check_{backend_type}"
    endpoint = f"/api/v1/knowledge_bases/{name}"
    texts = ["cats purr", "dogs bark", "birds sing"]

    try:
        response = await client.post(
            "/api/v1/knowledge_bases",
            json={"name": name, "embedding_provider": "OpenAI", "embedding_model": "text-embedding-3-small"},
            headers=logged_in_headers,
        )
        assert response.status_code == 201, response.text
        assert response.json()["backend_type"] == backend_type

        ingest = KnowledgeComponent(
            knowledge_base=name,
            column_config=[{"column_name": "text", "vectorize": True, "identifier": False}],
            _user_id=active_user.id,
        )
        ingest.set(input_df=DataFrame({"text": texts}))
        await ingest.build_kb_info()

        retrieve = KnowledgeComponent(
            knowledge_base=name, mode=MODE_RETRIEVE, search_query="cats", top_k=2, _user_id=active_user.id
        )
        assert len(await retrieve.retrieve_data()) == 2

        response = await client.post(
            f"{endpoint}/ingest",
            headers=logged_in_headers,
            files={"files": ("notes.txt", io.BytesIO(b"fish swim"), "text/plain")},
        )
        assert response.status_code == 200, response.text
        runs = await _wait_for_runs(client, endpoint, logged_in_headers, count=2)
        assert {run["status"] for run in runs} == {"succeeded"}

        response = await client.get(f"{endpoint}/chunks", headers=logged_in_headers)
        assert response.status_code == 200, response.text
        assert response.json()["total"] == len(texts) + 1
        response = await client.get(endpoint, headers=logged_in_headers)
        assert response.status_code == 200, response.text
        assert response.json()["chunks"] == len(texts) + 1

        response = await client.delete(endpoint, headers=logged_in_headers)
        assert response.status_code == 200, response.text
    finally:
        await _dispose_this_loops_engines()

    called = {name.rsplit(".", 1)[1] for name, _loop, _thread in kb_loops}
    assert {"operation", "ensure_ready", "add_embedded_documents", "similarity_search", "count"} <= called
    this_loop, this_thread = asyncio.get_running_loop(), threading.current_thread()
    elsewhere = [name for name, loop, thread in kb_loops if loop is not this_loop or thread is not this_thread]
    assert elsewhere == []


async def test_knowledge_tools_have_no_sync_entry_point(active_user):
    """An agent awaits the Knowledge tools; a sync call fails instead of starting a loop."""
    component = KnowledgeComponent(knowledge_base="any", _user_id=active_user.id)
    tools = ComponentToolkit(component=component).get_tools()

    assert tools
    for tool in tools:
        assert tool.func is None
        assert tool.coroutine is not None
        with no_second_event_loop() as calls, pytest.raises(NotImplementedError):
            tool.invoke({})
        assert calls == []
