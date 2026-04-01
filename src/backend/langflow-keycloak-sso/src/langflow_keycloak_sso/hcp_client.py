"""HCP (Hynix Cloud Platform) API client for project-level role authorization."""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


async def fetch_allowed_employees(hcp_api_url: str, timeout: int = 10) -> set[str]:
    """Call the HCP roles API and return the set of all allowed employee numbers.

    The API is expected to return:
        {"response": {"managers": [...], "deployApprovers": [...], "developers": [...]}}

    Every value across all role arrays is collected and compared as a string.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(hcp_api_url, timeout=timeout)

    if resp.status_code != 200:
        logger.error("HCP roles API returned %s: %s", resp.status_code, resp.text)
        raise ValueError(f"HCP roles API returned {resp.status_code}")

    data = resp.json()
    response_body = data.get("response", {})

    allowed: set[str] = set()
    for role_key in ("managers", "deployApprovers", "developers"):
        for emp_id in response_body.get(role_key, []):
            allowed.add(str(emp_id).upper())

    logger.info("HCP roles API returned %d allowed employees", len(allowed))
    return allowed
