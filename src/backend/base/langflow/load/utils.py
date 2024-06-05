import httpx


def upload(file_path, host, port, flow_id):
    """
    Upload a file to the storage service and return the file path.

    Args:
        file_path (str): The path to the file to be uploaded.
        host (str): The host URL of the storage service.
        port (int): The port number of the storage service.
        flow_id (UUID): The ID of the flow to which the file belongs.

    Returns:
        dict: A dictionary containing the file path.

    Raises:
        Exception: If an error occurs during the upload process.
    """
    try:
        url = f"{host}:{port}/api/v1/upload/{flow_id}"
        response = httpx.post(url, files={"file": open(file_path, "rb")})
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Error uploading file: {response.status_code}")
    except Exception as e:
        raise Exception(f"Error uploading file: {e}")


def upload_file(file_path, host, port, flow_id, components, tweaks={}):
    """
    Upload a file to the storage service and return the file path.

    Args:
        file_path (str): The path to the file to be uploaded.
        host (str): The host URL of the storage service.
        port (int): The port number of the storage service.
        flow_id (UUID): The ID of the flow to which the file belongs.
        components (str): List of component IDs or names that need the file.
        tweaks (dict): A dictionary of tweaks to be applied to the file.

    Returns:
        dict: A dictionary containing the file path and any tweaks that were applied.

    Raises:
        Exception: If an error occurs during the upload process.
    """
    try:
        response = upload(file_path, host, port, flow_id)
        if response["file_path"]:
            for component in components:
                if isinstance(component, str):
                    tweaks[component] = {"file_path": response["file_path"]}
                else:
                    raise ValueError(f"Component ID or name must be a string. Got {type(component)}")
            return tweaks
        else:
            raise ValueError("Error uploading file")
    except Exception as e:
        raise ValueError(f"Error uploading file: {e}")
