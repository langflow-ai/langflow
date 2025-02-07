import shutil
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
import respx
from langflow.main import create_app
from langflow.services.deps import get_db_service


@pytest.fixture(name="service_override_func")
def custom_service_override_func(monkeypatch, request, load_flows_dir):
    """Override service_override_func to include SSO settings."""

    def _service_override_func():
        from langflow.services.manager import service_manager

        # Clear the services cache to ensure we start fresh
        service_manager.factories.clear()
        service_manager.services.clear()

        # Set up SSO settings before creating the app
        monkeypatch.setenv("LANGFLOW_SSO_ENABLED", "true")
        monkeypatch.setenv("LANGFLOW_SSO_AUTH_URL", "https://fake-sso.com/authorize")
        monkeypatch.setenv("LANGFLOW_SSO_TOKEN_URL", "https://fake-sso.com/token")
        monkeypatch.setenv("LANGFLOW_SSO_USERINFO_URL", "https://fake-sso.com/userinfo")
        monkeypatch.setenv("LANGFLOW_SSO_CLIENT_ID", "fake_client_id")
        monkeypatch.setenv("LANGFLOW_SSO_CLIENT_SECRET", "fake_client_secret")
        monkeypatch.setenv("LANGFLOW_SSO_REDIRECT_URI", "http://testserver/api/v1/sso/callback")

        # Create a temporary database
        db_dir = tempfile.mkdtemp()
        db_path = Path(db_dir) / "test.db"
        monkeypatch.setenv("LANGFLOW_DATABASE_URL", f"sqlite:///{db_path}")
        monkeypatch.setenv("LANGFLOW_AUTO_LOGIN", "false")

        if "load_flows" in request.keywords:
            shutil.copyfile(
                pytest.BASIC_EXAMPLE_PATH, Path(load_flows_dir) / "c54f9130-f2fa-4a3e-b22a-3856d946351b.json"
            )
            monkeypatch.setenv("LANGFLOW_LOAD_FLOWS_PATH", load_flows_dir)
            monkeypatch.setenv("LANGFLOW_AUTO_LOGIN", "true")

        app = create_app()
        db_service = get_db_service()
        db_service.database_url = f"sqlite:///{db_path}"
        db_service.reload_engine()
        return app, db_path

    return _service_override_func


@pytest.mark.asyncio
async def test_sso_login_redirect(client):
    """Tests that the /sso/login endpoint responds with a redirection to the SSO provider.

    Tests that it sets a state cookie for CSRF protection.
    """
    response = await client.get("/api/v1/sso/login", follow_redirects=False)
    assert response.status_code in (302, 307)

    # Verify that the state cookie is set
    sso_state = response.cookies.get("sso_state")
    assert sso_state is not None

    # Parse the redirect URL and validate its query parameters
    redirect_url = response.headers.get("location")
    parsed_url = urlparse(redirect_url)
    assert parsed_url.scheme == "https"
    assert parsed_url.netloc == "fake-sso.com"
    qs = parse_qs(parsed_url.query)
    assert qs.get("client_id") == ["fake_client_id"]
    assert qs.get("response_type") == ["code"]
    assert qs.get("scope") == ["openid profile"]
    assert qs.get("redirect_uri") == ["http://testserver/api/v1/sso/callback"]
    assert qs.get("state") == [sso_state]


