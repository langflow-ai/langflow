
import hashlib
import re
from copy import deepcopy
from datetime import datetime
from typing import Any

import orjson
from botocore.exceptions import (
    ClientError,
    NoCredentialsError,
)
from botocore.exceptions import (
    ConnectionError as BotoConnectionError,
)
from fastapi import HTTPException, status
from lfx.log import logger
from pydantic import ValidationError

from langflow.services.database.models.base import orjson_dumps
from langflow.services.publish.schema import FlowBlob, IDType, ProjectBlob


########################################################
# normalize the publish backend key prefix
########################################################
def add_trailing_slash(s):
    return s + "/" if (s and not s.endswith("/")) else s


VERSION_PATTERN = re.compile(r"versions/([^/]+)\.json$")
def parse_blob_key(key: str, last_modified: datetime | None, cls) -> Any:
    """Extracts the version ID from the S3 object key to return a metadata object."""
    match = VERSION_PATTERN.search(key)
    version_id = match.group(1) if match else key # fallback to the full key if no match
    return cls(version_id=version_id, last_modified=last_modified)


########################################################
# validation
########################################################
MISSING_BUCKET_NAME_MSG = "Publish backend bucket name not specified"
MISSING_ALL_ID_MSG = "user_id and {item_type}_id are required."
MISSING_ITEM_MSG = "{item} is missing or empty."
INVALID_KEY_MSG = "Flow or Project Key is invalid or missing."


def require_bucket_name(bucket_name: str | None):
    """Raises a ValueError if the bucket name is None or empty."""
    if not (bucket_name and bucket_name.strip()):
        raise ValueError(MISSING_BUCKET_NAME_MSG)


def require_all_ids(
    user_id: IDType,
    item_id: IDType,
    item_type: str
    ):
    """Raises a ValueError if the user or item id is None or empty."""
    if not (user_id and item_id):
        raise ValueError(MISSING_ALL_ID_MSG.format(item_type=item_type))


def require_publish_key(key: str | None):
    """Raises a ValueError if the key is None or empty."""
    if not key:
        raise ValueError(MISSING_ITEM_MSG.format(item="Publish key"))


def validate_flow_blob(
    flow_data_str: str,
    *,
    detail: str,
    use_http_exception: bool = True,
) -> FlowBlob:
    try:
        return FlowBlob.model_validate(orjson.loads(flow_data_str))
    except ValidationError as exc:
        if use_http_exception:
            raise HTTPException(status_code=500, detail=detail) from exc
        raise ValueError(detail) from exc


def validate_project_blob(
    project_blob_str: str,
    *,
    detail: str,
    use_http_exception: bool = True,
) -> ProjectBlob:
    try:
        return ProjectBlob.model_validate(orjson.loads(project_blob_str))
    except ValidationError as exc:
        if use_http_exception:
            raise HTTPException(status_code=500, detail=detail) from exc
        raise ValueError(detail) from exc


def validate_all(
    bucket_name: str | None,
    user_id: IDType,
    item_id: IDType,
    item_type: str,
    ):
    """Validate all required parameters for publish operations.

    Args:
        bucket_name (str | None): The name of the S3 bucket.
        user_id (IDType): The unique identifier of the user.
        item_id (IDType): The unique identifier of the item (e.g., flow ID, project ID).
        item_type (str): The type of the item being processed (e.g., 'flow').

    Raises:
        ValueError: If bucket_name or IDs are missing.
    """
    require_bucket_name(bucket_name)
    require_all_ids(user_id, item_id, item_type)


########################################################
# normalization for version comparison
########################################################
# keys to remove when comparing flows versions
EXCLUDE_NODE_KEYS = {
    # "position" # should we consider changes to node position as a meaningful change or not?
    "selected",
    "dragging",
    "positionAbsolute",
    "measured",
    "resizing",
    "width",
    "height",
    ("data", "node", "last_updated"), # nested
    ("data", "node", "lf_version"), # should we update starter projects?
    ("data", "node", "outputs", "hidden"),
    }
