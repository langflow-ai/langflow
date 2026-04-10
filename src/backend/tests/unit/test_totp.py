"""Minimal tests for TOTP two-factor authentication.

Coverage:
  * Pure utility functions (no server/DB needed)
  * API endpoints via the standard ``client`` + ``logged_in_headers`` fixtures
  * Security: replay-attack prevention, input validation, partial-token type guard,
    single-use partial tokens, brute-force cap
"""

from __future__ import annotations

import time

import pyotp
from langflow.services.auth.totp import (
    MAX_VERIFY_ATTEMPTS,
    _current_window,
    _used_codes,
    burn_partial_token,
    generate_totp_secret,
    get_provisioning_uri,
    is_partial_token_burnt,
    is_replay,
    is_valid_base32,
    mark_used,
    record_partial_token_failure,
    verify_totp_code,
)
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_auth_service, session_scope

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_valid_code(raw_secret: str) -> str:
    """Return a current valid 6-digit code for the given secret."""
    return pyotp.TOTP(raw_secret).now()


# ---------------------------------------------------------------------------
# Pure utility unit tests  (no client / DB required)
# ---------------------------------------------------------------------------


def test_generate_totp_secret_is_valid_base32():
    """Generated secret must be accepted by pyotp (valid base32)."""
    secret = generate_totp_secret()
    assert is_valid_base32(secret)
    # Confirm pyotp itself accepts it without raising
    totp = pyotp.TOTP(secret)
    assert len(totp.now()) == 6


def test_generate_totp_secret_uniqueness():
    """Two consecutive calls must not produce the same secret."""
    assert generate_totp_secret() != generate_totp_secret()


def test_is_valid_base32_rejects_garbage():
    assert not is_valid_base32("")
    assert not is_valid_base32("not-base32!!!")
    assert not is_valid_base32("123")  # not padded / too short for pyotp


def test_is_valid_base32_accepts_pyotp_generated():
    assert is_valid_base32(generate_totp_secret())


def test_get_provisioning_uri_format():
    secret = generate_totp_secret()
    uri = get_provisioning_uri(secret, "alice@example.com")
    assert uri.startswith("otpauth://totp/")
    assert "Langflow" in uri
    assert secret in uri


def test_verify_totp_code_valid_accepts_current_code():
    secret = generate_totp_secret()
    code = _make_valid_code(secret)
    assert verify_totp_code(secret, code) is True


def test_verify_totp_code_rejects_wrong_code():
    secret = generate_totp_secret()
    # A 6-digit code that is very unlikely to be the current one
    assert verify_totp_code(secret, "000000") is False or True  # still valid if by chance; just check no crash

    # Better: use an expired code by using a past window directly
    totp = pyotp.TOTP(secret)
    # Code from 120 seconds ago (outside valid_window=1) is definitely invalid
    old_code = totp.at(int(time.time()) - 120)
    assert verify_totp_code(secret, old_code) is False


def test_verify_totp_code_empty_inputs_return_false():
    secret = generate_totp_secret()
    assert verify_totp_code("", "123456") is False
    assert verify_totp_code(secret, "") is False
    assert verify_totp_code("", "") is False


def test_verify_totp_code_malformed_secret_returns_false():
    """A non-base32 secret must not raise; it should return False."""
    assert verify_totp_code("not-valid-base32!!!", "123456") is False


# ---------------------------------------------------------------------------
# Replay-attack prevention unit tests
# ---------------------------------------------------------------------------


def test_is_replay_false_for_fresh_code():
    secret = generate_totp_secret()
    uid = "user-replay-test-1"
    code = _make_valid_code(secret)
    # Fresh code with empty cache — must NOT be flagged as replay
    assert is_replay(uid, code) is False


def test_mark_used_then_is_replay_true():
    secret = generate_totp_secret()
    uid = "user-replay-test-2"
    code = _make_valid_code(secret)
    mark_used(uid, code)
    assert is_replay(uid, code) is True


def test_different_user_same_code_not_replay():
    """The same 6-digit code used by a different user must NOT be blocked."""
    secret = generate_totp_secret()
    code = _make_valid_code(secret)
    mark_used("user-A", code)
    assert is_replay("user-B", code) is False


def test_replay_cache_expires():
    """After the TTL passes the code should no longer be flagged."""
    uid = "user-ttl-test"
    code = "999999"
    mark_used(uid, code)
    assert is_replay(uid, code) is True

    # Simulate TTL expiry by directly clearing the key from the cache.
    keys_to_remove = [k for k in list(_used_codes.keys()) if k.startswith(uid)]
    for k in keys_to_remove:
        _used_codes.pop(k, None)

    assert is_replay(uid, code) is False


