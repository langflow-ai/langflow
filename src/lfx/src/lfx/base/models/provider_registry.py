"""Process-wide registry for bundle-contributed model providers.

Langflow's model-provider system (``MODEL_PROVIDER_METADATA``, the lazy
class-import tables in ``unified_models.class_registry``, the
``LIVE_MODEL_PROVIDERS`` gate, and the credential/instantiation/live-discovery
dispatch) is defined as static module-level data in this package.  A third
party historically could not add a provider without editing those core files.

This module is the supported extension point.  An extension bundle declares
providers in its manifest (``providers[]``); at load time the extension loader
builds a :class:`ProviderSpec` for each and calls :func:`register_provider`,
which merges the provider into the core tables **in place**.  Because every
existing accessor reads those same objects -- the ``@lru_cache``-d variable
maps, the module-level ``model_provider_metadata`` reference, the
``/api/v1/models`` surface -- a registered provider becomes visible everywhere
with no further edits.  Live-discovery and credential-validation callables are
referenced by dotted path and imported lazily only when invoked, so a
registered provider adds no import cost until it is actually used.

Guarantees:

- **Core wins.** A bundle that re-declares a built-in provider name is ignored
  with a warning; the built-in definition is never overwritten.
- **Zero cost when empty.** With no provider registered, nothing mutates and
  behavior is byte-identical to the un-patched tables.
- **Failure isolation.** Registration validates the spec and raises on a bad
  one (the loader catches per-provider); a broken live-discovery/validator
  import degrades to "no live models" / "generic validation", never a crash.

Registration happens once, at single-threaded startup, before any request
touches the model system.  A lock guards the bookkeeping so a future
concurrent loader stays correct, and :func:`clear` undoes every mutation as a
test seam.
"""

from __future__ import annotations

import importlib
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from lfx.base.models.model_metadata import (
    CONDITIONAL_LIVE_MODEL_PROVIDERS,
    LIVE_MODEL_PROVIDERS,
    MODEL_PROVIDER_METADATA,
)
from lfx.base.models.unified_models.class_registry import (
    _EMBEDDING_CLASS_IMPORTS,
    _MODEL_CLASS_IMPORTS,
    EMBEDDING_PARAM_MAPPINGS,
    EMBEDDING_PROVIDER_CLASS_MAPPING,
)
from lfx.log.logger import logger

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

# Provider names that ship in core lfx.  Captured at import (before any bundle
# can register) so collision detection never depends on registration order.
_CORE_PROVIDER_NAMES: frozenset[str] = frozenset(MODEL_PROVIDER_METADATA)

ClassRef = tuple[str, str, str | None]
"""``(module_path, attribute_name, install_hint | None)`` -- the shape the lazy
class-import tables in ``class_registry`` expect."""


@dataclass(frozen=True)
class ProviderSpec:
    """A bundle-declared model provider, ready to merge into the core tables.

    ``metadata`` mirrors a single ``MODEL_PROVIDER_METADATA`` value (``icon``,
    ``variables``, ``mapping`` with at least ``model_class``, ``api_docs_url``,
    ``max_tokens_field_name``).  The remaining fields supply what metadata alone
    cannot express: the lazy class-import tuples, the embedding wiring, the
    api-key-optional flag, the live-discovery gate, and the dotted-path
    callables for live discovery and credential validation.
    """

    name: str
    metadata: dict
    # LLM chat class, keyed under metadata["mapping"]["model_class"].  Omit when
    # the provider reuses a class already in _MODEL_CLASS_IMPORTS (e.g. an
    # OpenAI-compatible provider reusing "ChatOpenAI").
    model_class: ClassRef | None = None
    # Embedding wiring.  ``embedding_class_name`` is the value stored in
    # EMBEDDING_PROVIDER_CLASS_MAPPING[name] and the key into
    # _EMBEDDING_CLASS_IMPORTS; ``embedding_class`` supplies the import tuple
    # when that class is novel.  ``embedding_param_key``/``embedding_param_mapping``
    # populate EMBEDDING_PARAM_MAPPINGS.
    embedding_class_name: str | None = None
    embedding_class: ClassRef | None = None
    embedding_param_key: str | None = None
    embedding_param_mapping: Mapping[str, str] | None = None
    # Whether get_llm / get_embeddings must raise when no API key is configured.
    # OpenAI-compatible local servers (vLLM, Ollama) set this False.
    api_key_required: bool = True
    # Live model discovery.  ``live`` adds the provider to LIVE_MODEL_PROVIDERS;
    # ``conditional_live`` adds it to CONDITIONAL_LIVE_MODEL_PROVIDERS instead
    # (live only when a custom endpoint is configured).
    live: bool = False
    conditional_live: bool = False
    # Dotted-path "module.path:attr" callables, imported lazily on first use.
    #   live_discovery(user_id, model_type) -> list[dict]
    #   validator(provider, variables, model_name) -> None  (raises ValueError on failure)
    live_discovery: str | None = None
    validator: str | None = None

    def model_class_name(self) -> str | None:
        """Class name this provider's metadata references for its LLM."""
        return (self.metadata.get("mapping") or {}).get("model_class")


