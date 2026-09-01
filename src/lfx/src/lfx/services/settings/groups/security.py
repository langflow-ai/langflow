from typing import Literal

from pydantic import BaseModel, Field, field_validator


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
    ClickHouse), the SQL Database components, the Glean and AstraDB-CQL tools, the DataStax
    Astra DB / HCD API endpoint (shared by the Data API, tool, vector store, graph and chat-memory
    components), model-provider model discovery (LiteLLM/HuggingFace/xAI/DeepSeek/Groq/watsonx),
    the Ollama / LM Studio / Home Assistant base-URL fields, the A2A Agent agent URL, and the
    PaddleOCR base URL.

    Default True: connector host validation follows ssrf_protection_enabled / ssrf_allowed_hosts
    so tenant-controlled connector URLs cannot reach internal/cloud-metadata hosts by default.
    Single-tenant/self-hosted operators who intentionally point connectors at localhost or private
    networks can either allowlist those hosts or set this to False. For the SQL Database
    components, the separate LANGFLOW_RESTRICT_LOCAL_FILE_ACCESS toggle still governs local-file
    dialects (e.g. sqlite) independently of this flag."""
    connector_ssrf_allow_loopback: bool = True
    """Whether a literal loopback host (localhost, 127.0.0.0/8, ::1) is allowed for ordinary HTTP
    CONNECTOR URLs, even while connector SSRF validation is on.

    Default True because connectors routinely target a *local* service: Ollama and LM Studio
    default to http://localhost:11434 / http://localhost:1234, and local vector stores bind to
    loopback. Blocking loopback by default would break those single-tenant setups out of the box.
    Cloud-metadata (169.254.169.254) and private/RFC1918 ranges are still blocked regardless.

    Multi-tenant deployers, where a tenant pointing a connector at the *server's* loopback is an
    SSRF vector, set this to False to block loopback too. Only literal loopback references are
    exempted — a hostname that *resolves* to loopback is still blocked, so DNS-rebinding cannot
    abuse this. When SSRF validation is enabled, credential-bearing URLs guarded by
    ``lfx.base.models.provider_ssrf`` use the strict path and require an explicit
    ``ssrf_allowed_hosts`` entry for loopback. Has no effect on the API Request component,
    database URLs, or git URLs, which validate loopback independently."""

    # API key handling
    disable_track_apikey_usage: bool = False
    remove_api_keys: bool = False

    # Custom Component Security
    allow_custom_components: bool = True
    """If set to False, blocks execution of components whose code does not match a known
    server template and disables registered built-in code-execution components at runtime.

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

    substitute_outdated_component_code: bool = True
    """Whether a built-in component whose stored code has drifted from this server's copy is
    rebuilt with this server's code instead of being refused. Only consulted when
    ``allow_custom_components`` is False (with the default True nothing is gated, so nothing is
    substituted).

    With ``allow_custom_components=False`` the node's stored code never runs anyway — the build
    already substitutes the server's copy keyed by code hash (``resolve_trusted_code_for_build``).
    The hash check therefore refuses flows over code it was not going to execute, which makes every
    upgrade that touches a built-in component break every saved flow using it until each node is
    updated by hand.

    Default is True: a node whose ``type`` is a known server component is rebuilt with that
    component's current server code, matching what the unauthenticated public build path already
    does by default (see ``prepare_public_flow_build``). Nothing new becomes runnable — the code
    that runs is always this server's own, selected by component type, and a node whose type is
    not a known server component is still refused. Substitutions are logged, and the stored flow is
    left untouched so the editor keeps flagging the node as outdated.

    Set to False to keep the strict behavior: refuse the build whenever a node's stored code does
    not match the current server template. Has no effect when ``allow_custom_components`` is True."""

    block_code_interpreter_components: bool = False
    """If set to True, blocks built-in components that execute user- or model-supplied
    Python, including Python Interpreter/REPL/Function, Smart Transform, CSV Agent,
    CodeAct, Cuga, and OpenDsStar.

    The policy is enforced during flow validation and again during component and tool
    execution. ``LANGFLOW_ALLOW_CUSTOM_COMPONENTS=false`` also disables these registered
    code-execution components while blocking user-authored component code. Set this flag
    independently when custom components should remain allowed but built-in code execution
    should not.

    Defaults to False to preserve existing single-tenant behavior."""

    sandbox_backend: str = "none"
    """Execution backend for user-authored code in the code-execution components
    (Python Interpreter and the legacy Python REPL tool).

    - "none" (default): code runs in-process via ``exec`` with the best-effort
      Python-level hardening (restricted builtins + AST checks). Preserves existing
      behavior; nothing extra to install.
    - "exec-sandbox": each execution runs in a dedicated QEMU microVM via the
      optional ``exec-sandbox`` package (``pip install 'langflow[sandbox]'``;
      requires Python >= 3.12 and QEMU 8+ with KVM/HVF hardware acceleration —
      hosts without a hardware hypervisor are refused unless
      ``sandbox_allow_software_emulation`` is enabled). The VM has a read-only
      rootfs, no host filesystem access, and no network unless
      ``sandbox_allow_network`` is enabled. In this mode the Python-level import
      allow-list and AST escape-gadget restrictions are not applied — the VM
      boundary replaces them — so sandboxed code may import any module available
      in the guest image. If the backend is configured but unusable, execution
      fails closed with an error instead of silently running in-process.

    See https://github.com/langflow-ai/langflow/issues/12029."""

    sandbox_timeout_seconds: int = Field(default=30, ge=1, le=300)
    """Wall-clock limit for one sandboxed execution, in seconds (1-300).
    Only used when sandbox_backend is not "none"."""

    sandbox_memory_mb: int = Field(default=192, ge=128)
    """Guest VM memory for sandboxed executions, in MB (minimum 128).
    Only used when sandbox_backend is not "none"."""

    sandbox_allow_network: bool = False
    """Whether sandboxed code may access the network. Default False: the microVM
    runs fully offline, which is the strongest isolation. Note the in-process
    backend has full server-side network access, so enabling the sandbox with the
    default here is a behavior change for code that fetches URLs.

    When enabled WITHOUT ``sandbox_allowed_domains``, exec-sandbox's DNS filter
    still only permits its package-registry defaults (PyPI /
    files.pythonhosted.org) — ordinary APIs stay unreachable until their domains
    are listed explicitly. Only used when sandbox_backend is not "none"."""

    sandbox_allowed_domains: list[str] = []
    """Comma-separated list of domains sandboxed code may reach when
    ``sandbox_allow_network`` is enabled (forwarded to exec-sandbox's DNS
    filter). Empty (default) keeps exec-sandbox's package-registry-only
    default. Listing a domain here permits guest egress to it, so treat this
    like an SSRF allow-list: prefer narrow, fully-qualified domains.
    Only used when sandbox_backend is not "none"."""

    sandbox_allow_software_emulation: bool = False
    """Permit the sandbox to run without a hardware hypervisor (KVM on Linux,
    HVF on macOS), letting QEMU fall back to TCG software emulation.

    Default False and strongly recommended to keep it that way: upstream
    exec-sandbox documents TCG as NOT security-supported (and ~5-8x slower),
    while sandbox mode disables the in-process Python defenses on the
    assumption of a hardware boundary. Enable only for trusted/development
    workloads, e.g. CI smoke tests or containers without /dev/kvm passthrough.
    Only used when sandbox_backend is not "none"."""

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

    # Runtime tweak policy
    tweaks_policy: Literal["permissive", "declared", "off"] = "permissive"
    """Which fields a run request may set through ``tweaks``.

    ``permissive`` (default) preserves existing behavior: the protected-field floor
    refuses code fields and privileged sinks, and every other field accepts a tweak.

    ``declared`` honors the per-flow allowlist the flow author sets in the parameters
    panel. On a flow where at least one field is marked editable via API, only those
    fields accept a tweak. A flow where the author has marked nothing keeps permissive
    behavior, so enabling this does not break flows nobody has prepared.

    ``off`` refuses every tweak, and also refuses component-targeted ``inputs``. A
    caller can still send ``input_value`` and ``session_id``, so chat flows keep
    running.

    The protected-field floor applies in all three modes and no setting relaxes it.
    ``declared`` cannot expose a code field, because the flow author's allowlist is
    consulted only after the floor has already refused.

    Refused tweaks return 422 naming the refused keys in every mode. They previously
    logged a warning and returned 200, which left a caller unable to tell a refused
    tweak from an applied one.

    This setting governs what a *caller* may override. ``tweaks`` is also the internal
    mechanism for passing values into a sub-flow, so tweaks the runtime generates for
    itself (the Run Flow component feeding its declared inputs to a sub-flow, resolved
    global-variable values) are not judged by it. Otherwise ``off`` would stop the Run
    Flow component and every flow used as an agent tool, which is not what closing an
    API surface should mean. The protected-field floor still applies to those.

    MCP deserves one qualification. Its primary ``input_value`` travels through the
    normal graph-input channel and is not a tweak. Additional advertised input fields
    are translated into tweaks, so this setting judges them. Under ``off`` those extra
    fields are refused, while ``input_value``-only MCP tools continue to work. Use
    ``permissive`` or ``declared`` for MCP tools that require tweak-backed parameters."""
    # Serving-plane end-user identity
    serving_end_user_header: str | None = None
    """Name of the trusted request header that carries the end-user identity on the serving plane
    (e.g. ``X-End-User-Id``). The value is an opaque, deterministic per-user string minted and
    injected by the authenticated gateway; Langflow does not parse or validate it, it only uses it
    as the per-user memory/state scope key.

    UNSET (the default) means the feature is OFF: no end-user identity is read and every serving
    request is fully anonymous (ephemeral, no persisted per-user memory). Setting a header name
    turns the feature on, but the header is still only trusted when
    ``serving_trust_proxy_headers`` is True.

    Security: an unverified client-supplied header would let any caller read another user's memory,
    so the header must be injected/validated by the authenticated gateway and the serving pods must
    be reachable only through that gateway (network policy). See ``serving_trust_proxy_headers``."""
    serving_trust_proxy_headers: bool = False
    """Fail-closed opt-in for the serving-plane end-user identity header. The header named by
    ``serving_end_user_header`` is trusted ONLY when this is True.

    Default False: even with a header name configured, the header is ignored and every request is
    anonymous until an operator explicitly opts in. Enable this only when the deployment guarantees
    (a) the authenticated gateway injects/overwrites the header from a validated identity and
    (b) network policy makes the gateway the only caller able to reach the serving pods. Without
    those two guarantees a client can spoof the header and read another user's memory."""
    serving_end_user_required: bool = False
    """Whether a serving request with no end-user identity is rejected. Only meaningful when the
    feature is on (``serving_end_user_header`` set and ``serving_trust_proxy_headers`` True).

    Default False: a request with no identity is allowed and runs as an anonymous, ephemeral
    session with no persisted memory. Set True to reject identity-less requests instead (e.g. a
    deployment that must attribute every run to an end user)."""
    serving_trace_end_user: bool = False
    """Whether the serving-plane end-user id is forwarded to the configured tracing provider.

    The end-user id is PII (the same reason outbound MCP forwarding is allowlist-gated and
    fail-closed). Tracing providers (Langfuse, LangSmith, Opik, ...) are third-party SaaS, so this is
    OFF by default: an identified serving run's trace shows only the service account (SID), never the
    end user. Set True to surface the end user as the ``langflow.tracing_user_id`` trace label
    (attribution) — an explicit operator decision to send that identity off-deployment. Independent of
    the primary ``trace.userId``, which is always the SID regardless of this flag."""
    serving_internal_mcp_hosts: str | None = None
    """Comma-separated allowlist of hosts (``host`` or ``host:port``) treated as INTERNAL for
    outbound MCP calls. When a flow's MCPTools component calls out to a server whose host is on this
    list, the serving-plane end-user identity header (``serving_end_user_header``) is auto-appended
    so a sibling project on the same plane can attribute the run to the same end user.

    Default UNSET means the allowlist is empty, so the end-user header is NEVER auto-appended to any
    outbound MCP call (fail-closed): the identity is PII and must never leak to an external MCP
    server. Only hosts an operator explicitly lists here — the deployment's own serving endpoints —
    receive it. Matching is exact on the URL host (and port when given); it does not widen to
    subdomains. Unrelated to by-name header substitution, which stays opt-in and unaffected."""

    # Rate Limiting
    rate_limit_enabled: bool = True
    """Enable rate limiting for login and public-flow endpoints. Set to False to disable."""
    rate_limit_per_minute: int = 5
    """Number of login attempts allowed per minute per IP."""
    rate_limit_storage_uri: str = "memory://"
    """Storage backend for rate limiting. Use 'memory://' for single-server or 'redis://host:port' for multi-server."""
    rate_limit_trust_proxy: bool = False
    """Trust X-Forwarded-For header when behind a reverse proxy. Only enable when behind a trusted proxy."""
    public_flow_rate_limit_per_minute: int = 20
    """Public-flow runs allowed per minute per IP on the unauthenticated v1 build and v2 workflow endpoints.
    V1 uses one bucket per flow; v2 uses its public-workflow bucket. Each run executes as the flow owner, so
    anonymous callers are throttled separately from and more generously than login. Gated by rate_limit_enabled."""

    @field_validator("sandbox_allowed_domains", mode="after")
    @classmethod
    def normalize_sandbox_allowed_domains(cls, value: list[str]) -> list[str]:
        """Strip whitespace and drop empty entries.

        The env parser splits ``LANGFLOW_SANDBOX_ALLOWED_DOMAINS=a.com, b.com``
        on commas without trimming, and exec-sandbox's DNS filter rejects
        entries with leading/trailing whitespace — normalize here so the
        natural comma-and-space spelling works.
        """
        return [domain.strip() for domain in value if domain and domain.strip()]

    @field_validator("sandbox_backend", mode="before")
    @classmethod
    def validate_sandbox_backend(cls, value):
        """Reject unknown backends at startup so a typo cannot silently disable sandboxing."""
        # Sourced from the sandbox module rather than repeated here: a second
        # hand-maintained list would let the two drift, and a name accepted by
        # only one of them either fails at startup or reaches a dispatch that
        # cannot serve it.
        from lfx.utils.sandbox import known_sandbox_backends

        normalized = str(value).strip().lower() if value is not None else "none"
        allowed = set(known_sandbox_backends())
        if normalized not in allowed:
            msg = f"sandbox_backend must be one of {sorted(allowed)}, got {value!r}"
            raise ValueError(msg)
        return normalized

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