@pytest.mark.asyncio
async def test_sso_callback_success(client):
    """Tests a successful SSO callback flow.

    - Mocks the token exchange and userinfo endpoints.
    - Verifies that tokens are generated.
    - Verifies that the login cookies are set.
    """
    fake_state = "fakestate123"
    fake_code = "fakecode123"
    # Set the sso_state cookie manually
    client.cookies.set("sso_state", fake_state)

    with respx.mock(base_url="https://fake-sso.com") as mock:
        # Mock the token exchange endpoint
        mock.post("/token").respond(
            status_code=200,
            json={"access_token": "fake_access_token"},
        )
        # Mock the userinfo endpoint
        mock.get("/userinfo").respond(
            status_code=200,
            json={"sub": "12345", "name": "Test User"},
        )

        response = await client.get(f"/api/v1/sso/callback?code={fake_code}&state={fake_state}")
        assert response.status_code == 200
        tokens = response.json()
        # Check that the returned tokens include at least an access and a refresh token.
        assert "access_token" in tokens
        assert "refresh_token" in tokens

        # Validate that login cookies are now set (access token, refresh token, and API key cookies)
        assert client.cookies.get("access_token_lf") is not None
        assert client.cookies.get("refresh_token_lf") is not None
        assert client.cookies.get("apikey_tkn_lflw") is not None


@pytest.mark.asyncio
async def test_sso_callback_invalid_state(client):
    """Tests state parameter validation in SSO callback.

    Tests that if the query string state does not match the state cookie,
    the endpoint returns an error.
    """
    fake_state = "validstate"
    fake_code = "fakecode123"
    # Set cookie with a valid state but then pass an invalid state in the query parameters
    client.cookies.set("sso_state", fake_state)
    invalid_state = "invalidstate"
    response = await client.get(f"/api/v1/sso/callback?code={fake_code}&state={invalid_state}")
    assert response.status_code == 400
    json_resp = response.json()
    assert "Invalid state parameter" in json_resp.get("detail", "")


@pytest.mark.asyncio
async def test_sso_callback_token_exchange_failure(client):
    """Tests that the endpoint returns an error if the token exchange with the SSO provider fails."""
    fake_state = "fakestate456"
    fake_code = "fakecode456"
    client.cookies.set("sso_state", fake_state)
    with respx.mock(base_url="https://fake-sso.com") as mock:
        # Simulate token exchange failure by returning a 400 error
        mock.post("/token").respond(
            status_code=400,
            json={"error": "invalid_grant"},
        )
        response = await client.get(f"/api/v1/sso/callback?code={fake_code}&state={fake_state}")
        assert response.status_code == 400
        json_resp = response.json()
        assert "Failed to exchange code for token" in json_resp.get("detail", "")


@pytest.mark.asyncio
async def test_sso_disabled(client):
    """Test that SSO endpoints return 400 when SSO is disabled."""
    # Override SSO_ENABLED setting
    from langflow.services.deps import get_settings_service

    auth_settings = get_settings_service().auth_settings
    auth_settings.SSO_ENABLED = False

    # Test /sso/login endpoint
    response = await client.get("/api/v1/sso/login")
    assert response.status_code == 400
    assert response.json()["detail"] == "SSO is not enabled"

    # Test /sso/callback endpoint
    response = await client.get("/api/v1/sso/callback?code=fake&state=fake")
    assert response.status_code == 400
    assert response.json()["detail"] == "SSO is not enabled"


@pytest.mark.asyncio
async def test_sso_callback_missing_code(client):
    """Test that callback fails when code parameter is missing."""
    fake_state = "fakestate123"
    client.cookies.set("sso_state", fake_state)
    response = await client.get(f"/api/v1/sso/callback?state={fake_state}")
    assert response.status_code == 400
    assert "code" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_sso_callback_missing_state_cookie(client):
    """Test that callback fails when state cookie is missing."""
    response = await client.get("/api/v1/sso/callback?code=fake&state=fake")
    assert response.status_code == 400
    assert "state parameter" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_sso_userinfo_failure(client):
    """Test handling of userinfo endpoint failure."""
    fake_state = "fakestate123"
    fake_code = "fakecode123"
    client.cookies.set("sso_state", fake_state)

    with respx.mock(base_url="https://fake-sso.com") as mock:
        # Mock successful token exchange
        mock.post("/token").respond(
            status_code=200,
            json={"access_token": "fake_access_token"},
        )
        # Mock failed userinfo endpoint
        mock.get("/userinfo").respond(status_code=500)

        response = await client.get(f"/api/v1/sso/callback?code={fake_code}&state={fake_state}")
        assert response.status_code == 400
        assert "Failed to fetch user information" in response.json()["detail"]