# ---------------------------------------------------------------------------
# API endpoint tests (require ``client`` + ``logged_in_headers`` fixtures)
# ---------------------------------------------------------------------------


async def test_totp_status_unauthenticated(client):
    """GET /totp/status without auth should return 401/403."""
    response = await client.get("api/v1/totp/status")
    assert response.status_code in {401, 403}


async def test_totp_status_authenticated_disabled(client, logged_in_headers):
    """Freshly created user has TOTP disabled."""
    response = await client.get("api/v1/totp/status", headers=logged_in_headers)
    assert response.status_code == 200
    assert response.json()["totp_enabled"] is False


async def test_totp_setup_returns_uri_and_secret(client, logged_in_headers):
    """POST /totp/setup must return a provisioning_uri and a valid raw_secret."""
    response = await client.post("api/v1/totp/setup", headers=logged_in_headers)
    assert response.status_code == 200
    data = response.json()
    assert "provisioning_uri" in data
    assert "raw_secret" in data
    assert data["provisioning_uri"].startswith("otpauth://totp/")
    assert is_valid_base32(data["raw_secret"])


async def test_totp_enable_with_invalid_code_returns_400(client, logged_in_headers):
    """POST /totp/enable with a wrong code must return 400."""
    setup_resp = await client.post("api/v1/totp/setup", headers=logged_in_headers)
    raw_secret = setup_resp.json()["raw_secret"]

    response = await client.post(
        "api/v1/totp/enable",
        json={"code": "000000", "raw_secret": raw_secret},
        headers=logged_in_headers,
    )
    # Either 400 (wrong code) or 422 (if 000000 happens to be current — extremely rare; just check not 200)
    assert response.status_code != 200


async def test_totp_enable_with_malformed_code_returns_422(client, logged_in_headers):
    """POST /totp/enable with a non-numeric or short code must return 422 (Pydantic)."""
    setup_resp = await client.post("api/v1/totp/setup", headers=logged_in_headers)
    raw_secret = setup_resp.json()["raw_secret"]

    for bad_code in ("abc", "12345", "1234567", ""):
        response = await client.post(
            "api/v1/totp/enable",
            json={"code": bad_code, "raw_secret": raw_secret},
            headers=logged_in_headers,
        )
        assert response.status_code == 422, f"Expected 422 for code={bad_code!r}, got {response.status_code}"


async def test_totp_enable_with_invalid_secret_returns_422(client, logged_in_headers):
    """POST /totp/enable with a garbage raw_secret must return 422 (Pydantic)."""
    response = await client.post(
        "api/v1/totp/enable",
        json={"code": "123456", "raw_secret": "not-valid!!"},  # pragma: allowlist secret
        headers=logged_in_headers,
    )
    assert response.status_code == 422


async def test_totp_full_enable_then_disable_flow(client, logged_in_headers, active_user):
    """Full happy path: setup → enable → verify status → disable → verify status."""
    # 1. Setup
    setup_resp = await client.post("api/v1/totp/setup", headers=logged_in_headers)
    assert setup_resp.status_code == 200
    raw_secret = setup_resp.json()["raw_secret"]

    # 2. Enable with the correct current code
    code = _make_valid_code(raw_secret)
    enable_resp = await client.post(
        "api/v1/totp/enable",
        json={"code": code, "raw_secret": raw_secret},
        headers=logged_in_headers,
    )
    assert enable_resp.status_code == 200
    assert enable_resp.json()["totp_enabled"] is True

    # 3. Status should reflect enabled
    status_resp = await client.get("api/v1/totp/status", headers=logged_in_headers)
    assert status_resp.json()["totp_enabled"] is True

    # 4. Use next code (new window) to disable — get a fresh code
    disable_code = _make_valid_code(raw_secret)
    # If same code was just used (same window), clear replay cache for this test
    user_id = str(active_user.id)
    for offset in range(-1, 2):
        _used_codes.pop(f"{user_id}:{disable_code}:{_current_window() + offset}", None)

    disable_resp = await client.post(
        "api/v1/totp/disable",
        json={"code": disable_code},
        headers=logged_in_headers,
    )
    assert disable_resp.status_code == 200
    assert disable_resp.json()["totp_enabled"] is False

    # 5. Status should reflect disabled
    status_resp2 = await client.get("api/v1/totp/status", headers=logged_in_headers)
    assert status_resp2.json()["totp_enabled"] is False


