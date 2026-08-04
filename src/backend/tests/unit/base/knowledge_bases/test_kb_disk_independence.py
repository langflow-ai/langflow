"""Knowledge Bases must not depend on a shared filesystem when remote-backed.

A KB whose vectors live in pgvector / OpenSearch / Chroma Cloud keeps nothing
of substance on local disk, so every read path has to resolve from the
``knowledge_base`` row. Before this, a replica that never held the KB directory
would 404 (routes) or raise "Metadata not found" (retrieval component) even
though the vectors were sitting readable in the configured store — which forced
operators onto an RWX volume shared across replicas.

These tests pin the row-first contract at each layer that used to read disk.
"""

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lfx.base.knowledge_bases.backends import BackendType, requires_local_disk


class TestRequiresLocalDisk:
    """The single predicate every 'do we need the directory?' call site shares."""

    def test_local_chroma_requires_disk(self):
        assert requires_local_disk(BackendType.CHROMA.value, {}) is True

    def test_explicit_local_mode_requires_disk(self):
        assert requires_local_disk(BackendType.CHROMA.value, {"mode": "local"}) is True

    def test_chroma_cloud_does_not_require_disk(self):
        assert requires_local_disk(BackendType.CHROMA.value, {"mode": "cloud"}) is False

    def test_chroma_cloud_mode_is_case_insensitive(self):
        assert requires_local_disk(BackendType.CHROMA.value, {"mode": "Cloud"}) is False

    @pytest.mark.parametrize(
        "backend_type",
        [BackendType.POSTGRES.value, BackendType.OPENSEARCH.value, BackendType.MONGODB.value],
    )
    def test_remote_backends_never_require_disk(self, backend_type):
        assert requires_local_disk(backend_type, {}) is False

    def test_none_backend_type_defaults_to_chroma(self):
        # ``backend_type`` is NOT NULL with a "chroma" default, but a legacy
        # row read through a loose path can still surface None. Treat it as
        # local so we never skip a check a real local KB needed.
        assert requires_local_disk(None, None) is True


class TestLoadKbMetadataDbFirst:
    """The routes' metadata reader: row first, sidecar only as a legacy fallback."""

    async def test_prefers_supplied_record_without_touching_disk(self):
        from langflow.api.utils.kb_helpers import load_kb_metadata_db_first

        record = MagicMock()
        with patch("langflow.api.utils.knowledge_base_service.record_to_metadata_dict") as to_dict:
            to_dict.return_value = {"embedding_model": "from-row"}
            result = await load_kb_metadata_db_first(
                user_id=uuid.uuid4(),
                kb_name="kb",
                kb_path=Path("/nonexistent-on-this-replica"),
                record=record,
            )
        assert result == {"embedding_model": "from-row"}
        to_dict.assert_called_once_with(record)

    async def test_looks_up_row_when_no_record_supplied(self):
        from langflow.api.utils.kb_helpers import load_kb_metadata_db_first

        record = MagicMock()
        user_id = uuid.uuid4()
        with (
            patch(
                "langflow.api.utils.knowledge_base_service.get_by_user_and_name",
                new=AsyncMock(return_value=record),
            ) as get_row,
            patch(
                "langflow.api.utils.knowledge_base_service.record_to_metadata_dict",
                return_value={"embedding_model": "from-row"},
            ),
        ):
            result = await load_kb_metadata_db_first(user_id=user_id, kb_name="kb")
        assert result == {"embedding_model": "from-row"}
        get_row.assert_awaited_once_with(user_id, "kb")

    async def test_returns_empty_when_no_row_and_no_path(self):
        """A caller that passes no ``kb_path`` must never touch the filesystem."""
        from langflow.api.utils.kb_helpers import load_kb_metadata_db_first

        with (
            patch(
                "langflow.api.utils.knowledge_base_service.get_by_user_and_name",
                new=AsyncMock(return_value=None),
            ),
            patch("langflow.api.utils.kb_helpers.KBAnalysisHelper.get_metadata") as get_metadata,
        ):
            result = await load_kb_metadata_db_first(user_id=uuid.uuid4(), kb_name="kb")
        assert result == {}
        get_metadata.assert_not_called()

    async def test_falls_back_to_sidecar_for_legacy_disk_only_kb(self):
        from langflow.api.utils.kb_helpers import load_kb_metadata_db_first

        with (
            patch(
                "langflow.api.utils.knowledge_base_service.get_by_user_and_name",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "langflow.api.utils.kb_helpers.KBAnalysisHelper.get_metadata",
                return_value={"embedding_model": "from-disk"},
            ) as get_metadata,
        ):
            result = await load_kb_metadata_db_first(
                user_id=uuid.uuid4(),
                kb_name="kb",
                kb_path=Path("/tmp/legacy-kb"),  # noqa: S108 — patched, never read
                fast=False,
            )
        assert result == {"embedding_model": "from-disk"}
        assert get_metadata.call_args.kwargs["fast"] is False


