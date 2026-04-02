"""Tests for cache utility functions."""

import base64
from unittest.mock import MagicMock

import pytest

from langflow.services.cache.utils import (
    CACHE_DIR,
    PREFIX,
    filter_json,
    save_binary_file,
    update_build_status,
)


class TestFilterJson:
    """Tests for filter_json function."""

    def test_removes_viewport(self):
        data = {"viewport": {"x": 0, "y": 0, "zoom": 1}, "nodes": []}
        result = filter_json(data)
        assert "viewport" not in result
        assert "nodes" in result

    def test_removes_chat_history(self):
        data = {"chatHistory": [{"msg": "hello"}], "edges": []}
        result = filter_json(data)
        assert "chatHistory" not in result
        assert "edges" in result

    def test_removes_node_position_fields(self):
        data = {
            "nodes": [
                {
                    "id": "node1",
                    "position": {"x": 100, "y": 200},
                    "positionAbsolute": {"x": 100, "y": 200},
                    "selected": True,
                    "dragging": False,
                    "data": {"type": "test"},
                }
            ]
        }
        result = filter_json(data)
        node = result["nodes"][0]
        assert "position" not in node
        assert "positionAbsolute" not in node
        assert "selected" not in node
        assert "dragging" not in node
        assert node["id"] == "node1"
        assert node["data"] == {"type": "test"}

    def test_preserves_other_fields(self):
        data = {"nodes": [], "edges": [], "custom_field": "value"}
        result = filter_json(data)
        assert result["custom_field"] == "value"

    def test_does_not_modify_original(self):
        data = {"viewport": {"x": 0}, "nodes": []}
        result = filter_json(data)
        assert "viewport" in data  # Original unchanged
        assert "viewport" not in result

    def test_empty_data(self):
        data = {}
        result = filter_json(data)
        assert result == {}

    def test_no_nodes(self):
        data = {"viewport": {"x": 0}}
        result = filter_json(data)
        assert "viewport" not in result


class TestSaveBinaryFile:
    """Tests for save_binary_file function."""

    def test_rejects_invalid_file_type(self):
        content = f"data:application/octet-stream;base64,{base64.b64encode(b'test').decode()}"
        with pytest.raises(ValueError, match="is not accepted"):
            save_binary_file(content, "test.exe", [".txt", ".json"])

    def test_rejects_empty_content(self):
        with pytest.raises(ValueError, match="reload the file"):
            save_binary_file("", "test.txt", [".txt"])

    def test_saves_valid_file(self, tmp_path):
        """Test saving a valid binary file."""
        encoded = base64.b64encode(b"hello world").decode()
        content = f"data:text/plain;base64,{encoded}"

        from unittest.mock import patch

        with patch("langflow.services.cache.utils.CACHE_DIR", str(tmp_path)):
            result = save_binary_file(content, "test.txt", [".txt"])
            assert result.endswith("test.txt")


class TestUpdateBuildStatus:
    """Tests for update_build_status function."""

    def test_updates_status(self):
        mock_cache = MagicMock()
        mock_cache.__getitem__ = MagicMock(return_value={"status": "building"})
        mock_cache.__setitem__ = MagicMock()

        update_build_status(mock_cache, "flow1", "completed")

        mock_cache.__setitem__.assert_called()

    def test_raises_when_flow_not_found(self):
        mock_cache = MagicMock()
        mock_cache.__getitem__ = MagicMock(return_value=None)

        with pytest.raises(ValueError, match="not found in cache"):
            update_build_status(mock_cache, "flow1", "completed")


class TestConstants:
    """Test cache constants."""

    def test_cache_dir_is_string(self):
        assert isinstance(CACHE_DIR, str)

    def test_prefix(self):
        assert PREFIX == "langflow_cache"
