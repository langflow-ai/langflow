"""Runtime registration of extra OpenAI-compatible model providers.

This module mutates Langflow's in-memory model catalog so providers like
DeepSeek and GLM appear in the "Model providers" dialog, can be configured with
an API key, and instantiate through ``langchain_openai.ChatOpenAI`` pointed at
the provider's ``base_url`` — all WITHOUT editing any Langflow / lfx source
file.

Why this works without touching ``get_llm``:
  * The provider catalog (``MODEL_PROVIDER_METADATA``) and the static model
    lists (``_STATIC_MODELS_DETAILED``) are read every request from the *same*
    objects we mutate here, so in-place mutation is visible immediately.
  * Instantiation resolves the LangChain class via ``get_model_class(name)``,
    which checks ``_model_class_cache`` first. We pre-seed that cache with a
    small factory that injects the right ``base_url``. No per-provider
    ``if/elif`` branch in ``get_llm`` is required.
"""

from __future__ import annotations

import logging
import re
import sys
from typing import Any, Callable

from .config import load_provider_specs

logger = logging.getLogger("langflow_extra_providers")

# Providers we have registered, and the catalog group list we own per provider
# (kept so re-applying refreshes contents instead of duplicating rows).
_OWNED_GROUPS: dict[str, list] = {}
# Generated factories, also exposed as module attributes so the lfx class
# registry can re-import them by name if its cache is ever rebuilt.
_FACTORIES: dict[str, Callable[..., Any]] = {}


def _class_name_for(provider_name: str) -> str:
    slug = re.sub(r"\W+", "_", provider_name).strip("_")
    return f"ChatOpenAICompat__{slug}"


def _make_factory(base_url: str, default_headers: dict[str, str] | None) -> Callable[..., Any]:
    """Build a callable that returns a ChatOpenAI bound to ``base_url``.

    ``get_llm`` calls ``model_class(**kwargs)``; a factory is sufficient (the
    only consumer instantiates it). Importing ChatOpenAI is deferred to call
    time so merely registering a provider never imports langchain_openai.
    """

    def _factory(**kwargs: Any) -> Any:
        from langchain_openai import ChatOpenAI

        kwargs.setdefault("base_url", base_url)
        if default_headers:
            merged = dict(default_headers)
            merged.update(kwargs.get("default_headers") or {})
            kwargs["default_headers"] = merged
        return ChatOpenAI(**kwargs)

    return _factory


def apply(*, force: bool = False) -> list[str]:
    """Register the configured extra providers into Langflow's catalog.

    Idempotent: calling it again refreshes provider definitions without
    creating duplicate catalog rows. Returns the list of provider names added
    (or refreshed). Safe to call when lfx is not importable (returns []).
    """
    try:
        from lfx.base.models import model_metadata as mm
        from lfx.base.models.model_metadata import create_model_metadata
        from lfx.base.models.unified_models import class_registry as cr
        from lfx.base.models.unified_models import provider_queries as pq
    except Exception as exc:  # noqa: BLE001 - lfx absent or internal change
        logger.debug("langflow-extra-providers: lfx unavailable, skipping (%s)", exc)
        return []

    specs = load_provider_specs()
    touched: list[str] = []

    for provider_name, spec in specs.items():
        owned = provider_name in _OWNED_GROUPS
        # Never clobber a provider that Langflow itself defines (e.g. if a
        # future release ships a same-named provider). Only skip when we are
        # not the ones who put it there.
        if provider_name in mm.MODEL_PROVIDER_METADATA and not owned:
            logger.warning(
                "langflow-extra-providers: %r already defined by Langflow; skipping.",
                provider_name,
            )
            continue
        if owned and not force:
            # Already registered by us this process; nothing changed.
            touched.append(provider_name)
            continue

        class_name = _class_name_for(provider_name)
        factory = _make_factory(spec["base_url"], spec.get("default_headers"))
        _FACTORIES[class_name] = factory
        setattr(sys.modules[__name__], class_name, factory)
        # Pre-seed the cache (checked first in _import_class) and add a registry
        # entry as a fallback for any future cache rebuild.
        cr._model_class_cache[class_name] = factory  # noqa: SLF001
        cr._MODEL_CLASS_IMPORTS[class_name] = (__name__, class_name, None)  # noqa: SLF001

        api_key_var = spec["api_key_var"]
        icon = spec.get("icon", "OpenAI")
        mm.MODEL_PROVIDER_METADATA[provider_name] = {
            "icon": icon,
            "max_tokens_field_name": "max_tokens",
            "variables": [
                {
                    "variable_name": f"{provider_name} API Key",
                    "variable_key": api_key_var,
                    "description": spec.get(
                        "description",
                        f"API key for {provider_name} (OpenAI-compatible).",
                    ),
                    "required": True,
                    "is_secret": True,
                    "is_list": False,
                    "options": [],
                    "langchain_param": "api_key",
                    "component_metadata": {
                        "mapping_field": "api_key",
                        "required": False,
                        "advanced": True,
                        "info": f"Falls back to {api_key_var} environment variable",
                    },
                }
            ],
            "api_docs_url": spec.get("api_docs_url", ""),
            "mapping": {"model_class": class_name, "model_param": "model"},
        }

        # Build / refresh the catalog group we own for this provider.
        group = _OWNED_GROUPS.get(provider_name)
        if group is None:
            group = []
            _OWNED_GROUPS[provider_name] = group
            pq._STATIC_MODELS_DETAILED.append(group)  # noqa: SLF001
        group.clear()
        for model in spec.get("models", []):
            name = model.get("name")
            if not name:
                continue
            group.append(
                create_model_metadata(
                    provider=provider_name,
                    name=name,
                    icon=icon,
                    tool_calling=bool(model.get("tool_calling", True)),
                    reasoning=bool(model.get("reasoning", False)),
                )
            )
        touched.append(provider_name)

    # Invalidate derived lru_caches so the new providers are visible.
    for fn in (
        getattr(pq, "get_models_detailed", None),
        getattr(pq, "get_model_provider_variable_mapping", None),
        getattr(pq, "_get_all_provider_specific_field_names", None),
    ):
        clear = getattr(fn, "cache_clear", None)
        if clear is not None:
            try:
                clear()
            except Exception:  # noqa: BLE001
                logger.debug("cache_clear failed for %s", fn, exc_info=True)

    if touched:
        logger.info("langflow-extra-providers: registered providers %s", touched)
    return touched
