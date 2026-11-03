"""Connection string parser utilities for lfx package."""

from urllib.parse import quote


def transform_connection_string(connection_string) -> str:
    """Transform connection string by encoding the password part."""
    if not isinstance(connection_string, str) or not connection_string:
        msg = "connection string must be a non-empty string"
        raise ValueError(msg)
    if "@" not in connection_string:
        # No userinfo section, so there is no password to encode. A DSN such as
        # "postgresql://host:5432/db" is valid for trust/peer authentication and
        # must pass through untouched instead of failing the unpack below.
        return connection_string
    auth_part, db_url_name = connection_string.rsplit("@", 1)
    protocol_user, password_string = auth_part.rsplit(":", 1)
    if password_string.startswith("//") and "://" not in protocol_user:
        # "scheme://user@host" carries no password; the only ':' is the scheme separator.
        return connection_string
    encoded_password = quote(password_string, safe="")
    return f"{protocol_user}:{encoded_password}@{db_url_name}"
