from __future__ import annotations

from typing import Any
import json
import re
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from langchain_openai import ChatOpenAI
from pydantic.v1 import SecretStr

from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import (
    BoolInput,
    DictInput,
    IntInput,
    SecretStrInput,
    SliderInput,
    StrInput,
    DropdownInput,
)
from lfx.log.logger import logger


class VllmComponent(LCModelComponent):
    display_name = "vLLM"
    description = "Generates text using vLLM models via OpenAI-compatible API."
    icon = "vLLM"
    name = "vLLMModel"

    inputs = [
        *LCModelComponent.get_base_inputs(),
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
            info="The maximum number of tokens to generate. Set to 0 for unlimited tokens.",
            range_spec=RangeSpec(min=0, max=128000),
        ),
        DictInput(
            name="model_kwargs",
            display_name="Model Kwargs",
            advanced=True,
            info="Additional keyword arguments to pass to the model.",
        ),
        BoolInput(
            name="json_mode",
            display_name="JSON Mode",
            advanced=True,
            info="If True, it will output JSON regardless of passing a schema.",
        ),
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
            info="Optional regex to pick a preferred model id from /v1/models. "
                 "Example: 'granite|llama|mistral'. If no match, falls back to the first model.",
            value="",
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
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.1,
            range_spec=RangeSpec(min=0, max=1, step=0.01),
            show=True,
        ),
        IntInput(
            name="seed",
            display_name="Seed",
            info="Controls the reproducibility of the job. Set to -1 to disable (some providers may not support).",
            advanced=True,
            value=-1,
            required=False,
        ),
        IntInput(
            name="max_retries",
            display_name="Max Retries",
            info="Max retries when generating. Set to -1 to disable (some providers may not support).",
            advanced=True,
            value=-1,
            required=False,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout",
            info="Timeout for requests to vLLM completion API. Set to -1 to disable (some providers may not support).",
            advanced=True,
            value=-1,
            required=False,
        ),
    ]

    # ----------------------------
    # helpers: URL + model fetching
    # ----------------------------
    def _normalize_api_base(self, url: str) -> str:
        """
        Ensure base ends with '/v1' and has no trailing slash.
        Accepts:
          - http://host:port
          - http://host:port/v1
          - http://host:port/v1/
        Returns:
          - http://host:port/v1
        """
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
                rx = re.compile(pat)
                for mid in model_ids:
                    if rx.search(mid):
                        return mid
            except re.error:
                # invalid regex -> ignore and fallback
                pass
        return model_ids[0]

    # ----------------------------
    # core: build model
    # ----------------------------
    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        chosen_model = (self.model_name or "").strip()

        # runtime safety net: if auto-select is on but model is empty, try fetching once
        if self.auto_select_model and not chosen_model:
            ids = self._fetch_model_ids(self.api_base)
            chosen_model = self._pick_model(ids, self.model_name_pattern)
            if chosen_model:
                logger.debug(
                    f"Auto-selected vLLM model at runtime: {chosen_model}")

        logger.debug(
            f"Executing request with vLLM model: {chosen_model or self.model_name}")

        parameters = {
            "api_key": SecretStr(self.api_key).get_secret_value() if self.api_key else None,
            "model_name": chosen_model or self.model_name,
            "max_tokens": self.max_tokens or None,
            "model_kwargs": self.model_kwargs or {},
            "base_url": self._normalize_api_base(self.api_base) if self.api_base else "http://localhost:8000/v1",
            "temperature": self.temperature if self.temperature is not None else 0.1,
        }

        if self.seed is not None and self.seed != -1:
            parameters["seed"] = self.seed
        if self.timeout is not None and self.timeout != -1:
            parameters["timeout"] = self.timeout
        if self.max_retries is not None and self.max_retries != -1:
            parameters["max_retries"] = self.max_retries

        output = ChatOpenAI(**parameters)
        if self.json_mode:
            output = output.bind(response_format={"type": "json_object"})

        return output

    def _get_exception_message(self, e: Exception):
        try:
            from openai import BadRequestError
        except ImportError:
            return None
        if isinstance(e, BadRequestError):
            message = e.body.get("message")
            if message:
                return message
        return None

    # ----------------------------
    # UI config: dynamic dropdown
    # ----------------------------
    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:  # noqa: ARG002
        # Refresh model list when relevant fields change or refresh is pressed
        if field_name in {"api_base", "model_name", "auto_select_model", "model_name_pattern"}:
            api_base_to_use = field_value if field_name == "api_base" else self.api_base
            ids = self._fetch_model_ids(api_base_to_use)

            build_config["model_name"]["options"] = ids

            # auto-pick if enabled and value is empty (or invalid)
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
                # if auto is off, don't force selection; but clear invalid values
                if current and not current_valid:
                    build_config["model_name"]["value"] = ""

        return build_config
