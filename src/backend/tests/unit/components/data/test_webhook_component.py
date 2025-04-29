import pytest
from langflow.components.data import WebhookComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestWebhookComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return WebhookComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"data": '{"key": "value"}'}

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_build_data_with_valid_json(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = component.build_data()
        assert result.data == {"key": "value"}
        assert component.status == result

    def test_build_data_with_empty_data(self, component_class):
        component = component_class(data="")
        result = component.build_data()
        assert result.data == {}
        assert component.status == "No data provided."

    def test_build_data_with_invalid_json(self, component_class):
        component = component_class(data="invalid json")
        result = component.build_data()
        assert result.data == {"payload": "invalid json"}
        assert "Invalid JSON payload" in component.status
