from __future__ import annotations

import re
from typing import Any, Protocol, TypeGuard

_SECRET_NAME_PARTS = frozenset({"credential", "credentials", "passwd", "password", "secret"})
_SECRET_COMPOUND_NAMES = frozenset(
    {
        "access_key",
        "api_key",
        "apikey",
        "authorization",
        "client_secret",
        "connection_string",
        "cookie",
        "database_uri",
        "database_url",
        "dsn",
        "private_key",
        "proxy_authorization",
        "set_cookie",
    }
)


class SecretValue(Protocol):
    def get_secret_value(self) -> Any: ...


def is_secret_value(value: Any) -> TypeGuard[SecretValue]:
    return callable(getattr(value, "get_secret_value", None))


def unwrap_secret_value(value: Any) -> Any:
    seen: set[int] = set()
    while is_secret_value(value) and id(value) not in seen:
        seen.add(id(value))
        value = value.get_secret_value()
    return value


def secret_value_to_str(value: Any, *, strip: bool = False) -> str | None:
    value = unwrap_secret_value(value)
    if value is None:
        return None
    text = value if isinstance(value, str) else str(value)
    return text.strip() if strip else text


def normalized_secret_name(value: object) -> str:
    """Normalize snake, kebab, and camel-case names for classification."""
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(value or ""))
    return re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()


def is_secret_name(value: object) -> bool:
    normalized = normalized_secret_name(value)
    if normalized in _SECRET_COMPOUND_NAMES:
        return True
    parts = set(normalized.split("_"))
    is_token_value = normalized == "token" or normalized.endswith("_token")
    return bool(parts & _SECRET_NAME_PARTS) or is_token_value or {"api", "key"}.issubset(parts)
