from __future__ import annotations

from typing import Any
import json
import re
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from langchain_openai import OpenAIEmbeddings

from lfx.base.embeddings.model import LCEmbeddingsModel
from lfx.field_typing import Embeddings
from lfx.io import (
    BoolInput,
    DictInput,
    FloatInput,
    IntInput,
    SecretStrInput,
    DropdownInput,
    StrInput,
)
from lfx.log.logger import logger


class VllmEmbeddingsComponent(LCEmbeddingsModel):
    display_name = "vLLM Embeddings"
    description = "Generate embeddings using vLLM models via OpenAI-compatible API."
    icon = "vLLM"
    name = "vLLMEmbeddings"

    inputs = [
        StrInput(
            name="api_base",
            display_name="vLLM API Base",
            advanced=False,
            info="Base URL of the vLLM OpenAI-compatible server. "
                 "You can provide either http://host:port or http://host:port/v1",
            value="http://localhost:8000/v1",
            real_time_refresh=True,
        ),
        BoolInput(
            name="auto_select_model",
            display_name="Auto Select Model",
            advanced=False,
            info="If True, fetches available models from GET /v1/models and auto-selects one.",
            value=True,
        ),
        StrInput(
            name="model_name_pattern",
            display_name="Model Name Pattern (Regex)",
            advanced=True,
            info="Optional regex to pick a preferred embedding model id from /v1/models. "
                 "Example: 'bge|e5|gte|embed'. If no match, falls back to the first model.",
            value="bge|e5|gte|embed|embedding",
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            options=[],
            value="",
            advanced=False,
            info="Auto-fetched from GET /v1/models. Use refresh if empty.",
            refresh_button=True,
            real_time_refresh=True,
            required=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="The API Key to use for the vLLM model (optional for local servers).",
            advanced=False,
            value="",
            required=False,
        ),
        IntInput(
            name="dimensions",
            display_name="Dimensions",
            info="The number of dimensions the resulting output embeddings should have. "
                 "Only supported by certain models.",
            advanced=True,
        ),
        IntInput(
            name="chunk_size",
            display_name="Chunk Size",
            advanced=True,
            value=1000,
            info="The chunk size to use when processing documents.",
        ),
        IntInput(
            name="max_retries",
            display_name="Max Retries",
            value=3,
            advanced=True,
            info="Maximum number of retries for failed requests.",
        ),
        FloatInput(
            name="request_timeout",
            display_name="Request Timeout",
            advanced=True,
            info="Timeout for requests to vLLM API in seconds.",
        ),
        BoolInput(
            name="show_progress_bar",
            display_name="Show Progress Bar",
            advanced=True,
            info="Whether to show a progress bar when processing multiple documents.",
        ),
        BoolInput(
            name="skip_empty",
            display_name="Skip Empty",
            advanced=True,
            info="Whether to skip empty documents.",
        ),
        DictInput(
            name="model_kwargs",
            display_name="Model Kwargs",
            advanced=True,
            info="Additional keyword arguments to pass to the model.",
        ),
        DictInput(
            name="default_headers",
            display_name="Default Headers",
            advanced=True,
            info="Default headers to use for the API request.",
        ),
        DictInput(
            name="default_query",
            display_name="Default Query",
            advanced=True,
            info="Default query parameters to use for the API request.",
        ),
    ]

    # ----------------------------
    # helpers
    # ----------------------------
    def _normalize_api_base(self, url: str) -> str:
        b = (url or "").strip().rstrip("/")
        if not b.endswith("/v1"):
            b = f"{b}/v1"
        return b

    def _fetch_model_ids(self, api_base: str, timeout_s: int = 10) -> list[str]:
        base = self._normalize_api_base(api_base)
        url = f"{base}/models"

        req = Request(url, method="GET", headers={
                      "Accept": "application/json"})
        try:
            with urlopen(req, timeout=timeout_s) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            data = json.loads(raw)
        except (HTTPError, URLError, json.JSONDecodeError) as e:
            logger.debug(f"Failed to fetch vLLM models from {url}: {e}")
            return []

        items = data.get("data", [])
        ids: list[str] = []
        if isinstance(items, list):
            for m in items:
                if isinstance(m, dict) and m.get("id"):
                    ids.append(str(m["id"]))
        return sorted(set(ids))

    def _pick_model(self, model_ids: list[str], pattern: str) -> str:
        if not model_ids:
            return ""
        pat = (pattern or "").strip()
        if pat:
            try:
                rx = re.compile(pat, flags=re.IGNORECASE)
                for mid in model_ids:
                    if rx.search(mid):
                        return mid
            except re.error:
                # invalid regex -> ignore and fallback
                pass
        return model_ids[0]

    # ----------------------------
    # build embeddings
    # ----------------------------
    def build_embeddings(self) -> Embeddings:
        chosen_model = (self.model_name or "").strip()

        # runtime safety net: if auto-select is on but model is empty, try fetching once
        if self.auto_select_model and not chosen_model:
            ids = self._fetch_model_ids(self.api_base)
            chosen_model = self._pick_model(ids, self.model_name_pattern)
            if chosen_model:
                logger.debug(
                    f"Auto-selected vLLM embeddings model at runtime: {chosen_model}")

        return OpenAIEmbeddings(
            model=chosen_model or self.model_name,
            base_url=self._normalize_api_base(
                self.api_base) if self.api_base else "http://localhost:8000/v1",
            api_key=self.api_key or None,
            dimensions=self.dimensions or None,
            chunk_size=self.chunk_size,
            max_retries=self.max_retries,
            timeout=self.request_timeout or None,
            show_progress_bar=self.show_progress_bar,
            skip_empty=self.skip_empty,
            model_kwargs=self.model_kwargs,
            default_headers=self.default_headers or None,
            default_query=self.default_query or None,
        )

    # ----------------------------
    # UI config: dynamic dropdown
    # ----------------------------
    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:  # noqa: ARG002
        if field_name in {"api_base", "model_name", "auto_select_model", "model_name_pattern"}:
            api_base_to_use = field_value if field_name == "api_base" else self.api_base
            ids = self._fetch_model_ids(api_base_to_use)

            build_config["model_name"]["options"] = ids

            current = (build_config["model_name"].get("value") or "").strip()
            current_valid = current in ids if ids else False

            auto_on = bool(field_value) if field_name == "auto_select_model" else bool(
                getattr(self, "auto_select_model", True))
            pattern = (field_value if field_name == "model_name_pattern" else getattr(
                self, "model_name_pattern", "")) or ""

            if auto_on:
                if not current_valid:
                    build_config["model_name"]["value"] = self._pick_model(
                        ids, pattern)
            else:
                if current and not current_valid:
                    build_config["model_name"]["value"] = ""

        return build_config
