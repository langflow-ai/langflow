"""Regression test for webhook SSE real-time event delivery.

Bug: After POST /api/v1/webhook/{flow_id}, the UI's Inspect Output panel never shows
the Webhook build because the SSE endpoint `/api/v1/webhook-events/{flow_id}` was
returning 403 to the frontend subscriber. As a result the frontend `flowPool` stayed
empty and the Inspect Output panel showed "Please build the component first".

Root cause: `get_current_user_for_sse` takes `db: AsyncSession = Depends(...)` as a
default parameter — it is supposed to be invoked as a FastAPI dependency.
`webhook_events_stream` was calling it as a plain function
(`user = await get_current_user_for_sse(request)`), so the `db` argument was the
unresolved `Depends(...)` object instead of an `AsyncSession`. Every auth attempt then
blew up inside the auth service, was wrapped as `InvalidCredentialsError`, and the SSE
endpoint raised 403 for every request.

The regression was introduced in PR #11654 (Pluggable AuthService) when
`get_current_user_for_sse` was refactored from using `async with session_scope() as db`
internally to receiving `db` via FastAPI `Depends(...)`.

Fix: make `webhook_events_stream` resolve `get_current_user_for_sse` through FastAPI
dependency injection so the `db` session is properly provided.
"""

from __future__ import annotations

import asyncio


async def _assert_sse_not_forbidden(client, url: str) -> None:
    """Send a GET with a tight timeout and assert the endpoint does not return 403.

    SSE responses are long-lived, so we can't read the body; instead:
      * 403 response → regression is present (fails fast, before the timeout)
      * TimeoutError → the SSE stream opened (200) and is idle waiting for events
    """
    try:
        response = await asyncio.wait_for(client.get(url), timeout=3.0)
    except asyncio.TimeoutError:
        return

    assert response.status_code != 403, (
        f"SSE endpoint returned 403. Regression: get_current_user_for_sse was "
        "called directly instead of via FastAPI DI, so its `db` parameter was "
        f"a Depends(...) object. Body: {response.text}"
    )


async def test_should_not_return_403_when_accessing_webhook_sse_endpoint_with_valid_api_key(
    client,
    added_webhook_test,
    created_api_key,
):
    """Direct reproduction: SSE must accept `x-api-key` query param."""
    flow_id = added_webhook_test["id"]
    sse_url = f"api/v1/webhook-events/{flow_id}?x-api-key={created_api_key.api_key}"

    await _assert_sse_not_forbidden(client, sse_url)


async def test_should_not_return_403_when_accessing_webhook_sse_endpoint_with_valid_cookie(
    client,
    added_webhook_test,
    active_user,
):
    """SSE must accept `access_token_lf` cookie — the real path used by the browser.

    The frontend's EventSource relies on cookies (not headers or query params) for
    authentication. This test mirrors that exact flow to make sure the fix holds for
    the real end-user scenario.
    """
    login_response = await client.post(
        "api/v1/login",
        data={"username": active_user.username, "password": "testpassword"},
    )
    assert login_response.status_code == 200
    # httpx AsyncClient automatically persists Set-Cookie headers into client.cookies,
    # so subsequent requests will carry access_token_lf.
    assert "access_token_lf" in client.cookies

    flow_id = added_webhook_test["id"]
    sse_url = f"api/v1/webhook-events/{flow_id}"

    await _assert_sse_not_forbidden(client, sse_url)


async def test_should_not_return_403_on_sse_endpoint_when_webhook_auth_enable_is_true(
    client,
    added_webhook_test,
    created_api_key,
):
    """SSE auth is independent of LANGFLOW_WEBHOOK_AUTH_ENABLE.

    `WEBHOOK_AUTH_ENABLE` controls the POST /webhook endpoint (allow/deny public
    execution). It must not interfere with SSE subscription: the SSE endpoint always
    requires a logged-in user who owns the flow, regardless of the flag.
    """
    from langflow.services.deps import get_settings_service

    settings_service = get_settings_service()
    original = settings_service.auth_settings.WEBHOOK_AUTH_ENABLE

    try:
        settings_service.auth_settings.WEBHOOK_AUTH_ENABLE = True

        flow_id = added_webhook_test["id"]
        sse_url = f"api/v1/webhook-events/{flow_id}?x-api-key={created_api_key.api_key}"

        await _assert_sse_not_forbidden(client, sse_url)
    finally:
        settings_service.auth_settings.WEBHOOK_AUTH_ENABLE = original
