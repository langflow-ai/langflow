"""Add catalog policy rules for component and template governance.

Phase: EXPAND
Revision ID: d4a7c9e1b2f6
Revises: e8f1a2b3c4d5
Create Date: 2026-07-29 00:00:00.000000

The table is empty by default, preserving the existing default-allow catalog
behavior. P1 writes only global block rules; ``allow`` mode and scoped domains
are reserved so later phases can add behavior without replacing the schema.

Downgrade drops the table and all catalog-policy state. Back up policy rows
before downgrading if they will be needed after a future roll-forward.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from langflow.utils import migration
from sqlalchemy.dialects import postgresql
from sqlmodel.sql.sqltypes import AutoString

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from sqlalchemy.engine.reflection import Inspector

revision: str = "d4a7c9e1b2f6"  # pragma: allowlist secret
down_revision: str | None = "e8f1a2b3c4d5"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "catalog_policy_rule"
SCOPED_INDEX = "uq_catalog_policy_rule_scoped"
UNSCOPED_INDEX = "uq_catalog_policy_rule_unscoped"
_REQUIRED_INDEX_COLUMNS = (
    "resource_kind",
    "resource_key",
    "scope",
    "domain_id",
)
_REQUIRED_CHECKS = frozenset(
    {
        "ck_catalog_policy_rule_resource_kind",
        "ck_catalog_policy_rule_mode",
        "ck_catalog_policy_rule_scope",
        "ck_catalog_policy_rule_scope_domain_consistency",
    }
)
_SCHEMA_REMEDIATION = "Resolve the conflicting schema before rerunning this migration"
_CHECK_COLUMNS = ("resource_kind", "mode", "scope", "domain_id")
_SQLITE_UUID_LENGTH = 32
_BASELINE_CHECK_SQL = {
    "ck_catalog_policy_rule_resource_kind": "resource_kind IN ('component', 'template')",
    "ck_catalog_policy_rule_mode": "mode IN ('block', 'allow')",
    "ck_catalog_policy_rule_scope": "scope IN ('global', 'org', 'workspace')",
    "ck_catalog_policy_rule_scope_domain_consistency": (
        "(scope = 'global' AND domain_id IS NULL) OR (scope IN ('org', 'workspace') AND domain_id IS NOT NULL)"
    ),
}
_BASELINE_COLUMN_CONTRACTS = {
    "id": (False, "uuid", None),
    "resource_kind": (False, "string", None),
    "resource_key": (False, "string", None),
    "mode": (False, "string", "'block'"),
    "scope": (False, "string", "'global'"),
    "domain_id": (True, "uuid", None),
    "created_by": (True, "uuid", None),
    "created_at": (False, "datetime", "timestamp"),
    "updated_at": (False, "datetime", "timestamp"),
}
_REQUIRED_COLUMNS = frozenset(_BASELINE_COLUMN_CONTRACTS)
_BASELINE_UNIQUE_INDEXES = {
    SCOPED_INDEX: (
        ("resource_kind", "resource_key", "scope", "domain_id"),
        "domain_id IS NOT NULL",
    ),
    UNSCOPED_INDEX: (
        ("resource_kind", "resource_key", "scope"),
        "domain_id IS NULL",
    ),
}
_BASELINE_FOREIGN_KEYS = frozenset(
    {
        (
            ("created_by",),
            None,
            "user",
            ("id",),
            (("ondelete", "SET NULL"),),
        )
    }
)
_POSTGRES_CAST_PATTERN = re.compile(
    r"::\s*(?:character\s+varying|varchar|text)(?:\s*\[\s*\])?",
    flags=re.IGNORECASE,
)
_SQL_QUOTED_SEGMENT_PATTERN = re.compile(r"""('(?:''|[^'])*'|"(?:""|[^"])*")""")
_CHECK_TOKEN_PATTERN = re.compile(
    r"""
    (?P<string>'(?:''|[^'])*')
    |(?P<quoted_identifier>"(?:""|[^"])*")
    |(?P<identifier>[a-z_][a-z0-9_]*)
    |(?P<left_parenthesis>\()
    |(?P<right_parenthesis>\))
    |(?P<left_bracket>\[)
    |(?P<right_bracket>\])
    |(?P<comma>,)
    |(?P<equals>=)
    """,
    flags=re.IGNORECASE | re.VERBOSE,
)


