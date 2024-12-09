import re
from langflow.utils import constants
from urllib.parse import urlparse



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


def is_valid_database_url(url: str) -> bool:
    """
    Validate database connection URLs compatible with SQLAlchemy.

    Args:
        url (str): Database connection URL to validate

    Returns:
        bool: True if URL is valid, False otherwise
    """
    if not isinstance(url, str):
        return False

    # Regex for common database URL patterns
    db_url_pattern = r'^[a-z]+://.*$'

    # Basic pattern check
    if not re.match(db_url_pattern, url):
        return False

    try:
        parsed = urlparse(url)

        # Check for required scheme
        valid_schemes = ['sqlite', 'postgresql', 'mysql', 'oracle', 'mssql']
        if parsed.scheme not in valid_schemes:
            return False

        # SQLite specific validations
        if parsed.scheme == 'sqlite':
            # Allow absolute paths, relative paths, and memory database
            return (
                url.startswith('sqlite:///') or
                url.startswith('sqlite:////') or
                url == 'sqlite:///:memory:'
            )

        return True

    except Exception:
        return False