# ---------------------------------------------------------------------------
# Registry state
# ---------------------------------------------------------------------------

_lock = threading.RLock()
_registered: dict[str, ProviderSpec] = {}
# Resolved-callable caches (dotted path -> callable), keyed by provider name.
_live_discovery_cache: dict[str, Callable | None] = {}
_validator_cache: dict[str, Callable | None] = {}


@dataclass
class _Undo:
    """Bookkeeping so :func:`clear` can reverse every in-place mutation."""

    metadata_keys: set[str] = field(default_factory=set)
    model_class_keys: set[str] = field(default_factory=set)
    embedding_class_keys: set[str] = field(default_factory=set)
    embedding_provider_keys: set[str] = field(default_factory=set)
    embedding_param_keys: set[str] = field(default_factory=set)
    live_names: set[str] = field(default_factory=set)
    conditional_live_names: set[str] = field(default_factory=set)


_undo = _Undo()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def _validate_spec(spec: ProviderSpec) -> None:
    """Raise ``ValueError`` if *spec* is missing essentials needed to merge."""
    if not spec.name or not isinstance(spec.name, str):
        msg = "ProviderSpec.name must be a non-empty string"
        raise ValueError(msg)
    if not isinstance(spec.metadata, dict):
        msg = f"ProviderSpec.metadata for {spec.name!r} must be a dict"
        raise ValueError(msg)  # noqa: TRY004 - spec validation surfaces uniformly as ValueError
    if not spec.model_class_name():
        msg = f"ProviderSpec.metadata for {spec.name!r} must set mapping.model_class"
        raise ValueError(msg)
    if spec.live and spec.conditional_live:
        msg = f"ProviderSpec {spec.name!r} cannot be both live and conditional_live"
        raise ValueError(msg)


