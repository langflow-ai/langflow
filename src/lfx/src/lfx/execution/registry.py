"""Executor registry."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lfx.execution.executor import Executor


class ExecutorNotFoundError(LookupError):
    pass


class ExecutorKindCollisionError(ValueError):
    """Raised when registering an executor whose kind is already registered and replace=False."""


class ExecutorRegistry:
    def __init__(self) -> None:
        self._by_kind: dict[str, Executor] = {}

    def register(self, executor: Executor, *, replace: bool = True) -> None:
        """Register an executor by its kind.

        Args:
            executor: The executor to register.
            replace: If True (default), overwrite any existing executor with the same kind.
                If False, raise :class:`ExecutorKindCollisionError` instead. Discovery paths
                pass ``replace=False`` so an installed package cannot silently replace a
                pre-registered executor (notably the built-in ``in-process``).
        """
        if not replace and executor.kind in self._by_kind:
            msg = f"Executor kind={executor.kind!r} is already registered"
            raise ExecutorKindCollisionError(msg)
        self._by_kind[executor.kind] = executor

    def has(self, kind: str) -> bool:
        return kind in self._by_kind

    def get(self, kind: str) -> Executor:
        try:
            return self._by_kind[kind]
        except KeyError as exc:
            msg = f"No executor registered for kind={kind!r}"
            raise ExecutorNotFoundError(msg) from exc
