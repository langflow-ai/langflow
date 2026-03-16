"""Langflow database base model.

Defines ``LangflowBaseModel``, the canonical base class for **all** Langflow
database models (``table=True``).  It carries its own isolated
``sqlalchemy.MetaData`` instance so that Alembic autogenerate only sees tables
owned by Langflow — never tables registered by third-party libraries or other
applications sharing the same ``SQLModel`` global metadata.

Rules
-----
* Every model that sets ``table=True`` **must** ultimately inherit from
  ``LangflowBaseModel`` (either directly, or via an intermediate *Base class
  that inherits ``LangflowBaseModel``).
* Schema-only models (``table=False``, the default) used purely for API
  request/response serialization may continue to inherit directly from
  ``SQLModel`` — they do not participate in the metadata registry.
* ``issubclass(LangflowBaseModel, SQLModel)`` is ``True``, so FastAPI,
  Pydantic, and SQLModel integrations remain unchanged.

See Also:
--------
``langflow.alembic.env`` — the Alembic environment uses
``LangflowBaseModel.metadata`` as ``target_metadata`` and includes a
pre-migration validation check that aborts if any ``table=True`` model
in the codebase does *not* inherit from ``LangflowBaseModel``.
"""

import orjson
import sqlalchemy as sa
from sqlmodel import SQLModel


def orjson_dumps(v, *, default=None, sort_keys=False, indent_2=True):
    option = orjson.OPT_SORT_KEYS if sort_keys else None
    if indent_2:
        # orjson.dumps returns bytes, to match standard json.dumps we need to decode
        # option
        # To modify how data is serialized, specify option. Each option is an integer constant in orjson.
        # To specify multiple options, mask them together, e.g., option=orjson.OPT_STRICT_INTEGER | orjson.OPT_NAIVE_UTC
        if option is None:
            option = orjson.OPT_INDENT_2
        else:
            option |= orjson.OPT_INDENT_2
    if default is None:
        return orjson.dumps(v, option=option).decode()
    return orjson.dumps(v, default=default, option=option).decode()


# ---------------------------------------------------------------------------
# Isolated MetaData for Langflow tables
# ---------------------------------------------------------------------------
_langflow_metadata = sa.MetaData()


class LangflowBaseModel(SQLModel):
    """Base class for all Langflow database-backed models.

    Carries an isolated ``MetaData`` instance so Alembic only manages
    Langflow-owned tables.  Non-table (schema-only) subclasses are harmless
    because SQLModel/SQLAlchemy only registers a table when ``table=True``.

    Usage::

        class MyModel(LangflowBaseModel, table=True):
            __tablename__ = "my_model"
            id: int = Field(primary_key=True)
    """

    metadata = _langflow_metadata  # type: ignore[assignment]