def register_provider(spec: ProviderSpec) -> bool:
    """Merge *spec* into the core provider tables in place.

    Returns ``True`` when the provider was registered, ``False`` when it was
    skipped because the name collides with a core or already-registered
    provider (core wins; first bundle wins).  Raises ``ValueError`` if the spec
    is structurally invalid.
    """
    _validate_spec(spec)

    with _lock:
        if spec.name in _CORE_PROVIDER_NAMES:
            logger.warning(
                f"Extension tried to register model provider {spec.name!r}, which is a built-in "
                f"provider; ignoring the bundle definition (core providers take precedence)."
            )
            return False
        if spec.name in _registered:
            logger.warning(
                f"Model provider {spec.name!r} is already registered by another extension; "
                f"ignoring the duplicate registration (first registration wins)."
            )
            return False

        # Validate lazy-import + embedding keys before mutating any global table,
        # so a malformed spec is rejected wholesale (never partially applied) and
        # never clobbers a core/earlier-extension mapping that clear() would then
        # remove.
        class_name = spec.model_class_name()
        if class_name not in _MODEL_CLASS_IMPORTS and spec.model_class is None:
            msg = (
                f"ProviderSpec {spec.name!r} references unknown model class "
                f"{class_name!r} (no model_class import supplied)"
            )
            raise ValueError(msg)
        if (
            spec.model_class
            and class_name in _MODEL_CLASS_IMPORTS
            and _MODEL_CLASS_IMPORTS[class_name] != spec.model_class
        ):
            msg = f"ProviderSpec {spec.name!r} model class {class_name!r} conflicts with an existing import"
            raise ValueError(msg)
        if spec.embedding_class_name:
            if spec.embedding_class_name not in _EMBEDDING_CLASS_IMPORTS and spec.embedding_class is None:
                msg = (
                    f"ProviderSpec {spec.name!r} references unknown embedding class "
                    f"{spec.embedding_class_name!r} (no embedding_class import supplied)"
                )
                raise ValueError(msg)
            if (
                spec.embedding_class
                and spec.embedding_class_name in _EMBEDDING_CLASS_IMPORTS
                and _EMBEDDING_CLASS_IMPORTS[spec.embedding_class_name] != spec.embedding_class
            ):
                msg = (
                    f"ProviderSpec {spec.name!r} embedding class {spec.embedding_class_name!r} "
                    f"conflicts with an existing import"
                )
                raise ValueError(msg)
            if spec.embedding_param_key and spec.embedding_param_key in EMBEDDING_PARAM_MAPPINGS:
                msg = (
                    f"ProviderSpec {spec.name!r} embedding params {spec.embedding_param_key!r} "
                    f"conflict with an existing mapping"
                )
                raise ValueError(msg)

        # --- metadata (C1) -------------------------------------------------
        MODEL_PROVIDER_METADATA[spec.name] = spec.metadata
        _undo.metadata_keys.add(spec.name)

        # --- LLM class lazy-import (C3) ------------------------------------
        if spec.model_class and class_name and class_name not in _MODEL_CLASS_IMPORTS:
            _MODEL_CLASS_IMPORTS[class_name] = spec.model_class
            _undo.model_class_keys.add(class_name)

        # --- embedding wiring (C4) ----------------------------------------
        if spec.embedding_class_name:
            EMBEDDING_PROVIDER_CLASS_MAPPING[spec.name] = spec.embedding_class_name
            _undo.embedding_provider_keys.add(spec.name)
            if spec.embedding_class and spec.embedding_class_name not in _EMBEDDING_CLASS_IMPORTS:
                _EMBEDDING_CLASS_IMPORTS[spec.embedding_class_name] = spec.embedding_class
                _undo.embedding_class_keys.add(spec.embedding_class_name)
            if spec.embedding_param_key and spec.embedding_param_mapping is not None:
                EMBEDDING_PARAM_MAPPINGS[spec.embedding_param_key] = dict(spec.embedding_param_mapping)
                _undo.embedding_param_keys.add(spec.embedding_param_key)

        # --- live-discovery gate (C2) -------------------------------------
        if spec.live and spec.name not in LIVE_MODEL_PROVIDERS:
            LIVE_MODEL_PROVIDERS.append(spec.name)
            _undo.live_names.add(spec.name)
        if spec.conditional_live and spec.name not in CONDITIONAL_LIVE_MODEL_PROVIDERS:
            CONDITIONAL_LIVE_MODEL_PROVIDERS.append(spec.name)
            _undo.conditional_live_names.add(spec.name)

        _registered[spec.name] = spec
        _live_discovery_cache.pop(spec.name, None)
        _validator_cache.pop(spec.name, None)
        _clear_derived_caches()

    logger.debug(f"Registered bundle model provider {spec.name!r}")
    return True


def _clear_derived_caches() -> None:
    """Drop ``@lru_cache`` results that derive structures from the metadata.

    The metadata dict itself is shared by reference, so most accessors already
    see new entries; only the caches that build *new* objects from it must be
    invalidated.  Imported lazily to avoid an import cycle.
    """
    from lfx.base.models.unified_models import provider_queries

    provider_queries.get_model_provider_variable_mapping.cache_clear()
    provider_queries._get_all_provider_specific_field_names.cache_clear()  # noqa: SLF001 - known internal cache
    provider_queries.get_models_detailed.cache_clear()


# ---------------------------------------------------------------------------
# Dispatch lookups (used by the credential / live-discovery / instantiation seams)
# ---------------------------------------------------------------------------


