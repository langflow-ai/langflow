"""Identity partitioner: one unit per graph."""

from __future__ import annotations

from typing import Any

from lfx.execution.types import Unit


def identity_partition(
    graph: Any,
    *,
    inputs: list[dict[str, Any]],
    runtime_options: dict[str, Any] | None = None,
) -> list[Unit]:
    return [Unit(graph=graph, inputs=inputs, runtime_options=runtime_options or {})]
