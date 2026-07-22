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
import re
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

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
    from collections.abc import Callable, Sequence

# Provider names that ship in core lfx.  Captured at import (before any bundle
# can register) so collision detection never depends on registration order.
_CORE_PROVIDER_NAMES: frozenset[str] = frozenset(MODEL_PROVIDER_METADATA)

_PROVIDER_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_MIN_COMPONENT_MODULE_PARTS = 3
_RESERVED_PROVIDER_METADATA_KEYS = frozenset(
    {"provider", "name", "models", "num_models", "provider_id", "display_name", "aliases"}
)

ClassRef = tuple[str, str, str | None]
"""``(module_path, attribute_name, install_hint | None)`` -- the shape the lazy
class-import tables in ``class_registry`` expect."""


def _derive_provider_id(name: str) -> str:
    """Derive a compatibility ID for manifests that predate ``provider_id``."""
    provider_id = re.sub(r"[^a-z0-9._-]+", "-", name.strip().lower()).strip("-._")
    if not provider_id:
        msg = f"Could not derive a provider_id from provider name {name!r}"
        raise ValueError(msg)
    return provider_id


@dataclass(frozen=True)
class ProviderOrigin:
    """Loader-owned provenance for an extension provider declaration."""

    extension_id: str
    extension_version: str
    distribution: str | None = None
    manifest_path: str | None = None


@dataclass(frozen=True)
class ProviderDescriptor:
    """A bundle-declared model provider, ready to merge into the core tables.

    ``metadata`` mirrors a single ``MODEL_PROVIDER_METADATA`` value (``icon``,
    ``variables``, ``mapping`` with at least ``model_class``, ``api_docs_url``,
    ``max_tokens_field_name``).  The remaining fields supply what metadata alone
    cannot express: the lazy class-import tuples, the embedding wiring, the
    api-key-optional flag, the live-discovery gate, and the dotted-path
    callables for live discovery and credential validation.
    """

    name: str
    metadata: Mapping[str, Any]
    # Stable machine identity used by policy and extension compatibility.
    # ``name`` remains the legacy public selector stored in existing flows.
    provider_id: str | None = None
    display_name: str | None = None
    aliases: tuple[str, ...] = ()
    # LLM chat class, keyed under metadata["mapping"]["model_class"].  Omit when
    # the provider reuses a class already in _MODEL_CLASS_IMPORTS (e.g. an
    # OpenAI-compatible provider reusing "ChatOpenAI").
    model_class: ClassRef | None = None
    # Embedding wiring.  ``embedding_class_name`` is the value stored in
    # EMBEDDING_PROVIDER_CLASS_MAPPING[name] and the key into
    # _EMBEDDING_CLASS_IMPORTS; ``embedding_class`` supplies the import tuple
    # when that class is novel.  ``embedding_param_key``/``embedding_param_mapping``
    # populate EMBEDDING_PARAM_MAPPINGS. The mapping is always available under
    # ``name`` because runtime consumers index it by the selected provider; an
    # alternate key is retained as a compatibility alias for older manifests.
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
    # Dotted-path ``module.path:attr`` callable returning a flat list of
    # model-metadata rows. Provider ownership is stamped by the registry.
    catalog_loader: str | None = None
    # Filled by the extension loader, never by extension.json authors.
    origin: ProviderOrigin | None = None

    def model_class_name(self) -> str | None:
        """Class name this provider's metadata references for its LLM."""
        return (self.metadata.get("mapping") or {}).get("model_class")

    def canonical_id(self) -> str:
        """Return the explicit provider ID or the legacy-compatible derived ID."""
        return self.provider_id or _derive_provider_id(self.name)


# Backward-compatible public name used by existing extension packages.
ProviderSpec = ProviderDescriptor


@dataclass(frozen=True)
class ProviderRegistrySnapshot:
    """Immutable point-in-time view consumed by policy/readiness layers."""

    generation: int
    descriptors_by_id: Mapping[str, ProviderDescriptor]

    @property
    def provider_ids(self) -> frozenset[str]:
        return frozenset(self.descriptors_by_id)


# ---------------------------------------------------------------------------
# Registry state
# ---------------------------------------------------------------------------

