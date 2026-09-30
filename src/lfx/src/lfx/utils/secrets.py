from __future__ import annotations

from typing import Any, Protocol, TypeGuard


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
