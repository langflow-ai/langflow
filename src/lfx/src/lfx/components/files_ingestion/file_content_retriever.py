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
            "IMPORTANT: Pass ONLY the file path as a string argument (e.g., '/Users/name/document.txt'). "
            "Do NOT pass search results, Data objects, or other complex types. "
            "Returns: A Message containing the file's text content. "
            "Raises ValueError if file path is missing or file not found.",
            tool_mode=True,
        ),
        Output(
            display_name="Table",
            name="dataframe",
            method="retrieve_content_as_dataframe",
            info="Retrieves file content as a pandas DataFrame. "
            "IMPORTANT: Pass ONLY the file path as a string argument (e.g., '/Users/name/data.csv'). "
            "Do NOT pass search results, Data objects, or other complex types. "
            "Supported formats: CSV, Excel (.xlsx, .xls), Parquet, JSON, TSV. "
            "Returns: A DataFrame with the file's tabular data. "
            "Raises ValueError if file not found, unsupported format, or parsing fails.",
            tool_mode=True,
        ),
    ]

    def _is_likely_file_content(self, text: str, file_path: str) -> bool:
        """Heuristically determine whether Data.text is actual file content or metadata/summary text."""
        if not text:
            return False

        file_ext = Path(file_path).suffix.lower()
        stripped = text.lstrip()

        if stripped.startswith("## File Name") and "## File Path" in stripped and "## Overview" in stripped:
            return False

        if file_ext in {".csv", ".tsv"}:
            first_line = stripped.splitlines()[0] if stripped.splitlines() else ""
            return "," in first_line or "\t" in first_line

        if file_ext == ".json":
            return stripped.startswith(("{", "["))

        return True

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

        from lfx.schema.dataframe import DataFrame

        logger.debug(f"FileContentRetriever: Building file maps from {len(self.file_data)} input items")
        text_map: dict[str, str] = {}
        dataframe_map: dict[str, DataFrame] = {}

        for item in self.file_data:
            if isinstance(item, DataFrame):
                fp = item.attrs.get("source_file_path", "")
                if fp:
                    dataframe_map[fp] = item
                    if fp not in text_map:
                        text_map[fp] = item.to_csv(index=False)
                elif not item.empty and "file_path" in item.columns:
                    unique_paths = item["file_path"].dropna().unique()
                    for path in unique_paths:
                        path_str = str(path)
                        if path_str:
                            dataframe_map[path_str] = item
            elif isinstance(item, Data):
                fp = item.data.get("file_path", "")
                text = item.get_text() or ""
                if not fp:
                    continue

                if self._is_likely_file_content(text, fp):
                    text_map[fp] = text
                else:
                    logger.debug(
                        "FileContentRetriever: Skipping Data text for '%s'"
                        " because it looks like metadata/summary, not file content",
                        fp,
                    )

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
            # Return empty result when no path is provided (e.g., during tool building)
            logger.info("FileContentRetriever: No file path provided, returning empty Message")
            return Message(text="")

        # Get cached maps (built once and reused)
        text_map, _ = self._get_file_maps()
        content = text_map.get(query)

        if content is None:
            available = list(text_map.keys())
            msg = f"File '{query}' not found. Available files: {available}"
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
            # Return empty DataFrame when no path is provided (e.g., during tool building)
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
        _text_map, dataframe_map = self._get_file_maps()

        # Check if we have a DataFrame for this file
        if query in dataframe_map:
            df = dataframe_map[query]
            logger.info(
                f"FileContentRetriever: Successfully retrieved DataFrame for '{query}' "
                f"({len(df)} rows, {len(df.columns)} columns)"
            )
            return df

        available_prepared = list(dataframe_map.keys())
        if available_prepared:
            msg = (
                f"File '{query}' does not have a prepared DataFrame available. "
                "This component does not build DataFrames during tool calls. "
                "Prepare the DataFrame upstream and pass it through file_data. "
                f"Prepared DataFrame files: {available_prepared}"
            )
        else:
            msg = (
                f"File '{query}' does not have a prepared DataFrame available. "
                "No prepared DataFrames were provided in file_data. "
                "Prepare the DataFrame upstream and pass it through file_data."
            )
        logger.error(f"FileContentRetriever: {msg}")
        raise ValueError(msg)
