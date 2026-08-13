"""Narrow warning filters used while running Alembic migrations."""

import warnings

from sqlalchemy.exc import SAWarning

_KNOWN_SQLITE_EXPRESSION_INDEX_WARNING = (
    r"^Skipped unsupported reflection of expression-based index "
    r"ix_message_session_metadata_(?:tenant|user)$"
)
_KNOWN_SQLITE_AUTOGENERATE_EXPRESSION_INDEX_WARNING = (
    r"^autogenerate skipping metadata-specified expression-based index "
    r"'ix_message_session_metadata_(?:tenant|user)'; dialect 'sqlite' under SQLAlchemy [^ ]+ "
    r"can't reflect these indexes so they can't be compared$"
)
# SQLite reports composite foreign keys through PRAGMA foreign_key_list only, so
# SQLAlchemy's SQL-parsed fallback cannot match them and warns on every reflect.
_KNOWN_SQLITE_FOREIGN_KEY_REFLECTION_WARNING = (
    r".*SQL-parsed foreign key constraint.*could not be located in PRAGMA foreign_keys.*"
)


def filter_known_sqlite_reflection_warnings() -> None:
    """Ignore only the known SQLite reflection gaps hit by our PostgreSQL-shaped schema."""
    warnings.filterwarnings(
        "ignore",
        message=_KNOWN_SQLITE_EXPRESSION_INDEX_WARNING,
        category=SAWarning,
    )
    warnings.filterwarnings(
        "ignore",
        message=_KNOWN_SQLITE_AUTOGENERATE_EXPRESSION_INDEX_WARNING,
        category=UserWarning,
    )
    warnings.filterwarnings(
        "ignore",
        message=_KNOWN_SQLITE_FOREIGN_KEY_REFLECTION_WARNING,
        category=SAWarning,
    )
