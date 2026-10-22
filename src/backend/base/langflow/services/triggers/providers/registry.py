"""Server trigger hooks owned by installed integration bundles."""

from __future__ import annotations

import re
from dataclasses import dataclass
from importlib import metadata
from typing import TYPE_CHECKING, Any, Literal

from lfx.log.logger import logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from datetime import datetime

    from lfx.integrations.models import CredentialLease
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.connection.oauth.adapter import OAuthAdapter
    from langflow.services.database.models.connection.schemas import ConnectionCreate
    from langflow.services.database.models.trigger.model import Trigger, TriggerCleanup, TriggerSubscription
    from langflow.services.triggers.ingress.verifiers import IngressSecrets, Verified
    from langflow.services.triggers.listeners.adapters import ListenerAdapter, ListenerTrigger
    from langflow.services.triggers.source_poll import SourceRound

ENTRY_POINT_GROUP = "langflow.trigger_providers"
_MAX_PROVIDER_ID_LENGTH = 32
_MAX_KIND_LENGTH = 64
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]*$")
_KIND = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_COMPONENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SECRET_FIELDS = re.compile(r"token|secret|password|privatekey|apikey|credential", re.IGNORECASE)
_BUILTINS = frozenset({"slack", "microsoft", "google", "webhook"})


@dataclass(frozen=True)
class TriggerKind:
    """A bundle component's public configuration and supported transports."""

    kind: str
    component: str
    display_name: str
    config_fields: tuple[str, ...]
    required_scopes: tuple[str, ...] = ()
    identity: Literal["user_delegated", "bot", "service"] = "user_delegated"
    poll_mechanism: str | None = None
    push_mechanism: str | None = None
    listener_factory: Callable[[ListenerTrigger], ListenerAdapter] | None = None
    listener_mechanism: str | None = None


@dataclass(frozen=True)
class TriggerProvider:
    """Trusted server hooks loaded only from the owning bundle distribution."""

    provider_id: str
    bundle: str
    kinds: tuple[TriggerKind, ...]
    normalize_config: Callable[[str, dict[str, Any]], dict[str, Any]]
    collect: Callable[[Trigger, CredentialLease], Awaitable[SourceRound]] | None = None
    provision: Callable[[AsyncSession, Trigger], Awaitable[TriggerSubscription | None]] | None = None
    renew: Callable[[AsyncSession, TriggerSubscription], Awaitable[datetime]] | None = None
    revoke: Callable[[TriggerCleanup, CredentialLease], Awaitable[None]] | None = None
    verify: Callable[..., Verified] | None = None
    verify_get: Callable[..., Verified] | None = None
    ingress_secrets: Callable[[AsyncSession, Trigger], Awaitable[IngressSecrets]] | None = None
    ingress_is_hint: bool = False
    api_origins: tuple[str, ...] = ()
    validate_manual_credential: Callable[..., Awaitable[ConnectionCreate]] | None = None
    oauth: OAuthAdapter | None = None
    prepare: Callable[[AsyncSession, Trigger], Awaitable[None]] | None = None

    def __post_init__(self) -> None:
        if (
            not _KIND.fullmatch(self.provider_id)
            or len(self.provider_id) > _MAX_PROVIDER_ID_LENGTH
            or self.provider_id in _BUILTINS
        ):
            msg = "A trigger extension must own a distinct provider id."
            raise ValueError(msg)
        if not _IDENTIFIER.fullmatch(self.bundle) or not self.kinds or not callable(self.normalize_config):
            msg = "A trigger extension requires a bundle, kinds, and a configuration validator."
            raise ValueError(msg)
        seen: set[str] = set()
        components: set[str] = set()
        for spec in self.kinds:
            mechanisms = (spec.poll_mechanism, spec.push_mechanism, spec.listener_mechanism)
            if (
                not _KIND.fullmatch(spec.kind)
                or len(spec.kind) > _MAX_KIND_LENGTH
                or not spec.kind.startswith(f"{self.provider_id}.")
                or spec.kind in seen
                or spec.component in components
                or not _COMPONENT.fullmatch(spec.component)
                or not spec.display_name.strip()
                or "connection" not in spec.config_fields
                or len(set(spec.config_fields)) != len(spec.config_fields)
                or any(
                    not _IDENTIFIER.fullmatch(field) or _SECRET_FIELDS.search(field.replace("_", ""))
                    for field in spec.config_fields
                )
                or spec.identity not in {"user_delegated", "bot", "service"}
                or not any(mechanisms)
                or any(
                    value is not None and (not _KIND.fullmatch(value) or not value.startswith(f"{self.provider_id}."))
                    for value in mechanisms
                )
            ):
                msg = "A trigger extension declares invalid or duplicate kind metadata."
                raise ValueError(msg)
            if spec.poll_mechanism and self.collect is None:
                msg = "Polling trigger kinds require a collector."
                raise ValueError(msg)
            if spec.push_mechanism and self.verify is None:
                msg = "Push trigger kinds require a signature verifier."
                raise ValueError(msg)
            if bool(spec.listener_mechanism) != bool(spec.listener_factory):
                msg = "Custom listener mechanisms require a listener factory."
                raise ValueError(msg)
            if self.ingress_is_hint and self.collect is None:
                msg = "Source hint deliveries require a collector."
                raise ValueError(msg)
            seen.add(spec.kind)
            components.add(spec.component)


