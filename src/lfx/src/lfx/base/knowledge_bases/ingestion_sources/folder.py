"""Local-folder ingestion source.

Walks a directory on the server's filesystem and ingests matching
files. Safe-by-default via ``allowed_roots`` — the caller must declare
which directories are permitted, and the resolved folder path must be
inside one of them (no symlink traversal out).

Intended for Langflow Desktop and self-hosted deployments where the
operator can reason about which directories the service can read. In
multi-tenant cloud the allow-list should be configured to an empty
list (or per-tenant roots) so arbitrary-path access is refused.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING, Any

from lfx.base.knowledge_bases.ingestion_sources.base import (
    IngestionItem,
    IngestionItemContent,
    KBIngestionSource,
    SourceType,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

# Matches ``lfx.base.data.utils.extract_text_from_bytes`` dispatch table.
# Keep lowercase without the leading dot.
DEFAULT_TEXT_EXTENSIONS: tuple[str, ...] = (
    "txt",
    "md",
    "markdown",
    "rst",
    "csv",
    "tsv",
    "json",
    "jsonl",
    "yaml",
    "yml",
    "xml",
    "html",
    "htm",
    "pdf",
    "docx",
    "doc",
    "pptx",
    "ppt",
    "xlsx",
    "xls",
)

# Files larger than this are skipped to prevent a single pathological
# file from blocking a batch. Matches WxO's per-file ceiling for PDFs
# etc. Can be overridden in ``source_config["max_file_size_bytes"]``.
DEFAULT_MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024


class FolderSource(KBIngestionSource):
    """Walks ``path`` and yields every matching file.

    ``source_config`` shape::

        {
            "path": "/absolute/or/expanded/~ path",
            "recursive": True,           # default: True
            "extensions": ["pdf", "md"], # default: DEFAULT_TEXT_EXTENSIONS
            "max_file_size_bytes": 10_000_000,  # default: DEFAULT_MAX_FILE_SIZE_BYTES
            "allowed_roots": ["/home/alice"],  # required for safety
            "per_file_metadata": {
                "relative/path.pdf": {"category": "invoice"},
                "basename.txt": {"tag": ["urgent"]},
            },
        }

    ``allowed_roots`` comes from settings at the call site — sources
    don't reach into settings themselves so tests can drive the
    constraint directly.

    ``per_file_metadata`` is matched on either the relative path under
    the resolved root (``item_id``) or the bare filename, with the
    relative-path lookup taking precedence so two files with the same
    basename in different subfolders can be tagged independently.
    """

    source_type = SourceType.FOLDER
    display_name = "Folder"
    description = "Ingest every matching file from a server-side folder."
    icon = "folder"
    requires_credentials = False

    async def validate_config(self) -> None:
        path_str = self.source_config.get("path")
        if not path_str or not isinstance(path_str, str):
            msg = "FolderSource requires a non-empty 'path' string in source_config."
            raise ValueError(msg)

        path = Path(path_str).expanduser().resolve()
        if not path.exists():
            msg = f"Folder {path} does not exist."
            raise ValueError(msg)
        if not path.is_dir():
            msg = f"Path {path} is not a directory."
            raise ValueError(msg)

        allowed_roots = self.source_config.get("allowed_roots") or []
        if not allowed_roots:
            msg = (
                "FolderSource refuses to walk without an allow-list. Configure "
                "LANGFLOW_KB_ALLOWED_FOLDER_ROOTS or pass 'allowed_roots' in source_config."
            )
            raise ValueError(msg)

        resolved_roots = [Path(r).expanduser().resolve() for r in allowed_roots]
        # Path.is_relative_to is the right primitive — it rejects symlink
        # escapes because ``resolve()`` already followed them.
        if not any(path == root or path.is_relative_to(root) for root in resolved_roots):
            allowed_display = ", ".join(str(r) for r in resolved_roots)
            msg = f"Folder {path} is outside the configured allow-list ({allowed_display})."
            raise ValueError(msg)

        max_size = self.source_config.get("max_file_size_bytes", DEFAULT_MAX_FILE_SIZE_BYTES)
        if not isinstance(max_size, int) or max_size <= 0:
            msg = "max_file_size_bytes must be a positive integer."
            raise ValueError(msg)

    def _resolved_path(self) -> Path:
        return Path(self.source_config["path"]).expanduser().resolve()

    def _extension_whitelist(self) -> tuple[str, ...]:
        extensions = self.source_config.get("extensions")
        if extensions is None:
            return DEFAULT_TEXT_EXTENSIONS
        normalized = tuple(ext.lower().lstrip(".") for ext in extensions if ext)
        return normalized or DEFAULT_TEXT_EXTENSIONS

    def _max_size(self) -> int:
        return int(self.source_config.get("max_file_size_bytes", DEFAULT_MAX_FILE_SIZE_BYTES))

    async def list_items(self) -> AsyncIterator[IngestionItem]:
        root = self._resolved_path()
        recursive = bool(self.source_config.get("recursive", True))
        extensions = self._extension_whitelist()
        max_size = self._max_size()
        per_file_metadata: dict[str, dict[str, Any]] = self.source_config.get("per_file_metadata") or {}

        iterator = root.rglob("*") if recursive else root.iterdir()
        for file_path in iterator:
            if not file_path.is_file():
                continue

            ext = file_path.suffix.lstrip(".").lower()
            if ext and ext not in extensions:
                continue

            try:
                stat = file_path.stat()
            except OSError:
                # Unreadable file: let the caller record it as skipped
                # at fetch time rather than silently dropping it here.
                stat = None

            size_bytes = stat.st_size if stat is not None else 0
            if size_bytes > max_size:
                # Skip oversized files; they'd blow up memory or
                # embedding budgets.
                continue

            # Use path relative to root as item_id so duplicate basenames
            # in different subfolders don't collide.
            rel = file_path.relative_to(root)
            item_metadata: dict[str, Any] = {
                "relative_path": str(rel),
                "modified_at": stat.st_mtime if stat is not None else None,
            }
            # Prefer the relative-path lookup so two files named ``invoice.pdf``
            # in different subfolders can carry different tags. Fall back to
            # bare filename for ergonomic batch tagging.
            override = per_file_metadata.get(str(rel)) or per_file_metadata.get(file_path.name)
            if override:
                item_metadata.update(override)
            yield IngestionItem(
                item_id=str(rel),
                display_name=file_path.name,
                mime_type=mimetypes.guess_type(file_path.name)[0],
                source_url=file_path.as_uri(),
                source_metadata=item_metadata,
                size_bytes=size_bytes,
            )

    async def fetch_content(self, item: IngestionItem) -> IngestionItemContent:
        root = self._resolved_path()
        # Reconstruct the absolute path from item_id, then re-verify it
        # stays under root — defense against someone mutating item_id
        # between list and fetch.
        candidate = (root / item.item_id).resolve()
        if candidate != root and not candidate.is_relative_to(root):
            msg = f"Refusing to read {candidate}: escaped folder root {root}."
            raise ValueError(msg)

        raw = candidate.read_bytes()
        return IngestionItemContent(raw_bytes=raw, file_name=candidate.name)

    def describe(self) -> dict[str, Any]:
        base = super().describe()
        config = dict(self.source_config)
        # Don't echo allow-list roots to unauthenticated surfaces.
        config.pop("allowed_roots", None)
        base["config"] = config
        return base
