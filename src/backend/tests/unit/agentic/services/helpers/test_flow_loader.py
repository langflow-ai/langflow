"""Tests for flow loader module.

Tests _temporary_sys_path context manager, resolve_flow_path,
_load_graph_from_python, and load_graph_for_execution functions.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from langflow.agentic.services.helpers.flow_loader import (
    _load_graph_from_python,
    _temporary_sys_path,
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


class TestResolveFlowPath:
    """Tests for resolve_flow_path function."""

    def test_should_return_json_path_for_explicit_json_extension(self, tmp_path):
        """Should return JSON path when .json extension is explicit."""
        json_file = tmp_path / "test.json"
        json_file.write_text("{}")

        with patch("langflow.agentic.services.helpers.flow_loader.FLOWS_BASE_PATH", tmp_path):
            result_path, result_type = resolve_flow_path("test.json")

            assert result_type == "json"
            assert result_path == json_file

    def test_should_return_python_path_for_explicit_py_extension(self, tmp_path):
        """Should return Python path when .py extension is explicit."""
        py_file = tmp_path / "test.py"
        py_file.write_text("# test")

        with patch("langflow.agentic.services.helpers.flow_loader.FLOWS_BASE_PATH", tmp_path):
            result_path, result_type = resolve_flow_path("test.py")

            assert result_type == "python"
            assert result_path == py_file

    def test_should_prefer_python_over_json_when_both_exist(self, tmp_path):
        """Should prefer .py over .json when auto-detecting."""
        py_file = tmp_path / "test.py"
        py_file.write_text("# test")
        json_file = tmp_path / "test.json"
        json_file.write_text("{}")

        with patch("langflow.agentic.services.helpers.flow_loader.FLOWS_BASE_PATH", tmp_path):
            result_path, result_type = resolve_flow_path("test")

            assert result_type == "python"
            assert result_path == py_file

    def test_should_fallback_to_json_when_python_not_found(self, tmp_path):
        """Should use .json when .py doesn't exist."""
        json_file = tmp_path / "test.json"
        json_file.write_text("{}")

        with patch("langflow.agentic.services.helpers.flow_loader.FLOWS_BASE_PATH", tmp_path):
            result_path, result_type = resolve_flow_path("test")

            assert result_type == "json"
            assert result_path == json_file

    def test_should_reject_filename_with_path_traversal_sequences(self, tmp_path):
        """Should reject filenames containing '..' before any path construction."""
        with patch("langflow.agentic.services.helpers.flow_loader.FLOWS_BASE_PATH", tmp_path):
            with pytest.raises(HTTPException) as exc_info:
                resolve_flow_path("../../etc/passwd")

            assert exc_info.value.status_code == 400
            assert "Invalid flow filename" in exc_info.value.detail

    def test_should_reject_filename_with_backslash_traversal(self, tmp_path):
        """Should reject filenames containing backslash path separators."""
        with patch("langflow.agentic.services.helpers.flow_loader.FLOWS_BASE_PATH", tmp_path):
            with pytest.raises(HTTPException) as exc_info:
                resolve_flow_path("..\\..\\etc\\passwd")

            assert exc_info.value.status_code == 400
            assert "Invalid flow filename" in exc_info.value.detail

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


class TestBugsAndEdgeCases:
    """Tests that challenge the code — exposing real bugs and untested edge cases."""

    def test_resolve_flow_path_traversal_escape(self, tmp_path):
        """resolve_flow_path should reject paths that traverse outside FLOWS_BASE_PATH."""
        flows_dir = tmp_path / "flows"
        flows_dir.mkdir()
        secret = tmp_path / "secret.json"
        secret.write_text('{"secret": true}')

        with patch("langflow.agentic.services.helpers.flow_loader.FLOWS_BASE_PATH", flows_dir):
            with pytest.raises(HTTPException) as exc_info:
                resolve_flow_path("../secret.json")

            assert exc_info.value.status_code == 400

    def test_resolve_flow_path_empty_string_returns_directory(self, tmp_path):
        """L78: resolve_flow_path('') returns FLOWS_BASE_PATH directory as a 'json' file.

        Empty string → base_name = '' → no .py/.json match → direct_path = FLOWS_BASE_PATH
        → exists() = True (it's a directory) → returned as 'json'.
        Downstream code will crash trying to read a directory as JSON.
        """
        with patch("langflow.agentic.services.helpers.flow_loader.FLOWS_BASE_PATH", tmp_path):
            result_path, result_type = resolve_flow_path("")

        assert result_path == tmp_path  # Returns directory as if it were a file
        assert result_type == "json"

    def test_resolve_flow_path_only_extension_literal(self, tmp_path):
        """resolve_flow_path('.json') treats it as literal filename, not just extension."""
        # File literally named '.json'
        dot_json = tmp_path / ".json"
        dot_json.write_text("{}")

        with patch("langflow.agentic.services.helpers.flow_loader.FLOWS_BASE_PATH", tmp_path):
            result_path, result_type = resolve_flow_path(".json")

        assert result_path == dot_json
        assert result_type == "json"

    @pytest.mark.asyncio
    async def test_load_graph_returns_none_from_get_graph(self):
        """get_graph() returning None is passed through without validation.

        No check that the returned value is actually a Graph instance.
        Downstream code will crash on None.
        """
        mock_module = MagicMock()
        mock_module.get_graph = MagicMock(return_value=None)

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

        # Documents: None is returned without validation
        assert result is None

    def test_sys_modules_uses_stem_as_module_name(self):
        """L110: module_name = flow_path.stem — files with same stem collide in sys.modules.

        Two concurrent requests loading /path/a/flow.py and /path/b/flow.py
        both use 'flow' as module_name, creating a race condition in sys.modules.
        """
        path_a = Path("/path/a/flow.py")
        path_b = Path("/path/b/flow.py")
        # Same stem means same key in sys.modules — concurrent collision
        assert path_a.stem == path_b.stem == "flow"

    def test_temporary_sys_path_crashes_if_path_removed_during_context(self):
        """L34: sys.path.remove() raises ValueError if path was removed inside context.

        If code inside the context (or another thread) removes the path,
        the finally block crashes with ValueError instead of handling gracefully.
        """
        test_path = "/unique/concurrent/removal/test/path"

        with (
            pytest.raises(ValueError, match="not in list"),
            _temporary_sys_path(test_path),
        ):
            # Simulate another thread or code removing the path
            sys.path.remove(test_path)