def _strip_postgres_casts(value: object) -> str:
    """Remove reflection-added casts outside string and identifier quotes."""
    pieces = _SQL_QUOTED_SEGMENT_PATTERN.split(str(value))
    return "".join(piece if index % 2 else _POSTGRES_CAST_PATTERN.sub("", piece) for index, piece in enumerate(pieces))


def _strip_outer_parentheses(value: str) -> str:
    """Remove parentheses only when they wrap the complete SQL expression."""
    result = value
    while result.startswith("(") and result.endswith(")"):
        depth = 0
        in_literal = False
        wraps_expression = True
        index = 0
        while index < len(result):
            character = result[index]
            if character == "'":
                if in_literal and index + 1 < len(result) and result[index + 1] == "'":
                    index += 2
                    continue
                in_literal = not in_literal
            elif not in_literal:
                if character == "(":
                    depth += 1
                elif character == ")":
                    depth -= 1
                    if depth == 0 and index != len(result) - 1:
                        wraps_expression = False
                        break
            index += 1
        if not wraps_expression or depth != 0 or in_literal:
            break
        result = result[1:-1]
    return result


def _default_signature(value: object | None) -> str | None:
    """Preserve a complete server-default expression across reflection."""
    if value is None:
        return None
    sql = _strip_postgres_casts(value)
    pieces = re.split(r"('(?:''|[^'])*')", sql)
    normalized = "".join(
        piece if index % 2 else "".join(character.lower() for character in piece if not character.isspace())
        for index, piece in enumerate(pieces)
    )
    return _strip_outer_parentheses(normalized)


def _column_type_signature(column_type: object, *, dialect_name: str) -> str:
    """Normalize model and reflected column types across SQLite/PostgreSQL."""
    if isinstance(column_type, sa.Uuid):
        return "uuid"
    if (
        dialect_name == "sqlite"
        and isinstance(column_type, sa.CHAR)
        and getattr(column_type, "length", None) == _SQLITE_UUID_LENGTH
    ):
        return "uuid"
    if isinstance(column_type, sa.DateTime):
        if dialect_name == "postgresql" and bool(getattr(column_type, "timezone", False)):
            return "datetime:tz"
        return "datetime"
    if isinstance(column_type, sa.CHAR):
        return f"char:{getattr(column_type, 'length', None)}"
    if dialect_name == "postgresql" and isinstance(column_type, postgresql.CITEXT):
        return "string:case-insensitive:citext"
    if isinstance(column_type, sa.String):
        length = getattr(column_type, "length", None)
        collation = getattr(column_type, "collation", None)
        if collation is not None and str(collation).lower() not in {"binary", "default"}:
            return f"string:collation:{str(collation).lower()}"
        return "string" if length is None else f"string:{length}"
    return f"{type(column_type).__module__}.{type(column_type).__qualname__}"


def _column_default_signature(column_name: str, value: object | None) -> str | None:
    """Normalize ordinary literals and SQLAlchemy's dialect-specific now()."""
    signature = _default_signature(value)
    if column_name in {"created_at", "updated_at"} and signature in {"current_timestamp", "now()"}:
        return "timestamp"
    return signature


