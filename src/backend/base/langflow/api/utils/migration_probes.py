"""Whether a destination can take this instance's data, asked before anything is copied.

Each probe answers {"ok": True} or {"ok": False, "code": ..., "reason": ...}, and none
raises for a destination that fails: a traceback would print the address it was given,
password included. A reason is the driver's own first line with the password and the
keys taken out. It can name the database user, so it is shown and never saved.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import ipaddress
import os
import re
from http import HTTPStatus
from typing import TYPE_CHECKING, Any
from urllib.parse import quote
from uuid import uuid4

import sqlalchemy as sa

from langflow.services.database.sqlite_to_postgres import (
    _foreign_users,
    _model_tables,
    _sync_postgres_url,
    _sync_sqlite_url,
)

if TYPE_CHECKING:
    from collections.abc import Callable

# The copy of a knowledge base leaves one table like this in the database.
_KNOWLEDGE_BASE_TABLE = re.compile(r"lf_[0-9a-f]{24}")
# Seconds to wait for a destination, so an address that leads nowhere answers while the admin watches.
_TIMEOUT = 10
# The options of an address that carry a secret.
_PASSWORD_OPTIONS = frozenset({"password", "sslpassword"})


def location(address: str) -> str | None:
    """Where a database is, without the user or the password. None for an address that cannot be read."""
    try:
        url = sa.make_url(address)
    except (sa.exc.ArgumentError, ValueError):
        return None
    return f"{url.host}:{url.port}/{url.database}" if url.port else f"{url.host}/{url.database}"


def database_identity(address: str) -> str:
    """Where an address leads and as whom, as a short digest that is safe to keep.

    The location leaves out the options of an address, and a host or a search_path given
    there changes which database a copy lands in. Everything that decides it goes in here:
    the user, the host, the port, the database name and every option. The driver and the
    password do not, so the same destination written two ways has one identity.
    """
    try:
        url = sa.make_url(address)
    except (sa.exc.ArgumentError, ValueError):
        return ""
    options = sorted((name, value) for name, value in url.query.items() if name not in _PASSWORD_OPTIONS)
    host = url.host
    # An IPv6 host can be written in several ways that lead to one place, so it goes in by one of them.
    with contextlib.suppress(ValueError):
        host = str(ipaddress.ip_address(host or ""))
    target = (url.get_backend_name(), url.username, host, url.port, url.database, options)
    return hashlib.sha256(repr(target).encode()).hexdigest()[:16]


def probe_database(address: str, source_address: str) -> dict[str, Any]:
    """Whether the database at this address can take the copy of this instance's SQLite database."""

    def empty_and_writable(target: sa.Connection) -> dict[str, Any] | None:
        ours = {*_model_tables(), "alembic_version"}
        strangers = [
            name
            for name in sa.inspect(target).get_table_names()
            if name not in ours and not _KNOWLEDGE_BASE_TABLE.fullmatch(name)
        ]
        if strangers:
            return _failed("db_not_empty", f"It holds tables that are not Langflow's, such as {strangers[0]}.")
        source = sa.create_engine(_sync_sqlite_url(source_address))
        try:
            with source.connect() as own:
                # The copy refuses the same thing. An earlier run of it leaves only this instance's users.
                if _foreign_users(own, target):
                    return _failed("db_not_empty", "It holds users that this instance does not have.")
        finally:
            source.dispose()
        return _cannot_create(target)

    return _ask(address, empty_and_writable)


