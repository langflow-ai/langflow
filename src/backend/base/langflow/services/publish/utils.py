
import hashlib
import re
from copy import deepcopy
from datetime import datetime
from typing import Any
from uuid import UUID

from botocore.exceptions import (
    ClientError,
    NoCredentialsError,
)
from botocore.exceptions import (
    ConnectionError as BotoConnectionError,
)
from fastapi import HTTPException, status
from lfx.log import logger

from langflow.services.database.models.base import orjson_dumps

# commonly used types
IDType = str | UUID | None
IDTypeStrict = str | UUID


########################################################
# normalize the publish backend key prefix
########################################################
def add_trailing_slash(s):
    return s + "/" if (s and not s.endswith("/")) else s


########################################################
# sanitization and parsing of the object key
########################################################
ALNUM_PATTERN = re.compile(r"[^a-zA-Z0-9_.-]+") # Allowed: a-z, A-Z, 0-9, _, ., -
def to_alnum_string(s: str | None):
    """Returns a new string with invalid characters removed.

    Allowed characters: alphanumeric, underscore, dot, hyphen.
    """
    return ALNUM_PATTERN.sub("", s) if s else None


KEY_VAL_PATTERN = re.compile(r"([^/]+)=([^/]+)")
def parse_blob_key(key: str, last_modified: datetime | None, cls) -> Any:
    """Matches key-value pairs in an s3 object key to return a metadata object."""
    data = dict(KEY_VAL_PATTERN.findall(key))
    data["version_id"] = data["id"]
    data["last_modified"] = last_modified
    return cls(**data)


########################################################
# validation
########################################################
INVALID_FLOW_MSG = (
    "Invalid flow. Flow data must contain ALL of these keys:\n"
    "- name (must be non-empty and contain at least one alphanumeric character)\n"
    "- description (can be None or empty)\n"
    "- nodes (can be None or empty)\n"
    "- edges (can be None or empty)"
)
INVALID_PROJECT_MSG = (
    "Invalid project. Project data must contain ALL of these keys:\n"
    "- name (must be non-empty and contain at least one alphanumeric character)\n"
    "- description (can be None or empty)\n"
    "- flows (must be a list)"
)
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


def require_valid_flow(flow_data: dict | None):
    """Validates the flow data dictionary for publishing.

    Raises a ValueError if the data is None, empty,
    or does not have sufficient fields for publishing:
    - name (must contain at least one alphanumeric character)
    - description (can be None or empty)
    - nodes (can be None or empty)
    - edges (can be None or empty)

    Modifies flow_data["name"] in-place to remove all non-alphanumeric characters.
    """
    if not flow_data:
        raise ValueError(MISSING_ITEM_MSG.format(item="Flow data"))

    flow_data["name"] = to_alnum_string(flow_data.get("name", None))

    if not (
        flow_data["name"] and
        "description" in flow_data and
        "nodes" in flow_data and
        "edges" in flow_data
        ):
        raise ValueError(INVALID_FLOW_MSG)


def require_valid_project(project_data: dict | None):
    """Validates the project data dictionary for publishing."""
    if not project_data:
        raise ValueError(MISSING_ITEM_MSG.format(item="Project data"))

    project_data["name"] = to_alnum_string(project_data.get("name", None))

    if not (
        project_data["name"] and
        "description" in project_data and
        "flows" in project_data and
        isinstance(project_data["flows"], list)
    ):
        raise ValueError(INVALID_PROJECT_MSG)


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


def compute_flow_hash(graph_data: dict | None):
    """Returns the SHA256 of the normalized, key-ordered flow json."""
    graph_data = normalized_flow_data(graph_data)
    cleaned_graph_json = orjson_dumps(graph_data, sort_keys=True)
    return hashlib.sha256(cleaned_graph_json.encode("utf-8")).hexdigest()


def compute_project_hash(project_data: dict | None):
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
                msg = f"The {resource_name} already exists. Please update its contents or retry with a new tag."
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
