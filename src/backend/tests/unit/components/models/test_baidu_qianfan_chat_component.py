import pytest
from langflow.components.models import QianfanChatEndpointComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestQianfanChatEndpointComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return QianfanChatEndpointComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "model": "ERNIE-4.0-8K",
            "qianfan_ak": "your_access_key",
            "qianfan_sk": "your_secret_key",
            "top_p": 0.8,
            "temperature": 0.95,
            "penalty_score": 1.0,
            "endpoint": "https://your.endpoint.url",
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "qianfan", "file_name": "QianfanChatEndpoint"},
        ]

    async def test_build_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        model = component.build_model()
        assert model is not None
        assert hasattr(model, "model")
        assert model.model == default_kwargs["model"]

    async def test_invalid_credentials(self, component_class):
        component = component_class(
            model="ERNIE-4.0-8K",
            qianfan_ak="invalid_access_key",
            qianfan_sk="invalid_secret_key",
            top_p=0.8,
            temperature=0.95,
            penalty_score=1.0,
            endpoint="https://your.endpoint.url",
        )
        with pytest.raises(ValueError, match="Could not connect to Baidu Qianfan API."):
            component.build_model()
