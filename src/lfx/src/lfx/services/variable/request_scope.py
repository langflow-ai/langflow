"""Request-scoped variables for lfx serve (and other in-process runners).

TRM/WXO inject credentials via ``global_vars`` on ``POST /flows/{id}/run`` without
mutating process-wide ``os.environ``. This module holds the active request's flat
lookup table in a ContextVar so :class:`~lfx.services.variable.service.VariableService`
can resolve the same names as the ``lfx run`` subprocess path.
"""

from __future__ import annotations

import contextvars
from typing import Any

_request_variables: contextvars.ContextVar[dict[str, str] | None] = contextvars.ContextVar(
    "lfx_request_variables",
    default=None,
)


def get_active_request_variables() -> dict[str, str] | None:
    """Return the current request's variable map, if any."""
    return _request_variables.get()


def activate_request_variables(variables: dict[str, str] | None) -> contextvars.Token[Any]:
    """Bind *variables* for the current async task / thread."""
    return _request_variables.set(variables)


def reset_request_variables(token: contextvars.Token[Any]) -> None:
    """Restore the previous request scope."""
    _request_variables.reset(token)
