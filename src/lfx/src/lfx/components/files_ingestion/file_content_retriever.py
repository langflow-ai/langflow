"""Component that retrieves file content by path, for use as an agent tool.

Takes file data from a Read File component and allows an agent to look up
a specific file's content by providing its path.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from lfx.custom.custom_component.component import Component
from lfx.io import HandleInput, Output, QueryInput
from lfx.log.logger import logger
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message


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

    def __deepcopy__(self, memo: dict) -> FileContentRetrieverComponent:
        """Override deepcopy to preserve cached maps across tool invocations."""
        from copy import deepcopy as _deepcopy
        from typing import cast

        new_component = cast("FileContentRetrieverComponent", super().__deepcopy__(memo))
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

        logger.debug(f"FileContentRetriever: Building file maps from {len(self.file_data)} input items")
        text_map: dict[str, str] = {}
        dataframe_map: dict[str, DataFrame] = {}

        for item in self.file_data:
            if isinstance(item, DataFrame):
                fp = item.attrs.get("source_file_path", "")
                if fp:
                    dataframe_map[fp] = item
                elif not item.empty and "file_path" in item.columns:
                    # Multi-file DataFrame: one row per file with file_path and text columns.
                    # Extract each file's text content into text_map instead of mapping
                    # each path to the summary DataFrame (which is just the file index,
                    # not the actual file data).
                    has_text_col = "text" in item.columns
                    for _, row in item.iterrows():
                        path_str = str(row.get("file_path", ""))
                        if not path_str:
                            continue
                        if has_text_col and path_str not in text_map:
                            text = str(row["text"]) if pd.notna(row["text"]) else ""
                            if text:
                                text_map[path_str] = text
            elif isinstance(item, Message):
                fp = getattr(item, "file_path", "") or ""
                text = item.get_text() or ""
                if not fp:
                    continue
                if text:
                    text_map[fp] = text
            elif isinstance(item, Data):
                fp = item.data.get("file_path", "")
                text = item.get_text() or ""
                if not fp:
                    continue

                if text:
                    text_map[fp] = text
            else:
                logger.warning(
                    "FileContentRetriever: Unsupported input type %s, skipping",
                    type(item).__name__,
                )

        # For text entries that don't have a pre-built DataFrame, try to parse
        # CSV/TSV/JSON content into a DataFrame eagerly so it's ready for tool calls.
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

        self._cached_text_map = text_map
        self._cached_dataframe_map = dataframe_map

        _max_display = 5
        all_keys = {*text_map.keys(), *dataframe_map.keys()}
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
        return Message(text=content)

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
