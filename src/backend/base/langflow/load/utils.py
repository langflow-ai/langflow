from pathlib import Path

import httpx

from langflow.services.database.models.flow.model import FlowBase


def upload(file_path: str, host: str, flow_id: str):
    """
    Upload a file to Langflow and return the file path.

    Args:
        file_path (str): The path to the file to be uploaded.
        host (str): The host URL of Langflow.
        flow_id (UUID): The ID of the flow to which the file belongs.

    Returns:
        dict: A dictionary containing the file path.

    Raises:
        Exception: If an error occurs during the upload process.
    """
    try:
        url = f"{host}/api/v1/upload/{flow_id}"
        with Path(file_path).open("rb") as file:
            response = httpx.post(url, files={"file": file})
            if response.status_code in (httpx.codes.OK, httpx.codes.CREATED):
                return response.json()
            msg = f"Error uploading file: {response.status_code}"
            raise Exception(msg)
    except Exception as e:
        msg = f"Error uploading file: {e}"
        raise Exception(msg) from e


def upload_file(file_path: str, host: str, flow_id: str, components: list[str], tweaks: dict | None = None):
    """
    Upload a file to Langflow and return the file path.

    Args:
        file_path (str): The path to the file to be uploaded.
        host (str): The host URL of Langflow.
        port (int): The port number of Langflow.
        flow_id (UUID): The ID of the flow to which the file belongs.
        components (str): List of component IDs or names that need the file.
        tweaks (dict): A dictionary of tweaks to be applied to the file.

    Returns:
        dict: A dictionary containing the file path and any tweaks that were applied.

    Raises:
        Exception: If an error occurs during the upload process.
    """
    if not tweaks:
        tweaks = {}
    try:
        response = upload(file_path, host, flow_id)
        if response["file_path"]:
            for component in components:
                if isinstance(component, str):
                    tweaks[component] = {"path": response["file_path"]}
                else:
                    msg = f"Component ID or name must be a string. Got {type(component)}"
                    raise ValueError(msg)
            return tweaks
        msg = "Error uploading file"
        raise ValueError(msg)
    except Exception as e:
        msg = f"Error uploading file: {e}"
        raise ValueError(msg) from e


def get_flow(url: str, flow_id: str):
    """Get the details of a flow from Langflow.

    Args:
        url (str): The host URL of Langflow.
        port (int): The port number of Langflow.
        flow_id (UUID): The ID of the flow to retrieve.

    Returns:
        dict: A dictionary containing the details of the flow.

    Raises:
        Exception: If an error occurs during the retrieval process.
    """
    try:
        flow_url = f"{url}/api/v1/flows/{flow_id}"
        response = httpx.get(flow_url)
        if response.status_code == httpx.codes.OK:
            json_response = response.json()
            return FlowBase(**json_response).model_dump()
        msg = f"Error retrieving flow: {response.status_code}"
        raise Exception(msg)
    except Exception as e:
        msg = f"Error retrieving flow: {e}"
        raise Exception(msg) from e
