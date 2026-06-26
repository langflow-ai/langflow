"""Unit tests for langflow.services.memory_base.task.

Covers the gaps not addressed by TestIngestMemoryTask in test_memory_bases.py:
- ingest_memory_task: missing kb_root, pre-ingestion cancel, zero-document early-out
- extract_content_block_text: all block types, edge cases
- build_documents_from_messages: chunking, content-block text, missing fields
- sync_kb_metadata: source_types merge
- _advance_cursor: vanished session, normal update
- _mark_messages_ingested: correct DB update shape
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langflow.services.database.models.message.model import MessageTable

# ------------------------------------------------------------------ #
#  Shared helpers                                                      #
# ------------------------------------------------------------------ #


def _make_message(
    *,
    flow_id: uuid.UUID | None = None,
    session_id: str = "sess-1",
    text: str = "hello",
    run_id: uuid.UUID | None = None,
    timestamp: datetime | None = None,
    content_blocks: list | None = None,
) -> MessageTable:
    return MessageTable(
        id=uuid.uuid4(),
        sender="AI",
        sender_name="Bot",
        session_id=session_id,
        text=text,
        flow_id=flow_id or uuid.uuid4(),
        timestamp=timestamp or datetime.now(timezone.utc),
        run_id=run_id,
        content_blocks=content_blocks or [],
    )


def _fake_scope(mock_db):
    class _FakeCtx:
        async def __aenter__(self):
            return mock_db

        async def __aexit__(self, *a):
            pass

    scope = MagicMock()
    scope.return_value = _FakeCtx()
    return scope


# ------------------------------------------------------------------ #
#  ingest_memory_task — orchestrator edge cases                       #
# ------------------------------------------------------------------ #


class TestIngestMemoryTaskEdgeCases:
    @pytest.mark.asyncio
    async def test_raises_when_kb_root_not_configured(self):
        from langflow.services.memory_base.task import IngestionRequest, ingest_memory_task

        with (
            patch(
                "langflow.services.memory_base.task.KBStorageHelper.get_root_path",
                return_value=None,
            ),
            pytest.raises(RuntimeError, match="Knowledge base root path is not configured"),
        ):
            await ingest_memory_task(
                request=IngestionRequest(
                    memory_base_id=uuid.uuid4(),
                    session_id="s1",
                    flow_id=uuid.uuid4(),
                    kb_name="kb",
                    kb_username="user",
                    user_id=uuid.uuid4(),
                    embedding_provider="OpenAI",
                    embedding_model="text-embedding-3-small",
                    cursor_id=None,
                    task_job_id=uuid.uuid4(),
                    job_service=MagicMock(),
                ),
            )

    @pytest.mark.asyncio
    async def test_returns_early_when_job_cancelled_before_write(self, tmp_path):
        """is_job_cancelled=True after fetch must return without touching Chroma."""
        from langflow.services.memory_base.task import IngestionRequest, ingest_memory_task

        flow_id = uuid.uuid4()
        msg = _make_message(flow_id=flow_id)
        chroma_client_called = False

        def fake_get_client(_path):
            nonlocal chroma_client_called
            chroma_client_called = True
            return MagicMock()

        with (
            patch(
                "langflow.services.memory_base.task._acquire_session_lock",
                AsyncMock(return_value=asyncio.Lock()),
            ),
            patch("langflow.services.memory_base.task._release_session_lock", AsyncMock()),
            patch("langflow.services.memory_base.task._read_live_cursor", AsyncMock(return_value=None)),
            patch(
                "langflow.services.memory_base.task._fetch_pending_messages",
                AsyncMock(return_value=[msg]),
            ),
            patch(
                "langflow.services.memory_base.task.build_documents_from_messages",
                return_value=[MagicMock()],
            ),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.is_job_cancelled",
                AsyncMock(return_value=True),
            ),
            patch(
                "langflow.services.memory_base.task.KBStorageHelper.get_fresh_chroma_client",
                side_effect=fake_get_client,
            ),
            patch(
                "langflow.services.memory_base.task.KBStorageHelper.get_root_path",
                return_value=tmp_path,
            ),
        ):
            result = await ingest_memory_task(
                request=IngestionRequest(
                    memory_base_id=uuid.uuid4(),
                    session_id="s1",
                    flow_id=flow_id,
                    kb_name="kb",
                    kb_username="user",
                    user_id=uuid.uuid4(),
                    embedding_provider="OpenAI",
                    embedding_model="text-embedding-3-small",
                    cursor_id=None,
                    task_job_id=uuid.uuid4(),
                    job_service=MagicMock(),
                ),
            )

        assert result == {"message": "Job cancelled before ingestion", "ingested": 0}
        assert not chroma_client_called

    @pytest.mark.asyncio
    async def test_returns_early_when_documents_list_is_empty(self, tmp_path):
        """All-whitespace messages produce zero documents — early exit before Chroma."""
        from langflow.services.memory_base.task import IngestionRequest, ingest_memory_task

        flow_id = uuid.uuid4()
        msg = _make_message(flow_id=flow_id, text="   ")  # whitespace only

        with (
            patch(
                "langflow.services.memory_base.task._acquire_session_lock",
                AsyncMock(return_value=asyncio.Lock()),
            ),
            patch("langflow.services.memory_base.task._release_session_lock", AsyncMock()),
            patch("langflow.services.memory_base.task._read_live_cursor", AsyncMock(return_value=None)),
            patch(
                "langflow.services.memory_base.task._fetch_pending_messages",
                AsyncMock(return_value=[msg]),
            ),
            patch(
                "langflow.services.memory_base.task.KBStorageHelper.get_root_path",
                return_value=tmp_path,
            ),
        ):
            result = await ingest_memory_task(
                request=IngestionRequest(
                    memory_base_id=uuid.uuid4(),
                    session_id="s1",
                    flow_id=flow_id,
                    kb_name="kb",
                    kb_username="user",
                    user_id=uuid.uuid4(),
                    embedding_provider="OpenAI",
                    embedding_model="text-embedding-3-small",
                    cursor_id=None,
                    task_job_id=uuid.uuid4(),
                    job_service=MagicMock(),
                ),
            )

        assert result == {"message": "No non-empty messages to ingest", "ingested": 0}

    @pytest.mark.asyncio
    async def test_mark_messages_ingested_called_on_success(self, tmp_path):
        """_mark_messages_ingested must be called exactly once on a successful run."""
        from langflow.services.memory_base.task import IngestionRequest, ingest_memory_task

        flow_id = uuid.uuid4()
        msg = _make_message(flow_id=flow_id)

        mark_ingested_mock = AsyncMock()

        with (
            patch(
                "langflow.services.memory_base.task._acquire_session_lock",
                AsyncMock(return_value=asyncio.Lock()),
            ),
            patch("langflow.services.memory_base.task._release_session_lock", AsyncMock()),
            patch("langflow.services.memory_base.task._read_live_cursor", AsyncMock(return_value=None)),
            patch(
                "langflow.services.memory_base.task._fetch_pending_messages",
                AsyncMock(return_value=[msg]),
            ),
            patch(
                "langflow.services.memory_base.task.build_documents_from_messages",
                return_value=[MagicMock()],
            ),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.is_job_cancelled",
                AsyncMock(return_value=False),
            ),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.build_embeddings",
                AsyncMock(return_value=MagicMock()),
            ),
            patch(
                "langflow.services.memory_base.task.KBStorageHelper.get_fresh_chroma_client",
                return_value=MagicMock(),
            ),
            patch("langflow.services.memory_base.task.Chroma"),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.write_documents_to_chroma",
                AsyncMock(return_value=1),
            ),
            patch("langflow.services.memory_base.task.sync_kb_metadata"),
            patch("langflow.services.memory_base.task._mark_messages_ingested", mark_ingested_mock),
            patch("langflow.services.memory_base.task._advance_cursor", AsyncMock()),
            patch(
                "langflow.services.memory_base.task.KBStorageHelper.get_root_path",
                return_value=tmp_path,
            ),
            patch("langflow.services.memory_base.task.KBStorageHelper.release_chroma_resources"),
        ):
            await ingest_memory_task(
                request=IngestionRequest(
                    memory_base_id=uuid.uuid4(),
                    session_id="s1",
                    flow_id=flow_id,
                    kb_name="kb",
                    kb_username="user",
                    user_id=uuid.uuid4(),
                    embedding_provider="OpenAI",
                    embedding_model="text-embedding-3-small",
                    cursor_id=None,
                    task_job_id=uuid.uuid4(),
                    job_service=MagicMock(),
                ),
            )

        mark_ingested_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_mark_messages_ingested_not_called_when_cancelled(self, tmp_path):
        """When write returns fewer docs than sent, messages must NOT be stamped."""
        from langflow.services.memory_base.task import IngestionRequest, ingest_memory_task

        flow_id = uuid.uuid4()
        msg = _make_message(flow_id=flow_id)

        mark_ingested_mock = AsyncMock()

        with (
            patch(
                "langflow.services.memory_base.task._acquire_session_lock",
                AsyncMock(return_value=asyncio.Lock()),
            ),
            patch("langflow.services.memory_base.task._release_session_lock", AsyncMock()),
            patch("langflow.services.memory_base.task._read_live_cursor", AsyncMock(return_value=None)),
            patch(
                "langflow.services.memory_base.task._fetch_pending_messages",
                AsyncMock(return_value=[msg]),
            ),
            patch(
                "langflow.services.memory_base.task.build_documents_from_messages",
                return_value=[MagicMock()],
            ),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.is_job_cancelled",
                AsyncMock(return_value=False),
            ),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.build_embeddings",
                AsyncMock(return_value=MagicMock()),
            ),
            patch(
                "langflow.services.memory_base.task.KBStorageHelper.get_fresh_chroma_client",
                return_value=MagicMock(),
            ),
            patch("langflow.services.memory_base.task.Chroma"),
            # Partial write simulates mid-run cancellation
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.write_documents_to_chroma",
                AsyncMock(return_value=0),
            ),
            patch("langflow.services.memory_base.task.sync_kb_metadata"),
            patch("langflow.services.memory_base.task._mark_messages_ingested", mark_ingested_mock),
            patch("langflow.services.memory_base.task._advance_cursor", AsyncMock()),
            patch(
                "langflow.services.memory_base.task.KBStorageHelper.get_root_path",
                return_value=tmp_path,
            ),
            patch("langflow.services.memory_base.task.KBStorageHelper.release_chroma_resources"),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.cleanup_chroma_chunks_by_job",
                AsyncMock(),
            ) as cleanup_mock,
        ):
            result = await ingest_memory_task(
                request=IngestionRequest(
                    memory_base_id=uuid.uuid4(),
                    session_id="s1",
                    flow_id=flow_id,
                    kb_name="kb",
                    kb_username="user",
                    user_id=uuid.uuid4(),
                    embedding_provider="OpenAI",
                    embedding_model="text-embedding-3-small",
                    cursor_id=None,
                    task_job_id=uuid.uuid4(),
                    job_service=MagicMock(),
                ),
            )

        mark_ingested_mock.assert_not_awaited()
        assert "cancelled" in result["message"].lower()
        cleanup_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cleanup_called_on_write_exception(self, tmp_path):
        """When write_documents_to_chroma raises, partial chunks must be cleaned up."""
        from langflow.services.memory_base.task import IngestionRequest, ingest_memory_task

        flow_id = uuid.uuid4()
        msg = _make_message(flow_id=flow_id)

        with (
            patch(
                "langflow.services.memory_base.task._acquire_session_lock",
                AsyncMock(return_value=asyncio.Lock()),
            ),
            patch("langflow.services.memory_base.task._release_session_lock", AsyncMock()),
            patch("langflow.services.memory_base.task._read_live_cursor", AsyncMock(return_value=None)),
            patch(
                "langflow.services.memory_base.task._fetch_pending_messages",
                AsyncMock(return_value=[msg]),
            ),
            patch(
                "langflow.services.memory_base.task.build_documents_from_messages",
                return_value=[MagicMock()],
            ),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.is_job_cancelled",
                AsyncMock(return_value=False),
            ),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.build_embeddings",
                AsyncMock(return_value=MagicMock()),
            ),
            patch(
                "langflow.services.memory_base.task.KBStorageHelper.get_fresh_chroma_client",
                return_value=MagicMock(),
            ),
            patch("langflow.services.memory_base.task.Chroma"),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.write_documents_to_chroma",
                AsyncMock(side_effect=RuntimeError("Chroma write failed")),
            ),
            patch(
                "langflow.services.memory_base.task.KBStorageHelper.get_root_path",
                return_value=tmp_path,
            ),
            patch("langflow.services.memory_base.task.KBStorageHelper.release_chroma_resources"),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.cleanup_chroma_chunks_by_job",
                AsyncMock(),
            ) as cleanup_mock,
            pytest.raises(RuntimeError, match="Chroma write failed"),
        ):
            await ingest_memory_task(
                request=IngestionRequest(
                    memory_base_id=uuid.uuid4(),
                    session_id="s1",
                    flow_id=flow_id,
                    kb_name="kb",
                    kb_username="user",
                    user_id=uuid.uuid4(),
                    embedding_provider="OpenAI",
                    embedding_model="text-embedding-3-small",
                    cursor_id=None,
                    task_job_id=uuid.uuid4(),
                    job_service=MagicMock(),
                ),
            )

        cleanup_mock.assert_awaited_once()


# ------------------------------------------------------------------ #
#  extract_content_block_text                                         #
# ------------------------------------------------------------------ #


class TestExtractContentBlockText:
    def _call(self, blocks):
        from langflow.services.memory_base.document_builders import extract_content_block_text

        return extract_content_block_text(blocks)

    def test_empty_list_returns_empty_string(self):
        assert self._call([]) == ""

    def test_text_block_extracted(self):
        blocks = [{"contents": [{"type": "text", "text": "hello world"}]}]
        result = self._call(blocks)
        assert result == "hello world"

    def test_text_block_whitespace_only_skipped(self):
        blocks = [{"contents": [{"type": "text", "text": "   "}]}]
        result = self._call(blocks)
        assert result == ""

    def test_code_block_with_language(self):
        blocks = [{"contents": [{"type": "code", "language": "python", "code": "print('hi')"}]}]
        result = self._call(blocks)
        assert result == "```python\nprint('hi')\n```"

    def test_code_block_without_language(self):
        blocks = [{"contents": [{"type": "code", "language": "", "code": "x = 1"}]}]
        result = self._call(blocks)
        assert result == "```\nx = 1\n```"

    def test_code_block_empty_code_skipped(self):
        blocks = [{"contents": [{"type": "code", "language": "python", "code": ""}]}]
        result = self._call(blocks)
        assert result == ""

    def test_json_block_serialized(self):
        data = {"key": "value", "num": 42}
        blocks = [{"contents": [{"type": "json", "data": data}]}]
        result = self._call(blocks)
        assert result == json.dumps(data, ensure_ascii=False)

    def test_json_block_none_data_skipped(self):
        blocks = [{"contents": [{"type": "json", "data": None}]}]
        result = self._call(blocks)
        assert result == ""

    def test_unknown_block_type_skipped(self):
        blocks = [
            {
                "contents": [
                    {"type": "tool_use", "tool": "search"},
                    {"type": "error", "message": "failed"},
                    {"type": "media", "url": "http://x.com/img.png"},
                    {"type": "text", "text": "kept"},
                ]
            }
        ]
        result = self._call(blocks)
        assert result == "kept"

    def test_non_dict_entry_skipped(self):
        # entries that aren't dicts should be silently skipped
        blocks = [{"contents": ["not a dict", 42, None, {"type": "text", "text": "ok"}]}]
        result = self._call(blocks)
        assert result == "ok"

    def test_non_dict_block_skipped(self):
        # top-level block that isn't a dict
        blocks = ["string block", {"contents": [{"type": "text", "text": "valid"}]}]
        result = self._call(blocks)
        assert result == "valid"

    def test_multiple_blocks_joined_with_double_newline(self):
        blocks = [
            {"contents": [{"type": "text", "text": "first"}]},
            {"contents": [{"type": "text", "text": "second"}]},
        ]
        result = self._call(blocks)
        assert result == "first\n\nsecond"

    def test_multiple_entries_in_same_block_joined(self):
        blocks = [
            {
                "contents": [
                    {"type": "text", "text": "a"},
                    {"type": "text", "text": "b"},
                ]
            }
        ]
        result = self._call(blocks)
        assert result == "a\n\nb"


# ------------------------------------------------------------------ #
#  build_documents_from_messages                                      #
# ------------------------------------------------------------------ #


class TestBuildDocumentsFromMessages:
    def _call(self, messages, *, session_id="s1", flow_id=None, job_id="test-job-id"):
        from langflow.services.memory_base.document_builders import build_documents_from_messages

        return build_documents_from_messages(
            messages,
            session_id=session_id,
            flow_id=flow_id or str(uuid.uuid4()),
            job_id=job_id,
        )

    def test_content_blocks_contribute_to_doc_text(self):
        flow_id = uuid.uuid4()
        msg = _make_message(
            flow_id=flow_id,
            text="",
            content_blocks=[{"contents": [{"type": "text", "text": "from block"}]}],
        )
        docs = self._call([msg], flow_id=str(flow_id))
        assert len(docs) == 1
        assert "from block" in docs[0].page_content

    def test_text_and_content_blocks_combined(self):
        flow_id = uuid.uuid4()
        msg = _make_message(
            flow_id=flow_id,
            text="msg text",
            content_blocks=[{"contents": [{"type": "text", "text": "block text"}]}],
        )
        docs = self._call([msg], flow_id=str(flow_id))
        assert len(docs) == 1
        assert "msg text" in docs[0].page_content
        assert "block text" in docs[0].page_content

    def test_long_message_split_into_multiple_chunks(self):
        from langflow.services.memory_base.document_builders import MESSAGE_CHUNK_SIZE

        flow_id = uuid.uuid4()
        # Craft text longer than chunk size
        long_text = "x " * (MESSAGE_CHUNK_SIZE + 100)
        msg = _make_message(flow_id=flow_id, text=long_text)
        docs = self._call([msg], flow_id=str(flow_id))
        assert len(docs) > 1

    def test_chunk_index_and_total_chunks_metadata(self):
        from langflow.services.memory_base.document_builders import MESSAGE_CHUNK_SIZE

        flow_id = uuid.uuid4()
        long_text = "word " * (MESSAGE_CHUNK_SIZE // 4)
        msg = _make_message(flow_id=flow_id, text=long_text)
        docs = self._call([msg], flow_id=str(flow_id))
        for i, doc in enumerate(docs):
            assert doc.metadata["chunk_index"] == i
            assert doc.metadata["total_chunks"] == len(docs)

    def test_missing_run_id_stored_as_empty_string(self):
        flow_id = uuid.uuid4()
        msg = _make_message(flow_id=flow_id, run_id=None)
        docs = self._call([msg], flow_id=str(flow_id))
        assert docs[0].metadata["run_id"] == ""

    def test_run_id_stored_as_string(self):
        flow_id = uuid.uuid4()
        run_id = uuid.uuid4()
        msg = _make_message(flow_id=flow_id, run_id=run_id)
        docs = self._call([msg], flow_id=str(flow_id))
        assert docs[0].metadata["run_id"] == str(run_id)

    def test_missing_timestamp_stored_as_empty_string(self):
        flow_id = uuid.uuid4()
        msg = _make_message(flow_id=flow_id)
        # validate_assignment=True on the model prevents setting timestamp=None
        # directly, so bypass Pydantic validation via object.__setattr__.
        object.__setattr__(msg, "timestamp", None)
        docs = self._call([msg], flow_id=str(flow_id))
        assert docs[0].metadata["timestamp"] == ""

    def test_source_metadata_uses_session_id(self):
        flow_id = uuid.uuid4()
        msg = _make_message(flow_id=flow_id, session_id="my-session")
        docs = self._call([msg], session_id="my-session", flow_id=str(flow_id))
        assert docs[0].metadata["source"] == "memory_base/my-session"

    def test_job_id_included_in_metadata(self):
        flow_id = uuid.uuid4()
        job_id = str(uuid.uuid4())
        msg = _make_message(flow_id=flow_id)
        docs = self._call([msg], flow_id=str(flow_id), job_id=job_id)
        assert docs[0].metadata["job_id"] == job_id

    def test_job_id_defaults_to_empty_string(self):
        flow_id = uuid.uuid4()
        msg = _make_message(flow_id=flow_id)
        docs = self._call([msg], flow_id=str(flow_id), job_id="")
        assert docs[0].metadata["job_id"] == ""

    def test_multiple_messages_produce_separate_docs(self):
        flow_id = uuid.uuid4()
        msgs = [_make_message(flow_id=flow_id, text=f"msg {i}") for i in range(3)]
        docs = self._call(msgs, flow_id=str(flow_id))
        assert len(docs) == 3
        message_ids = [d.metadata["message_id"] for d in docs]
        assert len(set(message_ids)) == 3


# ------------------------------------------------------------------ #
#  sync_kb_metadata                                                   #
# ------------------------------------------------------------------ #


class TestSyncKbMetadata:
    def test_preserves_existing_source_types(self, tmp_path):
        from langflow.services.memory_base.document_builders import sync_kb_metadata as _sync_kb_metadata

        kb_path = tmp_path / "kb"
        kb_path.mkdir()

        with (
            patch(
                "langflow.services.memory_base.document_builders.KBAnalysisHelper.get_metadata",
                return_value={"chunks": 5, "source_types": ["file"]},
            ),
            patch("langflow.services.memory_base.document_builders.KBAnalysisHelper.update_text_metrics"),
            patch(
                "langflow.services.memory_base.document_builders.KBStorageHelper.get_directory_size", return_value=2048
            ),
        ):
            _sync_kb_metadata(kb_path=kb_path, chroma=MagicMock())

        written = json.loads((kb_path / "embedding_metadata.json").read_text())
        assert "file" in written["source_types"]
        assert "memory" in written["source_types"]

    def test_source_types_sorted(self, tmp_path):
        from langflow.services.memory_base.document_builders import sync_kb_metadata as _sync_kb_metadata

        kb_path = tmp_path / "kb"
        kb_path.mkdir()

        with (
            patch(
                "langflow.services.memory_base.document_builders.KBAnalysisHelper.get_metadata",
                return_value={"chunks": 0, "source_types": ["zzz", "aaa"]},
            ),
            patch("langflow.services.memory_base.document_builders.KBAnalysisHelper.update_text_metrics"),
            patch("langflow.services.memory_base.document_builders.KBStorageHelper.get_directory_size", return_value=0),
        ):
            _sync_kb_metadata(kb_path=kb_path, chroma=MagicMock())

        written = json.loads((kb_path / "embedding_metadata.json").read_text())
        assert written["source_types"] == sorted(written["source_types"])

    def test_json_decode_error_swallowed(self, tmp_path):
        from langflow.services.memory_base.document_builders import sync_kb_metadata as _sync_kb_metadata

        kb_path = tmp_path / "kb"
        kb_path.mkdir()

        with patch(
            "langflow.services.memory_base.document_builders.KBAnalysisHelper.get_metadata",
            side_effect=json.JSONDecodeError("bad", "", 0),
        ):
            # Must not raise
            _sync_kb_metadata(kb_path=kb_path, chroma=MagicMock())

    def test_value_error_swallowed(self, tmp_path):
        from langflow.services.memory_base.document_builders import sync_kb_metadata as _sync_kb_metadata

        kb_path = tmp_path / "kb"
        kb_path.mkdir()

        with (
            patch(
                "langflow.services.memory_base.document_builders.KBAnalysisHelper.get_metadata",
                return_value={},
            ),
            patch(
                "langflow.services.memory_base.document_builders.KBAnalysisHelper.update_text_metrics",
                side_effect=ValueError("bad metric"),
            ),
        ):
            _sync_kb_metadata(kb_path=kb_path, chroma=MagicMock())


# ------------------------------------------------------------------ #
#  _advance_cursor                                                     #
# ------------------------------------------------------------------ #


class TestAdvanceCursor:
    @pytest.mark.asyncio
    async def test_normal_update(self):
        from langflow.services.database.models.memory_base.model import MemoryBaseSession
        from langflow.services.memory_base.task import _advance_cursor

        mb_id = uuid.uuid4()
        new_cursor = uuid.uuid4()
        task_job_id = uuid.uuid4()

        mbs = MemoryBaseSession(
            id=uuid.uuid4(),
            memory_base_id=mb_id,
            session_id="s1",
            cursor_id=None,
            total_processed=5,
        )

        mock_db = AsyncMock()
        mock_select_result = MagicMock()
        mock_select_result.first = MagicMock(return_value=mbs)
        # First exec = SELECT, second exec = UPDATE MemoryBaseWorkflowRun
        mock_db.exec = AsyncMock(side_effect=[mock_select_result, MagicMock()])

        await _advance_cursor(
            mock_db,
            memory_base_id=mb_id,
            session_id="s1",
            new_cursor_id=new_cursor,
            ingested_count=3,
            task_job_id=task_job_id,
        )

        assert mbs.cursor_id == new_cursor
        assert mbs.total_processed == 8  # 5 + 3
        assert mbs.last_sync_at is not None
        mock_db.add.assert_called_once_with(mbs)
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_vanished_session_does_not_raise(self):
        """If MemoryBaseSession is gone, _advance_cursor must log a warning and return."""
        from langflow.services.memory_base.task import _advance_cursor

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.first = MagicMock(return_value=None)  # session vanished
        mock_db.exec = AsyncMock(return_value=mock_result)

        await _advance_cursor(
            mock_db,
            memory_base_id=uuid.uuid4(),
            session_id="gone",
            new_cursor_id=uuid.uuid4(),
            ingested_count=1,
            task_job_id=uuid.uuid4(),
        )

        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_awaited()


# ------------------------------------------------------------------ #
#  _mark_messages_ingested                                            #
# ------------------------------------------------------------------ #


class TestMarkMessagesIngested:
    @pytest.mark.asyncio
    async def test_executes_bulk_update(self):
        from langflow.services.memory_base.task import _mark_messages_ingested

        flow_id = uuid.uuid4()
        messages = [_make_message(flow_id=flow_id) for _ in range(3)]
        job_id = uuid.uuid4()
        memory_base_id = uuid.uuid4()

        mock_conn = MagicMock()
        mock_conn.dialect.name = "sqlite"

        mock_db = AsyncMock()
        mock_db.exec = AsyncMock()
        mock_db.connection = AsyncMock(return_value=mock_conn)

        await _mark_messages_ingested(mock_db, messages=messages, job_id=job_id, memory_base_id=memory_base_id)

        mock_db.exec.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_sets_ingestion_job_id_and_timestamp(self):
        """The INSERT statement must include job_id and ingested_at for each message."""
        from langflow.services.memory_base.task import _mark_messages_ingested

        flow_id = uuid.uuid4()
        messages = [_make_message(flow_id=flow_id)]
        job_id = uuid.uuid4()
        memory_base_id = uuid.uuid4()

        captured_stmt = {}

        mock_conn = MagicMock()
        mock_conn.dialect.name = "sqlite"

        async def capture_exec(stmt):
            captured_stmt["stmt"] = stmt
            return MagicMock()

        mock_db = AsyncMock()
        mock_db.exec = capture_exec
        mock_db.connection = AsyncMock(return_value=mock_conn)

        await _mark_messages_ingested(mock_db, messages=messages, job_id=job_id, memory_base_id=memory_base_id)

        assert "stmt" in captured_stmt, "db.exec was not called"
        stmt = captured_stmt["stmt"]
        # The INSERT statement must reference job_id and ingested_at columns
        stmt_str = str(stmt.compile())
        assert "job_id" in stmt_str
        assert "ingested_at" in stmt_str


# ------------------------------------------------------------------ #
#  TestIngestionLocking — serialization and cursor re-read           #
# ------------------------------------------------------------------ #


class TestIngestionLocking:
    """Tests for the per-session lock, live cursor re-read, and graceful early-exits."""

    _BASE_KWARGS: dict = {
        "session_id": "s1",
        "kb_name": "kb",
        "kb_username": "user",
        "embedding_provider": "OpenAI",
        "embedding_model": "text-embedding-3-small",
    }

    @pytest.mark.asyncio
    async def test_live_cursor_used_not_dispatch_snapshot(self, tmp_path):
        """_fetch_pending_messages must receive the live cursor, not the dispatch-time one."""
        import langflow.services.memory_base.task as task_module

        memory_base_id = uuid.uuid4()
        flow_id = uuid.uuid4()
        dispatch_cursor = uuid.uuid4()  # what was captured at dispatch time
        live_cursor = uuid.uuid4()  # what the DB currently says

        fetch_calls: list = []

        async def _recording_fetch(db, *, flow_id, session_id, cursor_id):  # noqa: ARG001
            fetch_calls.append(cursor_id)
            return []  # empty → early exit; no Chroma setup needed

        task_module._session_ingestion_locks.pop((memory_base_id, "s1"), None)

        with (
            patch(
                "langflow.services.memory_base.task.KBStorageHelper.get_root_path",
                return_value=tmp_path,
            ),
            patch(
                "langflow.services.memory_base.task._read_live_cursor",
                AsyncMock(return_value=live_cursor),
            ),
            patch(
                "langflow.services.memory_base.task._fetch_pending_messages",
                side_effect=_recording_fetch,
            ),
        ):
            result = await task_module.ingest_memory_task(
                request=task_module.IngestionRequest(
                    memory_base_id=memory_base_id,
                    flow_id=flow_id,
                    user_id=uuid.uuid4(),
                    cursor_id=dispatch_cursor,
                    task_job_id=uuid.uuid4(),
                    job_service=MagicMock(),
                    **self._BASE_KWARGS,
                ),
            )

        assert result == {"message": "No pending messages", "ingested": 0}
        assert len(fetch_calls) == 1
        assert fetch_calls[0] == live_cursor, (
            f"Expected fetch called with live_cursor={live_cursor!r}, got {fetch_calls[0]!r}"
        )

    @pytest.mark.asyncio
    async def test_lock_released_on_task_exception(self, tmp_path):
        """Lock must be released via finally even when the task raises inside the lock body."""
        import langflow.services.memory_base.task as task_module

        memory_base_id = uuid.uuid4()

        task_module._session_ingestion_locks.pop((memory_base_id, "s1"), None)

        with (
            patch(
                "langflow.services.memory_base.task.KBStorageHelper.get_root_path",
                return_value=tmp_path,
            ),
            patch(
                "langflow.services.memory_base.task._read_live_cursor",
                AsyncMock(return_value=None),
            ),
            patch(
                "langflow.services.memory_base.task._fetch_pending_messages",
                AsyncMock(side_effect=RuntimeError("DB exploded inside lock")),
            ),
            pytest.raises(RuntimeError, match="DB exploded inside lock"),
        ):
            await task_module.ingest_memory_task(
                request=task_module.IngestionRequest(
                    memory_base_id=memory_base_id,
                    flow_id=uuid.uuid4(),
                    user_id=uuid.uuid4(),
                    cursor_id=None,
                    task_job_id=uuid.uuid4(),
                    job_service=MagicMock(),
                    **self._BASE_KWARGS,
                ),
            )

        lock = task_module._session_ingestion_locks[(memory_base_id, "s1")]
        assert not lock.locked(), "Lock must be released after exception (finally block must have run)"

    @pytest.mark.asyncio
    async def test_lock_timeout_raises_asyncio_timeout_error(self, tmp_path):
        """When the lock cannot be acquired within the timeout, asyncio.TimeoutError is raised.

        This allows execute_with_status to record JobStatus.TIMED_OUT for an accurate audit trail.
        """
        import langflow.services.memory_base.task as task_module

        memory_base_id = uuid.uuid4()

        task_module._session_ingestion_locks.pop((memory_base_id, "s1"), None)
        # Use the factory so the lock is inserted into the WeakValueDictionary;
        # holding blocking_lock as a strong reference keeps it alive there so the
        # task finds the same lock object and blocks on acquire.
        blocking_lock = task_module._get_or_create_session_lock((memory_base_id, "s1"))
        await blocking_lock.acquire()  # hold it — task will timeout waiting

        try:
            with (
                patch(
                    "langflow.services.memory_base.task.KBStorageHelper.get_root_path",
                    return_value=tmp_path,
                ),
                patch(
                    "langflow.services.memory_base.task.get_settings_service",
                    return_value=MagicMock(settings=MagicMock(max_ingestion_timeout_secs=0.01)),
                ),
                pytest.raises(asyncio.TimeoutError),
            ):
                await task_module.ingest_memory_task(
                    request=task_module.IngestionRequest(
                        memory_base_id=memory_base_id,
                        flow_id=uuid.uuid4(),
                        user_id=uuid.uuid4(),
                        cursor_id=None,
                        task_job_id=uuid.uuid4(),
                        job_service=MagicMock(),
                        **self._BASE_KWARGS,
                    ),
                )
        finally:
            blocking_lock.release()

    @pytest.mark.asyncio
    async def test_noop_when_cursor_advanced_by_prior_job(self, tmp_path):
        """If a prior job already advanced the cursor to msg3, fetch from msg3 finds nothing — graceful exit."""
        import langflow.services.memory_base.task as task_module

        memory_base_id = uuid.uuid4()
        msg3_id = uuid.uuid4()

        advance_cursor_mock = AsyncMock()

        task_module._session_ingestion_locks.pop((memory_base_id, "s1"), None)

        with (
            patch(
                "langflow.services.memory_base.task.KBStorageHelper.get_root_path",
                return_value=tmp_path,
            ),
            patch(
                "langflow.services.memory_base.task._read_live_cursor",
                AsyncMock(return_value=msg3_id),  # prior job advanced to msg3
            ),
            patch(
                "langflow.services.memory_base.task._fetch_pending_messages",
                AsyncMock(return_value=[]),  # nothing after msg3
            ),
            patch(
                "langflow.services.memory_base.task._advance_cursor",
                advance_cursor_mock,
            ),
        ):
            result = await task_module.ingest_memory_task(
                request=task_module.IngestionRequest(
                    memory_base_id=memory_base_id,
                    flow_id=uuid.uuid4(),
                    user_id=uuid.uuid4(),
                    cursor_id=None,  # dispatch-time snapshot before prior job ran
                    task_job_id=uuid.uuid4(),
                    job_service=MagicMock(),
                    **self._BASE_KWARGS,
                ),
            )

        assert result == {"message": "No pending messages", "ingested": 0}
        advance_cursor_mock.assert_not_awaited()


# ------------------------------------------------------------------ #
#  build_preprocessed_document                                        #
# ------------------------------------------------------------------ #


class TestBuildPreprocessedDocument:
    def _call(
        self,
        output_text: str = "Summary text about the conversation.",
        source_message_ids: list | None = None,
        session_id: str = "s1",
        flow_id: str | None = None,
        job_id: str = "job-1",
        preproc_output_id: str = "preproc-1",
    ):
        from langflow.services.memory_base.document_builders import build_preprocessed_document

        return build_preprocessed_document(
            output_text=output_text,
            source_message_ids=source_message_ids or ["id1", "id2"],
            session_id=session_id,
            flow_id=flow_id or str(uuid.uuid4()),
            job_id=job_id,
            preproc_output_id=preproc_output_id,
        )

    def test_empty_output_text_returns_empty_list(self):
        assert self._call(output_text="") == []

    def test_whitespace_only_output_returns_empty_list(self):
        assert self._call(output_text="   ") == []

    def test_normal_text_returns_documents(self):
        docs = self._call()
        assert len(docs) >= 1

    def test_preprocessed_flag_true_in_metadata(self):
        docs = self._call()
        assert docs[0].metadata["preprocessed"] is True

    def test_preproc_output_id_in_metadata(self):
        docs = self._call(preproc_output_id="abc-123")
        assert docs[0].metadata["preproc_output_id"] == "abc-123"

    def test_source_message_ids_comma_joined_in_metadata(self):
        docs = self._call(source_message_ids=["id1", "id2"])
        assert docs[0].metadata["source_message_ids"] == "id1,id2"

    def test_single_source_id_not_mangled(self):
        docs = self._call(source_message_ids=["only-id"])
        assert docs[0].metadata["source_message_ids"] == "only-id"

    def test_session_id_in_metadata(self):
        docs = self._call(session_id="my-session")
        assert docs[0].metadata["session_id"] == "my-session"

    def test_source_is_memory_base_session(self):
        docs = self._call(session_id="my-sess")
        assert docs[0].metadata["source"] == "memory_base/my-sess"

    def test_job_id_in_metadata(self):
        docs = self._call(job_id="job-xyz")
        assert docs[0].metadata["job_id"] == "job-xyz"

    def test_sender_is_machine(self):
        docs = self._call()
        assert docs[0].metadata["sender"] == "Machine"

    def test_sender_name_is_preprocessor(self):
        docs = self._call()
        assert docs[0].metadata["sender_name"] == "Preprocessor"

    def test_long_text_produces_multiple_chunks(self):
        from langflow.services.memory_base.document_builders import MESSAGE_CHUNK_SIZE

        long_text = "word " * (MESSAGE_CHUNK_SIZE + 100)
        docs = self._call(output_text=long_text)
        assert len(docs) > 1

    def test_chunk_index_and_total_chunks_correct_for_multi_chunk(self):
        from langflow.services.memory_base.document_builders import MESSAGE_CHUNK_SIZE

        long_text = "word " * (MESSAGE_CHUNK_SIZE + 100)
        docs = self._call(output_text=long_text)
        for i, doc in enumerate(docs):
            assert doc.metadata["chunk_index"] == i
            assert doc.metadata["total_chunks"] == len(docs)

    def test_flow_id_in_metadata(self):
        flow_id = str(uuid.uuid4())
        docs = self._call(flow_id=flow_id)
        assert docs[0].metadata["flow_id"] == flow_id

    def test_timestamp_and_run_id_are_empty_strings(self):
        docs = self._call()
        assert docs[0].metadata["timestamp"] == ""
        assert docs[0].metadata["run_id"] == ""


# ------------------------------------------------------------------ #
#  ingest_memory_task — preprocessing path                           #
# ------------------------------------------------------------------ #


class TestIngestMemoryTaskPreprocessing:
    """Tests for the preprocessing=True branch of ingest_memory_task."""

    def _make_request(self, flow_id, memory_base_id=None, **kwargs):
        from langflow.services.memory_base.task import IngestionRequest

        defaults = {
            "memory_base_id": memory_base_id or uuid.uuid4(),
            "session_id": "s1",
            "flow_id": flow_id,
            "kb_name": "kb",
            "kb_username": "user",
            "user_id": uuid.uuid4(),
            "embedding_provider": "OpenAI",
            "embedding_model": "text-embedding-3-small",
            "cursor_id": None,
            "task_job_id": uuid.uuid4(),
            "job_service": MagicMock(),
            "preprocessing": True,
            "preproc_model": "gpt-4o-mini",
            "preproc_instructions": "Summarize.",
            "preproc_kill_phrase": "NO_INGEST",
        }
        defaults.update(kwargs)
        return IngestionRequest(**defaults)

    def _make_preproc_row_mock(self, source_ids=None, output_text="Cached LLM output"):
        row = MagicMock()
        row.id = uuid.uuid4()
        row.source_message_ids = source_ids or []
        row.output_text = output_text
        row.status = "processed"
        return row

    @pytest.mark.asyncio
    async def test_kill_phrase_result_skips_chroma_write(self, tmp_path):
        from langflow.services.memory_base.preprocessing import PreprocessingResult
        from langflow.services.memory_base.task import ingest_memory_task

        flow_id = uuid.uuid4()
        msg = _make_message(flow_id=flow_id)
        kill_result = PreprocessingResult(status="skipped", output_text="", raw_response="NO_INGEST")

        with (
            patch("langflow.services.memory_base.task.KBStorageHelper.get_root_path", return_value=tmp_path),
            patch("langflow.services.memory_base.task._acquire_session_lock", AsyncMock(return_value=asyncio.Lock())),
            patch("langflow.services.memory_base.task._release_session_lock", AsyncMock()),
            patch("langflow.services.memory_base.task._read_live_cursor", AsyncMock(return_value=None)),
            patch("langflow.services.memory_base.task._fetch_pending_messages", AsyncMock(return_value=[msg])),
            patch("langflow.services.memory_base.task._get_pending_preproc_row", AsyncMock(return_value=None)),
            patch("langflow.services.memory_base.task.run_preprocessing", AsyncMock(return_value=kill_result)),
            patch("langflow.services.memory_base.task._insert_preproc_row", AsyncMock(return_value=MagicMock())),
            patch("langflow.services.memory_base.task._mark_messages_ingested", AsyncMock()),
            patch("langflow.services.memory_base.task._advance_cursor", AsyncMock()),
        ):
            result = await ingest_memory_task(request=self._make_request(flow_id))

        assert result == {"message": "Skipped by kill phrase", "ingested": 0, "skipped": True}

    @pytest.mark.asyncio
    async def test_kill_phrase_inserts_skipped_preproc_row(self, tmp_path):
        from langflow.services.memory_base.preprocessing import PreprocessingResult
        from langflow.services.memory_base.task import ingest_memory_task

        flow_id = uuid.uuid4()
        msg = _make_message(flow_id=flow_id)
        kill_result = PreprocessingResult(status="skipped", output_text="", raw_response="NO_INGEST")
        insert_mock = AsyncMock(return_value=MagicMock())

        with (
            patch("langflow.services.memory_base.task.KBStorageHelper.get_root_path", return_value=tmp_path),
            patch("langflow.services.memory_base.task._acquire_session_lock", AsyncMock(return_value=asyncio.Lock())),
            patch("langflow.services.memory_base.task._release_session_lock", AsyncMock()),
            patch("langflow.services.memory_base.task._read_live_cursor", AsyncMock(return_value=None)),
            patch("langflow.services.memory_base.task._fetch_pending_messages", AsyncMock(return_value=[msg])),
            patch("langflow.services.memory_base.task._get_pending_preproc_row", AsyncMock(return_value=None)),
            patch("langflow.services.memory_base.task.run_preprocessing", AsyncMock(return_value=kill_result)),
            patch("langflow.services.memory_base.task._insert_preproc_row", insert_mock),
            patch("langflow.services.memory_base.task._mark_messages_ingested", AsyncMock()),
            patch("langflow.services.memory_base.task._advance_cursor", AsyncMock()),
        ):
            await ingest_memory_task(request=self._make_request(flow_id))

        insert_mock.assert_awaited_once()
        call_kwargs = insert_mock.call_args.kwargs
        assert call_kwargs["status"] == "skipped"
        assert call_kwargs["output_text"] is None

    @pytest.mark.asyncio
    async def test_kill_phrase_does_not_open_chroma(self, tmp_path):
        from langflow.services.memory_base.preprocessing import PreprocessingResult
        from langflow.services.memory_base.task import ingest_memory_task

        flow_id = uuid.uuid4()
        msg = _make_message(flow_id=flow_id)
        kill_result = PreprocessingResult(status="skipped", output_text="", raw_response="NO_INGEST")
        chroma_client_mock = MagicMock()

        with (
            patch("langflow.services.memory_base.task.KBStorageHelper.get_root_path", return_value=tmp_path),
            patch("langflow.services.memory_base.task._acquire_session_lock", AsyncMock(return_value=asyncio.Lock())),
            patch("langflow.services.memory_base.task._release_session_lock", AsyncMock()),
            patch("langflow.services.memory_base.task._read_live_cursor", AsyncMock(return_value=None)),
            patch("langflow.services.memory_base.task._fetch_pending_messages", AsyncMock(return_value=[msg])),
            patch("langflow.services.memory_base.task._get_pending_preproc_row", AsyncMock(return_value=None)),
            patch("langflow.services.memory_base.task.run_preprocessing", AsyncMock(return_value=kill_result)),
            patch("langflow.services.memory_base.task._insert_preproc_row", AsyncMock(return_value=MagicMock())),
            patch("langflow.services.memory_base.task._mark_messages_ingested", AsyncMock()),
            patch("langflow.services.memory_base.task._advance_cursor", AsyncMock()),
            patch(
                "langflow.services.memory_base.task.KBStorageHelper.get_fresh_chroma_client",
                chroma_client_mock,
            ),
        ):
            await ingest_memory_task(request=self._make_request(flow_id))

        chroma_client_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_kill_phrase_does_not_call_build_preprocessed_document(self, tmp_path):
        from langflow.services.memory_base.preprocessing import PreprocessingResult
        from langflow.services.memory_base.task import ingest_memory_task

        flow_id = uuid.uuid4()
        msg = _make_message(flow_id=flow_id)
        kill_result = PreprocessingResult(status="skipped", output_text="", raw_response="NO_INGEST")
        build_doc_mock = MagicMock(return_value=[MagicMock()])

        with (
            patch("langflow.services.memory_base.task.KBStorageHelper.get_root_path", return_value=tmp_path),
            patch("langflow.services.memory_base.task._acquire_session_lock", AsyncMock(return_value=asyncio.Lock())),
            patch("langflow.services.memory_base.task._release_session_lock", AsyncMock()),
            patch("langflow.services.memory_base.task._read_live_cursor", AsyncMock(return_value=None)),
            patch("langflow.services.memory_base.task._fetch_pending_messages", AsyncMock(return_value=[msg])),
            patch("langflow.services.memory_base.task._get_pending_preproc_row", AsyncMock(return_value=None)),
            patch("langflow.services.memory_base.task.run_preprocessing", AsyncMock(return_value=kill_result)),
            patch("langflow.services.memory_base.task._insert_preproc_row", AsyncMock(return_value=MagicMock())),
            patch("langflow.services.memory_base.task._mark_messages_ingested", AsyncMock()),
            patch("langflow.services.memory_base.task._advance_cursor", AsyncMock()),
            patch("langflow.services.memory_base.task.build_preprocessed_document", build_doc_mock),
        ):
            await ingest_memory_task(request=self._make_request(flow_id))

        build_doc_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_kill_phrase_does_not_call_update_preproc_row_status(self, tmp_path):
        from langflow.services.memory_base.preprocessing import PreprocessingResult
        from langflow.services.memory_base.task import ingest_memory_task

        flow_id = uuid.uuid4()
        msg = _make_message(flow_id=flow_id)
        kill_result = PreprocessingResult(status="skipped", output_text="", raw_response="NO_INGEST")
        update_mock = AsyncMock()

        with (
            patch("langflow.services.memory_base.task.KBStorageHelper.get_root_path", return_value=tmp_path),
            patch("langflow.services.memory_base.task._acquire_session_lock", AsyncMock(return_value=asyncio.Lock())),
            patch("langflow.services.memory_base.task._release_session_lock", AsyncMock()),
            patch("langflow.services.memory_base.task._read_live_cursor", AsyncMock(return_value=None)),
            patch("langflow.services.memory_base.task._fetch_pending_messages", AsyncMock(return_value=[msg])),
            patch("langflow.services.memory_base.task._get_pending_preproc_row", AsyncMock(return_value=None)),
            patch("langflow.services.memory_base.task.run_preprocessing", AsyncMock(return_value=kill_result)),
            patch("langflow.services.memory_base.task._insert_preproc_row", AsyncMock(return_value=MagicMock())),
            patch("langflow.services.memory_base.task._mark_messages_ingested", AsyncMock()),
            patch("langflow.services.memory_base.task._advance_cursor", AsyncMock()),
            patch("langflow.services.memory_base.task._update_preproc_row_status", update_mock),
        ):
            await ingest_memory_task(request=self._make_request(flow_id))

        update_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_kill_phrase_marks_messages_ingested(self, tmp_path):
        from langflow.services.memory_base.preprocessing import PreprocessingResult
        from langflow.services.memory_base.task import ingest_memory_task

        flow_id = uuid.uuid4()
        msg = _make_message(flow_id=flow_id)
        kill_result = PreprocessingResult(status="skipped", output_text="", raw_response="NO_INGEST")
        mark_mock = AsyncMock()

        with (
            patch("langflow.services.memory_base.task.KBStorageHelper.get_root_path", return_value=tmp_path),
            patch("langflow.services.memory_base.task._acquire_session_lock", AsyncMock(return_value=asyncio.Lock())),
            patch("langflow.services.memory_base.task._release_session_lock", AsyncMock()),
            patch("langflow.services.memory_base.task._read_live_cursor", AsyncMock(return_value=None)),
            patch("langflow.services.memory_base.task._fetch_pending_messages", AsyncMock(return_value=[msg])),
            patch("langflow.services.memory_base.task._get_pending_preproc_row", AsyncMock(return_value=None)),
            patch("langflow.services.memory_base.task.run_preprocessing", AsyncMock(return_value=kill_result)),
            patch("langflow.services.memory_base.task._insert_preproc_row", AsyncMock(return_value=MagicMock())),
            patch("langflow.services.memory_base.task._mark_messages_ingested", mark_mock),
            patch("langflow.services.memory_base.task._advance_cursor", AsyncMock()),
        ):
            await ingest_memory_task(request=self._make_request(flow_id))

        mark_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_kill_phrase_advances_cursor(self, tmp_path):
        from langflow.services.memory_base.preprocessing import PreprocessingResult
        from langflow.services.memory_base.task import ingest_memory_task

        flow_id = uuid.uuid4()
        msg = _make_message(flow_id=flow_id)
        kill_result = PreprocessingResult(status="skipped", output_text="", raw_response="NO_INGEST")
        advance_mock = AsyncMock()

        with (
            patch("langflow.services.memory_base.task.KBStorageHelper.get_root_path", return_value=tmp_path),
            patch("langflow.services.memory_base.task._acquire_session_lock", AsyncMock(return_value=asyncio.Lock())),
            patch("langflow.services.memory_base.task._release_session_lock", AsyncMock()),
            patch("langflow.services.memory_base.task._read_live_cursor", AsyncMock(return_value=None)),
            patch("langflow.services.memory_base.task._fetch_pending_messages", AsyncMock(return_value=[msg])),
            patch("langflow.services.memory_base.task._get_pending_preproc_row", AsyncMock(return_value=None)),
            patch("langflow.services.memory_base.task.run_preprocessing", AsyncMock(return_value=kill_result)),
            patch("langflow.services.memory_base.task._insert_preproc_row", AsyncMock(return_value=MagicMock())),
            patch("langflow.services.memory_base.task._mark_messages_ingested", AsyncMock()),
            patch("langflow.services.memory_base.task._advance_cursor", advance_mock),
        ):
            await ingest_memory_task(request=self._make_request(flow_id))

        advance_mock.assert_awaited_once()
        assert advance_mock.call_args.kwargs["new_cursor_id"] == msg.id

    @pytest.mark.asyncio
    async def test_normal_result_ingests_to_chroma(self, tmp_path):
        from langflow.services.memory_base.preprocessing import PreprocessingResult
        from langflow.services.memory_base.task import ingest_memory_task

        flow_id = uuid.uuid4()
        msg = _make_message(flow_id=flow_id)
        ok_result = PreprocessingResult(status="ingested", output_text="Summary.", raw_response="Summary.")
        preproc_row = self._make_preproc_row_mock()

        with (
            patch("langflow.services.memory_base.task.KBStorageHelper.get_root_path", return_value=tmp_path),
            patch("langflow.services.memory_base.task._acquire_session_lock", AsyncMock(return_value=asyncio.Lock())),
            patch("langflow.services.memory_base.task._release_session_lock", AsyncMock()),
            patch("langflow.services.memory_base.task._read_live_cursor", AsyncMock(return_value=None)),
            patch("langflow.services.memory_base.task._fetch_pending_messages", AsyncMock(return_value=[msg])),
            patch("langflow.services.memory_base.task._get_pending_preproc_row", AsyncMock(return_value=None)),
            patch("langflow.services.memory_base.task.run_preprocessing", AsyncMock(return_value=ok_result)),
            patch("langflow.services.memory_base.task._insert_preproc_row", AsyncMock(return_value=preproc_row)),
            patch("langflow.services.memory_base.task.build_preprocessed_document", return_value=[MagicMock()]),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.is_job_cancelled",
                AsyncMock(return_value=False),
            ),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.build_embeddings",
                AsyncMock(return_value=MagicMock()),
            ),
            patch(
                "langflow.services.memory_base.task.KBStorageHelper.get_fresh_chroma_client",
                return_value=MagicMock(),
            ),
            patch("langflow.services.memory_base.task.Chroma"),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.write_documents_to_chroma",
                AsyncMock(return_value=1),
            ),
            patch("langflow.services.memory_base.task.sync_kb_metadata"),
            patch("langflow.services.memory_base.task._update_preproc_row_status", AsyncMock()),
            patch("langflow.services.memory_base.task._mark_messages_ingested", AsyncMock()),
            patch("langflow.services.memory_base.task._advance_cursor", AsyncMock()),
            patch("langflow.services.memory_base.task.KBStorageHelper.release_chroma_resources"),
        ):
            result = await ingest_memory_task(request=self._make_request(flow_id))

        assert result == {"message": "Success", "ingested": 1}

    @pytest.mark.asyncio
    async def test_normal_result_inserts_processed_preproc_row(self, tmp_path):
        from langflow.services.memory_base.preprocessing import PreprocessingResult
        from langflow.services.memory_base.task import ingest_memory_task

        flow_id = uuid.uuid4()
        msg = _make_message(flow_id=flow_id)
        ok_result = PreprocessingResult(status="ingested", output_text="Summary.", raw_response="Summary.")
        preproc_row = self._make_preproc_row_mock()
        insert_mock = AsyncMock(return_value=preproc_row)

        with (
            patch("langflow.services.memory_base.task.KBStorageHelper.get_root_path", return_value=tmp_path),
            patch("langflow.services.memory_base.task._acquire_session_lock", AsyncMock(return_value=asyncio.Lock())),
            patch("langflow.services.memory_base.task._release_session_lock", AsyncMock()),
            patch("langflow.services.memory_base.task._read_live_cursor", AsyncMock(return_value=None)),
            patch("langflow.services.memory_base.task._fetch_pending_messages", AsyncMock(return_value=[msg])),
            patch("langflow.services.memory_base.task._get_pending_preproc_row", AsyncMock(return_value=None)),
            patch("langflow.services.memory_base.task.run_preprocessing", AsyncMock(return_value=ok_result)),
            patch("langflow.services.memory_base.task._insert_preproc_row", insert_mock),
            patch("langflow.services.memory_base.task.build_preprocessed_document", return_value=[MagicMock()]),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.is_job_cancelled",
                AsyncMock(return_value=False),
            ),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.build_embeddings",
                AsyncMock(return_value=MagicMock()),
            ),
            patch(
                "langflow.services.memory_base.task.KBStorageHelper.get_fresh_chroma_client",
                return_value=MagicMock(),
            ),
            patch("langflow.services.memory_base.task.Chroma"),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.write_documents_to_chroma",
                AsyncMock(return_value=1),
            ),
            patch("langflow.services.memory_base.task.sync_kb_metadata"),
            patch("langflow.services.memory_base.task._update_preproc_row_status", AsyncMock()),
            patch("langflow.services.memory_base.task._mark_messages_ingested", AsyncMock()),
            patch("langflow.services.memory_base.task._advance_cursor", AsyncMock()),
            patch("langflow.services.memory_base.task.KBStorageHelper.release_chroma_resources"),
        ):
            await ingest_memory_task(request=self._make_request(flow_id))

        insert_mock.assert_awaited_once()
        assert insert_mock.call_args.kwargs["status"] == "processed"

    @pytest.mark.asyncio
    async def test_normal_result_flips_row_to_ingested_after_chroma_write(self, tmp_path):
        from langflow.services.memory_base.preprocessing import PreprocessingResult
        from langflow.services.memory_base.task import ingest_memory_task

        flow_id = uuid.uuid4()
        msg = _make_message(flow_id=flow_id)
        ok_result = PreprocessingResult(status="ingested", output_text="Summary.", raw_response="Summary.")
        preproc_row = self._make_preproc_row_mock()
        update_mock = AsyncMock()

        with (
            patch("langflow.services.memory_base.task.KBStorageHelper.get_root_path", return_value=tmp_path),
            patch("langflow.services.memory_base.task._acquire_session_lock", AsyncMock(return_value=asyncio.Lock())),
            patch("langflow.services.memory_base.task._release_session_lock", AsyncMock()),
            patch("langflow.services.memory_base.task._read_live_cursor", AsyncMock(return_value=None)),
            patch("langflow.services.memory_base.task._fetch_pending_messages", AsyncMock(return_value=[msg])),
            patch("langflow.services.memory_base.task._get_pending_preproc_row", AsyncMock(return_value=None)),
            patch("langflow.services.memory_base.task.run_preprocessing", AsyncMock(return_value=ok_result)),
            patch("langflow.services.memory_base.task._insert_preproc_row", AsyncMock(return_value=preproc_row)),
            patch("langflow.services.memory_base.task.build_preprocessed_document", return_value=[MagicMock()]),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.is_job_cancelled",
                AsyncMock(return_value=False),
            ),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.build_embeddings",
                AsyncMock(return_value=MagicMock()),
            ),
            patch(
                "langflow.services.memory_base.task.KBStorageHelper.get_fresh_chroma_client",
                return_value=MagicMock(),
            ),
            patch("langflow.services.memory_base.task.Chroma"),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.write_documents_to_chroma",
                AsyncMock(return_value=1),
            ),
            patch("langflow.services.memory_base.task.sync_kb_metadata"),
            patch("langflow.services.memory_base.task._update_preproc_row_status", update_mock),
            patch("langflow.services.memory_base.task._mark_messages_ingested", AsyncMock()),
            patch("langflow.services.memory_base.task._advance_cursor", AsyncMock()),
            patch("langflow.services.memory_base.task.KBStorageHelper.release_chroma_resources"),
        ):
            await ingest_memory_task(request=self._make_request(flow_id))

        update_mock.assert_awaited_once()
        assert update_mock.call_args.kwargs["status"] == "ingested"

    @pytest.mark.asyncio
    async def test_normal_result_calls_build_preprocessed_document_with_source_ids(self, tmp_path):
        from langflow.services.memory_base.preprocessing import PreprocessingResult
        from langflow.services.memory_base.task import ingest_memory_task

        flow_id = uuid.uuid4()
        msg = _make_message(flow_id=flow_id)
        ok_result = PreprocessingResult(status="ingested", output_text="Summary.", raw_response="Summary.")
        preproc_row = self._make_preproc_row_mock()
        build_doc_mock = MagicMock(return_value=[MagicMock()])

        with (
            patch("langflow.services.memory_base.task.KBStorageHelper.get_root_path", return_value=tmp_path),
            patch("langflow.services.memory_base.task._acquire_session_lock", AsyncMock(return_value=asyncio.Lock())),
            patch("langflow.services.memory_base.task._release_session_lock", AsyncMock()),
            patch("langflow.services.memory_base.task._read_live_cursor", AsyncMock(return_value=None)),
            patch("langflow.services.memory_base.task._fetch_pending_messages", AsyncMock(return_value=[msg])),
            patch("langflow.services.memory_base.task._get_pending_preproc_row", AsyncMock(return_value=None)),
            patch("langflow.services.memory_base.task.run_preprocessing", AsyncMock(return_value=ok_result)),
            patch("langflow.services.memory_base.task._insert_preproc_row", AsyncMock(return_value=preproc_row)),
            patch("langflow.services.memory_base.task.build_preprocessed_document", build_doc_mock),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.is_job_cancelled",
                AsyncMock(return_value=False),
            ),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.build_embeddings",
                AsyncMock(return_value=MagicMock()),
            ),
            patch(
                "langflow.services.memory_base.task.KBStorageHelper.get_fresh_chroma_client",
                return_value=MagicMock(),
            ),
            patch("langflow.services.memory_base.task.Chroma"),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.write_documents_to_chroma",
                AsyncMock(return_value=1),
            ),
            patch("langflow.services.memory_base.task.sync_kb_metadata"),
            patch("langflow.services.memory_base.task._update_preproc_row_status", AsyncMock()),
            patch("langflow.services.memory_base.task._mark_messages_ingested", AsyncMock()),
            patch("langflow.services.memory_base.task._advance_cursor", AsyncMock()),
            patch("langflow.services.memory_base.task.KBStorageHelper.release_chroma_resources"),
        ):
            await ingest_memory_task(request=self._make_request(flow_id))

        build_doc_mock.assert_called_once()
        call_kwargs = build_doc_mock.call_args.kwargs
        assert str(msg.id) in call_kwargs["source_message_ids"]

    @pytest.mark.asyncio
    async def test_missing_preproc_model_raises_runtime_error(self, tmp_path):
        from langflow.services.memory_base.task import ingest_memory_task

        flow_id = uuid.uuid4()
        msg = _make_message(flow_id=flow_id)

        with (
            patch("langflow.services.memory_base.task.KBStorageHelper.get_root_path", return_value=tmp_path),
            patch("langflow.services.memory_base.task._acquire_session_lock", AsyncMock(return_value=asyncio.Lock())),
            patch("langflow.services.memory_base.task._release_session_lock", AsyncMock()),
            patch("langflow.services.memory_base.task._read_live_cursor", AsyncMock(return_value=None)),
            patch("langflow.services.memory_base.task._fetch_pending_messages", AsyncMock(return_value=[msg])),
            patch("langflow.services.memory_base.task._get_pending_preproc_row", AsyncMock(return_value=None)),
            pytest.raises(RuntimeError, match="preproc_model is not set"),
        ):
            await ingest_memory_task(request=self._make_request(flow_id, preproc_model=None))

    @pytest.mark.asyncio
    async def test_resume_path_skips_llm_call(self, tmp_path):
        from langflow.services.memory_base.preprocessing import PreprocessingResult
        from langflow.services.memory_base.task import ingest_memory_task

        flow_id = uuid.uuid4()
        msg = _make_message(flow_id=flow_id)
        preproc_row = self._make_preproc_row_mock(source_ids=[str(msg.id)])
        run_preproc_mock = AsyncMock(
            return_value=PreprocessingResult(status="ingested", output_text="Cached.", raw_response="Cached.")
        )

        with (
            patch("langflow.services.memory_base.task.KBStorageHelper.get_root_path", return_value=tmp_path),
            patch("langflow.services.memory_base.task._acquire_session_lock", AsyncMock(return_value=asyncio.Lock())),
            patch("langflow.services.memory_base.task._release_session_lock", AsyncMock()),
            patch("langflow.services.memory_base.task._read_live_cursor", AsyncMock(return_value=None)),
            patch("langflow.services.memory_base.task._fetch_pending_messages", AsyncMock(return_value=[msg])),
            patch("langflow.services.memory_base.task._get_pending_preproc_row", AsyncMock(return_value=preproc_row)),
            patch("langflow.services.memory_base.task.run_preprocessing", run_preproc_mock),
            patch("langflow.services.memory_base.task.build_preprocessed_document", return_value=[MagicMock()]),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.is_job_cancelled",
                AsyncMock(return_value=False),
            ),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.build_embeddings",
                AsyncMock(return_value=MagicMock()),
            ),
            patch(
                "langflow.services.memory_base.task.KBStorageHelper.get_fresh_chroma_client",
                return_value=MagicMock(),
            ),
            patch("langflow.services.memory_base.task.Chroma"),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.write_documents_to_chroma",
                AsyncMock(return_value=1),
            ),
            patch("langflow.services.memory_base.task.sync_kb_metadata"),
            patch("langflow.services.memory_base.task._update_preproc_row_status", AsyncMock()),
            patch("langflow.services.memory_base.task._mark_messages_ingested", AsyncMock()),
            patch("langflow.services.memory_base.task._advance_cursor", AsyncMock()),
            patch("langflow.services.memory_base.task.KBStorageHelper.release_chroma_resources"),
        ):
            await ingest_memory_task(request=self._make_request(flow_id))

        run_preproc_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_resume_does_not_call_insert_preproc_row(self, tmp_path):
        from langflow.services.memory_base.task import ingest_memory_task

        flow_id = uuid.uuid4()
        msg = _make_message(flow_id=flow_id)
        preproc_row = self._make_preproc_row_mock(source_ids=[str(msg.id)])
        insert_mock = AsyncMock()

        with (
            patch("langflow.services.memory_base.task.KBStorageHelper.get_root_path", return_value=tmp_path),
            patch("langflow.services.memory_base.task._acquire_session_lock", AsyncMock(return_value=asyncio.Lock())),
            patch("langflow.services.memory_base.task._release_session_lock", AsyncMock()),
            patch("langflow.services.memory_base.task._read_live_cursor", AsyncMock(return_value=None)),
            patch("langflow.services.memory_base.task._fetch_pending_messages", AsyncMock(return_value=[msg])),
            patch("langflow.services.memory_base.task._get_pending_preproc_row", AsyncMock(return_value=preproc_row)),
            patch("langflow.services.memory_base.task._insert_preproc_row", insert_mock),
            patch("langflow.services.memory_base.task.build_preprocessed_document", return_value=[MagicMock()]),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.is_job_cancelled",
                AsyncMock(return_value=False),
            ),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.build_embeddings",
                AsyncMock(return_value=MagicMock()),
            ),
            patch(
                "langflow.services.memory_base.task.KBStorageHelper.get_fresh_chroma_client",
                return_value=MagicMock(),
            ),
            patch("langflow.services.memory_base.task.Chroma"),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.write_documents_to_chroma",
                AsyncMock(return_value=1),
            ),
            patch("langflow.services.memory_base.task.sync_kb_metadata"),
            patch("langflow.services.memory_base.task._update_preproc_row_status", AsyncMock()),
            patch("langflow.services.memory_base.task._mark_messages_ingested", AsyncMock()),
            patch("langflow.services.memory_base.task._advance_cursor", AsyncMock()),
            patch("langflow.services.memory_base.task.KBStorageHelper.release_chroma_resources"),
        ):
            await ingest_memory_task(request=self._make_request(flow_id))

        insert_mock.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_resume_path_restricts_batch_to_source_ids(self, tmp_path):
        from langflow.services.memory_base.task import ingest_memory_task

        flow_id = uuid.uuid4()
        msg1 = _make_message(flow_id=flow_id, text="first")
        msg2 = _make_message(flow_id=flow_id, text="second")
        preproc_row = self._make_preproc_row_mock(source_ids=[str(msg1.id)], output_text="Cached.")
        build_doc_mock = MagicMock(return_value=[MagicMock()])

        with (
            patch("langflow.services.memory_base.task.KBStorageHelper.get_root_path", return_value=tmp_path),
            patch("langflow.services.memory_base.task._acquire_session_lock", AsyncMock(return_value=asyncio.Lock())),
            patch("langflow.services.memory_base.task._release_session_lock", AsyncMock()),
            patch("langflow.services.memory_base.task._read_live_cursor", AsyncMock(return_value=None)),
            patch("langflow.services.memory_base.task._fetch_pending_messages", AsyncMock(return_value=[msg1, msg2])),
            patch("langflow.services.memory_base.task._get_pending_preproc_row", AsyncMock(return_value=preproc_row)),
            patch("langflow.services.memory_base.task.build_preprocessed_document", build_doc_mock),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.is_job_cancelled",
                AsyncMock(return_value=False),
            ),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.build_embeddings",
                AsyncMock(return_value=MagicMock()),
            ),
            patch(
                "langflow.services.memory_base.task.KBStorageHelper.get_fresh_chroma_client",
                return_value=MagicMock(),
            ),
            patch("langflow.services.memory_base.task.Chroma"),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.write_documents_to_chroma",
                AsyncMock(return_value=1),
            ),
            patch("langflow.services.memory_base.task.sync_kb_metadata"),
            patch("langflow.services.memory_base.task._update_preproc_row_status", AsyncMock()),
            patch("langflow.services.memory_base.task._mark_messages_ingested", AsyncMock()),
            patch("langflow.services.memory_base.task._advance_cursor", AsyncMock()),
            patch("langflow.services.memory_base.task.KBStorageHelper.release_chroma_resources"),
        ):
            await ingest_memory_task(request=self._make_request(flow_id))

        build_doc_mock.assert_called_once()
        call_ids = build_doc_mock.call_args.kwargs["source_message_ids"]
        assert str(msg1.id) in call_ids
        assert str(msg2.id) not in call_ids

    @pytest.mark.asyncio
    async def test_resume_path_vanished_messages_returns_early(self, tmp_path):
        from langflow.services.memory_base.task import ingest_memory_task

        flow_id = uuid.uuid4()
        msg = _make_message(flow_id=flow_id)
        preproc_row = self._make_preproc_row_mock(source_ids=["ghost-id-1", "ghost-id-2"])

        with (
            patch("langflow.services.memory_base.task.KBStorageHelper.get_root_path", return_value=tmp_path),
            patch("langflow.services.memory_base.task._acquire_session_lock", AsyncMock(return_value=asyncio.Lock())),
            patch("langflow.services.memory_base.task._release_session_lock", AsyncMock()),
            patch("langflow.services.memory_base.task._read_live_cursor", AsyncMock(return_value=None)),
            patch("langflow.services.memory_base.task._fetch_pending_messages", AsyncMock(return_value=[msg])),
            patch("langflow.services.memory_base.task._get_pending_preproc_row", AsyncMock(return_value=preproc_row)),
            patch("langflow.services.memory_base.task._update_preproc_row_status", AsyncMock()),
        ):
            result = await ingest_memory_task(request=self._make_request(flow_id))

        assert result == {"message": "Preprocessing source messages missing", "ingested": 0}

    @pytest.mark.asyncio
    async def test_resume_path_vanished_updates_row_to_skipped(self, tmp_path):
        from langflow.services.memory_base.task import ingest_memory_task

        flow_id = uuid.uuid4()
        msg = _make_message(flow_id=flow_id)
        preproc_row = self._make_preproc_row_mock(source_ids=["ghost-id-1"])
        update_mock = AsyncMock()

        with (
            patch("langflow.services.memory_base.task.KBStorageHelper.get_root_path", return_value=tmp_path),
            patch("langflow.services.memory_base.task._acquire_session_lock", AsyncMock(return_value=asyncio.Lock())),
            patch("langflow.services.memory_base.task._release_session_lock", AsyncMock()),
            patch("langflow.services.memory_base.task._read_live_cursor", AsyncMock(return_value=None)),
            patch("langflow.services.memory_base.task._fetch_pending_messages", AsyncMock(return_value=[msg])),
            patch("langflow.services.memory_base.task._get_pending_preproc_row", AsyncMock(return_value=preproc_row)),
            patch("langflow.services.memory_base.task._update_preproc_row_status", update_mock),
        ):
            await ingest_memory_task(request=self._make_request(flow_id))

        update_mock.assert_awaited_once()
        call_kwargs = update_mock.call_args.kwargs
        assert call_kwargs["status"] == "skipped"
        assert call_kwargs["clear_output"] is True

    @pytest.mark.asyncio
    async def test_preprocessing_empty_document_output_returns_early(self, tmp_path):
        from langflow.services.memory_base.preprocessing import PreprocessingResult
        from langflow.services.memory_base.task import ingest_memory_task

        flow_id = uuid.uuid4()
        msg = _make_message(flow_id=flow_id)
        ok_result = PreprocessingResult(status="ingested", output_text="", raw_response="")
        preproc_row = self._make_preproc_row_mock()

        with (
            patch("langflow.services.memory_base.task.KBStorageHelper.get_root_path", return_value=tmp_path),
            patch("langflow.services.memory_base.task._acquire_session_lock", AsyncMock(return_value=asyncio.Lock())),
            patch("langflow.services.memory_base.task._release_session_lock", AsyncMock()),
            patch("langflow.services.memory_base.task._read_live_cursor", AsyncMock(return_value=None)),
            patch("langflow.services.memory_base.task._fetch_pending_messages", AsyncMock(return_value=[msg])),
            patch("langflow.services.memory_base.task._get_pending_preproc_row", AsyncMock(return_value=None)),
            patch("langflow.services.memory_base.task.run_preprocessing", AsyncMock(return_value=ok_result)),
            patch("langflow.services.memory_base.task._insert_preproc_row", AsyncMock(return_value=preproc_row)),
            patch("langflow.services.memory_base.task.build_preprocessed_document", return_value=[]),
        ):
            result = await ingest_memory_task(request=self._make_request(flow_id))

        assert result == {"message": "No non-empty messages to ingest", "ingested": 0}

    @pytest.mark.asyncio
    async def test_preprocessing_job_cancelled_before_chroma(self, tmp_path):
        from langflow.services.memory_base.preprocessing import PreprocessingResult
        from langflow.services.memory_base.task import ingest_memory_task

        flow_id = uuid.uuid4()
        msg = _make_message(flow_id=flow_id)
        ok_result = PreprocessingResult(status="ingested", output_text="Summary.", raw_response="Summary.")
        preproc_row = self._make_preproc_row_mock()
        chroma_client_mock = MagicMock()

        with (
            patch("langflow.services.memory_base.task.KBStorageHelper.get_root_path", return_value=tmp_path),
            patch("langflow.services.memory_base.task._acquire_session_lock", AsyncMock(return_value=asyncio.Lock())),
            patch("langflow.services.memory_base.task._release_session_lock", AsyncMock()),
            patch("langflow.services.memory_base.task._read_live_cursor", AsyncMock(return_value=None)),
            patch("langflow.services.memory_base.task._fetch_pending_messages", AsyncMock(return_value=[msg])),
            patch("langflow.services.memory_base.task._get_pending_preproc_row", AsyncMock(return_value=None)),
            patch("langflow.services.memory_base.task.run_preprocessing", AsyncMock(return_value=ok_result)),
            patch("langflow.services.memory_base.task._insert_preproc_row", AsyncMock(return_value=preproc_row)),
            patch("langflow.services.memory_base.task.build_preprocessed_document", return_value=[MagicMock()]),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.is_job_cancelled",
                AsyncMock(return_value=True),
            ),
            patch(
                "langflow.services.memory_base.task.KBStorageHelper.get_fresh_chroma_client",
                chroma_client_mock,
            ),
        ):
            result = await ingest_memory_task(request=self._make_request(flow_id))

        assert result == {"message": "Job cancelled before ingestion", "ingested": 0}
        chroma_client_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_preprocessing_chroma_write_failure_raises_and_cleans_up(self, tmp_path):
        from langflow.services.memory_base.preprocessing import PreprocessingResult
        from langflow.services.memory_base.task import ingest_memory_task

        flow_id = uuid.uuid4()
        msg = _make_message(flow_id=flow_id)
        ok_result = PreprocessingResult(status="ingested", output_text="Summary.", raw_response="Summary.")
        preproc_row = self._make_preproc_row_mock()
        cleanup_mock = AsyncMock()

        with (
            patch("langflow.services.memory_base.task.KBStorageHelper.get_root_path", return_value=tmp_path),
            patch("langflow.services.memory_base.task._acquire_session_lock", AsyncMock(return_value=asyncio.Lock())),
            patch("langflow.services.memory_base.task._release_session_lock", AsyncMock()),
            patch("langflow.services.memory_base.task._read_live_cursor", AsyncMock(return_value=None)),
            patch("langflow.services.memory_base.task._fetch_pending_messages", AsyncMock(return_value=[msg])),
            patch("langflow.services.memory_base.task._get_pending_preproc_row", AsyncMock(return_value=None)),
            patch("langflow.services.memory_base.task.run_preprocessing", AsyncMock(return_value=ok_result)),
            patch("langflow.services.memory_base.task._insert_preproc_row", AsyncMock(return_value=preproc_row)),
            patch("langflow.services.memory_base.task.build_preprocessed_document", return_value=[MagicMock()]),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.is_job_cancelled",
                AsyncMock(return_value=False),
            ),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.build_embeddings",
                AsyncMock(return_value=MagicMock()),
            ),
            patch(
                "langflow.services.memory_base.task.KBStorageHelper.get_fresh_chroma_client",
                return_value=MagicMock(),
            ),
            patch("langflow.services.memory_base.task.Chroma"),
            patch(
                "langflow.services.memory_base.task.KBIngestionHelper.write_documents_to_chroma",
                AsyncMock(side_effect=RuntimeError("Chroma write failed")),
            ),
            patch("langflow.services.memory_base.task.KBIngestionHelper.cleanup_chroma_chunks_by_job", cleanup_mock),
            patch("langflow.services.memory_base.task.KBStorageHelper.release_chroma_resources"),
            pytest.raises(RuntimeError, match="Chroma write failed"),
        ):
            await ingest_memory_task(request=self._make_request(flow_id))

        cleanup_mock.assert_awaited_once()


# ------------------------------------------------------------------ #
#  Preprocessing DB helpers                                           #
# ------------------------------------------------------------------ #


class TestPreprocessingHelpers:
    """Tests for _get_pending_preproc_row, _insert_preproc_row, _update_preproc_row_status."""

    def _make_preproc_row(
        self,
        *,
        status: str = "processed",
        output_text: str | None = "some text",
        source_ids: list | None = None,
    ):
        from langflow.services.database.models.memory_base.model import MemoryBasePreprocessingOutput

        return MemoryBasePreprocessingOutput(
            memory_base_id=uuid.uuid4(),
            session_id="sess-1",
            status=status,
            output_text=output_text,
            source_message_ids=source_ids or [],
            model_used="gpt-4o-mini",
        )

    # ---- _get_pending_preproc_row ----

    @pytest.mark.asyncio
    async def test_get_pending_preproc_row_returns_none_when_no_rows(self):
        from langflow.services.memory_base.task import _get_pending_preproc_row

        mock_result = MagicMock()
        mock_result.first = MagicMock(return_value=None)
        mock_db = AsyncMock()
        mock_db.exec = AsyncMock(return_value=mock_result)

        result = await _get_pending_preproc_row(mock_db, uuid.uuid4(), "sess-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_pending_preproc_row_returns_row_when_present(self):
        from langflow.services.memory_base.task import _get_pending_preproc_row

        row = self._make_preproc_row()
        mock_result = MagicMock()
        mock_result.first = MagicMock(return_value=row)
        mock_db = AsyncMock()
        mock_db.exec = AsyncMock(return_value=mock_result)

        result = await _get_pending_preproc_row(mock_db, row.memory_base_id, "sess-1")
        assert result is row
        assert result.status == "processed"

    # ---- _insert_preproc_row ----

    @pytest.mark.asyncio
    async def test_insert_preproc_row_calls_add_commit_refresh(self):
        from langflow.services.memory_base.task import _insert_preproc_row

        mock_db = AsyncMock()
        await _insert_preproc_row(
            mock_db,
            memory_base_id=uuid.uuid4(),
            session_id="s1",
            job_id=uuid.uuid4(),
            status="processed",
            output_text="Summary",
            source_message_ids=["id1", "id2"],
            model_used="gpt-4o-mini",
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_awaited_once()
        mock_db.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_insert_preproc_row_returns_row_with_correct_status_and_memory_base_id(self):
        from langflow.services.database.models.memory_base.model import MemoryBasePreprocessingOutput
        from langflow.services.memory_base.task import _insert_preproc_row

        mock_db = AsyncMock()
        mb_id = uuid.uuid4()
        result = await _insert_preproc_row(
            mock_db,
            memory_base_id=mb_id,
            session_id="s1",
            job_id=uuid.uuid4(),
            status="skipped",
            output_text=None,
            source_message_ids=["id1"],
            model_used="gpt-4",
        )

        assert isinstance(result, MemoryBasePreprocessingOutput)
        assert result.status == "skipped"
        assert result.memory_base_id == mb_id
        assert result.output_text is None

    @pytest.mark.asyncio
    async def test_insert_preproc_row_stores_source_message_ids(self):
        from langflow.services.memory_base.task import _insert_preproc_row

        mock_db = AsyncMock()
        ids = ["aaa", "bbb", "ccc"]
        result = await _insert_preproc_row(
            mock_db,
            memory_base_id=uuid.uuid4(),
            session_id="s1",
            job_id=uuid.uuid4(),
            status="processed",
            output_text="ok",
            source_message_ids=ids,
            model_used="gpt-4",
        )

        assert result.source_message_ids == ids

    # ---- _update_preproc_row_status ----

    @pytest.mark.asyncio
    async def test_update_preproc_row_status_sets_status(self):
        from langflow.services.memory_base.task import _update_preproc_row_status

        row = self._make_preproc_row(status="processed")
        mock_db = MagicMock()
        await _update_preproc_row_status(mock_db, row, status="ingested", task_job_id=uuid.uuid4())
        assert row.status == "ingested"

    @pytest.mark.asyncio
    async def test_update_preproc_row_status_updates_job_id(self):
        from langflow.services.memory_base.task import _update_preproc_row_status

        row = self._make_preproc_row()
        new_job_id = uuid.uuid4()
        mock_db = MagicMock()
        await _update_preproc_row_status(mock_db, row, status="ingested", task_job_id=new_job_id)
        assert row.job_id == new_job_id

    @pytest.mark.asyncio
    async def test_update_preproc_row_status_clear_output_false_preserves_text(self):
        from langflow.services.memory_base.task import _update_preproc_row_status

        row = self._make_preproc_row(output_text="important text")
        mock_db = MagicMock()
        await _update_preproc_row_status(mock_db, row, status="ingested", task_job_id=uuid.uuid4(), clear_output=False)
        assert row.output_text == "important text"

    @pytest.mark.asyncio
    async def test_update_preproc_row_status_clear_output_true_nullifies_text(self):
        from langflow.services.memory_base.task import _update_preproc_row_status

        row = self._make_preproc_row(output_text="some text")
        mock_db = MagicMock()
        await _update_preproc_row_status(mock_db, row, status="skipped", task_job_id=uuid.uuid4(), clear_output=True)
        assert row.output_text is None

    @pytest.mark.asyncio
    async def test_update_preproc_row_status_calls_db_add(self):
        from langflow.services.memory_base.task import _update_preproc_row_status

        row = self._make_preproc_row()
        mock_db = MagicMock()
        await _update_preproc_row_status(mock_db, row, status="ingested", task_job_id=uuid.uuid4())
        mock_db.add.assert_called_once_with(row)

    @pytest.mark.asyncio
    async def test_update_preproc_row_status_updates_updated_at_timestamp(self):
        from datetime import datetime, timezone

        from langflow.services.memory_base.task import _update_preproc_row_status

        old_time = datetime(2020, 1, 1, tzinfo=timezone.utc)
        row = self._make_preproc_row()
        row.updated_at = old_time
        mock_db = MagicMock()
        await _update_preproc_row_status(mock_db, row, status="ingested", task_job_id=uuid.uuid4())
        assert row.updated_at > old_time


# ------------------------------------------------------------------ #
#  _fetch_pending_messages — error-message filtering                  #
# ------------------------------------------------------------------ #


class TestFetchPendingMessagesFiltersErrors:
    """Regression: component error/exception messages must never be ingested.

    See bug report: "[Memory Base] Error messages from components are indexed as
    valid chunks in Chroma".  The fetch must skip messages where ``error=True``
    or ``category='error'`` so failure output (e.g. an embedder API error) is
    never embedded as legitimate conversation context.
    """

    @staticmethod
    def _engine():
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlmodel.pool import StaticPool

        return create_async_engine(
            "sqlite+aiosqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

    @pytest.mark.asyncio
    async def test_excludes_messages_with_error_flag_or_error_category(self):
        from langflow.services.database.models.message.model import MessageTable
        from langflow.services.memory_base.task import _fetch_pending_messages
        from sqlmodel import SQLModel
        from sqlmodel.ext.asyncio.session import AsyncSession

        engine = self._engine()
        try:
            async with engine.begin() as conn:
                await conn.run_sync(SQLModel.metadata.create_all)

            flow_id = uuid.uuid4()
            session_id = "sess-error-filter"
            base_ts = datetime.now(timezone.utc)

            good_user = MessageTable(
                id=uuid.uuid4(),
                sender="User",
                sender_name="User",
                session_id=session_id,
                text="What is the weather?",
                flow_id=flow_id,
                timestamp=base_ts,
                error=False,
                category="message",
            )
            error_flag_only = MessageTable(
                id=uuid.uuid4(),
                sender="Knowledge Base",
                sender_name="Knowledge Base",
                session_id=session_id,
                text="[Knowledge Base] Error embedding content (INVALID_ARGUMENT): 400.",
                flow_id=flow_id,
                timestamp=base_ts.replace(microsecond=base_ts.microsecond + 1),
                error=True,
                category="message",  # category may not always be "error"
            )
            error_category = MessageTable(
                id=uuid.uuid4(),
                sender="Knowledge Base",
                sender_name="Knowledge Base",
                session_id=session_id,
                text="EmbedContentRequest.content contains an empty Part.",
                flow_id=flow_id,
                timestamp=base_ts.replace(microsecond=base_ts.microsecond + 2),
                error=False,  # legacy rows may have error=False but category="error"
                category="error",
            )
            good_ai = MessageTable(
                id=uuid.uuid4(),
                sender="Machine",
                sender_name="AI",
                session_id=session_id,
                text="The weather is sunny.",
                flow_id=flow_id,
                timestamp=base_ts.replace(microsecond=base_ts.microsecond + 3),
                error=False,
                category="message",
            )

            async with AsyncSession(engine, expire_on_commit=False) as db:
                db.add_all([good_user, error_flag_only, error_category, good_ai])
                await db.commit()

                fetched = await _fetch_pending_messages(
                    db,
                    flow_id=flow_id,
                    session_id=session_id,
                    cursor_id=None,
                )

            fetched_ids = {m.id for m in fetched}
            assert good_user.id in fetched_ids
            assert good_ai.id in fetched_ids
            assert error_flag_only.id not in fetched_ids, "error=True message must be filtered"
            assert error_category.id not in fetched_ids, "category='error' message must be filtered"
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_other_session_or_flow_messages_still_excluded_even_when_error(self):
        """Sanity check: error filter does not accidentally pull in cross-session rows."""
        from langflow.services.database.models.message.model import MessageTable
        from langflow.services.memory_base.task import _fetch_pending_messages
        from sqlmodel import SQLModel
        from sqlmodel.ext.asyncio.session import AsyncSession

        engine = self._engine()
        try:
            async with engine.begin() as conn:
                await conn.run_sync(SQLModel.metadata.create_all)

            flow_id = uuid.uuid4()
            other_flow_id = uuid.uuid4()
            session_id = "sess-A"
            other_session_id = "sess-B"
            ts = datetime.now(timezone.utc)

            # Good message in *another* session — must not be returned.
            other_session_msg = MessageTable(
                id=uuid.uuid4(),
                sender="User",
                sender_name="User",
                session_id=other_session_id,
                text="cross-session leak attempt",
                flow_id=flow_id,
                timestamp=ts,
                error=False,
                category="message",
            )
            # Good message in another flow — must not be returned either.
            other_flow_msg = MessageTable(
                id=uuid.uuid4(),
                sender="User",
                sender_name="User",
                session_id=session_id,
                text="cross-flow leak attempt",
                flow_id=other_flow_id,
                timestamp=ts,
                error=False,
                category="message",
            )
            good = MessageTable(
                id=uuid.uuid4(),
                sender="User",
                sender_name="User",
                session_id=session_id,
                text="kept",
                flow_id=flow_id,
                timestamp=ts.replace(microsecond=ts.microsecond + 1),
                error=False,
                category="message",
            )

            async with AsyncSession(engine, expire_on_commit=False) as db:
                db.add_all([other_session_msg, other_flow_msg, good])
                await db.commit()

                fetched = await _fetch_pending_messages(
                    db,
                    flow_id=flow_id,
                    session_id=session_id,
                    cursor_id=None,
                )

            fetched_ids = {m.id for m in fetched}
            assert fetched_ids == {good.id}
        finally:
            await engine.dispose()