_lock = threading.RLock()
_registered: dict[str, ProviderDescriptor] = {}
_registered_ids: dict[str, str] = {}
_registered_aliases: dict[str, str] = {}
# Resolved-callable caches (dotted path -> callable), keyed by provider name.
_live_discovery_cache: dict[str, Callable | None] = {}
_validator_cache: dict[str, Callable | None] = {}
_catalog_cache: dict[str, tuple[dict[str, Any], ...]] = {}
_generation = 0


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


def _core_provider_ids() -> dict[str, str]:
    """Return stable-id -> legacy-name mappings for providers shipped in core."""
    return {
        str(metadata.get("provider_id") or _derive_provider_id(name)): name
        for name, metadata in MODEL_PROVIDER_METADATA.items()
        if name in _CORE_PROVIDER_NAMES
    }


def _core_aliases() -> dict[str, str]:
    aliases: dict[str, str] = {}
    for provider_id, name in _core_provider_ids().items():
        metadata = MODEL_PROVIDER_METADATA[name]
        values = (name, provider_id, metadata.get("display_name"), *(metadata.get("aliases") or ()))
        for value in values:
            if isinstance(value, str) and value:
                aliases[value.casefold()] = name
    return aliases


def _validate_callable_path(value: str, field_name: str, provider_name: str) -> None:
    module_path, sep, attr = value.partition(":")
    if not sep or not module_path or not attr:
        msg = f"ProviderDescriptor {provider_name!r} {field_name} must be of the form 'module.path:attribute'"
        raise ValueError(msg)


def _validate_spec(spec: ProviderDescriptor) -> None:
    """Raise ``ValueError`` if *spec* is missing essentials needed to merge."""
    if not spec.name or not isinstance(spec.name, str):
        msg = "ProviderSpec.name must be a non-empty string"
        raise ValueError(msg)
    if not isinstance(spec.metadata, Mapping):
        msg = f"ProviderSpec.metadata for {spec.name!r} must be a mapping"
        raise ValueError(msg)  # noqa: TRY004 - spec validation surfaces uniformly as ValueError
    reserved_metadata_keys = _RESERVED_PROVIDER_METADATA_KEYS.intersection(spec.metadata)
    if reserved_metadata_keys:
        keys = ", ".join(sorted(reserved_metadata_keys))
        msg = f"ProviderDescriptor.metadata for {spec.name!r} contains reserved keys: {keys}"
        raise ValueError(msg)
    if not spec.model_class_name():
        msg = f"ProviderSpec.metadata for {spec.name!r} must set mapping.model_class"
        raise ValueError(msg)
    if spec.live and spec.conditional_live:
        msg = f"ProviderSpec {spec.name!r} cannot be both live and conditional_live"
        raise ValueError(msg)

    provider_id = spec.canonical_id()
    if not _PROVIDER_ID_RE.fullmatch(provider_id):
        msg = f"ProviderDescriptor.provider_id for {spec.name!r} must match ^[a-z0-9][a-z0-9._-]*$"
        raise ValueError(msg)
    if spec.display_name is not None and not spec.display_name.strip():
        msg = f"ProviderDescriptor.display_name for {spec.name!r} must be non-empty"
        raise ValueError(msg)
    normalized_aliases: set[str] = set()
    for alias in spec.aliases:
        if not isinstance(alias, str) or not alias.strip():
            msg = f"ProviderDescriptor.aliases for {spec.name!r} must contain non-empty strings"
            raise ValueError(msg)
        normalized = alias.casefold()
        if normalized in normalized_aliases:
            msg = f"ProviderDescriptor.aliases for {spec.name!r} contain a duplicate alias {alias!r}"
            raise ValueError(msg)
        normalized_aliases.add(normalized)
    for field_name in ("live_discovery", "validator", "catalog_loader"):
        value = getattr(spec, field_name)
        if value is not None:
            _validate_callable_path(value, field_name, spec.name)


