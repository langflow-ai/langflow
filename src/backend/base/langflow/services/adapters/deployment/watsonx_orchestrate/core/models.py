"""Model-catalog retrieval helpers for the wxO deployment adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langflow.services.adapters.deployment.watsonx_orchestrate.types import WxOClient


def fetch_models_adapter(clients: WxOClient, params: dict[str, Any] | None = None) -> Any:
    """Fetch raw provider models through the adapter client seam."""
    return clients.get_models_raw(params=params)
