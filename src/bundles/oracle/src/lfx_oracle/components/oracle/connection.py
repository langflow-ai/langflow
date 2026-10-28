from __future__ import annotations

import re
from typing import Any

from lfx.utils.ssrf_protection import (
    SSRFProtectionError,
    is_connector_ssrf_validation_enabled,
    is_ssrf_protection_enabled,
    validate_connector_hostname_for_ssrf,
)

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


def _validate_connection_targets(params: dict[str, Any]) -> dict[str, Any]:
    """Validate every address the Oracle driver can use before connecting."""
    if not is_connector_ssrf_validation_enabled() or not is_ssrf_protection_enabled():
        return params

    import oracledb

    unsupported = {"params", "pool", "pool_alias", "conn_class", "handle", "debug_jdwp"} & params.keys()
    if unsupported:
        msg = "Oracle connection overrides cannot bypass destination validation."
        raise SSRFProtectionError(msg)

    dsn = params.get("dsn")
    if isinstance(dsn, str) and "://" in dsn and not dsn.lower().startswith(("tcp://", "tcps://")):
        msg = "Oracle connection strings must use TCP or TCPS."
        raise SSRFProtectionError(msg)
    try:
        parsed = oracledb.ConnectParams(**{key: value for key, value in params.items() if key not in {"dsn", "schema"}})
        if dsn:
            parsed.parse_connect_string(dsn)
    except (oracledb.Error, TypeError, ValueError) as exc:
        msg = "Oracle connection string could not be validated. Use an Easy Connect address or a configured TNS alias."
        raise SSRFProtectionError(msg) from exc

    hosts = parsed.host if isinstance(parsed.host, list) else [parsed.host]
    proxies = parsed.https_proxy if isinstance(parsed.https_proxy, list) else [parsed.https_proxy]
    if not hosts or not all(hosts):
        msg = "Oracle connection string must contain a network host."
        raise SSRFProtectionError(msg)
    for host in [*hosts, *proxies, params.get("host"), params.get("https_proxy")]:
        if host:
            validate_connector_hostname_for_ssrf(host)

    if dsn:
        # Freeze the parsed address so aliases cannot be resolved again during connection.
        params = {**params, "dsn": parsed.get_connect_string()}
    return params


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

    return _validate_connection_targets(params)
