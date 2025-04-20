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
