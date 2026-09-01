"""Marks the packaged first-party flows that Langflow ships and executes itself.

The custom-component and local-file policies exist to constrain *tenant-supplied*
flows. The Langflow Assistant is itself implemented as a flow, shipped inside the
package, and it is loaded through the same seams — so those policies applied to it
too, and it blocked itself.

Two markers, not one, because the two exemptions need different lifetimes and
conflating them makes the wider one ambient over the narrower one's work:

``packaged_flow_load_scope``
    Wraps graph *construction* only. Exempts the unregistered-component gate,
    which is the whole of the bug. Deliberately closed before the flow runs: the
    assistant builds and runs tenant flows during a turn (``run_working_flow``,
    ``flow_graph_build_check``), and each of those reaches
    ``validate_flow_for_current_settings`` through ``Graph.from_payload``. A
    marker still set at that point would exempt tenant canvas data, which is the
    arbitrary-code-execution safety net that ``graph/base.py`` relies on.

``packaged_flow_run_scope``
    Spans the run, because the packaged flow's Directory node reads its component
    library at execution time. Read by ``file_path_security`` alone, and
    clamped there to the installed package directory for reads only — so even
    though this marker is live while the agent's tools run, nothing gains reach
    over tenant uploads, reserved secret/key/DB files, or arbitrary server paths.

Both are set only by ``flow_executor``, and only for artifacts ``resolve_flow_path``
has confined to the packaged flows directory. Neither is a general escape hatch:
what is exempted depends on which scope is open, and the narrow one does not span
the work the wide one covers.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

_packaged_flow_load: ContextVar[bool] = ContextVar("lfx_packaged_flow_load", default=False)
_packaged_flow_run: ContextVar[bool] = ContextVar("lfx_packaged_flow_run", default=False)


def packaged_flow_load_is_active() -> bool:
    """Whether a packaged first-party flow is being constructed right now."""
    return _packaged_flow_load.get()


def packaged_flow_run_is_active() -> bool:
    """Whether a packaged first-party flow's load or run is in progress."""
    return _packaged_flow_run.get()


@contextmanager
def packaged_flow_load_scope() -> Iterator[None]:
    """Mark graph construction of a packaged first-party flow.

    Keep this as tight as the construction itself. Anything validated while it is
    open is exempted from the component gate, so it must not span the flow's run.
    """
    token = _packaged_flow_load.set(True)
    try:
        yield
    finally:
        _packaged_flow_load.reset(token)


@contextmanager
def packaged_flow_run_scope() -> Iterator[None]:
    """Mark the load and run of a packaged first-party flow, for file access only.

    Bind this inside the coroutine or generator body that does the work, not around
    an async generator from the outside: an async generator body runs in the context
    of whoever calls ``__anext__``, so an outer scope would set and reset across its
    suspension points.
    """
    token = _packaged_flow_run.set(True)
    try:
        yield
    finally:
        _packaged_flow_run.reset(token)
