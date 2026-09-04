import re

from pydantic import BaseModel, field_validator

from lfx.log.logger import logger


class McpSettings(BaseModel):
    """MCP server, session manager, and composer settings, plus the A2A protocol toggle."""

    mcp_base_url: str = ""
    """External base URL (scheme + host + optional path) used to build MCP server URLs.
    Set it to the externally reachable origin (e.g. 'https://langflow.example.com'); this is
    required in multi-pod deployments where the pod binds 0.0.0.0 but must advertise a routable
    gateway/service address, since the bind host cannot also serve as the advertised host.
    When empty (default): the backend builds URLs from host/port (0.0.0.0 -> localhost) and the
    frontend falls back to the browser's window.location.origin."""

    mcp_server_timeout: int = 20
    """The number of seconds to wait before giving up on establishing a connection to the MCP server."""

    mcp_tool_execution_timeout: float = 180.0
    """Maximum seconds to wait for MCP tool execution before timing out.
    Default is 180 seconds (3 minutes) to support long-running operations.
    Supports decimal values for sub-second timeouts (e.g., 0.5 for 500ms).
    Individual components can override this with their own timeout setting.
    Must be a positive number greater than 0."""

    @field_validator("mcp_tool_execution_timeout")
    @classmethod
    def validate_mcp_tool_execution_timeout(cls, v: float) -> float:
        """Validate that mcp_tool_execution_timeout is positive."""
        if v <= 0:
            msg = "mcp_tool_execution_timeout must be greater than 0"
            raise ValueError(msg)
        return v

    # ---------------------------------------------------------------------
    # MCP Session-manager tuning
    # ---------------------------------------------------------------------
    mcp_max_sessions_per_server: int = 10
    """Maximum number of MCP sessions to keep per unique server (command/url).
    Mirrors the default constant MAX_SESSIONS_PER_SERVER in util.py. Adjust to
    control resource usage or concurrency per server."""

    mcp_session_idle_timeout: int = 400  # seconds (~6.7 minutes)
    """How long (in seconds) an MCP session can stay idle before the background
    cleanup task disposes of it."""

    mcp_session_cleanup_interval: int = 120  # seconds
    """Frequency (in seconds) at which the background cleanup task wakes up to
    reap idle sessions."""

    # MCP Server
    mcp_server_enabled: bool = True
    """If set to False, Langflow will not enable the MCP server."""

    mcp_sse_enabled: bool = True
    """If set to False, the legacy SSE transport and its message endpoint answer 404.

    ``mcp_server_enabled`` mounts both transports and there is no way to serve only the
    modern one. SSE holds a stream open for the life of the connection and keeps a
    never-evicted ``SseServerTransport`` per project, which is a poor fit for a shared
    multi-tenant serving tier. Default True preserves compatibility for clients that
    still speak SSE; Streamable HTTP is unaffected either way.
    Env var: LANGFLOW_MCP_SSE_ENABLED."""
    mcp_server_enable_progress_notifications: bool = False
    """If set to False, Langflow will not send progress notifications in the MCP server."""

    # Add projects to MCP servers automatically on creation
    add_projects_to_mcp_servers: bool = True
    """If set to True, newly created projects will be added to the user's MCP servers config automatically."""

    skip_mcp_auto_init: bool = False
    """If set to True, Langflow skips the background MCP server auto-initialization on startup.

    The startup task reconciles every project's MCP server config, which for apikey/none
    projects can spawn ``uvx mcp-proxy`` and open an outbound connection. On an offline or
    firewalled host (or CI) that connect has no bounded timeout and blocks until the OS
    connect timeout (~127s). Enable this in tests or air-gapped deployments to keep startup
    local and deterministic."""

    # MCP Composer
    mcp_composer_enabled: bool = True
    """If set to False, Langflow will not start the MCP Composer service."""
    mcp_composer_version: str = "==0.1.0.8.10"
    """Version constraint for mcp-composer when using uvx. Uses PEP 440 syntax."""

    mcp_sdk_constraint: str = "mcp~=1.28"
    """Requirement injected as ``uvx --with`` when Langflow launches an MCP server through uvx.

    ``uvx`` resolves each server into its own ephemeral environment, so Langflow's own
    ``mcp`` pin does not apply there. ``mcp-proxy`` and ``mcp-composer`` still declare an
    unbounded ``mcp>=1.x``, and the 2.0 SDK removed ``request_ctx`` and renamed ``McpError``,
    so an unconstrained resolve installs a release those packages cannot import. Keep the
    specifier free of ``<``/``>``, which the stdio command policy rejects as shell
    metacharacters. The exact configured specifier is exempt from
    ``mcp_server_allowed_packages``, so allowlisted deployments keep working without
    adding ``mcp``. Set to an empty string to disable the injection once upstream
    supports the 2.x SDK. Env var: LANGFLOW_MCP_SDK_CONSTRAINT."""

    # A2A protocol
    a2a_enabled: bool = False
    """If set to True, Langflow serves spec-valid A2A agent cards at a per-flow
    discovery endpoint for agent-typed, a2a_enabled flows. Default off (opt-in).
    Env var: LANGFLOW_A2A_ENABLED."""
    a2a_allow_private_webhooks: bool = False
    """If True, A2A push-notification webhooks may target private/loopback/link-local
    addresses. Default False blocks them (SSRF protection on the public endpoint); enable
    only in a trusted network where agents notify internal services.
    Env var: LANGFLOW_A2A_ALLOW_PRIVATE_WEBHOOKS."""

    # MCP Server management
    mcp_servers_locked: bool = False
    """If set to True, users cannot add or modify MCP servers via the UI/API.

    This control is independent from ``embedded_mode`` and must be enabled
    explicitly when you want to lock MCP server management.
    """

    mcp_server_allowed_packages: str | None = None
    """Comma-separated package allowlist for MCP ``npx``/``uvx`` stdio servers.

    When set, package runners may download and execute only these exact package names.
    Version specifiers are allowed but do not change the package identity. Leave unset to
    preserve the legacy single-tenant behavior. Multi-tenant deployments should set this
    to the packages installed by their operator; an empty value blocks all package runners.
    """

    mcp_server_env_allowlist: str | None = None
    """Comma-separated allowlist of environment-variable names an MCP stdio config may set.

    Unset (the default) applies only the built-in policy, which denies whole runtime families
    -- loader (``LD_*``/``DYLD_*``), OpenSSL (``OPENSSL_*``), interpreter option and module
    paths (``PYTHON*``, ``NODE_*``, ``PERL*``, ``JAVA_*``, ...), package-runner source
    overrides (``UV_*``, ``NPM_CONFIG_*``, ``PIP_*``), git helper commands (``GIT_*``), and
    TLS trust anchors -- while permitting the arbitrary vendor-named credentials that real MCP
    servers require (``GITHUB_TOKEN``, ``BRAVE_API_KEY``, ...).

    Setting this switches to a strict allowlist: exactly these names are accepted and every
    other name is rejected. That is the durable posture for multi-tenant deployments, since no
    blocklist can enumerate every code-loading variable across libc, OpenSSL, git, and every
    interpreter. An explicitly empty value (``""``) is the strictest setting -- it rejects all
    tenant-supplied environment variables -- and is distinct from leaving this unset.

    Because the list is authoritative, naming a loader or interpreter variable here
    re-enables that code-execution vector; list only application credentials and configuration
    your servers actually need. Langflow always injects ``PATH`` itself, so it need not be
    listed. Env var: LANGFLOW_MCP_SERVER_ENV_ALLOWLIST.
    """

    mcp_server_interpreter_hardening: bool = False
    """If set to True, blocks tenant-controlled Python, Node.js, and shell MCP entrypoints.

    The command allowlist alone cannot make ``python <uploaded-file>`` or
    ``node <uploaded-file>`` or ``bash <uploaded-file>`` safe. Hardened mode rejects direct
    interpreter/script invocations while retaining validated package wrappers and the
    authenticated internal ``python -m langflow.agentic.mcp`` server. Leave disabled to
    preserve legacy single-tenant MCP configurations.
    """

    @field_validator("mcp_composer_version", mode="before")
    @classmethod
    def validate_mcp_composer_version(cls, value):
        """Ensure the version string has a version specifier prefix.

        If a bare version like '0.1.0.7' is provided, prepend '~=' to allow patch updates.
        Supports PEP 440 specifiers: ==, !=, <=, >=, <, >, ~=, ===
        """
        if not value:
            return "==0.1.0.8.10"  # Default

        specifiers = ["===", "==", "!=", "<=", ">=", "~=", "<", ">"]
        if any(value.startswith(spec) for spec in specifiers):
            return value

        if re.match(r"^\d+(\.\d+)*", value):
            logger.debug(f"Adding ~= prefix to bare version '{value}' -> '~={value}'")
            return f"~={value}"

        return value
