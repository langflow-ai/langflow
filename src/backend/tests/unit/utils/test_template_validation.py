"""Unit tests for template validation utilities."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest
from langflow.utils.template_validation import (
    _validate_event_stream,
    validate_flow_can_build,
    validate_flow_code,
    validate_flow_execution,
    validate_template_structure,
)


class AsyncIteratorMock:
    """Mock class that provides proper async iteration."""

    def __init__(self, items):
        self.items = items

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.items:
            raise StopAsyncIteration
        return self.items.pop(0)


class TestValidateTemplateStructure:
    """Test cases for validate_template_structure function."""

    def test_valid_template_structure(self):
        """Test validation passes for valid template structure."""
        template_data = {
            "nodes": [
                {"id": "node1", "data": {"type": "input"}},
                {"id": "node2", "data": {"type": "output"}},
            ],
            "edges": [{"source": "node1", "target": "node2"}],
        }
        errors = validate_template_structure(template_data, "test.json")
        assert errors == []

    def test_valid_template_with_data_wrapper(self):
        """Test validation passes for template with data wrapper."""
        template_data = {
            "data": {
                "nodes": [{"id": "node1", "data": {"type": "input"}}],
                "edges": [],
            }
        }
        errors = validate_template_structure(template_data, "test.json")
        assert errors == []

    def test_missing_nodes_field(self):
        """Test validation fails when nodes field is missing."""
        template_data = {"edges": []}
        errors = validate_template_structure(template_data, "test.json")
        assert "test.json: Missing 'nodes' field" in errors

    def test_missing_edges_field(self):
        """Test validation fails when edges field is missing."""
        template_data = {"nodes": []}
        errors = validate_template_structure(template_data, "test.json")
        assert "test.json: Missing 'edges' field" in errors

    def test_nodes_not_list(self):
        """Test validation fails when nodes is not a list."""
        template_data = {"nodes": "not_a_list", "edges": []}
        errors = validate_template_structure(template_data, "test.json")
        assert "test.json: 'nodes' must be a list" in errors

    def test_edges_not_list(self):
        """Test validation fails when edges is not a list."""
        template_data = {"nodes": [], "edges": "not_a_list"}
        errors = validate_template_structure(template_data, "test.json")
        assert "test.json: 'edges' must be a list" in errors

    def test_node_missing_id(self):
        """Test validation fails when node is missing id."""
        template_data = {
            "nodes": [{"data": {"type": "input"}}],
            "edges": [],
        }
        errors = validate_template_structure(template_data, "test.json")
        assert "test.json: Node 0 missing 'id'" in errors

    def test_node_missing_data(self):
        """Test validation fails when node is missing data."""
        template_data = {
            "nodes": [{"id": "node1"}],
            "edges": [],
        }
        errors = validate_template_structure(template_data, "test.json")
        assert "test.json: Node 0 missing 'data'" in errors

    def test_multiple_validation_errors(self):
        """Test multiple validation errors are collected."""
        template_data = {
            "nodes": [
                {"data": {"type": "input"}},  # Missing id
                {"id": "node2"},  # Missing data
            ],
            "edges": "not_a_list",
        }
        errors = validate_template_structure(template_data, "test.json")
        assert len(errors) == 3
        assert "Node 0 missing 'id'" in str(errors)
        assert "Node 1 missing 'data'" in str(errors)
        assert "'edges' must be a list" in str(errors)


class TestValidateFlowCanBuild:
    """Test cases for validate_flow_can_build function."""

    @patch("langflow.utils.template_validation.Graph")
    def test_valid_flow_builds_successfully(self, mock_graph_class):
        """Test validation passes when flow builds successfully."""
        # Setup mock graph
        mock_graph = Mock()
        mock_graph.vertices = [Mock(id="vertex1"), Mock(id="vertex2")]
        mock_graph_class.from_payload.return_value = mock_graph

        template_data = {
            "nodes": [{"id": "node1", "data": {"type": "input"}}],
            "edges": [],
        }

        errors = validate_flow_can_build(template_data, "test.json")
        assert errors == []
        mock_graph_class.from_payload.assert_called_once()
        mock_graph.validate_stream.assert_called_once()

    @patch("langflow.utils.template_validation.Graph")
    def test_flow_build_fails_with_exception(self, mock_graph_class):
        """Test validation fails when flow build raises exception."""
        mock_graph_class.from_payload.side_effect = ValueError("Build failed")

        template_data = {"nodes": [], "edges": []}
        errors = validate_flow_can_build(template_data, "test.json")
        assert len(errors) == 1
        assert "test.json: Failed to build flow graph: Build failed" in errors

    @patch("langflow.utils.template_validation.Graph")
    def test_flow_has_no_vertices(self, mock_graph_class):
        """Test validation fails when flow has no vertices."""
        mock_graph = Mock()
        mock_graph.vertices = []
        mock_graph_class.from_payload.return_value = mock_graph

        template_data = {"nodes": [], "edges": []}
        errors = validate_flow_can_build(template_data, "test.json")
        assert "test.json: Flow has no vertices after building" in errors

    @patch("langflow.utils.template_validation.Graph")
    def test_vertex_missing_id(self, mock_graph_class):
        """Test validation fails when vertex is missing ID."""
        mock_vertex = Mock()
        mock_vertex.id = None
        mock_graph = Mock()
        mock_graph.vertices = [mock_vertex]
        mock_graph_class.from_payload.return_value = mock_graph

        template_data = {"nodes": [], "edges": []}
        errors = validate_flow_can_build(template_data, "test.json")
        assert "test.json: Vertex missing ID" in errors

    @patch("langflow.utils.template_validation.Graph")
    def test_uses_unique_flow_id(self, mock_graph_class):
        """Test that unique flow ID and name are used."""
        mock_graph = Mock()
        mock_graph.vertices = [Mock(id="vertex1")]
        mock_graph_class.from_payload.return_value = mock_graph

        template_data = {"nodes": [], "edges": []}
        validate_flow_can_build(template_data, "my_flow.json")

        # Verify from_payload was called with proper parameters
        call_args = mock_graph_class.from_payload.call_args
        assert call_args[0][0] == template_data  # template_data
        assert len(call_args[0][1]) == 36  # UUID length
        assert call_args[0][2] == "my_flow"  # flow_name
        # The user_id is passed as a keyword argument
        assert call_args[1]["user_id"] == "test_user"

    @patch("langflow.utils.template_validation.Graph")
    def test_validate_stream_exception(self, mock_graph_class):
        """Test that validate_stream exceptions are caught."""
        mock_graph = Mock()
        mock_graph.vertices = [Mock(id="vertex1")]
        mock_graph.validate_stream.side_effect = ValueError("Stream validation failed")
        mock_graph_class.from_payload.return_value = mock_graph

        template_data = {"nodes": [], "edges": []}
        errors = validate_flow_can_build(template_data, "test.json")

        assert len(errors) == 1
        assert "Failed to build flow graph: Stream validation failed" in errors[0]


class TestValidateFlowCode:
    """Test cases for validate_flow_code function."""

    @patch("langflow.utils.template_validation.validate_code")
    def test_valid_flow_code(self, mock_validate_code):
        """Test validation passes when code is valid."""
        mock_validate_code.return_value = {
            "imports": {"errors": []},
            "function": {"errors": []},
        }

        template_data = {
            "data": {
                "nodes": [
                    {
                        "id": "node1",
                        "data": {
                            "id": "node1",
                            "node": {
                                "template": {
                                    "code_field": {
                                        "type": "code",
                                        "value": "def hello(): return 'world'",
                                    }
                                }
                            },
                        },
                    }
                ]
            }
        }

        errors = validate_flow_code(template_data, "test.json")
        assert errors == []
        mock_validate_code.assert_called_once_with("def hello(): return 'world'")

    @patch("langflow.utils.template_validation.validate_code")
    def test_code_import_errors(self, mock_validate_code):
        """Test validation fails when code has import errors."""
        mock_validate_code.return_value = {
            "imports": {"errors": ["Module not found: nonexistent_module"]},
            "function": {"errors": []},
        }

        template_data = {
            "nodes": [
                {
                    "data": {
                        "id": "node1",
                        "node": {
                            "template": {
                                "code_field": {
                                    "type": "code",
                                    "value": "import nonexistent_module",
                                }
                            }
                        },
                    }
                }
            ]
        }

        errors = validate_flow_code(template_data, "test.json")
        assert len(errors) == 1
        assert "Import error in node node1: Module not found: nonexistent_module" in errors[0]

    @patch("langflow.utils.template_validation.validate_code")
    def test_code_function_errors(self, mock_validate_code):
        """Test validation fails when code has function errors."""
        mock_validate_code.return_value = {
            "imports": {"errors": []},
            "function": {"errors": ["Syntax error in function"]},
        }

        template_data = {
            "nodes": [
                {
                    "data": {
                        "id": "node2",
                        "node": {
                            "template": {
                                "code_field": {
                                    "type": "code",
                                    "value": "def broken(: pass",
                                }
                            }
                        },
                    }
                }
            ]
        }

        errors = validate_flow_code(template_data, "test.json")
        assert len(errors) == 1
        assert "Function error in node node2: Syntax error in function" in errors[0]

    def test_no_code_fields(self):
        """Test validation passes when there are no code fields."""
        template_data = {
            "nodes": [{"data": {"node": {"template": {"text_field": {"type": "text", "value": "hello"}}}}}]
        }

        errors = validate_flow_code(template_data, "test.json")
        assert errors == []

    def test_empty_code_value(self):
        """Test validation passes when code value is empty."""
        template_data = {"nodes": [{"data": {"node": {"template": {"code_field": {"type": "code", "value": ""}}}}}]}

        errors = validate_flow_code(template_data, "test.json")
        assert errors == []

    def test_code_validation_exception(self):
        """Test validation handles exceptions gracefully."""
        template_data = {
            "nodes": [{"data": {"node": {"template": {"code_field": {"type": "code", "value": "def test(): pass"}}}}}]
        }

        with patch("langflow.utils.template_validation.validate_code", side_effect=ValueError("Unexpected error")):
            errors = validate_flow_code(template_data, "test.json")
            assert len(errors) == 1
            assert "Code validation failed: Unexpected error" in errors[0]

    def test_code_validation_other_exceptions(self):
        """Test validation handles different exception types."""
        template_data = {
            "nodes": [{"data": {"node": {"template": {"code_field": {"type": "code", "value": "def test(): pass"}}}}}]
        }

        # Test TypeError
        with patch("langflow.utils.template_validation.validate_code", side_effect=TypeError("Type error")):
            errors = validate_flow_code(template_data, "test.json")
            assert len(errors) == 1
            assert "Code validation failed: Type error" in errors[0]

        # Test KeyError
        with patch("langflow.utils.template_validation.validate_code", side_effect=KeyError("key")):
            errors = validate_flow_code(template_data, "test.json")
            assert len(errors) == 1
            assert "Code validation failed: 'key'" in errors[0]

        # Test AttributeError
        with patch("langflow.utils.template_validation.validate_code", side_effect=AttributeError("Attribute error")):
            errors = validate_flow_code(template_data, "test.json")
            assert len(errors) == 1
            assert "Code validation failed: Attribute error" in errors[0]


class TestValidateFlowExecution:
    """Test cases for validate_flow_execution function."""

    @pytest.mark.asyncio
    async def test_successful_flow_execution(self):
        """Test validation passes when flow execution succeeds."""
        # Mock client responses
        mock_client = AsyncMock()

        # Mock create flow response
        create_response = Mock()
        create_response.status_code = 201
        create_response.json.return_value = {"id": "flow123"}
        mock_client.post.return_value = create_response

        # Mock build response
        build_response = Mock()
        build_response.status_code = 200
        build_response.json.return_value = {"job_id": "job123"}

        # Mock events response
        events_response = Mock()
        events_response.status_code = 200
        events_response.aiter_lines = Mock(
            return_value=AsyncIteratorMock(
                [
                    '{"event": "vertices_sorted", "job_id": "job123", "data": {"ids": ["v1"]}}',
                    '{"event": "end_vertex", "job_id": "job123", "data": {"build_data": {"result": "success"}}}',
                    '{"event": "end", "job_id": "job123"}',
                ]
            )
        )

        # Set up call sequence
        mock_client.post.side_effect = [create_response, build_response]
        mock_client.get.return_value = events_response
        mock_client.delete.return_value = Mock()

        template_data = {"nodes": [], "edges": []}
        headers = {"Authorization": "Bearer token"}

        errors = await validate_flow_execution(mock_client, template_data, "test.json", headers)
        assert errors == []

        # Verify API calls
        assert mock_client.post.call_count == 2
        mock_client.get.assert_called_once()
        mock_client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_flow_creation_fails(self):
        """Test validation fails when flow creation fails."""
        mock_client = AsyncMock()
        create_response = Mock()
        create_response.status_code = 400
        mock_client.post.return_value = create_response

        template_data = {"nodes": [], "edges": []}
        headers = {"Authorization": "Bearer token"}

        errors = await validate_flow_execution(mock_client, template_data, "test.json", headers)
        assert len(errors) == 1
        assert "Failed to create flow: 400" in errors[0]

    @pytest.mark.asyncio
    async def test_flow_build_fails(self):
        """Test validation fails when flow build fails."""
        mock_client = AsyncMock()

        # Mock successful create
        create_response = Mock()
        create_response.status_code = 201
        create_response.json.return_value = {"id": "flow123"}

        # Mock failed build
        build_response = Mock()
        build_response.status_code = 500

        mock_client.post.side_effect = [create_response, build_response]
        mock_client.delete.return_value = Mock()

        template_data = {"nodes": [], "edges": []}
        headers = {"Authorization": "Bearer token"}

        errors = await validate_flow_execution(mock_client, template_data, "test.json", headers)
        assert len(errors) == 1
        assert "Failed to build flow: 500" in errors[0]

    @pytest.mark.asyncio
    async def test_execution_timeout(self):
        """Test validation fails when execution times out."""
        mock_client = AsyncMock()
        mock_client.post.side_effect = asyncio.TimeoutError()

        template_data = {"nodes": [], "edges": []}
        headers = {"Authorization": "Bearer token"}

        errors = await validate_flow_execution(mock_client, template_data, "test.json", headers)
        assert len(errors) == 1
        assert "Flow execution timed out" in errors[0]

    @pytest.mark.asyncio
    async def test_cleanup_on_exception(self):
        """Test that flow cleanup happens even when exceptions occur."""
        mock_client = AsyncMock()

        # Mock successful create
        create_response = Mock()
        create_response.status_code = 201
        create_response.json.return_value = {"id": "flow123"}

        # Mock build that raises exception
        mock_client.post.side_effect = [create_response, ValueError("Build error")]
        mock_client.delete.return_value = Mock()

        template_data = {"nodes": [], "edges": []}
        headers = {"Authorization": "Bearer token", "timeout": 10}

        errors = await validate_flow_execution(mock_client, template_data, "test.json", headers)
        assert len(errors) == 1
        assert "Flow execution validation failed: Build error" in errors[0]

        # Verify cleanup was called
        mock_client.delete.assert_called_once_with("api/v1/flows/flow123", headers=headers, timeout=10)


class TestValidateEventStream:
    """Test cases for _validate_event_stream function."""

    @pytest.mark.asyncio
    async def test_valid_event_stream(self):
        """Test validation passes for valid event stream."""
        mock_response = Mock()
        mock_response.aiter_lines = Mock(
            return_value=AsyncIteratorMock(
                [
                    '{"event": "vertices_sorted", "job_id": "job123", "data": {"ids": ["v1", "v2"]}}',
                    '{"event": "end_vertex", "job_id": "job123", "data": {"build_data": {"result": "success"}}}',
                    '{"event": "end_vertex", "job_id": "job123", "data": {"build_data": {"result": "success"}}}',
                    '{"event": "end", "job_id": "job123"}',
                ]
            )
        )

        errors = []
        await _validate_event_stream(mock_response, "job123", "test.json", errors)
        assert errors == []

    @pytest.mark.asyncio
    async def test_missing_end_event(self):
        """Test validation fails when end event is missing."""
        mock_response = Mock()
        mock_response.aiter_lines = Mock(
            return_value=AsyncIteratorMock(
                ['{"event": "vertices_sorted", "job_id": "job123", "data": {"ids": ["v1"]}}']
            )
        )

        errors = []
        await _validate_event_stream(mock_response, "job123", "test.json", errors)
        assert len(errors) == 1
        assert "Missing end event in execution" in errors[0]

    @pytest.mark.asyncio
    async def test_job_id_mismatch(self):
        """Test validation fails when job ID doesn't match."""
        mock_response = Mock()
        mock_response.aiter_lines = Mock(
            return_value=AsyncIteratorMock(
                [
                    '{"event": "vertices_sorted", "job_id": "wrong_job", "data": {"ids": ["v1"]}}',
                    '{"event": "end", "job_id": "job123"}',
                ]
            )
        )

        errors = []
        await _validate_event_stream(mock_response, "job123", "test.json", errors)
        assert len(errors) == 1
        assert "Job ID mismatch in event stream" in errors[0]

    @pytest.mark.asyncio
    async def test_invalid_json_in_stream(self):
        """Test validation handles invalid JSON in event stream."""
        mock_response = Mock()
        mock_response.aiter_lines = Mock(
            return_value=AsyncIteratorMock(["invalid json", '{"event": "end", "job_id": "job123"}'])
        )

        errors = []
        await _validate_event_stream(mock_response, "job123", "test.json", errors)
        assert len(errors) == 1
        assert "Invalid JSON in event stream: invalid json" in errors[0]

    @pytest.mark.asyncio
    async def test_error_event_handling(self):
        """Test validation handles error events properly."""
        mock_response = Mock()
        mock_response.aiter_lines = Mock(
            return_value=AsyncIteratorMock(
                [
                    '{"event": "error", "job_id": "job123", "data": {"error": "Something went wrong"}}',
                    '{"event": "error", "job_id": "job123", "data": {"error": "False"}}',  # Should be ignored
                    '{"event": "error", "job_id": "job123", "data": "String error"}',
                    '{"event": "end", "job_id": "job123"}',
                ]
            )
        )

        errors = []
        await _validate_event_stream(mock_response, "job123", "test.json", errors)
        assert len(errors) == 2
        assert "Flow execution error: Something went wrong" in errors[0]
        assert "Flow execution error: String error" in errors[1]

    @pytest.mark.asyncio
    async def test_missing_vertex_ids(self):
        """Test validation fails when vertices_sorted event missing IDs."""
        mock_response = Mock()
        mock_response.aiter_lines = Mock(
            return_value=AsyncIteratorMock(
                [
                    '{"event": "vertices_sorted", "job_id": "job123", "data": {}}',
                    '{"event": "end", "job_id": "job123"}',
                ]
            )
        )

        errors = []
        await _validate_event_stream(mock_response, "job123", "test.json", errors)
        assert len(errors) == 1
        assert "Missing vertex IDs in vertices_sorted event" in errors[0]

    @pytest.mark.asyncio
    async def test_missing_build_data(self):
        """Test validation fails when end_vertex event missing build_data."""
        mock_response = Mock()
        mock_response.aiter_lines = Mock(
            return_value=AsyncIteratorMock(
                [
                    '{"event": "end_vertex", "job_id": "job123", "data": {}}',
                    '{"event": "end", "job_id": "job123"}',
                ]
            )
        )

        errors = []
        await _validate_event_stream(mock_response, "job123", "test.json", errors)
        assert len(errors) == 1
        assert "Missing build_data in end_vertex event" in errors[0]

    @pytest.mark.asyncio
    async def test_event_stream_timeout(self):
        """Test validation handles timeout gracefully."""

        class SlowAsyncIterator:
            """Async iterator that will cause timeout."""

            def __aiter__(self):
                return self

            async def __anext__(self):
                await asyncio.sleep(10)  # Will cause timeout
                return '{"event": "end", "job_id": "job123"}'

        mock_response = Mock()
        mock_response.aiter_lines = Mock(return_value=SlowAsyncIterator())

        errors = []
        await _validate_event_stream(mock_response, "job123", "test.json", errors)
        assert len(errors) == 1
        assert "Flow execution timeout" in errors[0]

    @pytest.mark.asyncio
    async def test_common_event_types_ignored(self):
        """Test that common event types don't cause errors."""
        mock_response = Mock()
        mock_response.aiter_lines = Mock(
            return_value=AsyncIteratorMock(
                [
                    '{"event": "message", "job_id": "job123"}',
                    '{"event": "token", "job_id": "job123"}',
                    '{"event": "add_message", "job_id": "job123"}',
                    '{"event": "stream_closed", "job_id": "job123"}',
                    '{"event": "end", "job_id": "job123"}',
                ]
            )
        )

        errors = []
        await _validate_event_stream(mock_response, "job123", "test.json", errors)
        assert errors == []

    @pytest.mark.asyncio
    async def test_vertices_sorted_without_end_vertex_events(self):
        """Test validation with vertices_sorted but no end_vertex events."""
        mock_response = Mock()
        mock_response.aiter_lines = Mock(
            return_value=AsyncIteratorMock(
                [
                    '{"event": "vertices_sorted", "job_id": "job123", "data": {"ids": ["v1", "v2"]}}',
                    '{"event": "end", "job_id": "job123"}',
                ]
            )
        )

        errors = []
        await _validate_event_stream(mock_response, "job123", "test.json", errors)
        assert errors == []

    @pytest.mark.asyncio
    async def test_vertex_count_tracking(self):
        """Test that vertex_count is properly tracked."""
        mock_response = Mock()
        mock_response.aiter_lines = Mock(
            return_value=AsyncIteratorMock(
                [
                    '{"event": "vertices_sorted", "job_id": "job123", "data": {"ids": ["v1", "v2", "v3"]}}',
                    '{"event": "end_vertex", "job_id": "job123", "data": {"build_data": {"result": "success"}}}',
                    '{"event": "end_vertex", "job_id": "job123", "data": {"build_data": {"result": "success"}}}',
                    '{"event": "end_vertex", "job_id": "job123", "data": {"build_data": {"result": "success"}}}',
                    '{"event": "end", "job_id": "job123"}',
                ]
            )
        )

        errors = []
        await _validate_event_stream(mock_response, "job123", "test.json", errors)
        assert errors == []

    @pytest.mark.asyncio
    async def test_empty_lines_in_stream(self):
        """Test that empty lines in event stream are properly handled."""
        mock_response = Mock()
        mock_response.aiter_lines = Mock(
            return_value=AsyncIteratorMock(
                [
                    "",  # Empty line
                    '{"event": "vertices_sorted", "job_id": "job123", "data": {"ids": ["v1"]}}',
                    "",  # Another empty line
                    '{"event": "end", "job_id": "job123"}',
                    "",  # Empty line at end
                ]
            )
        )

        errors = []
        await _validate_event_stream(mock_response, "job123", "test.json", errors)
        assert errors == []

    @pytest.mark.asyncio
    async def test_event_stream_validation_exception(self):
        """Test that event stream validation handles exceptions properly."""
        mock_response = Mock()
        mock_response.aiter_lines = Mock(
            return_value=AsyncIteratorMock(
                [
                    '{"event": "end", "job_id": "job123"}',
                ]
            )
        )

        # Mock the json.loads to raise a different exception type
        errors = []
        with patch("langflow.utils.template_validation.json.loads", side_effect=TypeError("Type error")):
            await _validate_event_stream(mock_response, "job123", "test.json", errors)
            assert len(errors) == 1
            assert "Event stream validation failed: Type error" in errors[0]
