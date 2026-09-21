"""Component that retrieves file content by path, for use as an agent tool.

Takes file data from a Read File component and allows an agent to look up
a specific file's content by providing its path.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from lfx.custom.custom_component.component import Component
from lfx.inputs.inputs import StrInput
from lfx.io import HandleInput, Output, QueryInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message
from lfx.utils.file_path_security import component_file_access_scopes, enforce_local_file_access

if TYPE_CHECKING:
    from collections.abc import Iterator


class FileContentRetrieverComponent(Component):
    display_name = "File Content Retriever"
    description = (
        "Retrieves the text content of a file given its path. "
        "Connect to an agent as a tool so it can read file contents."
    )
    icon = "file-text"
    name = "FileContentRetriever"
    add_tool_output = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._cached_text_map: dict[str, str] | None = None
        self._cached_dataframe_map: dict[str, DataFrame] | None = None

    def __deepcopy__(self, memo: dict):
        """Override deepcopy to preserve cached maps across tool invocations."""
        from copy import deepcopy as _deepcopy

        new_component = super().__deepcopy__(memo)
        # Copy the cached maps so they don't need to be rebuilt, but avoid sharing mutable state
        new_component._cached_text_map = (  # noqa: SLF001
            _deepcopy(self._cached_text_map, memo) if self._cached_text_map else None
        )
        new_component._cached_dataframe_map = (  # noqa: SLF001
            _deepcopy(self._cached_dataframe_map, memo) if self._cached_dataframe_map else None
        )
        return new_component

    inputs = [
        HandleInput(
            name="file_data",
            display_name="File Data",
            input_types=["Data", "DataFrame", "Message"],
            is_list=True,
            info="Output from a Read File component.",
        ),
        StrInput(
            name="persistent_dir",
            display_name="Persistent Directory",
            value="",
            info="Optional directory for persisting file maps across runs. If empty, maps are kept in memory only.",
        ),
        QueryInput(
            name="file_path",
            display_name="File Path",
            info=(
                "The full file path as a string (e.g., '/path/to/file.csv'). "
                "Do not pass search results or other objects."
            ),
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(
            display_name="File Content",
            name="content",
            method="retrieve_content",
            info="Retrieves file content as text. "
            "IMPORTANT: Pass ONLY the file path as a string (e.g., '/Users/name/document.txt'). "
            "If you have search results from a vector store, you MUST extract the file_path string first. "
            "Example: file_path = result['data']['file_path'], then call retrieve_content(file_path). "
            "Returns: A Message containing the file's text content. "
            "Raises ValueError if file path is missing or file not found.",
            tool_mode=True,
        ),
        Output(
            display_name="Table",
            name="dataframe",
            method="retrieve_content_as_dataframe",
            info="Retrieves file content as a pandas DataFrame. "
            "IMPORTANT: Pass ONLY the file path as a string (e.g., '/Users/name/data.csv'). "
            "If you have search results from a vector store, you MUST extract the file_path string first. "
            "Example: file_path = result['data']['file_path'], then call retrieve_content_as_dataframe(file_path). "
            "Supported formats: CSV, Excel (.xlsx, .xls), Parquet, JSON, TSV. "
            "Returns: A DataFrame with the file's tabular data. "
            "Raises ValueError if file not found, unsupported format, or parsing fails.",
            tool_mode=True,
        ),
    ]

    # ---- Persistence helpers ----

    @staticmethod
    def _path_hash(file_path: str) -> str:
        """Return a short hash for use as a safe filename."""
        return hashlib.sha256(file_path.encode()).hexdigest()[:16]

    def _resolve_persistent_base(self) -> Path:
        """Validate persistent_dir against local-file-access restrictions before use.

        persistent_dir is a tenant-controlled input field. Without containment it can point
        at any absolute server path, letting this component read/write outside the
        authenticated user's storage scope even when LANGFLOW_RESTRICT_LOCAL_FILE_ACCESS
        is enabled. When the restriction is disabled (OSS default) this is a no-op and the
        path is used as-is, preserving single-tenant behavior.
        """
        return enforce_local_file_access(
            Path(self.persistent_dir).expanduser(),
            scope_ids=component_file_access_scopes(self),
        )

    @staticmethod
    def _resolve_scoped_dir(base: Path, name: str) -> Path | None:
        """Resolve ``base/name`` and require it to stay inside the authorized *base*.

        ``texts`` / ``dataframes`` are children of a validated directory, but a child
        can be a symlink: if it points outside, its own resolved path is outside too,
        so anything checked against *it* is checked against the wrong boundary. The
        authorized base is the only boundary that means anything here, and it must be
        resolved first so a symlinked base is compared like with like.
        """
        resolved_base = base.resolve()
        candidate = (resolved_base / name).resolve()
        if candidate != resolved_base and not candidate.is_relative_to(resolved_base):
            logger.warning(
                f"FileContentRetriever: Refusing directory '{name}': resolves outside the persistent directory."
            )
            return None
        return candidate

    @staticmethod
    def _resolve_index_entry(index_dir: Path, entry_name: object, authorized_base: Path | None = None) -> Path | None:
        """Resolve an index-listed file name, rejecting anything outside the authorized base.

        Index files (text_index.json / dataframe_index.json) may be staged or tampered
        with, so entry names are untrusted. Names with path separators or traversal
        sequences are refused, and the resolved path must stay inside *authorized_base*
        - the directory the access check actually approved. Validating against
        *index_dir* alone is not enough: if that child directory is itself a symlink out
        of the base, both it and the candidate resolve outside and the comparison
        succeeds against a boundary that was never authorized.
        """
        if not isinstance(entry_name, str) or not entry_name:
            return None
        if ".." in entry_name or any(char in entry_name for char in ("/", "\\", "\x00")):
            logger.warning(
                f"FileContentRetriever: Ignoring index entry '{entry_name}': contains path separators "
                "or traversal sequences."
            )
            return None
        boundary = (authorized_base if authorized_base is not None else index_dir).resolve()
        candidate = (index_dir.resolve() / entry_name).resolve()
        if candidate != boundary and not candidate.is_relative_to(boundary):
            logger.warning(
                f"FileContentRetriever: Ignoring index entry '{entry_name}': resolves outside the "
                "authorized persistent directory."
            )
            return None
        return candidate

    @staticmethod
    def _resolve_write_target(index_dir: Path, name: str, authorized_base: Path) -> Path:
        """Return the path to write *name* to, refusing one that escapes *authorized_base*.

        ``_resolve_scoped_dir`` keeps the parent directory in scope, but the final
        filename can be a symlink of its own: ``write_text()`` and ``to_parquet()``
        follow it and overwrite whatever it points at. The component owns these hashed
        names, so a link sitting on one was planted by somebody else - refuse it, and
        re-check the resolved path against the authorized base.
        """
        target = index_dir / name
        if target.is_symlink():
            msg = f"FileContentRetriever: persistence target '{name}' is a symlink; refusing to write through it."
            raise ValueError(msg)
        if not target.resolve().is_relative_to(authorized_base.resolve()):
            msg = (
                f"FileContentRetriever: persistence target '{name}' resolves outside the persistent "
                "directory; refusing to persist."
            )
            raise ValueError(msg)
        return target

    def _load_persistent_maps(self) -> tuple[dict[str, str], dict[str, DataFrame]]:
        """Load maps from the persistent directory. Returns ({}, {}) if nothing on disk."""
        base = self._resolve_persistent_base()
        text_map: dict[str, str] = {}
        dataframe_map: dict[str, DataFrame] = {}

        # Load text files: index maps file_path -> text filename on disk
        text_index_file = base / "text_index.json"
        text_dir = base / "texts"
        if text_index_file.exists() and text_dir.exists():
            try:
                index = json.loads(text_index_file.read_text(encoding="utf-8"))
                for fp, txt_name in index.items():
                    txt_path = self._resolve_index_entry(text_dir, txt_name, base)
                    if txt_path is not None and txt_path.exists():
                        try:
                            text_map[fp] = txt_path.read_text(encoding="utf-8")
                        except OSError as e:
                            logger.warning(f"FileContentRetriever: Failed to load text for '{fp}': {e}")
                logger.debug(f"FileContentRetriever: Loaded {len(text_map)} text entries from disk")
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"FileContentRetriever: Failed to load text_index.json: {e}")

        # Load DataFrames: index maps file_path -> parquet filename on disk
        df_index_file = base / "dataframe_index.json"
        df_dir = base / "dataframes"
        if df_index_file.exists() and df_dir.exists():
            try:
                index = json.loads(df_index_file.read_text(encoding="utf-8"))
                for fp, parquet_name in index.items():
                    pq_path = self._resolve_index_entry(df_dir, parquet_name, base)
                    if pq_path is not None and pq_path.exists():
                        try:
                            dataframe_map[fp] = DataFrame(pd.read_parquet(pq_path))
                            dataframe_map[fp].attrs["source_file_path"] = fp
                        except Exception as e:  # noqa: BLE001
                            logger.warning(f"FileContentRetriever: Failed to load parquet for '{fp}': {e}")
                logger.debug(f"FileContentRetriever: Loaded {len(dataframe_map)} dataframes from disk")
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"FileContentRetriever: Failed to load dataframe_index.json: {e}")

        return text_map, dataframe_map

    def _save_persistent_maps(self, text_map: dict[str, str], dataframe_map: dict[str, DataFrame]) -> None:
        """Save maps to the persistent directory (atomic writes)."""
        base = self._resolve_persistent_base()
        base.mkdir(parents=True, exist_ok=True)
        # Resolve the children against the authorized base before writing: this
        # loop also unlinks orphans, so a "texts" symlink pointing out of the
        # base would delete files outside it, not merely write to them.
        text_dir = self._resolve_scoped_dir(base, "texts")
        df_dir = self._resolve_scoped_dir(base, "dataframes")
        if text_dir is None or df_dir is None:
            msg = (
                "FileContentRetriever: persistent directory contains a 'texts' or 'dataframes' entry that "
                "resolves outside it; refusing to persist."
            )
            raise ValueError(msg)
        text_dir.mkdir(exist_ok=True)
        df_dir.mkdir(exist_ok=True)

        # Validate every output path before writing anything: an in-scope directory can
        # still hold a symlinked leaf, and refusing halfway through would leave part of
        # the escape carried out.
        text_index: dict[str, str] = {fp: f"{self._path_hash(fp)}.txt" for fp in text_map}
        df_index: dict[str, str] = {fp: f"{self._path_hash(fp)}.parquet" for fp in dataframe_map}
        text_targets = {fp: self._resolve_write_target(text_dir, name, base) for fp, name in text_index.items()}
        df_targets = {fp: self._resolve_write_target(df_dir, name, base) for fp, name in df_index.items()}

        # Save each text entry as a separate file
        for fp, text in text_map.items():
            with self._atomic_target(text_targets[fp]) as tmp:
                tmp.write_text(text, encoding="utf-8")

        # Atomic write for text_index.json
        self._atomic_json_write(base / "text_index.json", text_index)

        # Save each DataFrame as parquet
        for fp, df in dataframe_map.items():
            with self._atomic_target(df_targets[fp]) as tmp:
                df.to_parquet(tmp, index=False)

        # Atomic write for dataframe_index.json
        self._atomic_json_write(base / "dataframe_index.json", df_index)

        # Clean up orphaned files on disk
        valid_txt_files = set(text_index.values())
        for f in text_dir.iterdir():
            if f.name not in valid_txt_files:
                f.unlink(missing_ok=True)
        valid_pq_files = set(df_index.values())
        for f in df_dir.iterdir():
            if f.name not in valid_pq_files:
                f.unlink(missing_ok=True)

        logger.debug(f"FileContentRetriever: Saved {len(text_map)} text + {len(dataframe_map)} dataframes to '{base}'")

    @staticmethod
    @contextmanager
    def _atomic_target(target: Path) -> Iterator[Path]:
        """Yield a temp sibling to write into, then move it onto *target*.

        ``Path.replace`` acts on the path itself rather than on what it points to, so a
        symlink sitting at *target* is replaced instead of written through - the payload
        cannot land outside the directory even if the link appears between the check in
        ``_resolve_write_target`` and this write.
        """
        fd, tmp_name = tempfile.mkstemp(dir=str(target.parent), suffix=".tmp")
        tmp = Path(tmp_name)
        try:
            os.close(fd)
            yield tmp
            tmp.replace(target)
        finally:
            tmp.unlink(missing_ok=True)

    @classmethod
    def _atomic_json_write(cls, target: Path, data: dict) -> None:
        """Write JSON atomically via temp file + rename."""
        with cls._atomic_target(target) as tmp, tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    # ---- Map building helpers ----

    def _build_maps_from_input(
        self,
        skip_paths: set[str] | None = None,
    ) -> tuple[dict[str, str], dict[str, DataFrame]]:
        """Build text and dataframe maps from self.file_data, skipping paths in *skip_paths*."""
        skip = skip_paths or set()
        text_map: dict[str, str] = {}
        dataframe_map: dict[str, DataFrame] = {}

        if not self.file_data:
            return text_map, dataframe_map

        for item in self.file_data:
            if isinstance(item, DataFrame):
                fp = item.attrs.get("source_file_path", "")
                if fp and fp not in skip:
                    dataframe_map[fp] = item
                elif not item.empty and "file_path" in item.columns:
                    has_text_col = "text" in item.columns
                    for _, row in item.iterrows():
                        path_str = str(row.get("file_path", ""))
                        if not path_str or path_str in skip:
                            continue
                        if has_text_col and path_str not in text_map:
                            text = str(row["text"]) if pd.notna(row["text"]) else ""
                            if text:
                                text_map[path_str] = text
            elif isinstance(item, Message):
                fp = getattr(item, "file_path", "") or ""
                text = item.get_text() or ""
                if not fp or fp in skip:
                    continue
                if text:
                    text_map[fp] = text
            elif isinstance(item, Data):
                fp = item.data.get("file_path", "")
                text = item.get_text() or ""
                if not fp or fp in skip:
                    continue
                if text:
                    text_map[fp] = text
            else:
                logger.warning(
                    "FileContentRetriever: Unsupported input type %s, skipping",
                    type(item).__name__,
                )

        return text_map, dataframe_map

    def _collect_input_paths(self) -> set[str]:
        """Collect all file paths present in the current file_data input."""
        paths: set[str] = set()
        if not self.file_data:
            return paths
        for item in self.file_data:
            if isinstance(item, DataFrame):
                fp = item.attrs.get("source_file_path", "")
                if fp:
                    paths.add(fp)
                elif not item.empty and "file_path" in item.columns:
                    paths.update(str(p) for p in item["file_path"].dropna() if p)
            elif isinstance(item, Message):
                fp = getattr(item, "file_path", "") or ""
                if fp:
                    paths.add(fp)
            elif isinstance(item, Data):
                fp = item.data.get("file_path", "")
                if fp:
                    paths.add(fp)
        return paths

    @staticmethod
    def _parse_text_to_dataframes(text_map: dict[str, str], dataframe_map: dict[str, DataFrame]) -> None:
        """Eagerly parse CSV/TSV/JSON text entries into DataFrames."""
        from io import StringIO

        for fp, text in text_map.items():
            if fp in dataframe_map:
                continue
            ext = Path(fp).suffix.lower()
            try:
                if ext == ".csv":
                    df = DataFrame(pd.read_csv(StringIO(text)))
                elif ext == ".tsv":
                    df = DataFrame(pd.read_csv(StringIO(text), sep="\t"))
                elif ext == ".json":
                    df = DataFrame(pd.read_json(StringIO(text)))
                else:
                    continue
                df.attrs["source_file_path"] = fp
                dataframe_map[fp] = df
                logger.debug(f"FileContentRetriever: Parsed text into DataFrame for '{fp}'")
            except (ValueError, pd.errors.ParserError) as e:
                logger.debug(f"FileContentRetriever: Could not parse text as DataFrame for '{fp}': {e}")

    # ---- Main entry point ----

    def _get_file_maps(self) -> tuple[dict[str, str], dict[str, DataFrame]]:
        """Get cached file maps or build them if not cached.

        Returns:
            tuple: (text_map, dataframe_map)
                - text_map: file_path -> text content
                - dataframe_map: file_path -> DataFrame
        """
        if self._cached_text_map is not None and self._cached_dataframe_map is not None:
            logger.debug(
                f"FileContentRetriever: Using cached maps - "
                f"{len(self._cached_text_map)} text files, {len(self._cached_dataframe_map)} dataframes"
            )
            return self._cached_text_map, self._cached_dataframe_map

        text_map: dict[str, str] = {}
        dataframe_map: dict[str, DataFrame] = {}

        # Load persisted maps if a persistent directory is configured
        has_persistent = bool(getattr(self, "persistent_dir", ""))
        if has_persistent:
            text_map, dataframe_map = self._load_persistent_maps()

        # Merge new input data — new input overwrites persisted entries for the same path
        # so that updated files are never served stale from the cache.
        new_text, new_df = self._build_maps_from_input()
        text_map.update(new_text)
        dataframe_map.update(new_df)

        # Eager CSV/TSV/JSON parsing
        self._parse_text_to_dataframes(text_map, dataframe_map)

        # Auto-sync: remove persisted entries no longer in file_data input
        # Only sync when file_data is non-empty (tool calls have empty file_data)
        maps_changed = bool(new_text or new_df)
        if has_persistent and self.file_data:
            input_paths = self._collect_input_paths()
            if input_paths:
                stale = {*text_map, *dataframe_map} - input_paths
                if stale:
                    for path in stale:
                        text_map.pop(path, None)
                        dataframe_map.pop(path, None)
                    logger.info(f"FileContentRetriever: Removed {len(stale)} stale entries: {sorted(stale)}")
                    maps_changed = True

        # Persist updated maps if directory is configured and maps changed
        if has_persistent and maps_changed:
            self._save_persistent_maps(text_map, dataframe_map)

        self._cached_text_map = text_map
        self._cached_dataframe_map = dataframe_map

        _max_display = 5
        all_keys = {*text_map.keys(), *dataframe_map.keys()}
        if not all_keys:
            logger.warning(
                "FileContentRetriever: Maps are empty — no files were loaded. "
                "Check that file_data is connected and contains valid files with file_path metadata."
            )
        else:
            logger.info(
                f"FileContentRetriever: Built and cached maps - "
                f"{len(text_map)} text files, {len(dataframe_map)} dataframes. "
                f"Available files: {list(all_keys)[:_max_display]}"
                f"{'...' if len(all_keys) > _max_display else ''}"
            )

        return text_map, dataframe_map

    def retrieve_content(self, file_path: str = "") -> Message:
        """Retrieve file content as text.

        Args:
            file_path: The full file path as a string (e.g., '/path/to/file.txt').

        Returns:
            Message: The file content as text, or empty Message if no path provided.

        Raises:
            ValueError: If file not found.
        """
        # Use explicit argument, fallback to self.file_path for backward compatibility
        query = file_path or self.file_path

        logger.debug(
            f"FileContentRetriever.retrieve_content called - "
            f"arg file_path='{file_path}', self.file_path='{self.file_path}', query='{query}'"
        )

        if not query:
            # Eagerly build maps so they're cached before deepcopy in tool calls
            self._get_file_maps()
            logger.info("FileContentRetriever: No file path provided, returning empty Message")
            return Message(text="")

        # Get cached maps (built once and reused)
        text_map, dataframe_map = self._get_file_maps()
        content = text_map.get(query)

        # Fall back to CSV representation of DataFrame if no text content
        if content is None and query in dataframe_map:
            content = dataframe_map[query].to_csv(index=False)

        if content is None:
            available = sorted({*text_map.keys(), *dataframe_map.keys()})
            preview = available[:5]
            extra = f" (and {len(available) - 5} more)" if len(available) > 5 else ""  # noqa: PLR2004
            msg = f"File '{query}' not found. Available files: {preview}{extra}"
            logger.error(f"FileContentRetriever: {msg}")
            raise ValueError(msg)

        logger.info(f"FileContentRetriever: Successfully retrieved content for '{query}' ({len(content)} chars)")
        return Message(text=content, file_path=query)

    def retrieve_content_as_dataframe(self, file_path: str = "") -> DataFrame:
        """Retrieve file content as a DataFrame for tabular data files.

        Args:
            file_path: The full file path as a string (e.g., '/path/to/file.csv').

        Returns:
            DataFrame: The file content as a pandas DataFrame, or empty DataFrame if no path provided.

        Raises:
            ValueError: If file not found or file type is not supported.
        """
        # Supported tabular file extensions
        tabular_extensions = {".csv", ".xlsx", ".xls", ".parquet", ".json", ".tsv"}

        # Use explicit argument, fallback to self.file_path for backward compatibility
        query = file_path or self.file_path

        logger.debug(
            f"FileContentRetriever.retrieve_content_as_dataframe called - "
            f"arg file_path='{file_path}', self.file_path='{self.file_path}', query='{query}', "
            f"type(file_path)={type(file_path)}, repr(file_path)={file_path!r}"
        )

        if not query:
            # Eagerly build maps so they're cached before deepcopy in tool calls
            self._get_file_maps()
            logger.info("FileContentRetriever: No file path provided, returning empty DataFrame")
            return DataFrame(pd.DataFrame())

        # Check file extension
        file_ext = Path(query).suffix.lower()
        if file_ext not in tabular_extensions:
            supported = ", ".join(sorted(tabular_extensions))
            msg = (
                f"File type '{file_ext}' is not supported for DataFrame conversion. "
                f"Supported formats: {supported}. "
                f"File: '{query}'"
            )
            logger.error(f"FileContentRetriever: {msg}")
            raise ValueError(msg)

        # Get cached maps (built once and reused)
        text_map, dataframe_map = self._get_file_maps()

        # Check if we have a DataFrame for this file
        if query in dataframe_map:
            df = dataframe_map[query]
            logger.info(
                f"FileContentRetriever: Successfully retrieved DataFrame for '{query}' "
                f"({len(df)} rows, {len(df.columns)} columns)"
            )
            return df

        available = sorted({*text_map.keys(), *dataframe_map.keys()})
        max_preview = 5
        preview = available[:max_preview]
        extra = f" (and {len(available) - max_preview} more)" if len(available) > max_preview else ""
        if available:
            msg = f"File '{query}' not found. Available: {preview}{extra}"
        else:
            msg = f"File '{query}' not found. No files were provided in file_data."
        logger.error(f"FileContentRetriever: {msg}")
        raise ValueError(msg)
