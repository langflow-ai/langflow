"""Unit tests for the run.base module.

This module demonstrates different testing approaches:

1. UNIT TESTS (with mocks): Test individual functions in isolation
2. INTEGRATION TESTS (with real components): Test with actual graphs and components
3. ENVIRONMENT-BASED TESTS: Test with real environment variable injection

Strategies to reduce mocking:
- Use real components for simple functionality
- Create test-specific components that are predictable
- Test actual graph execution for critical paths
- Mock only external dependencies (file I/O, network calls, etc.)
"""

import json
from io import StringIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lfx.interface.components import component_cache
from lfx.run.base import RunError, _materialize_flow_dict, output_error, run_flow


class TestRunError:
    """Tests for the RunError exception class."""

    def test_run_error_with_message_only(self):
        """Test RunError with just a message."""
        error = RunError("Test error message")
        assert str(error) == "Test error message"
        assert error.original_exception is None

    def test_run_error_with_original_exception(self):
        """Test RunError with an original exception."""
        original = ValueError("Original error")
        error = RunError("Wrapper message", original)
        assert str(error) == "Wrapper message"
        assert error.original_exception is original
        assert isinstance(error.original_exception, ValueError)

    def test_run_error_inheritance(self):
        """Test that RunError inherits from Exception."""
        error = RunError("Test")
        assert isinstance(error, Exception)


class TestOutputError:
    """Tests for the output_error helper function."""

    def test_output_error_returns_dict(self):
        """Test that output_error returns a proper dict structure."""
        result = output_error("Test error", verbose=False)
        assert isinstance(result, dict)
        assert result["success"] is False
        assert result["type"] == "error"
        assert result["exception_message"] == "Test error"

    def test_output_error_with_exception(self):
        """Test output_error with an exception provided."""
        exc = ValueError("Value error message")
        result = output_error("Test error", verbose=False, exception=exc)
        assert result["exception_type"] == "ValueError"
        assert result["exception_message"] == "Value error message"

    def test_output_error_verbose_writes_to_stderr(self, capsys):
        """Test that verbose mode writes to stderr."""
        output_error("Test error", verbose=True)
        captured = capsys.readouterr()
        assert "Test error" in captured.err

    def test_output_error_non_verbose_silent(self, capsys):
        """Test that non-verbose mode doesn't write to stderr."""
        output_error("Test error", verbose=False)
        captured = capsys.readouterr()
        assert captured.err == ""


class TestRunFlowInputValidation:
    """Tests for run_flow input source validation."""

    @pytest.mark.asyncio
    async def test_no_input_source_raises_error(self):
        """Test that providing no input source raises RunError."""
        with pytest.raises(RunError) as exc_info:
            await run_flow(
                script_path=None,
                flow_json=None,
                stdin=False,
            )
        assert "No input source provided" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_multiple_input_sources_raises_error(self, tmp_path):
        """Test that providing multiple input sources raises RunError."""
        script = tmp_path / "test.py"
        script.write_text("graph = None")

        with pytest.raises(RunError) as exc_info:
            await run_flow(
                script_path=script,
                flow_json='{"data": {}}',
                stdin=False,
            )
        assert "Multiple input sources provided" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_script_path_and_stdin_raises_error(self, tmp_path):
        """Test that script_path + stdin raises RunError."""
        script = tmp_path / "test.py"
        script.write_text("graph = None")

        with pytest.raises(RunError) as exc_info:
            await run_flow(
                script_path=script,
                flow_json=None,
                stdin=True,
            )
        assert "Multiple input sources provided" in str(exc_info.value)


class TestRunFlowFileValidation:
    """Tests for run_flow file path validation."""

    @pytest.mark.asyncio
    async def test_nonexistent_file_raises_error(self, tmp_path):
        """Test that a non-existent file raises RunError."""
        nonexistent = tmp_path / "does_not_exist.py"

        with pytest.raises(RunError) as exc_info:
            await run_flow(script_path=nonexistent)
        assert "does not exist" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_directory_instead_of_file_raises_error(self, tmp_path):
        """Test that a directory raises RunError."""
        directory = tmp_path / "test_dir"
        directory.mkdir()

        with pytest.raises(RunError) as exc_info:
            await run_flow(script_path=directory)
        assert "is not a file" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invalid_extension_raises_error(self, tmp_path):
        """Test that an invalid file extension raises RunError."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("not a script")

        with pytest.raises(RunError) as exc_info:
            await run_flow(script_path=txt_file)
        assert "must be a .py or .json file" in str(exc_info.value)


class TestRunFlowJsonInput:
    """Tests for run_flow with flow_json input."""

    @pytest.mark.asyncio
    async def test_invalid_json_raises_error(self):
        """Test that invalid JSON raises RunError."""
        with pytest.raises(RunError) as exc_info:
            await run_flow(flow_json='{"nodes": [invalid')
        assert "Invalid JSON content" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_valid_json_creates_temp_file_and_loads_graph(self):
        """Test that valid JSON creates a temporary file and loads the graph."""
        valid_json = '{"data": {"nodes": [], "edges": []}}'

        # Mock the load functions to avoid actual execution
        with (
            patch("lfx.load.aload_flow_from_json") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
        ):
            mock_graph = MagicMock()
            mock_graph.context = {}
            mock_graph.vertices = []
            mock_graph.edges = []
            mock_graph.prepare = MagicMock()

            async def mock_async_start(_inputs, **_kwargs):
                yield

            mock_graph.async_start = mock_async_start
            mock_load.return_value = mock_graph
            mock_validate.return_value = []
            mock_extract.return_value = {"success": True, "result": "test"}

            result = await run_flow(flow_json=valid_json)

            # The function should have loaded from JSON successfully
            mock_load.assert_called_once()
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_custom_component_validation_errors_surface_as_run_error(self):
        blocked_flow = json.dumps(
            {
                "data": {
                    "nodes": [
                        {
                            "id": "node-1",
                            "data": {
                                "id": "node-1",
                                "type": "TotallyCustom",
                                "node": {
                                    "display_name": "Blocked Node",
                                    "template": {
                                        "code": {"value": "print('blocked')"},
                                    },
                                },
                            },
                        }
                    ],
                    "edges": [],
                }
            }
        )

        settings_service = SimpleNamespace(settings=SimpleNamespace(allow_custom_components=False))

        with (
            patch(
                "lfx.services.deps.get_settings_service",
                return_value=settings_service,
            ),
            patch(
                "lfx.utils.flow_validation.ensure_component_hash_lookups_loaded",
                new=AsyncMock(return_value={"ChatInput": {"knownhash1234"}}),
            ),
            patch.object(component_cache, "type_to_current_hash", {"ChatInput": {"knownhash1234"}}),
            pytest.raises(
                RunError,
                match="custom components are not allowed",
            ),
        ):
            await run_flow(flow_json=blocked_flow)


class TestRunFlowStdinInput:
    """Tests for run_flow with stdin input."""

    @pytest.mark.asyncio
    async def test_empty_stdin_raises_error(self):
        """Test that empty stdin raises RunError."""
        with patch("sys.stdin", StringIO("")):
            with pytest.raises(RunError) as exc_info:
                await run_flow(stdin=True)
            assert "No content received from stdin" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invalid_stdin_json_raises_error(self):
        """Test that invalid JSON from stdin raises RunError."""
        with patch("sys.stdin", StringIO('{"invalid": json')):
            with pytest.raises(RunError) as exc_info:
                await run_flow(stdin=True)
            assert "Invalid JSON content from stdin" in str(exc_info.value)


class TestRunFlowPythonScript:
    """Tests for run_flow with Python script input."""

    @pytest.fixture
    def valid_script(self, tmp_path):
        """Create a valid Python script with a graph variable."""
        script_content = """
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph import Graph

