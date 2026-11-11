"""Credential-free source identity shared by the checker and report consumers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Annotated, Literal

import sqlalchemy as sa
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

_SHA256 = r"^[0-9a-f]{64}$"


class SQLiteSourceLocator(BaseModel):
    """The canonical file selected by the reader."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    path: str = Field(min_length=1, pattern=r"^(?:/|[A-Za-z]:[\\/]|\\\\)")


class PostgreSQLSourceLocator(BaseModel):
    """The connected endpoint and an opaque fingerprint of its ordered search path."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    host: str | None
    port: int = Field(ge=1, le=65535)
    database: str = Field(min_length=1)
    search_path_sha256: str = Field(pattern=_SHA256)


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class _SourceIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    kind: str
    locator: SQLiteSourceLocator | PostgreSQLSourceLocator
    sha256: str = Field(pattern=_SHA256)

    @model_validator(mode="after")
    def fingerprint_matches_locator(self) -> _SourceIdentity:
        """Reject reports whose fingerprint does not match their source locator."""
        if self.sha256 != _digest({"kind": self.kind, "locator": self.locator.model_dump()}):
            msg = "the source identity fingerprint does not match its locator"
            raise ValueError(msg)
        return self


class SQLiteSourceIdentity(_SourceIdentity):
    kind: Literal["sqlite"]
    locator: SQLiteSourceLocator


class PostgreSQLSourceIdentity(_SourceIdentity):
    kind: Literal["postgresql"]
    locator: PostgreSQLSourceLocator


SourceIdentity = Annotated[SQLiteSourceIdentity | PostgreSQLSourceIdentity, Field(discriminator="kind")]
SOURCE_IDENTITY_ADAPTER: TypeAdapter[SourceIdentity] = TypeAdapter(SourceIdentity)


def identity_for_source(database_url: str, connection: sa.Connection) -> SourceIdentity:
    """Identify the selected locator without copying credentials or URL options."""
    url = sa.make_url(database_url)
    locator: SQLiteSourceLocator | PostgreSQLSourceLocator
    if url.get_backend_name() == "sqlite":
        if not url.database or url.database == ":memory:":
            msg = "the SQLite source must name a database file"
            raise ValueError(msg)
        locator = SQLiteSourceLocator(path=str(Path(url.database).expanduser().resolve()))
        kind = "sqlite"
    elif url.get_backend_name() in {"postgresql", "postgres"}:
        database, schemas = connection.exec_driver_sql("SELECT current_database(), current_schemas(false)").one()
        info = connection.connection.driver_connection.info
        locator = PostgreSQLSourceLocator(
            host=info.host,
            port=info.port,
            database=database,
            search_path_sha256=_digest(schemas),
        )
        connection.rollback()
        kind = "postgresql"
    else:
        msg = "source identities require a SQLite or PostgreSQL connection"
        raise ValueError(msg)
    return SOURCE_IDENTITY_ADAPTER.validate_python(
        {
            "kind": kind,
            "locator": locator.model_dump(),
            "sha256": _digest({"kind": kind, "locator": locator.model_dump()}),
        }
    )
