"""Branded chat model and model catalog for the Langflow provider registry."""

from __future__ import annotations

from typing import Any

import httpx
from langchain_openai import ChatOpenAI
from lfx.base.models.model_metadata import create_model_metadata
from lfx.base.models.model_utils import get_provider_variable_value

API_BASE = "https://api.acedata.cloud/v1"
PUBLIC_CHAT_CATALOG = "https://platform.acedata.cloud/api/v1/models/"
PROVIDER = "Ace Data Cloud"
ICON = "Bot"
_CATALOG = (
    "gpt-4.1-mini",
    "gpt-5.4-mini",
    "claude-sonnet-4-6",
    "gemini-3.1-flash-lite",
    "deepseek-v4-flash",
)


class ChatAceDataCloud(ChatOpenAI):
    """ChatOpenAI wired to Ace Data Cloud's fixed OpenAI-compatible endpoint."""

    def __init__(self, **kwargs: Any) -> None:
        kwargs["base_url"] = API_BASE
        kwargs["max_retries"] = 0
        super().__init__(**kwargs)


def load_catalog() -> list[dict[str, Any]]:
    """Small, public chat starter catalog; live discovery fills in current models."""
    return [
        create_model_metadata(
            provider=PROVIDER,
            name=name,
            icon=ICON,
            model_type="llm",
            tool_calling=False,
            default=name == "gpt-4.1-mini",
        )
        for name in _CATALOG
    ]


def fetch_live_models(user_id: Any, model_type: str = "llm") -> list[dict[str, Any]]:
    """Read the authenticated catalog; never expose non-chat models as chat."""
    if model_type != "llm":
        return []
    key = get_provider_variable_value(user_id, "ACEDATACLOUD_API_KEY")
    if not key:
        return []
    try:
        available_response = httpx.get(
            f"{API_BASE}/models",
            headers={"Authorization": f"Bearer {key}"},
            timeout=8,
            follow_redirects=False,
        )
        available_response.raise_for_status()
        available = {
            row["id"]
            for row in available_response.json()["data"]
            if isinstance(row, dict) and isinstance(row.get("id"), str)
        }
        catalog_response = httpx.get(
            PUBLIC_CHAT_CATALOG,
            params={"type": "chat", "limit": 200},
            timeout=8,
            follow_redirects=False,
        )
        catalog_response.raise_for_status()
        catalog_rows = catalog_response.json()["data"]
        chat_models = {row["id"]: row for row in catalog_rows if isinstance(row, dict) and _is_chat_model(row)}
        return [
            create_model_metadata(
                provider=PROVIDER,
                name=name,
                icon=ICON,
                model_type="llm",
                # The public catalog does not declare tool support per model.
                tool_calling=False,
                reasoning="reasoning" in chat_models[name].get("capabilities", []),
                default=name == "gpt-4.1-mini",
            )
            for name in sorted(chat_models.keys() & available)
        ]
    except (httpx.HTTPError, KeyError, ValueError, TypeError, AttributeError):
        return []


def _is_chat_model(row: dict[str, Any]) -> bool:
    """Keep image-generating variants out of the text-model selector."""
    return (
        isinstance(row.get("id"), str)
        and bool(row["id"])
        and row.get("type") == "chat"
        and "image_generation" not in row.get("capabilities", [])
    )
