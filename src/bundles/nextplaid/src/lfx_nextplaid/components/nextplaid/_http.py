"""Apply connector policy to the NextPlaid SDK's module-level HTTP calls."""

from functools import partial
from types import SimpleNamespace

import requests
from lfx.utils.ssrf_protection import (
    is_connector_ssrf_validation_enabled,
    is_ssrf_protection_enabled,
    validate_connector_url_for_ssrf,
)
from lfx.utils.ssrf_requests import refuse_redirects


def _request(method: str, url: str, **kwargs) -> requests.Response:
    """Validate each SDK request and refuse redirects while connector policy applies."""
    validate_connector_url_for_ssrf(url)
    with requests.Session() as session:
        if is_ssrf_protection_enabled() and is_connector_ssrf_validation_enabled():
            refuse_redirects(session)
        return session.request(method, url, **kwargs)


_CONNECTOR_REQUESTS = SimpleNamespace(
    get=partial(_request, "GET"),
    post=partial(_request, "POST"),
    delete=partial(_request, "DELETE"),
    HTTPError=requests.HTTPError,
)


def secure_nextplaid_http() -> None:
    """Replace only the SDK's Requests reference before its constructor can send traffic."""
    from langchain_plaid.vectorstores import plaid

    # The SDK exposes no client hook and calls Requests directly from these
    # module globals. This shared shim carries no caller state and leaves
    # the process-wide Requests module unchanged.
    if not hasattr(plaid, "requests"):
        msg = "The installed NextPlaid SDK exposes no supported HTTP policy hook."
        raise RuntimeError(msg)
    plaid.requests = _CONNECTOR_REQUESTS
