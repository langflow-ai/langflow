import pytest
from lfx.base.mcp.source_policy import (
    is_package_manager_config_env_var,
    validate_mcp_stdio_source_policy,
)


@pytest.mark.parametrize(
    "env_var",
    [
        "NPM_CONFIG_REGISTRY",
        "npm_config_userconfig",
        "UV_DEFAULT_INDEX",
        "uv_index_url",
        "PIP_INDEX_URL",
        "pip_extra_index_url",
    ],
)
def test_package_manager_configuration_namespaces_are_reserved(env_var):
    assert is_package_manager_config_env_var(env_var)


@pytest.mark.parametrize(
    ("command", "args"),
    [
        ("uvx", ["--default-index", "https://packages.example.invalid/simple", "mcp-server"]),
        ("uvx", ["--index-url=https://packages.example.invalid/simple", "mcp-server"]),
        ("uvx", ["--from", "git+https://code.example.invalid/server.git", "mcp-server"]),
        ("uvx", ["--from", "server.whl", "mcp-server"]),
        ("uvx", ["-wgit+https://code.example.invalid/addon.git", "mcp-server"]),
        ("uvx", ["https://packages.example.invalid/server.whl"]),
        ("npx", ["--registry=https://packages.example.invalid", "@example/mcp-server"]),
        ("npx", ["--package", "git+https://code.example.invalid/server.git"]),
        ("npx", ["https://packages.example.invalid/server.tgz"]),
        ("npx", ["server.tgz"]),
        ("docker", ["run", "-v", "/:/host", "mcp-server"]),
        ("docker", ["run", "-iv", "/:/host", "mcp-server"]),
        ("docker", ["run", "--volume=/var/run:/host/run", "mcp-server"]),
        ("docker", ["run", "--mount", "type=bind,source=/,target=/host", "mcp-server"]),
        ("sh", ["-c", "uvx --default-index https://packages.example.invalid/simple mcp-server"]),
        ("bash", ["-lc", "npx --registry=https://packages.example.invalid @example/mcp-server"]),
        ("cmd", ["/c", "docker", "run", "--mount", "type=bind,source=/,target=/host", "mcp-server"]),
        ("sh", ["-c", "true; uvx --index-url https://packages.example.invalid/simple mcp-server"]),
        ("sh", ["-c", "exec uvx --index-url https://packages.example.invalid/simple mcp-server"]),
    ],
)
def test_source_redirects_and_host_mounts_are_rejected(command, args):
    with pytest.raises(ValueError, match="not allowed"):
        validate_mcp_stdio_source_policy(command, args)


@pytest.mark.parametrize(
    ("command", "args"),
    [
        ("uvx", ["--from", "lfx", "lfx-mcp"]),
        ("uvx", ["--from=lfx==1.10.3", "lfx-mcp"]),
        ("uvx", ["-wlfx", "mcp-server"]),
        ("uvx", ["mcp-proxy", "--transport", "streamablehttp", "https://mcp.example.com"]),
        ("npx", ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"]),
        ("npx", ["@example/mcp-server@1.2.3", "--endpoint", "https://mcp.example.com"]),
        ("docker", ["run", "--rm", "-i", "--entrypoint", "mcp-server", "-u", "1000", "mcp-image"]),
        ("sh", ["-c", "uvx --from lfx lfx-mcp"]),
        ("bash", ["-c", "python -m mcp_server"]),
        ("cmd", ["/c", "npx", "@example/mcp-server", "--endpoint", "https://mcp.example.com"]),
    ],
)
def test_trusted_registry_packages_and_non_host_access_args_are_allowed(command, args):
    validate_mcp_stdio_source_policy(command, args)
