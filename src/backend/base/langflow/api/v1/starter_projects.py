from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from langflow.api.utils import CurrentActiveUser
from langflow.services.deps import get_catalog_policy_service

router = APIRouter(prefix="/starter-projects", tags=["Flows"])


# Pydantic models for API schema compatibility
class ViewPort(BaseModel):
    x: float
    y: float
    zoom: float


class NodeData(BaseModel):
    # This is a simplified version - the actual NodeData has many more fields
    # but we only need the basic structure for the API schema
    model_config = {"extra": "allow"}  # Allow extra fields


class EdgeData(BaseModel):
    # This is a simplified version - the actual EdgeData has many more fields
    # but we only need the basic structure for the API schema
    model_config = {"extra": "allow"}  # Allow extra fields


class GraphData(BaseModel):
    nodes: list[dict[str, Any]]  # Use dict to be flexible with the complex NodeData structure
    edges: list[dict[str, Any]]  # Use dict to be flexible with the complex EdgeData structure
    viewport: ViewPort | None = None


class GraphDumpResponse(BaseModel):
    data: GraphData
    is_component: bool | None = None
    name: str | None = None
    name_key: str
    description: str | None = None
    endpoint_name: str | None = None


@router.get("/", status_code=200)
async def get_starter_projects(
    request: Request,
    current_user: CurrentActiveUser,
    *,
    include_blocked: bool = False,
) -> list[GraphDumpResponse]:
    """Get a list of starter projects."""
    from langflow.initial_setup.load import get_starter_projects_dump
    from langflow.utils.i18n import translate_flow_notes

    if include_blocked and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only superusers can include blocked catalog templates.")

    catalog_policy_snapshot = get_catalog_policy_service().snapshot
    locale = getattr(request.state, "locale", "en")

    try:
        # Get the raw data from lfx GraphDump
        raw_data = get_starter_projects_dump()

        # Convert TypedDict GraphDump to Pydantic GraphDumpResponse
        results = []
        for item in raw_data:
            name_key = item.get("name_key")
            if not isinstance(name_key, str):
                continue
            if not include_blocked and catalog_policy_snapshot.is_template_blocked(name_key):
                continue

            nodes = item.get("data", {}).get("nodes", [])
            translated_nodes = translate_flow_notes(nodes, locale)

            # Create GraphData
            graph_data = GraphData(
                nodes=translated_nodes,
                edges=item.get("data", {}).get("edges", []),
                viewport=item.get("data", {}).get("viewport"),
            )

            # Create GraphDumpResponse
            graph_dump = GraphDumpResponse(
                data=graph_data,
                is_component=item.get("is_component"),
                name=item.get("name"),
                name_key=name_key,
                description=item.get("description"),
                endpoint_name=item.get("endpoint_name"),
            )
            results.append(graph_dump)

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return results
