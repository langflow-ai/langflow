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


def filter_known_sqlite_reflection_warnings() -> None:
    """Ignore only the two known PostgreSQL expression indexes on SQLite."""
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