def _check_tokens(value: object) -> list[tuple[str, str]]:
    """Tokenize the restricted CHECK grammar used by catalog policy."""
    sql = _strip_postgres_casts(value)
    tokens: list[tuple[str, str]] = []
    position = 0
    while position < len(sql):
        if sql[position].isspace():
            position += 1
            continue
        match = _CHECK_TOKEN_PATTERN.match(sql, position)
        if match is None:
            msg = f"Unsupported token in catalog policy CHECK expression at offset {position}"
            raise ValueError(msg)
        kind = str(match.lastgroup)
        lexeme = match.group()
        if kind == "quoted_identifier":
            kind = "identifier"
            lexeme = lexeme[1:-1].replace('""', '"')
        elif kind == "identifier":
            lexeme = lexeme.lower()
        tokens.append((kind, lexeme))
        position = match.end()

    while True:
        simplified: list[tuple[str, str]] = []
        index = 0
        changed = False
        while index < len(tokens):
            if (
                index + 2 < len(tokens)
                and tokens[index][0] == "left_parenthesis"
                and tokens[index + 2][0] == "right_parenthesis"
                and tokens[index + 1][0] == "identifier"
                and tokens[index + 1][1] in _CHECK_COLUMNS
            ):
                simplified.append(tokens[index + 1])
                index += 3
                changed = True
                continue
            simplified.append(tokens[index])
            index += 1
        tokens = simplified
        if not changed:
            return tokens


def _combine_boolean(operator: str, expressions: list[tuple[object, ...]]) -> tuple[object, ...]:
    """Canonicalize commutative, associative boolean operations."""
    flattened: list[tuple[object, ...]] = []
    for expression in expressions:
        if expression[0] == operator:
            flattened.extend(expression[1:])
        else:
            flattened.append(expression)
    if len(flattened) == 1:
        return flattened[0]
    return (operator, *sorted(flattened, key=repr))


class _CheckParser:
    """Parse the deliberately small, side-effect-free CHECK expression grammar."""

    def __init__(self, tokens: list[tuple[str, str]]) -> None:
        self.tokens = tokens
        self.position = 0

    def parse(self) -> tuple[object, ...]:
        expression = self._parse_or()
        if self.position != len(self.tokens):
            msg = "Unexpected trailing tokens in catalog policy CHECK expression"
            raise ValueError(msg)
        return expression

    def _parse_or(self) -> tuple[object, ...]:
        expressions = [self._parse_and()]
        while self._accept_keyword("or"):
            expressions.append(self._parse_and())
        return _combine_boolean("or", expressions)

    def _parse_and(self) -> tuple[object, ...]:
        expressions = [self._parse_factor()]
        while self._accept_keyword("and"):
            expressions.append(self._parse_factor())
        return _combine_boolean("and", expressions)

    def _parse_factor(self) -> tuple[object, ...]:
        if self._accept("left_parenthesis") is not None:
            expression = self._parse_or()
            self._expect("right_parenthesis")
            return expression
        return self._parse_predicate()

    def _parse_predicate(self) -> tuple[object, ...]:
        column = self._expect("identifier")[1]
        if column not in _CHECK_COLUMNS:
            msg = "Unexpected column in catalog policy CHECK expression"
            raise ValueError(msg)

        if self._accept("equals") is not None:
            if self._accept_keyword("any"):
                return ("in", column, self._parse_postgres_array())
            return ("equals", column, self._string_value(self._expect("string")[1]))
        if self._accept_keyword("in"):
            return ("in", column, self._parse_string_list())
        if self._accept_keyword("is"):
            is_not = self._accept_keyword("not")
            self._expect_keyword("null")
            return ("is_not_null" if is_not else "is_null", column)
        msg = "Unsupported catalog policy CHECK predicate"
        raise ValueError(msg)

    def _parse_string_list(self) -> tuple[str, ...]:
        self._expect("left_parenthesis")
        values = self._parse_string_values()
        self._expect("right_parenthesis")
        return values

    def _parse_postgres_array(self) -> tuple[str, ...]:
        wrapper_count = 0
        while self._accept("left_parenthesis") is not None:
            wrapper_count += 1
        if wrapper_count == 0:
            msg = "Expected a parenthesized PostgreSQL catalog policy array"
            raise ValueError(msg)
        self._expect_keyword("array")
        self._expect("left_bracket")
        values = self._parse_string_values()
        self._expect("right_bracket")
        for _ in range(wrapper_count):
            self._expect("right_parenthesis")
        return values

    def _parse_string_values(self) -> tuple[str, ...]:
        values = [self._string_value(self._expect("string")[1])]
        while self._accept("comma") is not None:
            values.append(self._string_value(self._expect("string")[1]))
        return tuple(sorted(set(values)))

    def _accept(self, kind: str) -> tuple[str, str] | None:
        if self.position < len(self.tokens) and self.tokens[self.position][0] == kind:
            token = self.tokens[self.position]
            self.position += 1
            return token
        return None

    def _accept_keyword(self, keyword: str) -> bool:
        if self.position < len(self.tokens) and self.tokens[self.position] == ("identifier", keyword):
            self.position += 1
            return True
        return False

    def _expect(self, kind: str) -> tuple[str, str]:
        token = self._accept(kind)
        if token is None:
            msg = f"Expected {kind} in catalog policy CHECK expression"
            raise ValueError(msg)
        return token

    def _expect_keyword(self, keyword: str) -> None:
        if not self._accept_keyword(keyword):
            msg = f"Expected {keyword} in catalog policy CHECK expression"
            raise ValueError(msg)

    @staticmethod
    def _string_value(token: str) -> str:
        return token[1:-1].replace("''", "'")


