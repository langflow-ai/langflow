import hashlib
from copy import deepcopy
from uuid import UUID

from lfx.log.logger import logger

from langflow.services.database.models.base import orjson_dumps
from langflow.services.database.models.flow_history.schema import IDType

########################################################
# validation
########################################################
MISSING_ALL_ID_MSG = "user_id and {item_type}_id are required."


def require_all_ids(
    user_id: IDType,
    item_id: IDType,
    item_type: str
    ):
    """Raises a ValueError if the user or item id is None or empty."""
    if not (user_id and item_id):
        raise ValueError(MISSING_ALL_ID_MSG.format(item_type=item_type))


# def validate_flow_blob(
#     flow_data: dict,
#     *,
#     detail: str,
#     use_http_exception: bool = True,
# ) -> FlowBlob:
#     try:
#         return FlowBlob.model_validate(flow_data)
#     except ValidationError as exc:
#         if use_http_exception:
#             raise HTTPException(status_code=500, detail=detail) from exc
#         raise ValueError(detail) from exc


# def validate_project_blob(
#     project_blob: dict,
#     *,
#     detail: str,
#     use_http_exception: bool = True,
# ) -> ProjectBlob:
#     try:
#         return ProjectBlob.model_validate(project_blob)
#     except ValidationError as exc:
#         if use_http_exception:
#             raise HTTPException(status_code=500, detail=detail) from exc
#         raise ValueError(detail) from exc


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
# validation
########################################################
MISSING_USER_OR_FLOW_ID_MSG = "user_id and flow_id are required."
MISSING_USER_OR_VERSION_ID_MSG = "user_id and version_id is required."
MISSING_USER_OR_FLOW_OR_VERSION_ID_MSG = "user_id, flow_id and version_id is required."
IMPROPER_VERSION_NUMBER_MSG = (
    "Received invalid value for version number. "
    "Please provide a version number greater than or equal to 0."
    )


def require_user_and_flow_ids(
    user_id: str | UUID | None,
    flow_id: str | UUID | None,
    ):
    """Raise a ValueError if user_id or flow_id is not provided."""
    if not (user_id and flow_id):
        raise ValueError(MISSING_USER_OR_FLOW_ID_MSG)


def require_user_flow_version_ids(
    user_id: str | UUID | None,
    flow_id: str | UUID | None,
    version_id: str | UUID | None,
    ):
    """Raise a ValueError if user_id or flow_id is not provided."""
    if not (user_id and flow_id and version_id):
        raise ValueError(MISSING_USER_OR_FLOW_OR_VERSION_ID_MSG)


def require_user_flow_ids(
    user_id: str | UUID | None,
    flow_id: str | UUID | None,
    ):
    """Raise a ValueError if user_id or flow_id is not provided."""
    if not (user_id and flow_id):
        raise ValueError(MISSING_USER_OR_FLOW_ID_MSG)


def require_user_version_ids(
    user_id: str | UUID | None,
    version_id: str | UUID | None,
    ):
    """Raise a ValueError if user_id or flow_id is not provided."""
    if not (user_id and version_id):
        raise ValueError(MISSING_USER_OR_VERSION_ID_MSG)


def require_proper_version(version : int | None):
    """Raise a ValueError if version is not provided or is not a positive integer."""
    if not (version and version > -1):
        raise ValueError(IMPROPER_VERSION_NUMBER_MSG)


def _get_uuid(value: str | UUID) -> UUID:
    """Get a UUID from a string or UUID."""
    return UUID(value) if isinstance(value, str) else value
