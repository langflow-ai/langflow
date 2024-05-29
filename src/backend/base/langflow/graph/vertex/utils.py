from typing import TYPE_CHECKING

from loguru import logger

from langflow.services.deps import get_monitor_service

if TYPE_CHECKING:
    from langflow.graph.vertex.base import Vertex


def build_clean_params(target: "Vertex") -> dict:
    """
    Cleans the parameters of the target vertex.
    """
    # Removes all keys that the values aren't python types like str, int, bool, etc.
    params = {
        key: value for key, value in target.params.items() if isinstance(value, (str, int, bool, float, list, dict))
    }
    # if it is a list we need to check if the contents are python types
    for key, value in params.items():
        if isinstance(value, list):
            params[key] = [item for item in value if isinstance(item, (str, int, bool, float, list, dict))]
    return params


def log_transaction(source: "Vertex", target: "Vertex", flow_id, status, error=None):
    """
    Logs a transaction between two vertices.

    Args:
        source (Vertex): The source vertex of the transaction.
        target (Vertex): The target vertex of the transaction.
        status: The status of the transaction.
        error (Optional): Any error associated with the transaction.

    Raises:
        Exception: If there is an error while logging the transaction.

    """
    try:
        monitor_service = get_monitor_service()
        clean_params = build_clean_params(target)
        data = {
            "source": source.vertex_type,
            "target": target.vertex_type,
            "target_args": clean_params,
            "timestamp": monitor_service.get_timestamp(),
            "status": status,
            "error": error,
            "flow_id": flow_id,
        }
        monitor_service.add_row(table_name="transactions", data=data)
    except Exception as e:
        logger.error(f"Error logging transaction: {e}")
