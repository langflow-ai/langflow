from unittest.mock import MagicMock

from langchain_community.utilities import SQLDatabase
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class MockSQLDatabase(SQLDatabase):
    """Mock SQL database for testing."""

    def __init__(self, mock_results=None):
        """Initialize the mock database."""
        self.engine = create_engine("sqlite:///:memory:")
        self._run_mock = MagicMock()
        self._run_mock.side_effect = self._default_run
        self.run_called = False
        self.run_args = None
        self.run_kwargs = None
        self.mock_results = mock_results or [{"id": 1, "name": "Test"}]

        # Create and populate the test table
        with self.engine.connect() as conn:
            conn.execute(text("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)"))
            conn.execute(text("INSERT INTO test (id, name) VALUES (1, 'Test')"))
            conn.commit()

        super().__init__(self.engine)

    def _default_run(self, command, fetch="all", include_columns=False, **kwargs):
        """Default implementation of run method."""
        self.run_called = True
        self.run_args = command
        self.run_kwargs = kwargs
        return self.mock_results

    def run(self, command, fetch="all", include_columns=False, **kwargs):
        """Run a SQL command."""
        return self._run_mock(command, fetch=fetch, include_columns=include_columns, **kwargs)

    @classmethod
    def from_uri(cls, database_uri: str, **kwargs):
        """Create a MockSQLDatabase instance from a URI."""
        return cls(**kwargs)

    def get_usable_table_names(self) -> list[str]:
        """Mock implementation that returns a list of table names.

        Returns:
            A list containing a single test table name
        """
        return ["test"]

    def get_table_info(self, table_name: str) -> str:
        """Mock implementation that returns table information.

        Args:
            table_name: The name of the table

        Returns:
            A string describing the table structure
        """
        return "id INTEGER, name TEXT"
