"""Behavioral tests for the unified-model credential resolver.

Covers ``get_api_key_for_provider`` and ``get_all_variables_for_provider`` with a
focus on the no-env-fallback contract: when a served flow disables env fallback,
the resolver must not read process-wide ``os.environ`` credentials, while
request-scoped variables (injected via lfx serve ``global_vars``) must still
resolve through VariableService.

No behavior is mocked. Tests that exercise the VariableService path register the
real minimal ``VariableService`` on the global service manager; environment is
managed with pytest's ``monkeypatch``. The service-path tests are ``async`` so the
call runs inside a live event loop, exercising the ``run_until_complete``
worker-thread hop (and its contextvars propagation) end to end.
"""

from __future__ import annotations

from contextlib import contextmanager

import pytest
from lfx.base.models.unified_models import (
    get_all_variables_for_provider,
    get_api_key_for_provider,
    get_model_provider_variable_mapping,
)
from lfx.services.variable.request_scope import (
    activate_no_env_fallback,
    activate_request_variables,
    reset_no_env_fallback,
    reset_request_variables,
)

_PROVIDER = "OpenAI"
_USER_ID = "11111111-1111-1111-1111-111111111111"
_MISSING = object()


def _primary_var_name() -> str:
    mapping = get_model_provider_variable_mapping()
    assert _PROVIDER in mapping, f"expected {_PROVIDER} in provider mapping: {sorted(mapping)}"
    return mapping[_PROVIDER]


@contextmanager
def _no_env_fallback():
    token = activate_no_env_fallback(disabled=True)
    try:
        yield
    finally:
        reset_no_env_fallback(token)


@contextmanager
def _request_scope(variables: dict[str, str] | None):
    token = activate_request_variables(variables)
    try:
        yield
    finally:
        reset_request_variables(token)


@pytest.fixture
def variable_service_registered():
    """Register the real minimal VariableService on the global manager, then restore.

    Standalone lfx has no VariableService factory, so ``get_variable_service()``
    returns None by default. Registering the genuine service (not a mock) lets the
    credential resolver exercise the request-scoped lookup path for real.
    """
    from lfx.services.manager import get_service_manager
    from lfx.services.schema import ServiceType
    from lfx.services.variable.service import VariableService

    manager = get_service_manager()
    prev_class = manager.service_classes.get(ServiceType.VARIABLE_SERVICE, _MISSING)
    prev_instance = manager.services.get(ServiceType.VARIABLE_SERVICE, _MISSING)

    manager.register_service_class(ServiceType.VARIABLE_SERVICE, VariableService, override=True)
    manager.services.pop(ServiceType.VARIABLE_SERVICE, None)  # force a fresh instance
    try:
        yield
    finally:
        manager.services.pop(ServiceType.VARIABLE_SERVICE, None)
        manager.service_classes.pop(ServiceType.VARIABLE_SERVICE, None)
        if prev_class is not _MISSING:
            manager.service_classes[ServiceType.VARIABLE_SERVICE] = prev_class
        if prev_instance is not _MISSING:
            manager.services[ServiceType.VARIABLE_SERVICE] = prev_instance


# ---------------------------------------------------------------------------
# get_api_key_for_provider — env gating (no VariableService, == standalone lfx)
# ---------------------------------------------------------------------------


def test_literal_key_returned_as_is_regardless_of_flag():
    """A literal key (not an env-var name) is returned verbatim, flag on or off."""
    literal = "sk-literal-abc1234567890"
    assert get_api_key_for_provider(None, _PROVIDER, literal) == literal
    with _no_env_fallback():
        assert get_api_key_for_provider(None, _PROVIDER, literal) == literal


def test_primary_key_resolves_from_env_by_default(monkeypatch):
    """No api_key + env fallback enabled: the canonical provider var resolves from os.environ."""
    monkeypatch.setenv(_primary_var_name(), "sk-env")
    assert get_api_key_for_provider(None, _PROVIDER, None) == "sk-env"


def test_primary_key_env_suppressed_under_no_env_fallback(monkeypatch):
    """No api_key + env fallback disabled: the os.getenv read is skipped -> None."""
    monkeypatch.setenv(_primary_var_name(), "sk-env")
    with _no_env_fallback():
        assert get_api_key_for_provider(None, _PROVIDER, None) is None


def test_named_variable_resolves_from_env_by_default(monkeypatch):
    """api_key given as an env-var NAME resolves that name from os.environ."""
    monkeypatch.setenv("MY_OPENAI_KEY", "sk-resolved")
    assert get_api_key_for_provider(None, _PROVIDER, "MY_OPENAI_KEY") == "sk-resolved"