_cache_key: tuple[tuple[str, int], ...] | None = None
_cache_records: tuple[object, ...] = ()
_providers: dict[str, TriggerProvider] = {}


def _distribution_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def all_providers() -> tuple[TriggerProvider, ...]:
    """Discover hooks only for successfully loaded integration owners."""
    from lfx.extension.bundle_registry import get_default_registry

    global _cache_key, _cache_records, _providers  # noqa: PLW0603
    snapshot = get_default_registry().snapshot()
    key = tuple(sorted((name, id(record)) for name, record in snapshot.items()))
    if key == _cache_key:
        return tuple(_providers.values())
    owners = {
        integration.provider_id: integration
        for record in snapshot.values()
        for integration in record.integrations
        if integration.distribution
    }
    discovered: dict[str, TriggerProvider] = {}
    conflicts: set[str] = set()
    for entry in metadata.entry_points(group=ENTRY_POINT_GROUP):
        owner = owners.get(entry.name)
        distribution = getattr(entry, "dist", None)
        name = distribution.metadata.get("Name", "") if distribution is not None else ""
        if owner is None or not name or _distribution_name(name) != _distribution_name(owner.distribution or ""):
            continue
        try:
            provider = entry.load()
            record = snapshot.get(owner.bundle)
            declared_components = {
                capability.component_ref
                for capability in owner.capability_manifest.capabilities
                if capability.component_ref is not None
            }
            if (
                not isinstance(provider, TriggerProvider)
                or provider.provider_id != entry.name
                or provider.bundle != owner.bundle
                or record is None
                or any(
                    spec.component not in record.class_names or spec.component not in declared_components
                    for spec in provider.kinds
                )
            ):
                msg = "Trigger hooks do not match their loaded integration owner."
                raise ValueError(msg)
        except Exception as exc:  # noqa: BLE001 - an optional broken bundle cannot stop API startup
            logger.warning("Trigger provider %s was unavailable (%s)", entry.name, type(exc).__name__)
            conflicts.add(entry.name)
            continue
        if provider.provider_id in discovered:
            conflicts.add(provider.provider_id)
        discovered[provider.provider_id] = provider
    _providers = {name: provider for name, provider in discovered.items() if name not in conflicts}
    _cache_key = key
    # Retain records so a later reload cannot reuse their object ids.
    _cache_records = tuple(snapshot.values())
    return tuple(_providers.values())


def get_provider(provider_id: str) -> TriggerProvider | None:
    return next((provider for provider in all_providers() if provider.provider_id == provider_id), None)


def get_kind(kind: str) -> TriggerKind | None:
    return next((spec for provider in all_providers() for spec in provider.kinds if spec.kind == kind), None)


def source_kinds() -> frozenset[str]:
    from langflow.services.triggers.constants import GOOGLE_SOURCE_KINDS, MICROSOFT_SOURCE_KINDS

    return (
        MICROSOFT_SOURCE_KINDS
        | GOOGLE_SOURCE_KINDS
        | frozenset(spec.kind for provider in all_providers() for spec in provider.kinds)
    )


def collecting_kinds() -> frozenset[str]:
    from langflow.services.triggers.constants import GOOGLE_SOURCE_KINDS, MICROSOFT_SOURCE_KINDS

    return (
        MICROSOFT_SOURCE_KINDS
        | GOOGLE_SOURCE_KINDS
        | frozenset(
            spec.kind
            for provider in all_providers()
            if provider.collect is not None and provider.ingress_is_hint
            for spec in provider.kinds
        )
    )


def push_mechanisms() -> frozenset[str]:
    from langflow.services.triggers.constants import PUSH_MECHANISMS

    return PUSH_MECHANISMS | frozenset(
        spec.push_mechanism for provider in all_providers() for spec in provider.kinds if spec.push_mechanism
    )


def canvas_only_kinds() -> frozenset[str]:
    from langflow.services.triggers.constants import CANVAS_ONLY_KINDS

    return CANVAS_ONLY_KINDS | source_kinds()


def component_kind(bundle: str, component: str) -> str | None:
    return next(
        (
            spec.kind
            for provider in all_providers()
            if provider.bundle == bundle
            for spec in provider.kinds
            if spec.component == component
        ),
        None,
    )


def capability_ids(kind: str) -> frozenset[str]:
    from lfx.extension.bundle_registry import get_default_registry

    spec = get_kind(kind)
    if spec is None:
        return frozenset()
    return frozenset(
        capability.id
        for integration in get_default_registry().list_integrations()
        if integration.provider_id == kind.split(".", 1)[0]
        for capability in integration.capability_manifest.capabilities
        if capability.component_ref == spec.component
    )
