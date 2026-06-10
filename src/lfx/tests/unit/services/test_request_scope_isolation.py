"""Isolation guarantees for request-scoped variables (lfx serve concurrency).

These tests verify the two properties that matter for running multiple flows in a
single ``lfx serve`` process:

1. **Per-request isolation** - one request's ``global_vars`` must never be visible
   to a concurrently-running request. This is provided by the ContextVar in
   :mod:`lfx.services.variable.request_scope`: each asyncio task gets its own
   context copy, so activating a scope in one task cannot leak into another.
2. **No accidental env fallback for supplied credentials** - when a request scope
   provides a variable, resolution must use it and must not consult ``os.environ``
   for that name (so a stale/foreign env var can never shadow a request credential).
"""

from __future__ import annotations

import asyncio
import os
from unittest.mock import patch

from lfx.services.variable.request_scope import (
    activate_no_env_fallback,
    activate_request_variables,
    get_active_request_variables,
    reset_no_env_fallback,
    reset_request_variables,
)
from lfx.services.variable.service import VariableService


async def test_concurrent_request_scopes_are_isolated():
    """Two concurrent requests each see only their own request-scoped variable."""
    service = VariableService()
    observed: dict[str, str | None] = {}

    async def handle(request_id: str, secret: str) -> None:
        token = activate_request_variables({"access_token": secret})
        try:
            # Yield so the sibling task activates its own scope before we read;
            # if the ContextVar leaked across tasks this read would see it.
            await asyncio.sleep(0.01)
            observed[request_id] = await service.get_variable("access_token")
            # Read again after another yield to catch any cross-task overwrite.
            await asyncio.sleep(0.01)
            observed[f"{request_id}-recheck"] = await service.get_variable("access_token")
        finally:
            reset_request_variables(token)

    await asyncio.gather(handle("A", "secret-A"), handle("B", "secret-B"))

    assert observed["A"] == "secret-A"
    assert observed["A-recheck"] == "secret-A"
    assert observed["B"] == "secret-B"
    assert observed["B-recheck"] == "secret-B"


async def test_unscoped_request_does_not_see_a_concurrent_scope():
    """A request with no active scope must not observe another request's live scope."""
    service = VariableService()
    scope_active = asyncio.Event()
    scope_may_exit = asyncio.Event()
    observed: dict[str, str | None] = {}

    async def scoped() -> None:
        token = activate_request_variables({"access_token": "secret-A"})
        try:
            scope_active.set()
            await scope_may_exit.wait()  # hold the scope open while the other task reads
        finally:
            reset_request_variables(token)

    async def unscoped() -> None:
        await scope_active.wait()  # read while scoped()'s scope is definitely active
        observed["value"] = await service.get_variable("access_token")
        scope_may_exit.set()

    await asyncio.gather(scoped(), unscoped())

    assert observed["value"] is None


async def test_scope_does_not_leak_after_reset():
    """After reset, the variable is no longer resolvable (request teardown is clean)."""
    service = VariableService()

    token = activate_request_variables({"access_token": "secret"})
    assert await service.get_variable("access_token") == "secret"
    reset_request_variables(token)

    assert get_active_request_variables() is None
    assert await service.get_variable("access_token") is None


async def test_scoped_value_used_without_consulting_env_for_that_name():
    """A request-supplied variable is returned without falling back to os.environ.

    Guards against a regression where the env tier runs first (or in addition),
    which would let a process env var shadow a per-request credential.
    """
    service = VariableService()
    token = activate_request_variables({"access_token": "from-request"})
    with (
        patch.dict(os.environ, {"access_token": "from-env"}),
        patch("lfx.services.variable.service.os.getenv") as mock_getenv,
    ):
        try:
            assert await service.get_variable("access_token") == "from-request"
        finally:
            reset_request_variables(token)

    name_lookups = [c for c in mock_getenv.call_args_list if c.args and c.args[0] == "access_token"]
    assert not name_lookups, f"os.getenv('access_token') must not be consulted, got: {name_lookups}"


async def test_env_fallback_enabled_by_default():
    """Without the no-env-fallback flag, env resolution still works (default preserved)."""
    service = VariableService()
    with patch.dict(os.environ, {"DEFAULT_SECRET": "from-env"}):
        assert await service.get_variable("DEFAULT_SECRET") == "from-env"


