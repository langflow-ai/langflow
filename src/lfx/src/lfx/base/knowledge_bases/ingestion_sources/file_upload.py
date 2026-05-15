"""File-upload ingestion source.

Wraps the in-memory ``list[(file_name, bytes)]`` payload the existing
``/ingest`` API route already assembles from FastAPI's ``UploadFile``
list. Lets the ingestion machinery treat direct uploads identically to
folder walks and future cloud connectors without forcing the API to
change its shape for this phase.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.base.knowledge_bases.ingestion_sources.base import (
    IngestionItem,
    IngestionItemContent,
    KBIngestionSource,
    SourceType,
)

# Each ``files`` entry is ``(name, bytes)``.
_FILES_TUPLE_ARITY = 2

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class FileUploadSource(KBIngestionSource):
    """Serves items from a preloaded ``files`` list.

    ``source_config`` shape::

        {
            "files": [(file_name, raw_bytes), ...],
            "source_name": "optional-display-grouping",
            "per_file_metadata": {
                "filename.pdf": {"category": "invoice", ...},
                ...
            },
        }

    The bytes payload lives entirely in memory — intended only for
    direct HTTP uploads. For anything large or durable, use
    ``FolderSource`` (local walk) or a cloud connector (Phase 3).

    ``per_file_metadata`` is optional. When present, each entry is merged
    onto the matching file's ``IngestionItem.source_metadata`` so the
    ingestion pipeline can persist user-supplied per-file tags on every
    chunk produced from that file.
    """

    source_type = SourceType.FILE_UPLOAD
    display_name = "File Upload"
    description = "Ingest one or more files uploaded via the Langflow UI or API."
    icon = "upload"
    requires_credentials = False

    async def validate_config(self) -> None:
        files = self.source_config.get("files")
        if not isinstance(files, list) or not files:
            msg = "FileUploadSource requires a non-empty 'files' list in source_config."
            raise ValueError(msg)

        for entry in files:
            if not (isinstance(entry, tuple) and len(entry) == _FILES_TUPLE_ARITY):
                msg = f"Each entry in FileUploadSource.files must be a (name, bytes) tuple; got {type(entry).__name__}."
                raise TypeError(msg)
            name, content = entry
            if not isinstance(name, str) or not name:
                msg = "File entry name must be a non-empty string."
                raise ValueError(msg)
            if not isinstance(content, (bytes, bytearray)):
                msg = f"File entry content must be bytes; got {type(content).__name__} for {name!r}."
                raise TypeError(msg)

    async def list_items(self) -> AsyncIterator[IngestionItem]:
        files: list[tuple[str, bytes]] = self.source_config.get("files", [])
        source_name = self.source_config.get("source_name")
        per_file_metadata: dict[str, dict[str, Any]] = self.source_config.get("per_file_metadata") or {}
        for idx, (name, content) in enumerate(files):
            item_metadata: dict[str, Any] = {}
            if source_name:
                item_metadata["source_name"] = source_name
            file_overrides = per_file_metadata.get(name)
            if file_overrides:
                # User-supplied keys win over the source-level ``source_name``
                # tag. The validator at the API boundary already blocked any
                # reserved keys, so this merge is safe.
                item_metadata.update(file_overrides)
            yield IngestionItem(
                item_id=f"{idx}:{name}",
                display_name=name,
                source_url=f"upload://{name}",
                source_metadata=item_metadata,
                size_bytes=len(content),
            )

    async def fetch_content(self, item: IngestionItem) -> IngestionItemContent:
        files: list[tuple[str, bytes]] = self.source_config.get("files", [])
        # item_id is "{idx}:{name}"; split on the first ":" so filenames
        # containing colons still round-trip correctly.
        idx_str, _, name = item.item_id.partition(":")
        idx = int(idx_str)
        if idx >= len(files):
            msg = f"FileUploadSource item index {idx} out of range for {len(files)} files."
            raise IndexError(msg)
        stored_name, stored_bytes = files[idx]
        # Defensive: the stored name should match, but prefer the live
        # value if the caller mutated source_config between list and fetch.
        file_name = stored_name or name or item.display_name
        return IngestionItemContent(raw_bytes=bytes(stored_bytes), file_name=file_name)

    def describe(self) -> dict[str, Any]:
        """Redact the raw bytes from ``describe`` output.

        Running describe on a FileUploadSource before/after ingestion
        should show how many files are queued, not dump the binary
        payload into logs or UIs.
        """
        base = super().describe()
        files: list[tuple[str, bytes]] = self.source_config.get("files", [])
        per_file_metadata: dict[str, dict[str, Any]] = self.source_config.get("per_file_metadata") or {}
        base["config"] = {
            "source_name": self.source_config.get("source_name"),
            "file_count": len(files),
            "file_names": [name for name, _ in files],
            "total_bytes": sum(len(content) for _, content in files),
            "files_with_metadata": sum(1 for name, _ in files if per_file_metadata.get(name)),
        }
        return base
