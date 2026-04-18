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
    # When set, the driver runs this command once via hyperfine --setup before the
    # measured iterations, and bind-mounts a shared host tmp dir at /bench-state so
    # state written by the pre-warm survives into every iteration's fresh --rm
    # container. Used by scenarios that need a populated DB or filesystem cache to
    # exercise the cache-hit path (e.g. langflow_run_no_change_restart / SVC-01).
    prewarm_command: list[str] | None = None
    # When True, the scenario's command is the measurement harness itself: it runs
    # the pre-warm, loops internally, and writes a hyperfine-compatible JSON
    # report to $BENCH_OUTPUT_JSON. The driver invokes the command once inside a
    # single container (no hyperfine wrapping) and copies the JSON back to the
    # reports directory. Useful for scenarios where hyperfine's opaque output
    # capture makes CI debugging impossible.
    self_measuring: bool = False


__all__ = ["Scenario"]