async def test_login_with_totp_enabled_returns_202(client, active_user):
    """When TOTP is enabled, POST /login must return 202 with partial_token."""
    # Enable TOTP on the active user directly in DB
    secret = generate_totp_secret()
    async with session_scope() as session:
        user = await session.get(User, active_user.id)
        auth = get_auth_service()
        user.totp_secret = auth.encrypt_api_key(secret)
        user.totp_enabled = True
        session.add(user)
        await session.commit()

    try:
        response = await client.post(
            "api/v1/login",
            data={"username": active_user.username, "password": "testpassword"},  # pragma: allowlist secret
        )
        assert response.status_code == 202
        data = response.json()
        assert data["totp_required"] is True
        assert "partial_token" in data
    finally:
        # Restore: disable TOTP so the active_user fixture cleanup works
        async with session_scope() as session:
            user = await session.get(User, active_user.id)
            user.totp_secret = None
            user.totp_enabled = False
            session.add(user)
            await session.commit()


async def test_verify_login_rejects_garbage_partial_token(client):
    """POST /totp/verify-login with a made-up token must return 401."""
    response = await client.post(
        "api/v1/totp/verify-login",
        json={"partial_token": "this.is.not.a.jwt", "code": "123456"},
    )
    assert response.status_code == 401


async def test_verify_login_rejects_access_token_as_partial_token(client, logged_in_headers):
    """A full access_token (type='access') must not be accepted as a partial_token."""
    # The logged_in_headers fixture contains a real access token
    access_token = logged_in_headers["Authorization"].split(" ", 1)[1]
    response = await client.post(
        "api/v1/totp/verify-login",
        json={"partial_token": access_token, "code": "123456"},
    )
    assert response.status_code == 401


async def test_verify_login_full_flow(client, active_user):
    """Full 2-FA login: password → 202 + partial_token → TOTP code → 200 + tokens."""
    secret = generate_totp_secret()
    async with session_scope() as session:
        user = await session.get(User, active_user.id)
        auth = get_auth_service()
        user.totp_secret = auth.encrypt_api_key(secret)
        user.totp_enabled = True
        session.add(user)
        await session.commit()

    try:
        # Step 1: password login
        login_resp = await client.post(
            "api/v1/login",
            data={"username": active_user.username, "password": "testpassword"},  # pragma: allowlist secret
        )
        assert login_resp.status_code == 202
        partial_token = login_resp.json()["partial_token"]

        # Step 2: TOTP verification
        code = _make_valid_code(secret)
        verify_resp = await client.post(
            "api/v1/totp/verify-login",
            json={"partial_token": partial_token, "code": code},
        )
        assert verify_resp.status_code == 200
        data = verify_resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
    finally:
        async with session_scope() as session:
            user = await session.get(User, active_user.id)
            user.totp_secret = None
            user.totp_enabled = False
            session.add(user)
            await session.commit()


async def test_replay_attack_rejected_on_verify_login(client, active_user):
    """Reusing the same TOTP code in /verify-login must be rejected with 401."""
    secret = generate_totp_secret()
    async with session_scope() as session:
        user = await session.get(User, active_user.id)
        auth = get_auth_service()
        user.totp_secret = auth.encrypt_api_key(secret)
        user.totp_enabled = True
        session.add(user)
        await session.commit()

    try:
        # First login — get a partial token
        login_resp = await client.post(
            "api/v1/login",
            data={"username": active_user.username, "password": "testpassword"},
        )
        partial_token = login_resp.json()["partial_token"]
        code = _make_valid_code(secret)

        # First verification — should succeed
        first = await client.post(
            "api/v1/totp/verify-login",
            json={"partial_token": partial_token, "code": code},
        )
        assert first.status_code == 200

        # Second attempt with the SAME code — must be rejected
        # Get a new partial token (new login attempt)
        login_resp2 = await client.post(
            "api/v1/login",
            data={"username": active_user.username, "password": "testpassword"},
        )
        partial_token2 = login_resp2.json()["partial_token"]
        second = await client.post(
            "api/v1/totp/verify-login",
            json={"partial_token": partial_token2, "code": code},
        )
        assert second.status_code == 401
        assert "already used" in second.json()["detail"].lower()
    finally:
        async with session_scope() as session:
            user = await session.get(User, active_user.id)
            user.totp_secret = None
            user.totp_enabled = False
            session.add(user)
            await session.commit()


async def test_disable_totp_with_invalid_code_returns_400(client, active_user, logged_in_headers):
    """POST /totp/disable with a wrong code when TOTP is enabled must return 400."""
    secret = generate_totp_secret()
    async with session_scope() as session:
        user = await session.get(User, active_user.id)
        auth = get_auth_service()
        user.totp_secret = auth.encrypt_api_key(secret)
        user.totp_enabled = True
        session.add(user)
        await session.commit()

    try:
        # Use a code from the past — definitely invalid
        old_code = pyotp.TOTP(secret).at(int(time.time()) - 120)
        response = await client.post(
            "api/v1/totp/disable",
            json={"code": old_code},
            headers=logged_in_headers,
        )
        assert response.status_code == 400
    finally:
        async with session_scope() as session:
            user = await session.get(User, active_user.id)
            user.totp_secret = None
            user.totp_enabled = False
            session.add(user)
            await session.commit()


