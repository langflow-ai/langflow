import hashlib
from copy import deepcopy

from lfx.log.logger import logger

from langflow.services.database.models.base import orjson_dumps

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

