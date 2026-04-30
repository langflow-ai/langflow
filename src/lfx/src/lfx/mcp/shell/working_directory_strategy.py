"""Working-directory isolation strategies.

The shell MCP server is a single process shared by every flow on a
Langflow backend. The default ``shared`` strategy preserves the
existing single-tenant behaviour: every call sees the same configured
``working_directory``. The ``ephemeral`` strategy hands every call its
own ``tempfile.TemporaryDirectory`` rooted under the configured base
and deletes it on release, giving multi-tenant deployments a hard
isolation boundary at zero state cost.

Strategies are picked once at server boot via :func:`build_strategy`
based on ``ShellServerConfig.isolation`` -- the choice is part of the
frozen config so a TOCTOU swap between validation and exec is not
possible.
"""

from __future__ import annotations

import tempfile
from contextlib import contextmanager
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Iterator

    from lfx.mcp.shell.shell_config import IsolationMode


_EPHEMERAL_PREFIX = "lfx-shell-"


@runtime_checkable
class WorkingDirectoryStrategy(Protocol):
    """Strategy contract: produce a working directory for one call.

    ``acquire`` is a context manager so the caller does not have to
    track lifetime separately -- the directory exists for the duration
    of the ``with`` block and is torn down (or kept) per the strategy.
    """

    def acquire(self) -> Iterator[str]:  # pragma: no cover - protocol stub
        ...


class SharedStrategy:
    """Every call yields the same configured base directory.

    Single-tenant default. Files persist between calls; tenants on a
    multi-tenant deployment can read/write each other's data.
    """

    def __init__(self, *, base_directory: str) -> None:
        self._base_directory = base_directory

    @contextmanager
    def acquire(self) -> Iterator[str]:
        yield self._base_directory


class EphemeralStrategy:
    """Every call gets a fresh ``TemporaryDirectory`` under the base.

    The temp directory is deleted when the ``with`` block exits. Two
    parallel calls receive distinct directories, so tenants never see
    each other's files. The cost is that an agent cannot rely on state
    from one call surviving into the next -- which is the right
    default for untrusted agents anyway.
    """

    def __init__(self, *, base_directory: str) -> None:
        self._base_directory = base_directory

    @contextmanager
    def acquire(self) -> Iterator[str]:
        with tempfile.TemporaryDirectory(prefix=_EPHEMERAL_PREFIX, dir=self._base_directory) as path:
            yield path


def build_strategy(mode: IsolationMode, *, base_directory: str) -> WorkingDirectoryStrategy:
    """Materialise the strategy chosen via ``ShellServerConfig.isolation``."""
    # Local import to avoid a cycle: shell_config imports types from
    # this module's neighbour ``shell_constants`` and we want
    # ``working_directory_strategy`` to be importable in isolation.
    from lfx.mcp.shell.shell_config import IsolationMode as _IsolationMode

    if mode is _IsolationMode.EPHEMERAL:
        return EphemeralStrategy(base_directory=base_directory)
    return SharedStrategy(base_directory=base_directory)