def test_named_variable_env_suppressed_under_no_env_fallback(monkeypatch):
    """Env-var-name api_key + fallback disabled + no user: env skipped, unresolved -> None."""
    monkeypatch.setenv("MY_OPENAI_KEY", "sk-resolved")
    with _no_env_fallback():
        # No user_id -> service not consulted; all-caps name resolves to None when unresolved.
        assert get_api_key_for_provider(None, _PROVIDER, "MY_OPENAI_KEY") is None


def test_unknown_provider_returns_none():
    """A provider with no variable mapping yields None (no env read attempted)."""
    assert get_api_key_for_provider(None, "NoSuchProvider", None) is None


# ---------------------------------------------------------------------------
# get_all_variables_for_provider — env gating (no user_id branch)
# ---------------------------------------------------------------------------


def test_get_all_variables_resolves_env_by_default(monkeypatch):
    """No user_id + env fallback enabled: provider vars are read from os.environ."""
    monkeypatch.setenv(_primary_var_name(), "sk-env")
    result = get_all_variables_for_provider(None, _PROVIDER)
    assert result.get(_primary_var_name()) == "sk-env"


def test_get_all_variables_unknown_provider_returns_empty():
    """A provider with no variables yields an empty dict."""
    assert get_all_variables_for_provider(None, "NoSuchProvider") == {}


def test_env_if_allowed_gates_connection_config(monkeypatch):
    """instantiation._env_if_allowed (used for provider URLs/IDs/headers) honors the flag."""
    from lfx.base.models.unified_models.instantiation import _env_if_allowed

    monkeypatch.setenv("WATSONX_URL", "https://env.example")
    assert _env_if_allowed("WATSONX_URL") == "https://env.example"
    with _no_env_fallback():
        assert _env_if_allowed("WATSONX_URL") is None


# ---------------------------------------------------------------------------
# VariableService path — request-scope resolution + precedence (real service)
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("variable_service_registered")
async def test_request_scope_resolves_under_no_env_fallback(monkeypatch):
    """Flag on + request scope set: the resolver returns the request credential, never env."""
    var = _primary_var_name()
    monkeypatch.setenv(var, "sk-env-must-not-win")
    with _no_env_fallback(), _request_scope({var: "sk-from-request"}):
        # Async context -> run_until_complete takes the thread-hop branch; the request
        # scope must survive into the worker thread (contextvars propagation).
        assert get_api_key_for_provider(_USER_ID, _PROVIDER, None) == "sk-from-request"


@pytest.mark.usefixtures("variable_service_registered")
async def test_request_scope_wins_over_env_on_primary_path(monkeypatch):
    """Primary path checks VariableService before os.environ, so request scope wins (flag off)."""
    var = _primary_var_name()
    monkeypatch.setenv(var, "sk-env")
    with _request_scope({var: "sk-from-request"}):
        assert get_api_key_for_provider(_USER_ID, _PROVIDER, None) == "sk-from-request"


@pytest.mark.usefixtures("variable_service_registered")
async def test_named_variable_resolves_from_request_scope_under_no_env_fallback(monkeypatch):
    """Named-variable path + flag on: env skipped, request scope resolves the name."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-must-not-win")
    with _no_env_fallback(), _request_scope({"OPENAI_API_KEY": "sk-from-request"}):
        assert get_api_key_for_provider(_USER_ID, _PROVIDER, "OPENAI_API_KEY") == "sk-from-request"


@pytest.mark.usefixtures("variable_service_registered")
async def test_named_variable_request_scope_precedes_env_when_fallback_enabled(monkeypatch):
    """Documents current precedence: for an explicitly-named var, VariableService is read first.

    Mirrors the primary path — ``_resolve_var_name`` consults VariableService (where the
    user's encrypted global variable, and the request scope it rides on, live) before
    ``os.environ``, so the request-scoped credential wins even with env fallback enabled.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
    with _request_scope({"OPENAI_API_KEY": "sk-from-request"}):
        assert get_api_key_for_provider(_USER_ID, _PROVIDER, "OPENAI_API_KEY") == "sk-from-request"


@pytest.mark.usefixtures("variable_service_registered")
async def test_get_all_variables_resolves_request_scope_under_no_env_fallback(monkeypatch):
    """Flag on + user_id + request scope: provider vars come from the request, not env."""
    var = _primary_var_name()
    monkeypatch.setenv(var, "sk-env-must-not-win")
    with _no_env_fallback(), _request_scope({var: "sk-from-request"}):
        result = get_all_variables_for_provider(_USER_ID, _PROVIDER)
    assert result == {var: "sk-from-request"}
