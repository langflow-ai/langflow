import pytest
from lfx.base.mcp.security import validate_mcp_stdio_config
from lfx.base.mcp.source_policy import (
    is_package_manager_config_env_var,
    validate_mcp_stdio_source_policy,
)


def _validate_policy(command, args):
    if command in {"sh", "bash", "cmd"}:
        validate_mcp_stdio_config(command, args, None)
    else:
        validate_mcp_stdio_source_policy(command, args)


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
        ("docker", ["run", "--volumes-from=other", "mcp-server"]),
        ("docker", ["run", "--device", "/dev/example", "mcp-server"]),
        ("docker", ["run", "--device=/dev/example", "mcp-server"]),
        ("docker", ["run", "--device-cgroup-rule", "b 8:0 rwm", "mcp-server"]),
        ("docker", ["run", "--privileged", "mcp-server"]),
        ("docker", ["run", "--cap-add", "SYS_ADMIN", "mcp-server"]),
        ("docker", ["run", "--pid", "host", "mcp-server"]),
        ("docker", ["run", "--ipc=container:other", "mcp-server"]),
        ("docker", ["run", "--uts", "host", "mcp-server"]),
        ("docker", ["run", "--network", "host", "mcp-server"]),
        ("docker", ["run", "--net=container:other", "mcp-server"]),
        ("docker", ["run", "--security-opt", "seccomp=unconfined", "mcp-server"]),
        ("docker", ["run", "--security-opt=apparmor=unconfined", "mcp-server"]),
        ("docker", ["run", "--security-opt", "label:disable", "mcp-server"]),
        ("sh", ["-c", "uvx --default-index https://packages.example.invalid/simple mcp-server"]),
        ("bash", ["-lc", "npx --registry=https://packages.example.invalid @example/mcp-server"]),
        ("cmd", ["/c", "docker", "run", "--mount", "type=bind,source=/,target=/host", "mcp-server"]),
        ("sh", ["-c", "docker cp other:/run/secrets/token /workspace/token"]),
        ("sh", ["-c", "true; uvx --index-url https://packages.example.invalid/simple mcp-server"]),
        ("sh", ["-c", "exec uvx --index-url https://packages.example.invalid/simple mcp-server"]),
    ],
)
def test_source_redirects_and_docker_host_access_are_rejected(command, args):
    with pytest.raises(ValueError, match=r"not allowed|dangerous shell metacharacter|cannot execute"):
        _validate_policy(command, args)


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
        ("docker", ["run", "--rm", "-i", "--network", "bridge", "mcp-image"]),
        ("docker", ["run", "--rm", "-i", "--network", "mcp-network", "mcp-image"]),
        ("docker", ["run", "--rm", "-i", "--ipc", "private", "mcp-image"]),
        ("docker", ["run", "--rm", "-i", "--security-opt", "no-new-privileges", "mcp-image"]),
        ("sh", ["-c", "uvx --from lfx lfx-mcp"]),
        ("bash", ["-c", "python -m mcp_server"]),
        ("cmd", ["/c", "npx", "@example/mcp-server", "--endpoint", "https://mcp.example.com"]),
    ],
)
def test_trusted_registry_packages_and_isolated_docker_args_are_allowed(command, args):
    _validate_policy(command, args)


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["cp", "other:/run/secrets/token", "/workspace/token"],
        ["inspect", "other"],
        ["network", "connect", "shared", "other"],
    ],
)
def test_docker_requires_run_subcommand_by_default(args):
    with pytest.raises(ValueError, match=r"not allowed"):
        validate_mcp_stdio_source_policy("docker", args, docker_hardening=False)


@pytest.mark.parametrize(
    ("command", "args"),
    [
        ("uvx", ["unapproved-server"]),
        ("npx", ["@example/unapproved-server"]),
        ("uvx", ["--from", "lfx", "python"]),
    ],
)
def test_operator_package_allowlist_and_uvx_entrypoints_are_enforced(command, args):
    with pytest.raises(ValueError, match=r"not allowed"):
        validate_mcp_stdio_source_policy(
            command,
            args,
            allowed_packages=frozenset({"lfx", "mcp-proxy"}),
        )


