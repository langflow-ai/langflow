from typing import Optional

from fastapi import Depends
from sqlmodel import Session

from langflow.services.deps import get_session

from .model import Flow


def get_flow_by_id(session: Session = Depends(get_session), flow_id: Optional[str] = None) -> Flow | None:
    """Get flow by id."""

    if flow_id is None:
        raise ValueError("Flow id is required.")

    return session.get(Flow, flow_id)


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
