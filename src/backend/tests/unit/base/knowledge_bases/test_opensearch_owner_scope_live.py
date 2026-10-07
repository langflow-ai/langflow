"""Live checks that OpenSearch knowledge bases are isolated per owner.

Knowledge base names are unique per user, not globally. These tests give two
users a knowledge base with the same name and verify that neither can read,
count, search, or delete the other's chunks.

Opt-in: set ``LANGFLOW_RUN_OPENSEARCH_INTEGRATION_TESTS=1`` and ``OPENSEARCH_URL``
to a reachable cluster with security disabled, for example
``docker run -p 9200:9200 -e discovery.type=single-node -e DISABLE_SECURITY_PLUGIN=true
opensearchproject/opensearch:2.11.0``.
"""

from __future__ import annotations

import hashlib
import importlib
import os
import uuid
from typing import TYPE_CHECKING

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


def _require_live_opensearch() -> None:
    if os.getenv("LANGFLOW_RUN_OPENSEARCH_INTEGRATION_TESTS") != "1":
        pytest.skip("Set LANGFLOW_RUN_OPENSEARCH_INTEGRATION_TESTS=1 to run live OpenSearch tests")
    if not os.getenv("OPENSEARCH_URL"):
        pytest.skip("OPENSEARCH_URL not set")
    pytest.importorskip("opensearchpy")


class _HashEmbeddings(Embeddings):
    """Deterministic embeddings so no model or API key is involved."""

    def _vector(self, text: str) -> list[float]:
        return [byte / 255 for byte in hashlib.sha256(text.encode()).digest()[:8]]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


def _backend(kb_name: str, owner_id: uuid.UUID, backend_config: dict | None = None) -> BaseVectorStoreBackend:
    return create_backend(
        "opensearch",
        kb_name=kb_name,
        backend_config=backend_config or {"url_variable": "OPENSEARCH_URL"},
        embedding_function=_HashEmbeddings(),
        user_id=owner_id,
    )


async def _write(backend: BaseVectorStoreBackend, *texts: str) -> None:
    await backend.ensure_ready()
    await backend.add_documents([Document(page_content=text) for text in texts])
    backend._os_client.indices.refresh(index=backend._os_index)


async def _contents(backend: BaseVectorStoreBackend) -> list[str]:
    found: list[str] = []
    async for batch in backend.iter_documents(batch_size=100):
        found.extend(doc.content for doc in batch)
    return sorted(found)


async def _drop(backend: BaseVectorStoreBackend) -> None:
    try:
        await backend.ensure_ready()
        await backend.delete_collection()
    finally:
        await backend.teardown()


@pytest.mark.api_key_required
async def test_same_kb_name_for_two_owners_does_not_share_chunks() -> None:
    _require_live_opensearch()
    kb_name = f"docs_{uuid.uuid4().hex[:8]}"
    alice, bob = _backend(kb_name, uuid.uuid4()), _backend(kb_name, uuid.uuid4())
    try:
        await _write(alice, "alice: payroll")
        await _write(bob, "bob: merger plan")

        assert alice._os_index != bob._os_index
        assert await _contents(alice) == ["alice: payroll"]
        assert await _contents(bob) == ["bob: merger plan"]
        assert await alice.count() == 1
        assert await bob.count() == 1
        hits = await alice.similarity_search("bob: merger plan", k=5)
        assert [doc.page_content for doc, _ in hits] == ["alice: payroll"]

        await alice.delete_collection()
        assert bob._os_client.indices.exists(index=bob._os_index)
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
    client: AsyncClient,
    active_user,
    logged_in_headers,
    user_two,
) -> None:
    _require_live_opensearch()
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
                    "backend_type": "opensearch",
                    "backend_config": {"url_variable": "OPENSEARCH_URL"},
                },
            )
            assert response.status_code == 201, response.text

        # Ingestion writes through ``backend.add_documents`` with the owner's id;
        # seed through the same path so no embedding model is needed.
        for owner_id, text in ((active_user.id, "user one chunk"), (user_two.id, "user two chunk")):
            backend = _backend(kb_name, owner_id)
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
            await _drop(_backend(kb_name, owner_id))


def _migrate(monkeypatch: pytest.MonkeyPatch, rows: list[tuple[uuid.UUID, str, dict]]) -> list[dict]:
    """Run the index-pin migration over ``knowledge_base`` rows and return their configs in order."""
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
                    id=row_id, user_id=owner_id, name=name, backend_type="opensearch", backend_config=config
                )
            )
        monkeypatch.setattr(_PIN_MIGRATION, "op", Operations(MigrationContext.configure(conn)))
        _PIN_MIGRATION.upgrade()
        configs = {
            row["id"]: row["backend_config"]
            for row in conn.execute(sa.select(table.c.id, table.c.backend_config)).mappings()
        }
    return [configs[row_id] for row_id in ids]


def _legacy_backend(kb_name: str, owner_id: uuid.UUID) -> BaseVectorStoreBackend:
    """A backend writing where pre-scoping code did: the index named from ``kb_name``."""
    config = {"url_variable": "OPENSEARCH_URL", "index_name": _PIN_MIGRATION.legacy_index_name(kb_name)}
    return _backend(kb_name, owner_id, config)


@pytest.mark.api_key_required
async def test_pinned_pre_scoping_index_keeps_serving_its_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    _require_live_opensearch()
    kb_name = f"Docs {uuid.uuid4().hex[:8]}"
    owner, newcomer = uuid.uuid4(), uuid.uuid4()
    legacy = _legacy_backend(kb_name, owner)
    backends = [legacy]
    try:
        await _write(legacy, "chunk written before the upgrade")

        [pinned_config] = _migrate(monkeypatch, [(owner, kb_name, {"url_variable": "OPENSEARCH_URL"})])
        assert pinned_config["index_name"] == legacy._os_index

        after_upgrade = _backend(kb_name, owner, pinned_config)
        # A same-named KB another user creates after the upgrade has no pin.
        other_user = _backend(kb_name, newcomer)
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
async def test_index_already_shared_by_two_owners_is_neither_served_nor_deleted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _require_live_opensearch()
    kb_name = f"docs_{uuid.uuid4().hex[:8]}"
    alice, bob = uuid.uuid4(), uuid.uuid4()
    shared = _legacy_backend(kb_name, alice)
    backends = [shared]
    try:
        await _write(shared, "alice chunk", "bob chunk")

        alice_config, bob_config = _migrate(
            monkeypatch,
            [(alice, kb_name, {"url_variable": "OPENSEARCH_URL"}), (bob, kb_name, {"url_variable": "OPENSEARCH_URL"})],
        )
        assert "index_name" not in alice_config
        assert alice_config["legacy_shared_index"] == shared._os_index
        assert bob_config["legacy_shared_index"] == shared._os_index

        alice_kb, bob_kb = _backend(kb_name, alice, alice_config), _backend(kb_name, bob, bob_config)
        backends += [alice_kb, bob_kb]
        await alice_kb.ensure_ready()
        await bob_kb.ensure_ready()
        assert await _contents(alice_kb) == []
        assert await _contents(bob_kb) == []

        await alice_kb.delete_collection()
        await bob_kb.delete_collection()
        assert await _contents(shared) == ["alice chunk", "bob chunk"]
    finally:
        for backend in backends:
            await _drop(backend)
