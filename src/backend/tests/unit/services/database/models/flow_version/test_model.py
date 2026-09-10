"""Schema contracts for the ``flow_version`` model."""

from __future__ import annotations

from langflow.services.database.models.flow_version.model import VERSION_NUMBER_CHECK_NAME, FlowVersion
from sqlalchemy import CheckConstraint, Column, Integer, MetaData, Table
from sqlalchemy.sql.naming import conv

# Mirrors NAMING_CONVENTION in ``langflow/alembic/env.py`` (env.py cannot be imported: it runs migrations on import).
_NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def _check_names(table: Table) -> set[str]:
    return {constraint.name for constraint in table.constraints if isinstance(constraint, CheckConstraint)}


def test_flow_version_check_name_is_final_and_survives_naming_convention():
    """The conv()-marked name must not be re-prefixed when the table is copied under env.py's convention."""
    table = FlowVersion.__table__
    check_names = _check_names(table)

    assert check_names == {VERSION_NUMBER_CHECK_NAME}
    assert all(isinstance(name, conv) for name in check_names)

    copied = table.to_metadata(MetaData(naming_convention=_NAMING_CONVENTION))
    assert _check_names(copied) == check_names


def test_plain_string_check_name_is_re_prefixed_by_naming_convention():
    """Negative control: a plain-string name is rewritten by the convention, which is the drift being guarded."""
    table = Table(
        "flow_version",
        MetaData(naming_convention=_NAMING_CONVENTION),
        Column("version_number", Integer),
        CheckConstraint("version_number >= 1", name="check_version_number_positive"),
    )

    assert _check_names(table) == {"ck_flow_version_check_version_number_positive"}