@pytest.mark.parametrize(
    ("command", "args"),
    [
        ("uvx", ["mcp-proxy"]),
        ("uvx", ["--from", "lfx", "lfx-mcp"]),
        ("uvx", ["--with", "lfx", "mcp-proxy"]),
    ],
)
def test_operator_package_allowlist_preserves_approved_packages(command, args):
    validate_mcp_stdio_source_policy(
        command,
        args,
        allowed_packages=frozenset({"lfx", "mcp-proxy"}),
    )


@pytest.mark.parametrize(
    "args",
    [
        ["--package", "mcp-proxy", "--package", "attacker-package", "mcp-proxy"],
        ["--package=mcp-proxy", "--package=attacker-package", "mcp-proxy"],
        ["-p", "attacker-package", "mcp-proxy"],
    ],
)
def test_npx_allowlist_checks_every_explicit_package(args):
    with pytest.raises(ValueError, match="Package 'attacker-package' is not allowed"):
        validate_mcp_stdio_source_policy(
            "npx",
            args,
            allowed_packages=frozenset({"mcp-proxy"}),
        )


def test_npx_allowlist_rejects_unrelated_explicit_package_entrypoint():
    with pytest.raises(ValueError, match="Entrypoint 'python' is not allowed for MCP npx"):
        validate_mcp_stdio_source_policy(
            "npx",
            ["--package", "mcp-proxy", "python", "-c", "print('not executed')"],
            allowed_packages=frozenset({"mcp-proxy"}),
        )


def test_npx_explicit_package_rejects_unverified_same_name_path_entrypoint():
    with pytest.raises(ValueError, match="Package 'lfx' has no verified entrypoint"):
        validate_mcp_stdio_config(
            "npx",
            ["--package", "lfx", "lfx"],
            {},
            allowed_packages={"lfx"},
        )


def test_npx_explicit_package_rejects_unverified_secondary_package():
    with pytest.raises(ValueError, match="Package 'lfx' has no verified entrypoint"):
        validate_mcp_stdio_config(
            "npx",
            ["--package", "lfx", "--package", "mcp-proxy", "mcp-proxy"],
            {},
            allowed_packages={"lfx", "mcp-proxy"},
        )


def test_npx_allowlist_rejects_shell_call_mode():
    with pytest.raises(ValueError, match="Argument '--call' is not allowed"):
        validate_mcp_stdio_source_policy(
            "npx",
            ["--call", "mcp-proxy", "--package", "attacker-package"],
            allowed_packages=frozenset({"mcp-proxy"}),
        )


def test_npx_allowlist_preserves_matching_explicit_package_entrypoint():
    validate_mcp_stdio_config(
        "npx",
        ["--package", "mcp-proxy", "mcp-proxy", "--transport", "stdio"],
        {},
        allowed_packages={"mcp-proxy"},
    )


def test_npx_double_dash_keeps_following_package_flag_as_command_argument():
    validate_mcp_stdio_config(
        "npx",
        ["--package", "mcp-proxy", "--", "mcp-proxy", "--package", "command-argument"],
        {},
        allowed_packages=frozenset({"mcp-proxy"}),
    )


def test_npx_first_positional_keeps_following_package_flag_as_command_argument():
    validate_mcp_stdio_config(
        "npx",
        ["--package", "mcp-proxy", "mcp-proxy", "--package", "command-argument"],
        {},
        allowed_packages=frozenset({"mcp-proxy"}),
    )


@pytest.mark.parametrize(
    "args",
    [
        ["--with=mcp-proxy", "--with=attacker-package", "mcp-proxy"],
        ["--with", "mcp-proxy", "--with", "attacker-package", "mcp-proxy"],
        ["-wmcp-proxy", "-wattacker-package", "mcp-proxy"],
    ],
)
def test_uvx_allowlist_checks_every_additional_package(args):
    with pytest.raises(ValueError, match="Package 'attacker-package' is not allowed for MCP uvx"):
        validate_mcp_stdio_config(
            "uvx",
            args,
            {},
            allowed_packages={"mcp-proxy"},
        )


