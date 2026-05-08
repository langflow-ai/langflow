"""Unit tests for ``knowledge_base_service``.

Exercises the real DB session (via the test harness) so SQL-level
concerns (unique constraint, JSON serialization, update behavior)
surface here rather than leaking into API-level tests.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from langflow.api.utils import knowledge_base_service
from langflow.services.database.models.knowledge_base import KnowledgeBaseStatus

if TYPE_CHECKING:
    from pathlib import Path


class TestCreateAndRead:
    async def test_create_and_get_by_user_and_name(self, active_user):
        record = await knowledge_base_service.create_record(
            user_id=active_user.id,
            name="phase_15_kb_alpha",
            model_selection={"name": "text-embedding-3-small", "provider": "OpenAI"},
            chunk_size=512,
            chunk_overlap=64,
            separator="\n",
            column_config=[{"column_name": "text", "vectorize": True, "identifier": True}],
        )
        assert record.id is not None
        assert record.status == KnowledgeBaseStatus.READY.value

        fetched = await knowledge_base_service.get_by_user_and_name(active_user.id, "phase_15_kb_alpha")
        assert fetched is not None
        assert fetched.id == record.id
        assert fetched.model_selection == {"name": "text-embedding-3-small", "provider": "OpenAI"}
        assert fetched.chunk_size == 512

    async def test_get_by_user_and_name_returns_none_when_missing(self, active_user):
        result = await knowledge_base_service.get_by_user_and_name(active_user.id, "does_not_exist")
        assert result is None

    async def test_list_by_user_orders_newest_first(self, active_user):
        first = await knowledge_base_service.create_record(
            user_id=active_user.id,
            name="phase_15_kb_list_a",
            model_selection={"name": "m", "provider": "OpenAI"},
        )
        second = await knowledge_base_service.create_record(
            user_id=active_user.id,
            name="phase_15_kb_list_b",
            model_selection={"name": "m", "provider": "OpenAI"},
        )
        rows = await knowledge_base_service.list_by_user(active_user.id)
        ids = [r.id for r in rows]
        # Both ours must be present and the newer one must precede the older one.
        assert first.id in ids
        assert second.id in ids
        assert ids.index(second.id) < ids.index(first.id)


class TestUpdates:
    async def test_update_stats_refreshes_cached_counters(self, active_user):
        record = await knowledge_base_service.create_record(
            user_id=active_user.id,
            name="phase_15_kb_stats",
            model_selection={"name": "m", "provider": "OpenAI"},
        )
        await knowledge_base_service.update_stats(
            record.id,
            chunks=10,
            words=200,
            characters=1000,
            size_bytes=4096,
            source_types=["pdf", "md"],
            chunk_size=512,
            chunk_overlap=64,
            separator="\n",
        )
        fetched = await knowledge_base_service.get_by_id(record.id)
        assert fetched is not None
        assert fetched.chunks == 10
        assert fetched.words == 200
        assert fetched.characters == 1000
        assert fetched.size_bytes == 4096
        assert fetched.source_types == ["md", "pdf"]  # dedup + sorted
        assert fetched.chunk_size == 512
        assert fetched.chunk_overlap == 64
        assert fetched.separator == "\n"

    async def test_update_stats_can_clear_separator(self, active_user):
        record = await knowledge_base_service.create_record(
            user_id=active_user.id,
            name="phase_15_kb_separator_clear",
            model_selection={"name": "m", "provider": "OpenAI"},
            separator="\n",
        )

        await knowledge_base_service.update_stats(record.id, separator=None)

        fetched = await knowledge_base_service.get_by_id(record.id)
        assert fetched is not None
        assert fetched.separator is None

    async def test_update_stats_missing_row_is_silent(self, active_user):  # noqa: ARG002
        import uuid

        # Should not raise — logged and returned.
        await knowledge_base_service.update_stats(uuid.uuid4(), chunks=1)

    async def test_update_status(self, active_user):
        record = await knowledge_base_service.create_record(
            user_id=active_user.id,
            name="phase_15_kb_status",
            model_selection={"name": "m", "provider": "OpenAI"},
        )
        await knowledge_base_service.update_status(
            record.id, status=KnowledgeBaseStatus.FAILED, failure_reason="test error"
        )
        fetched = await knowledge_base_service.get_by_id(record.id)
        assert fetched is not None
        assert fetched.status == KnowledgeBaseStatus.FAILED.value
        assert fetched.failure_reason == "test error"


class TestDelete:
    async def test_delete_by_user_and_name_removes_row(self, active_user):
        await knowledge_base_service.create_record(
            user_id=active_user.id,
            name="phase_15_kb_delete",
            model_selection={"name": "m", "provider": "OpenAI"},
        )
        assert await knowledge_base_service.get_by_user_and_name(active_user.id, "phase_15_kb_delete") is not None

        await knowledge_base_service.delete_by_user_and_name(active_user.id, "phase_15_kb_delete")
        assert await knowledge_base_service.get_by_user_and_name(active_user.id, "phase_15_kb_delete") is None

    async def test_delete_missing_is_noop(self, active_user):
        # Should not raise — the row may have never existed.
        await knowledge_base_service.delete_by_user_and_name(active_user.id, "never_created")


class TestNormalization:
    def test_record_to_metadata_dict_matches_json_shape(self):
        import uuid
        from datetime import datetime, timezone

        from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord

        record = KnowledgeBaseRecord(
            id=uuid.uuid4(),
            name="kb",
            user_id=uuid.uuid4(),
            # Provider / model now derived from ``model_selection`` —
            # the flat columns no longer exist on the table.
            model_selection={"name": "text-embedding-3-small", "provider": "OpenAI"},
            chunk_size=1000,
            chunk_overlap=200,
            backend_type="opensearch",
            backend_config={"index_name": "kb_index"},
            chunks=4,
            words=200,
            characters=1000,
            size_bytes=500,
            source_types=["pdf"],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        snapshot = knowledge_base_service.record_to_metadata_dict(record)
        # Flat fields are derived views over ``model_selection``.
        assert snapshot["embedding_provider"] == "OpenAI"
        assert snapshot["embedding_model"] == "text-embedding-3-small"
        # Matches legacy JSON keys so downstream readers stay intact.
        for key in [
            "id",
            "embedding_provider",
            "embedding_model",
            "model_selection",
            "chunk_size",
            "chunk_overlap",
            "backend_type",
            "backend_config",
            "chunks",
            "words",
            "characters",
            "size",
            "source_types",
            "status",
            "avg_chunk_size",
        ]:
            assert key in snapshot
        assert snapshot["size"] == 500  # note the legacy JSON uses "size" not "size_bytes"
        assert snapshot["avg_chunk_size"] == round(1000 / 4, 1)
        assert snapshot["backend_type"] == "opensearch"
        assert snapshot["backend_config"] == {"index_name": "kb_index"}

    def test_record_to_metadata_dict_maps_zero_chunk_ready_kb_to_empty_status(self):
        import uuid

        from langflow.services.database.models.knowledge_base import KnowledgeBaseRecord

        record = KnowledgeBaseRecord(
            id=uuid.uuid4(),
            name="kb_empty",
            user_id=uuid.uuid4(),
            model_selection={"name": "text-embedding-3-small", "provider": "OpenAI"},
            chunks=0,
            words=0,
            characters=0,
            size_bytes=0,
            status=KnowledgeBaseStatus.READY.value,
        )

        snapshot = knowledge_base_service.record_to_metadata_dict(record)
        assert snapshot["status"] == "empty"


class TestBackfillFromDisk:
    async def test_backfill_inserts_missing_rows(self, active_user, tmp_path: Path):
        kb_root = tmp_path / active_user.username
        kb_root.mkdir()

        # Two on-disk KBs, no DB rows yet.
        for name, provider in [("diskonly_a", "OpenAI"), ("diskonly_b", "HuggingFace")]:
            kb_dir = kb_root / name
            kb_dir.mkdir()
            (kb_dir / "embedding_metadata.json").write_text(
                json.dumps(
                    {
                        "embedding_provider": provider,
                        "embedding_model": "m",
                        "chunk_size": 512,
                        "chunk_overlap": 50,
                        "chunks": 161,
                        "words": 3200,
                        "characters": 18000,
                        "size": 4096,
                        "source_types": ["txt", "pdf"],
                    }
                )
            )

        inserted = await knowledge_base_service.backfill_from_disk(user_id=active_user.id, kb_user_root=kb_root)
        assert inserted == 2

        a = await knowledge_base_service.get_by_user_and_name(active_user.id, "diskonly_a")
        assert a is not None
        # Provider lives on ``model_selection`` now (synthesized by the
        # backfill from the legacy flat fields on disk).
        assert a.model_selection.get("provider") == "OpenAI"
        assert a.chunk_size == 512
        assert a.chunks == 161
        assert a.words == 3200
        assert a.characters == 18000
        assert a.size_bytes > 0
        assert a.source_types == ["pdf", "txt"]

    async def test_backfill_uses_recounted_disk_stats(self, active_user, tmp_path: Path, monkeypatch):
        kb_root = tmp_path / active_user.username
        kb_root.mkdir()
        kb_dir = kb_root / "legacy_with_chunks"
        kb_dir.mkdir()
        (kb_dir / "chroma.sqlite3").write_text("legacy vector data")
        (kb_dir / "embedding_metadata.json").write_text(
            json.dumps(
                {
                    "embedding_provider": "OpenAI",
                    "embedding_model": "m",
                    "chunk_size": 512,
                    "chunk_overlap": 50,
                    "chunks": 0,
                    "words": 0,
                    "characters": 0,
                    "size": 0,
                    "source_types": [],
                }
            )
        )

        def fake_get_metadata(kb_path: Path, *, fast: bool = False) -> dict:
            assert kb_path == kb_dir
            assert fast is False
            return {
                "embedding_provider": "OpenAI",
                "embedding_model": "m",
                "chunk_size": 512,
                "chunk_overlap": 50,
                "chunks": 161,
                "words": 3200,
                "characters": 18000,
                "size": 4096,
                "source_types": ["file_upload"],
            }

        monkeypatch.setattr("langflow.api.utils.kb_helpers.KBAnalysisHelper.get_metadata", fake_get_metadata)

        inserted = await knowledge_base_service.backfill_from_disk(user_id=active_user.id, kb_user_root=kb_root)
        assert inserted == 1

        record = await knowledge_base_service.get_by_user_and_name(active_user.id, "legacy_with_chunks")
        assert record is not None
        assert record.chunks == 161
        assert record.words == 3200
        assert record.characters == 18000
        assert record.size_bytes == 4096
        assert record.source_types == ["file_upload"]
        assert knowledge_base_service.record_to_metadata_dict(record)["status"] == KnowledgeBaseStatus.READY.value

    async def test_backfill_is_idempotent(self, active_user, tmp_path: Path):
        kb_root = tmp_path / active_user.username
        kb_root.mkdir()
        kb_dir = kb_root / "diskonly_idem"
        kb_dir.mkdir()
        (kb_dir / "embedding_metadata.json").write_text(
            json.dumps({"embedding_provider": "OpenAI", "embedding_model": "m"})
        )

        first = await knowledge_base_service.backfill_from_disk(user_id=active_user.id, kb_user_root=kb_root)
        second = await knowledge_base_service.backfill_from_disk(user_id=active_user.id, kb_user_root=kb_root)
        assert first == 1
        assert second == 0  # already backfilled — no duplicates created

    async def test_backfill_skips_missing_metadata(self, active_user, tmp_path: Path):
        kb_root = tmp_path / active_user.username
        kb_root.mkdir()
        kb_dir = kb_root / "unreadable"
        kb_dir.mkdir()
        # No metadata file → skip, don't crash.

        inserted = await knowledge_base_service.backfill_from_disk(user_id=active_user.id, kb_user_root=kb_root)
        assert inserted == 0

    async def test_backfill_missing_root_returns_zero(self, active_user, tmp_path: Path):
        inserted = await knowledge_base_service.backfill_from_disk(
            user_id=active_user.id, kb_user_root=tmp_path / "does_not_exist"
        )
        assert inserted == 0

    async def test_backfill_skips_directories_with_deletion_sentinel(self, active_user, tmp_path: Path):
        """Backfill must skip directories carrying the ``.kb_deleted`` sentinel.

        A KB whose row was deleted but whose bytes remain on disk (locked
        Chroma SQLite, etc.) carries a ``.kb_deleted`` sentinel.  The backfill
        must NOT re-insert such directories or the deleted KB would
        reappear on every server restart.
        """
        from langflow.api.utils.kb_helpers import KB_DELETED_SENTINEL

        kb_root = tmp_path / active_user.username
        kb_root.mkdir()
        kb_dir = kb_root / "tombstoned"
        kb_dir.mkdir()
        (kb_dir / "embedding_metadata.json").write_text(
            json.dumps({"embedding_provider": "OpenAI", "embedding_model": "m"})
        )
        (kb_dir / KB_DELETED_SENTINEL).touch()

        inserted = await knowledge_base_service.backfill_from_disk(user_id=active_user.id, kb_user_root=kb_root)
        assert inserted == 0
        assert await knowledge_base_service.get_by_user_and_name(active_user.id, "tombstoned") is None


class TestBackfillAllUsersFromDisk:
    async def test_backfill_all_users_scans_each_user_root(self, active_user, tmp_path: Path):
        from langflow.services.database.models.user.model import User
        from langflow.services.deps import get_auth_service, session_scope

        other_username = "phase15_other_user"
        other_user_id = None

        async with session_scope() as session:
            other_user = User(
                username=other_username,
                password=get_auth_service().get_password_hash("testpassword"),
                is_active=True,
                is_superuser=False,
            )
            session.add(other_user)
            await session.flush()
            await session.refresh(other_user)
            other_user_id = other_user.id
        assert other_user_id is not None

        for username, kb_name in [(active_user.username, "startup_kb_a"), (other_username, "startup_kb_b")]:
            kb_dir = tmp_path / username / kb_name
            kb_dir.mkdir(parents=True)
            (kb_dir / "embedding_metadata.json").write_text(
                json.dumps(
                    {
                        "embedding_provider": "OpenAI",
                        "embedding_model": "text-embedding-3-small",
                    }
                )
            )

        try:
            inserted = await knowledge_base_service.backfill_all_users_from_disk(kb_root=tmp_path)
            assert inserted == 2
            assert await knowledge_base_service.get_by_user_and_name(active_user.id, "startup_kb_a") is not None
            assert await knowledge_base_service.get_by_user_and_name(other_user_id, "startup_kb_b") is not None
        finally:
            async with session_scope() as session:
                other_user = await session.get(User, other_user_id)
                if other_user is not None:
                    await session.delete(other_user)


class TestReadMetadata:
    async def test_read_metadata_prefers_db(self, active_user, tmp_path: Path):
        record = await knowledge_base_service.create_record(
            user_id=active_user.id,
            name="phase_15_kb_read_db",
            model_selection={"name": "from_db", "provider": "OpenAI"},
        )
        await knowledge_base_service.update_stats(record.id, chunks=7, words=42, characters=100, size_bytes=2048)

        # Write a conflicting disk copy — DB read should win.
        kb_path = tmp_path / "phase_15_kb_read_db"
        kb_path.mkdir()
        (kb_path / "embedding_metadata.json").write_text(json.dumps({"embedding_provider": "from_disk", "chunks": 999}))

        metadata = await knowledge_base_service.read_metadata(
            user_id=active_user.id, name="phase_15_kb_read_db", kb_path=kb_path
        )
        assert metadata["embedding_provider"] == "OpenAI"
        assert metadata["embedding_model"] == "from_db"
        assert metadata["chunks"] == 7

    async def test_read_metadata_falls_back_to_disk(self, active_user, tmp_path: Path):
        kb_path = tmp_path / "phase_15_kb_only_disk"
        kb_path.mkdir()
        (kb_path / "embedding_metadata.json").write_text(json.dumps({"embedding_provider": "only_disk", "chunks": 3}))

        metadata = await knowledge_base_service.read_metadata(
            user_id=active_user.id, name="phase_15_kb_only_disk", kb_path=kb_path
        )
        assert metadata["embedding_provider"] == "only_disk"
        assert metadata["chunks"] == 3

    async def test_read_metadata_returns_empty_when_nowhere(self, active_user, tmp_path: Path):
        metadata = await knowledge_base_service.read_metadata(
            user_id=active_user.id, name="not_in_db_or_disk", kb_path=tmp_path / "ghost"
        )
        assert metadata == {}


class TestUniqueConstraint:
    async def test_duplicate_user_name_rejected(self, active_user):
        from sqlalchemy.exc import IntegrityError

        await knowledge_base_service.create_record(
            user_id=active_user.id,
            name="phase_15_kb_dup",
            model_selection={"name": "m", "provider": "OpenAI"},
        )
        with pytest.raises(IntegrityError):
            await knowledge_base_service.create_record(
                user_id=active_user.id,
                name="phase_15_kb_dup",
                model_selection={"name": "m", "provider": "OpenAI"},
            )