class TestRetrievalComponentMetadataResolution:
    """The serving-plane fix: retrieval resolves its embedding config from the row.

    ``KnowledgeBaseComponent`` is a thin subclass of the shared
    ``KnowledgeComponent``, so exercising the base method covers both the
    retrieval and ingestion components.
    """

    @pytest.fixture
    def component(self):
        from lfx.components.files_and_knowledge.retrieval import KnowledgeBaseComponent

        return KnowledgeBaseComponent(knowledge_base="kb")

    async def test_uses_row_when_sidecar_absent(self, component, tmp_path):
        """The exact case that used to raise 'Metadata not found' on a fresh replica."""
        missing_kb_dir = tmp_path / "no-such-kb"
        assert not (missing_kb_dir / "embedding_metadata.json").exists()

        row_metadata = {"model_selection": {"name": "m", "provider": "OpenAI"}, "chunk_size": 1000}
        with patch.object(component, "_metadata_from_record", new=AsyncMock(return_value=row_metadata)):
            result = await component._load_kb_metadata_db_first(missing_kb_dir, require_api_key=True)

        assert result == row_metadata

    async def test_row_wins_over_sidecar_but_inherits_legacy_api_key(self, component, tmp_path):
        """The row has no ``api_key`` column, so the sidecar still supplies it."""
        import json as _json

        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        (kb_dir / "embedding_metadata.json").write_text(
            _json.dumps({"model_selection": {"name": "stale", "provider": "OpenAI"}, "api_key": "decrypted-key"})
        )

        row_metadata = {"model_selection": {"name": "current", "provider": "OpenAI"}}
        with (
            patch.object(component, "_metadata_from_record", new=AsyncMock(return_value=row_metadata)),
            patch.object(
                component,
                "_get_kb_metadata",
                return_value={"model_selection": {"name": "stale", "provider": "OpenAI"}, "api_key": "decrypted-key"},
            ),
        ):
            result = await component._load_kb_metadata_db_first(kb_dir, require_api_key=True)

        assert result["model_selection"]["name"] == "current"
        assert result["api_key"] == "decrypted-key"

    async def test_falls_back_to_sidecar_when_no_row(self, component, tmp_path):
        """Legacy disk-only KBs keep working unchanged."""
        import json as _json

        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        sidecar = {"model_selection": {"name": "legacy", "provider": "OpenAI"}}
        (kb_dir / "embedding_metadata.json").write_text(_json.dumps(sidecar))

        with (
            patch.object(component, "_metadata_from_record", new=AsyncMock(return_value=None)),
            patch.object(component, "_get_kb_metadata", return_value=sidecar),
        ):
            result = await component._load_kb_metadata_db_first(kb_dir, require_api_key=False)

        assert result == sidecar

    async def test_returns_empty_when_neither_source_resolves(self, component, tmp_path):
        """Caller still fails loudly — we removed the disk dependency, not the check."""
        with patch.object(component, "_metadata_from_record", new=AsyncMock(return_value=None)):
            result = await component._load_kb_metadata_db_first(tmp_path / "gone", require_api_key=False)
        assert result == {}


class TestKnowledgeBasesDropdown:
    """``get_knowledge_bases`` backs the canvas dropdown and is DB-first."""

    async def test_lists_rows_when_kb_root_does_not_exist(self, tmp_path):
        """The premature ``kb_root.exists()`` guard made the DB branch unreachable.

        On a remote-backed deployment there may be no KB directory at all, so an
        early return left the dropdown empty despite rows existing.
        """
        from lfx.base.knowledge_bases.knowledge_base_utils import get_knowledge_bases

        user_id = uuid.uuid4()
        row = MagicMock()
        row.name = "remote_kb"
        row.source_types = []

        missing_root = tmp_path / "never-created"
        assert not missing_root.exists()

        session = MagicMock()
        session.exec = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[row])))

        session_cm = MagicMock()
        session_cm.__aenter__ = AsyncMock(return_value=session)
        session_cm.__aexit__ = AsyncMock(return_value=False)

        user = MagicMock()
        user.username = "someone"

        with (
            patch("lfx.services.deps.session_scope", return_value=session_cm),
            patch(
                "langflow.services.database.models.user.crud.get_user_by_id",
                new=AsyncMock(return_value=user),
            ),
        ):
            names = await get_knowledge_bases(missing_root, user_id)

        assert names == ["remote_kb"]
