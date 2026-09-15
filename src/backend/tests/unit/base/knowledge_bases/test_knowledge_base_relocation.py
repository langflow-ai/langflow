"""Tests for relocating knowledge base vectors between backends.

Runs against the real test database and real local Chroma directories. The
Chroma-to-Postgres move needs a pgvector database and is opt-in via
``LANGFLOW_RUN_PGVECTOR_INTEGRATION_TESTS=1`` and ``PGVECTOR_CONNECTION_STRING``.
"""

from __future__ import annotations

import contextlib
import gc
import os
import uuid
from typing import TYPE_CHECKING

import pytest
from langflow.api.utils import knowledge_base_service
from langflow.api.utils.knowledge_base_relocation import relocate_knowledge_bases
from langflow.services.deps import get_settings_service
from lfx.base.knowledge_bases.backends import ChromaLocalBackend, IngestedDocument, create_backend

if TYPE_CHECKING:
    from pathlib import Path

DIM = 8


@pytest.fixture
def kb_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "knowledge_bases"
    root.mkdir()
    monkeypatch.setattr(get_settings_service().settings, "knowledge_bases_dir", str(root))
    return root


async def _seed_chroma_kb(kb_root: Path, username: str, kb_name: str, n: int) -> list[IngestedDocument]:
    path = kb_root / username / kb_name
    path.mkdir(parents=True)
    docs = [
        IngestedDocument(id=f"chunk-{i}", content=f"doc {i}", metadata={"i": i}, embedding=[i / 100] * DIM)
        for i in range(n)
    ]
    backend = ChromaLocalBackend(kb_name=kb_name, kb_path=path)
    try:
        await backend.add_embedded_documents(docs)
    finally:
        await backend.teardown()
        gc.collect()
    return docs


class TestRelocationWithoutATarget:
    async def test_stubbed_source_backend_is_reported_not_raised(self, active_user, kb_root):  # noqa: ARG002
        record = await knowledge_base_service.create_record(
            user_id=active_user.id, name="kb_on_astra", backend_type="astra", chunks=3
        )

        results = await relocate_knowledge_bases(target_backend_type="postgres", target_backend_config={})

        result = next(r for r in results if r.kb_id == record.id)
        assert result.status == "failed"
        assert "astra" in result.reason
        row = await knowledge_base_service.get_by_id(record.id)
        assert row.backend_type == "astra"

    async def test_kb_already_on_the_target_is_skipped(self, active_user, kb_root):  # noqa: ARG002
        record = await knowledge_base_service.create_record(
            user_id=active_user.id, name="kb_on_pg", backend_type="postgres"
        )

        results = await relocate_knowledge_bases(target_backend_type="postgres", target_backend_config={})

        assert next(r for r in results if r.kb_id == record.id).status == "skipped"

    async def test_dry_run_counts_without_writing(self, active_user, kb_root):
        await _seed_chroma_kb(kb_root, active_user.username, "kb_dry", 7)
        record = await knowledge_base_service.create_record(
            user_id=active_user.id, name="kb_dry", model_selection={"name": "m", "provider": "p"}, chunks=7
        )

        results = await relocate_knowledge_bases(target_backend_type="postgres", target_backend_config={}, dry_run=True)

        result = next(r for r in results if r.kb_id == record.id)
        assert result.status == "would_relocate"
        assert result.source_count == 7
        row = await knowledge_base_service.get_by_id(record.id)
        assert row.backend_type == "chroma"

    async def test_empty_model_selection_is_warned_about(self, active_user, kb_root):
        await _seed_chroma_kb(kb_root, active_user.username, "kb_no_model", 2)
        record = await knowledge_base_service.create_record(user_id=active_user.id, name="kb_no_model", chunks=2)

        results = await relocate_knowledge_bases(target_backend_type="postgres", target_backend_config={}, dry_run=True)

        warnings = next(r for r in results if r.kb_id == record.id).warnings
        assert any("model_selection" in w for w in warnings)

    async def test_source_holding_fewer_chunks_than_recorded_is_not_repointed(self, active_user, kb_root):
        # The row says 10, the store holds 4: that is what a truncated or
        # half-lost store looks like, so the relocation must refuse, not copy 4.
        await _seed_chroma_kb(kb_root, active_user.username, "kb_short", 4)
        record = await knowledge_base_service.create_record(
            user_id=active_user.id, name="kb_short", model_selection={"name": "m", "provider": "p"}, chunks=10
        )

        results = await relocate_knowledge_bases(target_backend_type="postgres", target_backend_config={})

        result = next(r for r in results if r.kb_id == record.id)
        assert result.status == "failed"
        assert "4 of 10" in result.reason
        row = await knowledge_base_service.get_by_id(record.id)
        assert row.backend_type == "chroma"


@pytest.mark.api_key_required
class TestRelocationToPostgresLive:
    @pytest.fixture(autouse=True)
    def _require_pgvector(self):
        if os.getenv("LANGFLOW_RUN_PGVECTOR_INTEGRATION_TESTS") != "1" or not os.getenv("PGVECTOR_CONNECTION_STRING"):
            pytest.skip("Set LANGFLOW_RUN_PGVECTOR_INTEGRATION_TESTS=1 and PGVECTOR_CONNECTION_STRING")
        pytest.importorskip("pgvector")

    async def test_moves_vectors_and_repoints_the_row(self, active_user, kb_root, tmp_path: Path):
        kb_name = f"kb_move_{uuid.uuid4().hex[:6]}"
        seeded = await _seed_chroma_kb(kb_root, active_user.username, kb_name, 12)
        record = await knowledge_base_service.create_record(
            user_id=active_user.id, name=kb_name, model_selection={"name": "m", "provider": "p"}, chunks=12
        )
        target = create_backend(
            "postgres", kb_name=kb_name, kb_path=tmp_path, backend_config={}, user_id=active_user.id
        )
        try:
            results = await relocate_knowledge_bases(
                target_backend_type="postgres", target_backend_config={}, batch_size=5
            )
            result = next(r for r in results if r.kb_id == record.id)
            assert result.status == "relocated", result.reason
            assert (result.source_count, result.copied, result.target_count) == (12, 12, 12)

            row = await knowledge_base_service.get_by_id(record.id)
            assert row.backend_type == "postgres"

            moved = {}
            async for batch in target.iter_documents(include_embeddings=True):
                moved.update({d.id: d for d in batch})
            for doc in seeded:
                assert moved[doc.id].content == doc.content
                assert moved[doc.id].embedding == pytest.approx(doc.embedding)

            # The row now names the target, so a second run leaves it alone.
            rerun = await relocate_knowledge_bases(target_backend_type="postgres", target_backend_config={})
            assert next(r for r in rerun if r.kb_id == record.id).status == "skipped"
        finally:
            with contextlib.suppress(Exception):
                await target.delete_collection()
            await target.teardown()
