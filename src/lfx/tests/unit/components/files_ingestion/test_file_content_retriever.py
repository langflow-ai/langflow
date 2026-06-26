"""Tests for FileContentRetrieverComponent.

These tests verify that the FileContentRetriever correctly receives
and serves file content from various upstream input formats (Data objects,
DataFrames with attrs, DataFrames with file_path column).
"""

import pandas as pd
import pytest
from lfx.components.files_ingestion.file_content_retriever import FileContentRetrieverComponent
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message

# -- Helpers to build realistic upstream outputs --

CSV_CONTENT = "name,price,neighbourhood\nCozy Apt,150,Brooklyn\nLuxury Loft,500,Manhattan\nBudget Room,45,Queens\n"

CSV_METADATA_SUMMARY = (
    "## File Name\nairbnbs.csv\n\n"
    "## File Path\n/tmp/airbnbs.csv\n\n"
    "## Overview\nThe original file is a CSV dataset containing Airbnb listings.\n\n"
    "## Document Type\ndataset\n"
)


def _make_structured_dataframe(file_path: str) -> DataFrame:
    """Simulate single-file Read File 'Structured Content' output (load_files_structured).

    This is what Read File produces for a single CSV: a DataFrame whose rows are
    the actual CSV rows, with attrs["source_file_path"] set.
    """
    df = DataFrame(
        [
            {"name": "Cozy Apt", "price": 150, "neighbourhood": "Brooklyn"},
            {"name": "Luxury Loft", "price": 500, "neighbourhood": "Manhattan"},
            {"name": "Budget Room", "price": 45, "neighbourhood": "Queens"},
        ]
    )
    df.attrs["source_file_path"] = file_path
    return df


def _make_multi_file_dataframe(file_paths: list[str]) -> DataFrame:
    """Simulate multi-file Read File 'Files' output (load_files).

    This is what Read File produces for multiple files: one row per file,
    with file_path and text columns.  The text is a metadata summary, NOT
    the raw file content.
    """
    rows = [{"file_path": fp, "text": CSV_METADATA_SUMMARY} for fp in file_paths]
    return DataFrame(rows)


def _make_data_with_content(file_path: str, text: str) -> Data:
    """Create a Data object that carries actual file content in its text field."""
    return Data(data={"file_path": file_path, "text": text})


def _make_data_with_metadata(file_path: str) -> Data:
    """Create a Data object whose text is a metadata summary (not raw content)."""
    return Data(data={"file_path": file_path, "text": CSV_METADATA_SUMMARY})


def _build_component(**overrides) -> FileContentRetrieverComponent:
    comp = FileContentRetrieverComponent()
    for k, v in overrides.items():
        setattr(comp, k, v)
    return comp


# ---------------------------------------------------------------------------
# Tests for _get_file_maps
# ---------------------------------------------------------------------------


