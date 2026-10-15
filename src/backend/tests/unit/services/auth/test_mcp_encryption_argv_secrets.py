"""Header values carried in ``args`` are secrets and must be stored as such.

``mcp-proxy`` takes request headers positionally -- ``--headers <name>
<value>`` -- rather than as a map, and project MCP servers are registered that
way with a real Langflow API key as the value. Encrypting only the ``env`` and
``headers`` maps left that one key in plaintext in ``mcp_server.config``.
"""

import pytest
from langflow.services.auth.mcp_encryption import (
    decrypt_mcp_config,
    encrypt_mcp_config,
    is_encrypted,
)

API_KEY = "sk-test-project-key"  # pragma: allowlist secret
URL = "http://localhost:7860/api/v1/mcp/project/x/streamable"


def _project_server_config(api_key: str = API_KEY) -> dict:
    return {
        "command": "uvx",
        "args": [
            "mcp-proxy",
            "--transport",
            "streamablehttp",
            "--headers",
            "x-api-key",
            api_key,
            URL,
        ],
    }


@pytest.fixture(autouse=True)
def _encryption_key():
    """Without a key, ``encrypt_api_key`` has nothing to do and these prove nothing."""
    from langflow.services.deps import get_settings_service

    if not get_settings_service().auth_settings.SECRET_KEY.get_secret_value():
        pytest.skip("no encryption key configured in this environment")


def test_the_project_api_key_is_encrypted_at_rest():
    stored = encrypt_mcp_config(_project_server_config())

    value = stored["args"][5]
    assert value != API_KEY
    assert is_encrypted(value)


def test_structural_args_are_left_alone():
    """Only the value after a header name is a secret; the rest is argv."""
    stored = encrypt_mcp_config(_project_server_config())

    assert stored["command"] == "uvx"
    assert stored["args"][:5] == ["mcp-proxy", "--transport", "streamablehttp", "--headers", "x-api-key"]
    assert stored["args"][6] == URL


def test_a_round_trip_returns_a_runnable_config():
    assert decrypt_mcp_config(encrypt_mcp_config(_project_server_config())) == _project_server_config()


def test_encrypting_twice_does_not_double_wrap():
    once = encrypt_mcp_config(_project_server_config())

    assert encrypt_mcp_config(once) == once


def test_rows_written_before_this_shipped_still_decrypt():
    """Plaintext values pass through, as they already do for env and headers."""
    assert decrypt_mcp_config(_project_server_config()) == _project_server_config()


def test_a_trailing_headers_flag_is_not_an_index_error():
    """Malformed argv must not take the whole config down."""
    config = {"command": "uvx", "args": ["mcp-proxy", "--headers", "x-api-key"]}

    assert encrypt_mcp_config(config) == config
    assert decrypt_mcp_config(config) == config


def test_args_that_are_not_a_list_are_ignored():
    config = {"command": "uvx", "args": "mcp-proxy --headers x-api-key secret"}

    assert encrypt_mcp_config(config) == config
