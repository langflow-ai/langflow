from __future__ import annotations

import re
from typing import Any

_SENSITIVE_CONNECTION_PARAM_KEYS = {
    "access_token",
    "connection_string",
    "credential",
    "credentials",
    "dsn",
    "newpassword",
    "passwd",
    "password",
    "private_key",
    "proxy_user",
    "pwd",
    "secret",
    "tns",
    "token",
    "user",
    "username",
    "wallet_password",
}


def _is_sensitive_connection_param_key(key: str) -> bool:
    normalized_key = re.sub(r"[^0-9a-zA-Z]+", "_", key.strip().lower()).strip("_")
    compact_key = normalized_key.replace("_", "")
    return any(
        normalized_key == sensitive_key or compact_key == sensitive_key.replace("_", "")
        for sensitive_key in _SENSITIVE_CONNECTION_PARAM_KEYS
    )


def split_credentialized_dsn(dsn: str) -> tuple[str | None, str | None, str]:
    if "@" not in dsn:
        return None, None, dsn

    credentials, dsn_without_credentials = dsn.rsplit("@", 1)
    if "/" not in credentials:
        return None, None, dsn

    user, password = credentials.split("/", 1)
    return user or None, password or None, dsn_without_credentials


def build_connection_params(
    connection_params: dict[str, Any] | None = None,
    *,
    user: str | None = None,
    password: str | None = None,
    dsn: str | None = None,
    wallet_password: str | None = None,
) -> dict[str, Any]:
    raw_params = {key: value for key, value in (connection_params or {}).items() if value not in (None, "")}
    sensitive_keys = sorted(key for key in raw_params if _is_sensitive_connection_param_key(key))
    if sensitive_keys:
        keys = ", ".join(sensitive_keys)
        msg = (
            f"connection_params contains sensitive keys: {keys}. "
            "Use the dedicated secret fields for user, password, dsn, wallet_password, and proxy."
        )
        raise ValueError(msg)

    if isinstance(dsn, str) and (not user or not password):
        parsed_user, parsed_password, parsed_dsn = split_credentialized_dsn(dsn)
        user = user or parsed_user
        password = password or parsed_password
        dsn = parsed_dsn

    params = dict(raw_params)

    if user:
        params["user"] = user
    if password:
        params["password"] = password
    if dsn:
        params["dsn"] = dsn
    if wallet_password:
        params["wallet_password"] = wallet_password

    return params
