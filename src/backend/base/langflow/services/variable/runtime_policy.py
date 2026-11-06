"""Optional account-bound runtime resolution for serving-plane extensions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import UUID

from lfx.services.variable.exceptions import RuntimeVariableError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from pydantic import SecretStr


@dataclass(frozen=True)
class RuntimeVariable:
    """An authoritative result that must not fall back to another source."""

    value: str | SecretStr


_resolver: Callable[..., Awaitable[RuntimeVariable | None]] | None = None
_bulk_resolver: Callable[..., Awaitable[dict[str, str] | None]] | None = None
_mutation_guard: Callable[..., Awaitable[None]] | None = None


def register_runtime_variable_resolver(resolver: Callable[..., Awaitable[RuntimeVariable | None]] | None) -> None:
    """Install an account policy at application startup."""
    global _resolver  # noqa: PLW0603 - explicit process-wide extension registration
    _resolver = resolver


def register_runtime_variables_resolver(resolver: Callable[..., Awaitable[dict[str, str] | None]] | None) -> None:
    """Install the same account policy for MCP's bulk variable map."""
    global _bulk_resolver  # noqa: PLW0603 - explicit process-wide extension registration
    _bulk_resolver = resolver


def register_variable_mutation_guard(guard: Callable[..., Awaitable[None]] | None) -> None:
    """Coordinate ordinary writes with an extension's activation transaction."""
    global _mutation_guard  # noqa: PLW0603 - explicit process-wide extension registration
    _mutation_guard = guard


async def guard_variable_mutation(**context: Any) -> None:
    """Acquire an optional account writer lock before querying or changing rows."""
    from langflow.services.deployment_artifacts.activation import load_activation_extensions

    load_activation_extensions()
    if _mutation_guard is not None:
        context["user_id"] = UUID(str(context["user_id"]))
        await _mutation_guard(**context)


def runtime_variables_policy_enabled() -> bool:
    """Avoid opening a database session when no bulk account policy is installed."""
    _load_runtime_policy()
    return _bulk_resolver is not None


def _load_runtime_policy() -> None:
    from langflow.services.deployment_artifacts.activation import load_activation_extensions

    try:
        load_activation_extensions()
    except Exception:  # noqa: BLE001 - every policy failure must disable fallback
        msg = "Deployment variable policy is unavailable"
        raise RuntimeVariableError(msg, reason="policy_unavailable") from None


async def resolve_runtime_variable(**context: Any) -> RuntimeVariable | None:
    """None means the extension does not manage this execution account."""
    _load_runtime_policy()
    if _resolver is None:
        return None
    try:
        context["user_id"] = UUID(str(context["user_id"]))
        return await _resolver(**context)
    except RuntimeVariableError:
        raise
    except Exception:  # noqa: BLE001 - database/plugin failures must disable fallback
        msg = "Deployment variable policy is unavailable"
        raise RuntimeVariableError(msg, reason="policy_unavailable") from None


async def resolve_runtime_variables(**context: Any) -> dict[str, str] | None:
    """None preserves the OSS bulk behavior for unmanaged accounts."""
    _load_runtime_policy()
    if _bulk_resolver is None:
        return None
    try:
        context["user_id"] = UUID(str(context["user_id"]))
        return await _bulk_resolver(**context)
    except RuntimeVariableError:
        raise
    except Exception:  # noqa: BLE001 - database/plugin failures must disable fallback
        msg = "Deployment variable policy is unavailable"
        raise RuntimeVariableError(msg, reason="policy_unavailable") from None
