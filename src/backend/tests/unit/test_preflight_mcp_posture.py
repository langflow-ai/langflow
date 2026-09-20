"""Production preflight reports MCP knobs left at a single-tenant default.

Eleven settings default to the permissive value. A multi-tenant serving plane has to
override all of them by hand and nothing tells the operator when one is missed, so the
first symptom is an incident rather than a boot message.
"""

from types import SimpleNamespace

import pytest
from langflow.cli.preflight import DEGRADED_CHECKS, REQUIRED_CHECKS, probe_mcp_posture

_HARDENED = {
    "mcp_server_enabled": True,
    "skip_mcp_auto_init": True,
    "add_projects_to_mcp_servers": False,
    "mcp_composer_enabled": False,
    "mcp_servers_locked": True,
    "mcp_sse_enabled": False,
    "mcp_server_interpreter_hardening": True,
    "mcp_server_docker_hardening": True,
    "ssrf_protection_enabled": True,
    "connector_ssrf_validation_enabled": True,
    "connector_ssrf_allow_loopback": False,
    "disable_track_apikey_usage": True,
    "mcp_server_allowed_packages": "",
    "mcp_server_env_allowlist": "",
}


def _service(**overrides):
    return SimpleNamespace(settings=SimpleNamespace(**{**_HARDENED, **overrides}))


@pytest.mark.asyncio
async def test_should_pass_when_fully_hardened():
    result = await probe_mcp_posture(_service())

    assert result.status == "ok"


@pytest.mark.asyncio
async def test_should_skip_when_mcp_server_is_disabled():
    """A plane that does not serve MCP has nothing to harden."""
    result = await probe_mcp_posture(_service(mcp_server_enabled=False, skip_mcp_auto_init=False))

    assert result.status == "ok"
    assert "disabled" in result.detail


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("override", "expected_env"),
    [
        ({"skip_mcp_auto_init": False}, "LANGFLOW_SKIP_MCP_AUTO_INIT"),
        ({"add_projects_to_mcp_servers": True}, "LANGFLOW_ADD_PROJECTS_TO_MCP_SERVERS"),
        ({"mcp_composer_enabled": True}, "LANGFLOW_MCP_COMPOSER_ENABLED"),
        ({"mcp_servers_locked": False}, "LANGFLOW_MCP_SERVERS_LOCKED"),
        ({"mcp_sse_enabled": True}, "LANGFLOW_MCP_SSE_ENABLED"),
        ({"connector_ssrf_allow_loopback": True}, "LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK"),
        ({"disable_track_apikey_usage": False}, "LANGFLOW_DISABLE_TRACK_APIKEY_USAGE"),
        ({"mcp_server_allowed_packages": None}, "LANGFLOW_MCP_SERVER_ALLOWED_PACKAGES"),
        ({"mcp_server_env_allowlist": None}, "LANGFLOW_MCP_SERVER_ENV_ALLOWLIST"),
    ],
)
async def test_should_name_each_permissive_setting(override, expected_env):
    """The operator needs the variable name, not just a count."""
    result = await probe_mcp_posture(_service(**override))

    assert result.status == "warn"
    assert expected_env in result.detail
    assert result.remediation


@pytest.mark.asyncio
async def test_should_report_every_permissive_setting_at_once():
    """Listing one at a time would make hardening an eleven-boot loop."""
    result = await probe_mcp_posture(_service(skip_mcp_auto_init=False, mcp_sse_enabled=True))

    assert result.status == "warn"
    assert "LANGFLOW_SKIP_MCP_AUTO_INIT" in result.detail
    assert "LANGFLOW_MCP_SSE_ENABLED" in result.detail


def test_should_register_as_degraded_not_required():
    """Promoting this to required would fail the boot of every existing prod deploy."""
    assert any(check.key == "mcp_posture" for check in DEGRADED_CHECKS)
    assert not any(check.key == "mcp_posture" for check in REQUIRED_CHECKS)
