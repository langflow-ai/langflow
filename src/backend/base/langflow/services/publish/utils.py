
import hashlib
import re
from copy import deepcopy
from datetime import datetime, timezone

from lfx.log import logger

from langflow.services.database.models.base import orjson_dumps
from langflow.services.publish.service import IDType

INVALID_FLOW_MSG = (
    "Invalid flow. Flow data must contain ALL of these keys:\n"
    "- name (must be non-empty and contain at least one alphanumeric character)\n"
    "- description (must exist, can be None or empty)\n"
    "- nodes (must exist, can be None or empty)\n"
    "- edges (must exist, can be None or empty)"
)
MISSING_BUCKET_NAME_MSG = "Publish backend bucket name not specified"
MISSING_ALL_ID_MSG = "user_id and {item_type}_id are required."
MISSING_ITEM_MSG = "{item} is missing or empty."
INVALID_KEY_MSG = "Invalid key."


# normalize the publish backend key prefix
def add_trailing_slash(s):
    return s + "/" if (s and not s.endswith("/")) else s


########################################################
# utilities for sanitizing the object key
########################################################
pattern = re.compile(r"[\W_]+") # alphanumeric: [^a-zA-Z0-9_]
def to_alnum_string(s: str | None):
    """Returns a new string with non-alphanumeric characters removed."""
    return pattern.sub("", s) if s else None


def utc_now_strf() -> str:
    """Return current UTC timestamp as an alphanumeric string with microsecond precision."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


########################################################
# validation for publishing
########################################################
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
    - name (must be none empty and contain at least one alphanumeric character)
    - description (must exist, can be None or empty)
    - nodes (must exist, can be None or empty)
    - edges (must exist, can be None or empty)
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
        ValueError: If bucket_name, IDs, or required item data are missing.
    """
    require_bucket_name(bucket_name)
    require_all_ids(user_id, item_id, item_type)


########################################################
# flow normalization for version comparison
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


def compute_dict_hash(graph_data: dict | None):
    graph_data = normalized_flow_data(graph_data)
    cleaned_graph_json = orjson_dumps(graph_data, sort_keys=True)
    return hashlib.sha256(cleaned_graph_json.encode("utf-8")).hexdigest()
