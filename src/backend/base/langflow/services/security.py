"""Optional fastapi-guard security middleware wiring.

fastapi-guard (https://github.com/Guard-Core/fastapi-guard) provides IP
block/allow lists, rate limiting with auto-ban, user-agent blocking,
penetration-attempt detection, security headers, optional Redis-backed
shared state, and optional IPInfo geo/cloud-provider lookups.

Everything here is opt-in: with no LANGFLOW_GUARD_* environment variables
set, attach_guard() is a no-op and the app behaves exactly as before. Set
LANGFLOW_GUARD_ENABLED=true to activate the middleware. It layers on top
of the existing slowapi endpoint limiters and touches none of them.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import FastAPI
    from guard import SecurityConfig

DEFAULT_EXCLUDED_PATHS = "/health,/docs,/redoc,/openapi.json,/api/version"
# Empty by default on purpose: langflow is frequently deployed with clients
# on the same private network, and trusting private-range peers would let
# any of them spoof X-Forwarded-For. Behind a reverse proxy, set
# LANGFLOW_GUARD_TRUSTED_PROXIES to the proxy's addresses.
DEFAULT_TRUSTED_PROXIES = ""
# Query parameters that carry user text by design: the search boxes
# (knowledge-base chunks, projects, folders, store, users, teams, end users)
# and the traces `query` filter. The endpoints treat their values as data
# (escaped LIKE patterns, substring filters, sanitized trace search), so
# signature scanning them only produces false positives such as
# `search=SELECT * FROM users`. Every other parameter, the path and the
# headers are still scanned.
DEFAULT_EXCLUDED_DETECTION_PARAMS = "search,query"
# fastapi-guard's default Permissions-Policy is `microphone=()`, which blocks
# the voice assistant's getUserMedia call. Same-origin microphone stays
# allowed; geolocation and camera, which Langflow never uses, stay off.
PERMISSIONS_POLICY = "geolocation=(), microphone=(self), camera=()"


def _env_bool(name: str, *, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in ("1", "true", "yes", "on"):
        return True
    if normalized in ("", "0", "false", "no", "off"):
        return False
    msg = f"{name} must be a boolean (1/true/yes/on or 0/false/no/off), got {raw!r}"
    raise ValueError(msg)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw not in (None, "") else default


def _env_str(name: str, default: str | None = None) -> str | None:
    raw = os.environ.get(name)
    return raw if raw not in (None, "") else default


def _env_csv(name: str, default: str | None = None) -> tuple[str, ...]:
    return tuple(item.strip() for item in (_env_str(name, default) or "").split(",") if item.strip())


def build_guard_config() -> SecurityConfig:
    """Build the SecurityConfig from LANGFLOW_GUARD_* environment variables."""
    from guard import SecurityConfig

    kwargs: dict[str, Any] = {
        "enable_rate_limiting": True,
        "rate_limit": _env_int("LANGFLOW_GUARD_RATE_LIMIT", 100),
        "rate_limit_window": _env_int("LANGFLOW_GUARD_RATE_LIMIT_WINDOW", 60),
        "enable_ip_banning": True,
        "auto_ban_threshold": _env_int("LANGFLOW_GUARD_AUTO_BAN_THRESHOLD", 10),
        "auto_ban_duration": _env_int("LANGFLOW_GUARD_AUTO_BAN_DURATION", 300),
        # On by default: the advertised behavior is that repeated rate-limit
        # violations ban the source, not just 429 it. Set
        # LANGFLOW_GUARD_RATE_LIMIT_AUTO_BAN=0 to keep 429-only enforcement.
        "enable_rate_limit_auto_ban": _env_bool("LANGFLOW_GUARD_RATE_LIMIT_AUTO_BAN", default=True),
        "enable_penetration_detection": True,
        # Flow specs, chat prompts, and file uploads are data, not commands
        # this API executes: signature-scanning bodies false-positives on
        # ordinary content (SQL/HTML/shell text inside messages). Detection
        # keeps screening the URL path, query params, and headers; body
        # scanning is opt-in via LANGFLOW_GUARD_SCAN_BODY.
        "detection_scan_body": _env_bool("LANGFLOW_GUARD_SCAN_BODY"),
        "excluded_detection_params": set(
            _env_csv("LANGFLOW_GUARD_EXCLUDED_DETECTION_PARAMS", DEFAULT_EXCLUDED_DETECTION_PARAMS)
        ),
        # In-memory state unless a Redis URL is configured; reuse the
        # deployment's REDIS_URL when present so counters and bans survive
        # langflow's default multi-worker gunicorn setup.
        "enable_redis": False,
        "passive_mode": _env_bool("LANGFLOW_GUARD_PASSIVE_MODE"),
        "blacklist": _env_csv("LANGFLOW_GUARD_BLOCKED_IPS"),
        "blocked_user_agents": list(_env_csv("LANGFLOW_GUARD_BLOCKED_USER_AGENTS")),
        "trusted_proxies": _env_csv("LANGFLOW_GUARD_TRUSTED_PROXIES", DEFAULT_TRUSTED_PROXIES),
        "trusted_proxy_depth": _env_int("LANGFLOW_GUARD_TRUSTED_PROXY_DEPTH", 1),
        "exclude_paths": list(_env_csv("LANGFLOW_GUARD_EXCLUDED_PATHS", DEFAULT_EXCLUDED_PATHS)),
        "custom_log_file": _env_str("LANGFLOW_GUARD_LOG_FILE"),
        "log_format": _env_str("LANGFLOW_GUARD_LOG_FORMAT", "text"),
        "security_headers": (
            {
                "enabled": True,
                "hsts": {"max_age": 31536000, "include_subdomains": True},
                "frame_options": "SAMEORIGIN",
                "content_type_options": "nosniff",
                "referrer_policy": "strict-origin-when-cross-origin",
                "permissions_policy": PERMISSIONS_POLICY,
            }
            if _env_bool("LANGFLOW_GUARD_SECURITY_HEADERS")
            else None
        ),
        "enforce_https": _env_bool("LANGFLOW_GUARD_ENFORCE_HTTPS"),
    }

    # Behind a TLS-terminating proxy, enforce_https must read the forwarded
    # scheme or every request looks like plain HTTP.
    explicit_xfp = _env_str("LANGFLOW_GUARD_TRUST_X_FORWARDED_PROTO")
    if explicit_xfp is not None:
        kwargs["trust_x_forwarded_proto"] = _env_bool("LANGFLOW_GUARD_TRUST_X_FORWARDED_PROTO")
    else:
        kwargs["trust_x_forwarded_proto"] = _env_bool("LANGFLOW_GUARD_ENFORCE_HTTPS")

    if allowed_ips := _env_csv("LANGFLOW_GUARD_ALLOWED_IPS"):
        kwargs["whitelist"] = allowed_ips
    if blocked_countries := _env_csv("LANGFLOW_GUARD_BLOCKED_COUNTRIES"):
        kwargs["blocked_countries"] = frozenset(blocked_countries)
    if allowed_countries := _env_csv("LANGFLOW_GUARD_ALLOWED_COUNTRIES"):
        kwargs["whitelist_countries"] = frozenset(allowed_countries)
    if cloud_providers := _env_csv("LANGFLOW_GUARD_BLOCK_CLOUD_PROVIDERS"):
        kwargs["block_cloud_providers"] = frozenset(cloud_providers)

    redis_url = _env_str("LANGFLOW_GUARD_REDIS_URL") or _env_str("REDIS_URL")
    if redis_url:
        kwargs["enable_redis"] = True
        kwargs["redis_url"] = redis_url
        kwargs["redis_prefix"] = "langflow_guard:"

    if ipinfo_token := _env_str("IPINFO_TOKEN"):
        kwargs["ipinfo_token"] = ipinfo_token

    return SecurityConfig(**kwargs)


def attach_guard(app: FastAPI) -> None:
    """Attach the fastapi-guard middleware when LANGFLOW_GUARD_ENABLED is set.

    No-op unless the env flag is on. Fails loudly when the flag is on but
    the package is missing: a misconfiguration must never silently disable
    security. Also exposes the shared SecurityDecorator on app.state so
    per-route guard decorators adopt the same config as the middleware.
    """
    if not _env_bool("LANGFLOW_GUARD_ENABLED"):
        return
    try:
        from guard import SecurityDecorator, SecurityMiddleware
    except ImportError as exc:
        msg = (
            "LANGFLOW_GUARD_ENABLED=true requires the fastapi-guard package. Install it with: pip install fastapi-guard"
        )
        raise RuntimeError(msg) from exc

    from lfx.log.logger import logger

    config = build_guard_config()
    app.add_middleware(SecurityMiddleware, config=config)
    app.state.guard_decorator = SecurityDecorator(config)
    logger.info("fastapi-guard security middleware enabled")
