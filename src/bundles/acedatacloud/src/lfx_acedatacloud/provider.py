"""Branded chat model and model catalog for the Langflow provider registry."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any

import httpx
from langchain_openai import ChatOpenAI
from lfx.base.models.model_metadata import create_model_metadata
from lfx.base.models.model_utils import get_provider_variable_value

API_BASE = "https://api.acedata.cloud/v1"
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
        super().__init__(**kwargs)


def load_catalog() -> list[dict[str, Any]]:
    """Small, public chat starter catalog; live discovery fills in current models."""
    return [
        create_model_metadata(
            provider=PROVIDER,
            name=name,
            icon=ICON,
            model_type="llm",
            tool_calling=True,
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
        response = httpx.get(
            f"{API_BASE}/models",
            headers={"Authorization": f"Bearer {key}"},
            timeout=8,
            follow_redirects=False,
        )
        response.raise_for_status()
        rows = response.json().get("data", [])
        names = sorted(
            {
                row["id"]
                for row in rows
                if isinstance(row, dict) and isinstance(row.get("id"), str) and row["id"] and _is_chat_model(row)
            }
        )
        return [
            create_model_metadata(
                provider=PROVIDER,
                name=name,
                icon=ICON,
                model_type="llm",
                tool_calling=True,
                default=name == "gpt-4.1-mini",
            )
            for name in names
        ]
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        return []


def _is_chat_model(row: dict[str, Any]) -> bool:
    """Offer only public chat models verified in the Ace model catalog."""
    if row["id"] not in _chat_model_ids():
        return False
    modalities = row.get("modalities") or row.get("architecture") or {}
    if isinstance(modalities, dict):
        outputs = modalities.get("output") or modalities.get("output_modalities")
        if isinstance(outputs, list):
            return "text" in outputs
    return True


@lru_cache(maxsize=1)
def _chat_model_ids() -> frozenset[str]:
    data = json.loads(files("lfx_acedatacloud").joinpath("chat_models.json").read_text())
    return frozenset(data["models"])
