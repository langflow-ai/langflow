"""Shared request handling for CompanyEnrich's fixed HTTPS API."""

from typing import Any

import httpx
from lfx.inputs.inputs import IntInput, SecretStrInput
from lfx.schema.data import Data
from pydantic import SecretStr

from lfx_bundles.companyenrich._core import core_arguments
from lfx_bundles.companyenrich._validation import prepare_request

API_URL = "https://api.companyenrich.com"
MAX_PAGE_SIZE = 100
MAX_TIMEOUT = 300
MAX_SEED_DOMAINS = 10


def connection_inputs() -> list:
    return [
        SecretStrInput(
            name="api_key",
            display_name="CompanyEnrich API Key",
            required=True,
            info="API key from app.companyenrich.com. Some operations consume CompanyEnrich credits.",
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
) -> Any:
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
    return result


async def execute(component, operation: str, values: dict | None = None, **advanced) -> Data:
    """Execute one validated operation and preserve any JSON response shape."""
    if values is not None:
        values = dict(values)
        for field in ("semantic_query", "query"):
            if isinstance(values.get(field), str):
                values[field] = values[field].strip() or None
        if operation == "get_companies_enrich":
            values["domain"] = company_domain(values["domain"])
        if operation.startswith("post_companies_similar"):
            domains = values.get("domains")
            if not isinstance(domains, list) or not 1 <= len(domains) <= MAX_SEED_DOMAINS:
                msg = "Provide between one and ten seed domains."
                raise ValueError(msg)
            values["domains"] = [company_domain(domain) for domain in domains]
        if operation == "post_companies_search" and not any(
            values.get(k) for k in ("semantic_query", "query", "filters")
        ):
            msg = "Provide Search Query or at least one filter."
            raise ValueError(msg)
        body, query = core_arguments(operation, values)
        advanced = {"body": body, "query": query}
    method, path, query, body = prepare_request(operation, **advanced)
    result = await request(
        component.api_key, method, path, timeout=component.timeout, params=query or None, payload=body
    )
    component.status = result
    return Data(data=result if isinstance(result, dict) else {"data": result})