def _check_ast(value: object) -> tuple[object, ...] | None:
    """Return a shape-preserving AST, or None for unsupported SQL."""
    try:
        return _CheckParser(_check_tokens(value)).parse()
    except ValueError:
        return None


def _current_model_table() -> sa.Table:
    """Load the current model contract only for the create_all-first path."""
    from langflow.services.database.models.catalog_policy import CatalogPolicyRule

    return CatalogPolicyRule.__table__


def _current_check_sql() -> dict[str, object]:
    """Return named CHECK expressions from the current model."""
    return {
        str(constraint.name): constraint.sqltext
        for constraint in _current_model_table().constraints
        if isinstance(constraint, sa.CheckConstraint) and constraint.name is not None
    }


def _matches_check_contract(reflected: Mapping[str, object], expected: Mapping[str, object]) -> bool:
    """Return whether reflected checks satisfy one complete contract."""
    if expected.keys() != reflected.keys():
        return False
    for name, sqltext in expected.items():
        reflected_ast = _check_ast(reflected[name])
        expected_ast = _check_ast(sqltext)
        if reflected_ast is None or expected_ast is None or reflected_ast != expected_ast:
            return False
    return True


def _validate_check_constraints(inspector: Inspector) -> None:
    """Accept the frozen migration checks or the current model's checks."""
    reflected_constraints = inspector.get_check_constraints(TABLE_NAME)
    named_constraints = [constraint for constraint in reflected_constraints if constraint.get("name") is not None]
    reflected = {str(constraint["name"]): constraint.get("sqltext") for constraint in named_constraints}
    current = _current_check_sql()
    has_unnamed_checks = any(constraint.get("name") is None for constraint in reflected_constraints)
    has_duplicate_names = len(named_constraints) != len(reflected)
    has_behavior_options = any(
        any(bool(value) for value in (constraint.get("dialect_options") or {}).values())
        for constraint in reflected_constraints
    )
    if (
        not has_unnamed_checks
        and not has_duplicate_names
        and not has_behavior_options
        and (_matches_check_contract(reflected, _BASELINE_CHECK_SQL) or _matches_check_contract(reflected, current))
    ):
        return

    missing_baseline = _REQUIRED_CHECKS - reflected.keys()
    missing_current = current.keys() - reflected.keys()
    if missing_baseline and missing_current:
        missing = sorted(missing_baseline if len(missing_baseline) <= len(missing_current) else missing_current)
        detail = f"{TABLE_NAME} exists but is missing required check constraints: {missing}"
    else:
        detail = f"{TABLE_NAME} has incompatible check constraint definitions"
    _raise_schema_error(detail)