class TestGetFileMaps:
    """Verify _get_file_maps correctly builds text_map and dataframe_map."""

    def test_structured_dataframe_populates_dataframe_map(self):
        """A single-file structured DataFrame (attrs path) should appear in dataframe_map."""
        fp = "/tmp/airbnbs.csv"
        df = _make_structured_dataframe(fp)
        comp = _build_component(file_data=[df])

        _text_map, df_map = comp._get_file_maps()

        assert fp in df_map, "Structured DataFrame should be in dataframe_map"

    def test_structured_dataframe_has_all_rows(self):
        """The DataFrame stored in dataframe_map must contain ALL rows, not a summary."""
        fp = "/tmp/airbnbs.csv"
        df = _make_structured_dataframe(fp)
        comp = _build_component(file_data=[df])

        _text_map, df_map = comp._get_file_maps()

        stored_df = df_map[fp]
        assert len(stored_df) == 3, f"Expected 3 data rows, got {len(stored_df)}"
        assert set(stored_df.columns) == {"name", "price", "neighbourhood"}

    def test_data_with_real_content_populates_text_map(self):
        """Data objects whose text IS file content should end up in text_map."""
        fp = "/tmp/airbnbs.csv"
        data = _make_data_with_content(fp, CSV_CONTENT)
        comp = _build_component(file_data=[data])

        text_map, _df_map = comp._get_file_maps()

        assert fp in text_map
        assert text_map[fp] == CSV_CONTENT

    def test_data_with_metadata_summary_still_stored(self):
        """Data objects whose text is a metadata summary should still be stored in text_map."""
        fp = "/tmp/airbnbs.csv"
        data = _make_data_with_metadata(fp)
        comp = _build_component(file_data=[data])

        text_map, _df_map = comp._get_file_maps()

        assert fp in text_map

    def test_multi_file_dataframe_maps_each_file_to_text(self):
        """Multi-file DataFrame (file_path column) should map each unique path to text_map."""
        fps = ["/tmp/airbnbs.csv", "/tmp/tripadvisor.csv"]
        df = _make_multi_file_dataframe(fps)
        comp = _build_component(file_data=[df])

        text_map, _df_map = comp._get_file_maps()

        for fp in fps:
            assert fp in text_map, f"Expected '{fp}' in text_map"

    def test_multi_file_dataframe_does_not_return_summary_as_data(self):
        """BUG REPRO: summary DataFrame should not be returned as file data.

        When Read File outputs a 2-row summary DataFrame (one row per file,
        columns = [file_path, text]), the retriever should NOT return that 2-row summary
        as the file's data. It should either have actual parsed data or raise clearly.

        This reproduces the real-world scenario:
        - Read File with 2 CSV files outputs a DataFrame with 2 rows, 2 columns
        - FileContentRetriever maps each file_path to that same 2-row DataFrame
        - Agent gets back 2 rows instead of thousands of actual data rows
        """
        fps = ["/tmp/airbnbs.csv", "/tmp/tripadvisor.csv"]
        df = _make_multi_file_dataframe(fps)
        comp = _build_component(file_data=[df])

        _text_map, df_map = comp._get_file_maps()

        for fp in fps:
            if fp in df_map:
                stored_df = df_map[fp]
                # The stored DataFrame should NOT be the 2-row summary table.
                # If it has a "file_path" column and only 2 rows, that's the summary, not data.
                is_summary = (
                    "file_path" in stored_df.columns
                    and len(stored_df) == len(fps)
                    and set(stored_df.columns) == {"file_path", "text"}
                )
                assert not is_summary, (
                    f"dataframe_map['{fp}'] contains the summary DataFrame "
                    f"(shape={stored_df.shape}, cols={list(stored_df.columns)}) "
                    f"instead of the actual file data. The agent will get 2 rows "
                    f"instead of the real data."
                )

    def test_multi_file_text_content_available(self):
        """Multi-file DataFrame text content should be in text_map.

        When Read File outputs a multi-file DataFrame where the 'text' column
        contains actual CSV content, that content should be available via text_map
        so retrieve_content can return it.
        """
        fp = "/tmp/airbnbs.csv"
        csv_text = "name,price\nCozy Apt,150\nLuxury Loft,500\n"
        df = DataFrame(
            [
                {"file_path": fp, "text": csv_text},
            ]
        )
        comp = _build_component(file_data=[df])

        text_map, _df_map = comp._get_file_maps()

        assert fp in text_map, f"File '{fp}' should be in text_map when the text column contains CSV content"
        assert text_map[fp] == csv_text


# ---------------------------------------------------------------------------
# Tests for retrieve_content
# ---------------------------------------------------------------------------


class TestRetrieveContent:
    """Verify retrieve_content returns the correct text for a given file path."""

    def test_retrieve_from_structured_dataframe(self):
        """retrieve_content should return CSV text for a structured DataFrame file."""
        fp = "/tmp/airbnbs.csv"
        df = _make_structured_dataframe(fp)
        comp = _build_component(file_data=[df], file_path=fp)

        result = comp.retrieve_content()

        assert isinstance(result, Message)
        text = result.get_text()
        assert "Cozy Apt" in text
        assert "Luxury Loft" in text
        assert "Budget Room" in text

    def test_retrieve_from_data_with_content(self):
        """retrieve_content should return the raw text from a Data object."""
        fp = "/tmp/airbnbs.csv"
        data = _make_data_with_content(fp, CSV_CONTENT)
        comp = _build_component(file_data=[data], file_path=fp)

        result = comp.retrieve_content()

        assert result.get_text() == CSV_CONTENT

    def test_retrieve_missing_file_raises_value_error(self):
        """retrieve_content should raise ValueError for an unknown file path."""
        comp = _build_component(file_data=[], file_path="/tmp/nonexistent.csv")

        with pytest.raises(ValueError, match="not found"):
            comp.retrieve_content()

    def test_retrieve_no_path_returns_empty(self):
        """retrieve_content with no path should return an empty Message."""
        comp = _build_component(file_data=[], file_path="")

        result = comp.retrieve_content()

        assert result.get_text() == ""

    def test_retrieve_with_explicit_argument(self):
        """retrieve_content(file_path=...) should use the explicit arg over self.file_path."""
        fp = "/tmp/airbnbs.csv"
        df = _make_structured_dataframe(fp)
        comp = _build_component(file_data=[df], file_path="/tmp/wrong.csv")

        result = comp.retrieve_content(file_path=fp)

        assert "Cozy Apt" in result.get_text()