def register_provider(spec: ProviderDescriptor) -> bool:
    """Merge *spec* into the core provider tables in place.

    Returns ``True`` when the provider was registered, ``False`` when it was
    skipped because the name collides with a core or already-registered
    provider (core wins; first bundle wins).  Raises ``ValueError`` if the spec
    is structurally invalid.
    """
    _validate_spec(spec)

    global _generation  # noqa: PLW0603 - registry generation advances atomically with registration

    with _lock:
        provider_id = spec.canonical_id()
        core_aliases = _core_aliases()
        identity_aliases = (spec.name, provider_id, spec.display_name, *spec.aliases)
        normalized_identities = {
            identity.casefold() for identity in identity_aliases if isinstance(identity, str) and identity
        }

        if spec.name in _CORE_PROVIDER_NAMES or spec.name.casefold() in core_aliases:
            logger.warning(
                f"Extension tried to register model provider {spec.name!r}, which is a built-in "
                f"provider; ignoring the bundle definition (core providers take precedence)."
            )
            return False
        if provider_id in _core_provider_ids():
            msg = (
                f"ProviderDescriptor {spec.name!r} provider_id {provider_id!r} conflicts with "
                f"built-in provider {_core_provider_ids()[provider_id]!r}"
            )
            raise ValueError(msg)
        if spec.name in _registered:
            logger.warning(
                f"Model provider {spec.name!r} is already registered by another extension; "
                f"ignoring the duplicate registration (first registration wins)."
            )
            return False
        if provider_id in _registered_ids:
            msg = (
                f"ProviderDescriptor {spec.name!r} provider_id {provider_id!r} conflicts with "
                f"registered provider {_registered_ids[provider_id]!r}"
            )
            raise ValueError(msg)
        conflicting_core_alias = next((alias for alias in normalized_identities if alias in core_aliases), None)
        if conflicting_core_alias is not None:
            msg = (
                f"ProviderDescriptor {spec.name!r} alias {conflicting_core_alias!r} conflicts with "
                f"built-in provider {core_aliases[conflicting_core_alias]!r}"
            )
            raise ValueError(msg)
        conflicting_alias = next((alias for alias in normalized_identities if alias in _registered_aliases), None)
        if conflicting_alias is not None:
            msg = (
                f"ProviderDescriptor {spec.name!r} alias {conflicting_alias!r} conflicts with "
                f"registered provider {_registered_aliases[conflicting_alias]!r}"
            )
            raise ValueError(msg)

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
            if spec.embedding_param_mapping is not None:
                embedding_param_keys = {spec.name}
                if spec.embedding_param_key:
                    embedding_param_keys.add(spec.embedding_param_key)
                conflicting_param_key = next(
                    (key for key in embedding_param_keys if key in EMBEDDING_PARAM_MAPPINGS),
                    None,
                )
                if conflicting_param_key is not None:
                    msg = (
                        f"ProviderSpec {spec.name!r} embedding params {conflicting_param_key!r} "
                        f"conflict with an existing mapping"
                    )
                    raise ValueError(msg)

        # --- metadata (C1) -------------------------------------------------
        metadata = dict(spec.metadata)
        metadata["provider_id"] = provider_id
        metadata["display_name"] = spec.display_name or spec.name
        if spec.aliases:
            metadata["aliases"] = list(spec.aliases)
        MODEL_PROVIDER_METADATA[spec.name] = metadata
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
            if spec.embedding_param_mapping is not None:
                embedding_param_keys = {spec.name}
                if spec.embedding_param_key:
                    embedding_param_keys.add(spec.embedding_param_key)
                for embedding_param_key in embedding_param_keys:
                    EMBEDDING_PARAM_MAPPINGS[embedding_param_key] = dict(spec.embedding_param_mapping)
                    _undo.embedding_param_keys.add(embedding_param_key)

        # --- live-discovery gate (C2) -------------------------------------
        if spec.live and spec.name not in LIVE_MODEL_PROVIDERS:
            LIVE_MODEL_PROVIDERS.append(spec.name)
            _undo.live_names.add(spec.name)
        if spec.conditional_live and spec.name not in CONDITIONAL_LIVE_MODEL_PROVIDERS:
            CONDITIONAL_LIVE_MODEL_PROVIDERS.append(spec.name)
            _undo.conditional_live_names.add(spec.name)

        _registered[spec.name] = spec
        _registered_ids[provider_id] = spec.name
        for identity in normalized_identities:
            _registered_aliases[identity] = spec.name
        _live_discovery_cache.pop(spec.name, None)
        _validator_cache.pop(spec.name, None)
        _catalog_cache.pop(spec.name, None)
        _generation += 1
        _clear_derived_caches()

    logger.debug(f"Registered bundle model provider {spec.name!r}")
    return True


