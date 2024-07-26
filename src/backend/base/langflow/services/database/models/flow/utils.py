from typing import Optional

from fastapi import Depends
from sqlmodel import Session
from sqlalchemy import delete

from langflow.services.deps import get_session

from .model import Flow
from .. import TransactionTable, MessageTable
from loguru import logger


def get_flow_by_id(session: Session = Depends(get_session), flow_id: Optional[str] = None) -> Flow | None:
    """Get flow by id."""

    if flow_id is None:
        raise ValueError("Flow id is required.")

    return session.get(Flow, flow_id)


def delete_flow_by_id(flow_id: str, session: Session) -> None:
    """Delete flow by id."""
    # Manually delete flow, transactions and messages because foreign key constraints might be disabled
    session.exec(delete(Flow).where(Flow.id == flow_id))  # type: ignore
    session.exec(delete(TransactionTable).where(TransactionTable.flow_id == flow_id))  #  type: ignore
    session.exec(delete(MessageTable).where(MessageTable.flow_id == flow_id))  #  type: ignore
    logger.info(f"Deleted flow {flow_id}")


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
