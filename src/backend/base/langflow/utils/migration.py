from collections.abc import Iterator
from contextlib import contextmanager

import sqlalchemy as sa


@contextmanager
def preserve_sqlite_triggers(conn: sa.Connection, *table_names: str) -> Iterator[None]:
    """Preserve installed triggers while rebuilding a SQLite table.

    Include both the rebuilt table and tables whose triggers reference it.
    SQLite drops triggers attached to the old table, while surviving triggers
    can prevent Alembic from renaming the replacement table. A savepoint rolls
    back the schema and triggers if the rebuild or trigger restoration fails.
    """
    if conn.dialect.name != "sqlite":
        yield
        return

    triggers = conn.execute(
        sa.text(
            """
            SELECT name, sql FROM sqlite_master
            WHERE type = 'trigger' AND tbl_name IN :table_names
            ORDER BY rowid
            """
        ).bindparams(sa.bindparam("table_names", expanding=True)),
        {"table_names": table_names},
    ).all()
    if not triggers:
        yield
        return

    with conn.begin_nested():
        for name, _ in triggers:
            quoted_name = conn.dialect.identifier_preparer.quote_identifier(name)
            conn.exec_driver_sql(f"DROP TRIGGER main.{quoted_name}")
        yield
        for _, sql in triggers:
            conn.exec_driver_sql(sql)


def table_exists(name, conn):
    """Check if a table exists.

    Parameters:
    name (str): The name of the table to check.
    conn (sqlalchemy.engine.Engine or sqlalchemy.engine.Connection): The SQLAlchemy engine or connection to use.

    Returns:
    bool: True if the table exists, False otherwise.
    """
    inspector = sa.inspect(conn)
    return name in inspector.get_table_names()


def column_exists(table_name, column_name, conn):
    """Check if a column exists in a table.

    Parameters:
    table_name (str): The name of the table to check.
    column_name (str): The name of the column to check.
    conn (sqlalchemy.engine.Engine or sqlalchemy.engine.Connection): The SQLAlchemy engine or connection to use.

    Returns:
    bool: True if the column exists, False otherwise.
    """
    inspector = sa.inspect(conn)
    return column_name in [column["name"] for column in inspector.get_columns(table_name)]


def foreign_key_exists(table_name, fk_name, conn):
    """Check if a foreign key exists in a table.

    Parameters:
    table_name (str): The name of the table to check.
    fk_name (str): The name of the foreign key to check.
    conn (sqlalchemy.engine.Engine or sqlalchemy.engine.Connection): The SQLAlchemy engine or connection to use.

    Returns:
    bool: True if the foreign key exists, False otherwise.
    """
    inspector = sa.inspect(conn)
    return fk_name in [fk["name"] for fk in inspector.get_foreign_keys(table_name)]


def constraint_exists(table_name, constraint_name, conn):
    """Check if a constraint exists in a table.

    Parameters:
    table_name (str): The name of the table to check.
    constraint_name (str): The name of the constraint to check.
    conn (sqlalchemy.engine.Engine or sqlalchemy.engine.Connection): The SQLAlchemy engine or connection to use.

    Returns:
    bool: True if the constraint exists, False otherwise.
    """
    inspector = sa.inspect(conn)
    constraints = inspector.get_unique_constraints(table_name)
    return constraint_name in [constraint["name"] for constraint in constraints]
