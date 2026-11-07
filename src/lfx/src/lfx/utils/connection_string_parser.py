"""Connection string parser utilities for lfx package."""

from urllib.parse import quote


def transform_connection_string(connection_string) -> str:
    """Percent-encode the password segment of a database URL.

    Supports ``scheme://user:password@host/...`` and the legacy
    ``protocol:user:password@host`` form used by older components.

    The password is everything after the first ``:`` in the userinfo
    (RFC 3986), so a password that itself contains ``:``, ``@``, ``/``,
    or other reserved characters is encoded as a whole. Previous code
    used ``rsplit(":", 1)``, which treated only the fragment after the
    *last* colon as the password and left embedded colons unencoded —
    breaking e.g. ``postgresql://user:p:s/s@host/db``.
    """
    if not connection_string or "@" not in connection_string:
        return connection_string

    auth_part, db_url_name = connection_string.rsplit("@", 1)

    if "://" in auth_part:
        scheme, userinfo = auth_part.split("://", 1)
        if ":" not in userinfo:
            # No password (e.g. postgresql://user@host or postgresql://@host).
            return connection_string
        username, password = userinfo.split(":", 1)
        return f"{scheme}://{username}:{quote(password, safe='')}@{db_url_name}"

    if ":" not in auth_part:
        return connection_string

    # Legacy forms without "://":
    # - user:password@host
    # - protocol:user:password@host (password may contain ":")
    segments = auth_part.split(":")
    if len(segments) == 2:
        username, password = segments
        return f"{username}:{quote(password, safe='')}@{db_url_name}"

    protocol, username, password = segments[0], segments[1], ":".join(segments[2:])
    return f"{protocol}:{username}:{quote(password, safe='')}@{db_url_name}"