def _validate_columns(columns: list[dict[str, object]], *, dialect_name: str) -> None:
    """Validate types, defaults, and nullability against frozen or current models."""
    reflected = {str(column["name"]): column for column in columns}
    current_table = _current_model_table()
    for column_name, frozen_contract in _BASELINE_COLUMN_CONTRACTS.items():
        baseline_contract = frozen_contract
        if frozen_contract[1] == "datetime" and dialect_name == "postgresql":
            baseline_contract = (frozen_contract[0], "datetime:tz", frozen_contract[2])
        current_column = current_table.c[column_name]
        current_default = current_column.server_default
        current_contract = (
            bool(current_column.nullable),
            _column_type_signature(current_column.type, dialect_name=dialect_name),
            _column_default_signature(column_name, current_default.arg if current_default is not None else None),
        )
        actual_contract = (
            bool(reflected[column_name]["nullable"]),
            _column_type_signature(reflected[column_name]["type"], dialect_name=dialect_name),
            _column_default_signature(column_name, reflected[column_name].get("default")),
        )
        if actual_contract in {baseline_contract, current_contract}:
            continue

        if actual_contract[0] not in {baseline_contract[0], current_contract[0]}:
            detail = f"{TABLE_NAME}.{column_name} has incompatible nullability"
        elif actual_contract[1] not in {baseline_contract[1], current_contract[1]}:
            detail = f"{TABLE_NAME}.{column_name} has an incompatible type"
        else:
            detail = f"{TABLE_NAME}.{column_name} has an incompatible default"
        _raise_schema_error(detail)


def _foreign_key_options(options: Mapping[str, object]) -> tuple[tuple[str, str], ...]:
    """Normalize behavior-changing foreign-key options."""
    normalized: list[tuple[str, str]] = []
    for name in ("ondelete", "onupdate", "deferrable", "initially", "match"):
        value = options.get(name)
        if value is None or str(value).upper() == "NO ACTION":
            continue
        normalized.append((name, str(value).upper()))
    return tuple(normalized)


def _reflected_foreign_key_contracts(
    inspector: Inspector,
) -> frozenset[tuple[tuple[str, ...], str | None, str, tuple[str, ...], tuple[tuple[str, str], ...]]]:
    """Return behavior-relevant reflected foreign-key fields."""
    return frozenset(
        (
            tuple(str(column) for column in (foreign_key.get("constrained_columns") or ())),
            str(foreign_key["referred_schema"]) if foreign_key.get("referred_schema") is not None else None,
            str(foreign_key.get("referred_table")),
            tuple(str(column) for column in (foreign_key.get("referred_columns") or ())),
            _foreign_key_options(foreign_key.get("options") or {}),
        )
        for foreign_key in inspector.get_foreign_keys(TABLE_NAME)
    )


def _current_foreign_key_contracts() -> frozenset[
    tuple[tuple[str, ...], str | None, str, tuple[str, ...], tuple[tuple[str, str], ...]]
]:
    """Return foreign-key fields emitted by the current model."""
    return frozenset(
        (
            tuple(str(element.parent.name) for element in constraint.elements),
            str(constraint.referred_table.schema) if constraint.referred_table.schema is not None else None,
            str(constraint.referred_table.name),
            tuple(str(element.column.name) for element in constraint.elements),
            _foreign_key_options(
                {
                    "ondelete": constraint.ondelete,
                    "onupdate": constraint.onupdate,
                    "deferrable": constraint.deferrable,
                    "initially": constraint.initially,
                    "match": constraint.match,
                }
            ),
        )
        for constraint in _current_model_table().foreign_key_constraints
    )


def _validate_foreign_keys(inspector: Inspector) -> None:
    """Reject foreign keys beyond the frozen or current complete contract."""
    reflected = _reflected_foreign_key_contracts(inspector)
    if reflected not in {_BASELINE_FOREIGN_KEYS, _current_foreign_key_contracts()}:
        detail = f"{TABLE_NAME} has an incompatible foreign key contract"
        _raise_schema_error(detail)


def _raise_schema_error(detail: str) -> None:
    """Raise an actionable error for an incompatible pre-existing table."""
    msg = f"{detail}. {_SCHEMA_REMEDIATION}."
    raise RuntimeError(msg)


