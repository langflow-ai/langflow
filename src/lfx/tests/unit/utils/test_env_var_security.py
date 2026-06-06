"""Unit tests for the env-var fallback denylist (cross-environment leak guard)."""

import pytest
from lfx.utils.env_var_security import is_protected_env_var, safe_getenv


@pytest.mark.parametrize(
    "name",
    [
        "LANGFLOW_SECRET_KEY",
        "LANGFLOW_DATABASE_URL",
        "LANGFLOW_SUPERUSER_PASSWORD",
        "langflow_secret_key",  # case-insensitive
        "LFX_ANYTHING",
        "DATABASE_URL",
        "SECRET_KEY",
        "POSTGRES_PASSWORD",
        "AWS_SECRET_ACCESS_KEY",
        "",  # empty fails closed
    ],
)
def test_protected_names_are_blocked(name):
    assert is_protected_env_var(name) is True


@pytest.mark.parametrize(
    "name",
    [
        "OPENAI_API_KEY",
        "MY_CUSTOM_VALUE",
        "GREETING",
        "HTTP_PROXY",
    ],
)
def test_unprotected_names_are_allowed(name):
    assert is_protected_env_var(name) is False


def test_safe_getenv_returns_none_for_protected(monkeypatch):
    """A protected name must look unset even when it is actually set in the environment."""
    monkeypatch.setenv("LANGFLOW_SECRET_KEY", "super-secret-master-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@host/db")

    assert safe_getenv("LANGFLOW_SECRET_KEY") is None
    assert safe_getenv("DATABASE_URL") is None


def test_safe_getenv_returns_value_for_allowed(monkeypatch):
    monkeypatch.setenv("MY_CUSTOM_VALUE", "ok")
    assert safe_getenv("MY_CUSTOM_VALUE") == "ok"
    assert safe_getenv("UNSET_VARIABLE_NAME") is None
