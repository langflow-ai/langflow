"""How the search reads the ``details`` JSON, which each backend stores escaped."""

from __future__ import annotations

import json

from langflow.services.audit.feed import _search_clause
from langflow.services.database.models.audit_event.model import AuditEvent
from sqlalchemy.dialects import postgresql, sqlite
from sqlmodel import select


def _search_sql(dialect) -> str:
    return str(select(AuditEvent.id).where(_search_clause(AuditEvent, "Équipe")).compile(dialect=dialect))


def test_the_stored_details_escape_the_letters_a_person_would_type():
    """The premise both backends share: ``sa.JSON`` serializes with ``ensure_ascii``."""
    assert json.dumps({"role_name": "Équipe"}) == '{"role_name": "\\u00c9quipe"}'


def test_neither_backend_reads_the_details_column_as_plain_text():
    r"""Plain text is the escapes, which no typed word matches.

    Checked against PostgreSQL 17: a row stored as ``{"role_name": "\\u00c9quipe"}``
    is missed by ``CAST(details AS TEXT) ILIKE '%équipe%'`` and found once the cast
    goes through ``jsonb``, whose output writes the letters themselves. SQLite
    re-renders the JSON in Python instead.
    """
    assert "lf_json_text(audit_events.details)" in _search_sql(sqlite.dialect())
    assert "CAST(CAST(audit_events.details AS JSONB) AS TEXT)" in _search_sql(postgresql.dialect())
