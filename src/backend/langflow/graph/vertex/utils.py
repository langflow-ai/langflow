from langflow.utils.constants import PYTHON_BASIC_TYPES


def is_basic_type(obj):
    return type(obj) in PYTHON_BASIC_TYPES