chat_input = ChatInput()
chat_output = ChatOutput().set(input_value=chat_input.message_response)
graph = Graph(chat_input, chat_output)
"""
        script_path = tmp_path / "valid_script.py"
        script_path.write_text(script_content)
        return script_path

    @pytest.fixture
    def no_graph_script(self, tmp_path):
        """Create a script without a graph variable."""
        script_content = """
from lfx.components.input_output import ChatInput
chat_input = ChatInput()
# No graph variable
"""
        script_path = tmp_path / "no_graph.py"
        script_path.write_text(script_content)
        return script_path

    @pytest.mark.asyncio
    async def test_no_graph_variable_raises_error(self, no_graph_script):
        """Test that a script without graph variable raises RunError."""
        with pytest.raises(RunError) as exc_info:
            await run_flow(script_path=no_graph_script)
        assert "No 'graph' variable found" in str(exc_info.value)


class TestRunFlowSessionId:
    """Tests for run_flow session_id handling."""

    @staticmethod
    def _mock_graph():
        graph = MagicMock()
        graph.context = {}
        graph.vertices = []
        graph.edges = []
        graph.prepare = MagicMock()

        async def _async_start(_inputs, **_kwargs):
            yield

        graph.async_start = _async_start
        return graph

    @pytest.mark.asyncio
    async def test_session_id_autogenerated_when_not_provided(self, tmp_path):
        """run_flow must assign a session_id so memory-store paths don't fail validation."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")
        mock_graph = self._mock_graph()

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = Graph(...)"}
            mock_load.return_value = mock_graph
            mock_validate.return_value = []
            mock_extract.return_value = {"success": True, "result": "test"}

            await run_flow(script_path=script_path)

            assert mock_graph.session_id, "session_id should be auto-generated when not provided"
            assert isinstance(mock_graph.session_id, str)

    @pytest.mark.asyncio
    async def test_caller_session_id_is_preserved(self, tmp_path):
        """Caller-supplied session_id wins over auto-generation."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")
        mock_graph = self._mock_graph()

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = Graph(...)"}
            mock_load.return_value = mock_graph
            mock_validate.return_value = []
            mock_extract.return_value = {"success": True, "result": "test"}

            await run_flow(script_path=script_path, session_id="my-fixed-session")

            assert mock_graph.session_id == "my-fixed-session"

    @pytest.mark.asyncio
    async def test_autogenerated_session_ids_are_unique_across_runs(self, tmp_path):
        """Each run without a session_id should produce a distinct value."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")
        graph_a = self._mock_graph()
        graph_b = self._mock_graph()

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = Graph(...)"}
            mock_validate.return_value = []
            mock_extract.return_value = {"success": True, "result": "test"}

            mock_load.return_value = graph_a
            await run_flow(script_path=script_path)
            mock_load.return_value = graph_b
            await run_flow(script_path=script_path)

            assert graph_a.session_id != graph_b.session_id

    @pytest.mark.asyncio
    async def test_explicit_session_id_carries_across_consecutive_runs(self, tmp_path):
        """The same caller-supplied session_id reaches both graphs — Memory continuity surface.

        Counterpart to ``test_autogenerated_session_ids_are_unique_across_runs``: with an
        explicit session_id, two consecutive run_flow invocations must both stamp the
        graph with that exact value (otherwise --session-id would not actually achieve
        conversational continuity).
        """
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")
        graph_a = self._mock_graph()
        graph_b = self._mock_graph()

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = Graph(...)"}
            mock_validate.return_value = []
            mock_extract.return_value = {"success": True, "result": "test"}

            mock_load.return_value = graph_a
            await run_flow(script_path=script_path, session_id="continuity-session")
            mock_load.return_value = graph_b
            await run_flow(script_path=script_path, session_id="continuity-session")

            assert graph_a.session_id == "continuity-session"
            assert graph_b.session_id == "continuity-session"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad_value", ["", "   ", "\t\n"])
    async def test_empty_or_whitespace_session_id_is_rejected(self, tmp_path, bad_value):
        """Empty/whitespace session_id surfaces as RunError instead of silently auto-generating.

        The --session-id flag's purpose is Memory/MessageHistory continuity. If a shell
        quirk or env-var typo collapsed the value to empty, silently auto-generating
        a fresh UUID would mask the error: subsequent runs would not see prior state
        and the user would only notice via missing memory. Validate up-front instead.
        """
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")

        with pytest.raises(RunError) as exc_info:
            await run_flow(script_path=script_path, session_id=bad_value)
        assert "session_id" in str(exc_info.value)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad_value", ["", "   "])
    async def test_empty_or_whitespace_user_id_is_rejected(self, tmp_path, bad_value):
        """Same validation as session_id, applied to user_id (variable-scoping in DB-backed setups)."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")

        with pytest.raises(RunError) as exc_info:
            await run_flow(script_path=script_path, user_id=bad_value)
        assert "user_id" in str(exc_info.value)


class TestRunFlowSessionIdPropagation:
    """Session_id must reach Memory/MessageHistory components on the lfx run path.

    lfx run uses ``graph.async_start`` (not ``graph.arun``), so it bypasses the
    ``has_session_id_vertices`` propagation loop in ``Graph._run``. ``run_flow``
    must replicate that loop after assigning ``graph.session_id`` so components
    that read ``self.session_id`` from their input field (Memory.retrieve_messages
    etc.) actually see the configured value. Mirrors what
    ``langflow/api/utils/flow_utils.build_graph_from_data`` does for the playground.
    """

    @staticmethod
    def _mock_graph_with_vertices(vertex_specs):
        """Build a mock graph whose has_session_id_vertices loop drives ``vertex_specs``.

        Each spec is (vertex_id, raw_params_dict). Returns the graph plus the
        list of vertex mocks so tests can assert on update_raw_params calls.
        """
        graph = MagicMock()
        graph.context = {}
        graph.vertices = []
        graph.edges = []
        graph.prepare = MagicMock()

        async def _async_start(_inputs, **_kwargs):
            yield

        graph.async_start = _async_start

        vertex_mocks = {}
        for vertex_id, raw_params in vertex_specs:
            vertex = MagicMock()
            vertex.raw_params = dict(raw_params)
            vertex.update_raw_params = MagicMock()
            vertex_mocks[vertex_id] = vertex

        graph.has_session_id_vertices = list(vertex_mocks.keys())
        graph.get_vertex = MagicMock(side_effect=lambda vid: vertex_mocks.get(vid))
        return graph, vertex_mocks

    @staticmethod
    def _patches():
        return (
            patch("lfx.run.base.find_graph_variable"),
            patch("lfx.run.base.load_graph_from_script"),
            patch("lfx.run.base.validate_global_variables_for_env"),
            patch("lfx.run.base.extract_structured_result"),
        )

    @pytest.mark.asyncio
    async def test_session_id_propagates_to_vertex_with_empty_input(self, tmp_path):
        """A Memory vertex with no hardcoded session_id receives the run's session_id."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")
        graph, vertices = self._mock_graph_with_vertices([("memory-1", {})])

        find_p, load_p, validate_p, extract_p = self._patches()
        with find_p as mock_find, load_p as mock_load, validate_p as mock_validate, extract_p as mock_extract:
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = Graph(...)"}
            mock_load.return_value = graph
            mock_validate.return_value = []
            mock_extract.return_value = {"success": True, "result": "test"}

            await run_flow(script_path=script_path, session_id="from-cli")

        vertices["memory-1"].update_raw_params.assert_called_once_with({"session_id": "from-cli"}, overwrite=True)

    @pytest.mark.asyncio
    async def test_session_id_does_not_overwrite_hardcoded_vertex_value(self, tmp_path):
        """If the flow JSON pinned session_id on the Memory component, the CLI must not clobber it.

        Matches Langflow's playground behavior: ``build_graph_from_data`` only writes
        when ``raw_params.get("session_id")`` is falsy.
        """
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")
        graph, vertices = self._mock_graph_with_vertices([("memory-pinned", {"session_id": "hardcoded-in-flow"})])

        find_p, load_p, validate_p, extract_p = self._patches()
        with find_p as mock_find, load_p as mock_load, validate_p as mock_validate, extract_p as mock_extract:
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = Graph(...)"}
            mock_load.return_value = graph
            mock_validate.return_value = []
            mock_extract.return_value = {"success": True, "result": "test"}

            await run_flow(script_path=script_path, session_id="from-cli")

        vertices["memory-pinned"].update_raw_params.assert_not_called()

    @pytest.mark.asyncio
    async def test_session_id_propagation_handles_missing_vertex(self, tmp_path):
        """A stale vertex_id in has_session_id_vertices (get_vertex returns None) is skipped, not raised."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")
        graph, vertices = self._mock_graph_with_vertices([("real-vertex", {})])
        graph.has_session_id_vertices = ["real-vertex", "ghost-vertex"]

        find_p, load_p, validate_p, extract_p = self._patches()
        with find_p as mock_find, load_p as mock_load, validate_p as mock_validate, extract_p as mock_extract:
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = Graph(...)"}
            mock_load.return_value = graph
            mock_validate.return_value = []
            mock_extract.return_value = {"success": True, "result": "test"}

            await run_flow(script_path=script_path, session_id="from-cli")

        vertices["real-vertex"].update_raw_params.assert_called_once()


class TestRunFlowUserId:
    """user_id auto-generation on the lfx run path.

    AgentComponent (and any component that resolves variables) hits a precheck
    in ``custom_component.get_variable`` that requires a non-empty ``self.user_id``.
    lfx run has no notion of authenticated users, but the precheck still has to
    pass so the env-fallback variable service can answer. ``run_flow`` therefore
    auto-generates a ceremonial UUID when none is supplied; the value is unused
    for variable scoping in lfx (env vars are process-global) but exists to keep
    component initialization unblocked.
    """

    @staticmethod
    def _mock_graph():
        graph = MagicMock()
        graph.context = {}
        graph.vertices = []
        graph.edges = []
        graph.prepare = MagicMock()

        async def _async_start(_inputs, **_kwargs):
            yield

        graph.async_start = _async_start
        return graph

    @pytest.mark.asyncio
    async def test_user_id_autogenerated_when_not_provided(self, tmp_path):
        """run_flow assigns a UUID user_id so the component precheck passes."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")
        mock_graph = self._mock_graph()

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = Graph(...)"}
            mock_load.return_value = mock_graph
            mock_validate.return_value = []
            mock_extract.return_value = {"success": True, "result": "test"}

            await run_flow(script_path=script_path)

            assert mock_graph.user_id, "user_id should be auto-generated when not provided"
            assert isinstance(mock_graph.user_id, str)

    @pytest.mark.asyncio
    async def test_caller_user_id_is_preserved(self, tmp_path):
        """An explicit user_id wins over auto-generation."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")
        mock_graph = self._mock_graph()

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = Graph(...)"}
            mock_load.return_value = mock_graph
            mock_validate.return_value = []
            mock_extract.return_value = {"success": True, "result": "test"}

            await run_flow(script_path=script_path, user_id="real-user-uuid")

            assert mock_graph.user_id == "real-user-uuid"

    @pytest.mark.asyncio
    async def test_autogenerated_user_ids_are_unique_across_runs(self, tmp_path):
        """Each run without a user_id should produce a distinct value (ceremonial UUIDs differ)."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")
        graph_a = self._mock_graph()
        graph_b = self._mock_graph()

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = Graph(...)"}
            mock_validate.return_value = []
            mock_extract.return_value = {"success": True, "result": "test"}

            mock_load.return_value = graph_a
            await run_flow(script_path=script_path)
            mock_load.return_value = graph_b
            await run_flow(script_path=script_path)

            assert graph_a.user_id != graph_b.user_id