@pytest.mark.asyncio
async def test_sso_missing_sub_claim(client):
    """Test handling of missing sub claim in userinfo response."""
    fake_state = "fakestate123"
    fake_code = "fakecode123"
    client.cookies.set("sso_state", fake_state)

    with respx.mock(base_url="https://fake-sso.com") as mock:
        mock.post("/token").respond(
            status_code=200,
            json={"access_token": "fake_access_token"},
        )
        # Return userinfo without sub claim
        mock.get("/userinfo").respond(
            status_code=200,
            json={"name": "Test User"},
        )

        response = await client.get(f"/api/v1/sso/callback?code={fake_code}&state={fake_state}")
        assert response.status_code == 400
        assert "subject identifier" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_sso_cookie_security(client):
    """Test that SSO state cookie has proper security attributes."""
    response = await client.get("/api/v1/sso/login", follow_redirects=False)
    assert response.status_code in (302, 307)

    # Check cookie security attributes
    sso_state_cookie = response.cookies.get("sso_state")
    assert sso_state_cookie is not None

    # Cookie should be HttpOnly
    assert "HttpOnly" in response.headers["set-cookie"].lower()

    # In a production environment, these would also be checked:
    # assert "Secure" in response.headers["set-cookie"].lower()
    # assert "SameSite=Strict" in response.headers["set-cookie"]


@pytest.mark.asyncio
async def test_sso_callback_with_profile_info(client):
    """Test that SSO callback properly handles user profile information."""
    fake_state = "fakestate123"
    fake_code = "fakecode123"
    client.cookies.set("sso_state", fake_state)

    test_profile = {"sub": "user123456789", "name": "Test User", "picture": "https://example.com/profile.jpg"}

    with respx.mock(base_url="https://fake-sso.com") as mock:
        mock.post("/token").respond(
            status_code=200,
            json={"access_token": "fake_access_token"},
        )
        mock.get("/userinfo").respond(
            status_code=200,
            json=test_profile,
        )

        response = await client.get(f"/api/v1/sso/callback?code={fake_code}&state={fake_state}")
        assert response.status_code == 200

        # Verify that a second login with the same sub updates the profile
        test_profile["picture"] = "https://example.com/new_profile.jpg"
        mock.get("/userinfo").respond(
            status_code=200,
            json=test_profile,
        )

        response = await client.get(f"/api/v1/sso/callback?code={fake_code}&state={fake_state}")
        assert response.status_code == 200

        # Verify user in database has updated profile
        from langflow.services.deps import get_session

        async with get_session() as db:
            from langflow.services.database.models.user import User
            from sqlmodel import select

            expected_username = "sso_Test User_456789"[:50]  # last 6 chars of the sub
            query = select(User).where(User.username == expected_username)
            result = await db.exec(query)
            user = result.one()
            assert user.profile_image == "https://example.com/new_profile.jpg"


@pytest.mark.asyncio
async def test_sso_callback_minimal_userinfo(client):
    """Test SSO callback with minimal user information (only sub)."""
    fake_state = "fakestate123"
    fake_code = "fakecode123"
    client.cookies.set("sso_state", fake_state)

    with respx.mock(base_url="https://fake-sso.com") as mock:
        mock.post("/token").respond(
            status_code=200,
            json={"access_token": "fake_access_token"},
        )
        # Only provide the required sub claim
        mock.get("/userinfo").respond(
            status_code=200,
            json={"sub": "12345"},
        )

        response = await client.get(f"/api/v1/sso/callback?code={fake_code}&state={fake_state}")
        assert response.status_code == 200

        # Verify user was created with default values
        from langflow.services.deps import get_session

        async with get_session() as db:
            from langflow.services.database.models.user import User
            from sqlmodel import select

            query = select(User).where(User.username == "sso_12345")
            result = await db.exec(query)
            user = result.one()
            assert user.profile_image is None