@pytest.mark.parametrize(
    "args",
    [
        ["--with", "mcp-proxy", "attacker-package"],
        ["--no-sources-package", "mcp-proxy", "attacker-package"],
    ],
)
def test_uvx_option_value_cannot_mask_unapproved_primary_target(args):
    with pytest.raises(ValueError, match="Package 'attacker-package' is not allowed for MCP uvx"):
        validate_mcp_stdio_config(
            "uvx",
            args,
            {},
            allowed_packages={"mcp-proxy"},
        )


@pytest.mark.parametrize(
    ("args", "allowed_packages"),
    [
        (["--python-preference", "system", "attacker-package"], {"system"}),
        (["--future-value-option", "mcp-proxy", "attacker-package"], {"mcp-proxy"}),
    ],
)
def test_uvx_unknown_option_cannot_mask_primary_target(args, allowed_packages):
    with pytest.raises(ValueError, match=r"Argument '--[^']+' is not allowed for MCP stdio command 'uvx'"):
        validate_mcp_stdio_config("uvx", args, {}, allowed_packages=allowed_packages)


@pytest.mark.parametrize("flag", ["--isolated", "--no-config", "-qq", "-vv", "-qU", "-Un", "-qvU"])
def test_uvx_known_boolean_options_preserve_primary_target(flag):
    validate_mcp_stdio_config("uvx", [flag, "mcp-proxy"], {}, allowed_packages={"mcp-proxy"})


@pytest.mark.parametrize("option", ["-p3.12", "-Pfoo", "-Cfoo=bar"])
def test_uvx_attached_known_value_options_preserve_primary_target(option):
    validate_mcp_stdio_config("uvx", [option, "mcp-proxy"], {}, allowed_packages={"mcp-proxy"})


def test_npx_noninteractive_flag_remains_allowed_by_shared_policy():
    validate_mcp_stdio_config("npx", ["-y", "@modelcontextprotocol/server-filesystem"], None)


@pytest.mark.parametrize(
    ("command", "args"),
    [
        ("python", ["/tmp/tenant.py"]),
        ("python3", ["-m", "tenant.module"]),
        ("node", ["/tmp/tenant.js"]),
        ("bash", ["/tmp/tenant.sh"]),
        ("sh", ["/tmp/tenant.sh", "-c", "uvx mcp-proxy"]),
        ("cmd", [r"C:\tenant\evil.bat", "/c", "uvx", "mcp-proxy"]),
    ],
)
def test_interpreter_hardening_rejects_tenant_selected_code(command, args):
    with pytest.raises(ValueError, match=r"not allowed"):
        validate_mcp_stdio_source_policy(command, args, interpreter_hardening=True)


def test_interpreter_hardening_preserves_authenticated_agentic_module():
    validate_mcp_stdio_source_policy(
        "python",
        ["-m", "langflow.agentic.mcp"],
        interpreter_hardening=True,
    )


def test_windows_forward_slash_executable_path_preserves_source_policy():
    with pytest.raises(ValueError, match=r"not allowed"):
        validate_mcp_stdio_config(
            "C:/Program Files/uv/uvx.exe",
            ["--index-url", "https://packages.example.invalid/simple", "mcp-proxy"],
            None,
            allowed_packages=frozenset({"mcp-proxy"}),
            interpreter_hardening=True,
        )


@pytest.mark.parametrize(
    "args",
    [
        ["exec", "running-container", "sh"],
        ["run", "--env-file", "/etc/secrets", "mcp-image"],
        ["run", "--use-api-socket", "mcp-image"],
        ["run", "--network", "internal-control-plane", "mcp-image"],
        ["run", "-itp8080:80", "mcp-image"],
        ["run", "--runtime", "host-runtime", "mcp-image"],
        ["run", "--restart", "always", "mcp-image"],
    ],
)
def test_docker_hardening_rejects_remaining_host_access_bypasses(args):
    with pytest.raises(ValueError, match=r"not allowed"):
        validate_mcp_stdio_source_policy("docker", args, docker_hardening=True)


def test_docker_hardening_preserves_isolated_run():
    validate_mcp_stdio_source_policy(
        "docker",
        ["run", "--rm", "--network", "bridge", "--security-opt", "no-new-privileges", "mcp-image"],
        docker_hardening=True,
    )
