"""Index per-flow transaction timelines without adding a tie-order guarantee.

Revision ID: 9e7a4c2b1d60
Revises: 7fd2c80e5a39
Phase: EXPAND

Unlike message pagination, these queries have no id tie-breaker. Plain ascending
keys support both existing timestamp scan directions. PostgreSQL concurrent DDL
commits the runner transaction: its transaction advisory lock and SET LOCAL
lock_timeout do not survive. Startup retains its separate session lock. Direct
administrative invocations require one migration executor and no concurrent DDL.
Earlier pending work commits at this boundary; later revisions in the same run
also lose the transaction lock and local timeout. A stalled builder has no total
time bound here; other startup workers may exhaust their default 300s lock wait.
Conservative recovery/downgrade guards may refuse during unrelated maintenance
or a redacted build elsewhere in this database: retry after that operation ends.
A matching but not-live artifact may be an interrupted concurrent DROP, not
foreign DDL. It is refused without automatic repair: stop other migration/DDL,
inspect pg_index and pg_stat_progress_create_index, then have the database
operator finish the interrupted drop before retrying. Never change system catalogs.
Signature-match is not provenance: an identically named/defined operator index
also counts as owned for downgrade. Equal-time page/survivor identities can change.
SQLite's runner holds BEGIN EXCLUSIVE, potentially blocking readers and writers.
"""

import logging

import sqlalchemy as sa
from alembic import op

revision = "9e7a4c2b1d60"  # pragma: allowlist secret
down_revision = "7fd2c80e5a39"  # pragma: allowlist secret
branch_labels = None
depends_on = None

_TABLE = "transaction"
_INDEX = "ix_transaction_flow_id_timestamp"
_COLUMNS = ["flow_id", "timestamp"]
_log = logging.getLogger(__name__)


def _postgres_state(conn, *, downgrade=False):
    """Resolve the visible table once, then inspect only its namespace and OID."""
    target = conn.execute(
        sa.text(
            "SELECT c.oid, n.nspname, c.relkind FROM pg_class c "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE c.oid=to_regclass(:table)"
        ),
        {"table": '"transaction"'},
    ).first()
    if target is None:
        return None
    oid, schema, kind = target
    if kind != "r":
        msg = f"Cannot index {schema}.{_TABLE}: expected an ordinary table"
        if downgrade:
            _log.warning(msg + "; leaving non-owned relation unchanged")
            return None
        raise RuntimeError(msg)
    row = (
        conn.execute(
            sa.text(
                "SELECT c.oid AS index_oid, "
                "coalesce(c.relkind='i' AND a.amname='btree' AND i.indrelid=:table_oid "
                "AND i.indnkeyatts=2 AND i.indnatts=2 "
                "AND i.indkey::text=f.attnum::text || ' ' || t.attnum::text "
                "AND i.indoption::text='0 0' AND i.indcollation::text='0 0' "
                "AND NOT i.indisunique AND NOT i.indisprimary AND NOT i.indisexclusion "
                "AND i.indexprs IS NULL AND i.indpred IS NULL "
                "AND NOT EXISTS (SELECT 1 FROM pg_constraint k WHERE k.conindid=c.oid) "
                "AND (SELECT count(*)=2 FROM unnest(i.indclass::oid[]) WITH ORDINALITY x(opc,ord) "
                "JOIN pg_opclass oc ON oc.oid=x.opc AND oc.opcdefault "
                "WHERE oc.opcmethod=c.relam AND oc.opcintype=CASE x.ord "
                "WHEN 1 THEN f.atttypid ELSE t.atttypid END), false) AS matches, "
                "i.indisvalid, i.indisready, i.indislive "
                "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "LEFT JOIN pg_index i ON i.indexrelid=c.oid "
                "LEFT JOIN pg_am a ON a.oid=c.relam "
                "LEFT JOIN pg_attribute f ON f.attrelid=:table_oid AND f.attname='flow_id' AND NOT f.attisdropped "
                "LEFT JOIN pg_attribute t ON t.attrelid=:table_oid AND t.attname='timestamp' AND NOT t.attisdropped "
                "WHERE n.nspname=:schema AND c.relname=:name"
            ),
            {"table_oid": oid, "schema": schema, "name": _INDEX},
        )
        .mappings()
        .first()
    )
    return oid, schema, row


