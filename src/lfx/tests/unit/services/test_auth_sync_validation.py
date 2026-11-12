"""Synchronous host validation never leaks its execution context."""

import asyncio

import pytest
from lfx.services.auth.service import AuthService
from lfx.services.auth.utils import is_sync_auth_validation


@pytest.mark.parametrize("outcome", ["success", "denied", "canceled"])
async def test_sync_validation_context_is_reset_after_every_exit(outcome):
    auth = AuthService()
    original_loop = asyncio.get_running_loop()
    observed = []

    async def validate():
        observed.append(is_sync_auth_validation())
        assert asyncio.get_running_loop() is not original_loop
        if outcome == "denied":
            msg = "denied"
            raise PermissionError(msg)
        if outcome == "canceled":
            raise asyncio.CancelledError

    assert is_sync_auth_validation() is False
    if outcome == "success":
        auth.run_sync_validation(validate)
    else:
        exception = PermissionError if outcome == "denied" else asyncio.CancelledError
        with pytest.raises(exception):
            auth.run_sync_validation(validate)
    assert observed == [True]
    assert is_sync_auth_validation() is False
    await auth.validate_execution_user(None)
    assert is_sync_auth_validation() is False
