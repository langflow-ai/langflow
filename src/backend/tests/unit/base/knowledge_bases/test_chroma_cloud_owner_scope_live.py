"""Live checks that Chroma Cloud knowledge bases are isolated per owner.

Knowledge base names are unique per user, not globally, while every user whose
credentials resolve to the same Chroma Cloud tenant and database shares one
collection namespace. These tests give two users a knowledge base with the same
name and verify that neither can read, count, search, or delete the other's
chunks.

Opt-in: set ``LANGFLOW_RUN_CHROMA_CLOUD_INTEGRATION_TESTS=1`` and ``CHROMA_API_KEY``
(plus ``CHROMA_TENANT`` / ``CHROMA_DATABASE`` when the key does not imply them).
The tests create and delete collections named ``lf_<hex>`` and ``docs_<hex>``.

To use a local server instead of Chroma Cloud, run ``chroma run --port 8000`` and
also set ``CHROMA_CLOUD_HOST=localhost``, ``CHROMA_CLOUD_PORT=8000``,
``CHROMA_CLOUD_ENABLE_SSL=0``, ``CHROMA_API_KEY`` to any value,
``CHROMA_TENANT=default_tenant``, and ``CHROMA_DATABASE=default_database``.
"""

from __future__ import annotations

import functools
import hashlib
import importlib
import os
import uuid
from typing import TYPE_CHECKING

import chromadb
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from lfx.base.knowledge_bases.backends import create_backend

if TYPE_CHECKING:
    from httpx import AsyncClient
    from lfx.base.knowledge_bases.backends import BaseVectorStoreBackend

_PIN_MIGRATION = importlib.import_module("langflow.alembic.versions.386662af02e9_pin_legacy_remote_kb_storage_names")


