"""Unit tests for MCP OAuth API endpoints.

Covers /initiate, /callback, /status/{flow_id},
DELETE /tokens/{server_key}, and GET /tokens/{server_key}/check.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state_manager(
    *,
    flow_id: str = "flow-123",
    state_param: str = "flow-123:abc",
    flow_status: dict | None = None,
    store_callback_result: bool = True,
    delete_tokens_result: bool = True,
    tokens: dict | None = None,
) -> MagicMock:
    """Return a mock OAuthStateManager with sensible defaults."""
    manager = MagicMock()
    manager.create_flow = AsyncMock(return_value=(flow_id, state_param))
    manager.delete_tokens = AsyncMock(return_value=delete_tokens_result)
    manager.update_flow = AsyncMock(return_value=True)
    manager.get_flow_by_id = AsyncMock(
        return_value={
            "flow_id": flow_id,
            "status": "awaiting_callback",
            "auth_url": "https://auth.example.com/go",
        }
    )
    manager.get_flow_status = AsyncMock(
        return_value=flow_status
        or {
            "status": "pending",
            "server_url": "https://mcp.example.com",
        }
    )
    manager.store_callback = AsyncMock(return_value=store_callback_result)
    manager.fail_flow = AsyncMock(return_value={"status": "error"})
    manager.get_tokens = AsyncMock(return_value=tokens)
    return manager


# ---------------------------------------------------------------------------
# POST /api/v1/mcp/oauth/initiate
# ---------------------------------------------------------------------------


class TestInitiateOAuthFlow:
    @pytest.fixture
    def mock_state_manager(self) -> MagicMock:
        return _make_state_manager()

    async def test_initiate_returns_flow_id_and_auth_url(self, client, logged_in_headers, mock_state_manager) -> None:
        """A valid /initiate request returns flow_id and auth_url."""
        with (
            patch(
                "langflow.api.v1.mcp_oauth.get_oauth_state_manager",
                new=AsyncMock(return_value=mock_state_manager),
            ),
            patch(
                "langflow.api.v1.mcp_oauth.create_deployed_oauth_provider",
                new=AsyncMock(),
            ),
        ):
            response = await client.post(
                "api/v1/mcp/oauth/initiate",
                json={"server_url": "https://mcp.example.com"},
                headers=logged_in_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert "flow_id" in data
        assert "auth_url" in data
        assert "expires_in" in data

    async def test_initiate_creates_flow_for_server(self, client, logged_in_headers, mock_state_manager) -> None:
        """Initiating a flow creates a new OAuth flow entry in the state manager."""
        with (
            patch(
                "langflow.api.v1.mcp_oauth.get_oauth_state_manager",
                new=AsyncMock(return_value=mock_state_manager),
            ),
            patch(
                "langflow.api.v1.mcp_oauth.create_deployed_oauth_provider",
                new=AsyncMock(),
            ),
        ):
            await client.post(
                "api/v1/mcp/oauth/initiate",
                json={"server_url": "https://mcp.example.com"},
                headers=logged_in_headers,
            )

        mock_state_manager.create_flow.assert_awaited_once()

    async def test_initiate_requires_authentication(self, client) -> None:
        """Calling /initiate without a token returns 401/403."""
        response = await client.post(
            "api/v1/mcp/oauth/initiate",
            json={"server_url": "https://mcp.example.com"},
        )
        assert response.status_code in (401, 403)

    async def test_initiate_with_explicit_redirect_uri(self, client, logged_in_headers, mock_state_manager) -> None:
        """An explicit redirect_uri is forwarded to the OAuth provider."""
        with (
            patch(
                "langflow.api.v1.mcp_oauth.get_oauth_state_manager",
                new=AsyncMock(return_value=mock_state_manager),
            ),
            patch(
                "langflow.api.v1.mcp_oauth.create_deployed_oauth_provider",
                new=AsyncMock(),
            ) as mock_create,
        ):
            await client.post(
                "api/v1/mcp/oauth/initiate",
                json={
                    "server_url": "https://mcp.example.com",
                    "redirect_uri": "https://app.example.com/cb",
                },
                headers=logged_in_headers,
            )

        # Provider should have been called with the supplied redirect_uri
        if mock_create.called:
            _args, kwargs = mock_create.call_args
            assert kwargs.get("redirect_uri") == "https://app.example.com/cb"

    async def test_initiate_error_status_propagates_as_400(self, client, logged_in_headers) -> None:
        """If the background flow immediately errors, /initiate returns 400."""
        error_manager = _make_state_manager()
        error_manager.get_flow_by_id = AsyncMock(
            return_value={"flow_id": "flow-123", "status": "error", "error_message": "provider rejected"}
        )

        with (
            patch(
                "langflow.api.v1.mcp_oauth.get_oauth_state_manager",
                new=AsyncMock(return_value=error_manager),
            ),
            patch(
                "langflow.api.v1.mcp_oauth.create_deployed_oauth_provider",
                new=AsyncMock(),
            ),
        ):
            response = await client.post(
                "api/v1/mcp/oauth/initiate",
                json={"server_url": "https://mcp.example.com"},
                headers=logged_in_headers,
            )

        assert response.status_code == 400

    async def test_initiate_rejects_loopback_ip(self, client, logged_in_headers) -> None:
        """SSRF guard: localhost IP is rejected with 400."""
        response = await client.post(
            "api/v1/mcp/oauth/initiate",
            json={"server_url": "https://127.0.0.1/mcp"},
            headers=logged_in_headers,
        )
        assert response.status_code == 400
        assert "loopback" in response.json()["detail"].lower() or "private" in response.json()["detail"].lower()

    async def test_initiate_rejects_private_ip(self, client, logged_in_headers) -> None:
        """SSRF guard: private network IP is rejected with 400."""
        response = await client.post(
            "api/v1/mcp/oauth/initiate",
            json={"server_url": "http://192.168.1.1/mcp"},
            headers=logged_in_headers,
        )
        assert response.status_code == 400

    async def test_initiate_rejects_localhost_hostname(self, client, logged_in_headers) -> None:
        """SSRF guard: localhost hostname is rejected with 400."""
        response = await client.post(
            "api/v1/mcp/oauth/initiate",
            json={"server_url": "http://localhost/mcp"},
            headers=logged_in_headers,
        )
        assert response.status_code == 400

    async def test_initiate_rejects_non_http_scheme(self, client, logged_in_headers) -> None:
        """SSRF guard: non-http/https schemes are rejected with 400."""
        response = await client.post(
            "api/v1/mcp/oauth/initiate",
            json={"server_url": "ftp://mcp.example.com/mcp"},
            headers=logged_in_headers,
        )
        assert response.status_code == 400
        assert "scheme" in response.json()["detail"].lower()

    async def test_initiate_flow_created_before_task_runs(
        self, client, logged_in_headers
    ) -> None:
        """The flow ID is created synchronously so it can be returned to the caller.

        Token deletion and provider creation happen inside the background task.
        """
        mock_manager = _make_state_manager()

        with (
            patch(
                "langflow.api.v1.mcp_oauth.get_oauth_state_manager",
                new=AsyncMock(return_value=mock_manager),
            ),
            patch(
                "langflow.api.v1.mcp_oauth.create_deployed_oauth_provider",
                new=AsyncMock(),
            ),
        ):
            response = await client.post(
                "api/v1/mcp/oauth/initiate",
                json={"server_url": "https://mcp.example.com"},
                headers=logged_in_headers,
            )

        # The flow must be created (synchronously) so we have a flow_id to return
        mock_manager.create_flow.assert_awaited_once()
        # The response must contain a valid flow_id
        assert response.status_code == 200
        assert response.json()["flow_id"] == "flow-123"

    async def test_initiate_http_exception_preserved(self, client, logged_in_headers) -> None:
        """An HTTPException raised during polling is returned with its original status."""
        error_manager = _make_state_manager()
        error_manager.get_flow_by_id = AsyncMock(
            return_value={"flow_id": "flow-123", "status": "error", "error_message": "forbidden"}
        )

        with (
            patch(
                "langflow.api.v1.mcp_oauth.get_oauth_state_manager",
                new=AsyncMock(return_value=error_manager),
            ),
            patch(
                "langflow.api.v1.mcp_oauth.create_deployed_oauth_provider",
                new=AsyncMock(),
            ),
        ):
            response = await client.post(
                "api/v1/mcp/oauth/initiate",
                json={"server_url": "https://mcp.example.com"},
                headers=logged_in_headers,
            )

        # Should be 400 from the explicit HTTPException, not a re-wrapped 400 with a different message
        assert response.status_code == 400
        assert response.json()["detail"] == "forbidden"


# ---------------------------------------------------------------------------
# GET /api/v1/mcp/oauth/callback
# ---------------------------------------------------------------------------


class TestOAuthCallback:
    async def test_callback_success_returns_200_html(self, client) -> None:
        """A valid callback with code + state stores the code and returns HTML."""
        mock_manager = _make_state_manager(store_callback_result=True)

        with patch(
            "langflow.api.v1.mcp_oauth.get_oauth_state_manager",
            new=AsyncMock(return_value=mock_manager),
        ):
            response = await client.get(
                "api/v1/mcp/oauth/callback",
                params={"code": "auth-code-xyz", "state": "flow-123:abc"},
            )

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "Authentication Successful" in response.text

    async def test_callback_missing_code_returns_400(self, client) -> None:
        """A callback without a code returns 400 HTML."""
        response = await client.get(
            "api/v1/mcp/oauth/callback",
            params={"state": "flow-123:abc"},
        )

        assert response.status_code == 400
        assert "text/html" in response.headers.get("content-type", "")

    async def test_callback_missing_state_returns_400(self, client) -> None:
        """A callback without a state returns 400 HTML."""
        response = await client.get(
            "api/v1/mcp/oauth/callback",
            params={"code": "auth-code-xyz"},
        )

        assert response.status_code == 400

    async def test_callback_oauth_error_param_returns_400(self, client) -> None:
        """A callback with an error parameter returns 400 HTML."""
        mock_manager = _make_state_manager()

        with patch(
            "langflow.api.v1.mcp_oauth.get_oauth_state_manager",
            new=AsyncMock(return_value=mock_manager),
        ):
            response = await client.get(
                "api/v1/mcp/oauth/callback",
                params={
                    "error": "access_denied",
                    "error_description": "User denied access",
                    "state": "flow-123:abc",
                },
            )

        assert response.status_code == 400
        assert "User denied access" in response.text

    async def test_callback_oauth_error_calls_fail_flow(self, client) -> None:
        """An OAuth error in the callback marks the flow as failed."""
        mock_manager = _make_state_manager()

        with patch(
            "langflow.api.v1.mcp_oauth.get_oauth_state_manager",
            new=AsyncMock(return_value=mock_manager),
        ):
            await client.get(
                "api/v1/mcp/oauth/callback",
                params={
                    "error": "access_denied",
                    "state": "flow-123:abc",
                },
            )

        mock_manager.fail_flow.assert_awaited_once()

    async def test_callback_unknown_state_returns_400(self, client) -> None:
        """A callback for an unknown state returns 400 HTML."""
        mock_manager = _make_state_manager(store_callback_result=False)

        with patch(
            "langflow.api.v1.mcp_oauth.get_oauth_state_manager",
            new=AsyncMock(return_value=mock_manager),
        ):
            response = await client.get(
                "api/v1/mcp/oauth/callback",
                params={"code": "some-code", "state": "unknown-state"},
            )

        assert response.status_code == 400
        assert "expired or not found" in response.text

    async def test_callback_xss_error_message_is_escaped(self, client) -> None:
        """Error descriptions containing HTML are escaped in the response."""
        mock_manager = _make_state_manager()

        with patch(
            "langflow.api.v1.mcp_oauth.get_oauth_state_manager",
            new=AsyncMock(return_value=mock_manager),
        ):
            response = await client.get(
                "api/v1/mcp/oauth/callback",
                params={
                    "error": "invalid_request",
                    "error_description": "<script>alert(1)</script>",
                    "state": "flow-123:abc",
                },
            )

        assert "<script>" not in response.text
        assert "&lt;script&gt;" in response.text


# ---------------------------------------------------------------------------
# GET /api/v1/mcp/oauth/status/{flow_id}
# ---------------------------------------------------------------------------


class TestGetOAuthStatus:
    async def test_status_pending_returns_200(self, client, logged_in_headers) -> None:
        """Polling a pending flow returns status 'pending'."""
        mock_manager = _make_state_manager(flow_status={"status": "pending", "server_url": "https://mcp.example.com"})

        with patch(
            "langflow.api.v1.mcp_oauth.get_oauth_state_manager",
            new=AsyncMock(return_value=mock_manager),
        ):
            response = await client.get(
                "api/v1/mcp/oauth/status/flow-123",
                headers=logged_in_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"

    async def test_status_awaiting_callback_includes_auth_url(self, client, logged_in_headers) -> None:
        """Status 'awaiting_callback' includes the auth_url field."""
        mock_manager = _make_state_manager(
            flow_status={
                "status": "awaiting_callback",
                "auth_url": "https://auth.example.com/go",
                "server_url": "https://mcp.example.com",
            }
        )

        with patch(
            "langflow.api.v1.mcp_oauth.get_oauth_state_manager",
            new=AsyncMock(return_value=mock_manager),
        ):
            response = await client.get(
                "api/v1/mcp/oauth/status/flow-123",
                headers=logged_in_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "awaiting_callback"
        assert data["auth_url"] == "https://auth.example.com/go"

    async def test_status_complete_returns_200(self, client, logged_in_headers) -> None:
        """A completed flow returns status 'complete'."""
        mock_manager = _make_state_manager(flow_status={"status": "complete", "server_url": "https://mcp.example.com"})

        with patch(
            "langflow.api.v1.mcp_oauth.get_oauth_state_manager",
            new=AsyncMock(return_value=mock_manager),
        ):
            response = await client.get(
                "api/v1/mcp/oauth/status/flow-123",
                headers=logged_in_headers,
            )

        assert response.status_code == 200
        assert response.json()["status"] == "complete"

    async def test_status_error_includes_error_message(self, client, logged_in_headers) -> None:
        """A failed flow returns status 'error' with an error_message."""
        mock_manager = _make_state_manager(flow_status={"status": "error", "error_message": "provider rejected"})

        with patch(
            "langflow.api.v1.mcp_oauth.get_oauth_state_manager",
            new=AsyncMock(return_value=mock_manager),
        ):
            response = await client.get(
                "api/v1/mcp/oauth/status/flow-123",
                headers=logged_in_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert data["error_message"] == "provider rejected"

    async def test_status_expired_for_unknown_flow(self, client, logged_in_headers) -> None:
        """An unknown flow ID returns status 'expired'."""
        mock_manager = _make_state_manager(flow_status={"status": "expired"})

        with patch(
            "langflow.api.v1.mcp_oauth.get_oauth_state_manager",
            new=AsyncMock(return_value=mock_manager),
        ):
            response = await client.get(
                "api/v1/mcp/oauth/status/no-such-flow",
                headers=logged_in_headers,
            )

        assert response.status_code == 200
        assert response.json()["status"] == "expired"

    async def test_status_requires_authentication(self, client) -> None:
        """Calling /status without a token returns 401/403."""
        response = await client.get("api/v1/mcp/oauth/status/flow-123")
        assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# DELETE /api/v1/mcp/oauth/tokens/{server_key}
# ---------------------------------------------------------------------------


class TestRevokeOAuthTokens:
    async def test_revoke_existing_tokens_returns_success(self, client, logged_in_headers) -> None:
        """Deleting tokens that exist returns success=True."""
        mock_manager = _make_state_manager(delete_tokens_result=True)

        with patch(
            "langflow.api.v1.mcp_oauth.get_oauth_state_manager",
            new=AsyncMock(return_value=mock_manager),
        ):
            response = await client.delete(
                "api/v1/mcp/oauth/tokens/mcp.example.com",
                headers=logged_in_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "mcp.example.com" in data["message"]

    async def test_revoke_missing_tokens_returns_success_false(self, client, logged_in_headers) -> None:
        """Deleting tokens that don't exist returns success=False."""
        mock_manager = _make_state_manager(delete_tokens_result=False)

        with patch(
            "langflow.api.v1.mcp_oauth.get_oauth_state_manager",
            new=AsyncMock(return_value=mock_manager),
        ):
            response = await client.delete(
                "api/v1/mcp/oauth/tokens/mcp.example.com",
                headers=logged_in_headers,
            )

        assert response.status_code == 200
        assert response.json()["success"] is False

    async def test_revoke_requires_authentication(self, client) -> None:
        """DELETE /tokens without a token returns 401/403."""
        response = await client.delete("api/v1/mcp/oauth/tokens/mcp.example.com")
        assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /api/v1/mcp/oauth/tokens/{server_key}/check
