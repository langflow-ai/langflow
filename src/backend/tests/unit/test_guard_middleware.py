"""Unit tests for the optional fastapi-guard middleware wiring."""

import itertools

import pytest
from fastapi import FastAPI
from langflow.services.security import attach_guard

pytest.importorskip("guard")

from httpx import ASGITransport, AsyncClient

# Rate limiting and ban state in fastapi-guard are process-wide, so every
# test drives its own TEST-NET client IP to stay hermetic.
_IP = itertools.count(1)


def _unique_ip() -> str:
    n = next(_IP)
    return f"198.51.{n // 250}.{(n % 250) + 1}"


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    attach_guard(app)
    return app


async def _get(monkeypatch, client_ip, path="/ping", **env):
    monkeypatch.delenv("LANGFLOW_GUARD_ENABLED", raising=False)
    for name in (
        "LANGFLOW_GUARD_BLOCKED_IPS",
        "LANGFLOW_GUARD_RATE_LIMIT",
        "LANGFLOW_GUARD_RATE_LIMIT_WINDOW",
        "LANGFLOW_GUARD_PASSIVE_MODE",
    ):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)

    transport = ASGITransport(app=_build_app(), client=(client_ip, 50000))
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get(path)


async def test_disabled_by_default(monkeypatch):
    response = await _get(monkeypatch, _unique_ip())
    assert response.status_code == 200


async def test_blocked_ip_is_rejected(monkeypatch):
    blocked = _unique_ip()
    response = await _get(
        monkeypatch,
        blocked,
        LANGFLOW_GUARD_ENABLED="true",
        LANGFLOW_GUARD_BLOCKED_IPS=blocked,
    )
    assert response.status_code == 403


async def test_rate_limit_returns_429(monkeypatch):
    client_ip = _unique_ip()
    env = {
        "LANGFLOW_GUARD_ENABLED": "true",
        "LANGFLOW_GUARD_RATE_LIMIT": "2",
        "LANGFLOW_GUARD_RATE_LIMIT_WINDOW": "60",
    }
    assert (await _get(monkeypatch, client_ip, **env)).status_code == 200
    assert (await _get(monkeypatch, client_ip, **env)).status_code == 200
    assert (await _get(monkeypatch, client_ip, **env)).status_code == 429


async def test_passive_mode_never_blocks(monkeypatch):
    blocked = _unique_ip()
    response = await _get(
        monkeypatch,
        blocked,
        LANGFLOW_GUARD_ENABLED="true",
        LANGFLOW_GUARD_PASSIVE_MODE="true",
        LANGFLOW_GUARD_BLOCKED_IPS=blocked,
    )
    assert response.status_code == 200


async def test_invalid_boolean_fails_loudly(monkeypatch):
    """LANGFLOW_GUARD_ENABLED=tru must not silently run unprotected."""
    from langflow.services.security import attach_guard

    monkeypatch.setenv("LANGFLOW_GUARD_ENABLED", "tru")
    with pytest.raises(ValueError, match="LANGFLOW_GUARD_ENABLED"):
        attach_guard(FastAPI())


async def test_zero_trust_proxy_default(monkeypatch):
    """No proxy is trusted unless explicitly listed.

    On a LAN deployment a private-range peer must not be able to spoof
    X-Forwarded-For.
    """
    from langflow.services.security import build_guard_config

    monkeypatch.delenv("LANGFLOW_GUARD_ENABLED", raising=False)
    monkeypatch.delenv("LANGFLOW_GUARD_TRUSTED_PROXIES", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    config = build_guard_config()
    assert config.trusted_proxies == ()
    # Bodies are data here (flow specs, prompts, uploads): signature
    # scanning of bodies is opt-in, URL/query/header screening stays on.
    assert config.detection_scan_body is False

    monkeypatch.setenv("LANGFLOW_GUARD_TRUSTED_PROXIES", "10.0.0.1, 10.0.0.2")
    config = build_guard_config()
    assert config.trusted_proxies == ("10.0.0.1", "10.0.0.2")


async def test_rate_limit_auto_ban_flag(monkeypatch):
    """Rate-limit violations feed the ban engine by default.

    That is the advertised behavior; operators can keep 429-only
    enforcement, and invalid values fail loudly.
    """
    from langflow.services.security import build_guard_config

    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("LANGFLOW_GUARD_RATE_LIMIT_AUTO_BAN", raising=False)
    config = build_guard_config()
    assert config.enable_rate_limit_auto_ban is True

    monkeypatch.setenv("LANGFLOW_GUARD_RATE_LIMIT_AUTO_BAN", "0")
    config = build_guard_config()
    assert config.enable_rate_limit_auto_ban is False

    monkeypatch.setenv("LANGFLOW_GUARD_RATE_LIMIT_AUTO_BAN", "sometimes")
    with pytest.raises(ValueError, match="LANGFLOW_GUARD_RATE_LIMIT_AUTO_BAN"):
        build_guard_config()


async def test_free_text_params_skip_signature_scanning(monkeypatch):
    """Search boxes carry user text, so their values are not signature scanned.

    Operators can replace the list with LANGFLOW_GUARD_EXCLUDED_DETECTION_PARAMS.
    """
    from langflow.services.security import build_guard_config

    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("LANGFLOW_GUARD_EXCLUDED_DETECTION_PARAMS", raising=False)
    assert build_guard_config().excluded_detection_params == {"search", "query"}

    monkeypatch.setenv("LANGFLOW_GUARD_EXCLUDED_DETECTION_PARAMS", "search, q")
    assert build_guard_config().excluded_detection_params == {"search", "q"}


async def test_security_headers_keep_same_origin_microphone(monkeypatch):
    """The voice assistant calls getUserMedia, which `microphone=()` would block."""
    from langflow.services.security import PERMISSIONS_POLICY, build_guard_config

    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("LANGFLOW_GUARD_SECURITY_HEADERS", "true")
    assert build_guard_config().security_headers["permissions_policy"] == PERMISSIONS_POLICY
    assert "microphone=(self)" in PERMISSIONS_POLICY
