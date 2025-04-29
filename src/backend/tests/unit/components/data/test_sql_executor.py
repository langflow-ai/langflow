from unittest.mock import patch

import pytest
from langflow.components.data.sql_executor import SQLComponent
from langflow.schema import Message

from tests.base import ComponentTestBaseWithoutClient
from tests.unit.mock_sql_database import MockSQLDatabase


class TestSQLComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return SQLComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "database_url": "sqlite:///:memory:",
            "query": "SELECT * FROM test",
            "include_columns": True,
            "add_error": False,
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return []

    @pytest.fixture
    def mock_sql_db_class(self):
        """Return a mock SQLDatabase class."""
        with patch("langchain_community.utilities.SQLDatabase") as mock:
            yield mock

    def test_successful_query_with_columns(self, component_class: type[SQLComponent], mock_sql_db_class):
        """Test a successful SQL query with columns included."""
        mock_db = MockSQLDatabase(mock_results=[{"id": 1, "name": "Test"}])
        mock_sql_db_class.from_uri.return_value = mock_db

        component = component_class(
            database_url="sqlite:///:memory:",
            query="SELECT * FROM test",
            include_columns=True,
            add_error=False,
        )

        result = component.build_component()

        assert isinstance(result, Message)
        assert isinstance(result.text, str)
        assert "id | name" in result.text
        assert "1 | Test" in result.text
        assert mock_db.run_called
        assert mock_db.run_args == "SELECT * FROM test"
        assert mock_db.run_kwargs is not None
        assert mock_db.run_kwargs["include_columns"] is True
