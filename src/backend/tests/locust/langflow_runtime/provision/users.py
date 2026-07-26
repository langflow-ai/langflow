"""Authentication helpers for provision CLI modes."""

from __future__ import annotations

import os
import secrets
from typing import Any

from tests.locust.langflow_runtime.provision.api import ProvisionHttp
from tests.locust.langflow_runtime.provision.state import register_resource


def resolve_credentials(
    *,
    mode: str,
    username: str | None = None,
    password: str | None = None,
) -> tuple[str | None, str | None]:
    """Resolve username/password from flags or environment."""
    if mode == "existing-user":
        user = username or os.environ.get("PERF_USERNAME") or os.environ.get("LANGFLOW_SUPERUSER")
        pwd = password or os.environ.get("PERF_PASSWORD") or os.environ.get("LANGFLOW_SUPERUSER_PASSWORD")
        if not user or not pwd:
            msg = "existing-user mode requires --username/--password or PERF_USERNAME/PERF_PASSWORD"
            raise RuntimeError(msg)
        return user, pwd

    # superuser-pool (default) — credentials for the *admin* that creates the pool.
    user = username or os.environ.get("PERF_SUPERUSER") or os.environ.get("LANGFLOW_SUPERUSER") or "langflow"
    pwd = password or os.environ.get("PERF_SUPERUSER_PASSWORD") or os.environ.get("LANGFLOW_SUPERUSER_PASSWORD")
    return user, pwd


def authenticate(
    http: ProvisionHttp,
    *,
    mode: str,
    username: str | None = None,
    password: str | None = None,
) -> dict[str, Any]:
    """Authenticate like ``authenticate_setup_client``: password login or AUTO_LOGIN."""
    user, pwd = resolve_credentials(mode=mode, username=username, password=password)

    if pwd:
        assert user is not None
        token = http.login(user, pwd)
        return {"access_token": token, "username": user, "mode": mode, "via": "password"}

    # No password → try AUTO_LOGIN (typical local/dev).
    token = http.auto_login()
    return {"access_token": token, "username": user or "auto-login", "mode": mode, "via": "auto_login"}


def _find_user_id(http: ProvisionHttp, username: str) -> str | None:
    for row in http.list_users(limit=200):
        if str(row.get("username")) == username:
            return str(row.get("id")) if row.get("id") is not None else None
    return None


def ensure_suite_user_pool(
    http: ProvisionHttp,
    state: dict[str, Any],
    *,
    mode: str,
) -> dict[str, Any]:
    """Create (or reuse) a suite-tagged non-superuser and switch auth to that user.

    ``superuser-pool`` logs in as the admin, creates ``perf-{env_id}-user``, activates
    it when needed, then re-authenticates as the suite user for subsequent provision.
    ``existing-user`` leaves the authenticated caller unchanged.
    """
    if mode != "superuser-pool":
        state["user_pool"] = {"mode": mode, "created": False}
        return state

    env_id = str(state["env_id"])
    suite_username = f"perf-{env_id}-user"
    suite_password = secrets.token_urlsafe(24)

    created = http.create_user(suite_username, suite_password)
    user_id = created.get("id")
    if created.get("already_exists") or not user_id:
        user_id = _find_user_id(http, suite_username)
        if not user_id:
            msg = f"suite user {suite_username!r} exists but could not be resolved"
            raise RuntimeError(msg)
        # Reset password so we can log in without retaining a prior secret.
        http.patch_user(str(user_id), {"password": suite_password, "is_active": True})
    else:
        # Newly created users may be inactive depending on NEW_USER_IS_ACTIVE.
        http.patch_user(str(user_id), {"is_active": True})

    register_resource(
        state,
        kind="user",
        resource_id=str(user_id),
        name=suite_username,
        env_id=env_id,
    )
    state["user_pool"] = {
        "mode": mode,
        "created": True,
        "username": suite_username,
        "user_id": str(user_id),
    }
    state["credentials"]["suite_username"] = suite_username
    state["credentials"]["password"] = suite_password

    # Switch bearer to the suite user for keys/projects/flows ownership.
    http.login(suite_username, suite_password)
    state["username"] = suite_username
    return state
