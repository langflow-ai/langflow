import json
from typing import Any, Dict, Type

import orjson
from loguru import logger

from langflow.interface.importing.utils import import_by_type

NODE_TYPE_TO_CLASS = {}


def get_class_from_node_type(node_type: str) -> Type:
    pass


async def instantiate_class(node_type: str, base_type: str, params: Dict, user_id=None) -> Any:
    """Instantiate class from module type and key, and params"""
    params = convert_params_to_sets(params)
    params = convert_kwargs(params)

    logger.debug(f"Instantiating {node_type} of type {base_type}")
    class_object = import_by_type(_type=base_type, name=node_type)

    # Instantiate the class based on the type
    # NOTE: there will be no validation for now since the types are loaded from config.yaml
    # return await instantiate_based_on_type(class_object, base_type, node_type, params, user_id=user_id)
    return class_object(**params)


def convert_params_to_sets(params):
    """Convert certain params to sets"""
    if "allowed_special" in params:
        params["allowed_special"] = set(params["allowed_special"])
    if "disallowed_special" in params:
        params["disallowed_special"] = set(params["disallowed_special"])
    return params


def convert_kwargs(params):
    # if *kwargs are passed as a string, convert to dict
    # first find any key that has kwargs or config in it
    kwargs_keys = [key for key in params.keys() if "kwargs" in key or "config" in key]
    for key in kwargs_keys:
        if isinstance(params[key], str):
            try:
                params[key] = orjson.loads(params[key])
            except json.JSONDecodeError:
                # if the string is not a valid json string, we will
                # remove the key from the params
                params.pop(key, None)
    return params
