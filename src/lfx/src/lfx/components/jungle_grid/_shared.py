from __future__ import annotations

from lfx.io import DropdownInput, MessageTextInput, MultilineInput, SecretStrInput

from ._client import DEFAULT_API_BASE_URL, ROUTING_MODES, WORKLOAD_TYPES

ICON = "JungleGrid"
DOCUMENTATION_URL = "https://docs.langflow.org/bundles-jungle-grid"


def auth_inputs() -> list:
    """Build the shared server-side Jungle Grid credential inputs."""
    return [
        SecretStrInput(
            name="api_key",
            display_name="Jungle Grid API Key",
            required=True,
            password=True,
            info="Scoped Jungle Grid API key. It is sent only in the server-side Authorization header.",
        ),
        MessageTextInput(
            name="api_base_url",
            display_name="API Base URL",
            value=DEFAULT_API_BASE_URL,
            advanced=True,
            info="Path-free HTTPS Jungle Grid API origin. Defaults to production.",
        ),
    ]


def workload_type_input() -> DropdownInput:
    """Build the canonical workload-type selector."""
    return DropdownInput(
        name="workload_type",
        display_name="Workload Type",
        options=list(WORKLOAD_TYPES),
        value="inference",
        required=True,
        tool_mode=True,
    )


def routing_mode_input() -> DropdownInput:
    """Build the optional routing-mode selector."""
    return DropdownInput(
        name="routing_mode",
        display_name="Routing Mode",
        options=["", *ROUTING_MODES],
        value="",
        advanced=True,
        tool_mode=True,
        info="Optional routing preference: cost, speed, or balanced.",
    )


def command_input() -> MultilineInput:
    """Build the command input using the preferred JSON-array representation."""
    return MultilineInput(
        name="command",
        display_name="Command JSON",
        advanced=True,
        tool_mode=True,
        info=(
            'Preferred JSON array, for example ["python", "/workspace/scripts/run.py"]. '
            "Legacy command strings remain supported."
        ),
    )


def args_input() -> MultilineInput:
    """Build the optional JSON command-argument input."""
    return MultilineInput(
        name="args",
        display_name="Args JSON",
        advanced=True,
        tool_mode=True,
        info="Optional JSON array of additional command arguments. An explicit [] is preserved.",
    )