def unregister_provider(name: str) -> bool:
    """Remove one extension provider without disturbing other registrations."""
    global _generation  # noqa: PLW0603 - registry generation advances atomically with removal

    with _lock:
        spec = _registered.pop(name, None)
        if spec is None:
            return False

        provider_id = spec.canonical_id()
        _registered_ids.pop(provider_id, None)
        for alias, registered_name in tuple(_registered_aliases.items()):
            if registered_name == name:
                _registered_aliases.pop(alias, None)

        MODEL_PROVIDER_METADATA.pop(name, None)
        _undo.metadata_keys.discard(name)

        class_name = spec.model_class_name()
        if class_name in _undo.model_class_keys and not any(
            registered.model_class_name() == class_name for registered in _registered.values()
        ):
            _MODEL_CLASS_IMPORTS.pop(class_name, None)
            _undo.model_class_keys.discard(class_name)

        if spec.embedding_class_name:
            EMBEDDING_PROVIDER_CLASS_MAPPING.pop(name, None)
            _undo.embedding_provider_keys.discard(name)
            if spec.embedding_class_name in _undo.embedding_class_keys and not any(
                registered.embedding_class_name == spec.embedding_class_name for registered in _registered.values()
            ):
                _EMBEDDING_CLASS_IMPORTS.pop(spec.embedding_class_name, None)
                _undo.embedding_class_keys.discard(spec.embedding_class_name)

        embedding_param_keys = {name}
        if spec.embedding_param_key:
            embedding_param_keys.add(spec.embedding_param_key)
        for key in embedding_param_keys:
            if key in _undo.embedding_param_keys:
                EMBEDDING_PARAM_MAPPINGS.pop(key, None)
                _undo.embedding_param_keys.discard(key)

        if name in _undo.live_names:
            if name in LIVE_MODEL_PROVIDERS:
                LIVE_MODEL_PROVIDERS.remove(name)
            _undo.live_names.discard(name)
        if name in _undo.conditional_live_names:
            if name in CONDITIONAL_LIVE_MODEL_PROVIDERS:
                CONDITIONAL_LIVE_MODEL_PROVIDERS.remove(name)
            _undo.conditional_live_names.discard(name)

        _live_discovery_cache.pop(name, None)
        _validator_cache.pop(name, None)
        _catalog_cache.pop(name, None)
        _generation += 1
        _clear_derived_caches()

    logger.debug(f"Unregistered bundle model provider {name!r}")
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


def provider_id_for(provider: str) -> str | None:
    """Resolve a legacy name, display name, alias, or provider ID to its stable ID."""
    if not isinstance(provider, str) or not provider:
        return None

    metadata = MODEL_PROVIDER_METADATA.get(provider)
    if metadata is not None:
        return str(metadata.get("provider_id") or _derive_provider_id(provider))

    normalized = provider.casefold()
    core_name = _core_aliases().get(normalized)
    if core_name is not None:
        core_metadata = MODEL_PROVIDER_METADATA[core_name]
        return str(core_metadata.get("provider_id") or _derive_provider_id(core_name))

    registered_name = _registered_aliases.get(normalized)
    if registered_name is None:
        return None
    return _registered[registered_name].canonical_id()


