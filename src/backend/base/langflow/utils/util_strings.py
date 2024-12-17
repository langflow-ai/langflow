import re

from langflow.utils import constants


def truncate_long_strings(data, max_length=None):
    """Recursively traverse the dictionary or list and truncate strings longer than max_length."""
    if max_length is None:
        max_length = constants.MAX_TEXT_LENGTH

    if max_length < 0:
        return data

    if not isinstance(data, dict | list):
        if isinstance(data, str) and len(data) > max_length:
            return data[:max_length] + "..."
        return data

    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, str) and len(value) > max_length:
                data[key] = value[:max_length] + "..."
            elif isinstance(value, (dict | list)):
                truncate_long_strings(value, max_length)
    elif isinstance(data, list):
        for index, item in enumerate(data):
            if isinstance(item, str) and len(item) > max_length:
                data[index] = item[:max_length] + "..."
            elif isinstance(item, (dict | list)):
                truncate_long_strings(item, max_length)

    return data


def to_pythonic_variable_name(name):
    """Converts a given string into a Pythonic variable name in snake_case."""
    # Remove any characters that are not alphanumeric or spaces
    name = re.sub(r"[^\w\s]", "", name)
    # Replace spaces or other delimiters with underscores
    name = re.sub(r"[\s]+", "_", name)
    # Convert to lowercase
    name = name.lower()
    # Prepend an underscore if the name starts with a digit
    if name and name[0].isdigit():
        name = f"_{name}"
    return name
