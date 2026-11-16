"""Regression tests for deleting traces attached to a flow."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from langflow.api.utils import flow_utils
from langflow.services.database.models.traces.model import SpanTable, TraceTable
from langflow.services.evaluations import cleanup as evaluation_cleanup
from langflow.services.memory_base import flow_cleanup
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.selectable import Select


async def test_cascade_delete_flow_keeps_large_trace_deletes_below_postgres_bind_limit(monkeypatch):
    """Ensure trace cleanup uses bounded SQL parameters for large histories.

    @param monkeypatch: pytest fixture used to isolate the database side effects.
    @returns: None; asserts that no trace IDs are materialized and both deletes remain bounded.
    """
    flow_id = uuid4()
    materialized_trace_queries = 0
    trace_delete_parameter_counts = []
    trace_delete_sync_options = []

    async def record_exec(statement):
        """Record generated SQL and supply the large trace result for the regression.

        @param statement: SQLAlchemy statement issued by flow deletion.
        @returns: A result object sufficient for cascade_delete_flow.
        """
        nonlocal materialized_trace_queries

        if isinstance(statement, Select):
            table_names = {table.name for table in statement.get_final_froms()}
            if TraceTable.__tablename__ in table_names:
                materialized_trace_queries += 1
                return SimpleNamespace(all=lambda: list(range(65_536)))
            return SimpleNamespace(all=list)

        table = getattr(statement, "table", None)
        if table is not None and table.name in {SpanTable.__tablename__, TraceTable.__tablename__}:
            compiled = statement.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"render_postcompile": True},
            )
            trace_delete_parameter_counts.append(len(compiled.params))
            trace_delete_sync_options.append(statement.get_execution_options().get("synchronize_session"))
        return SimpleNamespace(rowcount=1)

    monkeypatch.setattr(flow_utils, "check_flow_has_deployed_versions", AsyncMock())
    monkeypatch.setattr(flow_cleanup, "purge_flow_memory_bases", AsyncMock(return_value=[]))
    monkeypatch.setattr(flow_utils, "delete_triggers", AsyncMock())
    monkeypatch.setattr(evaluation_cleanup, "detach_flow", AsyncMock())
    session = SimpleNamespace(exec=AsyncMock(side_effect=record_exec))

    assert await flow_utils.cascade_delete_flow(session, flow_id)
    assert materialized_trace_queries == 0
    assert trace_delete_parameter_counts == [1, 1]
    assert trace_delete_sync_options == [False, False]
