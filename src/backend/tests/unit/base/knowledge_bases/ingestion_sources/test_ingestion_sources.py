"""Unit tests for the KB ingestion-source abstraction.

Covers:

* Registry lookup / registration / error paths.
* ``FileUploadSource`` validation + list/fetch round-trip.
* ``FolderSource`` allow-list enforcement (both happy path and every
  failure mode), extension filter, size cap, and symlink-escape safety.
* ``IngestionSummary.record_item`` counter accounting.

Uses only tmp_path + synthetic bytes so tests run credential-free.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from lfx.base.knowledge_bases.ingestion_sources import (
    FileUploadSource,
    FolderSource,
    IngestionItemResult,
    IngestionItemStatus,
    IngestionSummary,
    KBIngestionSource,
    SourceType,
    create_source,
    get_source_class,
    register_source,
    registered_sources,
)

if TYPE_CHECKING:
    from pathlib import Path


class _DummySource(KBIngestionSource):
    source_type = SourceType.TEMPLATE  # reserved slot, reused here for the registry test
    display_name = "Dummy"

    async def list_items(self):  # pragma: no cover
        yield None

    async def fetch_content(self, item):  # pragma: no cover
        raise NotImplementedError


class TestRegistry:
    def test_builtins_registered(self):
        assert SourceType.FILE_UPLOAD in registered_sources()
        assert SourceType.FOLDER in registered_sources()
        assert get_source_class(SourceType.FILE_UPLOAD) is FileUploadSource
        assert get_source_class(SourceType.FOLDER) is FolderSource

    def test_create_source_accepts_string(self):
        source = create_source("file_upload", user_id=None, source_config={"files": [("x.txt", b"ok")]})
        assert isinstance(source, FileUploadSource)

    def test_unknown_source_type_raises(self):
        with pytest.raises(ValueError, match="Unknown ingestion source"):
            get_source_class("mystery")

    def test_unregistered_known_type_raises(self):
        # TEMPLATE has a SourceType value but no registered class.
        with pytest.raises(ValueError, match="not registered"):
            get_source_class(SourceType.TEMPLATE)

    def test_register_idempotent_but_collision_raises(self):
        register_source(SourceType.FILE_UPLOAD, FileUploadSource)  # idempotent
        with pytest.raises(ValueError, match="already registered"):
            register_source(SourceType.FILE_UPLOAD, _DummySource)


class TestFileUploadSource:
    async def test_validate_requires_files(self):
        source = FileUploadSource(user_id=None, source_config={})
        with pytest.raises(ValueError, match="non-empty"):
            await source.validate_config()

    async def test_validate_rejects_malformed_entries(self):
        source = FileUploadSource(user_id=None, source_config={"files": ["not-a-tuple"]})
        with pytest.raises(TypeError, match="name, bytes"):
            await source.validate_config()

    async def test_round_trip(self):
        payload = [("a.txt", b"alpha"), ("b.md", b"bravo"), ("c.pdf", b"charlie")]
        source = FileUploadSource(user_id=None, source_config={"files": payload})
        await source.validate_config()

        items = [item async for item in source.list_items()]
        assert [item.display_name for item in items] == ["a.txt", "b.md", "c.pdf"]
        assert items[0].size_bytes == 5

        content = await source.fetch_content(items[1])
        assert content.raw_bytes == b"bravo"
        assert content.file_name == "b.md"

    async def test_describe_redacts_bytes(self):
        source = FileUploadSource(user_id=None, source_config={"files": [("a.txt", b"secret-bytes")]})
        described = source.describe()
        # File names are public, bytes are not.
        assert described["config"]["file_names"] == ["a.txt"]
        assert "files" not in described["config"]
        assert described["config"]["total_bytes"] == len(b"secret-bytes")


class TestFolderSourceAllowList:
    async def test_rejects_missing_path(self):
        source = FolderSource(user_id=None, source_config={})
        with pytest.raises(ValueError, match="'path' string"):
            await source.validate_config()

    async def test_rejects_nonexistent_path(self, tmp_path: Path):
        source = FolderSource(
            user_id=None,
            source_config={"path": str(tmp_path / "missing"), "allowed_roots": [str(tmp_path)]},
        )
        with pytest.raises(ValueError, match="does not exist"):
            await source.validate_config()

    async def test_rejects_file_path(self, tmp_path: Path):
        file_path = tmp_path / "a.txt"
        file_path.write_text("x")
        source = FolderSource(
            user_id=None,
            source_config={"path": str(file_path), "allowed_roots": [str(tmp_path)]},
        )
        with pytest.raises(ValueError, match="not a directory"):
            await source.validate_config()

    async def test_empty_allow_list_refuses(self, tmp_path: Path):
        source = FolderSource(
            user_id=None,
            source_config={"path": str(tmp_path), "allowed_roots": []},
        )
        with pytest.raises(ValueError, match="allow-list"):
            await source.validate_config()

    async def test_outside_allow_list_refused(self, tmp_path: Path):
        outside = tmp_path / "outside"
        outside.mkdir()
        inside = tmp_path / "inside"
        inside.mkdir()
        source = FolderSource(
            user_id=None,
            source_config={"path": str(outside), "allowed_roots": [str(inside)]},
        )
        with pytest.raises(ValueError, match="outside the configured allow-list"):
            await source.validate_config()

    async def test_inside_allow_list_passes(self, tmp_path: Path):
        root = tmp_path / "root"
        inner = root / "inner"
        inner.mkdir(parents=True)
        source = FolderSource(
            user_id=None,
            source_config={"path": str(inner), "allowed_roots": [str(root)]},
        )
        await source.validate_config()  # no raise

    async def test_symlink_escape_blocked(self, tmp_path: Path):
        root = tmp_path / "allowed"
        root.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        sym = root / "escape"
        sym.symlink_to(outside)
        source = FolderSource(
            user_id=None,
            source_config={"path": str(sym), "allowed_roots": [str(root)]},
        )
        # ``resolve()`` follows the symlink before the containment check
        # — without that, this would slip past the allow-list.
        with pytest.raises(ValueError, match="outside the configured allow-list"):
            await source.validate_config()


class TestFolderSourceListAndFetch:
    async def test_extension_filter_applied(self, tmp_path: Path):
        (tmp_path / "keep.md").write_text("markdown")
        (tmp_path / "keep.txt").write_text("text")
        (tmp_path / "drop.jpg").write_bytes(b"\x89PNG")  # not in default extensions

        source = FolderSource(
            user_id=None,
            source_config={"path": str(tmp_path), "allowed_roots": [str(tmp_path)], "recursive": False},
        )
        items = [item async for item in source.list_items()]
        names = sorted(item.display_name for item in items)
        assert names == ["keep.md", "keep.txt"]

    async def test_recursive_walk(self, tmp_path: Path):
        (tmp_path / "root.md").write_text("x")
        nested = tmp_path / "nested"
        nested.mkdir()
        (nested / "deep.md").write_text("y")

        source = FolderSource(
            user_id=None,
            source_config={"path": str(tmp_path), "allowed_roots": [str(tmp_path)]},
        )
        items = [item async for item in source.list_items()]
        ids = sorted(item.item_id for item in items)
        assert ids == ["nested/deep.md", "root.md"]

    async def test_oversized_file_skipped(self, tmp_path: Path):
        small = tmp_path / "small.md"
        small.write_bytes(b"ok")
        big = tmp_path / "big.md"
        big.write_bytes(b"x" * 100)

        source = FolderSource(
            user_id=None,
            source_config={
                "path": str(tmp_path),
                "allowed_roots": [str(tmp_path)],
                "max_file_size_bytes": 10,
            },
        )
        items = [item async for item in source.list_items()]
        assert [item.display_name for item in items] == ["small.md"]

    async def test_fetch_content_refuses_escape(self, tmp_path: Path):
        """Mutated ``item_id`` must not allow reads outside the root."""
        inner = tmp_path / "inner"
        inner.mkdir()
        (inner / "safe.md").write_text("ok")

        source = FolderSource(
            user_id=None,
            source_config={"path": str(inner), "allowed_roots": [str(tmp_path)]},
        )
        items = [item async for item in source.list_items()]
        assert items
        # Tamper the item_id to try to escape the root.
        from dataclasses import replace

        malicious = replace(items[0], item_id="../outside.md")
        with pytest.raises((ValueError, OSError, FileNotFoundError)):
            await source.fetch_content(malicious)


class TestIngestionSummary:
    def test_record_item_updates_counters(self):
        summary = IngestionSummary(kb_name="kb", source_type="file_upload")
        summary.record_item(
            IngestionItemResult(
                item_id="1",
                display_name="a.txt",
                status=IngestionItemStatus.SUCCEEDED,
                chunks_created=3,
            ),
            size_bytes=100,
        )
        summary.record_item(
            IngestionItemResult(
                item_id="2",
                display_name="b.txt",
                status=IngestionItemStatus.FAILED,
                error_message="boom",
            ),
            size_bytes=50,
        )
        summary.record_item(
            IngestionItemResult(
                item_id="3",
                display_name="c.txt",
                status=IngestionItemStatus.SKIPPED,
            ),
            size_bytes=0,
        )

        assert summary.total_items == 3
        assert summary.succeeded == 1
        assert summary.failed == 1
        assert summary.skipped == 1
        assert summary.total_bytes == 150
        assert summary.chunks_created == 3
        assert len(summary.items) == 3


class TestPerFileMetadata:
    async def test_file_upload_per_file_metadata_propagates(self):
        payload = [("a.txt", b"alpha"), ("b.txt", b"beta")]
        source = FileUploadSource(
            user_id=None,
            source_config={
                "files": payload,
                "source_name": "batch",
                "per_file_metadata": {"a.txt": {"category": "invoice", "tag": ["urgent"]}},
            },
        )
        items = [item async for item in source.list_items()]
        # ``a.txt`` carries both the run-level source_name and its per-file overrides.
        assert items[0].source_metadata["category"] == "invoice"
        assert items[0].source_metadata["tag"] == ["urgent"]
        assert items[0].source_metadata["source_name"] == "batch"
        # ``b.txt`` only carries the source_name — no per-file override registered.
        assert items[1].source_metadata == {"source_name": "batch"}

    async def test_file_upload_describe_counts_metadata(self):
        source = FileUploadSource(
            user_id=None,
            source_config={
                "files": [("a.txt", b"x"), ("b.txt", b"y")],
                "per_file_metadata": {"a.txt": {"tag": "x"}},
            },
        )
        described = source.describe()
        assert described["config"]["files_with_metadata"] == 1

    async def test_folder_per_file_metadata_relative_path_wins(self, tmp_path: Path):
        nested = tmp_path / "nested"
        nested.mkdir()
        (tmp_path / "doc.md").write_text("root-doc")
        (nested / "doc.md").write_text("nested-doc")

        source = FolderSource(
            user_id=None,
            source_config={
                "path": str(tmp_path),
                "allowed_roots": [str(tmp_path)],
                "per_file_metadata": {
                    # Bare basename should not override the relative-path key
                    # for the nested file.
                    "doc.md": {"tier": "default"},
                    "nested/doc.md": {"tier": "nested"},
                },
            },
        )
        items = {item.item_id: item async for item in source.list_items()}
        assert items["doc.md"].source_metadata["tier"] == "default"
        assert items["nested/doc.md"].source_metadata["tier"] == "nested"

    async def test_folder_metadata_absent_for_unmatched_files(self, tmp_path: Path):
        (tmp_path / "doc.md").write_text("hello")
        source = FolderSource(
            user_id=None,
            source_config={"path": str(tmp_path), "allowed_roots": [str(tmp_path)]},
        )
        items = [item async for item in source.list_items()]
        # No per_file_metadata configured → only the source's own provenance keys remain.
        assert "tier" not in items[0].source_metadata
        assert items[0].source_metadata.get("relative_path") == "doc.md"
