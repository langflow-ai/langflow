"""Tests for langflow.api.utils.zip_utils module."""

import io
import zipfile

import pytest
from langflow.api.utils.zip_utils import (
    MAX_ZIP_ENTRIES,
    _extract_flows_sync,
    _ZipExtractionResult,
)


def _make_zip(files: dict[str, bytes]) -> bytes:
    """Helper to create a zip file in memory with the given filename->content mapping."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


class TestExtractFlowsSync:
    def test_single_valid_json(self):
        content = _make_zip({"flow.json": b'{"name": "test"}'})
        result = _extract_flows_sync(content)
        assert len(result.flows) == 1
        assert result.flows[0] == {"name": "test"}
        assert result.warnings == []

    def test_multiple_json_files(self):
        content = _make_zip(
            {
                "a.json": b'{"id": 1}',
                "b.json": b'{"id": 2}',
                "c.json": b'{"id": 3}',
            }
        )
        result = _extract_flows_sync(content)
        assert len(result.flows) == 3

    def test_non_json_files_ignored(self):
        content = _make_zip(
            {
                "flow.json": b'{"name": "test"}',
                "readme.txt": b"just text",
                "image.png": b"\x89PNG\r\n",
            }
        )
        result = _extract_flows_sync(content)
        assert len(result.flows) == 1

    def test_invalid_json_skipped_with_warning(self):
        content = _make_zip(
            {
                "good.json": b'{"name": "test"}',
                "bad.json": b"not valid json {{{",
            }
        )
        result = _extract_flows_sync(content)
        assert len(result.flows) == 1
        assert len(result.warnings) == 1
        assert "invalid JSON" in result.warnings[0]

    def test_bad_zip_raises_value_error(self):
        with pytest.raises(ValueError, match="not a valid ZIP archive"):
            _extract_flows_sync(b"not a zip file at all")

    def test_empty_zip(self):
        content = _make_zip({})
        result = _extract_flows_sync(content)
        assert result.flows == []
        assert result.warnings == []

    def test_case_insensitive_json_extension(self):
        content = _make_zip(
            {
                "FLOW.JSON": b'{"name": "upper"}',
                "Flow.Json": b'{"name": "mixed"}',
            }
        )
        result = _extract_flows_sync(content)
        assert len(result.flows) == 2

    def test_nested_json_in_directories(self):
        content = _make_zip(
            {
                "dir/flow.json": b'{"nested": true}',
            }
        )
        result = _extract_flows_sync(content)
        assert len(result.flows) == 1
        assert result.flows[0]["nested"] is True

    def test_too_many_entries_raises(self):
        files = {f"flow_{i}.json": b'{"id": 1}' for i in range(MAX_ZIP_ENTRIES + 1)}
        content = _make_zip(files)
        with pytest.raises(ValueError, match="exceeding the limit"):
            _extract_flows_sync(content)


class TestZipExtractionResult:
    def test_default_empty(self):
        r = _ZipExtractionResult()
        assert r.flows == []
        assert r.warnings == []

    def test_with_data(self):
        r = _ZipExtractionResult(flows=[{"a": 1}], warnings=["warn"])
        assert len(r.flows) == 1
        assert len(r.warnings) == 1
