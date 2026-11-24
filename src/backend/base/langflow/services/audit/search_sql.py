r"""Search expressions that ignore case the same way on SQLite and PostgreSQL.

PostgreSQL's ``ILIKE`` folds every letter, but SQLite folds only ASCII, so a
search for "äöü" missed "ÄÖÜ" there. On SQLite both sides are therefore folded
by Python functions that :func:`register_sqlite_search_functions` installs on
every connection; PostgreSQL keeps the plain ``ILIKE``.

Both backends also store the ``details`` JSON with its non-ASCII letters
escaped (``\u00c4``), which no typed word matches: the column is ``sa.JSON``,
whose serializer escapes them, and PostgreSQL's ``json`` keeps the text it was
handed. So neither backend may read that column as plain text -- SQLite
re-renders the JSON through ``lf_json_text`` and PostgreSQL through ``jsonb``,
whose output writes the letters themselves.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Text, literal
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import ColumnElement, FunctionElement

_CASEFOLD = "lf_casefold"
_JSON_TEXT = "lf_json_text"


class folded(FunctionElement):  # noqa: N801 - SQL function constructs are lower case by convention
    """A text expression compared without regard to case, in any script."""

    type = Text()
    inherit_cache = True


class json_text(FunctionElement):  # noqa: N801
    """A JSON column as the text a person would type, letters unescaped."""

    type = Text()
    inherit_cache = True


@compiles(folded)
def _folded_default(element: folded, compiler: Any, **kw: Any) -> str:
    return compiler.process(element.clauses, **kw)


@compiles(folded, "sqlite")
def _folded_sqlite(element: folded, compiler: Any, **kw: Any) -> str:
    return f"{_CASEFOLD}({compiler.process(element.clauses, **kw)})"


@compiles(json_text)
def _json_text_default(element: json_text, compiler: Any, **kw: Any) -> str:
    return f"CAST({compiler.process(element.clauses, **kw)} AS TEXT)"


@compiles(json_text, "postgresql")
def _json_text_postgresql(element: json_text, compiler: Any, **kw: Any) -> str:
    # ``json`` keeps the text it was given, so casting it straight to text
    # searches the escapes; ``jsonb`` is re-rendered from its parsed form.
    return f"CAST(CAST({compiler.process(element.clauses, **kw)} AS JSONB) AS TEXT)"


@compiles(json_text, "sqlite")
def _json_text_sqlite(element: json_text, compiler: Any, **kw: Any) -> str:
    return f"{_JSON_TEXT}({compiler.process(element.clauses, **kw)})"


def case_insensitive_like(column: ColumnElement[Any], pattern: str, *, escape: str) -> ColumnElement[bool]:
    """``column ILIKE pattern`` whose case folding covers every script on every backend."""
    return folded(column).ilike(folded(literal(pattern, type_=Text())), escape=escape)


def _casefold(value: object) -> str | None:
    return value.casefold() if isinstance(value, str) else None


def _unescaped_json(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return json.dumps(json.loads(value), ensure_ascii=False)
    except ValueError:
        return value


def register_sqlite_search_functions(dbapi_connection: Any) -> None:
    """Install the folding functions the search expressions call on SQLite."""
    dbapi_connection.create_function(_CASEFOLD, 1, _casefold, deterministic=True)
    dbapi_connection.create_function(_JSON_TEXT, 1, _unescaped_json, deterministic=True)
