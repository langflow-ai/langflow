from langflow.utils.version import get_version_info

from .model import Flow


def get_webhook_component_in_flow(flow_data: dict):
    """Get webhook component in flow data."""
    for node in flow_data.get("nodes", []):
        if "Webhook" in node.get("id"):
            return node
    return None


def get_all_webhook_components_in_flow(flow_data: dict | None):
    """Get all webhook components in flow data."""
    if not flow_data:
        return []
    return [node for node in flow_data.get("nodes", []) if "Webhook" in node.get("id")]


def get_components_versions(flow: Flow):
    versions: dict[str, str] = {}
    if flow.data is None:
        return versions
    nodes = flow.data.get("nodes", [])
    for node in nodes:
        data = node.get("data", {})
        data_node = data.get("node", {})
        if "lf_version" in data_node:
            versions[node["id"]] = data_node["lf_version"]
    return versions


def get_outdated_components(flow: Flow):
    component_versions = get_components_versions(flow)
    lf_version = get_version_info()["version"]
    outdated_components = []
    for key, value in component_versions.items():
        if value != lf_version:
            outdated_components.append(key)
    return outdated_components
