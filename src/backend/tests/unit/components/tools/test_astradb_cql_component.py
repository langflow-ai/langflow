import pytest

from langflow.components.tools import AstraDBCQLToolComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestAstraDBCQLToolComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return AstraDBCQLToolComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "tool_name": "Test Tool",
            "tool_description": "A tool for testing Astra DB",
            "keyspace": "test_keyspace",
            "table_name": "test_table",
            "token": "test_token",
            "api_endpoint": "https://test.api.endpoint",
            "projection_fields": "*",
            "partition_keys": {"id": "ID of the record"},
            "clustering_keys": {},
            "static_filters": {},
            "number_of_results": 5,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "tools", "file_name": "AstraDBCQLTool"},
        ]

    async def test_run_model(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.run_model(id="123")
        assert result is not None

    def test_create_args_schema(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        schema = component.create_args_schema()
        assert "ToolInput" in schema
        assert "id" in schema["ToolInput"].__annotations__

    def test_build_tool(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        tool = component.build_tool()
        assert tool.name == default_kwargs["tool_name"]
        assert tool.description == default_kwargs["tool_description"]
