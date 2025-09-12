from pathlib import Path

import httpx


class UploadError(Exception):
    """Raised when an error occurs during the upload process."""


def upload(file_path: str, host: str, flow_id: str):
    """Upload a file to Langflow and return the file path.

    Args:
        file_path (str): The path to the file to be uploaded.
        host (str): The host URL of Langflow.
        flow_id (UUID): The ID of the flow to which the file belongs.

    Returns:
        dict: A dictionary containing the file path.

    Raises:
        UploadError: If an error occurs during the upload process.
    """
    try:
        url = f"{host}/api/v1/upload/{flow_id}"
        with Path(file_path).open("rb") as file:
            response = httpx.post(url, files={"file": file})
            if response.status_code in {httpx.codes.OK, httpx.codes.CREATED}:
                return response.json()
    except Exception as e:
        msg = f"Error uploading file: {e}"
        raise UploadError(msg) from e

    msg = f"Error uploading file: {response.status_code}"
    raise UploadError(msg)


def upload_file(file_path: str, host: str, flow_id: str, components: list[str], tweaks: dict | None = None):
    """Upload a file to Langflow and return the file path.

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
        UploadError: If an error occurs during the upload process.
    """
    try:
        response = upload(file_path, host, flow_id)
    except Exception as e:
        msg = f"Error uploading file: {e}"
        raise UploadError(msg) from e

    if not tweaks:
        tweaks = {}
    if response["file_path"]:
        for component in components:
            if isinstance(component, str):
                tweaks[component] = {"path": response["file_path"]}
            else:
                msg = f"Error uploading file: component ID or name must be a string. Got {type(component)}"
                raise UploadError(msg)
        return tweaks

    msg = "Error uploading file"
    raise UploadError(msg)


def replace_tweaks_with_env(tweaks: dict, env_vars: dict) -> dict:
    """Replace keys in the tweaks dictionary with their corresponding environment variable values.

    This function recursively traverses the tweaks dictionary and replaces any string keys
    with their values from the provided environment variables. If a key's value is a dictionary,
    the function will call itself to handle nested dictionaries.

    Args:
        tweaks (dict): A dictionary containing keys that may correspond to environment variable names.
        env_vars (dict): A dictionary of environment variables where keys are variable names
                         and values are their corresponding values.

    Returns:
        dict: The updated tweaks dictionary with keys replaced by their environment variable values.
    """
    for key, value in tweaks.items():
        if isinstance(value, dict):
            # Recursively replace in nested dictionaries
            tweaks[key] = replace_tweaks_with_env(value, env_vars)
        elif isinstance(value, str):
            env_value = env_vars.get(value)  # Get the value from the provided environment variables
            if env_value is not None:
                tweaks[key] = env_value
    return tweaks
