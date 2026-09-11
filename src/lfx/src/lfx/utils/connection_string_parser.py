"""Connection string parser utilities for lfx package."""

from urllib.parse import quote


def transform_connection_string(connection_string) -> str:
    """Transform connection string by encoding the password part."""
    auth_part, db_url_name = connection_string.rsplit("@", 1)
    protocol_user, password_string = auth_part.rsplit(":", 1)
    if password_string.startswith("//") and "://" not in protocol_user:
        # "scheme://user@host" carries no password; the only ':' is the scheme separator.
        return connection_string
    encoded_password = quote(password_string, safe="")
    return f"{protocol_user}:{encoded_password}@{db_url_name}"
