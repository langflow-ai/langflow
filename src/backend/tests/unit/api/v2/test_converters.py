"""Comprehensive unit tests for V2 Workflow API converters.

This test module provides extensive coverage of the converter functions that
transform between V2 workflow schemas and V1 schemas. Tests include:

Test Coverage:
    - Native body parsing (parse_workflow_run_request)
    - Nested value extraction from various data structures
    - Text extraction from different message formats
    - Model source and file path extraction
    - Output content simplification
    - Metadata building for non-output nodes
    - Response creation (job, error, workflow responses)
    - End-to-end conversion from RunResponse to WorkflowExecutionResponse

Test Strategy:
    - Uses realistic payload structures from actual components
    - Covers edge cases, error conditions, and malformed data
    - Tests with mock objects to simulate component outputs
    - Validates proper handling of duplicate names and missing data
"""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock
from uuid import uuid4

import pytest
from langflow.api.v2.converters import (
    _build_metadata_for_non_output,
    _extract_file_path,
    _extract_model_source,
    _extract_nested_value,
    _extract_text_from_message,
    _get_raw_content,
    _simplify_output_content,
    _single_output_text,
    create_error_response,
    create_job_response,
    run_response_to_workflow_response,
)
from lfx.schema.workflow import (
    ComponentOutput,
    ErrorDetail,
    JobStatus,
    WorkflowExecutionResponse,
    WorkflowJobResponse,
)


def _setup_graph_get_vertex(graph: Mock, vertices: list[Mock]) -> None:
    """Helper to setup graph.get_vertex() mock for tests.

    Args:
        graph: The mock graph object
        vertices: List of mock vertex objects
    """
    vertex_map = {v.id: v for v in vertices}
    graph.get_vertex = Mock(side_effect=lambda vid: vertex_map.get(vid))


class TestExtractNestedValue:
    """Test suite for _extract_nested_value helper function with realistic payload structures."""

    def test_extract_model_output_message_model_name(self):
        """Test extracting model_name from LLM output structure."""
        # Realistic structure from OpenAI/Anthropic LLM components
        data = {
            "model_output": {
                "message": {
                    "text": "AI response here",
                    "model_name": "gpt-4",
                    "sender": "AI",
                    "sender_name": "AI",
                }
            }
        }
        result = _extract_nested_value(data, "model_output", "message", "model_name")
        assert result == "gpt-4"

    def test_extract_result_message_from_data_output(self):
        """Test extracting result from Data component output."""
        # Structure from Data/Calculator components
        data = {"result": {"message": {"result": "42"}, "type": "object"}}
        result = _extract_nested_value(data, "result", "message")
        assert result == {"result": "42"}

    def test_extract_message_from_chat_output(self):
        """Test extracting message from ChatOutput structure."""
        # ChatOutput component structure
        data = {
            "message": {
                "message": "Hello, how can I help you?",
                "type": "text",
                "sender": "AI",
            }
        }
        result = _extract_nested_value(data, "message", "message")
        assert result == "Hello, how can I help you?"

    def test_extract_nested_value_error_handling(self):
        """Test error handling for missing keys and None values in path."""
        # Missing key
        data = {"outputs": {"result": "value"}}
        result = _extract_nested_value(data, "outputs", "nonexistent")
        assert result is None

        # None in path
        data = {"results": None}
        result = _extract_nested_value(data, "results", "data")
        assert result is None

    def test_extract_from_result_data_object(self):
        """Test extracting from ResultData object with attributes."""
        # Simulating ResultData from lfx.graph.schema
        obj = Mock()
        obj.outputs = {"message": {"text": "output text"}}
        obj.results = {"data": "result data"}

        result = _extract_nested_value(obj, "outputs", "message", "text")
        assert result == "output text"

    def test_extract_text_from_output_value(self):
        """Test extracting from OutputValue structure."""
        # OutputValue structure from lfx.schema.schema
        data = {"message": {"text": "Hello World"}, "type": "message"}
        result = _extract_nested_value(data, "message", "text")
        assert result == "Hello World"

    def test_extract_from_pinecone_output(self):
        """Test extracting from Pinecone vector store output structure."""
        # Pinecone vector store typical output
        data = {
            "results": {
                "matches": [
                    {"id": "vec1", "score": 0.95, "metadata": {"text": "result 1"}},
                    {"id": "vec2", "score": 0.87, "metadata": {"text": "result 2"}},
                ]
            }
        }
        result = _extract_nested_value(data, "results", "matches")
        assert result is not None
        assert len(result) == 2
        assert result[0]["score"] == 0.95

    def test_extract_from_chroma_output(self):
        """Test extracting from Chroma vector store output structure."""
        # Chroma vector store typical output
        data = {
            "results": {
                "ids": [["id1", "id2"]],
                "distances": [[0.1, 0.3]],
                "documents": [["doc1 text", "doc2 text"]],
            }
        }
        result = _extract_nested_value(data, "results", "documents")
        assert result == [["doc1 text", "doc2 text"]]

    def test_extract_from_weaviate_output(self):
        """Test extracting from Weaviate vector store output structure."""
        # Weaviate vector store typical output
        data = {
            "data": {
                "Get": {
                    "Document": [
                        {"text": "document 1", "_additional": {"distance": 0.15}},
                        {"text": "document 2", "_additional": {"distance": 0.22}},
                    ]
                }
            }
        }
        result = _extract_nested_value(data, "data", "Get", "Document")
        assert result is not None
        assert len(result) == 2
        assert result[0]["text"] == "document 1"

    def test_extract_from_retriever_output(self):
        """Test extracting from generic retriever output structure."""
        # Generic retriever output with documents
        data = {
            "documents": [
                {"page_content": "Retrieved doc 1", "metadata": {"source": "file1.txt"}},
                {"page_content": "Retrieved doc 2", "metadata": {"source": "file2.txt"}},
            ]
        }
        result = _extract_nested_value(data, "documents")
        assert result is not None
        assert len(result) == 2
        assert result[0]["page_content"] == "Retrieved doc 1"


