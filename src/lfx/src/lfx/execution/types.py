"""Value objects for the execution layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Unit:
    graph: Any
    inputs: list[dict[str, Any]] = field(default_factory=list)
    runtime_options: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepResult:
    payload: Any


@dataclass
class RunComplete:
    outputs: list[Any]