class TestRunFlowFallbackToEnvVars:
    """run_flow must plumb fallback_to_env_vars into ``graph.async_start``.

    Without this, a langflow ``DatabaseVariableService`` registered alongside
    ``database_service`` would raise ``variable not found`` for any
    ``load_from_db=True`` field whose user_id has no Variable row (e.g., the
    ceremonial UUID lfx auto-generates). The flag tells
    ``loading.update_params_with_load_from_db_fields`` to fall back to
    ``os.environ`` when the DB lookup misses — same behavior as the langflow
    API path in ``processing.process.run_graph_internal``.
    """

    @staticmethod
    def _mock_graph_capturing_kwargs(captured: dict):
        graph = MagicMock()
        graph.context = {}
        graph.vertices = []
        graph.edges = []
        graph.prepare = MagicMock()

        async def _async_start(_inputs, **kwargs):
            captured.update(kwargs)
            yield

        graph.async_start = _async_start
        return graph

    @pytest.mark.asyncio
    async def test_passes_fallback_from_settings_default(self, tmp_path):
        """Setting defaults True; run_flow forwards True into async_start."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")
        captured: dict = {}
        mock_graph = self._mock_graph_capturing_kwargs(captured)

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = Graph(...)"}
            mock_load.return_value = mock_graph
            mock_validate.return_value = []
            mock_extract.return_value = {"success": True, "result": "test"}

            await run_flow(script_path=script_path)

        assert captured.get("fallback_to_env_vars") is True

    @pytest.mark.asyncio
    async def test_respects_settings_when_disabled(self, tmp_path):
        """When LANGFLOW_FALLBACK_TO_ENV_VAR=false, the flag plumbs through as False."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")
        captured: dict = {}
        mock_graph = self._mock_graph_capturing_kwargs(captured)
        mock_settings = MagicMock()
        mock_settings.settings.fallback_to_env_var = False

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
            patch("lfx.run._defaults.get_settings_service", return_value=mock_settings),
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = Graph(...)"}
            mock_load.return_value = mock_graph
            mock_validate.return_value = []
            mock_extract.return_value = {"success": True, "result": "test"}

            await run_flow(script_path=script_path)

        assert captured.get("fallback_to_env_vars") is False


