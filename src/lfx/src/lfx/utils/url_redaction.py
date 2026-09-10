"""Strip credentials out of URLs before they reach anyone reading a message.

A URL is a common carrier for a secret — userinfo and query strings both routinely hold
one — and the places a URL ends up (error messages, tracebacks, log aggregators, support
tickets) are exactly the places a secret must not. The reduction is deliberate rather than
clever: keep enough to identify the target, drop everything that can authenticate to it.
"""

import re
from urllib.parse import urlparse

URL_IN_TEXT_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z0-9+.\-]*://[^\s'\"<>]+")


def sanitize_url_for_display(url: str) -> str:
    """Reduce a URL to scheme, host, port and path.

    The port has to survive: a target named without it is the wrong target whenever the
    plane runs on anything but 80/443.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return url
    if not parsed.scheme or not parsed.hostname:
        return url
    host = f"{parsed.hostname}:{parsed.port}" if parsed.port else parsed.hostname
    return f"{parsed.scheme}://{host}{parsed.path}"


def redact_urls_in_text(text: str) -> str:
    """Sanitize every URL embedded in text we did not compose.

    Formatting our own targets safely is not enough. ``raise_for_status`` builds a message
    containing the full request URL, so a 401 arrives carrying the credential it just
    rejected, and that message is reproduced verbatim inside any traceback that crosses it.
    """
    return URL_IN_TEXT_PATTERN.sub(lambda match: sanitize_url_for_display(match.group(0)), text)
