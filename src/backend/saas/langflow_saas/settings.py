"""All SaaS configuration, driven entirely by environment variables.

Every setting has a safe default so the plugin works out-of-the-box in
development with zero extra configuration.  In production, set the variables
that are relevant to your deployment (billing, email, Redis, etc.).

Prefix: SAAS_   (e.g. SAAS_REDIS_URL, SAAS_STRIPE_SECRET_KEY)
"""

from __future__ import annotations

import os

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class SaaSSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SAAS_",
        env_file=".env",
        extra="ignore",
        populate_by_name=True,
    )

    # ------------------------------------------------------------------
    # Database
    # Falls back to Langflow's own DB URL so no extra config is needed
    # in single-DB setups.
    # ------------------------------------------------------------------
    database_url: str = Field(
        default_factory=lambda: os.getenv("LANGFLOW_DATABASE_URL", "sqlite:///./langflow.db"),
        description="DB URL for SaaS tables (defaults to LANGFLOW_DATABASE_URL).",
    )

    # ------------------------------------------------------------------
    # Redis (rate limiting + usage counters)
    # ------------------------------------------------------------------
    redis_url: str = Field(default="redis://localhost:6379/1")
    redis_enabled: bool = Field(default=True)

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------
    rate_limit_enabled: bool = Field(default=True)
    rate_limit_default_rpm: int = Field(default=60, description="Requests per minute per user (default plan).")
    rate_limit_burst_multiplier: int = Field(default=2, description="Burst capacity = rpm * multiplier.")
    # Path prefixes to apply rate limiting to.
    rate_limit_paths: list[str] = Field(default=["/api/v1/", "/api/v2/", "/api/saas/"])

    # ------------------------------------------------------------------
    # Email
    # ------------------------------------------------------------------
    email_provider: str = Field(
        default="console",
        description="Email backend: console | smtp | sendgrid | resend",
    )
    email_from: str = Field(default="noreply@example.com")
    email_from_name: str = Field(default="Langflow")
    # SMTP
    smtp_host: str = Field(default="localhost")
    smtp_port: int = Field(default=587)
    smtp_starttls: bool = Field(default=True)
    smtp_user: str = Field(default="")
    smtp_password: SecretStr = Field(default=SecretStr(""))
    # SendGrid
    sendgrid_api_key: SecretStr = Field(default=SecretStr(""))
    # Resend
    resend_api_key: SecretStr = Field(default=SecretStr(""))

    # ------------------------------------------------------------------
    # Billing (Stripe)
    # ------------------------------------------------------------------
    billing_enabled: bool = Field(default=False)
    stripe_secret_key: SecretStr = Field(default=SecretStr(""))
    stripe_webhook_secret: SecretStr = Field(default=SecretStr(""))
    stripe_publishable_key: str = Field(default="")

    # ------------------------------------------------------------------
    # Invitations
    # ------------------------------------------------------------------
    invitation_expire_hours: int = Field(default=48)
    app_base_url: str = Field(
        default_factory=lambda: os.getenv("LANGFLOW_BASE_URL", "http://localhost:7860"),
        description="Public base URL used in invitation/reset email links.",
    )
    invitation_secret: SecretStr = Field(
        default_factory=lambda: SecretStr(os.getenv("SAAS_INVITATION_SECRET", "change-me-in-production")),
        description="Secret for signing invitation tokens.",
    )

    # ------------------------------------------------------------------
    # Multi-tenancy behaviour
    # ------------------------------------------------------------------
    auto_create_personal_org: bool = Field(
        default=True,
        description="Automatically create a personal org when a new Langflow user is created.",
    )
    require_org_header: bool = Field(
        default=False,
        description="Reject API calls that don't include X-Org-ID when the user belongs to multiple orgs.",
    )

    # ------------------------------------------------------------------
    # Default plan quotas (used before billing is set up)
    # ------------------------------------------------------------------
    default_max_flows: int = Field(default=50)
    default_max_executions_per_day: int = Field(default=1000)
    default_max_members: int = Field(default=5)
    default_max_storage_mb: int = Field(default=500)


_settings: SaaSSettings | None = None


def get_saas_settings() -> SaaSSettings:
    global _settings
    if _settings is None:
        _settings = SaaSSettings()
    return _settings
