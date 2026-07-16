from pydantic import BaseModel, field_validator


class SecuritySettings(BaseModel):
    """CORS, SSRF protection, API key handling, and custom-component policy."""

    # CORS
    cors_origins: list[str] | str = "*"
    """Allowed origins for CORS. Can be a list of origins or '*' for all origins.
    Default is '*' for backward compatibility. In production, specify exact origins."""
    cors_allow_credentials: bool = True
    """Whether to allow credentials in CORS requests.
    Default is True for backward compatibility. In v2.0, this will be changed to False when using wildcard origins."""
    cors_allow_methods: list[str] | str = "*"
    """Allowed HTTP methods for CORS requests."""
    cors_allow_headers: list[str] | str = "*"
    """Allowed headers for CORS requests."""

    # SSRF Protection
    ssrf_protection_enabled: bool = True
    """If set to True, Langflow will enable SSRF (Server-Side Request Forgery) protection.
    When enabled, blocks requests to private IP ranges, localhost, and cloud metadata endpoints.
    When False, no URL validation is performed, allowing requests to any destination
    including internal services, private networks, and cloud metadata endpoints.
    Default is True to protect against SSRF attacks including DNS rebinding.

    Note: When ssrf_protection_enabled is disabled, the ssrf_allowed_hosts setting is ignored and has no effect."""
    ssrf_allowed_hosts: list[str] = []
    """Comma-separated list of hosts/IPs/CIDR ranges to allow despite SSRF protection.
    Examples: 'internal-api.company.local,192.168.1.0/24,10.0.0.5,*.dev.internal'
    Supports exact hostnames, wildcard domains (*.example.com), exact IPs, and CIDR ranges.

    Note: This setting only takes effect when ssrf_protection_enabled is True.
    When protection is disabled, all hosts are allowed regardless of this setting."""
    connector_ssrf_validation_enabled: bool = True
    """SSRF validation for CONNECTOR components that take a tenant-controlled host/URL:
    vector stores (Chroma/Qdrant/Elasticsearch/OpenSearch/Milvus/Weaviate/Supabase/Upstash/
    ClickHouse), the SQL Database components, the Glean and AstraDB-CQL tools, model-provider
    model discovery (LiteLLM/HuggingFace/xAI/DeepSeek/Groq/watsonx), and the Ollama / LM Studio /
    Home Assistant base-URL fields.

    Default True: connector host validation follows ssrf_protection_enabled / ssrf_allowed_hosts
    so tenant-controlled connector URLs cannot reach internal/cloud-metadata hosts by default.
    Single-tenant/self-hosted operators who intentionally point connectors at localhost or private
    networks can either allowlist those hosts or set this to False. For the SQL Database
    components, the separate LANGFLOW_RESTRICT_LOCAL_FILE_ACCESS toggle still governs local-file
    dialects (e.g. sqlite) independently of this flag."""
    connector_ssrf_allow_loopback: bool = True
    """Whether a literal loopback host (localhost, 127.0.0.0/8, ::1) is allowed for HTTP CONNECTOR
    and model-provider URLs, even while connector SSRF validation is on.

    Default True because connectors routinely target a *local* service: Ollama and LM Studio
    default to http://localhost:11434 / http://localhost:1234, and local vector stores bind to
    loopback. Blocking loopback by default would break those single-tenant setups out of the box.
    Cloud-metadata (169.254.169.254) and private/RFC1918 ranges are still blocked regardless.

    Multi-tenant deployers, where a tenant pointing a connector at the *server's* loopback is an
    SSRF vector, set this to False to block loopback too. Only literal loopback references are
    exempted — a hostname that *resolves* to loopback is still blocked, so DNS-rebinding cannot
    abuse this. Has no effect on the API Request component (always strict), database URLs, or git
    URLs, which validate loopback independently."""

    # API key handling
    disable_track_apikey_usage: bool = False
    remove_api_keys: bool = False

    # Custom Component Security
    allow_custom_components: bool = True
    """If set to False, blocks execution of components whose code does not match a known
    server template.

    The server validates node code against its component template cache;
    when the cache is not yet loaded (e.g., during startup), all flow execution is blocked
    as a safety measure.

    Note: LANGFLOW_COMPONENTS_PATH and LANGFLOW_COMPONENTS_INDEX_PATH can be used to define
    an allow-list of custom components that will be allowed to execute, even when
    allow_custom_components is False. That bypass can be disabled with
    allow_components_paths_override.

    Note: this is a beta feature. For security in a multi-tenant environment,
    use hardware-level isolation to restrict access."""
    custom_component_admin_only: bool = False
    """If set to True, only admin users can edit custom component code. Regular editors
    are blocked from modifying custom component templates."""

    allow_components_paths_override: bool = True
    """If set to False, LANGFLOW_COMPONENTS_PATH and LANGFLOW_COMPONENTS_INDEX_PATH will
    not bypass the allow_custom_components=False restriction — only components matching
    built-in server templates will be executable.

    Default is True, which preserves the existing behavior: components loaded from those
    env-var paths act as an admin-curated allow-list that remains executable even when
    allow_custom_components is False.

    Has no effect when allow_custom_components is True (the flag is not blocking anything
    to override)."""

    allow_public_custom_components: bool = False
    """If set to True, the unauthenticated public flow build path
    (POST /api/v1/build_public_tmp/{flow_id}/flow) honors allow_custom_components just like
    the authenticated build path, building the flow from the database as its owner.

    Default is False: on the public path the server substitutes its own trusted code into
    every known component and rejects unrecognized custom components, so anonymous visitors
    can only ever run server code that matches a known component template. The global
    allow_custom_components flag grants custom-code execution to *authenticated* users; it is
    intentionally not extended to the unauthenticated public path, which builds flows as their
    owner (report H1-3754930 follow-up). Enable this only if you knowingly want public flows to
    run custom component code permitted by allow_custom_components."""

    block_code_interpreter_components: bool = False
    """If set to True, blocks execution of any flow that contains a built-in
    arbitrary-code-execution component (Python Interpreter, Python REPL/Code tools, and the
    Smart Transform / lambda evaluator).

    These components are official, so their class-code hash is valid and they pass the
    ``allow_custom_components=False`` policy — yet they execute arbitrary Python supplied
    through their *input fields*, which is equivalent to letting users author custom code.

    Defaults to False to preserve existing behavior. Multi-tenant / untrusted-user
    deployments that disallow user-authored components should set this to True (alongside
    ``LANGFLOW_ALLOW_CUSTOM_COMPONENTS=false``) so these code-execution primitives cannot be
    used to break out of the component allow-list."""

    restrict_local_file_access: bool = False
    """If set to True, the built-in file-reading components (File, Directory, JSON/CSV-to-Data)
    may only read paths that resolve inside the authenticated user's or executing flow's storage
    subdirectory under ``config_dir``, where uploaded files live.

    These components accept a filesystem path from a tenant-controlled input field. With the
    default (False) a tenant can set that path to an absolute server path (``/etc/passwd``, the
    SQLite DB, secrets) or a traversal string and read arbitrary server files — or another
    tenant's uploads. Multi-tenant / untrusted-user deployments that disallow user-authored
    components should set this to True (alongside ``LANGFLOW_ALLOW_CUSTOM_COMPONENTS=false``) so
    these components cannot read server files or storage belonging to another user or flow.

    Defaults to False to preserve existing single-tenant behavior, where reading local server
    files by absolute path is a legitimate feature."""

    mcp_server_docker_hardening: bool = False
    """If set to True, applies a strict docker-argument policy to MCP stdio servers (both
    flow-embedded configs and the ``/api/v2/mcp/servers`` REST endpoint).

    ``docker`` is an allowed MCP transport, but flags like ``-v /:/host`` (mount the host
    filesystem), ``--use-api-socket`` (Docker-API root), ``--env-file`` (host file read),
    ``--device``, ``--network host``, and ``--privileged`` turn a container run into host access.
    With the default (False) only ``--privileged`` / ``--cap-add`` and the host-namespace ``=``
    forms are blocked, which preserves existing single-tenant behavior where docker MCP servers
    legitimately use volume mounts and custom networks.

    Multi-tenant / untrusted-tenant deployments should set this to True (alongside
    ``LANGFLOW_ALLOW_CUSTOM_COMPONENTS=false``): host file/API/device access, published ports,
    custom runtimes, restart persistence, and privilege flags are then rejected outright;
    host/another-container namespaces and non-default networks are rejected; and
    ``--security-opt`` is rejected only when it disables the sandbox. Benign forms (no flags,
    ``--user``, ``--network none``/``bridge``, ``--security-opt no-new-privileges``) stay allowed."""

    # Rate Limiting
    rate_limit_enabled: bool = True
    """Enable rate limiting for login and public-flow build endpoints. Set to False to disable."""
    rate_limit_per_minute: int = 5
    """Number of login attempts or builds of each public flow allowed per minute per IP."""
    rate_limit_storage_uri: str = "memory://"
    """Storage backend for rate limiting. Use 'memory://' for single-server or 'redis://host:port' for multi-server."""
    rate_limit_trust_proxy: bool = False
    """Trust X-Forwarded-For header when behind a reverse proxy. Only enable when behind a trusted proxy."""
    public_flow_rate_limit_per_minute: int = 20
    """Public-flow runs allowed per minute per IP on the unauthenticated /api/v2/workflows/public endpoint.
    Each run executes as the flow owner (real CPU/DB/LLM-credit cost), so anonymous callers are throttled
    separately from (and more generously than) the login limit. Gated by rate_limit_enabled."""

    @field_validator("cors_origins", mode="before")
    @classmethod
    def validate_cors_origins(cls, value):
        """Convert comma-separated string to list if needed.

        Pydantic-settings on Python 3.14 parses the env var "*" into ["*"]
        before this validator runs (the union list[str] | str resolves
        differently). Collapse that back to the bare-string wildcard so
        downstream consumers see the same shape on every Python version.
        """
        if isinstance(value, list) and value == ["*"]:
            return "*"
        if isinstance(value, str) and value != "*":
            if "," in value:
                return [origin.strip() for origin in value.split(",")]
            return [value]
        return value
