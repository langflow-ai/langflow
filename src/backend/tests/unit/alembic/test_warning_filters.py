import warnings

from langflow.alembic.warning_filters import filter_known_sqlite_reflection_warnings
from sqlalchemy.exc import SAWarning


def test_sqlite_reflection_filter_suppresses_only_known_expression_indexes() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        filter_known_sqlite_reflection_warnings()
        warnings.warn(
            "Skipped unsupported reflection of expression-based index ix_message_session_metadata_tenant",
            SAWarning,
            stacklevel=1,
        )
        warnings.warn(
            "Skipped unsupported reflection of expression-based index ix_message_session_metadata_user",
            SAWarning,
            stacklevel=1,
        )
        warnings.warn(
            "Skipped unsupported reflection of expression-based index ix_unrelated_expression",
            SAWarning,
            stacklevel=1,
        )
        warnings.warn(
            "autogenerate skipping metadata-specified expression-based index "
            "'ix_message_session_metadata_tenant'; dialect 'sqlite' under SQLAlchemy 2.0.51 "
            "can't reflect these indexes so they can't be compared",
            UserWarning,
            stacklevel=1,
        )
        warnings.warn(
            "autogenerate skipping metadata-specified expression-based index "
            "'ix_message_session_metadata_user'; dialect 'sqlite' under SQLAlchemy 2.0.51 "
            "can't reflect these indexes so they can't be compared",
            UserWarning,
            stacklevel=1,
        )
        warnings.warn(
            "autogenerate skipping metadata-specified expression-based index "
            "'ix_unrelated_expression'; dialect 'sqlite' under SQLAlchemy 2.0.51 "
            "can't reflect these indexes so they can't be compared",
            UserWarning,
            stacklevel=1,
        )
        warnings.warn(
            "WARNING: SQL-parsed foreign key constraint '('user_id', 'user', 'id')' "
            "could not be located in PRAGMA foreign_keys for table file",
            SAWarning,
            stacklevel=1,
        )
        warnings.warn(
            "Unrelated SQLite reflection problem for table file",
            SAWarning,
            stacklevel=1,
        )

    assert [str(item.message) for item in caught] == [
        "Skipped unsupported reflection of expression-based index ix_unrelated_expression",
        "autogenerate skipping metadata-specified expression-based index "
        "'ix_unrelated_expression'; dialect 'sqlite' under SQLAlchemy 2.0.51 "
        "can't reflect these indexes so they can't be compared",
        "Unrelated SQLite reflection problem for table file",
    ]
