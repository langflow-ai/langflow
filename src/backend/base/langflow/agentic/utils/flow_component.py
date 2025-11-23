"""Flow component operations utilities for Langflow."""

from typing import Any
from uuid import UUID

from lfx.graph.graph.base import Graph
from lfx.log.logger import logger

from langflow.helpers.flow import get_flow_by_id_or_endpoint_name
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import session_scope


async def get_component_details(
    flow_id_or_name: str,
    component_id: str,
    user_id: str | UUID | None = None,
) -> dict[str, Any]:
    """Get detailed information about a specific component in a flow.

    Args:
        flow_id_or_name: Flow ID (UUID) or endpoint name.
        component_id: The component/vertex ID to retrieve.
        user_id: Optional user ID to filter flows.

    Returns:
        Dictionary containing component details:
        - component_id: The component ID
        - component_type: The type/class of the component
        - display_name: Display name of the component
        - description: Component description
        - template: Full template configuration with all fields
        - outputs: List of output definitions
        - inputs: List of input definitions
        - flow_id: The parent flow ID
        - flow_name: The parent flow name
        - error: Error message if component not found

    Example:
        >>> details = await get_component_details("my-flow", "ChatInput-abc123")
        >>> print(details["display_name"])
        >>> print(details["template"]["input_value"]["value"])
    """
    try:
        flow = await get_flow_by_id_or_endpoint_name(flow_id_or_name, user_id)

        if flow is None:
            return {
                "error": f"Flow {flow_id_or_name} not found",
                "flow_id": flow_id_or_name,
            }

        if flow.data is None:
            return {
                "error": f"Flow {flow_id_or_name} has no data",
                "flow_id": str(flow.id),
                "flow_name": flow.name,
            }

        # Create graph from flow data
        flow_id_str = str(flow.id)
        graph = Graph.from_payload(flow.data, flow_id=flow_id_str, flow_name=flow.name)

        # Get the vertex (component)
        try:
            vertex = graph.get_vertex(component_id)
        except ValueError:
            return {
                "error": f"Component {component_id} not found in flow {flow_id_or_name}",
                "flow_id": flow_id_str,
                "flow_name": flow.name,
            }

        # Get full component data
        component_data = vertex.to_data()

        # Carefully serialize the 'input_flow' key to avoid non-serializable Edge objects
        def serialize_edges(edges):
            return [
                {
                    "source": getattr(e, "source", None),
                    "target": getattr(e, "target", None),
                    "type": getattr(e, "type", None),
                    "id": getattr(e, "id", None),
                }
                for e in edges
            ]

        return {
            "component_id": vertex.id,
            "node": component_data.get("data", {}).get("node", {}),
            "component_type": component_data.get("data", {}).get("node", {}).get("type"),
            "display_name": component_data.get("data", {}).get("node", {}).get("display_name"),
            "description": component_data.get("data", {}).get("node", {}).get("description"),
            "template": component_data.get("data", {}).get("node", {}).get("template", {}),
            "outputs": component_data.get("data", {}).get("node", {}).get("outputs", []),
            "input_flow": serialize_edges(vertex.edges),
            "flow_id": flow_id_str,
            "flow_name": flow.name,
        }

    except Exception as e:  # noqa: BLE001
        await logger.aerror(f"Error getting component details for {component_id} in {flow_id_or_name}: {e}")
        return {
            "error": str(e),
            "flow_id": flow_id_or_name,
            "component_id": component_id,
        }


async def get_component_field_value(
    flow_id_or_name: str,
    component_id: str,
    field_name: str,
    user_id: str | UUID | None = None,
) -> dict[str, Any]:
    """Get the value of a specific field in a component.

    Args:
        flow_id_or_name: Flow ID (UUID) or endpoint name.
        component_id: The component/vertex ID.
        field_name: The name of the field to retrieve.
        user_id: Optional user ID to filter flows.

    Returns:
        Dictionary containing:
        - field_name: The field name
        - value: The current value of the field
        - field_type: The type of the field
        - component_id: The component ID
        - flow_id: The flow ID
        - error: Error message if field not found

    Example:
        >>> result = await get_component_field_value("my-flow", "ChatInput-abc", "input_value")
        >>> print(result["value"])
    """
    try:
        flow = await get_flow_by_id_or_endpoint_name(flow_id_or_name, user_id)

        if flow is None:
            return {"error": f"Flow {flow_id_or_name} not found"}

        if flow.data is None:
            return {"error": f"Flow {flow_id_or_name} has no data"}

        flow_id_str = str(flow.id)
        graph = Graph.from_payload(flow.data, flow_id=flow_id_str, flow_name=flow.name)

        try:
            vertex = graph.get_vertex(component_id)
        except ValueError:
            return {
                "error": f"Component {component_id} not found in flow {flow_id_or_name}",
                "flow_id": flow_id_str,
            }

        component_data = vertex.to_data()
        template = component_data.get("data", {}).get("node", {}).get("template", {})

        if field_name not in template:
            available_fields = list(template.keys())
            return {
                "error": f"Field {field_name} not found in component {component_id}",
                "available_fields": available_fields,
                "component_id": component_id,
                "flow_id": flow_id_str,
            }

        field_config = template[field_name]

        return {
            "field_name": field_name,
            "value": field_config.get("value"),
            "field_type": field_config.get("field_type") or field_config.get("_input_type"),
            "display_name": field_config.get("display_name"),
            "required": field_config.get("required", False),
            "component_id": component_id,
            "flow_id": flow_id_str,
            **field_config,
        }

    except Exception as e:  # noqa: BLE001
        await logger.aerror(f"Error getting field {field_name} from {component_id} in {flow_id_or_name}: {e}")
        return {"error": str(e)}


