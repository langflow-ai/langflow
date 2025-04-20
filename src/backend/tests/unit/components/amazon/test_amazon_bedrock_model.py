from unittest.mock import MagicMock, patch

import pytest
from langflow.components.amazon.amazon_bedrock_model import AmazonBedrockComponent

from tests.base import ComponentTestBaseWithoutClient


class TestAmazonBedrockComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return AmazonBedrockComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "model_id": "anthropic.claude-3-haiku-20240307-v1:0",
            "aws_access_key_id": "test_key",
            "aws_secret_access_key": "test_secret",
            "region_name": "us-east-1",
            "temperature": 0.1,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.3.4", "module": "amazon", "file_name": "amazon_bedrock_model"},
        ]

    def test_temperature_parameter(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        frontend_node = component.to_frontend_node()
        node_data = frontend_node["data"]["node"]

        # Check if temperature parameter exists and has correct values
        assert "temperature" in node_data
        assert node_data["temperature"]["value"] == 0.1
        assert node_data["temperature"]["range_spec"]["min"] == 0
        assert node_data["temperature"]["range_spec"]["max"] == 1
        assert node_data["temperature"]["range_spec"]["step"] == 0.01

    def test_temperature_validation(self, component_class):
        # Test valid temperatures
        valid_temperatures = [0, 0.5, 1]
        for temp in valid_temperatures:
            component = component_class(temperature=temp)
            assert component.temperature == temp
            component.build_model()  # Should not raise error

    def test_invalid_temperature(self, component_class):
        # Test invalid temperatures
        invalid_temperatures = [-0.1, 1.1, 2.0]
        for temp in invalid_temperatures:
            component = component_class(temperature=temp)
            with pytest.raises(ValueError, match="Temperature must be between 0 and 1"):
                component.build_model()

    @patch("boto3.Session")
    @patch("langchain_aws.ChatBedrock")
    def test_build_model_with_credentials(self, mock_chat_bedrock, mock_session, component_class):
        mock_session_instance = MagicMock()
        mock_session.return_value = mock_session_instance
        mock_client = MagicMock()
        mock_session_instance.client.return_value = mock_client
        mock_chat_instance = MagicMock()
        mock_chat_bedrock.return_value = mock_chat_instance

        # Setup test values
        component = component_class(
            aws_access_key_id="test_key",
            aws_secret_access_key="test_secret",
            aws_session_token="test_token",
            region_name="us-west-2",
            model_id="anthropic.claude-v2",
            temperature=0.7,
            endpoint_url="https://custom-endpoint.aws",
            stream=True,
        )

        # Call build_model
        result = component.build_model()

        # Verify boto3.Session was called with correct credentials
        mock_session.assert_called_once_with(
            aws_access_key_id="test_key", aws_secret_access_key="test_secret", aws_session_token="test_token"
        )

        # Verify client was created with correct parameters
        mock_session_instance.client.assert_called_once_with(
            "bedrock-runtime", endpoint_url="https://custom-endpoint.aws", region_name="us-west-2"
        )

        # Verify ChatBedrock was created with correct parameters
        mock_chat_bedrock.assert_called_once()
        call_kwargs = mock_chat_bedrock.call_args.kwargs
        assert call_kwargs["client"] == mock_client
        assert call_kwargs["model_id"] == "anthropic.claude-v2"
        assert call_kwargs["model_kwargs"]["temperature"] == 0.7
        assert call_kwargs["endpoint_url"] == "https://custom-endpoint.aws"
        assert call_kwargs["streaming"] is True

        assert result == mock_chat_instance

    def test_build_model_with_profile(self, component_class, mock_session):
        mock_session_class, _ = mock_session

        component = component_class(
            credentials_profile_name="test_profile", temperature=0.5, model_id="anthropic.claude-v2"
        )

        component.build_model()

        # Verify session was created with profile
        mock_session_class.assert_called_once_with(profile_name="test_profile")

    def test_build_model_no_credentials(self, component_class, mock_session):
        mock_session_class, _ = mock_session

        component = component_class(temperature=0.5, model_id="anthropic.claude-v2")

        component.build_model()

        # Verify session was created without credentials
        mock_session_class.assert_called_once_with()

    def test_model_kwargs_merging(self, component_class, mock_session, mock_chat_bedrock):
        mock_chat_class, _ = mock_chat_bedrock

        component = component_class(
            model_kwargs={"top_p": 0.9, "temperature": 0.8},  # This temperature should be overridden
            temperature=0.5,  # This should take precedence
            model_id="anthropic.claude-v2",
        )

        component.build_model()

        # Verify model_kwargs were merged correctly
        call_kwargs = mock_chat_class.call_args.kwargs
        assert call_kwargs["model_kwargs"]["temperature"] == 0.5  # Component temperature takes precedence
        assert call_kwargs["model_kwargs"]["top_p"] == 0.9  # Other kwargs preserved