class TestRunFlowGlobalVariables:
    """Tests for run_flow global variables injection."""

    @pytest.mark.asyncio
    async def test_global_variables_none_does_not_inject(self, tmp_path):
        """Test that global_variables=None does not inject anything."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")

        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.vertices = []
        mock_graph.edges = []
        mock_graph.prepare = MagicMock()

        async def mock_async_start(_inputs, **_kwargs):
            yield

        mock_graph.async_start = mock_async_start

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = Graph(...)"}
            mock_load.return_value = mock_graph
            mock_validate.return_value = []
            mock_extract.return_value = {"success": True, "result": "test"}

            await run_flow(script_path=script_path, global_variables=None)

            # Verify request_variables was not set in context
            assert "request_variables" not in mock_graph.context

    @pytest.mark.asyncio
    async def test_global_variables_injected_into_context(self, tmp_path):
        """Test that global variables are injected into graph context."""
        script_content = """
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph import Graph

chat_input = ChatInput()
chat_output = ChatOutput().set(input_value=chat_input.message_response)
graph = Graph(chat_input, chat_output)
"""
        script_path = tmp_path / "test_script.py"
        script_path.write_text(script_content)

        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.vertices = []
        mock_graph.edges = []
        mock_graph.prepare = MagicMock()

        async def mock_async_start(_inputs, **_kwargs):
            yield

        mock_graph.async_start = mock_async_start

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = Graph(...)"}
            mock_load.return_value = mock_graph
            mock_validate.return_value = []
            mock_extract.return_value = {"success": True, "result": "test"}

            global_vars = {"API_KEY": "secret123", "DEBUG": "true"}

            await run_flow(
                script_path=script_path,
                global_variables=global_vars,
            )

            # Verify global variables were injected
            assert "request_variables" in mock_graph.context
            assert mock_graph.context["request_variables"]["API_KEY"] == "secret123"
            assert mock_graph.context["request_variables"]["DEBUG"] == "true"


class TestRunFlowOutputFormats:
    """Tests for run_flow output format handling."""

    @pytest.fixture
    def mock_successful_execution(self):
        """Set up mocks for successful graph execution."""
        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.vertices = []
        mock_graph.edges = []
        mock_graph.prepare = MagicMock()

        async def mock_async_start(_inputs, **_kwargs):
            yield

        mock_graph.async_start = mock_async_start
        return mock_graph

    @pytest.mark.asyncio
    async def test_json_format_returns_structured_result(self, tmp_path, mock_successful_execution):
        """Test that JSON format returns structured result with logs."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = ..."}
            mock_load.return_value = mock_successful_execution
            mock_validate.return_value = []
            mock_extract.return_value = {"success": True, "result": "test output"}

            result = await run_flow(script_path=script_path, output_format="json")

            assert "logs" in result
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_text_format_returns_output_dict(self, tmp_path, mock_successful_execution):
        """Test that text format returns dict with output key."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = ..."}
            mock_load.return_value = mock_successful_execution
            mock_validate.return_value = []
            mock_extract.return_value = {"result": "test output"}

            result = await run_flow(script_path=script_path, output_format="text")

            assert "output" in result
            assert result["format"] == "text"

    @pytest.mark.asyncio
    async def test_message_format_returns_output_dict(self, tmp_path, mock_successful_execution):
        """Test that message format returns dict with output key."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = ..."}
            mock_load.return_value = mock_successful_execution
            mock_validate.return_value = []
            mock_extract.return_value = {"result": "test output"}

            result = await run_flow(script_path=script_path, output_format="message")

            assert "output" in result
            assert result["format"] == "message"

    @pytest.mark.asyncio
    async def test_result_format_extracts_text(self, tmp_path, mock_successful_execution):
        """Test that result format uses extract_text_from_result."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_text_from_result") as mock_extract_text,
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = ..."}
            mock_load.return_value = mock_successful_execution
            mock_validate.return_value = []
            mock_extract_text.return_value = "extracted text"

            result = await run_flow(script_path=script_path, output_format="result")

            assert result["output"] == "extracted text"
            assert result["format"] == "result"


class TestRunFlowTiming:
    """Tests for run_flow timing functionality."""

    @pytest.fixture
    def mock_successful_execution(self):
        """Set up mocks for successful graph execution."""
        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.vertices = []
        mock_graph.edges = []
        mock_graph.prepare = MagicMock()

        # Create mock results with vertex info
        mock_result = MagicMock()
        mock_result.vertex = MagicMock()
        mock_result.vertex.display_name = "TestComponent"
        mock_result.vertex.id = "test-id-123"

        async def mock_async_start(_inputs, **_kwargs):
            yield mock_result

        mock_graph.async_start = mock_async_start
        return mock_graph

    @pytest.mark.asyncio
    async def test_timing_includes_metadata(self, tmp_path, mock_successful_execution):
        """Test that timing=True includes timing metadata in result."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = ..."}
            mock_load.return_value = mock_successful_execution
            mock_validate.return_value = []
            mock_extract.return_value = {"success": True, "result": "test"}

            result = await run_flow(script_path=script_path, timing=True)

            assert "timing" in result
            assert "load_time" in result["timing"]
            assert "execution_time" in result["timing"]
            assert "total_time" in result["timing"]
            assert "component_timings" in result["timing"]

    @pytest.mark.asyncio
    async def test_timing_false_excludes_metadata(self, tmp_path, mock_successful_execution):
        """Test that timing=False excludes timing metadata."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = ..."}
            mock_load.return_value = mock_successful_execution
            mock_validate.return_value = []
            mock_extract.return_value = {"success": True, "result": "test"}

            result = await run_flow(script_path=script_path, timing=False)

            assert "timing" not in result


class TestRunFlowVerbosity:
    """Tests for run_flow verbosity levels."""

    @pytest.mark.asyncio
    async def test_verbose_false_configures_critical_logging(self, tmp_path):
        """Test that verbose=False configures CRITICAL log level."""
        import sys

        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")

        # Get the actual module from sys.modules (not the instance exported by __init__.py)
        log_module = sys.modules["lfx.log.logger"]

        with (
            patch.object(log_module, "configure") as mock_configure,
            patch("lfx.run.base.find_graph_variable") as mock_find,
        ):
            mock_find.return_value = None  # This will cause an error, but we check configure was called

            with pytest.raises(RunError):
                await run_flow(script_path=script_path, verbose=False)

            mock_configure.assert_called()
            call_args = mock_configure.call_args
            assert call_args.kwargs.get("log_level") == "CRITICAL"

    @pytest.mark.asyncio
    async def test_verbose_true_configures_info_logging(self, tmp_path):
        """Test that verbose=True configures INFO log level."""
        import sys

        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")

        log_module = sys.modules["lfx.log.logger"]

        with (
            patch.object(log_module, "configure") as mock_configure,
            patch("lfx.run.base.find_graph_variable") as mock_find,
        ):
            mock_find.return_value = None

            with pytest.raises(RunError):
                await run_flow(script_path=script_path, verbose=True)

            mock_configure.assert_called()
            call_args = mock_configure.call_args
            assert call_args.kwargs.get("log_level") == "INFO"

    @pytest.mark.asyncio
    async def test_verbose_detailed_configures_debug_logging(self, tmp_path):
        """Test that verbose_detailed=True configures DEBUG log level."""
        import sys

        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")

        log_module = sys.modules["lfx.log.logger"]

        with (
            patch.object(log_module, "configure") as mock_configure,
            patch("lfx.run.base.find_graph_variable") as mock_find,
        ):
            mock_find.return_value = None

            with pytest.raises(RunError):
                await run_flow(script_path=script_path, verbose_detailed=True)

            mock_configure.assert_called()
            call_args = mock_configure.call_args
            assert call_args.kwargs.get("log_level") == "DEBUG"

    @pytest.mark.asyncio
    async def test_verbose_full_configures_debug_logging(self, tmp_path):
        """Test that verbose_full=True configures DEBUG log level."""
        import sys

        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")

        log_module = sys.modules["lfx.log.logger"]

        with (
            patch.object(log_module, "configure") as mock_configure,
            patch("lfx.run.base.find_graph_variable") as mock_find,
        ):
            mock_find.return_value = None

            with pytest.raises(RunError):
                await run_flow(script_path=script_path, verbose_full=True)

            mock_configure.assert_called()
            call_args = mock_configure.call_args
            assert call_args.kwargs.get("log_level") == "DEBUG"


class TestRunFlowVariableValidation:
    """Tests for run_flow global variable validation."""

    @pytest.fixture
    def mock_graph_with_validation_errors(self):
        """Set up mock graph that triggers validation errors."""
        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.vertices = []
        mock_graph.edges = []
        mock_graph.prepare = MagicMock()
        return mock_graph

    @pytest.mark.asyncio
    async def test_validation_errors_raise_run_error(self, tmp_path, mock_graph_with_validation_errors):
        """Test that validation errors raise RunError."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = ..."}
            mock_load.return_value = mock_graph_with_validation_errors
            mock_validate.return_value = ["Missing required variable: API_KEY"]

            with pytest.raises(RunError) as exc_info:
                await run_flow(script_path=script_path, check_variables=True)

            assert "Global variable validation failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_check_variables_false_skips_validation(self, tmp_path):
        """Test that check_variables=False skips validation."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")

        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.vertices = []
        mock_graph.edges = []
        mock_graph.prepare = MagicMock()

        async def mock_async_start(_inputs, **_kwargs):
            yield

        mock_graph.async_start = mock_async_start

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = ..."}
            mock_load.return_value = mock_graph
            mock_extract.return_value = {"success": True}

            await run_flow(script_path=script_path, check_variables=False)

            # validate_global_variables_for_env should not be called
            mock_validate.assert_not_called()


class TestRunFlowInputValueHandling:
    """Tests for run_flow input value handling."""

    @pytest.mark.asyncio
    async def test_input_value_takes_precedence(self, tmp_path):
        """Test that input_value takes precedence over input_value_option."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")

        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.vertices = []
        mock_graph.edges = []
        mock_graph.prepare = MagicMock()

        async def mock_async_start(_inputs, **_kwargs):
            yield

        mock_graph.async_start = mock_async_start

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
            patch("lfx.run.base.InputValueRequest") as mock_input_request,
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = ..."}
            mock_load.return_value = mock_graph
            mock_validate.return_value = []
            mock_extract.return_value = {"success": True}

            await run_flow(
                script_path=script_path,
                input_value="positional",
                input_value_option="option",
            )

            # InputValueRequest should be called with the positional value
            mock_input_request.assert_called_once_with(input_value="positional")

    @pytest.mark.asyncio
    async def test_input_value_option_used_when_no_positional(self, tmp_path):
        """Test that input_value_option is used when input_value is None."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")

        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.vertices = []
        mock_graph.edges = []
        mock_graph.prepare = MagicMock()

        async def mock_async_start(_inputs, **_kwargs):
            yield

        mock_graph.async_start = mock_async_start

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
            patch("lfx.run.base.InputValueRequest") as mock_input_request,
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = ..."}
            mock_load.return_value = mock_graph
            mock_validate.return_value = []
            mock_extract.return_value = {"success": True}

            await run_flow(
                script_path=script_path,
                input_value=None,
                input_value_option="option_value",
            )

            mock_input_request.assert_called_once_with(input_value="option_value")


class TestRunFlowJsonFileExecution:
    """Tests for run_flow JSON file execution."""

    @pytest.fixture
    def simple_json_flow(self, tmp_path):
        """Create a simple JSON flow file."""
        flow_data = {
            "data": {
                "nodes": [
                    {
                        "id": "ChatInput-1",
                        "type": "ChatInput",
                        "data": {"display_name": "Chat Input"},
                    },
                ],
                "edges": [],
            }
        }
        json_path = tmp_path / "flow.json"
        json_path.write_text(json.dumps(flow_data))
        return json_path

    @pytest.mark.asyncio
    async def test_json_file_calls_aload_flow_from_json(self, simple_json_flow):
        """Test that JSON file uses aload_flow_from_json."""
        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.vertices = []
        mock_graph.edges = []
        mock_graph.prepare = MagicMock()

        async def mock_async_start(_inputs, **_kwargs):
            yield

        mock_graph.async_start = mock_async_start

        with (
            patch("lfx.load.aload_flow_from_json") as mock_load_json,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
        ):
            mock_load_json.return_value = mock_graph
            mock_validate.return_value = []
            mock_extract.return_value = {"success": True}

            await run_flow(script_path=simple_json_flow)

            mock_load_json.assert_called_once()
            call_args = mock_load_json.call_args
            assert call_args[0][0] == simple_json_flow


class TestRunFlowEnvironmentIntegration:
    """Integration tests for run_flow with environment variables and real components."""

    @pytest.fixture
    def simple_env_script(self, tmp_path):
        """Create a simple script that uses environment variables."""
        script_content = """
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.custom.custom_component.component import Component
from lfx.template.field.base import Output, Input
from lfx.schema.message import Message
from lfx.graph import Graph

