import httpx
from lfx.load.utils import UploadError, replace_tweaks_with_env, upload, upload_file

from langflow.services.database.models.flow.model import FlowBase

GET_FLOW_TIMEOUT = 30.0
# Cap how much of an error response body is embedded in the raised UploadError
# so a large upstream error page (e.g. an HTML 500) can't bloat logs/messages.
GET_FLOW_ERROR_BODY_LIMIT = 500


def get_flow(url: str, flow_id: str):
    """Get the details of a flow from Langflow.

    Args:
        url (str): The host URL of Langflow.
        port (int): The port number of Langflow.
        flow_id (UUID): The ID of the flow to retrieve.

    Returns:
        dict: A dictionary containing the details of the flow.

    Raises:
        UploadError: If an error occurs during the retrieval process.
    """
    try:
        flow_url = f"{url}/api/v1/flows/{flow_id}"
        response = httpx.get(flow_url, timeout=GET_FLOW_TIMEOUT)
        if response.status_code == httpx.codes.OK:
            json_response = response.json()
            return FlowBase(**json_response).model_dump()
        response_text = response.text or ""
        msg = f"Error retrieving flow: {response.status_code}"
        if response_text:
            truncated = response_text[:GET_FLOW_ERROR_BODY_LIMIT]
            if len(response_text) > GET_FLOW_ERROR_BODY_LIMIT:
                truncated = f"{truncated}... (truncated)"
            msg = f"{msg} - {truncated}"
        raise UploadError(msg)
    except UploadError:
        raise
    except httpx.TimeoutException as e:
        msg = f"Error retrieving flow: request timed out after {GET_FLOW_TIMEOUT}s"
        raise UploadError(msg) from e
    except Exception as e:
        msg = f"Error retrieving flow: {e}"
        raise UploadError(msg) from e


__all__ = ["UploadError", "get_flow", "replace_tweaks_with_env", "upload", "upload_file"]
