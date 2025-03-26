import pytest
from langflow.components.tools import AstraDBToolComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestAstraDBToolComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return AstraDBToolComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "tool_name": "Test Tool",
            "tool_description": "A tool for testing Astra DB.",
            "namespace": "test_namespace",
            "collection_name": "test_collection",
            "token": "test_token",
            "api_endpoint": "https://test.api.endpoint",
            "projection_attributes": "*",
            "tool_params": {"!customerId": "Customer ID", "orderId": "Order ID"},
            "static_filters": {"status": "active"},
            "number_of_results": 5,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "tools", "file_name": "AstraDBTool"},
            {"version": "1.1.0", "module": "tools", "file_name": "AstraDBTool"},
        ]

    async def test_build_tool(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        tool = component.build_tool()
        assert tool is not None
        assert tool.name == default_kwargs["tool_name"]
        assert tool.description == default_kwargs["tool_description"]

    async def test_run_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component._build_collection = lambda: MockCollection()  # Mocking the collection
        result = component.run_model(customerId="12345")
        assert isinstance(result, list)
        assert all(isinstance(data, Data) for data in result)


class MockCollection:
    def find(self, query, projection, limit):
        return [{"customerId": "12345", "status": "active"}] * limit
