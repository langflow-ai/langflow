from __future__ import annotations

import json
import os
from typing import Any
from uuid import uuid4


def get_oracle_connection_params() -> dict[str, Any] | None:
    raw_params = os.getenv("ORACLE_CONNECTION_PARAMS")
    if raw_params:
        return json.loads(raw_params)

    user = os.getenv("ORACLE_USER") or os.getenv("VECDB_USER")
    password = os.getenv("ORACLE_PASSWORD") or os.getenv("VECDB_PASS")
    dsn = os.getenv("ORACLE_DSN") or os.getenv("VECDB_HOST")
    wallet_password = os.getenv("ORACLE_WALLET_PASSWORD")

    if dsn:
        connection_params = {
            "user": user,
            "password": password,
            "dsn": dsn,
            "wallet_password": wallet_password,
        }
        return {key: value for key, value in connection_params.items() if value}

    return None


def get_oracle_connection_inputs(connection_params: dict[str, Any] | None = None) -> dict[str, Any]:
    connection_params = dict(connection_params or get_oracle_connection_params() or {})
    inputs: dict[str, Any] = {
        "connection_params": {
            key: value
            for key, value in connection_params.items()
            if key not in {"user", "username", "password", "dsn", "tns", "connection_string", "wallet_password"}
        }
    }

    user = connection_params.get("user") or connection_params.get("username")
    if user:
        inputs["user"] = user

    password = connection_params.get("password")
    if password:
        inputs["password"] = password

    dsn = connection_params.get("dsn") or connection_params.get("connection_string") or connection_params.get("tns")
    if dsn:
        inputs["dsn"] = dsn

    wallet_password = connection_params.get("wallet_password")
    if wallet_password:
        inputs["wallet_password"] = wallet_password

    return inputs


def has_oracle_connection_params() -> bool:
    return get_oracle_connection_params() is not None


def get_oracle_embedding_params() -> dict[str, Any]:
    raw_params = os.getenv("ORACLE_EMBEDDING_PARAMS")
    if raw_params:
        return json.loads(raw_params)
    return {"provider": "database", "model": "ALL_MINILM_L12_V2"}


def get_oracle_test_connection_inputs(*, include_wallet_password: bool = False) -> dict[str, str]:
    inputs = {
        "user": os.getenv("ORACLE_TEST_USER") or os.getenv("VECDB_USER") or uuid4().hex,
        "password": os.getenv("ORACLE_TEST_PASSWORD") or os.getenv("VECDB_PASS") or uuid4().hex,
        "dsn": os.getenv("ORACLE_TEST_DSN") or os.getenv("VECDB_HOST") or uuid4().hex,
    }
    if include_wallet_password:
        inputs["wallet_password"] = os.getenv("ORACLE_TEST_WALLET_PASSWORD") or uuid4().hex
    return inputs


def get_oracle_owner(connection_params: dict[str, Any]) -> str:
    owner = os.getenv("ORACLE_OWNER") or connection_params.get("user") or connection_params.get("username")
    if owner:
        return owner

    dsn = connection_params.get("dsn")
    if isinstance(dsn, str) and "/" in dsn and "@" in dsn:
        return dsn.split("/", 1)[0]

    msg = "ORACLE_OWNER, ORACLE_USER, or VECDB_USER is required when DSN does not include a user."
    raise ValueError(msg)