def probe_vectors(address: str) -> dict[str, Any]:
    """Whether the database at this address can take knowledge bases as pgvector tables."""
    if importlib.util.find_spec("pgvector") is None:
        return _failed("pgvector_package_missing", "This server has no pgvector package. Install langflow[pgvector].")

    def has_the_extension(target: sa.Connection) -> dict[str, Any] | None:
        if target.scalar(sa.text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")):
            return _cannot_create(target)
        # Langflow never installs an extension, so one that is only available still has to be turned on.
        if target.scalar(sa.text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")):
            return _failed("pgvector_missing", "Run CREATE EXTENSION vector; in this database, then test again.")
        return _failed("pgvector_missing", "This database server does not have the vector extension.")

    return _ask(address, has_the_extension)


async def probe_files(
    *,
    bucket: str,
    prefix: str,
    access_key_id: str,
    secret_access_key: str,
    endpoint_url: str | None = None,
    ca_bundle: str | None = None,
) -> dict[str, Any]:
    """Whether these keys can write under this folder of the bucket, as the copy of the files will."""
    # Imported here, as the S3 storage does, so that a server which never moves does not load the S3 client.
    from aiobotocore.config import AioConfig
    from aiobotocore.session import AioSession

    key = "/".join(part for part in (prefix.strip("/"), f".langflow-migration-probe-{uuid4().hex}") if part)
    # The server's own AWS settings are not the destination's, so this session reads none of them: no
    # variable of its environment, no config file, no shared credentials file. A profile named there
    # would otherwise fail every client, whatever keys it was given.
    alone = {name: (None, None, default, cast) for name, (_, _, default, cast) in AioSession.SESSION_VARIABLES.items()}
    alone.update(
        config_file=(None, None, os.devnull, None),
        credentials_file=(None, None, os.devnull, None),
        ignore_configured_endpoint_urls=(None, None, True, None),
    )
    try:
        async with AioSession(alone).create_client(
            "s3",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            endpoint_url=endpoint_url,
            verify=ca_bundle,
            config=AioConfig(connect_timeout=_TIMEOUT, read_timeout=_TIMEOUT, retries={"total_max_attempts": 1}),
        ) as s3:
            await s3.head_bucket(Bucket=bucket)
            await s3.put_object(Bucket=bucket, Key=key, Body=b"")
            # Keys that may write and not delete leave this empty object behind. Nothing reads it.
            with contextlib.suppress(Exception):
                await s3.delete_object(Bucket=bucket, Key=key)
    except Exception as exc:  # noqa: BLE001 - a refusal, a network error and a bad setting are all answers
        response = getattr(exc, "response", None)
        status = response.get("ResponseMetadata", {}).get("HTTPStatusCode") if isinstance(response, dict) else None
        # The bucket answered that it is not there, or that these keys may not. Anything else never got an
        # answer about the bucket: an endpoint that cannot be used or reached, a timeout, a server error.
        code = {HTTPStatus.NOT_FOUND: "bucket_missing", HTTPStatus.FORBIDDEN: "bucket_denied"}.get(status)
        return _failed(code or "bucket_unreachable", _without(_first_line(exc), access_key_id, secret_access_key))
    return {"ok": True}


def _ask(address: str, question: Callable[[sa.Connection], dict[str, Any] | None]) -> dict[str, Any]:
    """Put a question to the PostgreSQL database at this address. The question returns what is wrong, or None."""
    try:
        url = sa.make_url(_sync_postgres_url(address))
    except (sa.exc.ArgumentError, ValueError):
        return _failed("db_unreachable", "This is not a database address.")
    if url.get_backend_name() != "postgresql":
        # Anything else would be opened too, and a SQLite address creates the file it names.
        return _failed("db_unreachable", "This is not a PostgreSQL address.")
    engine = None
    try:
        engine = sa.create_engine(url, connect_args={"connect_timeout": _TIMEOUT})
        with engine.connect() as target:
            return question(target) or {"ok": True}
    except ImportError:
        return _failed("db_unreachable", "This server has no PostgreSQL driver. Install langflow[postgresql].")
    except sa.exc.SQLAlchemyError as exc:
        return _failed("db_unreachable", _without(_first_line(getattr(exc, "orig", None) or exc), url.password))
    finally:
        if engine is not None:
            engine.dispose()


def _cannot_create(target: sa.Connection) -> dict[str, Any] | None:
    if target.scalar(sa.text("SELECT has_schema_privilege(current_schema(), 'CREATE')")):
        return None
    return _failed("no_create", "This database user cannot create tables here.")


def _failed(code: str, reason: str) -> dict[str, Any]:
    return {"ok": False, "code": code, "reason": reason}


def _first_line(exc: BaseException) -> str:
    # A driver's later lines repeat the statement it ran. An error with no words of its own is named instead.
    return (str(exc).splitlines() or [type(exc).__name__])[0]


def _without(text: str, *secrets: str | None) -> str:
    """The text with each secret taken out, both as it is and as an address spells it."""
    for secret in filter(None, secrets):
        text = text.replace(secret, "***").replace(quote(secret, safe=""), "***")
    return text
