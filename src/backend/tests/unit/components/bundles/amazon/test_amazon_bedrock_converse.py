"""Tests for the AmazonBedrockConverseComponent.

Verifies that the top_k parameter is correctly passed through
additional_model_request_fields to ChatBedrockConverse, fixing #14716.
"""

from unittest.mock import MagicMock, patch

import pytest

try:
    from lfx_amazon.components.amazon.amazon_bedrock_converse import AmazonBedrockConverseComponent
except ImportError:
    pytest.skip("lfx-amazon bundle not available", allow_module_level=True)

from tests.base import ComponentTestBaseWithoutClient


class TestAmazonBedrockConverseComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return AmazonBedrockConverseComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "model_id": "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "aws_access_key_id": "test-key",
            "aws_secret_access_key": "test-secret",
            "region_name": "us-east-1",
            "temperature": 0.7,
            "max_tokens": 4096,
            "top_p": 0.9,
            "top_k": 250,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    @patch("langchain_aws.chat_models.bedrock_converse.ChatBedrockConverse")
    def test_top_k_passed_via_additional_model_request_fields(self, mock_chat_cls, default_kwargs):
        """Verify top_k is passed through additional_model_request_fields (fixes #14716)."""
        mock_chat_cls.return_value = MagicMock()

        component = AmazonBedrockConverseComponent(**default_kwargs)
        component.build_model()

        mock_chat_cls.assert_called_once()
        call_kwargs = mock_chat_cls.call_args[1]

        assert "additional_model_request_fields" in call_kwargs
        assert call_kwargs["additional_model_request_fields"]["top_k"] == 250

    @patch("langchain_aws.chat_models.bedrock_converse.ChatBedrockConverse")
    def test_top_k_none_not_passed(self, mock_chat_cls, default_kwargs):
        """Verify top_k is NOT included when set to None."""
        mock_chat_cls.return_value = MagicMock()

        default_kwargs["top_k"] = None
        component = AmazonBedrockConverseComponent(**default_kwargs)
        component.build_model()

        call_kwargs = mock_chat_cls.call_args[1]
        additional_fields = call_kwargs.get("additional_model_request_fields", {})
        assert "top_k" not in additional_fields

    @patch("langchain_aws.chat_models.bedrock_converse.ChatBedrockConverse")
    def test_additional_model_fields_override_top_k(self, mock_chat_cls, default_kwargs):
        """Verify user-provided additional_model_fields can override top_k."""
        mock_chat_cls.return_value = MagicMock()

        default_kwargs["top_k"] = 250
        default_kwargs["additional_model_fields"] = [{"top_k": 50}]
        component = AmazonBedrockConverseComponent(**default_kwargs)
        component.build_model()

        call_kwargs = mock_chat_cls.call_args[1]
        # User override should win (applied after default top_k)
        assert call_kwargs["additional_model_request_fields"]["top_k"] == 50

    @patch("langchain_aws.chat_models.bedrock_converse.ChatBedrockConverse")
    def test_additional_model_fields_merged_with_top_k(self, mock_chat_cls, default_kwargs):
        """Verify additional_model_fields are merged alongside top_k."""
        mock_chat_cls.return_value = MagicMock()

        default_kwargs["top_k"] = 100
        default_kwargs["additional_model_fields"] = [{"custom_param": "value"}]
        component = AmazonBedrockConverseComponent(**default_kwargs)
        component.build_model()

        call_kwargs = mock_chat_cls.call_args[1]
        additional_fields = call_kwargs["additional_model_request_fields"]
        assert additional_fields["top_k"] == 100
        assert additional_fields["custom_param"] == "value"

    @patch("langchain_aws.chat_models.bedrock_converse.ChatBedrockConverse")
    def test_model_params_in_init_params(self, mock_chat_cls, default_kwargs):
        """Verify temperature, max_tokens, top_p go to init_params directly (not additional_fields)."""
        mock_chat_cls.return_value = MagicMock()

        component = AmazonBedrockConverseComponent(**default_kwargs)
        component.build_model()

        call_kwargs = mock_chat_cls.call_args[1]
        assert call_kwargs["temperature"] == 0.7
        assert call_kwargs["max_tokens"] == 4096
        assert call_kwargs["top_p"] == 0.9
        # top_k should NOT be in root init_params
        assert "top_k" not in call_kwargs or call_kwargs.get("top_k") is None
