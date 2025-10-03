import json
import os
from unittest.mock import Mock, patch

import httpx
import pytest
import respx
from httpx import Response
from lfx.base.langwatch.utils import get_cached_evaluators
from lfx.components.langwatch.langwatch import LangWatchComponent
from lfx.schema.data import Data
from lfx.schema.dotdict import dotdict

from tests.base import ComponentTestBaseWithoutClient


class TestLangWatchComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return LangWatchComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "evaluator_name": "test_evaluator",
            "api_key": "test_api_key",
            "input": "test input",
            "output": "test output",
            "expected_output": "expected output",
            "contexts": "context1, context2",
            "timeout": 30,
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return []

    @pytest.fixture
    def mock_evaluators(self):
        """Mock evaluators data."""
        return {
            "test_evaluator": {
                "name": "test_evaluator",
                "requiredFields": ["input", "output"],
                "optionalFields": ["contexts"],
                "settings": {
                    "temperature": {
                        "description": "Temperature setting",
                        "default": 0.7,
                    }
                },
                "settings_json_schema": {
                    "properties": {
                        "temperature": {
                            "type": "number",
                            "default": 0.7,
                        }
                    }
                },
            },
            "boolean_evaluator": {
                "name": "boolean_evaluator",
                "requiredFields": ["input"],
                "optionalFields": [],
                "settings": {
                    "strict_mode": {
                        "description": "Strict mode setting",
                        "default": True,
                    }
                },
                "settings_json_schema": {
                    "properties": {
                        "strict_mode": {
                            "type": "boolean",
                            "default": True,
                        }
                    }
                },
            },
        }

    @pytest.fixture
    async def component(self, component_class, default_kwargs, mock_evaluators):
        """Return a component instance."""
        comp = component_class(**default_kwargs)
        comp.evaluators = mock_evaluators
        return comp

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        """Clear the LRU cache before each test."""
        get_cached_evaluators.cache_clear()

    @patch("lfx.components.langwatch.langwatch.httpx.get")
    async def test_set_evaluators_success(self, mock_get, component, mock_evaluators):
        """Test successful setting of evaluators."""
        mock_response = Mock()
        mock_response.json.return_value = {"evaluators": mock_evaluators}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        endpoint = "https://app.langwatch.ai"
        component.set_evaluators(endpoint)
        assert component.evaluators == mock_evaluators

    @patch("lfx.components.langwatch.langwatch.httpx.get")
    async def test_set_evaluators_empty_response(self, mock_get, component):
        """Test setting evaluators with empty response."""
        mock_response = Mock()
        mock_response.json.return_value = {"evaluators": {}}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        endpoint = "https://app.langwatch.ai"
        with pytest.raises(ValueError, match="No evaluators found"):
            component.set_evaluators(endpoint)

    def test_get_dynamic_inputs(self, component, mock_evaluators):
        """Test dynamic input generation."""
        evaluator = mock_evaluators["test_evaluator"]
        dynamic_inputs = component.get_dynamic_inputs(evaluator)

        # Should create inputs for contexts (from optionalFields)
        assert "contexts" in dynamic_inputs
        # Should create inputs for temperature (from settings)
        assert "temperature" in dynamic_inputs

    def test_get_dynamic_inputs_with_boolean_setting(self, component, mock_evaluators):
        """Test dynamic input generation with boolean settings."""
        evaluator = mock_evaluators["boolean_evaluator"]
        dynamic_inputs = component.get_dynamic_inputs(evaluator)

        # Should create boolean input for strict_mode
        assert "strict_mode" in dynamic_inputs

    def test_get_dynamic_inputs_error_handling(self, component):
        """Test error handling in dynamic input generation."""
        # Test with invalid evaluator data
        invalid_evaluator = {"invalid": "data"}
        result = component.get_dynamic_inputs(invalid_evaluator)
        assert result == {}

    @patch.dict(os.environ, {"LANGWATCH_ENDPOINT": "https://test.langwatch.ai"})
    def test_update_build_config_basic(self, component, mock_evaluators):
        """Test basic build config update."""
        build_config = dotdict(
            {
                "evaluator_name": {"options": [], "value": None},
                "api_key": {"value": "test_key"},
                "code": {"value": ""},
                "_type": {"value": ""},
                "input": {"value": ""},
                "output": {"value": ""},
                "timeout": {"value": 30},
            }
        )

        # Mock the get_evaluators method (which doesn't exist, so create it)
        def mock_get_evaluators(endpoint):  # noqa: ARG001
            return mock_evaluators

        with patch.object(component, "get_evaluators", side_effect=mock_get_evaluators, create=True):
            result = component.update_build_config(build_config, None, None)

            # Should populate evaluator options
            assert "test_evaluator" in result["evaluator_name"]["options"]
            assert "boolean_evaluator" in result["evaluator_name"]["options"]

    @patch.dict(os.environ, {"LANGWATCH_ENDPOINT": "https://test.langwatch.ai"})
    def test_update_build_config_with_evaluator_selection(self, component, mock_evaluators):
        """Test build config update with evaluator selection."""
        build_config = dotdict(
            {
                "evaluator_name": {"options": [], "value": None},
                "api_key": {"value": "test_key"},
                "code": {"value": ""},
                "_type": {"value": ""},
                "input": {"value": ""},
                "output": {"value": ""},
                "timeout": {"value": 30},
            }
        )

        # Mock the get_evaluators method (which doesn't exist, so create it)
        def mock_get_evaluators(endpoint):  # noqa: ARG001
            return mock_evaluators

        with patch.object(component, "get_evaluators", side_effect=mock_get_evaluators, create=True):
            # Initialize current_evaluator attribute
            component.current_evaluator = None
            result = component.update_build_config(build_config, "test_evaluator", "evaluator_name")

            # Should set the selected evaluator
            assert result["evaluator_name"]["value"] == "test_evaluator"

    @patch("lfx.components.langwatch.langwatch.httpx.get")
    @respx.mock
    async def test_evaluate_success(self, mock_get, component, mock_evaluators):
        """Test successful evaluation."""
        # Mock the evaluators HTTP request
        mock_response = Mock()
        mock_response.json.return_value = {"evaluators": mock_evaluators}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Mock the evaluation endpoint
        eval_url = "https://app.langwatch.ai/api/evaluations/test_evaluator/evaluate"
        expected_response = {"score": 0.95, "reasoning": "Good evaluation"}
        respx.post(eval_url).mock(return_value=Response(200, json=expected_response))

        # Set up component
        component.evaluator_name = "test_evaluator"
        component.api_key = "test_api_key"
        component.input = "test input"
        component.output = "test output"
        component.contexts = "context1, context2"

        result = await component.evaluate()

        assert isinstance(result, Data)
        assert result.data == expected_response

    @respx.mock
    async def test_evaluate_no_api_key(self, component):
        """Test evaluation with missing API key."""
        component.api_key = None

        result = await component.evaluate()

        assert isinstance(result, Data)
        assert result.data["error"] == "API key is required"

    async def test_evaluate_no_evaluators(self, component):
        """Test evaluation when no evaluators are available."""
        component.api_key = "test_api_key"
        component.evaluator_name = None

        # Mock set_evaluators to avoid external HTTP calls
        with patch.object(component, "set_evaluators"):
            component.evaluators = {}  # Set empty evaluators directly
            component.current_evaluator = None  # Initialize the attribute

            result = await component.evaluate()

            assert isinstance(result, Data)
            assert "No evaluator selected" in result.data["error"]

    @patch("lfx.components.langwatch.langwatch.httpx.get")
    @respx.mock
    async def test_evaluate_evaluator_not_found(self, mock_get, component, mock_evaluators):
        """Test evaluation with non-existent evaluator."""
        # Mock evaluators HTTP request
        mock_response = Mock()
        mock_response.json.return_value = {"evaluators": mock_evaluators}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        component.api_key = "test_api_key"
        component.evaluator_name = "non_existent_evaluator"

        result = await component.evaluate()

        assert isinstance(result, Data)
        assert "Selected evaluator 'non_existent_evaluator' not found" in result.data["error"]

    @patch("lfx.components.langwatch.langwatch.httpx.get")
    @respx.mock
    async def test_evaluate_http_error(self, mock_get, component, mock_evaluators):
        """Test evaluation with HTTP error."""
        # Mock evaluators HTTP request
        mock_response = Mock()
        mock_response.json.return_value = {"evaluators": mock_evaluators}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Mock evaluation endpoint with error
        eval_url = "https://app.langwatch.ai/api/evaluations/test_evaluator/evaluate"
        respx.post(eval_url).mock(side_effect=httpx.RequestError("Connection failed"))

        component.api_key = "test_api_key"
        component.evaluator_name = "test_evaluator"
        component.input = "test input"
        component.output = "test output"

        result = await component.evaluate()

        assert isinstance(result, Data)
        assert "Evaluation error" in result.data["error"]

    @patch("lfx.components.langwatch.langwatch.httpx.get")
    @respx.mock
    async def test_evaluate_with_tracing(self, mock_get, component, mock_evaluators):
        """Test evaluation with tracing service."""
        # Mock evaluators HTTP request
        mock_response = Mock()
        mock_response.json.return_value = {"evaluators": mock_evaluators}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Mock evaluation endpoint
        eval_url = "https://app.langwatch.ai/api/evaluations/test_evaluator/evaluate"
        expected_response = {"score": 0.95, "reasoning": "Good evaluation"}

        # Set up request capture
        request_data = None

        def capture_request(request):
            nonlocal request_data
            request_data = json.loads(request.content.decode())
            return Response(200, json=expected_response)

        respx.post(eval_url).mock(side_effect=capture_request)

        # Set up component with mock tracing
        component.api_key = "test_api_key"
        component.evaluator_name = "test_evaluator"
        component.input = "test input"
        component.output = "test output"

        # Mock tracing service
        mock_tracer = Mock()
        mock_tracer.trace_id = "test_trace_id"
        component._tracing_service = Mock()
        component._tracing_service.get_tracer.return_value = mock_tracer

        result = await component.evaluate()

        # Verify trace_id was included in the request
        assert request_data["settings"]["trace_id"] == "test_trace_id"
        assert isinstance(result, Data)
        assert result.data == expected_response

    @patch("lfx.components.langwatch.langwatch.httpx.get")
    @respx.mock
    async def test_evaluate_with_contexts_parsing(self, mock_get, component, mock_evaluators):
        """Test evaluation with contexts parsing."""
        # Mock evaluators HTTP request
        mock_response = Mock()
        mock_response.json.return_value = {"evaluators": mock_evaluators}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Mock evaluation endpoint
        eval_url = "https://app.langwatch.ai/api/evaluations/test_evaluator/evaluate"
        expected_response = {"score": 0.95, "reasoning": "Good evaluation"}

        # Set up request capture
        request_data = None

        def capture_request(request):
            nonlocal request_data
            request_data = json.loads(request.content.decode())
            return Response(200, json=expected_response)

        respx.post(eval_url).mock(side_effect=capture_request)

        # Set up component
        component.api_key = "test_api_key"
        component.evaluator_name = "test_evaluator"
        component.input = "test input"
        component.output = "test output"
        component.contexts = "context1, context2, context3"

        result = await component.evaluate()

        # Verify contexts were parsed correctly (contexts are split by comma, including whitespace)
        assert request_data["data"]["contexts"] == ["context1", " context2", " context3"]
        assert isinstance(result, Data)
        assert result.data == expected_response

    @patch("lfx.components.langwatch.langwatch.httpx.get")
    @respx.mock
    async def test_evaluate_timeout_handling(self, mock_get, component, mock_evaluators):
        """Test evaluation with timeout."""
        # Mock evaluators HTTP request
        mock_response = Mock()
        mock_response.json.return_value = {"evaluators": mock_evaluators}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Mock evaluation endpoint with timeout
        eval_url = "https://app.langwatch.ai/api/evaluations/test_evaluator/evaluate"
        respx.post(eval_url).mock(side_effect=httpx.TimeoutException("Request timed out"))

        component.api_key = "test_api_key"
        component.evaluator_name = "test_evaluator"
        component.input = "test input"
        component.output = "test output"
        component.timeout = 5

        result = await component.evaluate()

        assert isinstance(result, Data)
        assert "Evaluation error" in result.data["error"]