# ---------------------------------------------------------------------------
# Tests for retrieve_content_as_dataframe
# ---------------------------------------------------------------------------


class TestRetrieveContentAsDataframe:
    """Verify retrieve_content_as_dataframe returns the right DataFrame."""

    def test_retrieve_structured_dataframe(self):
        """Should return the original structured DataFrame with all rows and columns."""
        fp = "/tmp/airbnbs.csv"
        df = _make_structured_dataframe(fp)
        comp = _build_component(file_data=[df], file_path=fp)

        result = comp.retrieve_content_as_dataframe()

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 3, f"Expected 3 rows, got {len(result)}"
        assert "price" in result.columns

    def test_retrieve_dataframe_unsupported_extension_raises(self):
        """Should raise ValueError for non-tabular file types."""
        fp = "/tmp/readme.txt"
        data = _make_data_with_content(fp, "hello world")
        comp = _build_component(file_data=[data], file_path=fp)

        with pytest.raises(ValueError, match="not supported"):
            comp.retrieve_content_as_dataframe()

    def test_retrieve_dataframe_missing_file_raises(self):
        """Should raise ValueError when file is not found at all."""
        fp = "/tmp/nonexistent.csv"
        comp = _build_component(file_data=[], file_path=fp)

        with pytest.raises(ValueError, match="not found"):
            comp.retrieve_content_as_dataframe()

    def test_retrieve_from_multi_file_dataframe_via_text_fallback(self):
        """retrieve_content should return text from a multi-file DataFrame's text column."""
        fp = "/tmp/airbnbs.csv"
        csv_text = "name,price\nCozy Apt,150\nLuxury Loft,500\n"
        df = DataFrame([{"file_path": fp, "text": csv_text}])
        comp = _build_component(file_data=[df], file_path=fp)

        result = comp.retrieve_content()

        assert result.get_text() == csv_text

    def test_retrieve_dataframe_parses_csv_text_on_demand(self):
        """CSV text in text_map should be parsed into a DataFrame eagerly.

        When no pre-built DataFrame exists but text_map has CSV content,
        retrieve_content_as_dataframe should return the parsed DataFrame.
        """
        fp = "/tmp/airbnbs.csv"
        csv_text = "name,price\nCozy Apt,150\nLuxury Loft,500\n"
        df = DataFrame([{"file_path": fp, "text": csv_text}])
        comp = _build_component(file_data=[df], file_path=fp)

        result = comp.retrieve_content_as_dataframe()

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert "price" in result.columns
        assert list(result["name"]) == ["Cozy Apt", "Luxury Loft"]

    def test_retrieve_no_path_returns_empty_dataframe(self):
        """With no path, should return an empty DataFrame."""
        comp = _build_component(file_data=[], file_path="")

        result = comp.retrieve_content_as_dataframe()

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# Tests for caching
# ---------------------------------------------------------------------------


class TestCaching:
    """Verify that file maps are cached and reused across calls."""

    def test_maps_are_cached(self):
        fp = "/tmp/airbnbs.csv"
        df = _make_structured_dataframe(fp)
        comp = _build_component(file_data=[df])

        text_map1, df_map1 = comp._get_file_maps()
        text_map2, df_map2 = comp._get_file_maps()

        assert text_map1 is text_map2
        assert df_map1 is df_map2