class EnvReader(Component):
    inputs = [Input(name="trigger", input_types=["Message"], field_type="Message")]
    outputs = [Output(name="env_value", method="get_env_value", types=["Message"])]

    def get_env_value(self) -> Message:
        # Access request_variables from graph context
        request_variables = self.graph.context.get("request_variables", {})
        # Get TEST_VAR
        value = request_variables.get("TEST_VAR", "Not Found")
        return Message(text=f"Value: {value}")

chat_input = ChatInput()
env_reader = EnvReader()
env_reader.set(trigger=chat_input.message_response)
chat_output = ChatOutput().set(input_value=env_reader.get_env_value)

graph = Graph(chat_input, chat_output)
"""
        script_path = tmp_path / "env_script.py"
        script_path.write_text(script_content)
        return script_path

    @pytest.mark.asyncio
    async def test_run_flow_with_env_vars_integration(self, simple_env_script):
        """Integration test that uses environment variables with real components."""
        global_vars = {"TEST_VAR": "Hello World"}

        result = await run_flow(
            script_path=simple_env_script,
            global_variables=global_vars,
            verbose=False,
            check_variables=False,  # Skip validation for this test
        )

        assert result["success"] is True
        assert "Value: Hello World" in result["result"]

    @pytest.mark.asyncio
    async def test_run_flow_without_env_vars_integration(self, simple_env_script):
        """Integration test without environment variables."""
        result = await run_flow(
            script_path=simple_env_script,
            global_variables=None,
            verbose=False,
            check_variables=False,  # Skip validation for this test
        )

        assert result["success"] is True
        assert "Value: Not Found" in result["result"]


class TestRunFlowExecutionErrors:
    """Tests for run_flow execution error handling."""

    @pytest.mark.asyncio
    async def test_graph_execution_error_raises_run_error(self, tmp_path):
        """Test that graph execution errors are wrapped in RunError."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")

        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.vertices = []
        mock_graph.edges = []
        mock_graph.prepare = MagicMock()

        async def failing_async_start(_inputs, **_kwargs):
            msg = "Execution failed"
            raise ValueError(msg)
            yield  # Required to make it an async generator

        mock_graph.async_start = failing_async_start

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = ..."}
            mock_load.return_value = mock_graph
            mock_validate.return_value = []

            with pytest.raises(RunError) as exc_info:
                await run_flow(script_path=script_path)

            assert "Failed to execute graph" in str(exc_info.value)
            assert exc_info.value.original_exception is not None

    @pytest.mark.asyncio
    async def test_graph_preparation_error_raises_run_error(self, tmp_path):
        """Test that graph preparation errors are wrapped in RunError."""
        script_path = tmp_path / "test.py"
        script_path.write_text("graph = None")

        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.vertices = []
        mock_graph.edges = []
        mock_graph.prepare = MagicMock(side_effect=RuntimeError("Preparation failed"))

        with (
            patch("lfx.run.base.find_graph_variable") as mock_find,
            patch("lfx.run.base.load_graph_from_script") as mock_load,
        ):
            mock_find.return_value = {"line_number": 1, "type": "Graph", "source_line": "graph = ..."}
            mock_load.return_value = mock_graph

            with pytest.raises(RunError) as exc_info:
                await run_flow(script_path=script_path)

            assert "Failed to prepare graph" in str(exc_info.value)


