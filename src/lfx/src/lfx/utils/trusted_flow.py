"""Marks the packaged first-party flows that Langflow ships and executes itself.

The custom-component and local-file policies exist to constrain *tenant-supplied*
flows. The Langflow Assistant is itself implemented as a flow, shipped inside the
package, and it is loaded through the same seams — so those policies applied to it
too, and it blocked itself.

Scope is deliberately narrow. The marker is bound to the *artifact*, not to "an
assistant request is in flight": the assistant also builds and runs tenant flows
(``run_working_flow``) and its agent carries a FileSystemTool, so a request-scoped
bypass would re-open precisely the code-execution and file-read escapes that
``agentic.helpers.validation`` and ``agentic.services.user_components_overlay``
refuse. Only flows resolved inside the packaged flows directory are marked, and
only ``flow_executor`` does the marking.

The file-access exemption is additionally constrained to the installed package
directory (see ``file_path_security.package_resource_root``), so even while the
marker is live during execution nothing gains the ability to read tenant uploads,
server secrets, or arbitrary server paths — only Langflow's own source.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

_packaged_flow_active: ContextVar[bool] = ContextVar(
    "lfx_packaged_flow_active", default=False
)


def packaged_flow_is_active() -> bool:
    """Whether the caller is inside a packaged first-party flow's load or run."""
    return _packaged_flow_active.get()


@contextmanager
def packaged_flow_scope() -> Iterator[None]:
    """Mark the enclosed load/run as a packaged first-party flow.

    Bind this inside the coroutine or generator body that does the work, not
    around an async generator from the outside: an async generator body runs in
    the context of whoever calls ``__anext__``, so an outer scope would set and
    reset across its suspension points.
    """
    token = _packaged_flow_active.set(True)
    try:
        yield
    finally:
        _packaged_flow_active.reset(token)
