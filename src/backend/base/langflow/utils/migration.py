from sqlalchemy.engine.reflection import Inspector


def table_exists(name, conn):
    """Check if a table exists.

    Parameters:
    name (str): The name of the table to check.
    conn (sqlalchemy.engine.Engine or sqlalchemy.engine.Connection): The SQLAlchemy engine or connection to use.

    Returns:
    bool: True if the table exists, False otherwise.
    """
    inspector = Inspector.from_engine(conn)
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
    inspector = Inspector.from_engine(conn)
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
    inspector = Inspector.from_engine(conn)
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
    inspector = Inspector.from_engine(conn)
    constraints = inspector.get_unique_constraints(table_name)
    return constraint_name in [constraint["name"] for constraint in constraints]