def model_component_provider_id(component: object, *, module_name: str | None = None) -> str:
    """Derive a stable policy identity for a standalone model component.

    Unified-model selectors already carry provider names explicitly. Legacy
    model and embedding components do not, so their package/module identity is
    the most stable systemic signal (``lfx_openai`` -> ``openai`` and
    ``lfx_bundles.mistral`` -> ``mistral``). Known display-name aliases are
    resolved through the registry first, covering names whose package token is
    intentionally shorter (for example IBM watsonx and Google Generative AI).

    A component may explicitly declare ``model_provider_id``. Unknown custom
    model subclasses still receive a deterministic display-name ID rather than
    becoming an unclassified policy bypass; the OSS allow-all service preserves
    compatibility while restrictive plugins can deny that ID.
    """
    explicit_id = getattr(component, "model_provider_id", None)
    if isinstance(explicit_id, str) and explicit_id:
        resolved = provider_id_for(explicit_id)
        return resolved or _derive_provider_id(explicit_id)

    display_name = getattr(component, "display_name", None)
    if isinstance(display_name, str) and (resolved := provider_id_for(display_name)):
        return resolved

    module = module_name or getattr(component.__class__, "__module__", "")
    parts = [part for part in module.split(".") if part]
    candidate: str | None = None
    if parts:
        if parts[0] == "_lfx_ext" and len(parts) >= _MIN_COMPONENT_MODULE_PARTS:
            # Extension modules are imported into
            # ``_lfx_ext.<slot>.<bundle>.*``; the bundle is the stable provider
            # identity even when the component display name adds "Chat" or
            # "Embeddings".
            candidate = parts[2]
        elif parts[0] == "lfx_bundles" and len(parts) > 1:
            candidate = parts[1]
        elif parts[0].startswith("lfx_") and parts[0] not in {"lfx_bundles", "lfx_components"}:
            candidate = parts[0].removeprefix("lfx_")
        elif len(parts) >= _MIN_COMPONENT_MODULE_PARTS and parts[:2] == ["lfx", "components"]:
            candidate = parts[2]

    if candidate:
        return provider_id_for(candidate) or _derive_provider_id(candidate)
    if isinstance(display_name, str) and display_name.strip():
        return _derive_provider_id(display_name)
    return _derive_provider_id(component.__class__.__name__)


def uses_standalone_model_provider_policy(component: object) -> bool:
    """Return whether the outer component boundary owns provider enforcement.

    Unified selector components delegate to ``get_llm``/``get_embeddings`` so
    the selected provider—not the wrapper's module—is enforced. Local utility
    components can opt out because they do not invoke a model provider.
    """
    return getattr(component, "model_provider_policy_mode", "standalone") == "standalone"


def provider_name_for_id(provider_id: str) -> str | None:
    """Return the legacy public provider name for a stable provider ID."""
    if not isinstance(provider_id, str) or not provider_id:
        return None
    core_name = _core_provider_ids().get(provider_id)
    if core_name is not None:
        return core_name
    return _registered_ids.get(provider_id)


def get_provider_descriptor(provider: str) -> ProviderDescriptor | None:
    """Return a descriptor for a core or extension provider."""
    provider_id = provider_id_for(provider)
    if provider_id is None:
        return None
    name = provider_name_for_id(provider_id)
    if name is None:
        return None
    registered = _registered.get(name)
    if registered is not None:
        return registered
    return ProviderDescriptor(
        name=name,
        provider_id=provider_id,
        display_name=str(MODEL_PROVIDER_METADATA[name].get("display_name") or name),
        aliases=tuple(MODEL_PROVIDER_METADATA[name].get("aliases") or ()),
        metadata=dict(MODEL_PROVIDER_METADATA[name]),
    )


def get_registry_snapshot(*, validate_catalogs: bool = False) -> ProviderRegistrySnapshot:
    """Return an immutable registry snapshot after optional eager catalog validation."""
    if validate_catalogs:
        validate_registered_provider_catalogs()
    with _lock:
        descriptors = {
            provider_id: _freeze_descriptor(descriptor)
            for provider_id in _core_provider_ids() | _registered_ids
            if (descriptor := get_provider_descriptor(provider_id)) is not None
        }
        return ProviderRegistrySnapshot(
            generation=_generation,
            descriptors_by_id=MappingProxyType(descriptors),
        )


def _freeze_value(value: Any) -> Any:
    """Recursively freeze manifest-owned containers for snapshot consumers."""
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze_value(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze_value(item) for item in value)
    return value


