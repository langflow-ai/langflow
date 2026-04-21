"""Regression tests for PostgreSQL enum serialization on the trace/span tables.

The PostgreSQL enums ``spanstatus``, ``spantype`` and ``spankind`` (created in
migration ``3478f0bd6ccb``) are defined with the enum *values* as labels.  If
SQLAlchemy falls back to its default behaviour of serialising the enum *name*,
inserts fail with e.g. ``invalid input value for enum spanstatus: "OK"``.

These tests pin the fix to issue #12817 by asserting the SQLAlchemy ``Enum``
columns on ``TraceTable`` / ``SpanTable`` advertise the enum values (not names)
and keep the PG enum type names aligned with the migration.
"""

from __future__ import annotations

import pytest
from langflow.services.database.models.traces.model import (
    SpanKind,
    SpanStatus,
    SpanTable,
    SpanType,
    TraceTable,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects import postgresql


def _column_enum(table, column_name: str) -> SQLEnum:
    column = table.__table__.c[column_name]
    assert isinstance(column.type, SQLEnum), f"{table.__name__}.{column_name} is not a SQLAlchemy Enum column"
    return column.type


class TestTraceStatusEnumColumn:
    def test_uses_lowercase_enum_values_not_names(self):
        enum_type = _column_enum(TraceTable, "status")
        assert enum_type.enums == ["unset", "ok", "error"]

    def test_pg_type_name_matches_migration(self):
        enum_type = _column_enum(TraceTable, "status")
        assert enum_type.name == "spanstatus"

    @pytest.mark.parametrize(
        ("member", "expected"),
        [
            (SpanStatus.UNSET, "unset"),
            (SpanStatus.OK, "ok"),
            (SpanStatus.ERROR, "error"),
        ],
    )
    def test_bind_processor_emits_enum_value(self, member, expected):
        enum_type = _column_enum(TraceTable, "status")
        dialect = postgresql.dialect()
        bind_processor = enum_type.bind_processor(dialect)
        # If bind_processor is None, SQLAlchemy passes the value through unchanged;
        # in that case the value coming from a ``str`` Enum is already the value
        # string, which is what PostgreSQL expects.
        bound = bind_processor(member) if bind_processor else member
        assert bound == expected


class TestSpanStatusEnumColumn:
    def test_uses_lowercase_enum_values_not_names(self):
        enum_type = _column_enum(SpanTable, "status")
        assert enum_type.enums == ["unset", "ok", "error"]

    def test_shares_pg_type_name_with_trace_status(self):
        # Both columns must point at the same PG enum type created by the migration.
        assert _column_enum(SpanTable, "status").name == "spanstatus"


class TestSpanTypeEnumColumn:
    def test_uses_lowercase_enum_values_not_names(self):
        enum_type = _column_enum(SpanTable, "span_type")
        assert enum_type.enums == [
            "chain",
            "llm",
            "tool",
            "retriever",
            "embedding",
            "parser",
            "agent",
        ]

    def test_pg_type_name_matches_migration(self):
        assert _column_enum(SpanTable, "span_type").name == "spantype"

    @pytest.mark.parametrize("member", list(SpanType))
    def test_bind_processor_emits_enum_value(self, member):
        enum_type = _column_enum(SpanTable, "span_type")
        dialect = postgresql.dialect()
        bind_processor = enum_type.bind_processor(dialect)
        bound = bind_processor(member) if bind_processor else member
        assert bound == member.value


class TestSpanKindEnumColumn:
    """Pin ``values_callable`` wiring on the ``span_kind`` column.

    SpanKind values happen to be uppercase, but we still want ``values_callable``
    configured so the column is explicit and consistent with the sibling enums.
    """

    def test_column_advertises_migration_labels(self):
        enum_type = _column_enum(SpanTable, "span_kind")
        assert enum_type.enums == ["INTERNAL", "CLIENT", "SERVER", "PRODUCER", "CONSUMER"]

    def test_pg_type_name_matches_migration(self):
        assert _column_enum(SpanTable, "span_kind").name == "spankind"

    @pytest.mark.parametrize("member", list(SpanKind))
    def test_bind_processor_emits_enum_value(self, member):
        enum_type = _column_enum(SpanTable, "span_kind")
        dialect = postgresql.dialect()
        bind_processor = enum_type.bind_processor(dialect)
        bound = bind_processor(member) if bind_processor else member
        assert bound == member.value