def _validate_sqlite_collations(conn: sa.Connection) -> None:
    """Reject case-folding collations that change exact-key uniqueness."""
    if conn.dialect.name != "sqlite":
        return
    table_sql = conn.execute(
        sa.text(
            """
            SELECT sql
            FROM sqlite_master
            WHERE tbl_name = :table_name
              AND type = 'table'
            """
        ),
        {"table_name": TABLE_NAME},
    ).scalar_one_or_none()
    reflected_collations = {
        next(value for value in match if value).lower()
        for match in re.findall(
            r"""\bcollate\s+(?:"([^"]+)"|`([^`]+)`|\[([^\]]+)\]|'([^']+)'|([a-z_][a-z0-9_]*))""",
            str(table_sql or ""),
            flags=re.IGNORECASE,
        )
    }
    unique_index_names = conn.execute(
        sa.text("""SELECT name FROM pragma_index_list(:table_name) WHERE "unique" = 1"""),
        {"table_name": TABLE_NAME},
    ).scalars()
    for index_name in unique_index_names:
        index_collations = conn.execute(
            sa.text("SELECT coll FROM pragma_index_xinfo(:index_name) WHERE key = 1"),
            {"index_name": index_name},
        ).scalars()
        reflected_collations.update(str(collation).lower() for collation in index_collations if collation is not None)
    if reflected_collations - {"binary"}:
        detail = f"{TABLE_NAME} has an incompatible case-insensitive collation"
        _raise_schema_error(detail)


def _validate_existing_table(conn: sa.Connection) -> None:
    """Validate stable structure without writing probe rows.

    Langflow calls SQLModel ``create_all`` before Alembic on a fresh install, so
    this path is normal startup behavior. Keep the checks limited to stable
    structural invariants so future model changes do not invalidate this
    historical migration.
    """
    inspector = sa.inspect(conn)
    reflected_columns = inspector.get_columns(TABLE_NAME)
    columns = {column["name"] for column in reflected_columns}
    missing_columns = _REQUIRED_COLUMNS - columns
    if missing_columns:
        detail = f"{TABLE_NAME} exists but is missing required columns: {sorted(missing_columns)}"
        _raise_schema_error(detail)
    current_columns = set(_current_model_table().c.keys())
    unsupported_required_columns = sorted(
        str(column["name"])
        for column in reflected_columns
        if column["name"] not in current_columns
        and not bool(column["nullable"])
        and _default_signature(column.get("default")) in {None, "null"}
        and column.get("computed") is None
        and column.get("identity") is None
    )
    if unsupported_required_columns:
        detail = f"{TABLE_NAME} has unsupported required columns: {unsupported_required_columns}"
        _raise_schema_error(detail)
    _validate_sqlite_collations(conn)
    _validate_columns(reflected_columns, dialect_name=conn.dialect.name)

    _validate_check_constraints(inspector)
    primary_key = inspector.get_pk_constraint(TABLE_NAME)
    if primary_key.get("constrained_columns") != ["id"]:
        detail = f"{TABLE_NAME} exists without the required primary key on id"
        _raise_schema_error(detail)

    _validate_foreign_keys(inspector)


def _raise_for_duplicate_rows(conn: sa.Connection, *, index_name: str) -> None:
    """Fail clearly when existing rows prevent a missing unique index repair."""
    table = sa.Table(TABLE_NAME, sa.MetaData(), autoload_with=conn)
    if index_name == SCOPED_INDEX:
        key_columns = [
            table.c.resource_kind,
            table.c.resource_key,
            table.c.scope,
            table.c.domain_id,
        ]
        predicate = table.c.domain_id.is_not(None)
    else:
        key_columns = [
            table.c.resource_kind,
            table.c.resource_key,
            table.c.scope,
        ]
        predicate = table.c.domain_id.is_(None)

    duplicate = conn.execute(
        sa.select(sa.literal(1)).where(predicate).group_by(*key_columns).having(sa.func.count() > 1).limit(1)
    ).first()
    if duplicate is not None:
        msg = (
            f"{TABLE_NAME} contains duplicate rows that prevent creating {index_name}; "
            "remove the duplicates before rerunning this migration"
        )
        raise RuntimeError(msg)