# ---------------------------------------------------------------------------
# --upgrade-flow option
# ---------------------------------------------------------------------------


class TestMaterializeFlowDict:
    """Direct tests for ``_materialize_flow_dict`` — the core outer-envelope unwrap.

    This helper backs ``--upgrade-flow`` input handling.
    Exported Langflow flows look like ``{"name": ..., "data": {<graph>}}``; the inner graph is
    ``{"nodes": [...], "edges": [...]}``. This helper must unwrap the envelope, pass a bare graph
    through unchanged, unwrap exactly one level, and fail loudly (RunError) on bad/missing input.
    """

    BARE = {"nodes": [{"id": "n1"}], "edges": []}

    def _materialize(self, **kwargs):
        defaults = {
            "flow_json": None,
            "stdin": False,
            "script_path": None,
            "upgrade_flow": None,
            "verbosity": 0,
            "verbose": False,
        }
        defaults.update(kwargs)
        return _materialize_flow_dict(**defaults)

    def test_inline_envelope_unwrapped(self):
        env = {"name": "F", "description": "d", "data": self.BARE}
        assert self._materialize(flow_json=json.dumps(env)) == self.BARE

    def test_inline_bare_passthrough(self):
        assert self._materialize(flow_json=json.dumps(self.BARE)) == self.BARE

    def test_stdin_envelope_unwrapped(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", StringIO(json.dumps({"name": "F", "data": self.BARE})))
        assert self._materialize(stdin=True) == self.BARE

    def test_stdin_bare_passthrough(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", StringIO(json.dumps(self.BARE)))
        assert self._materialize(stdin=True) == self.BARE

    def test_file_with_upgrade_envelope_unwrapped(self, tmp_path):
        f = tmp_path / "flow.json"
        f.write_text(json.dumps({"name": "F", "data": self.BARE}))
        assert self._materialize(script_path=f, upgrade_flow="check") == self.BARE

    def test_file_with_upgrade_bare_passthrough(self, tmp_path):
        f = tmp_path / "flow.json"
        f.write_text(json.dumps(self.BARE))
        assert self._materialize(script_path=f, upgrade_flow="check") == self.BARE

    def test_nested_envelope_unwraps_exactly_one_level(self):
        # Documents behavior: a doubly-nested {"data": {"data": ...}} unwraps a single level.
        assert self._materialize(flow_json=json.dumps({"data": {"data": self.BARE}})) == {"data": self.BARE}

    def test_plain_file_without_upgrade_returns_none(self, tmp_path):
        # A plain script path (no --upgrade-flow) is loaded later by path, not materialized here.
        f = tmp_path / "flow.json"
        f.write_text(json.dumps(self.BARE))
        assert self._materialize(script_path=f, upgrade_flow=None) is None

    def test_non_dict_json_raises(self):
        # A top-level JSON array has no .get(); this surfaces as a RunError (fails loudly).
        with pytest.raises(RunError):
            self._materialize(flow_json="[]")

    def test_py_script_with_upgrade_raises(self, tmp_path):
        f = tmp_path / "flow.py"
        f.write_text("graph = None\n")
        with pytest.raises(RunError):
            self._materialize(script_path=f, upgrade_flow="check")

    def test_upgrade_without_source_raises(self):
        with pytest.raises(RunError):
            self._materialize(upgrade_flow="check")

    def test_empty_stdin_raises(self, monkeypatch):
        monkeypatch.setattr("sys.stdin", StringIO("   "))
        with pytest.raises(RunError):
            self._materialize(stdin=True, upgrade_flow="check")


class TestUpgradeFlowOption:
    """Tests for the --upgrade-flow option wired into run_flow."""

    REGISTRY_CODE = "class MyComp:\n    pass  # v2"
    NODE_CODE = "class MyComp:\n    pass  # v1"

    def _registry(self):
        return {
            "Cat": {
                "MyComp": {
                    "template": {"code": {"value": self.REGISTRY_CODE}},
                    "outputs": [
                        {"name": "o", "display_name": "O", "types": ["M"], "method": "m", "allows_loop": False}
                    ],
                    "metadata": {},
                }
            }
        }

    def _flow_dict(self, code=None):
        return {
            "nodes": [
                {
                    "id": "n1",
                    "data": {
                        "id": "n1",
                        "type": "MyComp",
                        "node": {
                            "display_name": "My Component",
                            "edited": False,
                            "template": {"code": {"value": code or self.NODE_CODE}},
                            "outputs": [
                                {"name": "o", "display_name": "O", "types": ["M"], "method": "m", "allows_loop": False}
                            ],
                        },
                    },
                }
            ],
            "edges": [],
        }

    @pytest.mark.asyncio
    async def test_upgrade_flow_check_rejects_outdated_inline_json(self):
        """--upgrade-flow=check must reject outdated nodes from inline JSON."""
        import json as _json

        flow_json = _json.dumps(self._flow_dict(code=self.NODE_CODE))

        with (
            patch("lfx.upgrade.cli_gate._load_bundled_registry", return_value=self._registry()),
            pytest.raises(RunError, match="incompatible components"),
        ):
            await run_flow(flow_json=flow_json, upgrade_flow="check")

    @pytest.mark.asyncio
    async def test_upgrade_flow_check_rejects_outdated_file(self, tmp_path):
        """--upgrade-flow=check must fire for .json file path inputs, not just inline JSON."""
        import json as _json

        f = tmp_path / "flow.json"
        f.write_text(_json.dumps(self._flow_dict(code=self.NODE_CODE)))

        with (
            patch("lfx.upgrade.cli_gate._load_bundled_registry", return_value=self._registry()),
            pytest.raises(RunError, match="incompatible components"),
        ):
            await run_flow(script_path=f, upgrade_flow="check")

    @pytest.mark.asyncio
    async def test_upgrade_flow_check_rejects_outer_envelope_file(self, tmp_path):
        """Exported flows use an outer envelope; the checker must unwrap it before inspecting nodes.

        Shape: {"name":..., "data": {"nodes": [...], "edges": [...]}}.
        """
        import json as _json

        envelope = {"name": "My Flow", "data": self._flow_dict(code=self.NODE_CODE)}
        f = tmp_path / "flow.json"
        f.write_text(_json.dumps(envelope))

        with (
            patch("lfx.upgrade.cli_gate._load_bundled_registry", return_value=self._registry()),
            pytest.raises(RunError, match="incompatible components"),
        ):
            await run_flow(script_path=f, upgrade_flow="check")

    @pytest.mark.asyncio
    async def test_upgrade_flow_rejects_py_script(self, tmp_path):
        """--upgrade-flow on a .py script must fail fast with a clear error, not silently skip."""
        script = tmp_path / "flow.py"
        script.write_text("graph = None")

        with pytest.raises(RunError, match=r"only supported for JSON"):
            await run_flow(script_path=script, upgrade_flow="check")

    @pytest.mark.asyncio
    async def test_upgrade_flow_fails_fast_on_unreadable_json_file(self, tmp_path):
        """If the .json file can't be read for upgrade check, must raise RunError — not silently skip."""
        f = tmp_path / "broken.json"
        f.write_text("not valid json")

        with pytest.raises(RunError, match="could not read flow file"):
            await run_flow(script_path=f, upgrade_flow="check")

    @pytest.mark.asyncio
    async def test_upgrade_flow_unknown_mode_raises(self):
        """An unknown --upgrade-flow value must raise immediately, not silently pass."""
        import json as _json

        flow_json = _json.dumps(self._flow_dict(code=self.REGISTRY_CODE))

        with (
            patch("lfx.upgrade.cli_gate._load_bundled_registry", return_value=self._registry()),
            pytest.raises(RunError, match="Unknown --upgrade-flow"),
        ):
            await run_flow(flow_json=flow_json, upgrade_flow="typo")

    @pytest.mark.asyncio
    async def test_upgrade_flow_check_rejects_outer_envelope_inline_json(self):
        """--flow-json with an outer envelope must have its nodes inspected, not silently pass with zero nodes."""
        import json as _json

        envelope = {"name": "My Flow", "data": self._flow_dict(code=self.NODE_CODE)}
        flow_json = _json.dumps(envelope)

        with (
            patch("lfx.upgrade.cli_gate._load_bundled_registry", return_value=self._registry()),
            pytest.raises(RunError, match="incompatible components"),
        ):
            await run_flow(flow_json=flow_json, upgrade_flow="check")

    @pytest.mark.asyncio
    async def test_upgrade_flow_check_rejects_outer_envelope_stdin(self):
        """--stdin with an outer envelope must have its nodes inspected, not silently pass with zero nodes."""
        import json as _json
        from io import StringIO

        envelope = {"name": "My Flow", "data": self._flow_dict(code=self.NODE_CODE)}

        with (
            patch("lfx.upgrade.cli_gate._load_bundled_registry", return_value=self._registry()),
            patch("sys.stdin", StringIO(_json.dumps(envelope))),
            pytest.raises(RunError, match="incompatible components"),
        ):
            await run_flow(stdin=True, upgrade_flow="check")

    @pytest.mark.asyncio
    async def test_upgrade_flow_check_passes_clean_real_flow_without_registry_mock(self):
        """Regression: a known-clean real starter flow must PASS --upgrade-flow=check.

        Deliberately does NOT mock the registry. The original bug was that the gate read
        component_cache.all_types_dict (empty at gate time) instead of the bundled component
        index, so every component was classified 'blocked' and every flow rejected. Every
        other test here mocks a populated registry, which is exactly what hid the bug — this
        one exercises the real default source end-to-end.
        """
        from pathlib import Path

        fixture = Path(__file__).parents[2] / "fixtures" / "starter_flows" / "v1.9.0" / "basic_prompting.json"
        flow_json = fixture.read_text(encoding="utf-8")

        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.vertices = []
        mock_graph.edges = []
        mock_graph.prepare = MagicMock()

        async def _async_start(_inputs, **_kwargs):
            yield

        mock_graph.async_start = _async_start

        # Mock only the loader/executor (not the registry) so we isolate the gate decision:
        # the gate must pass using the real bundled index, then run_flow proceeds to load.
        with (
            patch("lfx.load.aload_flow_from_json") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
        ):
            mock_load.return_value = mock_graph
            mock_validate.return_value = []
            mock_extract.return_value = {"success": True, "result": "ok"}

            # Must not raise: clean flow + real bundled index => gate passes, loader is reached.
            await run_flow(flow_json=flow_json, upgrade_flow="check")
            mock_load.assert_called_once()

    @pytest.mark.asyncio
    async def test_upgrade_flow_safe_envelope_file_loads_successfully(self, tmp_path):
        """Happy path: --upgrade-flow=safe on an envelope file must proceed to load.

        All three input paths (file, --flow-json, --stdin) unwrap the outer envelope with
        raw.get("data", raw) before the upgrade check, so aload_flow_from_json always
        receives {"data": <inner_graph>}. The loader does flow_graph["data"] and Graph.from_payload
        handles the rest correctly.
        """
        import json as _json

        envelope = {"name": "My Flow", "description": "x", "data": self._flow_dict(code=self.NODE_CODE)}
        f = tmp_path / "flow.json"
        f.write_text(_json.dumps(envelope))

        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.vertices = []
        mock_graph.edges = []
        mock_graph.prepare = MagicMock()

        async def _async_start(_inputs, **_kwargs):
            yield

        mock_graph.async_start = _async_start

        with (
            patch("lfx.upgrade.cli_gate._load_bundled_registry", return_value=self._registry()),
            patch("lfx.load.aload_flow_from_json") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
        ):
            mock_load.return_value = mock_graph
            mock_validate.return_value = []
            mock_extract.return_value = {"success": True, "result": "ok"}

            await run_flow(script_path=f, upgrade_flow="safe")

            mock_load.assert_called_once()
            loaded_arg = mock_load.call_args[0][0]
            # Loader receives {"data": inner_graph} — the "data" key is always present.
            assert "data" in loaded_arg, f"loader got wrong shape: {list(loaded_arg)}"
            assert loaded_arg["data"]["nodes"][0]["data"]["node"]["template"]["code"]["value"] == self.REGISTRY_CODE

    @pytest.mark.asyncio
    async def test_upgrade_flow_safe_flat_file_loads_successfully(self, tmp_path):
        """Flat-shape file with --upgrade-flow=safe must still reach the loader without crashing."""
        import json as _json

        f = tmp_path / "flow.json"
        f.write_text(_json.dumps(self._flow_dict(code=self.NODE_CODE)))

        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.vertices = []
        mock_graph.edges = []
        mock_graph.prepare = MagicMock()

        async def _async_start(_inputs, **_kwargs):
            yield

        mock_graph.async_start = _async_start

        with (
            patch("lfx.upgrade.cli_gate._load_bundled_registry", return_value=self._registry()),
            patch("lfx.load.aload_flow_from_json") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
        ):
            mock_load.return_value = mock_graph
            mock_validate.return_value = []
            mock_extract.return_value = {"success": True, "result": "ok"}

            await run_flow(script_path=f, upgrade_flow="safe")

            mock_load.assert_called_once()
            loaded_arg = mock_load.call_args[0][0]
            # Loader receives {"data": inner_graph} for both flat and envelope inputs.
            assert "data" in loaded_arg
            assert loaded_arg["data"]["nodes"][0]["data"]["node"]["template"]["code"]["value"] == self.REGISTRY_CODE

    @pytest.mark.asyncio
    async def test_upgrade_flow_safe_envelope_inline_json_loads_successfully(self):
        """--flow-json with outer envelope + --upgrade-flow=safe must upgrade and pass {"data": inner} to loader.

        Symmetric to test_upgrade_flow_safe_envelope_file_loads_successfully but for the
        --flow-json input path. Regression: the envelope unwrap at parse time (line 162)
        must leave flow_dict as the inner graph so the loader receives {"data": inner}, not
        {"data": {"name":..., "data": inner}} (double-wrapped).
        """
        import json as _json

        envelope = {"name": "My Flow", "description": "x", "data": self._flow_dict(code=self.NODE_CODE)}
        flow_json = _json.dumps(envelope)

        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.vertices = []
        mock_graph.edges = []
        mock_graph.prepare = MagicMock()

        async def _async_start(_inputs, **_kwargs):
            yield

        mock_graph.async_start = _async_start

        with (
            patch("lfx.upgrade.cli_gate._load_bundled_registry", return_value=self._registry()),
            patch("lfx.load.aload_flow_from_json") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
        ):
            mock_load.return_value = mock_graph
            mock_validate.return_value = []
            mock_extract.return_value = {"success": True, "result": "ok"}

            await run_flow(flow_json=flow_json, upgrade_flow="safe")

            mock_load.assert_called_once()
            loaded_arg = mock_load.call_args[0][0]
            assert "data" in loaded_arg, f"loader got wrong shape: {list(loaded_arg)}"
            assert loaded_arg["data"]["nodes"][0]["data"]["node"]["template"]["code"]["value"] == self.REGISTRY_CODE

    @pytest.mark.asyncio
    async def test_upgrade_flow_safe_envelope_stdin_loads_successfully(self):
        """--stdin with outer envelope + --upgrade-flow=safe must upgrade and pass {"data": inner} to loader.

        Symmetric to the file and --flow-json envelope tests for the stdin input path.
        """
        import json as _json
        from io import StringIO

        envelope = {"name": "My Flow", "description": "x", "data": self._flow_dict(code=self.NODE_CODE)}

        mock_graph = MagicMock()
        mock_graph.context = {}
        mock_graph.vertices = []
        mock_graph.edges = []
        mock_graph.prepare = MagicMock()

        async def _async_start(_inputs, **_kwargs):
            yield

        mock_graph.async_start = _async_start

        with (
            patch("lfx.upgrade.cli_gate._load_bundled_registry", return_value=self._registry()),
            patch("lfx.load.aload_flow_from_json") as mock_load,
            patch("lfx.run.base.validate_global_variables_for_env") as mock_validate,
            patch("lfx.run.base.extract_structured_result") as mock_extract,
            patch("sys.stdin", StringIO(_json.dumps(envelope))),
        ):
            mock_load.return_value = mock_graph
            mock_validate.return_value = []
            mock_extract.return_value = {"success": True, "result": "ok"}

            await run_flow(stdin=True, upgrade_flow="safe")

            mock_load.assert_called_once()
            loaded_arg = mock_load.call_args[0][0]
            assert "data" in loaded_arg, f"loader got wrong shape: {list(loaded_arg)}"
            assert loaded_arg["data"]["nodes"][0]["data"]["node"]["template"]["code"]["value"] == self.REGISTRY_CODE
