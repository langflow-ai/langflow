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
    TraceRead,
    TraceSummaryRead,
    TraceTable,
    _LegacyCaseEnum,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import types as sa_types
from sqlalchemy.dialects import postgresql


def _column_enum(table, column_name: str) -> SQLEnum:
    column = table.__table__.c[column_name]
    col_type = column.type
    # Unwrap TypeDecorator to get the underlying SQLEnum impl.
    if isinstance(col_type, sa_types.TypeDecorator):
        col_type = col_type.impl
    assert isinstance(col_type, SQLEnum), f"{table.__name__}.{column_name} is not a SQLAlchemy Enum column"
    return col_type


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


class TestLegacyCaseEnumColumns:
    """The three columns with lowercase-value / uppercase-name enums must use _LegacyCaseEnum."""

    def test_trace_status_column_is_legacy_case_enum(self):
        assert isinstance(TraceTable.__table__.c["status"].type, _LegacyCaseEnum)

    def test_span_status_column_is_legacy_case_enum(self):
        assert isinstance(SpanTable.__table__.c["status"].type, _LegacyCaseEnum)

    def test_span_type_column_is_legacy_case_enum(self):
        assert isinstance(SpanTable.__table__.c["span_type"].type, _LegacyCaseEnum)

    def test_span_kind_column_is_plain_sqlenum(self):
        # SpanKind values are already uppercase so no legacy normalisation needed.
        assert not isinstance(SpanTable.__table__.c["span_kind"].type, _LegacyCaseEnum)


class TestLegacyCaseEnumResultProcessor:
    """Regression: process_result_value handles both legacy uppercase names and new lowercase values.

    Before values_callable=_enum_values was added, SQLAlchemy stored enum *names*
    ('OK', 'ERROR') rather than *values* ('ok', 'error'). After the fix the
    result_processor validates against the lowercase list, raising LookupError on
    old rows. _LegacyCaseEnum normalises the raw DB string so both forms work.
    """

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("ok", SpanStatus.OK),
            ("error", SpanStatus.ERROR),
            ("unset", SpanStatus.UNSET),
            ("OK", SpanStatus.OK),
            ("ERROR", SpanStatus.ERROR),
            ("UNSET", SpanStatus.UNSET),
        ],
    )
    def test_span_status_accepts_legacy_and_current_values(self, raw, expected):
        decoder = _LegacyCaseEnum(SpanStatus, name="spanstatus")
        assert decoder.process_result_value(raw, None) is expected

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("chain", SpanType.CHAIN),
            ("llm", SpanType.LLM),
            ("CHAIN", SpanType.CHAIN),
            ("LLM", SpanType.LLM),
        ],
    )
    def test_span_type_accepts_legacy_and_current_values(self, raw, expected):
        decoder = _LegacyCaseEnum(SpanType, name="spantype")
        assert decoder.process_result_value(raw, None) is expected

    def test_returns_none_for_none(self):
        decoder = _LegacyCaseEnum(SpanStatus, name="spanstatus")
        assert decoder.process_result_value(None, None) is None

    def test_returns_member_unchanged(self):
        decoder = _LegacyCaseEnum(SpanStatus, name="spanstatus")
        assert decoder.process_result_value(SpanStatus.OK, None) is SpanStatus.OK

    def test_raises_lookup_error_for_unknown_value(self):
        decoder = _LegacyCaseEnum(SpanStatus, name="spanstatus")
        with pytest.raises(LookupError):
            decoder.process_result_value("bogus", None)


_TRACE_DEFAULTS: dict = {
    "id": "00000000-0000-0000-0000-000000000001",
    "name": "t",
    "status": SpanStatus.OK,
    "start_time": None,
    "total_latency_ms": 0,
    "total_tokens": 0,
    "flow_id": "00000000-0000-0000-0000-000000000002",
    "session_id": "s",
}


class TestTraceSummaryReadIoFields:
    """Regression: input/output accept the '[Unserializable Object]' sentinel string.

    When a trace's input or output contains a non-JSON-serialisable object the
    serialisation layer stores the sentinel string '[Unserializable Object]'.
    TraceSummaryRead must accept that value so the list endpoint never 500s.
    """

    def test_accepts_dict_input(self):
        assert TraceSummaryRead(**{**_TRACE_DEFAULTS, "input": {"k": 1}}).input == {"k": 1}

    def test_accepts_dict_output(self):
        assert TraceSummaryRead(**{**_TRACE_DEFAULTS, "output": {"r": 2}}).output == {"r": 2}

    def test_accepts_none_input(self):
        assert TraceSummaryRead(**{**_TRACE_DEFAULTS, "input": None}).input is None

    def test_accepts_none_output(self):
        assert TraceSummaryRead(**{**_TRACE_DEFAULTS, "output": None}).output is None

    def test_accepts_unserializable_sentinel_as_input(self):
        assert (
            TraceSummaryRead(**{**_TRACE_DEFAULTS, "input": "[Unserializable Object]"}).input
            == "[Unserializable Object]"
        )

    def test_accepts_unserializable_sentinel_as_output(self):
        assert (
            TraceSummaryRead(**{**_TRACE_DEFAULTS, "output": "[Unserializable Object]"}).output
            == "[Unserializable Object]"
        )

    def test_defaults_input_and_output_to_none(self):
        s = TraceSummaryRead(**_TRACE_DEFAULTS)
        assert s.input is None
        assert s.output is None


_TRACE_READ_DEFAULTS: dict = {
    **_TRACE_DEFAULTS,
    "end_time": None,
}


class TestTraceReadIoFields:
    """Regression: TraceRead.input/output must also accept the sentinel string.

    TraceRead is built from the same stored data as TraceSummaryRead but was
    typed as dict|None, so the detail endpoint could still 500 on old rows.
    """

    def test_accepts_dict_input(self):
        assert TraceRead(**{**_TRACE_READ_DEFAULTS, "input": {"k": 1}}).input == {"k": 1}

    def test_accepts_dict_output(self):
        assert TraceRead(**{**_TRACE_READ_DEFAULTS, "output": {"r": 2}}).output == {"r": 2}

    def test_accepts_none_input(self):
        assert TraceRead(**{**_TRACE_READ_DEFAULTS, "input": None}).input is None

    def test_accepts_none_output(self):
        assert TraceRead(**{**_TRACE_READ_DEFAULTS, "output": None}).output is None

    def test_accepts_unserializable_sentinel_as_input(self):
        assert (
            TraceRead(**{**_TRACE_READ_DEFAULTS, "input": "[Unserializable Object]"}).input == "[Unserializable Object]"
        )

    def test_accepts_unserializable_sentinel_as_output(self):
        assert (
            TraceRead(**{**_TRACE_READ_DEFAULTS, "output": "[Unserializable Object]"}).output
            == "[Unserializable Object]"
        )

    def test_defaults_input_and_output_to_none(self):
        t = TraceRead(**_TRACE_READ_DEFAULTS)
        assert t.input is None
        assert t.output is None
