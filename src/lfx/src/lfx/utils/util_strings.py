import contextlib
import re
from urllib.parse import quote

from lfx.serialization import constants

_CREDENTIAL_MASK = "***"
_URL_SCHEME = re.compile(r"^[a-z][a-z0-9+.\-]*://", re.IGNORECASE)
# Query parameters that carry secrets, e.g. libpq's ``password`` and ``sslpassword``.
_SENSITIVE_QUERY_KEYWORDS = r"pass|pwd|secret|token|key"
_SENSITIVE_QUERY_KEY = re.compile(_SENSITIVE_QUERY_KEYWORDS, re.IGNORECASE)
_SENSITIVE_QUERY_PARAM = re.compile(rf"([?&][^=&#]*(?:{_SENSITIVE_QUERY_KEYWORDS})[^=&#]*)=[^&#]*", re.IGNORECASE)


def escape_like_pattern(value: str) -> str:
    r"""Escape SQL ``LIKE``/``ILIKE`` wildcards (and the escape char) in a user-supplied term.

    Use with ``escape="\\"`` so a search term containing ``%`` or ``_`` matches literally instead
    of acting as a wildcard (avoids over-broad matches and pathological patterns). Not an injection
    fix on its own — the value must still be passed as a bound parameter — it neutralizes the
    LIKE pattern metacharacters within that parameter.
    """
    return value.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")


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

    with contextlib.suppress(Exception):
        from sqlalchemy.engine import make_url

        parsed_url = make_url(url)
        # SQLAlchemy ends the password at the first "@", so an unescaped "@" in the
        # password leaves the rest of it in the host. Mask the raw string instead.
        if "@" not in (parsed_url.host or ""):
            if parsed_url.username or parsed_url.password:
                parsed_url = parsed_url.set(username=_CREDENTIAL_MASK, password=_CREDENTIAL_MASK)
            sensitive_query = {key: _CREDENTIAL_MASK for key in parsed_url.query if _SENSITIVE_QUERY_KEY.search(key)}
            if sensitive_query:
                parsed_url = parsed_url.update_query_dict(sensitive_query)
            # SQLAlchemy percent-encodes the mask outside the password slot; show it as-is.
            return str(parsed_url).replace(quote(_CREDENTIAL_MASK, safe=""), _CREDENTIAL_MASK)

    return _mask_unparsed_database_url(url)


def _mask_unparsed_database_url(url: str) -> str:
    """Mask credentials in a database URL whose structure SQLAlchemy could not determine.

    Everything between the scheme (when present) and the last ``@`` is treated as
    userinfo, because unescaped passwords may themselves contain ``@``, ``:`` or ``/``.
    """
    masked = _SENSITIVE_QUERY_PARAM.sub(rf"\1={_CREDENTIAL_MASK}", url)
    scheme_match = _URL_SCHEME.match(masked)
    scheme = scheme_match.group(0) if scheme_match else ""
    _userinfo, at_sign, host_and_path = masked[len(scheme) :].rpartition("@")
    if not at_sign:
        return masked
    return f"{scheme}{_CREDENTIAL_MASK}:{_CREDENTIAL_MASK}@{host_and_path}"


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