def _require_idle(conn, oid, schema, index_oid):
    """Conservative refusal, not proof of absence; single executor is required."""
    busy = conn.scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM pg_stat_progress_create_index "
            "WHERE datid=(SELECT oid FROM pg_database WHERE datname=current_database()) "
            "AND pid<>pg_backend_pid() AND (relid=:table_oid OR relid IS NULL OR index_relid=:index_oid)) "
            "OR EXISTS (SELECT 1 FROM pg_locks "
            "WHERE database=(SELECT oid FROM pg_database WHERE datname=current_database()) "
            "AND pid<>pg_backend_pid() AND relation IN (:table_oid,:index_oid) "
            "AND mode IN ('ShareUpdateExclusiveLock','ShareLock'))"
        ),
        {"table_oid": oid, "index_oid": index_oid},
    )
    if busy:
        msg = f"Cannot change {schema}.{_INDEX}: retry after the other operation ends (possibly active DDL)"
        raise RuntimeError(msg)


def _conflict(schema, *, downgrade):
    msg = f"Leaving conflicting non-owned or incomplete/dropping index/relation {schema}.{_INDEX} unchanged"
    if downgrade:
        _log.warning(msg)
    else:
        raise RuntimeError(msg)


def _postgres_change(conn, *, downgrade):
    state = _postgres_state(conn, downgrade=downgrade)
    if state is None:
        return
    oid, schema, row = state
    if row is not None and (not row["matches"] or not row["indislive"]):
        _conflict(schema, downgrade=downgrade)
        return
    if row is not None:
        usable = row["indisvalid"] and row["indisready"]
        if usable and not downgrade:
            return
        # Also protect a matching active build during downgrade: never silently
        # stamp through it. Queries failing for lack of visibility fail closed.
        _require_idle(conn, oid, schema, row["index_oid"])
    elif downgrade:
        _log.warning("Index %s.%s is absent; leaving it unchanged", schema, _INDEX)
        return
    with op.get_context().autocommit_block():
        if row is not None:
            op.drop_index(_INDEX, table_name=_TABLE, schema=schema, postgresql_concurrently=True)
        if not downgrade:
            op.create_index(_INDEX, _TABLE, _COLUMNS, schema=schema, postgresql_concurrently=True)


def _sqlite_change(conn, *, downgrade):
    if not sa.inspect(conn).has_table(_TABLE, schema="main"):
        return
    row = conn.execute(
        sa.text(
            "SELECT type,tbl_name FROM main.sqlite_master "
            "WHERE name=:name COLLATE NOCASE AND type IN ('index','table','view')"
        ),
        {"name": _INDEX},
    ).first()
    if row is not None:
        listed = {item[1].lower(): item for item in conn.exec_driver_sql('PRAGMA main.index_list("transaction")')}
        info = listed.get(_INDEX)
        # Names below are fixed migration constants, not user-provided SQL.
        keys = (
            [
                item
                for item in conn.exec_driver_sql('PRAGMA main.index_xinfo("ix_transaction_flow_id_timestamp")')
                if item[5]
            ]
            if row[0] == "index"
            else []
        )
        matches = (
            row[0] == "index"
            and row[1].lower() == _TABLE
            and info is not None
            and not info[2]
            and not info[4]
            and [item[2] for item in keys] == _COLUMNS
            and all(item[1] >= 0 and not item[3] and item[4] == "BINARY" for item in keys)
        )
        if not matches:
            _conflict("main", downgrade=downgrade)
            return
        if downgrade:
            op.drop_index(_INDEX, table_name=_TABLE, schema="main")
    elif not downgrade:
        op.create_index(_INDEX, _TABLE, _COLUMNS, schema="main")
    else:
        _log.warning("Index main.%s is absent; leaving it unchanged", _INDEX)


def upgrade() -> None:
    """Add or repair only the owned flow timeline index."""
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        _postgres_change(conn, downgrade=False)
    else:
        _sqlite_change(conn, downgrade=False)


def downgrade() -> None:
    """Remove only the owned index, preserving conflicting operator DDL."""
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        _postgres_change(conn, downgrade=True)
    else:
        _sqlite_change(conn, downgrade=True)
