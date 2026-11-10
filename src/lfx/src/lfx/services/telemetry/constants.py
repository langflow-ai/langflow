from typing import Final

DEFAULT_SEGMENT_WRITE_KEY: Final = ""

IBM_PRODUCT_PROPERTIES: Final = {
    "UT30": "30AS5",
    "productCode": "WW3151",
    "productCodeType": "WWPC",
    "productPlanName": "opensource",
    "productPlanType": "freemium",
    "productTitle": "Langflow",
}

IBM_COMMON_EVENT_MAP: Final[dict[str, tuple[str, str | None]]] = {
    "version": ("Started Process", "Langflow"),
    "run": ("Ran Process", "Langflow Flow"),
    "deployment": ("Ran Process", "Langflow Deployment"),
    "integration_action": ("Ran Process", "Langflow Integration"),
    "deployment_provider": ("Ran Process", "Langflow Deployment Provider"),
    "deployment_run": ("Ran Process", "Langflow Deployment"),
    "shutdown": ("Ended Process", "Langflow"),
    "email": ("UI Interaction", None),
    "playground": ("Ran Process", "Langflow Playground"),
    "component": ("Ran Process", "Langflow Component"),
    "component_inputs": ("Ran Process", "Langflow Component Input"),
    "component_index": ("Ran Process", "Langflow Component Index"),
    "exception": ("Ended Process", "Langflow Exception"),
    "mcp_tool": ("Ran Process", "Langflow MCP Tool"),
}


def get_ibm_common_event(path: str | None) -> tuple[str, str | None, str]:
    legacy_event = path or "version"
    event, process_type = IBM_COMMON_EVENT_MAP.get(
        legacy_event,
        ("Ran Process", f"Langflow {legacy_event.replace('_', ' ').title()}"),
    )
    return event, process_type, legacy_event
