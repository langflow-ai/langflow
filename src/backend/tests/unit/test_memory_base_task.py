"""Unit tests for langflow.services.memory_base.task.

Covers the gaps not addressed by TestIngestMemoryTask in test_memory_bases.py:
- ingest_memory_task: missing kb_root, pre-ingestion cancel, zero-document early-out
- _extract_content_block_text: all block types, edge cases
- _build_documents_from_messages: chunking, content-block text, missing fields
- _sync_kb_metadata: source_types merge
- _advance_cursor: vanished session, normal update
- _mark_messages_ingested: correct DB update shape
"""

from __future__ import annotations

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
        from langflow.services.memory_base.task import ingest_memory_task

        with (
            patch(
                "langflow.services.memory_base.task.KBStorageHelper.get_root_path",
                return_value=None,
            ),
            pytest.raises(RuntimeError, match="Knowledge base root path is not configured"),
        ):
            await ingest_memory_task(
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
            )

    @pytest.mark.asyncio
    async def test_returns_early_when_job_cancelled_before_write(self, tmp_path):
        """is_job_cancelled=True after fetch must return without touching Chroma."""
        from langflow.services.memory_base.task import ingest_memory_task

        flow_id = uuid.uuid4()
        msg = _make_message(flow_id=flow_id)
        chroma_client_called = False

        def fake_get_client(_path):
            nonlocal chroma_client_called
            chroma_client_called = True
            return MagicMock()

        with (
            patch(
                "langflow.services.memory_base.task._fetch_pending_messages",
                AsyncMock(return_value=[msg]),
            ),
            patch(
                "langflow.services.memory_base.task._build_documents_from_messages",
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
            )

        assert result == {"message": "Job cancelled before ingestion", "ingested": 0}
        assert not chroma_client_called

    @pytest.mark.asyncio
    async def test_returns_early_when_documents_list_is_empty(self, tmp_path):
        """All-whitespace messages produce zero documents — early exit before Chroma."""
        from langflow.services.memory_base.task import ingest_memory_task

        flow_id = uuid.uuid4()
        msg = _make_message(flow_id=flow_id, text="   ")  # whitespace only

        with (
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
            )

        assert result == {"message": "No non-empty messages to ingest", "ingested": 0}

    @pytest.mark.asyncio
    async def test_mark_messages_ingested_called_on_success(self, tmp_path):
        """_mark_messages_ingested must be called exactly once on a successful run."""
        from langflow.services.memory_base.task import ingest_memory_task

        flow_id = uuid.uuid4()
        msg = _make_message(flow_id=flow_id)

        mark_ingested_mock = AsyncMock()

        with (
            patch(
                "langflow.services.memory_base.task._fetch_pending_messages",
                AsyncMock(return_value=[msg]),
            ),
            patch(
                "langflow.services.memory_base.task._build_documents_from_messages",
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
            patch("langflow.services.memory_base.task._sync_kb_metadata"),
            patch("langflow.services.memory_base.task._mark_messages_ingested", mark_ingested_mock),
            patch("langflow.services.memory_base.task._advance_cursor", AsyncMock()),
            patch(
                "langflow.services.memory_base.task.KBStorageHelper.get_root_path",
                return_value=tmp_path,
            ),
            patch("langflow.services.memory_base.task.KBStorageHelper.release_chroma_resources"),
        ):
            await ingest_memory_task(
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
            )

        mark_ingested_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_mark_messages_ingested_not_called_when_cancelled(self, tmp_path):
        """When write returns fewer docs than sent, messages must NOT be stamped."""
        from langflow.services.memory_base.task import ingest_memory_task

        flow_id = uuid.uuid4()
        msg = _make_message(flow_id=flow_id)

        mark_ingested_mock = AsyncMock()

        with (
            patch(
                "langflow.services.memory_base.task._fetch_pending_messages",
                AsyncMock(return_value=[msg]),
            ),
            patch(
                "langflow.services.memory_base.task._build_documents_from_messages",
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
            patch("langflow.services.memory_base.task._sync_kb_metadata"),
            patch("langflow.services.memory_base.task._mark_messages_ingested", mark_ingested_mock),
            patch("langflow.services.memory_base.task._advance_cursor", AsyncMock()),
            patch(
                "langflow.services.memory_base.task.KBStorageHelper.get_root_path",
                return_value=tmp_path,
            ),
            patch("langflow.services.memory_base.task.KBStorageHelper.release_chroma_resources"),
        ):
            result = await ingest_memory_task(
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
            )

        mark_ingested_mock.assert_not_awaited()
        assert "cancelled" in result["message"].lower()


# ------------------------------------------------------------------ #
#  _extract_content_block_text                                        #
# ------------------------------------------------------------------ #


class TestExtractContentBlockText:
    def _call(self, blocks):
        from langflow.services.memory_base.task import _extract_content_block_text

        return _extract_content_block_text(blocks)

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
#  _build_documents_from_messages                                     #
# ------------------------------------------------------------------ #


class TestBuildDocumentsFromMessages:
    def _call(self, messages, *, session_id="s1", flow_id=None):
        from langflow.services.memory_base.task import _build_documents_from_messages

        return _build_documents_from_messages(
            messages,
            session_id=session_id,
            flow_id=flow_id or str(uuid.uuid4()),
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
        from langflow.services.memory_base.task import _MESSAGE_CHUNK_SIZE

        flow_id = uuid.uuid4()
        # Craft text longer than chunk size
        long_text = "x " * (_MESSAGE_CHUNK_SIZE + 100)
        msg = _make_message(flow_id=flow_id, text=long_text)
        docs = self._call([msg], flow_id=str(flow_id))
        assert len(docs) > 1

    def test_chunk_index_and_total_chunks_metadata(self):
        from langflow.services.memory_base.task import _MESSAGE_CHUNK_SIZE

        flow_id = uuid.uuid4()
        long_text = "word " * (_MESSAGE_CHUNK_SIZE // 4)
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

    def test_multiple_messages_produce_separate_docs(self):
        flow_id = uuid.uuid4()
        msgs = [_make_message(flow_id=flow_id, text=f"msg {i}") for i in range(3)]
        docs = self._call(msgs, flow_id=str(flow_id))
        assert len(docs) == 3
        message_ids = [d.metadata["message_id"] for d in docs]
        assert len(set(message_ids)) == 3


# ------------------------------------------------------------------ #
#  _sync_kb_metadata                                                  #
# ------------------------------------------------------------------ #


class TestSyncKbMetadata:
    def test_preserves_existing_source_types(self, tmp_path):
        from langflow.services.memory_base.task import _sync_kb_metadata

        kb_path = tmp_path / "kb"
        kb_path.mkdir()

        with (
            patch(
                "langflow.services.memory_base.task.KBAnalysisHelper.get_metadata",
                return_value={"chunks": 5, "source_types": ["file"]},
            ),
            patch("langflow.services.memory_base.task.KBAnalysisHelper.update_text_metrics"),
            patch("langflow.services.memory_base.task.KBStorageHelper.get_directory_size", return_value=2048),
        ):
            _sync_kb_metadata(kb_path=kb_path, chroma=MagicMock())

        written = json.loads((kb_path / "embedding_metadata.json").read_text())
        assert "file" in written["source_types"]
        assert "memory" in written["source_types"]

    def test_source_types_sorted(self, tmp_path):
        from langflow.services.memory_base.task import _sync_kb_metadata

        kb_path = tmp_path / "kb"
        kb_path.mkdir()

        with (
            patch(
                "langflow.services.memory_base.task.KBAnalysisHelper.get_metadata",
                return_value={"chunks": 0, "source_types": ["zzz", "aaa"]},
            ),
            patch("langflow.services.memory_base.task.KBAnalysisHelper.update_text_metrics"),
            patch("langflow.services.memory_base.task.KBStorageHelper.get_directory_size", return_value=0),
        ):
            _sync_kb_metadata(kb_path=kb_path, chroma=MagicMock())

        written = json.loads((kb_path / "embedding_metadata.json").read_text())
        assert written["source_types"] == sorted(written["source_types"])

    def test_json_decode_error_swallowed(self, tmp_path):
        from langflow.services.memory_base.task import _sync_kb_metadata

        kb_path = tmp_path / "kb"
        kb_path.mkdir()

        with patch(
            "langflow.services.memory_base.task.KBAnalysisHelper.get_metadata",
            side_effect=json.JSONDecodeError("bad", "", 0),
        ):
            # Must not raise
            _sync_kb_metadata(kb_path=kb_path, chroma=MagicMock())

    def test_value_error_swallowed(self, tmp_path):
        from langflow.services.memory_base.task import _sync_kb_metadata

        kb_path = tmp_path / "kb"
        kb_path.mkdir()

        with (
            patch(
                "langflow.services.memory_base.task.KBAnalysisHelper.get_metadata",
                return_value={},
            ),
            patch(
                "langflow.services.memory_base.task.KBAnalysisHelper.update_text_metrics",
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

        mbs = MemoryBaseSession(
            id=uuid.uuid4(),
            memory_base_id=mb_id,
            session_id="s1",
            cursor_id=None,
            total_processed=5,
        )

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.first = MagicMock(return_value=mbs)
        mock_db.exec = AsyncMock(return_value=mock_result)

        with patch("langflow.services.memory_base.task.session_scope", _fake_scope(mock_db)):
            await _advance_cursor(
                memory_base_id=mb_id,
                session_id="s1",
                new_cursor_id=new_cursor,
                ingested_count=3,
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

        with patch("langflow.services.memory_base.task.session_scope", _fake_scope(mock_db)):
            # Must not raise
            await _advance_cursor(
                memory_base_id=uuid.uuid4(),
                session_id="gone",
                new_cursor_id=uuid.uuid4(),
                ingested_count=1,
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

        mock_db = AsyncMock()
        mock_db.exec = AsyncMock()

        with patch("langflow.services.memory_base.task.session_scope", _fake_scope(mock_db)):
            await _mark_messages_ingested(messages=messages, job_id=job_id)

        mock_db.exec.assert_awaited_once()
        mock_db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_sets_ingestion_job_id_and_timestamp(self):
        """The UPDATE statement must bind ingestion_job_id and ingestion_timestamp."""
        from langflow.services.memory_base.task import _mark_messages_ingested
        from sqlalchemy.sql.dml import Update

        flow_id = uuid.uuid4()
        messages = [_make_message(flow_id=flow_id)]
        job_id = uuid.uuid4()

        captured_stmt = {}

        async def capture_exec(stmt):
            captured_stmt["stmt"] = stmt
            return MagicMock()

        mock_db = AsyncMock()
        mock_db.exec = capture_exec

        with patch("langflow.services.memory_base.task.session_scope", _fake_scope(mock_db)):
            await _mark_messages_ingested(messages=messages, job_id=job_id)

        stmt = captured_stmt["stmt"]
        assert isinstance(stmt, Update)
        # Verify the compiled values include both fields
        compiled_params = stmt.compile().params
        assert "ingestion_job_id" in compiled_params
        assert compiled_params["ingestion_job_id"] == job_id
        assert "ingestion_timestamp" in compiled_params
