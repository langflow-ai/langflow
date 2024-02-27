from sqlmodel import select

from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import get_session, get_settings_service


def build_flow_info(flow):
    return {
        "id": flow.id,
        "name": flow.name,
        "description": flow.description,
        "created_at": flow.created_at,
        "updated_at": flow.updated_at,
    }


def get_slack_flows_info():
    settings = get_settings_service().settings
    slack_flow_ids = settings.SLACK_FLOW_IDS
    if not slack_flow_ids:
        return {}
    with next(get_session()) as session:
        flows = session.exec(select(Flow).where(Flow.id.in_(slack_flow_ids))).all()
        return {flow.id: build_flow_info(flow) for flow in flows}
