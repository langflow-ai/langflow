"""Ace Data Cloud catalog and protocol-aware LangChain model factory."""

from __future__ import annotations

from functools import cached_property
from threading import Lock
from time import monotonic
from typing import TYPE_CHECKING, Any

import anthropic
import httpx
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from lfx.base.models.model_metadata import create_model_metadata

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

API_BASE = "https://api.acedata.cloud/v1"
PUBLIC_CHAT_CATALOG = "https://platform.acedata.cloud/api/v1/models/"
PROVIDER = "Ace Data Cloud"
ICON = "Bot"
_catalog_state: dict[str, Any] = {"rows": {}, "expires": 0.0}
_catalog_lock = Lock()


def get_provider_variable_value(user_id: Any, name: str) -> Any:
    # Catalog loading and model construction do not need the database services.
    from lfx.base.models.model_utils import get_provider_variable_value as get_value

    return get_value(user_id, name)


def _is_chat_model(row: dict[str, Any]) -> bool:
    # An image-capable chat model is still a chat model. Modality is authoritative.
    return isinstance(row.get("id"), str) and bool(row["id"].strip()) and row.get("type") == "chat"


def _protocols(row: dict[str, Any]) -> set[str]:
    protocols = set()
    for endpoint in row.get("endpoints", []):
        protocol = endpoint.get("protocol")
        expected = {
            "chat_completions": (API_BASE, "/v1/chat/completions"),
            "responses": (API_BASE, "/v1/responses"),
            "messages": ("https://api.acedata.cloud", "/v1/messages"),
        }.get(protocol)
        if (
            expected
            and (endpoint.get("base_url"), endpoint.get("path")) == expected
            and endpoint.get("auth") == "bearer"
        ):
            protocols.add(protocol)
    return protocols


def _public_catalog() -> dict[str, dict[str, Any]]:
    with _catalog_lock:
        if monotonic() < _catalog_state["expires"]:
            return _catalog_state["rows"]
        try:
            response = httpx.get(PUBLIC_CHAT_CATALOG, params={"type": "chat"}, timeout=8, follow_redirects=False)
            response.raise_for_status()
            rows = response.json()["data"]
            next_rows = {
                row["id"]: row for row in rows if isinstance(row, dict) and _is_chat_model(row) and _protocols(row)
            }
            if not next_rows:
                msg = "No published chat protocols returned"
                raise ValueError(msg)
            _catalog_state["rows"] = next_rows
            _catalog_state["expires"] = monotonic() + 300
        except (httpx.HTTPError, KeyError, ValueError, TypeError, AttributeError):
            # Do not replace a valid catalog with a transient failure or untyped list.
            _catalog_state["expires"] = monotonic() + 30
        return _catalog_state["rows"]


class _AceMessages(ChatAnthropic):
    """Reuse LangChain's native Messages implementation with the Ace credential."""

    @cached_property
    def _client_params(self) -> dict[str, Any]:
        params = dict(super()._client_params)
        params["api_key"] = ""  # Prevent the SDK reading an ambient Anthropic API key.
        params["auth_token"] = self.anthropic_api_key.get_secret_value()
        params["default_headers"] = {
            **{
                key: value
                for key, value in params["default_headers"].items()
                if key.lower() not in {"authorization", "x-api-key"}
            },
            "X-Api-Key": anthropic.Omit(),
        }
        return params


class ChatAceDataCloud:
    """Construct the standard LangChain client for the selected model's published API."""

    def __new__(cls, **kwargs: Any) -> BaseChatModel:
        base_url = kwargs.pop("base_url", kwargs.pop("openai_api_base", API_BASE))
        kwargs.setdefault("max_retries", 0)
        # The same ID at another provider does not establish Ace capabilities or limits.
        kwargs.setdefault("profile", {})
        if str(base_url).rstrip("/") != API_BASE:
            return ChatOpenAI(base_url=base_url, **kwargs)
        model = kwargs.get("model", kwargs.get("model_name"))
        protocols = _protocols(_public_catalog().get(model, {}))
        if not protocols:
            msg = "Select a model from the current Ace Data Cloud chat catalog; its API metadata is unavailable."
            raise ValueError(msg)
        if kwargs.get("use_responses_api") is True:
            if "responses" not in protocols:
                msg = "The selected Ace Data Cloud model does not publish a Responses API."
                raise ValueError(msg)
            return ChatOpenAI(base_url=API_BASE, **kwargs)
        if "chat_completions" in protocols:
            return ChatOpenAI(base_url=API_BASE, **kwargs)
        if "responses" in protocols:
            kwargs["use_responses_api"] = True
            return ChatOpenAI(base_url=API_BASE, **kwargs)
        kwargs.pop("use_responses_api", None)
        if "max_completion_tokens" in kwargs:
            kwargs.setdefault("max_tokens", kwargs.pop("max_completion_tokens"))
        if "model_name" in kwargs:
            kwargs.setdefault("model", kwargs.pop("model_name"))
        if "openai_api_key" in kwargs:
            kwargs.setdefault("api_key", kwargs.pop("openai_api_key"))
        if not kwargs.get("api_key"):
            msg = "An Ace Data Cloud API key is required."
            raise ValueError(msg)
        return _AceMessages(base_url="https://api.acedata.cloud", **kwargs)


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    # None means unknown, not a negative capability claim. The underlying clients
    # still accept explicit tools and user settings without borrowing vendor data.
    return create_model_metadata(
        provider=PROVIDER,
        name=row["id"],
        icon=ICON,
        model_type="llm",
        tool_calling=None,
        reasoning="reasoning" in row.get("capabilities", []),
    )


def load_catalog() -> list[dict[str, Any]]:
    """Discover every published chat model even before an API key is entered."""
    return [_metadata(row) for _, row in sorted(_public_catalog().items())]


def fetch_live_models(user_id: Any, model_type: str = "llm") -> list[dict[str, Any]]:
    """Intersect the typed public catalog with IDs visible to the selected account."""
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
        available = {
            row["id"] for row in response.json()["data"] if isinstance(row, dict) and isinstance(row.get("id"), str)
        }
        return [_metadata(row) for name, row in sorted(_public_catalog().items()) if name in available]
    except (httpx.HTTPError, KeyError, ValueError, TypeError, AttributeError):
        return []