def _index_predicate(index: Mapping[str, object]) -> object | None:
    """Return a reflected SQLite or PostgreSQL partial-index predicate."""
    dialect_options = index.get("dialect_options") or {}
    predicate = dialect_options.get("sqlite_where")
    if predicate is None:
        predicate = dialect_options.get("postgresql_where")
    return predicate


def _index_contract(
    columns: object,
    predicate: object | None,
) -> tuple[tuple[str, ...], tuple[object, ...] | None]:
    """Return the stable fields that determine uniqueness behavior."""
    column_names = tuple(str(column) for column in (columns or ()))
    if predicate is None:
        predicate_ast = None
    else:
        predicate_ast = _check_ast(predicate)
        if predicate_ast is None:
            predicate_ast = ("unsupported", _default_signature(predicate))
    return column_names, predicate_ast


def _current_unique_index_contracts() -> dict[str | None, tuple[tuple[str, ...], tuple[object, ...] | None]]:
    """Return unique-index contracts emitted by the current model."""
    contracts: dict[str | None, tuple[tuple[str, ...], tuple[object, ...] | None]] = {}
    for index in _current_model_table().indexes:
        if not index.unique:
            continue
        predicate = index.dialect_options["sqlite"].get("where")
        if predicate is None:
            predicate = index.dialect_options["postgresql"].get("where")
        contracts[str(index.name) if index.name is not None else None] = _index_contract(
            [column.name for column in index.columns],
            predicate,
        )
    return contracts


def _baseline_unique_index_contracts() -> dict[str, tuple[tuple[str, ...], tuple[object, ...] | None]]:
    """Return normalized contracts owned by this migration."""
    return {
        name: _index_contract(columns, predicate) for name, (columns, predicate) in _BASELINE_UNIQUE_INDEXES.items()
    }


def _reflected_unique_index_contracts(
    indexes: list[dict[str, object]],
) -> dict[str | None, tuple[tuple[str, ...], tuple[object, ...] | None]]:
    """Return explicit unique indexes, excluding constraint mirror indexes."""
    return {
        str(index["name"]) if index.get("name") is not None else None: _index_contract(
            index.get("column_names"),
            _index_predicate(index),
        )
        for index in indexes
        if bool(index.get("unique")) and index.get("duplicates_constraint") is None
    }


def _matches_repairable_index_contract(
    reflected: Mapping[str | None, tuple[tuple[str, ...], tuple[object, ...] | None]],
    expected: Mapping[str | None, tuple[tuple[str, ...], tuple[object, ...] | None]],
) -> bool:
    """Allow missing owned indexes while rejecting unknown or malformed ones."""
    return reflected.keys() <= expected.keys() and all(reflected[name] == expected[name] for name in reflected)


def _current_unique_constraint_contracts() -> frozenset[tuple[str | None, tuple[str, ...]]]:
    """Return table-level unique constraints emitted by the current model."""
    return frozenset(
        (
            str(constraint.name) if constraint.name is not None else None,
            tuple(str(column.name) for column in constraint.columns),
        )
        for constraint in _current_model_table().constraints
        if isinstance(constraint, sa.UniqueConstraint)
    )


def _validate_unique_contracts(inspector: Inspector, indexes: list[dict[str, object]]) -> None:
    """Reject uniqueness beyond the frozen or current complete model contract."""
    reflected_indexes = _reflected_unique_index_contracts(indexes)
    baseline_indexes = _baseline_unique_index_contracts()
    current_indexes = _current_unique_index_contracts()
    if not (
        _matches_repairable_index_contract(reflected_indexes, baseline_indexes)
        or _matches_repairable_index_contract(reflected_indexes, current_indexes)
    ):
        detail = f"{TABLE_NAME} has an incompatible unique index contract"
        _raise_schema_error(detail)

    reflected_constraints = frozenset(
        (
            str(constraint["name"]) if constraint.get("name") is not None else None,
            tuple(str(column) for column in (constraint.get("column_names") or ())),
        )
        for constraint in inspector.get_unique_constraints(TABLE_NAME)
    )
    if reflected_constraints not in {frozenset(), _current_unique_constraint_contracts()}:
        detail = f"{TABLE_NAME} has an incompatible unique constraint contract"
        _raise_schema_error(detail)


