"""Request-scoped variables for lfx serve (and other in-process runners).

TRM/WXO inject credentials via ``global_vars`` on ``POST /flows/{id}/run`` without
mutating process-wide ``os.environ``. This module holds the active request's flat
lookup table in a ContextVar so :class:`~lfx.services.variable.service.VariableService`
can resolve the same names as the ``lfx run`` subprocess path.

A second ContextVar mirrors ``graph.context['no_env_fallback']`` so the service can
honor the same "do not read ``os.environ``" contract that ``load_from_env_vars``
enforces for ``load_from_db`` fields — keeping the two resolution paths consistent.
"""

from __future__ import annotations

import contextvars
import json
import os

_request_variables: contextvars.ContextVar[dict[str, str] | None] = contextvars.ContextVar(
    "lfx_request_variables",
    default=None,
)
_no_env_fallback: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "lfx_no_env_fallback",
    default=False,
)


def global_var_alias(name: str) -> str:
    """The ``x-langflow-global-var-*`` name a request may send variable ``name`` under."""
    return f"x-langflow-global-var-{name.lower().replace('_', '-')}"


def variable_name_forms(name: str) -> tuple[str, str, str]:
    """Every name a request may send variable ``name`` under.

    As is; as ``X-LANGFLOW-GLOBAL-VAR-*`` header extraction leaves a dashed header name
    (``OPENAI-API-KEY``); and as the ``x-langflow-global-var-*`` alias that lfx serve keeps.
    """
    return (name, name.replace("_", "-"), global_var_alias(name))


def normalize_parsed_variables(parsed: dict) -> dict[str, str]:
    """Flatten a parsed JSON variable map to ``str`` values.

    Drops ``None`` (so a JSON ``null`` never becomes the truthy string "None" and
    masquerades as a credential) and serializes dict/list values as valid JSON
    (round-trippable via ``json.loads``) rather than a lossy Python repr. Scalars use ``str``.
    """
    return {
        str(key): json.dumps(value) if isinstance(value, dict | list) else str(value)
        for key, value in parsed.items()
        if value is not None
    }


def get_active_request_variables() -> dict[str, str] | None:
    """Return the current request's variable map, if any."""
    return _request_variables.get()


def get_effective_request_variables() -> dict[str, str]:
    """The request's variables: the active scope, else the ``LANGFLOW_REQUEST_VARIABLES`` env JSON.

    Credential lookups and endpoint checks both read this, so a value a check skips can never supply
    a key. The env JSON is a process-wide ``os.environ`` read, so it is skipped when the request
    disables env fallback.
    """
    active = get_active_request_variables()
    if active is not None:
        return active
    if is_env_fallback_disabled():
        return {}
    raw = os.getenv("LANGFLOW_REQUEST_VARIABLES")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = None
    if not isinstance(parsed, dict):
        from lfx.log.logger import logger

        logger.debug("LANGFLOW_REQUEST_VARIABLES must be a JSON object; skipping request-scoped lookup")
        return {}
    return normalize_parsed_variables(parsed)


def is_env_fallback_disabled() -> bool:
    """Return whether the current request forbids falling back to ``os.environ``."""
    return _no_env_fallback.get()


def activate_no_env_fallback(*, disabled: bool) -> contextvars.Token[bool]:
    """Bind the no-env-fallback flag for the current async task / thread."""
    return _no_env_fallback.set(disabled)


def reset_no_env_fallback(token: contextvars.Token[bool]) -> None:
    """Restore the previous no-env-fallback flag."""
    _no_env_fallback.reset(token)


def activate_request_variables(variables: dict[str, str] | None) -> contextvars.Token[dict[str, str] | None]:
    """Bind *variables* for the current async task / thread.

    Pass ``None`` to mean "no active scope" — lookups then fall back to the
    ``LANGFLOW_REQUEST_VARIABLES`` env var. An empty ``{}`` is an *active* empty
    scope that suppresses that env fallback, so callers normalizing an empty
    result should pass ``... or None`` to preserve it.
    """
    return _request_variables.set(variables)


def reset_request_variables(token: contextvars.Token[dict[str, str] | None]) -> None:
    """Restore the previous request scope."""
    _request_variables.reset(token)
