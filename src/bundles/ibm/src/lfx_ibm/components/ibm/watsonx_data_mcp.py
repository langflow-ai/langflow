"""IBM watsonx.data remote MCP server as an Agent toolset."""

from __future__ import annotations

import asyncio
from typing import Any

from lfx.base.mcp.preset import MCPPresetComponent, preset_control_inputs
from lfx.io import DropdownInput, SecretStrInput, StrInput
from lfx.utils.ssrf_protection import validate_connector_url_for_ssrf

# Tools documented for the watsonx.data remote MCP server (2.3.x).
WATSONX_DATA_MCP_TOOLS = [
    "LIST_DOCUMENT_LIBRARY",
    "QUERY_DOCUMENT_LIBRARY",
    "LIST_DOCUMENT_SET",
    "QUERY_DOCUMENT_SET",
    "LIST_DATA_ASSETS",
    "QUERY_DATA_ASSETS",
]

AUTH_BEARER = "bearer_token"
AUTH_IAM_API_KEY = "ibm_iam_apikey"  # pragma: allowlist secret -- option name, not a credential
AUTH_OPTIONS = [AUTH_BEARER, AUTH_IAM_API_KEY]

DEFAULT_IAM_URL = "https://iam.cloud.ibm.com"
MCP_PATH = "/api/v2/mcp/"


def require_https(url: str, label: str) -> str:
    """Return ``url`` if it is HTTPS, else raise.

    Every request this component makes carries a credential -- a bearer token to the MCP
    server, the IBM Cloud API key to IAM -- so plaintext HTTP is refused. SSRF validation
    gates *where* a request goes; it says nothing about protecting it in transit.
    """
    if not url.lower().startswith("https://"):
        msg = f"{label} must use https:// -- credentials are sent on every request. Got {url!r}."
        raise ValueError(msg)
    return url


def watsonx_data_mcp_url(instance_url: str) -> str:
    """Return ``https://<instance>/api/v2/mcp/`` for a watsonx.data instance URL."""
    base = (instance_url or "").strip()
    if not base:
        msg = "watsonx.data instance URL is required."
        raise ValueError(msg)
    if "://" not in base:
        base = f"https://{base}"
    require_https(base, "watsonx.data instance URL")
    base = base.rstrip("/")
    if base.endswith("/api/v2/mcp"):
        return base + "/"
    return base + MCP_PATH


def iam_bearer_token(api_key: str, iam_url: str = DEFAULT_IAM_URL) -> str:
    """Exchange an IBM Cloud IAM API key for a bearer token (SaaS)."""
    key = (api_key or "").strip()
    if not key:
        msg = "IBM Cloud API Key is required for ibm_iam_apikey authentication."
        raise ValueError(msg)
    url = (iam_url or DEFAULT_IAM_URL).strip() or DEFAULT_IAM_URL
    require_https(url, "IBM Cloud IAM URL")
    validate_connector_url_for_ssrf(url)
    from ibm_cloud_sdk_core.authenticators import IAMAuthenticator

    authenticator = IAMAuthenticator(apikey=key, url=url)
    token = authenticator.token_manager.get_token()
    if not token:
        msg = "IBM Cloud IAM did not return an access token."
        raise ValueError(msg)
    return token