def is_registered(provider: str) -> bool:
    """True if *provider* was contributed by a bundle (not a core provider)."""
    return provider in _registered


def is_api_key_optional(provider: str) -> bool:
    """True if *provider* is a registered provider that does not require an API key."""
    spec = _registered.get(provider)
    return spec is not None and not spec.api_key_required


def _resolve_callable(dotted: str) -> Callable:
    """Import a ``"module.path:attr"`` callable.  Raises on a malformed path."""
    module_path, sep, attr = dotted.partition(":")
    if not sep or not module_path or not attr:
        msg = f"Callable path {dotted!r} must be of the form 'module.path:attribute'"
        raise ValueError(msg)
    module = importlib.import_module(module_path)
    resolved = getattr(module, attr)
    if not callable(resolved):
        msg = f"Callable path {dotted!r} resolved to a non-callable attribute"
        raise ValueError(msg)  # noqa: TRY004 - callable-ref resolution surfaces uniformly as ValueError
    return resolved


def live_discovery_for(provider: str) -> Callable | None:
    """Return the registered live-discovery callable for *provider*, or ``None``.

    A malformed or unimportable path degrades to ``None`` (logged) so a broken
    bundle yields "no live models" rather than breaking the model catalog.
    """
    if provider in _live_discovery_cache:
        return _live_discovery_cache[provider]
    spec = _registered.get(provider)
    resolved: Callable | None = None
    if spec is not None and spec.live_discovery:
        try:
            resolved = _resolve_callable(spec.live_discovery)
        except Exception as exc:  # noqa: BLE001 - extension import side effects (SyntaxError, etc.) must stay isolated
            logger.warning(f"Could not load live-discovery callable for provider {provider!r}: {exc}")
            resolved = None
    _live_discovery_cache[provider] = resolved
    return resolved


def validator_for(provider: str) -> Callable | None:
    """Return the registered credential-validation callable for *provider*, or ``None``."""
    if provider in _validator_cache:
        return _validator_cache[provider]
    spec = _registered.get(provider)
    resolved: Callable | None = None
    if spec is not None and spec.validator:
        try:
            resolved = _resolve_callable(spec.validator)
        except Exception as exc:  # noqa: BLE001 - extension import side effects (SyntaxError, etc.) must stay isolated
            logger.warning(f"Could not load validator callable for provider {provider!r}: {exc}")
            resolved = None
    _validator_cache[provider] = resolved
    return resolved


def registered_provider_names() -> frozenset[str]:
    """Snapshot of the names contributed by bundles."""
    return frozenset(_registered)


# ---------------------------------------------------------------------------
# Test seam
# ---------------------------------------------------------------------------


def clear() -> None:
    """Reverse every registration, restoring the core tables to their import state.

    Intended for tests so a registered provider does not leak across cases.
    """
    with _lock:
        for key in _undo.metadata_keys:
            MODEL_PROVIDER_METADATA.pop(key, None)
        for key in _undo.model_class_keys:
            _MODEL_CLASS_IMPORTS.pop(key, None)
        for key in _undo.embedding_class_keys:
            _EMBEDDING_CLASS_IMPORTS.pop(key, None)
        for key in _undo.embedding_provider_keys:
            EMBEDDING_PROVIDER_CLASS_MAPPING.pop(key, None)
        for key in _undo.embedding_param_keys:
            EMBEDDING_PARAM_MAPPINGS.pop(key, None)
        for name in _undo.live_names:
            if name in LIVE_MODEL_PROVIDERS:
                LIVE_MODEL_PROVIDERS.remove(name)
        for name in _undo.conditional_live_names:
            if name in CONDITIONAL_LIVE_MODEL_PROVIDERS:
                CONDITIONAL_LIVE_MODEL_PROVIDERS.remove(name)
        _registered.clear()
        _live_discovery_cache.clear()
        _validator_cache.clear()
        _undo.metadata_keys.clear()
        _undo.model_class_keys.clear()
        _undo.embedding_class_keys.clear()
        _undo.embedding_provider_keys.clear()
        _undo.embedding_param_keys.clear()
        _undo.live_names.clear()
        _undo.conditional_live_names.clear()
        _clear_derived_caches()
