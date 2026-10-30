"""Shared request handling for CompanyEnrich's fixed HTTPS API."""

from typing import Any

import httpx
from lfx.inputs.inputs import IntInput, SecretStrInput
from pydantic import SecretStr

API_URL = "https://api.companyenrich.com"
MAX_PAGE_SIZE = 100
MAX_TIMEOUT = 300


def connection_inputs() -> list:
    return [
        SecretStrInput(
            name="api_key",
            display_name="CompanyEnrich API Key",
            required=True,
            info="API key from app.companyenrich.com. These operations consume CompanyEnrich credits.",
        ),
        IntInput(name="timeout", display_name="Timeout (seconds)", value=30, advanced=True),
    ]


def pagination_inputs() -> list:
    return [
        IntInput(name="page", display_name="Page", value=1, advanced=True),
        IntInput(
            name="page_size",
            display_name="Results Per Page",
            value=10,
            info="Between 1 and 100. More results consume more credits. Only one page is requested.",
            advanced=True,
        ),
    ]


def search_payload(filters: dict | None, page: int, page_size: int) -> dict[str, Any]:
    if isinstance(page, bool) or not isinstance(page, int) or page < 1:
        msg = "Page must be an integer greater than zero."
        raise ValueError(msg)
    if isinstance(page_size, bool) or not isinstance(page_size, int) or not 1 <= page_size <= MAX_PAGE_SIZE:
        msg = "Results Per Page must be an integer between 1 and 100."
        raise ValueError(msg)
    if filters is not None and not isinstance(filters, dict):
        msg = "Filters must be an object."
        raise TypeError(msg)
    reserved = {"page", "pageSize", "semanticQuery", "domains", "domain"}
    if reserved.intersection(filters or {}):
        msg = "Use the dedicated query, domains and pagination inputs instead of putting them in Filters."
        raise ValueError(msg)
    return {**(filters or {}), "page": page, "pageSize": page_size}


def company_domain(value: str) -> str:
    domain = value.strip()
    if not domain or "." not in domain or any(char.isspace() or char in "/?#@:" for char in domain):
        msg = "Provide a bare company domain such as stripe.com, without a URL scheme or path."
        raise ValueError(msg)
    return domain


async def request(
    api_key: str | SecretStr,
    method: str,
    path: str,
    *,
    timeout: int,
    params: dict | None = None,
    payload: dict | None = None,
) -> dict[str, Any]:
    key = api_key.get_secret_value() if isinstance(api_key, SecretStr) else api_key
    if not isinstance(key, str) or not key.strip():
        msg = "A CompanyEnrich API key is required."
        raise ValueError(msg)
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= MAX_TIMEOUT:
        msg = "Timeout must be an integer between 1 and 300 seconds."
        raise ValueError(msg)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            response = await client.request(
                method,
                f"{API_URL}{path}",
                headers={"Authorization": f"Bearer {key.strip()}", "Accept": "application/json"},
                params=params,
                json=payload,
            )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        msg = f"CompanyEnrich returned HTTP {exc.response.status_code}. Check your API key, credits and request inputs."
        raise ValueError(msg) from None
    except httpx.RequestError:
        msg = "Could not reach CompanyEnrich. Check connectivity or increase Timeout."
        raise ValueError(msg) from None
    try:
        result = response.json()
    except ValueError:
        msg = "CompanyEnrich returned invalid JSON."
        raise ValueError(msg) from None
    if not isinstance(result, dict):
        msg = "CompanyEnrich returned an unexpected response; expected an object."
        raise TypeError(msg)
    return result
