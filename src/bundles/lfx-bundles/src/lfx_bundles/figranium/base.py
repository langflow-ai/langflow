from __future__ import annotations

from typing import Any

import httpx


class FigraniumAPIClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def request(self, method: str, path: str, *, json: dict[str, Any] | None = None) -> Any:
        if not self.base_url:
            msg = "Figranium base URL is required."
            raise ValueError(msg)
        if not self.api_key:
            msg = "Figranium API key is required."
            raise ValueError(msg)

        try:
            response = httpx.request(
                method,
                f"{self.base_url}{path}",
                headers={"x-api-key": self.api_key, "accept": "application/json"},
                json=json,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text.strip()
            msg = f"Figranium API returned HTTP {exc.response.status_code}"
            if detail:
                msg += f": {detail}"
            raise ValueError(msg) from exc
        except httpx.HTTPError as exc:
            msg = f"Could not reach Figranium at {self.base_url}: {exc}"
            raise ValueError(msg) from exc

        if not response.content:
            return {}
        return response.json()


def secret_value(value: Any) -> str:
    if hasattr(value, "get_secret_value"):
        return value.get_secret_value()
    return str(value or "")