class TestExtractTextFromMessage:
    """Test suite for _extract_text_from_message function with realistic message structures."""

    def test_extract_from_chat_output_nested_message(self):
        """Test extracting from ChatOutput component with nested message.message structure."""
        # Typical ChatOutput structure
        content = {
            "message": {
                "message": "Hello, how can I help you today?",
                "type": "text",
                "sender": "AI",
                "sender_name": "AI",
            }
        }
        result = _extract_text_from_message(content)
        assert result == "Hello, how can I help you today?"

    def test_extract_from_llm_output_message_text(self):
        """Test extracting from LLM output with message.text structure."""
        # LLM component output structure
        content = {
            "message": {
                "text": "This is the AI response",
                "model_name": "gpt-4",
                "sender": "AI",
            }
        }
        result = _extract_text_from_message(content)
        assert result == "This is the AI response"

    def test_extract_direct_message_string(self):
        """Test extracting direct message string."""
        # Simple message structure
        content = {"message": "Direct message text"}
        result = _extract_text_from_message(content)
        assert result == "Direct message text"

    def test_extract_from_text_message_structure(self):
        """Test extracting from text.message structure (rare but possible)."""
        # Alternative structure where text contains message
        content = {"text": {"message": "Text contains message"}}
        result = _extract_text_from_message(content)
        assert result == "Text contains message"

    def test_extract_from_text_text_structure(self):
        """Test extracting from text.text nested structure."""
        # Nested text structure
        content = {"text": {"text": "Nested text value"}}
        result = _extract_text_from_message(content)
        assert result == "Nested text value"

    def test_extract_direct_text_string(self):
        """Test extracting direct text string."""
        # Simple text structure
        content = {"text": "Direct text value"}
        result = _extract_text_from_message(content)
        assert result == "Direct text value"

    def test_extract_priority_message_message_first(self):
        """Test that message.message takes priority over other fields."""
        content = {
            "message": {"message": "Priority Message", "text": "Should not return this"},
            "text": "Also should not return this",
        }
        result = _extract_text_from_message(content)
        assert result == "Priority Message"

    def test_extract_priority_message_text_over_direct_text(self):
        """Test that message.text is checked before direct text."""
        content = {
            "message": {"text": "Message Text"},
            "text": "Direct Text",
        }
        result = _extract_text_from_message(content)
        assert result == "Message Text"

    def test_extract_from_output_value_message_structure(self):
        """Test extracting from OutputValue message structure."""
        # OutputValue from lfx.schema.schema
        content = {
            "message": {
                "message": "Output value message",
                "type": "message",
            },
            "type": "message",
        }
        result = _extract_text_from_message(content)
        assert result == "Output value message"

    def test_extract_no_extractable_text(self):
        """Test when no text can be extracted from various structures."""
        # No text fields present
        content = {"data": "some data", "type": "object", "results": {}}
        result = _extract_text_from_message(content)
        assert result is None

        # Empty dict
        content = {}
        result = _extract_text_from_message(content)
        assert result is None

    def test_extract_non_string_values(self):
        """Test with non-string values in message/text fields."""
        content = {"message": {"message": 123, "text": ["list", "of", "items"]}}
        result = _extract_text_from_message(content)
        assert result is None

    def test_extract_text_circular_reference(self):
        """Test handling of circular references (should not cause infinite loop)."""
        # Create a circular reference structure
        content: dict[str, Any] = {"message": {}}
        content["message"]["self_ref"] = content  # Circular reference
        content["message"]["text"] = "Should extract this"

        # Should handle gracefully and extract the text
        result = _extract_text_from_message(content)
        assert result == "Should extract this"

    def test_extract_text_extremely_nested(self):
        """Test handling of extremely nested structures (10+ levels)."""
        # Build a 12-level deep nested structure
        content: dict[str, Any] = {
            "level1": {
                "level2": {
                    "level3": {
                        "level4": {
                            "level5": {
                                "level6": {
                                    "level7": {
                                        "level8": {"level9": {"level10": {"level11": {"level12": "deep value"}}}}
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        # Should return None as it doesn't match expected patterns
        result = _extract_text_from_message(content)
        assert result is None

    def test_extract_text_mixed_types_in_path(self):
        """Test handling of mixed types (list, dict, string) in extraction path."""
        # Message contains a list instead of expected dict
        content = {"message": ["item1", "item2", "item3"]}
        result = _extract_text_from_message(content)
        assert result is None

        # Text contains an integer
        content = {"text": 12345}
        result = _extract_text_from_message(content)
        assert result is None

        # Message.message is a list
        content = {"message": {"message": ["not", "a", "string"]}}
        result = _extract_text_from_message(content)
        assert result is None

    def test_extract_from_embedding_output(self):
        """Test extracting from embedding component output structure."""
        # OpenAI/Cohere embeddings typically return vectors, not text
        # But may have metadata with text
        content = {"embeddings": [[0.1, 0.2, 0.3]], "text": "Text that was embedded"}
        result = _extract_text_from_message(content)
        assert result == "Text that was embedded"

    def test_extract_from_tool_output(self):
        """Test extracting from tool/function call output structure."""
        # Tool output with result message
        content = {
            "message": {
                "message": "Tool executed successfully: result data",
                "tool_name": "calculator",
                "tool_input": {"operation": "add", "numbers": [1, 2]},
            }
        }
        result = _extract_text_from_message(content)
        assert result == "Tool executed successfully: result data"


class TestExtractModelSource:
    """Test suite for _extract_model_source function."""

    def test_extract_model_source_openai(self):
        """Test extracting model source from OpenAI LLM output."""
        raw_content = {
            "model_output": {
                "message": {
                    "text": "AI response",
                    "model_name": "gpt-4-turbo",
                    "sender": "AI",
                }
            }
        }
        result = _extract_model_source(raw_content, "llm-123", "OpenAI LLM")

        assert result == {
            "id": "llm-123",
            "display_name": "OpenAI LLM",
            "source": "gpt-4-turbo",
        }

    def test_extract_model_source_anthropic(self):
        """Test extracting model source from Anthropic LLM output."""
        raw_content = {
            "model_output": {
                "message": {
                    "text": "Claude response",
                    "model_name": "claude-3-opus-20240229",
                }
            }
        }
        result = _extract_model_source(raw_content, "claude-456", "Anthropic Claude")

        assert result["source"] == "claude-3-opus-20240229"

    def test_extract_model_source_missing_model_name(self):
        """Test when model_name is missing."""
        raw_content = {"model_output": {"message": {"text": "response"}}}
        result = _extract_model_source(raw_content, "llm-123", "OpenAI LLM")
        assert result is None

    def test_extract_model_source_missing_structure(self):
        """Test when model_output structure is missing or empty."""
        # Missing structure
        raw_content = {"output": "some output"}
        result = _extract_model_source(raw_content, "llm-123", "OpenAI LLM")
        assert result is None

        # Empty dict
        result = _extract_model_source({}, "llm-123", "OpenAI LLM")
        assert result is None


class TestExtractFilePath:
    """Test suite for _extract_file_path function."""

    def test_extract_file_path_valid(self):
        """Test extracting file path from SaveToFile component."""
        raw_content = {"message": {"message": "File saved successfully to /path/to/file.txt"}}
        result = _extract_file_path(raw_content, "SaveToFile")
        assert result == "File saved successfully to /path/to/file.txt"

    def test_extract_file_path_case_insensitive(self):
        """Test case-insensitive 'saved successfully' check."""
        raw_content = {"message": {"message": "File SAVED SUCCESSFULLY to /path/file.txt"}}
        result = _extract_file_path(raw_content, "SaveToFile")
        assert result == "File SAVED SUCCESSFULLY to /path/file.txt"

    def test_extract_file_path_wrong_component_type(self):
        """Test that non-SaveToFile components return None."""
        raw_content = {"message": {"message": "File saved successfully to /path/to/file.txt"}}
        result = _extract_file_path(raw_content, "ChatOutput")
        assert result is None

    def test_extract_file_path_missing_message(self):
        """Test when message structure is missing."""
        # Missing message structure
        raw_content = {"output": "some output"}
        result = _extract_file_path(raw_content, "SaveToFile")
        assert result is None

        # Message present - should return it regardless of content
        # (Changed behavior: no longer filters by "saved successfully" keyword)
        raw_content = {"message": {"message": "File processing failed"}}
        result = _extract_file_path(raw_content, "SaveToFile")
        assert result == "File processing failed"


class TestGetRawContent:
    """Test suite for _get_raw_content function."""

    def test_get_raw_content_from_outputs(self):
        """Test extracting from outputs attribute (ResultData structure)."""
        data = Mock()
        data.outputs = {"message": {"text": "output text"}}
        data.results = None
        data.messages = None

        result = _get_raw_content(data)
        assert result == {"message": {"text": "output text"}}

    def test_get_raw_content_from_results(self):
        """Test extracting from results attribute."""
        data = Mock()
        data.outputs = None
        data.results = {"result": "value"}
        data.messages = None

        result = _get_raw_content(data)
        assert result == {"result": "value"}

    def test_get_raw_content_from_messages(self):
        """Test extracting from messages attribute."""
        data = Mock()
        data.outputs = None
        data.results = None
        data.messages = [{"text": "message"}]

        result = _get_raw_content(data)
        assert result == [{"text": "message"}]

    def test_get_raw_content_from_dict_results(self):
        """Test extracting from dict with results or content key."""
        # Dict with results key
        data = {"results": {"result": "value"}}
        result = _get_raw_content(data)
        assert result == {"result": "value"}

        # Dict with content key
        data = {"content": {"result": "value"}}
        result = _get_raw_content(data)
        assert result == {"result": "value"}

    def test_get_raw_content_priority_outputs(self):
        """Test that outputs takes priority over results."""
        data = Mock()
        data.outputs = {"from": "outputs"}
        data.results = {"from": "results"}
        data.messages = None

        result = _get_raw_content(data)
        assert result == {"from": "outputs"}

    def test_get_raw_content_fallback(self):
        """Test fallback returns data as-is."""
        data = "raw string data"
        result = _get_raw_content(data)
        assert result == "raw string data"


class TestSimplifyOutputContent:
    """Test suite for _simplify_output_content function."""

    def test_simplify_message_type(self):
        """Test simplifying message type content."""
        content = {"message": {"message": "Hello World"}}
        result = _simplify_output_content(content, "message")
        assert result == "Hello World"

    def test_simplify_text_type(self):
        """Test simplifying text type content."""
        content = {"text": "Hello World"}
        result = _simplify_output_content(content, "text")
        assert result == "Hello World"

    def test_simplify_data_type(self):
        """Test simplifying data type content."""
        content = {"result": {"message": {"result": "4"}, "type": "object"}}
        result = _simplify_output_content(content, "data")
        assert result == {"result": "4"}

    def test_simplify_data_type_no_extraction(self):
        """Test data type when extraction path doesn't exist."""
        content = {"data": "raw data"}
        result = _simplify_output_content(content, "data")
        assert result == {"data": "raw data"}

    def test_simplify_unknown_type(self):
        """Test that unknown types return content as-is."""
        content = {"custom": "data"}
        result = _simplify_output_content(content, "custom_type")
        assert result == {"custom": "data"}

    def test_simplify_non_dict_content(self):
        """Test that non-dict content is returned as-is."""
        content = "plain string"
        result = _simplify_output_content(content, "message")
        assert result == "plain string"

    def test_simplify_message_no_text_found(self):
        """Test message type when no text can be extracted."""
        content = {"data": "some data"}
        result = _simplify_output_content(content, "message")
        assert result == {"data": "some data"}


class TestBuildMetadataForNonOutput:
    """Test suite for _build_metadata_for_non_output function."""

    def test_build_metadata_llm_component(self):
        """Test building metadata for LLM component."""
        raw_content = {"model_output": {"message": {"model_name": "gpt-4", "text": "response"}}}
        metadata = _build_metadata_for_non_output(raw_content, "llm-123", "OpenAI LLM", "OpenAIModel", "message")

        assert "source" in metadata
        assert metadata["source"]["source"] == "gpt-4"
        assert metadata["source"]["id"] == "llm-123"

    def test_build_metadata_save_to_file(self):
        """Test building metadata for SaveToFile component."""
        raw_content = {"message": {"message": "File saved successfully to /path/to/file.txt"}}
        metadata = _build_metadata_for_non_output(raw_content, "save-123", "Save File", "SaveToFile", "message")
        assert "file_path" in metadata
        assert metadata["file_path"] == "File saved successfully to /path/to/file.txt"

    def test_build_metadata_vector_store(self):
        """Test building metadata for vector store components."""
        # Pinecone vector store with index info
        raw_content = {
            "message": {
                "message": "Stored 5 vectors in index 'documents'",
                "index_name": "documents",
                "dimension": 1536,
                "metric": "cosine",
            }
        }
        metadata = _build_metadata_for_non_output(
            raw_content, "pinecone-123", "Pinecone Store", "PineconeVectorStore", "message"
        )

        # Should not extract special metadata (no model_name or file path)
        # But the raw message structure is preserved
        assert metadata == {}

    def test_build_metadata_retriever(self):
        """Test building metadata for retriever components."""
        # Retriever with search metadata
        raw_content = {
            "message": {"message": "Retrieved 3 documents", "query": "search term", "top_k": 3, "avg_score": 0.85}
        }
        metadata = _build_metadata_for_non_output(
            raw_content, "retriever-123", "Document Retriever", "VectorStoreRetriever", "message"
        )

        # Should not extract special metadata (no model_name or file path)
        assert metadata == {}

    def test_build_metadata_both_source_and_file(self):
        """Test building metadata with both source and file_path."""
        raw_content = {
            "model_output": {"message": {"model_name": "gpt-4"}},
            "message": {"message": "File saved successfully to /path/file.txt"},
        }
        metadata = _build_metadata_for_non_output(raw_content, "save-123", "Save File", "SaveToFile", "message")

        assert "source" in metadata
        assert "file_path" in metadata

    def test_build_metadata_non_message_type(self):
        """Test that non-message types return empty metadata."""
        raw_content = {"data": "some data"}
        metadata = _build_metadata_for_non_output(raw_content, "comp-123", "Component", "DataProcessor", "data")
        assert metadata == {}

    def test_build_metadata_non_dict_content(self):
        """Test that non-dict or empty content returns empty metadata."""
        # Non-dict content
        metadata = _build_metadata_for_non_output("string content", "comp-123", "Component", "TextProcessor", "message")
        assert metadata == {}

        # Empty dict
        metadata = _build_metadata_for_non_output({}, "comp-123", "Component", "Processor", "message")
        assert metadata == {}


class TestCreateJobResponse:
    """Test suite for create_job_response function."""

    def test_create_job_response_structure(self):
        """Test job response structure and timestamp format."""
        job_id = uuid4()
        flow_id = "flow-678"
        response = create_job_response(str(job_id), flow_id)

        assert isinstance(response, WorkflowJobResponse)
        assert response.job_id == job_id
        assert response.flow_id == flow_id
        assert response.status == JobStatus.QUEUED
        assert response.errors == []
        assert response.created_timestamp is not None
        # Verify timestamp format (ISO format should contain 'T')
        assert isinstance(response.created_timestamp, str)
        assert "T" in response.created_timestamp


class TestCreateErrorResponse:
    """Test suite for create_error_response function."""

    def test_create_error_response_structure(self):
        """Test error response structure."""
        flow_id = "flow-123"
        job_id = uuid4()
        request_inputs = {"test": "input"}
        error = ValueError("Test error message")

        response = create_error_response(flow_id, str(job_id), request_inputs, error)

        assert isinstance(response, WorkflowExecutionResponse)
        assert response.flow_id == flow_id
        assert response.job_id == job_id
        assert response.status == JobStatus.FAILED
        assert len(response.errors) == 1
        assert response.outputs == {}

    def test_create_error_response_error_details(self):
        """Test error details in response."""
        error = RuntimeError("Runtime error occurred")
        job_id = str(uuid4())
        response = create_error_response("flow-1", job_id, {}, error)

        error_detail = response.errors[0]
        assert isinstance(error_detail, ErrorDetail)
        assert error_detail.error == "Runtime error occurred"
        assert error_detail.code == "EXECUTION_ERROR"
        assert error_detail.details["error_type"] == "RuntimeError"
        assert error_detail.details["flow_id"] == "flow-1"

    def test_create_error_response_preserves_inputs(self):
        """Test that original inputs are preserved in error response."""
        inputs = {"component.param": "value"}
        request_inputs = inputs
        error = Exception("Error")

        response = create_error_response("flow-1", str(uuid4()), request_inputs, error)
        assert response.inputs == inputs

    def test_create_error_response_preserves_globals(self):
        """Test that body globals are preserved in error response."""
        globals_ = {"FILENAME": "relatório—final.pdf", "OWNER_NAME": "José"}
        error = Exception("Error")

        response = create_error_response("flow-1", str(uuid4()), {}, error, effective_globals=globals_)
        assert response.globals == globals_

    def test_create_error_response_has_no_output_text_or_session(self):
        """The failed path must not surface a text answer or a session to continue."""
        response = create_error_response("flow-1", str(uuid4()), {}, Exception("boom"))
        assert response.output_text is None
        assert response.session_id is None


class TestRunResponseToWorkflowResponse:
    """Test suite for run_response_to_workflow_response function."""

    def test_run_response_basic_output_node(self):
        """Test conversion with basic output node."""
        # Create mock graph
        graph = Mock()
        vertex = Mock()
        vertex.id = "output-123"
        vertex.display_name = "ChatOutput"
        vertex.vertex_type = "ChatOutput"
        vertex.is_output = True
        vertex.outputs = [{"types": ["Message"]}]

        graph.vertices = [vertex]
        graph.get_terminal_nodes = Mock(return_value=["output-123"])
        _setup_graph_get_vertex(graph, [vertex])

        # Create mock run response
        run_response = Mock()
        run_response.session_id = None
        result_data = Mock()
        result_data.component_id = "output-123"
        result_data.outputs = {"message": {"message": "Hello World"}}
        result_data.metadata = {}

        run_output = Mock()
        run_output.outputs = [result_data]
        run_response.outputs = [run_output]

        # Create request
        request_inputs = {"test": "input"}

        # Convert
        job_id = uuid4()
        response = run_response_to_workflow_response(run_response, "flow-123", str(job_id), request_inputs, graph)

        assert isinstance(response, WorkflowExecutionResponse)
        assert response.flow_id == "flow-123"
        assert response.job_id == job_id
        assert response.status == JobStatus.COMPLETED
        assert "output-123" in response.outputs
        assert response.outputs["output-123"].content == "Hello World"

    def test_run_response_preserves_globals(self):
        """Test conversion echoes body globals for debugging."""
        graph = Mock()
        graph.vertices = []
        graph.get_terminal_nodes = Mock(return_value=[])

        run_response = Mock()
        run_response.session_id = None
        run_response.outputs = []

        globals_ = {"FILENAME": "relatório—final.pdf", "OWNER_NAME": "José"}

        response = run_response_to_workflow_response(
            run_response, "flow-123", str(uuid4()), {}, graph, effective_globals=globals_
        )

        assert response.globals == globals_

    def test_run_response_non_output_terminal_node(self):
        """Test conversion with non-output terminal node."""
        # Create mock graph
        graph = Mock()
        vertex = Mock()
        vertex.id = "llm-123"
        vertex.display_name = "LLM"
        vertex.vertex_type = "OpenAIModel"
        vertex.is_output = False
        vertex.outputs = [{"types": ["Message"]}]

        graph.vertices = [vertex]
        graph.get_terminal_nodes = Mock(return_value=["llm-123"])
        _setup_graph_get_vertex(graph, [vertex])

        # Create mock run response with model info
        run_response = Mock()
        run_response.session_id = None
        result_data = Mock()
        result_data.component_id = "llm-123"
        result_data.outputs = {"model_output": {"message": {"model_name": "gpt-4", "text": "response"}}}
        result_data.metadata = {}

        run_output = Mock()
        run_output.outputs = [result_data]
        run_response.outputs = [run_output]

        request_inputs = {}

        job_id = str(uuid4())
        response = run_response_to_workflow_response(run_response, "flow-1", job_id, request_inputs, graph)

        assert "llm-123" in response.outputs
        output = response.outputs["llm-123"]
        assert output.content is None  # Non-output message nodes don't show content
        assert "source" in output.metadata
        assert output.metadata["source"]["source"] == "gpt-4"

    def test_run_response_duplicate_display_names(self):
        """Test handling of duplicate display names."""
        # Create mock graph with duplicate display names
        graph = Mock()
        vertex1 = Mock()
        vertex1.id = "output-1"
        vertex1.display_name = "Output"
        vertex1.vertex_type = "ChatOutput"
        vertex1.is_output = True
        vertex1.outputs = [{"types": ["Message"]}]

        vertex2 = Mock()
        vertex2.id = "output-2"
        vertex2.display_name = "Output"
        vertex2.vertex_type = "ChatOutput"
        vertex2.is_output = True
        vertex2.outputs = [{"types": ["Message"]}]

        graph.vertices = [vertex1, vertex2]
        graph.get_terminal_nodes = Mock(return_value=["output-1", "output-2"])
        _setup_graph_get_vertex(graph, [vertex1, vertex2])

        run_response = Mock()
        run_response.session_id = None
        run_response.outputs = []

        request_inputs = {}

        job_id = str(uuid4())
        response = run_response_to_workflow_response(run_response, "flow-1", job_id, request_inputs, graph)

        # Should use IDs instead of duplicate display names
        assert "output-1" in response.outputs
        assert "output-2" in response.outputs
        # When duplicate display names are detected, IDs are used as keys
        # The metadata contains component_type but display_name is not added in current implementation
        assert response.outputs["output-1"].metadata.get("component_type") == "ChatOutput"
        assert response.outputs["output-2"].metadata.get("component_type") == "ChatOutput"

    def test_run_response_data_type_non_output(self):
        """Test that data type non-output nodes show content."""
        graph = Mock()
        vertex = Mock()
        vertex.id = "data-123"
        vertex.display_name = "DataNode"
        vertex.vertex_type = "DataProcessor"
        vertex.is_output = False
        vertex.outputs = [{"types": ["Data"]}]

        graph.vertices = [vertex]
        graph.get_terminal_nodes = Mock(return_value=["data-123"])
        _setup_graph_get_vertex(graph, [vertex])

        run_response = Mock()
        run_response.session_id = None
        result_data = Mock()
        result_data.component_id = "data-123"
        result_data.outputs = {"result": {"message": {"result": "42"}}}
        result_data.metadata = {}

        run_output = Mock()
        run_output.outputs = [result_data]
        run_response.outputs = [run_output]

        request_inputs = {}

        job_id = str(uuid4())
        response = run_response_to_workflow_response(run_response, "flow-1", job_id, request_inputs, graph)

        # Data type non-output nodes should show content
        assert response.outputs["data-123"].content == {"result": "42"}

    def test_run_response_fallback_terminal_detection(self):
        """Test fallback terminal node detection when get_terminal_nodes fails."""
        graph = Mock()
        vertex = Mock()
        vertex.id = "output-123"
        vertex.display_name = "Output"
        vertex.vertex_type = "ChatOutput"
        vertex.is_output = True
        vertex.outputs = [{"types": ["Message"]}]

        graph.vertices = [vertex]
        # Simulate AttributeError
        graph.get_terminal_nodes = Mock(side_effect=AttributeError)
        graph.successor_map = {"output-123": []}  # No successors = terminal
        _setup_graph_get_vertex(graph, [vertex])

        run_response = Mock()
        run_response.session_id = None
        run_response.outputs = []

        request_inputs = {}

        job_id = str(uuid4())
        response = run_response_to_workflow_response(run_response, "flow-1", job_id, request_inputs, graph)

        assert "output-123" in response.outputs

    def test_run_response_preserves_inputs(self):
        """Test that inputs are preserved in response."""
        graph = Mock()
        graph.vertices = []
        graph.get_terminal_nodes = Mock(return_value=[])
        _setup_graph_get_vertex(graph, [])

        run_response = Mock()
        run_response.session_id = None
        run_response.outputs = []

        inputs = {"component.param": "value"}
        request_inputs = inputs

        job_id = str(uuid4())
        response = run_response_to_workflow_response(run_response, "flow-1", job_id, request_inputs, graph)
        assert response.inputs == inputs

    def test_run_response_vector_store_terminal(self):
        """Test vector store as terminal node."""
        graph = Mock()
        vertex = Mock()
        vertex.id = "pinecone-123"
        vertex.display_name = "Vector Store"
        vertex.vertex_type = "PineconeVectorStore"
        vertex.is_output = False
        vertex.outputs = [{"types": ["Data"]}]

        graph.vertices = [vertex]
        graph.get_terminal_nodes = Mock(return_value=["pinecone-123"])
        _setup_graph_get_vertex(graph, [vertex])

        run_response = Mock()
        run_response.session_id = None
        result_data = Mock()
        result_data.component_id = "pinecone-123"
        result_data.outputs = {"result": {"message": {"result": {"ids": ["vec1", "vec2"], "stored_count": 2}}}}
        result_data.metadata = {"index_name": "documents"}

        run_output = Mock()
        run_output.outputs = [result_data]
        run_response.outputs = [run_output]

        request_inputs = {}

        job_id = str(uuid4())
        response = run_response_to_workflow_response(run_response, "flow-1", job_id, request_inputs, graph)

        # Data type non-output nodes should show content
        assert "pinecone-123" in response.outputs
        assert response.outputs["pinecone-123"].content is not None
        assert "stored_count" in str(response.outputs["pinecone-123"].content)

    def test_run_response_retriever_with_metadata(self):
        """Test retriever with search metadata."""
        graph = Mock()
        vertex = Mock()
        vertex.id = "retriever-456"
        vertex.display_name = "Retriever"
        vertex.vertex_type = "VectorStoreRetriever"
        vertex.is_output = False
        vertex.outputs = [{"types": ["Data"]}]

        graph.vertices = [vertex]
        graph.get_terminal_nodes = Mock(return_value=["retriever-456"])
        _setup_graph_get_vertex(graph, [vertex])

        run_response = Mock()
        run_response.session_id = None
        result_data = Mock()
        result_data.component_id = "retriever-456"
        result_data.outputs = {
            "result": {"message": {"result": {"documents": ["doc1", "doc2", "doc3"], "scores": [0.95, 0.87, 0.82]}}}
        }
        result_data.metadata = {"query": "search term", "top_k": 3}

        run_output = Mock()
        run_output.outputs = [result_data]
        run_response.outputs = [run_output]

        request_inputs = {}

        job_id = str(uuid4())
        response = run_response_to_workflow_response(run_response, "flow-1", job_id, request_inputs, graph)

        # Should include content and metadata
        assert "retriever-456" in response.outputs
        output = response.outputs["retriever-456"]
        assert output.content is not None
        assert "documents" in str(output.content)
        # Metadata from result_data should be included
        assert output.metadata is not None
        assert output.metadata.get("query") == "search term"
        assert output.metadata.get("top_k") == 3

    def test_run_response_empty_outputs(self):
        """Test handling of empty outputs."""
        graph = Mock()
        graph.vertices = []
        graph.get_terminal_nodes = Mock(return_value=[])
        _setup_graph_get_vertex(graph, [])

        run_response = Mock()
        run_response.session_id = None
        run_response.outputs = None

        request_inputs = {}

        job_id = str(uuid4())
        response = run_response_to_workflow_response(run_response, "flow-1", job_id, request_inputs, graph)

        assert response.outputs == {}
        assert response.status == JobStatus.COMPLETED

    def test_run_response_corrupted_vertex_data(self):
        """Test handling of corrupted/malformed vertex data."""
        graph = Mock()

        # Create vertex with missing/corrupted attributes
        vertex = Mock()
        vertex.id = "corrupted-123"
        vertex.display_name = None  # Missing display name
        vertex.vertex_type = None  # Missing vertex type
        vertex.is_output = True
        vertex.outputs = None  # Missing outputs

        graph.vertices = [vertex]
        graph.get_terminal_nodes = Mock(return_value=["corrupted-123"])
        _setup_graph_get_vertex(graph, [vertex])

        run_response = Mock()
        run_response.session_id = None
        run_response.outputs = []

        request_inputs = {}

        # Should handle gracefully without crashing
        job_id = str(uuid4())
        response = run_response_to_workflow_response(run_response, "flow-1", job_id, request_inputs, graph)

        # Should use ID as fallback when display_name is None
        assert "corrupted-123" in response.outputs
        assert response.status == JobStatus.COMPLETED

    def test_run_response_missing_required_fields(self):
        """Test handling when result_data is missing required fields."""
        graph = Mock()
        vertex = Mock()
        vertex.id = "output-123"
        vertex.display_name = "Output"
        vertex.vertex_type = "ChatOutput"
        vertex.is_output = True
        vertex.outputs = [{"types": ["Message"]}]

        graph.vertices = [vertex]
        graph.get_terminal_nodes = Mock(return_value=["output-123"])
        _setup_graph_get_vertex(graph, [vertex])

        # Create result_data without component_id
        run_response = Mock()
        run_response.session_id = None
        result_data = Mock()
        result_data.component_id = None  # Missing component_id
        result_data.outputs = {"message": "test"}
        result_data.metadata = {}

        run_output = Mock()
        run_output.outputs = [result_data]
        run_response.outputs = [run_output]

        request_inputs = {}

        # Should handle gracefully - vertex won't match result_data
        job_id = str(uuid4())
        response = run_response_to_workflow_response(run_response, "flow-1", job_id, request_inputs, graph)

        # Output should exist but with no content (no matching result_data)
        assert "output-123" in response.outputs
        assert response.outputs["output-123"].content is None


_VALID_UUID = "67ccd2be-17f0-8190-81ff-3bb2cf6508e6"


class TestParseWorkflowRunRequest:
    """``parse_workflow_run_request`` projects ``WorkflowRunRequest`` onto ``ParsedWorkflowRun``."""

    def test_minimal_body_round_trips_with_defaults(self):
        from langflow.api.v2.converters import parse_workflow_run_request
        from lfx.schema.workflow import WorkflowRunRequest

        parsed = parse_workflow_run_request(WorkflowRunRequest(flow_id=_VALID_UUID))

        assert parsed.flow_id == _VALID_UUID
        assert parsed.tweaks == {}
        assert parsed.input_value == ""
        assert parsed.session_id is None
        assert parsed.run_id is None
        assert parsed.mode == "sync"
        assert parsed.start_component_id is None
        assert parsed.stop_component_id is None
        assert parsed.data is None
        assert parsed.files is None

    def test_full_body_round_trip(self):
        from langflow.api.v2.converters import parse_workflow_run_request
        from lfx.schema.workflow import WorkflowMode, WorkflowRunRequest

        request = WorkflowRunRequest(
            flow_id=_VALID_UUID,
            input_value="hello",
            tweaks={"ChatInput-abc": {"some_param": "v"}},
            session_id="session-123",
            mode=WorkflowMode.STREAM,
            stream_protocol="agui",
            data={"nodes": [], "edges": []},
            files=["a.txt", "b.png"],
            start_component_id="ChatInput-abc",
            stop_component_id="ChatOutput-xyz",
        )

        parsed = parse_workflow_run_request(request)

        assert parsed.flow_id == _VALID_UUID
        assert parsed.tweaks == {"ChatInput-abc": {"some_param": "v"}}
        assert parsed.input_value == "hello"
        assert parsed.session_id == "session-123"
        assert parsed.mode == "stream"
        assert parsed.start_component_id == "ChatInput-abc"
        assert parsed.stop_component_id == "ChatOutput-xyz"
        assert parsed.data == {"nodes": [], "edges": []}
        assert parsed.files == ["a.txt", "b.png"]

    def test_run_id_is_always_none_on_the_parsed_record(self):
        """The endpoint generates run_id; callers cannot supply it via the body."""
        from langflow.api.v2.converters import parse_workflow_run_request
        from lfx.schema.workflow import WorkflowRunRequest

        parsed = parse_workflow_run_request(WorkflowRunRequest(flow_id=_VALID_UUID))
        assert parsed.run_id is None


def _component_output(type_: str, content: Any) -> ComponentOutput:
    return ComponentOutput(type=type_, status=JobStatus.COMPLETED, content=content)


class TestSingleOutputText:
    """``_single_output_text`` surfaces the lone text answer, else None."""

    def test_single_message_output_returns_its_text(self):
        outputs = {"ChatOutput-abc": _component_output("message", "Hi there!")}
        assert _single_output_text(outputs) == "Hi there!"

    def test_single_text_output_returns_its_text(self):
        outputs = {"TextOutput-abc": _component_output("text", "plain answer")}
        assert _single_output_text(outputs) == "plain answer"

    def test_message_plus_data_returns_only_the_message(self):
        # A side DataOutput must not suppress the single text answer.
        outputs = {
            "ChatOutput-abc": _component_output("message", "the reply"),
            "DataOutput-xyz": _component_output("data", {"rows": [1, 2]}),
        }
        assert _single_output_text(outputs) == "the reply"

    def test_two_message_outputs_return_none(self):
        outputs = {
            "ChatOutput-a": _component_output("message", "Hi"),
            "ChatOutput-b": _component_output("message", "Bye"),
        }
        assert _single_output_text(outputs) is None

    def test_data_only_returns_none(self):
        outputs = {"DataOutput-xyz": _component_output("data", {"k": "v"})}
        assert _single_output_text(outputs) is None

    def test_no_outputs_returns_none(self):
        assert _single_output_text({}) is None

    def test_empty_string_answer_is_preserved(self):
        # A single, intentionally empty answer stays "" (distinct from None).
        outputs = {"ChatOutput-abc": _component_output("message", "")}
        assert _single_output_text(outputs) == ""

    def test_non_string_message_content_is_ignored(self):
        # content that isn't a plain string (e.g. None on a non-output node) doesn't count.
        outputs = {"ChatOutput-abc": _component_output("message", None)}
        assert _single_output_text(outputs) is None

    def test_string_content_data_output_excluded_by_type(self):
        # A data output whose content happens to be a plain string must still be
        # excluded by the TYPE filter alone, not merely by the non-str guard. This
        # isolates the type check: adding "data" to the accepted set would surface
        # this string as the answer, which is exactly what we must not do.
        outputs = {"DataOutput-xyz": _component_output("data", "looks like an answer but is data")}
        assert _single_output_text(outputs) is None


def _message_output_vertex(vertex_id: str) -> Mock:
    vertex = Mock()
    vertex.id = vertex_id
    vertex.display_name = "Chat Output"
    vertex.vertex_type = "ChatOutput"
    vertex.is_output = True
    vertex.outputs = [{"types": ["Message"]}]
    return vertex


def _message_result_data(component_id: str, text: str) -> Mock:
    result_data = Mock()
    result_data.component_id = component_id
    result_data.outputs = {"message": {"message": text}}
    result_data.metadata = {}
    return result_data


def _message_nonoutput_vertex(vertex_id: str) -> Mock:
    """A terminal LLM-style message node that is NOT an output (is_output=False)."""
    vertex = Mock()
    vertex.id = vertex_id
    vertex.display_name = "LLM"
    vertex.vertex_type = "OpenAIModel"
    vertex.is_output = False
    vertex.outputs = [{"types": ["Message"]}]
    return vertex


def _data_output_vertex(vertex_id: str) -> Mock:
    vertex = Mock()
    vertex.id = vertex_id
    vertex.display_name = "Data Output"
    vertex.vertex_type = "DataOutput"
    vertex.is_output = True
    vertex.outputs = [{"types": ["Data"]}]
    return vertex


def _data_result_data(component_id: str, payload: Any) -> Mock:
    result_data = Mock()
    result_data.component_id = component_id
    result_data.outputs = {"result": {"message": payload}}
    result_data.metadata = {}
    return result_data


def _text_output_vertex(vertex_id: str) -> Mock:
    vertex = Mock()
    vertex.id = vertex_id
    vertex.display_name = "Text Output"
    vertex.vertex_type = "TextOutput"
    vertex.is_output = True
    vertex.outputs = [{"types": ["Text"]}]
    return vertex


def _text_result_data(component_id: str, text: str) -> Mock:
    result_data = Mock()
    result_data.component_id = component_id
    result_data.outputs = {"text": {"text": text}}
    result_data.metadata = {}
    return result_data


def _graph_for(vertices: list[Mock]) -> Mock:
    graph = Mock()
    graph.vertices = vertices
    graph.get_terminal_nodes = Mock(return_value=[v.id for v in vertices])
    _setup_graph_get_vertex(graph, vertices)
    return graph


class TestOutputTextAndSessionId:
    """End-to-end: the sync response surfaces output_text and echoes session_id."""

    def test_single_chat_output_populates_output_text_and_session(self):
        vertex = _message_output_vertex("ChatOutput-abc")
        graph = _graph_for([vertex])

        run_response = Mock()
        run_response.session_id = "session-xyz"
        run_output = Mock()
        run_output.outputs = [_message_result_data("ChatOutput-abc", "Hi there!")]
        run_response.outputs = [run_output]

        response = run_response_to_workflow_response(run_response, "flow-1", str(uuid4()), {}, graph)

        assert response.output_text == "Hi there!"
        assert response.outputs["ChatOutput-abc"].content == "Hi there!"
        assert response.session_id == "session-xyz"

    def test_two_chat_outputs_leave_output_text_none(self):
        vertices = [_message_output_vertex("ChatOutput-a"), _message_output_vertex("ChatOutput-b")]
        graph = _graph_for(vertices)

        run_response = Mock()
        run_response.session_id = "session-xyz"
        run_output = Mock()
        run_output.outputs = [
            _message_result_data("ChatOutput-a", "Hi"),
            _message_result_data("ChatOutput-b", "Bye"),
        ]
        run_response.outputs = [run_output]

        response = run_response_to_workflow_response(run_response, "flow-1", str(uuid4()), {}, graph)

        assert response.output_text is None
        assert response.outputs["ChatOutput-a"].content == "Hi"
        assert response.outputs["ChatOutput-b"].content == "Bye"

    def test_session_id_none_passes_through(self):
        vertex = _message_output_vertex("ChatOutput-abc")
        graph = _graph_for([vertex])

        run_response = Mock()
        run_response.session_id = None
        run_output = Mock()
        run_output.outputs = [_message_result_data("ChatOutput-abc", "Hi")]
        run_response.outputs = [run_output]

        response = run_response_to_workflow_response(run_response, "flow-1", str(uuid4()), {}, graph)

        assert response.session_id is None
        assert response.output_text == "Hi"

    def test_terminal_non_output_message_leaves_output_text_none(self):
        # A terminal LLM (is_output=False) carries EXTRACTABLE text: if it were an
        # output node the converter would surface "raw model text" as content. But
        # because it is not an output node, content is suppressed to None, so
        # output_text must not surface that intermediate text as "the answer".
        # (If the is_output guard regressed, content would become "raw model text"
        # and this test would fail.)
        vertex = _message_nonoutput_vertex("LLM-xyz")
        graph = _graph_for([vertex])

        run_response = Mock()
        run_response.session_id = "session-xyz"
        run_output = Mock()
        run_output.outputs = [_message_result_data("LLM-xyz", "raw model text")]
        run_response.outputs = [run_output]

        response = run_response_to_workflow_response(run_response, "flow-1", str(uuid4()), {}, graph)

        assert response.outputs["LLM-xyz"].type == "message"
        assert response.outputs["LLM-xyz"].content is None
        assert response.output_text is None

    def test_chat_output_plus_data_output_still_surfaces_text(self):
        # The realistic "chat answer plus structured data" flow: a side DataOutput
        # classifies as type "data" and must not suppress the single text answer.
        chat = _message_output_vertex("ChatOutput-abc")
        data = _data_output_vertex("DataOutput-xyz")
        graph = _graph_for([chat, data])

        run_response = Mock()
        run_response.session_id = "session-xyz"
        run_output = Mock()
        run_output.outputs = [
            _message_result_data("ChatOutput-abc", "the reply"),
            _data_result_data("DataOutput-xyz", {"rows": [1, 2]}),
        ]
        run_response.outputs = [run_output]

        response = run_response_to_workflow_response(run_response, "flow-1", str(uuid4()), {}, graph)

        assert response.outputs["ChatOutput-abc"].type == "message"
        assert response.outputs["DataOutput-xyz"].type == "data"
        assert response.outputs["DataOutput-xyz"].content == {"rows": [1, 2]}
        assert response.output_text == "the reply"

    def test_data_only_flow_leaves_output_text_none(self):
        # A flow whose only terminal is a DataOutput produces a real type="data"
        # output, which the shortcut must exclude.
        data = _data_output_vertex("DataOutput-xyz")
        graph = _graph_for([data])

        run_response = Mock()
        run_response.session_id = "session-xyz"
        run_output = Mock()
        run_output.outputs = [_data_result_data("DataOutput-xyz", {"k": "v"})]
        run_response.outputs = [run_output]

        response = run_response_to_workflow_response(run_response, "flow-1", str(uuid4()), {}, graph)

        assert response.outputs["DataOutput-xyz"].type == "data"
        assert response.output_text is None

    def test_text_output_surfaces_output_text(self):
        # output_text is not ChatOutput-specific: a TextOutput (type "text") feeds it too.
        vertex = _text_output_vertex("TextOutput-abc")
        graph = _graph_for([vertex])

        run_response = Mock()
        run_response.session_id = "session-xyz"
        run_output = Mock()
        run_output.outputs = [_text_result_data("TextOutput-abc", "plain answer")]
        run_response.outputs = [run_output]

        response = run_response_to_workflow_response(run_response, "flow-1", str(uuid4()), {}, graph)

        assert response.outputs["TextOutput-abc"].type == "text"
        assert response.output_text == "plain answer"

    def test_output_entries_expose_only_the_de_nested_fields(self):
        # The outputs dict key already IS the component id, so each ComponentOutput
        # exposes exactly {type, status, content, metadata} and carries no redundant
        # inner id. Pinning the exact field set means adding a component_id field to
        # the ComponentOutput schema would fail here (the old "component_id not in
        # dump" check could never fail, since the schema has no such field).
        vertex = _message_output_vertex("ChatOutput-abc")
        graph = _graph_for([vertex])

        run_response = Mock()
        run_response.session_id = None
        run_output = Mock()
        run_output.outputs = [_message_result_data("ChatOutput-abc", "Hi")]
        run_response.outputs = [run_output]

        response = run_response_to_workflow_response(run_response, "flow-1", str(uuid4()), {}, graph)

        assert "ChatOutput-abc" in response.outputs
        assert set(response.outputs["ChatOutput-abc"].model_dump()) == {"type", "status", "content", "metadata"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
