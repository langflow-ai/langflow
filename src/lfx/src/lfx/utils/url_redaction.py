"""Strip credentials out of URLs before they reach anyone reading a message.

A URL is a common carrier for a secret — userinfo and query strings both routinely hold
one — and the places a URL ends up (error messages, tracebacks, log aggregators, support
tickets) are exactly the places a secret must not. The reduction is deliberate rather than
clever: keep enough to identify the target, drop everything that can authenticate to it.
"""

import re
from urllib.parse import urlparse

URL_IN_TEXT_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z0-9+.\-]*://[^\s'\"<>]+")
_SCHEME_PREFIX_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://")


def _strip_credentials_from_unparseable_url(url: str) -> str:
    """Best-effort credential stripping for a URL ``urlparse`` itself rejects.

    An unterminated IPv6 literal (``https://user:pw@[::1/mcp``) makes ``urlparse`` raise
    before userinfo or query are ever separated out, so handing the input back unchanged
    would leak exactly what this module exists to remove. Text that isn't URL-shaped to
    begin with carries no such risk and is returned as-is.
    """
    match = _SCHEME_PREFIX_PATTERN.match(url)
    if not match:
        return url
    scheme = url[: match.end()]
    rest = url[match.end() :]
    rest = re.split(r"[?#]", rest, maxsplit=1)[0]
    authority, sep, path = rest.partition("/")
    authority = authority.rpartition("@")[2]
    return f"{scheme}{authority}{sep}{path}"


def sanitize_url_for_display(url: str) -> str:
    """Reduce a URL to scheme, host, port and path.

    The port has to survive: a target named without it is the wrong target whenever the
    plane runs on anything but 80/443.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return _strip_credentials_from_unparseable_url(url)
    if not parsed.scheme or not parsed.hostname:
        return url
    try:
        port = parsed.port
    except ValueError:
        # ``.port`` rejects a port that is out of range or not a number. The URL is
        # malformed, but it can still carry a credential, so the netloc is kept
        # verbatim minus the userinfo rather than handing the whole URL back.
        return f"{parsed.scheme}://{parsed.netloc.rpartition('@')[2]}{parsed.path}"
    # An IPv6 literal needs its brackets back, or host and port run together into
    # something that no longer parses as the address it came from.
    hostname = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    host = f"{hostname}:{port}" if port else hostname
    return f"{parsed.scheme}://{host}{parsed.path}"


def redact_urls_in_text(text: str) -> str:
    """Sanitize every URL embedded in text we did not compose.

    Formatting our own targets safely is not enough. ``raise_for_status`` builds a message
    containing the full request URL, so a 401 arrives carrying the credential it just
    rejected, and that message is reproduced verbatim inside any traceback that crosses it.
    """
    return URL_IN_TEXT_PATTERN.sub(lambda match: sanitize_url_for_display(match.group(0)), text)
