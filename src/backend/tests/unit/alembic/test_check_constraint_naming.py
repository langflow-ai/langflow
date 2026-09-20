"""Guard against CHECK constraint names being double-prefixed by the naming convention.

``langflow/alembic/env.py`` installs ``ck_%(table_name)s_%(constraint_name)s`` on
``SQLModel.metadata``. SQLAlchemy applies that template to any plain-string
constraint name, so a name that already carries the ``ck_<table>_`` prefix is
rendered as ``ck_<table>_ck_<table>_...`` (truncated with a hash suffix on
PostgreSQL) unless it is marked final with ``op.f()`` / ``conv()`` (GH #15006).
"""

from __future__ import annotations

import ast

import sqlalchemy as sa
from alembic import command
from langflow.services.database import models  # noqa: F401  # registers every table on SQLModel.metadata
from sqlalchemy.sql.naming import conv
from sqlmodel import SQLModel

from .test_migration_execution import _SCRIPT_LOCATION, _engine_url, _make_alembic_cfg, db_url  # noqa: F401

# Mirrors the ``ck`` entry of NAMING_CONVENTION in ``langflow/alembic/env.py``.
_NAMING_CONVENTION = {"ck": "ck_%(table_name)s_%(constraint_name)s"}


def _doubled_prefix_names(table_name: str, names: set[str]) -> set[str]:
    return {name for name in names if name.startswith(f"ck_{table_name}_ck_")}


def _prefixed_checks(table: sa.Table) -> list[sa.CheckConstraint]:
    return [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, sa.CheckConstraint) and str(constraint.name).startswith("ck_")
    ]


def test_model_check_names_are_final_under_naming_convention():
    """Prefixed model CHECK names must be conv()-marked and survive re-attachment under the convention."""
    violations: dict[str, dict[str, list[str]]] = {}
    for table in SQLModel.metadata.sorted_tables:
        prefixed = _prefixed_checks(table)
        if not prefixed:
            continue
        unmarked = sorted(str(constraint.name) for constraint in prefixed if not isinstance(constraint.name, conv))
        copied = table.to_metadata(sa.MetaData(naming_convention=_NAMING_CONVENTION))
        rendered = {
            str(constraint.name) for constraint in copied.constraints if isinstance(constraint, sa.CheckConstraint)
        }
        doubled = sorted(_doubled_prefix_names(table.name, rendered))
        if unmarked or doubled:
            violations[table.name] = {"unmarked": unmarked, "doubled": doubled}
    assert violations == {}


def _string_assignments(module: ast.Module) -> dict[str, str]:
    """Resolve ``NAME = "literal"`` (directly or through ``NAME = OTHER_NAME``) anywhere in the module."""
    literals: dict[str, str] = {}
    aliases: dict[str, str] = {}
    for node in ast.walk(module):
        target = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target = node.targets[0].id
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target = node.target.id
        if target is None:
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            literals[target] = node.value.value
        elif isinstance(node.value, ast.Name):
            aliases[target] = node.value.id
    for name, source in aliases.items():
        seen = {name}
        resolved = source
        while resolved in aliases and resolved not in seen:
            seen.add(resolved)
            resolved = aliases[resolved]
        if resolved in literals:
            literals[name] = literals[resolved]
    return literals


def _check_name_argument(call: ast.Call) -> ast.expr | None:
    callee = call.func
    if isinstance(callee, ast.Attribute):
        attribute = callee.attr
    elif isinstance(callee, ast.Name):
        attribute = callee.id
    else:
        return None
    if attribute == "CheckConstraint":
        return next((keyword.value for keyword in call.keywords if keyword.arg == "name"), None)
    if attribute == "create_check_constraint":
        named = next((keyword.value for keyword in call.keywords if keyword.arg == "constraint_name"), None)
        if named is not None:
            return named
        return call.args[0] if call.args else None
    return None


def _plain_name(node: ast.expr | None, literals: dict[str, str]) -> str | None:
    """Return the plain-string name an argument resolves to; ``op.f()``/``conv()`` calls resolve to None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return literals.get(node.id)
    return None


def test_migrations_mark_prefixed_check_names_final():
    """A migration must wrap an already-prefixed CHECK name in ``op.f()`` so the convention leaves it alone."""
    offenders: list[str] = []
    for path in sorted((_SCRIPT_LOCATION / "versions").glob("*.py")):
        module = ast.parse(path.read_text(encoding="utf-8"))
        literals = _string_assignments(module)
        for node in ast.walk(module):
            if not isinstance(node, ast.Call):
                continue
            name = _plain_name(_check_name_argument(node), literals)
            if name is not None and name.startswith("ck_"):
                offenders.append(f"{path.name}:{node.lineno}: {name}")
    assert offenders == []


def test_migrated_schema_has_no_double_prefixed_check_names(db_url):  # noqa: F811
    """Upgrading a fresh database to head must not render ``ck_<table>_ck_<table>_...`` names."""
    command.upgrade(_make_alembic_cfg(db_url), "head")

    engine = sa.create_engine(_engine_url(db_url))
    try:
        inspector = sa.inspect(engine)
        doubled: dict[str, list[str]] = {}
        for table_name in inspector.get_table_names():
            names = {str(check["name"]) for check in inspector.get_check_constraints(table_name) if check.get("name")}
            rendered = _doubled_prefix_names(table_name, names)
            if rendered:
                doubled[table_name] = sorted(rendered)
    finally:
        engine.dispose()

    assert doubled == {}
