import pytest

from langflow.components.data import SQLExecutorComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestSQLExecutorComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return SQLExecutorComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "database_url": "sqlite:///:memory:",
            "query": "SELECT * FROM my_table",
            "include_columns": True,
            "passthrough": False,
            "add_error": False,
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    async def test_build_success(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.build(**default_kwargs)
        assert result is not None
        assert isinstance(result, str)

    async def test_build_with_error(self, component_class, default_kwargs):
        default_kwargs["query"] = "SELECT * FROM non_existing_table"
        component = component_class(**default_kwargs)
        result = await component.build(**default_kwargs)
        assert "Error" in result

    async def test_build_with_passthrough(self, component_class, default_kwargs):
        default_kwargs["query"] = "SELECT * FROM non_existing_table"
        default_kwargs["passthrough"] = True
        component = component_class(**default_kwargs)
        result = await component.build(**default_kwargs)
        assert result == default_kwargs["query"]

    async def test_build_with_add_error(self, component_class, default_kwargs):
        default_kwargs["query"] = "SELECT * FROM non_existing_table"
        default_kwargs["add_error"] = True
        component = component_class(**default_kwargs)
        result = await component.build(**default_kwargs)
        assert "Error" in result
        assert "Query: SELECT * FROM non_existing_table" in result
