"""Executor abstract base class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from lfx.execution.types import RunComplete, StepResult, Unit


class Executor(ABC):
    kind: ClassVar[str]

    @abstractmethod
    def execute(self, unit: Unit) -> AsyncIterator[StepResult | RunComplete]:
        """Yield StepResult items, end with a RunComplete."""
