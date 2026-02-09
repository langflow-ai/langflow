"""Tests for flow loader utilities.

Tests the flow path resolution, path traversal validation,
and Python/JSON flow loading functionality.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from langflow.agentic.services.helpers.flow_loader import (
    _load_graph_from_python,
    _temporary_sys_path,
    _validate_path_within_base,
    load_graph_for_execution,
    resolve_flow_path,
)


class TestTemporarySysPath:
    """Tests for _temporary_sys_path context manager."""

    def test_should_add_path_to_sys_path_temporarily(self):
        """Should add path to sys.path and remove after context."""
        test_path = "/some/unique/test/path"
        assert test_path not in sys.path

        with _temporary_sys_path(test_path):
            assert test_path in sys.path

        assert test_path not in sys.path

    def test_should_not_duplicate_existing_path(self):
        """Should not add path if already in sys.path."""
        existing_path = sys.path[0]
        original_count = sys.path.count(existing_path)

        with _temporary_sys_path(existing_path):
            assert sys.path.count(existing_path) == original_count

        assert sys.path.count(existing_path) == original_count

    def test_should_remove_path_even_on_exception(self):
        """Should remove path from sys.path even if exception occurs."""
        test_path = "/another/unique/test/path"
        assert test_path not in sys.path

        try:
            with _temporary_sys_path(test_path):
                assert test_path in sys.path
                msg = "test error"
                raise ValueError(msg)
        except ValueError:
            pass

        assert test_path not in sys.path


class TestValidatePathWithinBase:
    """Tests for _validate_path_within_base function."""

    def test_should_return_resolved_path_for_valid_path(self, tmp_path):
        """Should return resolved path when within base directory."""
        # Create a test file in tmp_path
        test_file = tmp_path / "test.py"
        test_file.touch()

        with patch("langflow.agentic.services.helpers.flow_loader.FLOWS_BASE_PATH", tmp_path):
            result = _validate_path_within_base(test_file, "test.py")

            assert result == test_file.resolve()

    def test_should_raise_400_for_path_traversal_attempt(self, tmp_path):
        """Should raise HTTPException 400 for path traversal attempts."""
        # Create a candidate path outside the base
        outside_path = tmp_path.parent / "outside.py"

        with patch("langflow.agentic.services.helpers.flow_loader.FLOWS_BASE_PATH", tmp_path):
            with pytest.raises(HTTPException) as exc_info:
                _validate_path_within_base(outside_path, "../outside.py")

            assert exc_info.value.status_code == 400
            assert "Invalid flow path" in exc_info.value.detail

    def test_should_block_dot_dot_path_traversal(self, tmp_path):
        """Should block path traversal using .. sequences."""
        # Create a path that uses .. to escape base
        traversal_path = tmp_path / ".." / ".." / "etc" / "passwd"

        with patch("langflow.agentic.services.helpers.flow_loader.FLOWS_BASE_PATH", tmp_path):
            with pytest.raises(HTTPException) as exc_info:
                _validate_path_within_base(traversal_path, "../../etc/passwd")

            assert exc_info.value.status_code == 400


class TestResolveFlowPath:
    """Tests for resolve_flow_path function."""

    def test_should_return_json_path_for_explicit_json_extension(self, tmp_path):
        """Should return JSON path when .json extension is explicit."""
        # Create test file
        json_file = tmp_path / "test.json"
        json_file.write_text("{}")

        with patch("langflow.agentic.services.helpers.flow_loader.FLOWS_BASE_PATH", tmp_path):
            result_path, result_type = resolve_flow_path("test.json")

            assert result_type == "json"
            assert result_path == json_file.resolve()

    def test_should_return_python_path_for_explicit_py_extension(self, tmp_path):
        """Should return Python path when .py extension is explicit."""
        # Create test file
        py_file = tmp_path / "test.py"
        py_file.write_text("# test")

        with patch("langflow.agentic.services.helpers.flow_loader.FLOWS_BASE_PATH", tmp_path):
            result_path, result_type = resolve_flow_path("test.py")

            assert result_type == "python"
            assert result_path == py_file.resolve()

    def test_should_prefer_python_over_json_when_both_exist(self, tmp_path):
        """Should prefer .py over .json when auto-detecting."""
        # Create both files
        py_file = tmp_path / "test.py"
        py_file.write_text("# test")
        json_file = tmp_path / "test.json"
        json_file.write_text("{}")

        with patch("langflow.agentic.services.helpers.flow_loader.FLOWS_BASE_PATH", tmp_path):
            result_path, result_type = resolve_flow_path("test")

            assert result_type == "python"
            assert result_path == py_file.resolve()

    def test_should_fallback_to_json_when_python_not_found(self, tmp_path):
        """Should use .json when .py doesn't exist."""
        # Create only JSON file
        json_file = tmp_path / "test.json"
        json_file.write_text("{}")

        with patch("langflow.agentic.services.helpers.flow_loader.FLOWS_BASE_PATH", tmp_path):
            result_path, result_type = resolve_flow_path("test")

            assert result_type == "json"
            assert result_path == json_file.resolve()

    def test_should_raise_404_when_flow_not_found(self, tmp_path):
        """Should raise HTTPException 404 when flow file doesn't exist."""
        with patch("langflow.agentic.services.helpers.flow_loader.FLOWS_BASE_PATH", tmp_path):
            with pytest.raises(HTTPException) as exc_info:
                resolve_flow_path("missing.json")

            assert exc_info.value.status_code == 404
            assert "not found" in exc_info.value.detail.lower()