class WatsonxDataMCPComponent(MCPPresetComponent):
    """Give an Agent governed access to watsonx.data document libraries and tables through MCP.

    The watsonx.data remote MCP server exposes ``LIST_/QUERY_DOCUMENT_LIBRARY``,
    ``LIST_/QUERY_DOCUMENT_SET`` and ``LIST_/QUERY_DATA_ASSETS`` (natural-language
    queries over selected Presto tables).  This component templates the
    ``/api/v2/mcp/`` endpoint from the instance URL, authenticates with a bearer
    token (or exchanges an IBM Cloud API key for one), and hands the tools to
    an Agent.
    """

    display_name = "IBM watsonx.data MCP"
    description = (
        "Give an Agent access to IBM watsonx.data document libraries, document sets, and data "
        "assets through the watsonx.data remote MCP server."
    )
    documentation: str = "https://docs.langflow.org/bundles-ibm"
    icon = "WatsonxData"
    name = "WatsonxDataMCP"
    metadata = {"keywords": ["ibm", "watsonx", "watsonx.data", "mcp", "document library", "lakehouse", "retrieval"]}

    inputs = [
        StrInput(
            name="instance_url",
            display_name="watsonx.data Instance URL",
            info="Base URL of the watsonx.data instance (the /api/v2/mcp/ path is appended automatically).",
            required=True,
        ),
        DropdownInput(
            name="auth_mode",
            display_name="Authentication",
            options=AUTH_OPTIONS,
            value=AUTH_BEARER,
            info=(
                "bearer_token: pass an access token as-is (IBM Cloud IAM token, or a CPD/Zen token for software). "
                "ibm_iam_apikey: exchange an IBM Cloud API key for a token before each connection."
            ),
            real_time_refresh=True,
        ),
        SecretStrInput(
            name="bearer_token",
            display_name="Bearer Token",
            info="Access token sent as Authorization: Bearer <token>.",
        ),
        SecretStrInput(
            name="api_key",
            display_name="IBM Cloud API Key",
            info="IBM Cloud IAM API key (ibm_iam_apikey authentication).",
            show=False,
        ),
        StrInput(
            name="iam_url",
            display_name="IAM Endpoint",
            info="IBM Cloud IAM token endpoint used for the API-key exchange.",
            value=DEFAULT_IAM_URL,
            advanced=True,
        ),
        StrInput(
            name="endpoint_override",
            display_name="Endpoint Override",
            info="Full MCP endpoint URL. Leave empty to build it from the instance URL.",
            advanced=True,
        ),
        *preset_control_inputs(
            WATSONX_DATA_MCP_TOOLS,
            tool_info=(
                "Tool to run for the Response output. In Tool Mode every server tool is exposed to the Agent. "
                "Use the refresh button to re-read the tool list from the server."
            ),
        ),
    ]

    # ------------------------------------------------------------ build cfg
    async def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        if field_name == "auth_mode":
            iam = field_value == AUTH_IAM_API_KEY
            if "api_key" in build_config:
                build_config["api_key"]["show"] = iam
            if "bearer_token" in build_config:
                build_config["bearer_token"]["show"] = not iam
            return build_config
        return await super().update_build_config(build_config, field_value, field_name)

    # ------------------------------------------------------------- helpers
    def endpoint_url(self) -> str:
        override = (getattr(self, "endpoint_override", "") or "").strip()
        url = override or watsonx_data_mcp_url(self.instance_url)
        require_https(url, "MCP endpoint")
        validate_connector_url_for_ssrf(url)
        return url

    async def _bearer(self) -> str:
        mode = getattr(self, "auth_mode", AUTH_BEARER) or AUTH_BEARER
        if mode == AUTH_IAM_API_KEY:
            # The IAM exchange is a blocking HTTP round-trip; keep it off the event loop.
            return await asyncio.to_thread(
                iam_bearer_token, getattr(self, "api_key", ""), getattr(self, "iam_url", DEFAULT_IAM_URL)
            )
        token = (getattr(self, "bearer_token", "") or "").strip()
        if not token:
            msg = "Bearer Token is required for bearer_token authentication."
            raise ValueError(msg)
        return token

    async def _mcp_server_config(self) -> tuple[str, dict[str, Any]]:
        url = self.endpoint_url()
        headers = {"Authorization": f"Bearer {await self._bearer()}"}
        return "watsonx-data-mcp", {
            "url": url,
            "headers": headers,
            "mode": "Streamable_HTTP",
            "verify_ssl": bool(getattr(self, "verify_ssl", True)),
        }
