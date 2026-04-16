"""MEAS-01 scenario definitions: lfx_bare, lfx_with_flow, langflow_run."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Scenario:
    """Defines a single cold-start measurement scenario.

    Attributes:
        name: unique scenario identifier (matches key in thresholds.json / baseline sidecar).
        variant: "lean" | "prebaked". Maps to a container image tag via driver._image_tag.
        command: argv-style command list executed inside the container (or host in --mode local).
        env: env vars passed into the container for this scenario.
        runs: hyperfine --min-runs / --max-runs target.
        captures_checkpoints: whether to extract lfx._bench checkpoint JSON.
        captures_pyinstrument: whether to run a pyinstrument capture pass.
        captures_importtime: whether to run a python -X importtime capture pass.
    """

    name: str
    variant: str  # "lean" | "prebaked"
    command: list[str]
    env: dict[str, str] = field(default_factory=dict)
    runs: int = 10
    captures_checkpoints: bool = True
    captures_pyinstrument: bool = True
    captures_importtime: bool = True


__all__ = ["Scenario"]