class TestLoadGraphFromPython:
    """Tests for _load_graph_from_python function."""

    @pytest.mark.asyncio
    async def test_should_load_graph_from_get_graph_function(self):
        """Should load graph by calling get_graph() function."""
        mock_graph = MagicMock()
        mock_module = MagicMock()
        mock_module.get_graph = MagicMock(return_value=mock_graph)

        with (
            patch("importlib.util.spec_from_file_location") as mock_spec_from_file,
            patch("importlib.util.module_from_spec") as mock_module_from_spec,
            patch("langflow.agentic.services.helpers.flow_loader._temporary_sys_path"),
        ):
            mock_spec = MagicMock()
            mock_spec.loader = MagicMock()
            mock_spec_from_file.return_value = mock_spec
            mock_module_from_spec.return_value = mock_module

            result = await _load_graph_from_python(Path("/test/flow.py"))

            assert result == mock_graph
            mock_module.get_graph.assert_called_once()

    @pytest.mark.asyncio
    async def test_should_pass_provider_params_to_get_graph(self):
        """Should pass provider, model_name, api_key_var to get_graph when accepted."""
        import inspect

        mock_graph = MagicMock()

        def mock_get_graph(
            provider=None,  # noqa: ARG001
            model_name=None,  # noqa: ARG001
            api_key_var=None,  # noqa: ARG001
        ):
            return mock_graph

        mock_module = MagicMock()
        mock_module.get_graph = mock_get_graph

        with (
            patch("importlib.util.spec_from_file_location") as mock_spec_from_file,
            patch("importlib.util.module_from_spec") as mock_module_from_spec,
            patch("langflow.agentic.services.helpers.flow_loader._temporary_sys_path"),
            patch.object(inspect, "signature", return_value=inspect.signature(mock_get_graph)),
        ):
            mock_spec = MagicMock()
            mock_spec.loader = MagicMock()
            mock_spec_from_file.return_value = mock_spec
            mock_module_from_spec.return_value = mock_module

            result = await _load_graph_from_python(
                Path("/test/flow.py"),
                provider="OpenAI",
                model_name="gpt-4",
                api_key_var="OPENAI_API_KEY",
            )

            assert result == mock_graph

    @pytest.mark.asyncio
    async def test_should_support_async_get_graph(self):
        """Should support async get_graph() functions."""
        mock_graph = MagicMock()

        async def mock_async_get_graph():
            return mock_graph

        mock_module = MagicMock()
        mock_module.get_graph = mock_async_get_graph

        with (
            patch("importlib.util.spec_from_file_location") as mock_spec_from_file,
            patch("importlib.util.module_from_spec") as mock_module_from_spec,
            patch("langflow.agentic.services.helpers.flow_loader._temporary_sys_path"),
        ):
            mock_spec = MagicMock()
            mock_spec.loader = MagicMock()
            mock_spec_from_file.return_value = mock_spec
            mock_module_from_spec.return_value = mock_module

            result = await _load_graph_from_python(Path("/test/flow.py"))

            assert result == mock_graph

    @pytest.mark.asyncio
    async def test_should_fallback_to_graph_variable(self):
        """Should use 'graph' variable if get_graph() not defined."""
        mock_graph = MagicMock()
        mock_module = MagicMock(spec=["graph"])
        mock_module.graph = mock_graph

        with (
            patch("importlib.util.spec_from_file_location") as mock_spec_from_file,
            patch("importlib.util.module_from_spec") as mock_module_from_spec,
            patch("langflow.agentic.services.helpers.flow_loader._temporary_sys_path"),
        ):
            mock_spec = MagicMock()
            mock_spec.loader = MagicMock()
            mock_spec_from_file.return_value = mock_spec
            mock_module_from_spec.return_value = mock_module

            result = await _load_graph_from_python(Path("/test/flow.py"))

            assert result == mock_graph

    @pytest.mark.asyncio
    async def test_should_raise_500_when_no_get_graph_or_graph(self):
        """Should raise HTTPException 500 when neither get_graph nor graph exists."""
        mock_module = MagicMock(spec=[])

        with (
            patch("importlib.util.spec_from_file_location") as mock_spec_from_file,
            patch("importlib.util.module_from_spec") as mock_module_from_spec,
            patch("langflow.agentic.services.helpers.flow_loader._temporary_sys_path"),
        ):
            mock_spec = MagicMock()
            mock_spec.loader = MagicMock()
            mock_spec_from_file.return_value = mock_spec
            mock_module_from_spec.return_value = mock_module

            with pytest.raises(HTTPException) as exc_info:
                await _load_graph_from_python(Path("/test/flow.py"))

            assert exc_info.value.status_code == 500
            assert "get_graph()" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_should_raise_500_when_spec_is_none(self):
        """Should raise HTTPException 500 when spec cannot be loaded."""
        with patch("importlib.util.spec_from_file_location", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await _load_graph_from_python(Path("/test/flow.py"))

            assert exc_info.value.status_code == 500
            assert "Could not load flow module" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_should_raise_500_on_module_execution_error(self):
        """Should raise HTTPException 500 when module execution fails."""
        with (
            patch("importlib.util.spec_from_file_location") as mock_spec_from_file,
            patch("importlib.util.module_from_spec") as mock_module_from_spec,
            patch("langflow.agentic.services.helpers.flow_loader._temporary_sys_path"),
        ):
            mock_spec = MagicMock()
            mock_spec.loader.exec_module.side_effect = ImportError("module error")
            mock_spec_from_file.return_value = mock_spec
            mock_module_from_spec.return_value = MagicMock()

            with pytest.raises(HTTPException) as exc_info:
                await _load_graph_from_python(Path("/test/flow.py"))

            assert exc_info.value.status_code == 500
            assert "Error loading flow module" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_should_cleanup_sys_modules_on_success(self):
        """Should remove module from sys.modules after loading."""
        mock_graph = MagicMock()
        mock_module = MagicMock()
        mock_module.get_graph = MagicMock(return_value=mock_graph)

        with (
            patch("importlib.util.spec_from_file_location") as mock_spec_from_file,
            patch("importlib.util.module_from_spec") as mock_module_from_spec,
            patch("langflow.agentic.services.helpers.flow_loader._temporary_sys_path"),
            patch.dict(sys.modules, {}, clear=False),
        ):
            mock_spec = MagicMock()
            mock_spec.loader = MagicMock()
            mock_spec_from_file.return_value = mock_spec
            mock_module_from_spec.return_value = mock_module

            await _load_graph_from_python(Path("/test/test_module.py"))

            assert "test_module" not in sys.modules


class TestLoadGraphForExecution:
    """Tests for load_graph_for_execution function."""

    @pytest.mark.asyncio
    async def test_should_use_python_loader_for_python_type(self):
        """Should use _load_graph_from_python for python flow type."""
        mock_graph = MagicMock()

        with patch(
            "langflow.agentic.services.helpers.flow_loader._load_graph_from_python",
            new_callable=AsyncMock,
            return_value=mock_graph,
        ) as mock_load:
            result = await load_graph_for_execution(
                Path("/test/flow.py"),
                "python",
                provider="OpenAI",
                model_name="gpt-4",
            )

            mock_load.assert_called_once_with(
                Path("/test/flow.py"),
                "OpenAI",
                "gpt-4",
                None,
            )
            assert result == mock_graph

    @pytest.mark.asyncio
    async def test_should_use_json_loader_for_json_type(self):
        """Should use load_and_prepare_flow + aload_flow_from_json for json type."""
        mock_graph = MagicMock()

        with (
            patch(
                "langflow.agentic.services.helpers.flow_loader.load_and_prepare_flow",
                return_value='{"data": {"nodes": []}}',
            ) as mock_prepare,
            patch(
                "langflow.agentic.services.helpers.flow_loader.aload_flow_from_json",
                new_callable=AsyncMock,
                return_value=mock_graph,
            ) as mock_load_json,
        ):
            result = await load_graph_for_execution(
                Path("/test/flow.json"),
                "json",
                provider="OpenAI",
                model_name="gpt-4",
            )

            mock_prepare.assert_called_once()
            mock_load_json.assert_called_once()
            assert result == mock_graph

    @pytest.mark.asyncio
    async def test_should_pass_api_key_var_to_loader(self):
        """Should pass api_key_var parameter to the appropriate loader."""
        mock_graph = MagicMock()

        with patch(
            "langflow.agentic.services.helpers.flow_loader._load_graph_from_python",
            new_callable=AsyncMock,
            return_value=mock_graph,
        ) as mock_load:
            await load_graph_for_execution(
                Path("/test/flow.py"),
                "python",
                provider="Anthropic",
                model_name="claude-3",
                api_key_var="ANTHROPIC_API_KEY",
            )

            mock_load.assert_called_once_with(
                Path("/test/flow.py"),
                "Anthropic",
                "claude-3",
                "ANTHROPIC_API_KEY",
            )