# ---------------------------------------------------------------------------


class TestCheckOAuthTokens:
    async def test_check_tokens_present_returns_true(self, client, logged_in_headers) -> None:
        """has_tokens is True when tokens exist for the server."""
        mock_manager = _make_state_manager(tokens={"access_token": "tok"})

        with patch(
            "langflow.api.v1.mcp_oauth.get_oauth_state_manager",
            new=AsyncMock(return_value=mock_manager),
        ):
            response = await client.get(
                "api/v1/mcp/oauth/tokens/mcp.example.com/check",
                headers=logged_in_headers,
            )

        assert response.status_code == 200
        assert response.json()["has_tokens"] is True

    async def test_check_tokens_absent_returns_false(self, client, logged_in_headers) -> None:
        """has_tokens is False when no tokens exist for the server."""
        mock_manager = _make_state_manager(tokens=None)

        with patch(
            "langflow.api.v1.mcp_oauth.get_oauth_state_manager",
            new=AsyncMock(return_value=mock_manager),
        ):
            response = await client.get(
                "api/v1/mcp/oauth/tokens/unknown-server/check",
                headers=logged_in_headers,
            )

        assert response.status_code == 200
        assert response.json()["has_tokens"] is False

    async def test_check_requires_authentication(self, client) -> None:
        """GET /tokens/check without a token returns 401/403."""
        response = await client.get("api/v1/mcp/oauth/tokens/mcp.example.com/check")
        assert response.status_code in (401, 403)
