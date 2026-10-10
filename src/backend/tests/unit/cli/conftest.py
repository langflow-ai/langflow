"""Failure fixtures shared by the CLI's database checks."""

import pytest
import sqlalchemy as sa
from langflow.services.deps import get_db_service


@pytest.fixture
def deny_revision_read(client):  # noqa: ARG001
    """Reproduce PostgreSQL's query-time permission failure on the local test engine."""
    engine = get_db_service().engine.sync_engine

    def deny(_connection, _cursor, statement, parameters, _context, _executemany):
        if statement == "SELECT version_num FROM alembic_version":
            raise sa.exc.ProgrammingError(
                statement, parameters, RuntimeError("permission denied for table alembic_version")
            )

    sa.event.listen(engine, "before_cursor_execute", deny)
    try:
        yield
    finally:
        sa.event.remove(engine, "before_cursor_execute", deny)