def _create_missing_indexes(conn: sa.Connection) -> None:
    """Create or validate the NULL-safe uniqueness indexes."""
    if not all(migration.column_exists(TABLE_NAME, column_name, conn) for column_name in _REQUIRED_INDEX_COLUMNS):
        detail = f"{TABLE_NAME} is missing columns required by its unique indexes"
        _raise_schema_error(detail)

    inspector = sa.inspect(conn)
    reflected_indexes = inspector.get_indexes(TABLE_NAME)
    _validate_unique_contracts(inspector, reflected_indexes)
    indexes = {index["name"]: index for index in reflected_indexes}
    expected_indexes = _BASELINE_UNIQUE_INDEXES
    current_indexes = _current_unique_index_contracts()
    for index_name, (expected_columns, expected_predicate) in expected_indexes.items():
        index = indexes.get(index_name)
        if index is None:
            continue
        reflected_contract = _index_contract(index.get("column_names"), _index_predicate(index))
        allowed_contracts = {
            _index_contract(expected_columns, expected_predicate),
            current_indexes.get(index_name),
        }
        if not bool(index.get("unique")) or reflected_contract not in allowed_contracts:
            detail = f"{TABLE_NAME}.{index_name} has an incompatible definition"
            _raise_schema_error(detail)

    existing_indexes = set(indexes)
    if SCOPED_INDEX not in existing_indexes:
        _raise_for_duplicate_rows(conn, index_name=SCOPED_INDEX)
        op.create_index(
            SCOPED_INDEX,
            TABLE_NAME,
            ["resource_kind", "resource_key", "scope", "domain_id"],
            unique=True,
            postgresql_where=sa.text("domain_id IS NOT NULL"),
            sqlite_where=sa.text("domain_id IS NOT NULL"),
        )
    if UNSCOPED_INDEX not in existing_indexes:
        _raise_for_duplicate_rows(conn, index_name=UNSCOPED_INDEX)
        op.create_index(
            UNSCOPED_INDEX,
            TABLE_NAME,
            ["resource_kind", "resource_key", "scope"],
            unique=True,
            postgresql_where=sa.text("domain_id IS NULL"),
            sqlite_where=sa.text("domain_id IS NULL"),
        )


def upgrade() -> None:
    """Create catalog policy storage or validate its stable existing shape."""
    conn = op.get_bind()

    if migration.table_exists(TABLE_NAME, conn):
        _validate_existing_table(conn)
    else:
        op.create_table(
            TABLE_NAME,
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("resource_kind", AutoString(), nullable=False),
            sa.Column("resource_key", AutoString(), nullable=False),
            sa.Column("mode", AutoString(), nullable=False, server_default=sa.text("'block'")),
            sa.Column("scope", AutoString(), nullable=False, server_default=sa.text("'global'")),
            sa.Column("domain_id", sa.Uuid(), nullable=True),
            sa.Column("created_by", sa.Uuid(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["created_by"], ["user.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.CheckConstraint(
                _BASELINE_CHECK_SQL["ck_catalog_policy_rule_resource_kind"],
                name="ck_catalog_policy_rule_resource_kind",
            ),
            sa.CheckConstraint(
                _BASELINE_CHECK_SQL["ck_catalog_policy_rule_mode"],
                name="ck_catalog_policy_rule_mode",
            ),
            sa.CheckConstraint(
                _BASELINE_CHECK_SQL["ck_catalog_policy_rule_scope"],
                name="ck_catalog_policy_rule_scope",
            ),
            sa.CheckConstraint(
                _BASELINE_CHECK_SQL["ck_catalog_policy_rule_scope_domain_consistency"],
                name="ck_catalog_policy_rule_scope_domain_consistency",
            ),
        )

    _create_missing_indexes(conn)


def downgrade() -> None:
    """Drop catalog policy storage and its rows."""
    conn = op.get_bind()
    if migration.table_exists(TABLE_NAME, conn):
        op.drop_table(TABLE_NAME)
