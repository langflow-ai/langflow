import pytest

from langflow.components.langchain_utilities import SQLDatabaseComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestSQLDatabaseComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return SQLDatabaseComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"uri": "postgres://user:password@localhost/dbname"}

    @pytest.fixture
    def file_names_mapping(self):
        return []

    def test_clean_up_uri(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        cleaned_uri = component.clean_up_uri("postgres://user:password@localhost/dbname")
        assert cleaned_uri == "postgresql://user:password@localhost/dbname"

    async def test_build_sqldatabase(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.run()
        assert result is not None
        assert isinstance(result, SQLDatabase)
