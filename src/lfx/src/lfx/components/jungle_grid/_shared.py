from __future__ import annotations

from lfx.io import FloatInput, MessageTextInput, MultilineInput, SecretStrInput

from ._client import DEFAULT_API_BASE_URL

ICON = "JungleGrid"
DOCUMENTATION_URL = "https://docs.langflow.org/bundles-jungle-grid"


def auth_inputs() -> list:
    return [
        SecretStrInput(
            name="api_key",
            display_name="Jungle Grid API Key",
            required=True,
            password=True,
            info="Scoped Jungle Grid API key. Keep this server-side and do not export it in public flows.",
        ),
        MessageTextInput(
            name="api_base_url",
            display_name="API Base URL",
            value=DEFAULT_API_BASE_URL,
            advanced=True,
            info="Jungle Grid API base URL. Defaults to the production API.",
        ),
    ]


def workload_inputs() -> list:
    return [
        MessageTextInput(
            name="name",
            display_name="Name",
            required=True,
            tool_mode=True,
            info="Name for the Jungle Grid workload.",
        ),
        MessageTextInput(
            name="image",
            display_name="Image",
            required=True,
            tool_mode=True,
            info="Container image for the workload.",
        ),
        MessageTextInput(
            name="workload_type",
            display_name="Workload Type",
            required=True,
            tool_mode=True,
            info="Documented Jungle Grid workload type.",
        ),
        FloatInput(
            name="model_size_gb",
            display_name="Model Size GB",
            required=True,
            tool_mode=True,
            info="Model size in GB used for Jungle Grid routing and estimation.",
        ),
        MessageTextInput(
            name="command",
            display_name="Command",
            advanced=True,
            tool_mode=True,
            info="Optional command for the workload.",
        ),
        MultilineInput(
            name="args",
            display_name="Args JSON",
            advanced=True,
            tool_mode=True,
            info='Optional JSON array of command arguments, for example ["--help"].',
        ),
        MessageTextInput(
            name="optimize_for",
            display_name="Optimize For",
            advanced=True,
            tool_mode=True,
            info="Optional documented Jungle Grid optimization target.",
        ),
    ]
