import sqlite3
from pathlib import Path

import pytest

from lfx.components.data.sql_executor import SQLComponent
from lfx.schema import DataFrame, Message
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

    def test_with_mock_database(self, mock_database_session, sample_database_records):
        """Test database query logic with mock database session (no real DB needed)."""
        # Configure mock database session to return sample records
        mock_result = mock_database_session.exec.return_value
        mock_result.all.return_value = sample_database_records
        mock_result.first.return_value = sample_database_records[0] if sample_database_records else None

        # Simulate executing a query like the SQLComponent would
        query_result = mock_database_session.exec("SELECT * FROM test_table")
        records = query_result.all()

        # Assert we got the expected sample data
        assert len(records) == 3
        assert records[0]["name"] == "Test Record 1"
        assert records[0]["id"] == 1
        assert records[1]["name"] == "Test Record 2"

        # Verify the database session was used correctly
        mock_database_session.exec.assert_called_once_with("SELECT * FROM test_table")

        # Test getting a single record
        single_record = query_result.first()
        assert single_record["name"] == "Test Record 1"

    def test_mock_database_error_handling(self, mock_database_session):
        """Test how mock database handles errors."""
        # Configure mock to raise an exception when executing query
        mock_database_session.exec.side_effect = Exception("Database connection failed")

        # Test that the exception is properly raised
        with pytest.raises(Exception, match="Database connection failed"):
            mock_database_session.exec("SELECT * FROM non_existent_table")

        # Verify the exec method was called
        mock_database_session.exec.assert_called_once_with("SELECT * FROM non_existent_table")
