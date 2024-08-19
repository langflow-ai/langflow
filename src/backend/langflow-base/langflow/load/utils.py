import httpx

from langflow.services.database.models.flow.model import FlowBase


def upload(file_path, host, flow_id):
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
        with open(file_path, "rb") as file:
            response = httpx.post(url, files={"file": file})
            if response.status_code == 200 or response.status_code == 201:
                return response.json()
            else:
                raise Exception(f"Error uploading file: {response.status_code}")
    except Exception as e:
        raise Exception(f"Error uploading file: {e}")


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
                    raise ValueError(f"Component ID or name must be a string. Got {type(component)}")
            return tweaks
        else:
            raise ValueError("Error uploading file")
    except Exception as e:
        raise ValueError(f"Error uploading file: {e}")


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
        if response.status_code == 200:
            json_response = response.json()
            flow = FlowBase(**json_response).model_dump()
            return flow
        else:
            raise Exception(f"Error retrieving flow: {response.status_code}")
    except Exception as e:
        raise Exception(f"Error retrieving flow: {e}")
