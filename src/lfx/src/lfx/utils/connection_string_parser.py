"""Connection string parser utilities for lfx package."""

import re
from urllib.parse import quote

# RFC 3986 scheme at the start of the auth segment (before the final "@").
_URL_SCHEME_SEP = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")


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

    # Only treat a leading scheme:// as URL form. A legacy password may itself
    # contain "://", which must not flip parsing into the URL branch.
    if _URL_SCHEME_SEP.match(auth_part):
        scheme, userinfo = auth_part.split("://", 1)
        if ":" not in userinfo:
            # No password (e.g. postgresql://user@host or postgresql://@host).
            return connection_string
        username, password = userinfo.split(":", 1)
        return f"{scheme}://{username}:{quote(password, safe='')}@{db_url_name}"

    if ":" not in auth_part:
        return connection_string

    # Legacy forms without a leading scheme://:
    # - user:password@host
    # - protocol:user:password@host (password may contain ":" or "://")
    first, _, rest = auth_part.partition(":")
    if ":" not in rest:
        return f"{first}:{quote(rest, safe='')}@{db_url_name}"

    username, _, password = rest.partition(":")
    return f"{first}:{username}:{quote(password, safe='')}@{db_url_name}"
