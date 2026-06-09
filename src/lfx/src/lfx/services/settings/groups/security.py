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

    # Rate Limiting
    rate_limit_enabled: bool = True
    """Enable rate limiting for login endpoint. Set to False to disable (useful for testing)."""
    rate_limit_per_minute: int = 5
    """Number of login attempts allowed per minute per IP."""
    rate_limit_storage_uri: str = "memory://"
    """Storage backend for rate limiting. Use 'memory://' for single-server or 'redis://host:port' for multi-server."""
    rate_limit_trust_proxy: bool = False
    """Trust X-Forwarded-For header when behind a reverse proxy. Only enable when behind a trusted proxy."""

    @field_validator("cors_origins", mode="before")
    @classmethod
    def validate_cors_origins(cls, value):
        """Convert comma-separated string to list if needed."""
        if isinstance(value, str) and value != "*":
            if "," in value:
                return [origin.strip() for origin in value.split(",")]
            return [value]
        return value
