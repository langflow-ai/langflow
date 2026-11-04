"""Unit tests for RedisIndexChatMemory connection URL building."""

from unittest.mock import patch

import pytest

pytest.importorskip("lfx_bundles")
pytest.importorskip("langchain_community")
pytest.importorskip("redis")

from lfx_bundles.redis.redis_chat import RedisIndexChatMemory
from redis.connection import parse_url


@pytest.fixture(autouse=True)
def _disable_connector_ssrf(monkeypatch):
    """These tests use fake hosts; SSRF validation is covered in test_connector_ssrf.py."""
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED", "false")


def _build_url(username: str, password: str) -> str:
    component = RedisIndexChatMemory()
    component.host = "redis.example.com"
    component.port = 6379
    component.database = "2"
    component.username = username
    component.password = password
    component.key_prefix = ""
    component.session_id = "session"
    with patch("lfx_bundles.redis.redis_chat.RedisChatMessageHistory") as mock_history:
        component.build_message_history()
    return mock_history.call_args.kwargs["url"]


@pytest.mark.parametrize(
    "password",
    [
        "p@ss/word#1",  # pragma: allowlist secret
        "with space+plus",  # pragma: allowlist secret
        "colon:and?query",  # pragma: allowlist secret
    ],
)
def test_password_with_reserved_characters_round_trips(password):
    parsed = parse_url(_build_url("user", password))

    assert parsed["password"] == password
    assert parsed["username"] == "user"
    assert parsed["host"] == "redis.example.com"
    assert parsed["port"] == 6379
    assert parsed["db"] == 2


def test_username_with_reserved_characters_round_trips():
    password = "pw"  # noqa: S105  # pragma: allowlist secret
    parsed = parse_url(_build_url("team@acme", password))

    assert parsed["username"] == "team@acme"
    assert parsed["password"] == password
