"""Connection string parser utilities for lfx package."""

from urllib.parse import quote


def transform_connection_string(connection_string) -> str:
    """Transform connection string by encoding the password part.

    Handles standard connection strings of the form
    ``scheme://user:password@host/db`` and returns the original string
    unchanged when the format does not contain a password to encode.
    """
    if "@" not in connection_string:
        return connection_string
    auth_part, db_url_name = connection_string.rsplit("@", 1)
    if ":" not in auth_part:
        return connection_string
    protocol_user, password_string = auth_part.rsplit(":", 1)
    if password_string.startswith("//") and "://" not in protocol_user:
        # "scheme://user@host" carries no password; the only ':' is the scheme separator.
        return connection_string
    encoded_password = quote(password_string, safe="")
    return f"{protocol_user}:{encoded_password}@{db_url_name}"