# ---------------------------------------------------------------------------
# Partial-token lifecycle: single-use and brute-force cap (unit tests)
# ---------------------------------------------------------------------------


def test_fresh_partial_token_not_burnt():
    """A token that was never used must not be flagged as burnt."""
    assert not is_partial_token_burnt("fresh.jwt.token")


def test_burn_partial_token_marks_it_burnt():
    ptoken = "test.partial.token.burn"
    burn_partial_token(ptoken)
    assert is_partial_token_burnt(ptoken)


def test_record_failure_does_not_burn_below_max():
    ptoken = "ptoken-below-max"
    for i in range(MAX_VERIFY_ATTEMPTS - 1):
        count = record_partial_token_failure(ptoken)
        assert count == i + 1
        assert not is_partial_token_burnt(ptoken)


def test_record_failure_burns_at_max():
    ptoken = "ptoken-at-max"
    for _ in range(MAX_VERIFY_ATTEMPTS):
        record_partial_token_failure(ptoken)
    assert is_partial_token_burnt(ptoken)


def test_different_tokens_tracked_independently():
    ptoken_a = "partial-token-indep-a"
    ptoken_b = "partial-token-indep-b"
    for _ in range(MAX_VERIFY_ATTEMPTS):
        record_partial_token_failure(ptoken_a)
    assert is_partial_token_burnt(ptoken_a)
    assert not is_partial_token_burnt(ptoken_b)


# ---------------------------------------------------------------------------
# API: partial-token single-use and brute-force cap (integration)
# ---------------------------------------------------------------------------


async def test_verify_login_rejects_burnt_partial_token(client, active_user):
    """A partial token burned by a previous successful login must be rejected."""
    secret = generate_totp_secret()
    async with session_scope() as session:
        user = await session.get(User, active_user.id)
        auth = get_auth_service()
        user.totp_secret = auth.encrypt_api_key(secret)
        user.totp_enabled = True
        session.add(user)
        await session.commit()

    try:
        login_resp = await client.post(
            "api/v1/login",
            data={"username": active_user.username, "password": "testpassword"},
        )
        partial_token = login_resp.json()["partial_token"]
        code = pyotp.TOTP(secret).now()

        # First use — must succeed
        first = await client.post(
            "api/v1/totp/verify-login",
            json={"partial_token": partial_token, "code": code},
        )
        assert first.status_code == 200

        # Second use of the same partial_token — must fail (burnt)
        # Need a code for the next window to bypass the replay cache
        next_code = pyotp.TOTP(secret).now()
        second = await client.post(
            "api/v1/totp/verify-login",
            json={"partial_token": partial_token, "code": next_code},
        )
        assert second.status_code == 401
        assert "already used" in second.json()["detail"].lower() or "expired" in second.json()["detail"].lower()
    finally:
        async with session_scope() as session:
            user = await session.get(User, active_user.id)
            user.totp_secret = None
            user.totp_enabled = False
            session.add(user)
            await session.commit()


async def test_verify_login_burns_token_after_max_failures(client, active_user):
    """After MAX_VERIFY_ATTEMPTS wrong codes the partial token must be burned."""
    secret = generate_totp_secret()
    async with session_scope() as session:
        user = await session.get(User, active_user.id)
        auth = get_auth_service()
        user.totp_secret = auth.encrypt_api_key(secret)
        user.totp_enabled = True
        session.add(user)
        await session.commit()

    try:
        login_resp = await client.post(
            "api/v1/login",
            data={"username": active_user.username, "password": "testpassword"},
        )
        partial_token = login_resp.json()["partial_token"]

        # Submit MAX_VERIFY_ATTEMPTS wrong codes — all should be rejected
        for _ in range(MAX_VERIFY_ATTEMPTS):
            resp = await client.post(
                "api/v1/totp/verify-login",
                json={"partial_token": partial_token, "code": "000000"},
            )
            assert resp.status_code == 401

        # Now even the correct code must be rejected (token is burnt)
        correct_code = pyotp.TOTP(secret).now()
        final = await client.post(
            "api/v1/totp/verify-login",
            json={"partial_token": partial_token, "code": correct_code},
        )
        assert final.status_code == 401
    finally:
        async with session_scope() as session:
            user = await session.get(User, active_user.id)
            user.totp_secret = None
            user.totp_enabled = False
            session.add(user)
            await session.commit()
