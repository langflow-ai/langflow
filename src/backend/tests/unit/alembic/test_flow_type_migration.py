"""Structure tests for the flow_type / a2a columns migration (9f1d1d602aa3).

Covers the additive flow.flow_type, flow.a2a_enabled and flow.a2a_card_overrides
columns: forward to head, then rollback to the prior revision. Runs on sqlite
and (when configured) postgres.
"""

from __future__ import annotations

from alembic import command
from sqlalchemy import create_engine, inspect

from .test_migration_execution import _engine_url, _make_alembic_cfg, db_url  # noqa: F401

_PRIOR_REVISION = "a1f4c9d27b30"  # pragma: allowlist secret
_A2A_COLUMNS = {"flow_type", "a2a_enabled", "a2a_card_overrides"}


def _flow_columns(db_url: str) -> set[str]:  # noqa: F811
    engine = create_engine(_engine_url(db_url))
    try:
        with engine.connect() as connection:
            return {c["name"] for c in inspect(connection).get_columns("flow")}
    finally:
        engine.dispose()


def test_flow_has_flow_type_and_a2a_columns(db_url):  # noqa: F811
    alembic_cfg = _make_alembic_cfg(db_url)
    command.upgrade(alembic_cfg, "head")

    assert _flow_columns(db_url) >= _A2A_COLUMNS


def test_flow_type_columns_dropped_on_downgrade(db_url):  # noqa: F811
    alembic_cfg = _make_alembic_cfg(db_url)
    command.upgrade(alembic_cfg, "head")
    command.downgrade(alembic_cfg, _PRIOR_REVISION)

    assert _A2A_COLUMNS.isdisjoint(_flow_columns(db_url))
