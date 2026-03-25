from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from contextvars import Token
    from uuid import UUID


@dataclass(frozen=True, slots=True)
class DeploymentAdapterContext:
    provider_id: UUID


class DeploymentProviderIDContext:
    _current: ClassVar[ContextVar[DeploymentAdapterContext | None]] = ContextVar(
        "langflow_current_deployment_context",
        default=None,
    )

    @classmethod
    def get_current(cls) -> DeploymentAdapterContext | None:
        return cls._current.get()

    @classmethod
    def set_current(cls, context: DeploymentAdapterContext) -> Token[DeploymentAdapterContext | None]:
        return cls._current.set(context)

    @classmethod
    def reset_current(cls, token: Token[DeploymentAdapterContext | None]) -> None:
        cls._current.reset(token)

    @classmethod
    @contextmanager
    def scope(cls, context: DeploymentAdapterContext):
        token: Token[DeploymentAdapterContext | None] = cls.set_current(context)
        try:
            yield
        finally:
            cls.reset_current(token)
