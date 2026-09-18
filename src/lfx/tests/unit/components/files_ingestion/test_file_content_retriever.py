"""Tests for FileContentRetrieverComponent.

These tests verify that the FileContentRetriever correctly receives
and serves file content from various upstream input formats (Data objects,
DataFrames with attrs, DataFrames with file_path column).
"""

import os
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from lfx.components.files_ingestion.file_content_retriever import FileContentRetrieverComponent
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message
from lfx.utils.file_path_security import LocalFileAccessError

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


# ---------------------------------------------------------------------------
# Tests for persistent_dir local-file-access enforcement (security)
# ---------------------------------------------------------------------------


@contextmanager
def _mock_settings(*, restricted: bool, config_dir: str):
    with patch("lfx.utils.file_path_security.get_settings_service") as mock_get:
        settings = MagicMock()
        settings.settings.restrict_local_file_access = restricted
        settings.settings.config_dir = config_dir
        settings.settings.database_url = ""
        mock_get.return_value = settings
        yield


class TestPersistentDirFileAccess:
    """persistent_dir is tenant-controlled and must honor LANGFLOW_RESTRICT_LOCAL_FILE_ACCESS."""

    def test_arbitrary_persistent_dir_allowed_when_unrestricted(self, tmp_path):
        """OSS default (restriction off): any absolute persistent_dir keeps working."""
        persist = tmp_path / "attacker_dir"
        data = _make_data_with_content("/etc/hostname", "PAYLOAD")
        comp = _build_component(file_data=[data], persistent_dir=str(persist))

        with _mock_settings(restricted=False, config_dir=str(tmp_path)):
            comp._get_file_maps()

        assert (persist / "text_index.json").exists()
        assert (persist / "texts").is_dir()

    def test_persistent_dir_outside_scope_blocked_when_restricted(self, tmp_path):
        """Restricted mode: a persistent_dir outside the caller's storage scope is refused."""
        persist = tmp_path / "outside" / "attacker_dir"
        data = _make_data_with_content("/x", "PAYLOAD")
        comp = _build_component(file_data=[data], persistent_dir=str(persist))
        comp._user_id = "user-1"

        with (
            _mock_settings(restricted=True, config_dir=str(tmp_path)),
            pytest.raises(LocalFileAccessError),
        ):
            comp._get_file_maps()

        assert not persist.exists(), "No files may be created outside the storage scope"

    def test_persistent_dir_inside_scope_allowed_when_restricted(self, tmp_path):
        """Restricted mode: a persistent_dir inside the caller's storage scope still works."""
        persist = tmp_path / "user-1" / "persist"
        data = _make_data_with_content("/x", "PAYLOAD")
        comp = _build_component(file_data=[data], persistent_dir=str(persist))
        comp._user_id = "user-1"

        with _mock_settings(restricted=True, config_dir=str(tmp_path)):
            text_map, _ = comp._get_file_maps()

        assert text_map["/x"] == "PAYLOAD"
        assert (persist / "text_index.json").exists()

    def test_persistent_dir_without_scope_fails_closed_when_restricted(self, tmp_path):
        """Restricted mode with no authenticated user/flow scope must deny, not silently allow."""
        comp = _build_component(file_data=[], persistent_dir=str(tmp_path / "persist"))

        with (
            _mock_settings(restricted=True, config_dir=str(tmp_path)),
            pytest.raises(LocalFileAccessError, match="requires an authenticated user or flow scope"),
        ):
            comp._get_file_maps()

    def test_save_persistent_maps_enforces_restriction(self, tmp_path):
        """The write path itself must enforce containment, not only the load path."""
        comp = _build_component(persistent_dir=str(tmp_path / "outside"))
        comp._user_id = "user-1"

        with (
            _mock_settings(restricted=True, config_dir=str(tmp_path)),
            pytest.raises(LocalFileAccessError),
        ):
            comp._save_persistent_maps({"/x": "PAYLOAD"}, {})

        assert not (tmp_path / "outside").exists()


