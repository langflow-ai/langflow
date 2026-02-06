from lfx.serialization import constants


def truncate_long_strings(data, max_length=None):
    """Recursively traverse the dictionary or list and truncate strings longer than max_length.

    Returns:
        The data with strings truncated if they exceed the max length.
    """
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


def sanitize_database_url(url: str) -> str:
    """Sanitize a database URL by masking sensitive credentials.

    Removes or masks username and password from the URL to prevent
    sensitive information from being exposed in logs or error messages.

    Args:
        url: Database connection URL to sanitize

    Returns:
        Sanitized URL with credentials masked as '***'
    """
    if not url:
        return url

    try:
        from sqlalchemy.engine import make_url

        parsed_url = make_url(url)
        if parsed_url.username:
            parsed_url = parsed_url.set(username="***", password="***")  # noqa: S106
        return str(parsed_url)
    except Exception:  # noqa: BLE001
        # Fallback: use regex if SQLAlchemy fails to parse
        import re

        pattern = r"(://)[^:/@]+(?::[^@]*)?@"
        return re.sub(pattern, r"\1***:***@", url)


def is_valid_database_url(url: str) -> bool:
    """Validate database connection URLs compatible with SQLAlchemy.

    Args:
        url: Database connection URL to validate

    Returns:
        True if URL is valid, False otherwise
    """
    if not url:
        return False

    try:
        from sqlalchemy.engine import make_url

        parsed_url = make_url(url)
        parsed_url.get_dialect()
        parsed_url.get_driver_name()
    except Exception:  # noqa: BLE001
        return False

    return True