def _freeze_descriptor(descriptor: ProviderDescriptor) -> ProviderDescriptor:
    embedding_mapping = (
        _freeze_value(descriptor.embedding_param_mapping) if descriptor.embedding_param_mapping is not None else None
    )
    return replace(
        descriptor,
        metadata=_freeze_value(descriptor.metadata),
        embedding_param_mapping=embedding_mapping,
    )


def _load_registered_catalog(provider: str) -> tuple[dict[str, Any], ...]:
    if provider in _catalog_cache:
        return _catalog_cache[provider]

    spec = _registered.get(provider)
    if spec is None or spec.catalog_loader is None:
        _catalog_cache[provider] = ()
        return ()

    loader = _resolve_callable(spec.catalog_loader)
    rows = loader()
    if not isinstance(rows, list):
        msg = f"Catalog loader for provider {provider!r} must return a list of model metadata rows"
        raise TypeError(msg)

    normalized_rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    provider_metadata = MODEL_PROVIDER_METADATA[provider]
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            msg = f"Catalog loader for provider {provider!r} returned non-dict row at index {index}"
            raise TypeError(msg)
        name = row.get("name")
        if not isinstance(name, str) or not name.strip():
            msg = f"Catalog loader for provider {provider!r} returned row {index} without a model name"
            raise ValueError(msg)
        normalized_name = name.strip()
        model_type = row.get("model_type", "llm")
        if model_type not in {"llm", "embeddings"}:
            msg = (
                f"Catalog loader for provider {provider!r} returned unsupported model_type "
                f"{model_type!r} at row {index}"
            )
            raise ValueError(msg)
        key = (model_type, normalized_name)
        if key in seen:
            msg = f"Catalog loader for provider {provider!r} returned duplicate model identity {key!r}"
            raise ValueError(msg)
        seen.add(key)

        normalized = dict(row)
        normalized["provider"] = provider
        normalized["name"] = normalized_name
        normalized["model_type"] = model_type
        normalized.setdefault("icon", provider_metadata.get("icon", "Bot"))
        normalized_rows.append(normalized)

    result = tuple(normalized_rows)
    _catalog_cache[provider] = result
    return result


def get_registered_model_catalogs() -> list[list[dict[str, Any]]]:
    """Return validated static catalog groups contributed by provider extensions.

    A bad optional extension is isolated from the shared catalog and logged. A
    deployment that requires an extension should call
    :func:`validate_registered_provider_catalogs` during readiness and fail
    startup on the same error.
    """
    groups: list[list[dict[str, Any]]] = []
    for provider in _registered:
        try:
            rows = _load_registered_catalog(provider)
        except Exception as exc:  # noqa: BLE001 - extension import and execution are isolated here
            logger.warning(f"Could not load static model catalog for provider {provider!r}: {exc}")
            continue
        if rows:
            groups.append([dict(row) for row in rows])
    return groups


def validate_registered_provider_catalogs(providers: Sequence[str] | None = None) -> None:
    """Eagerly validate provider catalogs for startup/readiness checks."""
    selected = tuple(providers) if providers is not None else tuple(_registered)
    for provider in selected:
        name = provider_name_for_id(provider) or provider
        if name not in _registered:
            msg = f"Cannot validate catalog for unregistered extension provider {provider!r}"
            raise ValueError(msg)
        _load_registered_catalog(name)


# ---------------------------------------------------------------------------
# Test seam
# ---------------------------------------------------------------------------


def clear() -> None:
    """Reverse every registration, restoring the core tables to their import state.

    Intended for tests so a registered provider does not leak across cases.
    """
    global _generation  # noqa: PLW0603 - test seam restores an empty extension generation

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
        _registered_ids.clear()
        _registered_aliases.clear()
        _live_discovery_cache.clear()
        _validator_cache.clear()
        _catalog_cache.clear()
        _undo.metadata_keys.clear()
        _undo.model_class_keys.clear()
        _undo.embedding_class_keys.clear()
        _undo.embedding_provider_keys.clear()
        _undo.embedding_param_keys.clear()
        _undo.live_names.clear()
        _undo.conditional_live_names.clear()
        _generation += 1
        _clear_derived_caches()