@pytest.fixture
def live_chroma_cloud(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Return the base ``backend_config`` for the configured Chroma Cloud (or local stand-in)."""
    if os.getenv("LANGFLOW_RUN_CHROMA_CLOUD_INTEGRATION_TESTS") != "1":
        pytest.skip("Set LANGFLOW_RUN_CHROMA_CLOUD_INTEGRATION_TESTS=1 to run live Chroma Cloud tests")
    if not os.getenv("CHROMA_API_KEY"):
        pytest.skip("CHROMA_API_KEY not set")
    config: dict = {"mode": "cloud"}
    if host := os.getenv("CHROMA_CLOUD_HOST"):
        config["cloud_host"] = host
    if port := os.getenv("CHROMA_CLOUD_PORT"):
        config["cloud_port"] = port
    if os.getenv("CHROMA_CLOUD_ENABLE_SSL") == "0":
        monkeypatch.setattr(chromadb, "CloudClient", functools.partial(chromadb.CloudClient, enable_ssl=False))
    return config


class _HashEmbeddings(Embeddings):
    """Deterministic embeddings so no model or API key is involved."""

    def _vector(self, text: str) -> list[float]:
        return [byte / 255 for byte in hashlib.sha256(text.encode()).digest()[:8]]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


def _backend(kb_name: str, owner_id: uuid.UUID, backend_config: dict) -> BaseVectorStoreBackend:
    return create_backend(
        "chroma",
        kb_name=kb_name,
        backend_config=backend_config,
        embedding_function=_HashEmbeddings(),
        user_id=owner_id,
    )


async def _write(backend: BaseVectorStoreBackend, *texts: str) -> None:
    await backend.ensure_ready()
    # Real ingestion always writes chunk metadata; Chroma stores an empty dict as None.
    await backend.add_documents([Document(page_content=text, metadata={"source": "live-test"}) for text in texts])


async def _contents(backend: BaseVectorStoreBackend) -> list[str]:
    found: list[str] = []
    async for batch in backend.iter_documents(batch_size=100):
        found.extend(doc.content for doc in batch)
    return sorted(found)


def _collection_names(backend: BaseVectorStoreBackend) -> set[str]:
    return {collection.name for collection in backend._get_cloud_client().list_collections()}


async def _drop(backend: BaseVectorStoreBackend) -> None:
    try:
        await backend.ensure_ready()
        if backend._resolve_collection_name() in _collection_names(backend):
            await backend.delete_collection()
    finally:
        await backend.teardown()


@pytest.mark.api_key_required
async def test_same_kb_name_for_two_owners_does_not_share_chunks(live_chroma_cloud: dict) -> None:
    kb_name = f"docs_{uuid.uuid4().hex[:8]}"
    alice = _backend(kb_name, uuid.uuid4(), live_chroma_cloud)
    bob = _backend(kb_name, uuid.uuid4(), live_chroma_cloud)
    try:
        await _write(alice, "alice: payroll")
        await _write(bob, "bob: merger plan")

        assert alice._resolve_collection_name() != bob._resolve_collection_name()
        assert await _contents(alice) == ["alice: payroll"]
        assert await _contents(bob) == ["bob: merger plan"]
        assert await alice.count() == 1
        assert await bob.count() == 1
        hits = await alice.similarity_search("bob: merger plan", k=5)
        assert [doc.page_content for doc, _ in hits] == ["alice: payroll"]

        await alice.delete_collection()
        assert bob._resolve_collection_name() in _collection_names(bob)
        assert await _contents(bob) == ["bob: merger plan"]
    finally:
        await _drop(alice)
        await _drop(bob)


async def _login(client: AsyncClient, username: str, password: str) -> dict[str, str]:
    response = await client.post("api/v1/login", data={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _chunk_contents(client: AsyncClient, kb_name: str, headers: dict[str, str]) -> list[str]:
    response = await client.get(f"api/v1/knowledge_bases/{kb_name}/chunks", headers=headers)
    assert response.status_code == 200, response.text
    return sorted(chunk["content"] for chunk in response.json()["chunks"])


@pytest.mark.api_key_required
async def test_two_users_same_kb_name_are_isolated_through_the_api(
    live_chroma_cloud: dict,
    client: AsyncClient,
    active_user,
    logged_in_headers,
    user_two,
) -> None:
    kb_name = f"docs_{uuid.uuid4().hex[:8]}"
    user_two_headers = await _login(client, user_two.username, "hashed_password")
    owners = {active_user.id: logged_in_headers, user_two.id: user_two_headers}
    try:
        for headers in owners.values():
            response = await client.post(
                "api/v1/knowledge_bases",
                headers=headers,
                json={
                    "name": kb_name,
                    "embedding_provider": "OpenAI",
                    "embedding_model": "text-embedding-3-small",
                    "backend_type": "chroma",
                    "backend_config": live_chroma_cloud,
                },
            )
            assert response.status_code == 201, response.text

        # Ingestion writes through ``backend.add_documents`` with the owner's id;
        # seed through the same path so no embedding model is needed.
        for owner_id, text in ((active_user.id, "user one chunk"), (user_two.id, "user two chunk")):
            backend = _backend(kb_name, owner_id, live_chroma_cloud)
            try:
                await _write(backend, text)
            finally:
                await backend.teardown()

        assert await _chunk_contents(client, kb_name, logged_in_headers) == ["user one chunk"]
        assert await _chunk_contents(client, kb_name, user_two_headers) == ["user two chunk"]

        response = await client.delete(f"api/v1/knowledge_bases/{kb_name}", headers=logged_in_headers)
        assert response.status_code == 200, response.text
        assert "warning" not in response.json()
        assert await _chunk_contents(client, kb_name, user_two_headers) == ["user two chunk"]
    finally:
        for owner_id in owners:
            await _drop(_backend(kb_name, owner_id, live_chroma_cloud))


def _migrate(monkeypatch: pytest.MonkeyPatch, rows: list[tuple[uuid.UUID, str, dict]]) -> list[dict]:
    """Run the storage-name pin migration over ``knowledge_base`` rows and return their configs in order."""
    metadata = sa.MetaData()
    table = sa.Table(
        "knowledge_base",
        metadata,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("backend_type", sa.String(), nullable=False),
        sa.Column("backend_config", sa.JSON(), nullable=False),
    )
    engine = sa.create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    ids = [uuid.uuid4() for _ in rows]
    with engine.begin() as conn:
        for row_id, (owner_id, name, config) in zip(ids, rows, strict=True):
            conn.execute(
                table.insert().values(
                    id=row_id, user_id=owner_id, name=name, backend_type="chroma", backend_config=config
                )
            )
        monkeypatch.setattr(_PIN_MIGRATION, "op", Operations(MigrationContext.configure(conn)))
        _PIN_MIGRATION.upgrade()
        configs = {
            row["id"]: row["backend_config"]
            for row in conn.execute(sa.select(table.c.id, table.c.backend_config)).mappings()
        }
    return [configs[row_id] for row_id in ids]


def _legacy_backend(kb_name: str, owner_id: uuid.UUID, base_config: dict) -> BaseVectorStoreBackend:
    """A backend writing where pre-scoping code did: the collection named after the KB."""
    return _backend(kb_name, owner_id, {**base_config, "collection_name": kb_name})


@pytest.mark.api_key_required
async def test_pinned_pre_scoping_collection_keeps_serving_its_owner(
    live_chroma_cloud: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    kb_name = f"Docs_{uuid.uuid4().hex[:8]}"
    owner, newcomer = uuid.uuid4(), uuid.uuid4()
    legacy = _legacy_backend(kb_name, owner, live_chroma_cloud)
    backends = [legacy]
    try:
        await _write(legacy, "chunk written before the upgrade")

        [pinned_config] = _migrate(monkeypatch, [(owner, kb_name, dict(live_chroma_cloud))])
        assert pinned_config["collection_name"] == kb_name

        after_upgrade = _backend(kb_name, owner, pinned_config)
        # A same-named KB another user creates after the upgrade has no pin.
        other_user = _backend(kb_name, newcomer, live_chroma_cloud)
        backends += [after_upgrade, other_user]
        assert await _contents(after_upgrade) == ["chunk written before the upgrade"]
        await _write(after_upgrade, "chunk written after the upgrade")
        await _write(other_user, "newcomer chunk")

        assert await _contents(after_upgrade) == ["chunk written after the upgrade", "chunk written before the upgrade"]
        assert await _contents(other_user) == ["newcomer chunk"]
        await other_user.delete_collection()
        assert await _contents(after_upgrade) == ["chunk written after the upgrade", "chunk written before the upgrade"]
    finally:
        for backend in backends:
            await _drop(backend)


@pytest.mark.api_key_required
async def test_collection_already_shared_by_two_owners_is_neither_served_nor_deleted(
    live_chroma_cloud: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    kb_name = f"docs_{uuid.uuid4().hex[:8]}"
    alice, bob = uuid.uuid4(), uuid.uuid4()
    shared = _legacy_backend(kb_name, alice, live_chroma_cloud)
    backends = [shared]
    try:
        await _write(shared, "alice chunk", "bob chunk")

        alice_config, bob_config = _migrate(
            monkeypatch,
            [(alice, kb_name, dict(live_chroma_cloud)), (bob, kb_name, dict(live_chroma_cloud))],
        )
        assert "collection_name" not in alice_config
        assert alice_config["legacy_shared_collection"] == kb_name
        assert bob_config["legacy_shared_collection"] == kb_name

        alice_kb = _backend(kb_name, alice, alice_config)
        bob_kb = _backend(kb_name, bob, bob_config)
        backends += [alice_kb, bob_kb]
        assert await _contents(alice_kb) == []
        assert await _contents(bob_kb) == []

        await alice_kb.delete_collection()
        await bob_kb.delete_collection()
        assert await _contents(shared) == ["alice chunk", "bob chunk"]
    finally:
        for backend in backends:
            await _drop(backend)
