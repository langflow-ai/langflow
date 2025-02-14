import pytest

from langflow.components.models import AmazonBedrockComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestAmazonBedrockComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return AmazonBedrockComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "model_id": "anthropic.claude-3-haiku-20240307-v1:0",
            "aws_access_key_id": "AWS_ACCESS_KEY_ID",
            "aws_secret_access_key": "AWS_SECRET_ACCESS_KEY",
            "region_name": "us-east-1",
            "model_kwargs": {},
            "endpoint_url": "https://example.com",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "aws", "file_name": "AmazonBedrock"},
        ]

    async def test_build_model_success(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        model = await component.build_model()
        assert model is not None

    async def test_build_model_missing_dependencies(self, component_class, default_kwargs):
        with pytest.raises(ImportError, match="langchain_aws is not installed"):
            component = component_class(**default_kwargs)
            component.build_model()

        with pytest.raises(ImportError, match="boto3 is not installed"):
            component = component_class(**default_kwargs)
            component.build_model()

    async def test_build_model_invalid_credentials(self, component_class, default_kwargs):
        default_kwargs["aws_access_key_id"] = None
        default_kwargs["aws_secret_access_key"] = None
        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match="Could not create a boto3 session."):
            await component.build_model()

    async def test_build_model_connection_error(self, component_class, default_kwargs):
        default_kwargs["endpoint_url"] = "invalid_url"
        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match="Could not connect to AmazonBedrock API."):
            await component.build_model()