async def update_component_field_value(
    flow_id_or_name: str,
    component_id: str,
    field_name: str,
    new_value: Any,
    user_id: str | UUID,
) -> dict[str, Any]:
    """Update the value of a specific field in a component and persist to database.

    Args:
        flow_id_or_name: Flow ID (UUID) or endpoint name.
        component_id: The component/vertex ID.
        field_name: The name of the field to update.
        new_value: The new value to set.
        user_id: User ID (required for authorization).

    Returns:
        Dictionary containing:
        - success: Boolean indicating if update was successful
        - field_name: The field name that was updated
        - old_value: The previous value
        - new_value: The new value that was set
        - component_id: The component ID
        - flow_id: The flow ID
        - error: Error message if update failed

    Example:
        >>> result = await update_component_field_value(
        ...     "my-flow",
        ...     "ChatInput-abc",
        ...     "input_value",
        ...     "Hello, world!",
        ...     user_id="user-123"
        ... )
        >>> print(result["success"])
    """
    try:
        # Load the flow
        flow = await get_flow_by_id_or_endpoint_name(flow_id_or_name, user_id)

        if flow is None:
            return {"error": f"Flow {flow_id_or_name} not found", "success": False}

        if flow.data is None:
            return {"error": f"Flow {flow_id_or_name} has no data", "success": False}

        flow_id_str = str(flow.id)

        # Find the component in the flow data
        flow_data = flow.data.copy()
        nodes = flow_data.get("nodes", [])

        component_found = False
        old_value = None

        for node in nodes:
            if node.get("id") == component_id:
                component_found = True
                template = node.get("data", {}).get("node", {}).get("template", {})

                if field_name not in template:
                    available_fields = list(template.keys())
                    return {
                        "error": f"Field {field_name} not found in component {component_id}",
                        "available_fields": available_fields,
                        "success": False,
                    }

                old_value = template[field_name].get("value")
                template[field_name]["value"] = new_value
                break

        if not component_found:
            return {
                "error": f"Component {component_id} not found in flow {flow_id_or_name}",
                "success": False,
            }

        # Update the flow in the database
        async with session_scope() as session:
            # Get the database flow object
            db_flow = await session.get(Flow, UUID(flow_id_str))

            if not db_flow:
                return {"error": f"Flow {flow_id_str} not found in database", "success": False}

            # Verify user has permission
            if str(db_flow.user_id) != str(user_id):
                return {"error": "User does not have permission to update this flow", "success": False}

            # Update the flow data
            db_flow.data = flow_data
            session.add(db_flow)
            await session.commit()
            await session.refresh(db_flow)

    except Exception as e:  # noqa: BLE001
        await logger.aerror(f"Error updating field {field_name} in {component_id} of {flow_id_or_name}: {e}")
        return {"error": str(e), "success": False}
    else:
        return {
            "success": True,
            "field_name": field_name,
            "old_value": old_value,
            "new_value": new_value,
            "component_id": component_id,
            "flow_id": flow_id_str,
            "flow_name": flow.name,
        }
    finally:
        await logger.ainfo("Updating field value completed")


async def list_component_fields(
    flow_id_or_name: str,
    component_id: str,
    user_id: str | UUID | None = None,
) -> dict[str, Any]:
    """List all available fields in a component with their current values.

    Args:
        flow_id_or_name: Flow ID (UUID) or endpoint name.
        component_id: The component/vertex ID.
        user_id: Optional user ID to filter flows.

    Returns:
        Dictionary containing:
        - component_id: The component ID
        - flow_id: The flow ID
        - fields: Dictionary of field_name -> field_info
        - field_count: Number of fields
        - error: Error message if component not found

    Example:
        >>> result = await list_component_fields("my-flow", "ChatInput-abc")
        >>> for field_name, field_info in result["fields"].items():
        ...     print(f"{field_name}: {field_info['value']}")
    """
    try:
        flow = await get_flow_by_id_or_endpoint_name(flow_id_or_name, user_id)

        if flow is None:
            return {"error": f"Flow {flow_id_or_name} not found"}

        if flow.data is None:
            return {"error": f"Flow {flow_id_or_name} has no data"}

        flow_id_str = str(flow.id)
        graph = Graph.from_payload(flow.data, flow_id=flow_id_str, flow_name=flow.name)

        try:
            vertex = graph.get_vertex(component_id)
        except ValueError:
            return {
                "error": f"Component {component_id} not found in flow {flow_id_or_name}",
                "flow_id": flow_id_str,
            }

        component_data = vertex.to_data()
        template = component_data.get("data", {}).get("node", {}).get("template", {})

        # Build field info dictionary
        fields_info = {}
        for field_name, field_config in template.items():
            fields_info[field_name] = {
                "value": field_config.get("value"),
                "field_type": field_config.get("field_type") or field_config.get("_input_type"),
                "display_name": field_config.get("display_name"),
                "required": field_config.get("required", False),
                "advanced": field_config.get("advanced", False),
                "show": field_config.get("show", True),
            }

        return {
            "component_id": component_id,
            "component_type": component_data.get("data", {}).get("node", {}).get("type"),
            "display_name": component_data.get("data", {}).get("node", {}).get("display_name"),
            "flow_id": flow_id_str,
            "flow_name": flow.name,
            "fields": fields_info,
            "field_count": len(fields_info),
        }

    except Exception as e:  # noqa: BLE001
        await logger.aerror(f"Error listing fields for {component_id} in {flow_id_or_name}: {e}")
        return {"error": str(e)}