EXCLUDE_EDGE_KEYS = {
    "id",
    "selected",
    "animated",
    "className",
    "style",
    }


def normalized_flow_data(flow_data: dict | None):
    """Filters a deepcopy of flow data to exclude transient state."""
    copy_flow_data = deepcopy(flow_data) # prevent modifying blob
    if copy_flow_data:
        try:
            copy_flow_data.pop("viewport", None)
            copy_flow_data.pop("chatHistory", None)
            remove_keys_from_dicts(copy_flow_data["nodes"], EXCLUDE_NODE_KEYS)
            remove_keys_from_dicts(copy_flow_data["edges"], EXCLUDE_EDGE_KEYS)
        except Exception as e: # noqa: BLE001
            logger.error(f"failed to filter flow contents: {e!s}")
            # don't want to block publishing, so nothing gets raised here
    return copy_flow_data


def remove_keys_from_dicts(dictlist : list[dict], exclude_keys : set):
    """Remove a set of keys from each dictionary in a list in-place."""
    for d in dictlist:
        for key in exclude_keys:
            if key and isinstance(key, tuple):
                pop_nested(d, key)
            else:
                d.pop(key, None)


def pop_nested(d: dict, keys: tuple):
    """Removes the nested keys from the dictionary."""
    cur = d # walk down until second last key
    for i in range(len(keys) - 1):
        cur = cur.get(keys[i], {})
    if isinstance(cur, list): # last key is in a list of dicts
        for _d in cur:
            _d.pop(keys[-1], None)
    else: # dict
        cur.pop(keys[-1], None)


def compute_flow_hash(graph_data: dict) -> str:
    """Returns the SHA256 of the normalized, key-ordered flow json."""
    graph_data = normalized_flow_data(graph_data)
    cleaned_graph_json = orjson_dumps(graph_data, sort_keys=True)
    return hashlib.sha256(cleaned_graph_json.encode("utf-8")).hexdigest()


def compute_project_hash(project_data: dict) -> str:
    """Returns the SHA256 of the normalized, key-ordered project json."""
    cleaned_graph_json = orjson_dumps(project_data, sort_keys=True)
    return hashlib.sha256(cleaned_graph_json.encode("utf-8")).hexdigest()


########################################################
# exception handling
########################################################
def handle_s3_error(e: Exception, resource_name: str = "flow", op: str = "get"):
    """Translates S3 exceptions into user-friendly HTTP exceptions.

    Args:
        e: The exception caught
        resource_name: Name of the resource (e.g., "flow")
        op: The operation being performed ("get", "put", "delete", "list")
    """
    if isinstance(e, ClientError):
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = e.response.get("Error", {}).get("Message", str(e))

        logger.error(f"S3 error ({error_code}): {error_msg}")

        if error_code in ("NoSuchKey", "404"):
            if op == "delete":
                msg = f"The {resource_name} is already deleted or does not exist."
            else:
                msg = f"The {resource_name} was not found."

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=msg,
            )
        if error_code == "NoSuchBucket":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Server configuration error: Publish bucket not found.",
            )
        if error_code == "AccessDenied":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied accessing storage.",
            )
        if error_code == "EntityTooLarge":
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"The {resource_name} is too large to publish.",
            )
        if error_code in ("PreconditionFailed", "412"):
            if op == "put":
                msg = f"The {resource_name} already exists. Please update its contents to generate a new version."
            elif op == "delete":
                msg = f"The {resource_name} could not be deleted because it has changed or no longer exists."
            else:
                msg = f"The {resource_name} state does not match the precondition."

            raise HTTPException(
                status_code=status.HTTP_412_PRECONDITION_FAILED,
                detail=msg,
            )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Storage service error: {error_msg}",
        )

    if isinstance(e, (BotoConnectionError, NoCredentialsError)):
        logger.error(f"S3 connection error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not connect to storage service."
        )

    logger.error(f"Unexpected S3 error: {e}")
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"An unexpected error occurred: {e!s}"
    )
