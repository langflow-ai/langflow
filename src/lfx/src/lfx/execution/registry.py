"""Executor registry."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lfx.execution.executor import Executor


class ExecutorNotFoundError(LookupError):
    pass


class ExecutorRegistry:
    def __init__(self) -> None:
        self._by_kind: dict[str, Executor] = {}

    def register(self, executor: Executor) -> None:
        self._by_kind[executor.kind] = executor

    def get(self, kind: str) -> Executor:
        try:
            return self._by_kind[kind]
        except KeyError as exc:
            msg = f"No executor registered for kind={kind!r}"
            raise ExecutorNotFoundError(msg) from exc
