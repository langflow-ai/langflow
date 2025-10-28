import httpx
from langchain_openai import ChatOpenAI
from pydantic.v1 import SecretStr

from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import DropdownInput, IntInput, SecretStrInput, SliderInput

# Max depth to search nested structures when discovering models
MAX_NESTED_DEPTH = 3


class HeliconeComponent(LCModelComponent):
    """Helicone API component for language models."""

    display_name = "Helicone"
    description = (
        "Helicone provides AI routing and observability with unified access to "
        "multiple AI models from different providers."
    )
    icon = "Helicone"

    inputs = [
        *LCModelComponent.get_base_inputs(),
        SecretStrInput(name="api_key", display_name="API Key", required=True),
        DropdownInput(
            name="model_name",
            display_name="Model",
            options=[],
            value="",
            refresh_button=True,
            real_time_refresh=True,
            required=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.7,
            range_spec=RangeSpec(min=0, max=2, step=0.01),
            advanced=True,
        ),
        IntInput(name="max_tokens", display_name="Max Tokens", advanced=True),
    ]

    def fetch_models(self) -> list[dict]:
        """Fetch available models from Helicone.

        Expected shape (from the public endpoint):
        { "data": { "models": [ { id, name, author, contextLength, endpoints, ... } ] } }
        Falls back to a lenient parser for other historical shapes.
        """
        try:
            response = httpx.get("https://jawn.helicone.ai/v1/public/model-registry/models", timeout=10.0)
            response.raise_for_status()
            data = response.json()

            models: list = []

            # Prefer the documented structure first: data.models
            if isinstance(data, dict):
                inner = data.get("data")
                if isinstance(inner, dict) and isinstance(inner.get("models"), list):
                    models = inner["models"]

            # Fallbacks for historical or alternative shapes
            if not models:
                if isinstance(data, list):
                    models = data
                elif isinstance(data, dict):
                    # Direct list at top-level or other common keys
                    if isinstance(data.get("models"), list):
                        models = data["models"]
                    elif isinstance(data.get("data"), list):
                        models = data["data"]
                    else:
                        # Last-resort nested search with guardrails
                        def find_models(obj: dict, depth: int = 0) -> list:
                            if depth > MAX_NESTED_DEPTH:
                                return []
                            for key in ("models", "items", "result"):  # avoid matching filters.providers
                                val = obj.get(key)
                                if isinstance(val, list):
                                    return val
                                if isinstance(val, dict):
                                    found = find_models(val, depth + 1)
                                    if found:
                                        return found
                            # Also traverse known container keys
                            for key in ("data", "payload"):
                                val = obj.get(key)
                                if isinstance(val, dict):
                                    found = find_models(val, depth + 1)
                                    if found:
                                        return found
                            return []

                        models = find_models(data)

            if not models:
                self.log(f"Unexpected API response structure from Jawn: {type(data)} — using empty list")
                return []

            parsed: list[dict] = []
            for m in models:
                if isinstance(m, str):
                    parsed.append({"id": m, "name": m, "context": 0})
                    continue
                if isinstance(m, dict):
                    # Prefer stable identifiers; fall back to provider model id if present
                    mid = m.get("id") or m.get("model") or m.get("providerModelId") or m.get("slug") or m.get("name")
                    if not mid:
                        # Skip entries without a stable identifier
                        continue
                    name = m.get("name") or mid
                    # support multiple possible context length keys
                    ctx = (
                        m.get("contextLength")
                        or m.get("context_length")
                        or m.get("context")
                        or m.get("maxCompletionTokens")
                        or 0
                    )
                    try:
                        ctx_int = int(ctx)  # best effort normalization
                    except (TypeError, ValueError):
                        ctx_int = 0
                    # Optionally capture provider information when available
                    provider = m.get("author")
                    try:
                        eps = m.get("endpoints")
                        if isinstance(eps, list) and eps:
                            ep0 = eps[0]
                            if isinstance(ep0, dict):
                                provider = ep0.get("provider") or ep0.get("providerSlug") or provider
                    except Exception:  # noqa: BLE001
                        provider = None

                    # Derive richer metadata for UI tooltips
                    supported_params = m.get("supportedParameters") or []
                    supports_tools = False
                    try:
                        if isinstance(supported_params, list):
                            lowered = [str(x).lower() for x in supported_params]
                            supports_tools = any(k in lowered for k in ("tools", "tool_choice"))
                    except (TypeError, ValueError):
                        supports_tools = False

                    max_output = m.get("maxOutput") or m.get("max_output")
                    try:
                        max_output = int(max_output) if max_output is not None else None
                    except (TypeError, ValueError):
                        max_output = None

                    input_modalities = m.get("inputModalities") or []
                    output_modalities = m.get("outputModalities") or []
                    description = m.get("description")
                    training_date = m.get("trainingDate") or m.get("training_date")

                    parsed.append(
                        {
                            "id": mid,
                            "name": name,
                            "context": ctx_int,
                            **({"provider": provider} if provider else {}),
                            **({"supports_tools": supports_tools} if supports_tools else {}),
                            **({"max_output": max_output} if max_output is not None else {}),
                            **({"input_modalities": input_modalities} if input_modalities else {}),
                            **({"output_modalities": output_modalities} if output_modalities else {}),
                            **({"description": description} if description else {}),
                            **({"training_date": training_date} if training_date else {}),
                        }
                    )

            return sorted(parsed, key=lambda x: x["name"]) if parsed else []
        except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as e:
            self.log(f"Error fetching models: {e}")
            return []

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:  # noqa: ARG002
        """Update model options."""
        try:
            models = self.fetch_models()
            model_cfg = build_config.get("model_name") if hasattr(build_config, "get") else build_config["model_name"]
            if models:
                options = [m["id"] for m in models]

                def build_tip(m: dict) -> str:
                    parts: list[str] = []
                    full_name = m.get("name") or m.get("id")
                    model_id = m.get("id")
                    provider = m.get("provider")
                    ctx = m.get("context")
                    max_out = m.get("max_output")
                    tools = m.get("supports_tools")
                    in_mod = m.get("input_modalities") or []
                    out_mod = m.get("output_modalities") or []
                    parts.append(full_name if full_name else str(model_id))
                    if provider:
                        parts.append(f"by {provider}")
                    if ctx:
                        parts.append(f"context {ctx:,}")
                    if max_out:
                        parts.append(f"max out {max_out:,}")
                    if tools is True:
                        parts.append("tools ✓")
                    if in_mod:
                        parts.append(f"in: {','.join(map(str, in_mod))}")
                    if out_mod:
                        parts.append(f"out: {','.join(map(str, out_mod))}")
                    # Join compactly for tooltip display
                    return " • ".join(parts)

                tooltips = {m["id"]: build_tip(m) for m in models}

                # Build options_metadata for richer UI rendering and hover tooltips
                def build_meta(m: dict) -> dict:
                    meta: dict = {}
                    if m.get("name"):
                        meta["name"] = m["name"]
                    if m.get("provider"):
                        meta["provider"] = m["provider"]
                    if m.get("context"):
                        meta["context"] = f"{int(m['context']):,}"
                    if m.get("max_output") is not None:
                        try:
                            meta["max_output"] = f"{int(m['max_output']):,}"
                        except (TypeError, ValueError):
                            meta["max_output"] = str(m["max_output"])
                    if m.get("supports_tools"):
                        meta["tools"] = "yes"
                    return meta

                model_cfg["options_metadata"] = [build_meta(m) for m in models]
                model_cfg["options"] = options
                # Some UIs still read this legacy field; set for compatibility
                model_cfg["tooltips"] = tooltips
                # Keep current value if still valid; else pick first option
                current = model_cfg.get("value")
                if current not in options:
                    model_cfg["value"] = options[0] if options else ""
            else:
                model_cfg["options"] = ["Failed to load models"]
                model_cfg["value"] = "Failed to load models"
        except Exception as e:  # noqa: BLE001
            # Never let dynamic updates break the UI; log and return original config
            self.log(f"Helicone update_build_config failed: {e}")
            return build_config
        return build_config

    def build_model(self) -> LanguageModel:
        """Build the Helicone model."""
        if not self.api_key:
            msg = "API key is required"
            raise ValueError(msg)
        if not self.model_name or self.model_name == "Loading...":
            msg = "Please select a model"
            raise ValueError(msg)

        kwargs = {
            "model": self.model_name,
            "openai_api_key": SecretStr(self.api_key).get_secret_value(),
            "openai_api_base": "https://ai-gateway.helicone.ai/v1",
            "temperature": self.temperature if self.temperature is not None else 0.7,
        }

        if self.max_tokens:
            kwargs["max_tokens"] = int(self.max_tokens)

        return ChatOpenAI(**kwargs)
