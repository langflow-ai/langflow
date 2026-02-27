from unittest.mock import MagicMock, patch

import pytest
from lfx.components.llm_operations.llm_conditional_router import SmartRouterComponent
from lfx.schema.message import Message

from tests.base import ComponentTestBaseWithoutClient


class TestSmartRouterComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return SmartRouterComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "model": [
                {
                    "name": "gpt-4o",
                    "provider": "OpenAI",
                    "icon": "OpenAI",
                    "metadata": {
                        "model_class": "ChatOpenAI",
                        "model_name_param": "model",
                        "api_key_param": "api_key",  # pragma: allowlist secret
                    },
                }
            ],
            "input_text": "I love this product!",
            "routes": [
                {
                    "route_category": "Positive",
                    "route_description": "Positive feedback, satisfaction, or compliments",
                    "output_value": "",
                },
                {
                    "route_category": "Negative",
                    "route_description": "Complaints, issues, or dissatisfaction",
                    "output_value": "",
                },
            ],
            "enable_else_output": False,
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return []

    def _create_component_with_mock_categorization(self, categorization_result, *, enable_else=False):
        """Helper to create a component with a mocked categorization result."""
        component = SmartRouterComponent()
        component.routes = [
            {"route_category": "Positive", "route_description": "Good feedback", "output_value": ""},
            {"route_category": "Negative", "route_description": "Bad feedback", "output_value": ""},
        ]
        component.input_text = "Test input"
        component.enable_else_output = enable_else
        component.message = None
        component._categorization_result = categorization_result
        component.stop = MagicMock()
        return component

    def test_positive_output(self):
        """Test routing to positive category."""
        component = self._create_component_with_mock_categorization("Positive")

        result = component.process_case()

        assert isinstance(result, Message)
        assert result.text == "Test input"
        component.stop.assert_any_call("category_2_result")  # Negative should be stopped

    def test_negative_output(self):
        """Test routing to negative category."""
        component = self._create_component_with_mock_categorization("Negative")

        result = component.process_case()

        assert isinstance(result, Message)
        assert result.text == "Test input"
        component.stop.assert_any_call("category_1_result")  # Positive should be stopped

    def test_neutral_output_no_match(self):
        """Test when input doesn't match any category (no else output)."""
        component = self._create_component_with_mock_categorization("NONE", enable_else=False)

        result = component.process_case()

        assert isinstance(result, Message)
        assert result.text == ""
        assert component.status == "No match found and Else output is disabled"

    def test_else_output(self):
        """Test else output when no category matches."""
        component = self._create_component_with_mock_categorization("NONE", enable_else=True)

        result = component.default_response()

        assert isinstance(result, Message)
        assert result.text == "Test input"
        assert "Routed to Else (no match)" in component.status

    def test_categorization_caching(self):
        """Test that LLM categorization result is cached and only called once."""
        component = SmartRouterComponent()
        component.routes = [
            {"route_category": "Positive", "route_description": "", "output_value": ""},
        ]
        component.input_text = "Great product!"
        component.model = [{"name": "test-model", "provider": "Test"}]
        component._user_id = "test-user"
        component.api_key = "test-key"  # pragma: allowlist secret

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Positive"
        mock_llm.invoke.return_value = mock_response

        with patch("lfx.components.llm_operations.llm_conditional_router.get_llm", return_value=mock_llm):
            result1 = component._get_categorization()
            result2 = component._get_categorization()

        assert result1 == "Positive"
        assert result2 == "Positive"
        assert mock_llm.invoke.call_count == 1  # LLM only called once due to caching
