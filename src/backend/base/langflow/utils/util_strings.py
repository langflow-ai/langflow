from langflow.utils import constants


def truncate_long_strings(data, max_length=None):
    """
    Recursively traverse the dictionary or list and truncate strings longer than max_length.
    Handles nested dictionaries, lists, and strings.
    """

    if max_length is None:
        max_length = constants.MAX_TEXT_LENGTH

    if max_length < 0:
        return data

    if isinstance(data, str):
        return data[:max_length] + "..." if len(data) > max_length else data

    elif isinstance(data, list):
        return [truncate_long_strings(item, max_length) for item in data]

    elif isinstance(data, dict):
        return {key: truncate_long_strings(value, max_length) for key, value in data.items()}

    return data