async def test_no_env_fallback_suppresses_env_in_variable_service():
    """With env fallback disabled, a variable only in os.environ resolves to None.

    Closes the gap where VariableService (model/KB credential path) ignored
    ``no_env_fallback`` and leaked process env credentials even under --no-env-fallback.
    """
    service = VariableService()
    scope_token = activate_request_variables({"access_token": "from-request"})
    flag_token = activate_no_env_fallback(disabled=True)
    with (
        patch.dict(os.environ, {"OTHER_SECRET": "from-env"}),
        patch("lfx.services.variable.service.os.getenv") as mock_getenv,
    ):
        try:
            # Supplied via the request scope -> still resolves.
            assert await service.get_variable("access_token") == "from-request"
            # Only in process env -> must NOT resolve when fallback is disabled.
            assert await service.get_variable("OTHER_SECRET") is None
        finally:
            reset_no_env_fallback(flag_token)
            reset_request_variables(scope_token)

    assert not mock_getenv.call_args_list, f"os.getenv must not be consulted, got: {mock_getenv.call_args_list}"


async def test_no_env_fallback_suppresses_langflow_request_variables_env():
    """Env fallback disabled + no active scope must not leak the process LANGFLOW_REQUEST_VARIABLES blob.

    Regression: _get_request_variables() read os.getenv("LANGFLOW_REQUEST_VARIABLES")
    before the no-env-fallback gate, so an empty-global_vars request under
    --no-env-fallback (which binds the scope to None) still resolved credentials
    from the process env blob, violating the "never reads os.environ" contract.
    """
    service = VariableService()
    scope_token = activate_request_variables(None)  # None == empty global_vars in serve
    flag_token = activate_no_env_fallback(disabled=True)
    with patch.dict(os.environ, {"LANGFLOW_REQUEST_VARIABLES": '{"leaked_token": "SHOULD-NOT-LEAK"}'}):
        try:
            assert await service.get_variable("leaked_token") is None
        finally:
            reset_no_env_fallback(flag_token)
            reset_request_variables(scope_token)


async def test_langflow_request_variables_env_blob_used_when_fallback_enabled():
    """Env blob resolves when fallback is enabled: null dropped, structured -> valid JSON string."""
    service = VariableService()
    scope_token = activate_request_variables(None)
    blob = '{"shared_token": "from-env-blob", "null_cred": null, "nested": {"a": 1}}'
    with patch.dict(os.environ, {"LANGFLOW_REQUEST_VARIABLES": blob}):
        try:
            assert await service.get_variable("shared_token") == "from-env-blob"
            # null is dropped (not the truthy string "None"); env/None fallthrough -> None.
            assert await service.get_variable("null_cred") is None
            # Structured value serialized as valid JSON, round-trippable via json.loads.
            assert await service.get_variable("nested") == '{"a": 1}'
        finally:
            reset_request_variables(scope_token)


async def test_no_env_fallback_flag_is_isolated_per_request():
    """The no-env-fallback flag is per-request.

    One request disabling it must not affect a concurrent request that allows
    env fallback.
    """
    service = VariableService()
    observed: dict[str, str | None] = {}

    async def strict_request() -> None:
        # Active (non-None) scope so resolution never reads LANGFLOW_REQUEST_VARIABLES.
        scope = activate_request_variables({"unused": "x"})
        flag = activate_no_env_fallback(disabled=True)
        try:
            await asyncio.sleep(0.01)  # let the lenient request run concurrently
            observed["strict"] = await service.get_variable("SHARED_ENV")
        finally:
            reset_no_env_fallback(flag)
            reset_request_variables(scope)

    async def lenient_request() -> None:
        scope = activate_request_variables({"unused": "y"})
        flag = activate_no_env_fallback(disabled=False)
        try:
            await asyncio.sleep(0.01)
            observed["lenient"] = await service.get_variable("SHARED_ENV")
        finally:
            reset_no_env_fallback(flag)
            reset_request_variables(scope)

    with patch.dict(os.environ, {"SHARED_ENV": "from-env"}):
        await asyncio.gather(strict_request(), lenient_request())

    assert observed["strict"] is None  # env fallback disabled for this request
    assert observed["lenient"] == "from-env"  # env fallback allowed for this request
