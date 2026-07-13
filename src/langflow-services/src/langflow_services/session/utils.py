import hashlib
import random
import string

import orjson

from langflow_services.cache.utils import filter_json


def orjson_dumps(v, *, default=None, sort_keys=False, indent_2=True):
    """Serialize with the same options as ``langflow.services.database.models.base``.

    Preserving ``indent_2=True`` is required for session-cache hash stability:
    ``compute_dict_hash`` historically hashed indented JSON.
    """
    option = orjson.OPT_SORT_KEYS if sort_keys else None
    if indent_2:
        if option is None:
            option = orjson.OPT_INDENT_2
        else:
            option |= orjson.OPT_INDENT_2
    if default is None:
        return orjson.dumps(v, option=option).decode()
    return orjson.dumps(v, default=default, option=option).decode()


def session_id_generator(size=6):
    return "".join(random.SystemRandom().choices(string.ascii_uppercase + string.digits, k=size))


def compute_dict_hash(graph_data):
    graph_data = filter_json(graph_data)

    cleaned_graph_json = orjson_dumps(graph_data, sort_keys=True)

    return hashlib.sha256(cleaned_graph_json.encode("utf-8")).hexdigest()
