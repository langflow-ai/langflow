import sqlite3
from pathlib import Path

import pytest
from langflow.components.data.sql_executor import SQLComponent
from langflow.schema import DataFrame, Message

from tests.base import ComponentTestBaseWithoutClient


class TestSQLComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def test_db(self):
        """Fixture that creates a temporary SQLite database for testing."""
        test_data_dir = Path(__file__).parent.parent.parent.parent / "data"
        db_path = test_data_dir / "test.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test (
                id INTEGER PRIMARY KEY,
                name TEXT
            )
        """)
        cursor.execute("""
            INSERT INTO test (id, name)
            VALUES (1, 'name_test')
        """)
        conn.commit()
        conn.close()
        yield str(db_path)

        Path(db_path).unlink()

    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return SQLComponent

    @pytest.fixture
    def default_kwargs(self, test_db):
        """Return the default kwargs for the component."""
        return {
            "database_url": f"sqlite:///{test_db}",
            "query": "SELECT * FROM test",
            "include_columns": True,
            "add_error": False,
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return an empty list since this component doesn't have version-specific files."""
        return []

    def test_successful_query_with_columns(self, component_class: type[SQLComponent], default_kwargs):
        """Test a successful SQL query with columns included."""
        component = component_class(**default_kwargs)

        result = component.build_component()

        assert isinstance(result, Message)
        assert isinstance(result.text, str)
        assert result.text == "[{'id': 1, 'name': 'name_test'}]"

    def test_successful_query_without_columns(self, component_class: type[SQLComponent], default_kwargs):
        """Test a successful SQL query without columns included."""
        default_kwargs["include_columns"] = False
        component = component_class(**default_kwargs)

        result = component.build_component()

        assert isinstance(result, Message)
        assert isinstance(result.text, str)
        assert result.text == "[(1, 'name_test')]"
        assert component.status == "[(1, 'name_test')]"
        assert component.query == "SELECT * FROM test"

    def test_query_error_with_add_error(self, component_class: type[SQLComponent], default_kwargs):
        """Test a SQL query that raises an error with add_error=True."""
        default_kwargs["add_error"] = True
        default_kwargs["query"] = "SELECT * FROM non_existent_table"
        component = component_class(**default_kwargs)

        result = component.build_component()

        assert isinstance(result, Message)
        assert isinstance(result.text, str)
        assert "no such table: non_existent_table" in result.text
        assert "Error:" in result.text
        assert "Query: SELECT * FROM non_existent_table" in result.text

    def test_run_sql_query(self, component_class: type[SQLComponent], default_kwargs):
        """Test building a DataFrame from a SQL query."""
        component = component_class(**default_kwargs)

        result = component.run_sql_query()

        assert isinstance(result, DataFrame)
        assert len(result) == 1
        assert "id" in result.columns
        assert "name" in result.columns
        assert result.iloc[0]["id"] == 1
        assert result.iloc[0]["name"] == "name_test"
