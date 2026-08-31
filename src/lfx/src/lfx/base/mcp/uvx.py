"""Shared argv helpers for MCP servers that Langflow launches through ``uvx``.

``uvx`` builds a fresh environment per invocation, so Langflow's own ``mcp`` pin never
reaches the server it spawns. The packages Langflow launches (``mcp-proxy``,
``mcp-composer``) declare an unbounded ``mcp>=1.x``, which now resolves to the 2.0 SDK --
a release that removed ``request_ctx`` and renamed ``McpError``, so those packages fail
at import. Injecting the constraint as ``--with`` keeps the resolve on a compatible SDK.
"""

# ``~=1.28`` is PEP 440 for ">=1.28, <2.0" and, unlike ``mcp<2.0.0``, contains no character
# that the stdio command policy rejects as a shell metacharacter.
DEFAULT_MCP_SDK_CONSTRAINT = "mcp~=1.28"


def mcp_sdk_constraint_args() -> list[str]:
    """Return the ``uvx --with`` pair that pins the MCP SDK, or an empty list when disabled.

    The result is meant to be spliced in ahead of the package operand::

        ["uvx", *mcp_sdk_constraint_args(), "mcp-proxy", ...]

    Operators disable the injection by setting ``LANGFLOW_MCP_SDK_CONSTRAINT`` to an empty
    string once upstream supports the 2.x SDK.
    """
    constraint = _configured_constraint()
    if not constraint:
        return []
    return ["--with", constraint]


def _configured_constraint() -> str:
    from lfx.services.deps import get_settings_service

    try:
        value = getattr(get_settings_service().settings, "mcp_sdk_constraint", DEFAULT_MCP_SDK_CONSTRAINT)
    except Exception:  # noqa: BLE001 - settings can be unavailable during early imports
        return DEFAULT_MCP_SDK_CONSTRAINT
    if not isinstance(value, str):
        return DEFAULT_MCP_SDK_CONSTRAINT
    return value.strip()
