from __future__ import annotations

from typing import Any

import httpx

BASE_URL = "https://api.pubrio.com"


def pubrio_get(api_key: str, endpoint: str) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {api_key}"}
    with httpx.Client(timeout=30) as client:
        response = client.get(f"{BASE_URL}{endpoint}", headers=headers)
        response.raise_for_status()
        return response.json()


def pubrio_post(api_key: str, endpoint: str, body: dict[str, Any]) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    with httpx.Client(timeout=30) as client:
        response = client.post(f"{BASE_URL}{endpoint}", headers=headers, json=body)
        response.raise_for_status()
        return response.json()


def split_csv(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [s.strip() for s in value.split(",") if s.strip()]