class TestPersistentIndexTraversal:
    """Index entry names from text_index.json / dataframe_index.json are untrusted."""

    def _stage_persistent_dir(self, tmp_path, index: dict) -> str:
        import json

        base = tmp_path / "persist"
        (base / "texts").mkdir(parents=True)
        (base / "text_index.json").write_text(json.dumps(index), encoding="utf-8")
        return str(base)

    def test_traversal_entry_does_not_read_outside_texts_dir(self, tmp_path):
        """A '../' entry in text_index.json must not escape the texts/ directory."""
        secret = tmp_path / "secret.txt"
        secret.write_text("SECRET_READ_VIA_TRAVERSAL", encoding="utf-8")
        persist = self._stage_persistent_dir(tmp_path, {"victim_key": "../../secret.txt"})
        comp = _build_component(file_data=[], persistent_dir=persist)

        with _mock_settings(restricted=False, config_dir=str(tmp_path)):
            text_map, _ = comp._load_persistent_maps()

        assert "victim_key" not in text_map
        assert all("SECRET_READ_VIA_TRAVERSAL" not in v for v in text_map.values())

    def test_absolute_path_entry_rejected(self, tmp_path):
        """An absolute-path entry in the index must be rejected."""
        secret = tmp_path / "secret.txt"
        secret.write_text("SECRET", encoding="utf-8")
        persist = self._stage_persistent_dir(tmp_path, {"victim_key": str(secret)})
        comp = _build_component(file_data=[], persistent_dir=persist)

        with _mock_settings(restricted=False, config_dir=str(tmp_path)):
            text_map, _ = comp._load_persistent_maps()

        assert text_map == {}

    def test_deep_traversal_entry_rejected(self, tmp_path):
        """Multi-level traversal entries (the PoC payload) must be rejected."""
        persist = self._stage_persistent_dir(tmp_path, {"victim_key": "../../../../etc/hostname"})
        comp = _build_component(file_data=[], persistent_dir=persist)

        with _mock_settings(restricted=False, config_dir=str(tmp_path)):
            text_map, _ = comp._load_persistent_maps()

        assert text_map == {}

    def test_legitimate_entry_still_loads(self, tmp_path):
        """A well-formed hash-style entry written by _save_persistent_maps must still load."""
        import json

        base = tmp_path / "persist"
        texts = base / "texts"
        texts.mkdir(parents=True)
        (texts / "abc123.txt").write_text("LEGIT CONTENT", encoding="utf-8")
        (base / "text_index.json").write_text(json.dumps({"/x": "abc123.txt"}), encoding="utf-8")
        comp = _build_component(file_data=[], persistent_dir=str(base))

        with _mock_settings(restricted=False, config_dir=str(tmp_path)):
            text_map, _ = comp._load_persistent_maps()

        assert text_map == {"/x": "LEGIT CONTENT"}

    def test_dataframe_index_traversal_rejected(self, tmp_path):
        """Traversal entries in dataframe_index.json must be rejected before any read.

        The external target exists on disk; containment must reject the entry without
        opening it (asserted via the read_parquet spy, since lfx has no parquet engine
        dependency to stage a real parquet file with).
        """
        import json

        secret = tmp_path / "secret.parquet"
        secret.write_bytes(b"PAR1-placeholder")
        base = tmp_path / "persist"
        (base / "dataframes").mkdir(parents=True)
        (base / "dataframe_index.json").write_text(json.dumps({"victim_key": "../../secret.parquet"}), encoding="utf-8")
        comp = _build_component(file_data=[], persistent_dir=str(base))

        with _mock_settings(restricted=False, config_dir=str(tmp_path)), patch.object(pd, "read_parquet") as mock_read:
            _, df_map = comp._load_persistent_maps()

        assert df_map == {}
        mock_read.assert_not_called()

    def test_nul_character_entry_rejected(self, tmp_path):
        """Entries containing NUL bytes must be rejected instead of reaching filesystem calls."""
        secret = tmp_path / "secret.txt"
        secret.write_text("SECRET", encoding="utf-8")
        persist = self._stage_persistent_dir(tmp_path, {"victim_key": "abc123.txt\x00/../../secret.txt"})
        comp = _build_component(file_data=[], persistent_dir=persist)

        with _mock_settings(restricted=False, config_dir=str(tmp_path)):
            text_map, _ = comp._load_persistent_maps()

        assert text_map == {}

    def test_nested_separator_entry_rejected(self, tmp_path):
        """Entries with path separators must be rejected even when the nested file exists."""
        import json

        base = tmp_path / "persist"
        nested = base / "texts" / "nested"
        nested.mkdir(parents=True)
        (nested / "evil.txt").write_text("NESTED CONTENT", encoding="utf-8")
        (base / "text_index.json").write_text(json.dumps({"victim_key": "nested/evil.txt"}), encoding="utf-8")
        comp = _build_component(file_data=[], persistent_dir=str(base))

        with _mock_settings(restricted=False, config_dir=str(tmp_path)):
            text_map, _ = comp._load_persistent_maps()

        assert text_map == {}

    def test_backslash_separator_entry_rejected(self, tmp_path):
        """Windows-style separators in entries must be rejected as well."""
        persist = self._stage_persistent_dir(tmp_path, {"victim_key": "..\\..\\secret.txt"})
        comp = _build_component(file_data=[], persistent_dir=persist)

        with _mock_settings(restricted=False, config_dir=str(tmp_path)):
            text_map, _ = comp._load_persistent_maps()

        assert text_map == {}

    @pytest.mark.skipif(os.name == "nt", reason="symlink creation requires privileges on Windows")
    def test_symlink_entry_escape_rejected(self, tmp_path):
        """A symlink planted inside texts/ pointing outside must not be followed."""
        import json

        secret = tmp_path / "secret.txt"
        secret.write_text("SECRET_VIA_SYMLINK", encoding="utf-8")
        base = tmp_path / "persist"
        texts = base / "texts"
        texts.mkdir(parents=True)
        (texts / "evil.txt").symlink_to(secret)
        (base / "text_index.json").write_text(json.dumps({"victim_key": "evil.txt"}), encoding="utf-8")
        comp = _build_component(file_data=[], persistent_dir=str(base))

        with _mock_settings(restricted=False, config_dir=str(tmp_path)):
            text_map, _ = comp._load_persistent_maps()

        assert "victim_key" not in text_map
        assert all("SECRET_VIA_SYMLINK" not in v for v in text_map.values())
